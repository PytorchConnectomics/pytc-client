from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT_DIR = Path(__file__).resolve().parent
_DEFAULT_LOG_PATH = _ROOT_DIR / ".logs" / "app" / "app-events.jsonl"
_ORIGINAL_STDOUT = sys.stdout
_ORIGINAL_STDERR = sys.stderr
_WRITE_LOCK = threading.Lock()
_CONFIG_LOCK = threading.Lock()
_CONFIGURED_COMPONENTS: set[str] = set()
_STDIO_REDIRECTED = False


def get_app_event_log_path() -> Path:
    raw_path = os.getenv("PYTC_APP_EVENT_LOG_PATH", "").strip()
    if raw_path:
        return Path(raw_path).expanduser().resolve(strict=False)
    return _DEFAULT_LOG_PATH


def _detect_stream_level(default_level: str, message: str) -> str:
    text = (message or "").strip()
    upper = text.upper()
    if upper.startswith("INFO:") or " INFO:" in upper:
        return "INFO"
    if upper.startswith("WARNING:") or upper.startswith("WARN:") or " WARNING:" in upper:
        return "WARNING"
    if upper.startswith("DEBUG:") or " DEBUG:" in upper:
        return "DEBUG"
    if upper.startswith("ERROR:") or " ERROR:" in upper:
        return "ERROR"
    if "TRACEBACK" in upper or "EXCEPTION" in upper or "FAILED" in upper:
        return "ERROR"
    return default_level.upper()


def _normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _normalize_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(item) for item in value]
    return str(value)


def append_app_event(
    *,
    component: str,
    event: str,
    level: str = "INFO",
    message: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    log_path = get_app_event_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "component": component,
        "event": event,
        "level": level.upper(),
        "message": message or "",
    }
    record.update(
        {
            key: _normalize_value(value)
            for key, value in fields.items()
            if value is not None
        }
    )

    with _WRITE_LOCK:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    return record


class _AppEventStream:
    def __init__(
        self,
        *,
        component: str,
        stream_name: str,
        level: str,
        original_stream,
    ) -> None:
        self.component = component
        self.stream_name = stream_name
        self.level = level
        self.original_stream = original_stream
        self._buffer = ""

    def write(self, data) -> int:
        text = str(data)
        if not text:
            return 0

        self.original_stream.write(text)
        self._buffer += text

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                append_app_event(
                    component=self.component,
                    event=f"{self.stream_name}_line",
                    level=_detect_stream_level(self.level, line),
                    message=line,
                    stream=self.stream_name,
                )

        return len(text)

    def flush(self) -> None:
        self.original_stream.flush()
        if self._buffer.strip():
            append_app_event(
                component=self.component,
                event=f"{self.stream_name}_line",
                level=_detect_stream_level(self.level, self._buffer),
                message=self._buffer,
                stream=self.stream_name,
            )
        self._buffer = ""

    def isatty(self) -> bool:
        return bool(getattr(self.original_stream, "isatty", lambda: False)())

    def fileno(self) -> int:
        return self.original_stream.fileno()


def configure_process_logging(component: str) -> Path:
    global _STDIO_REDIRECTED

    with _CONFIG_LOCK:
        if component in _CONFIGURED_COMPONENTS:
            return get_app_event_log_path()

        if not _STDIO_REDIRECTED:
            sys.stdout = _AppEventStream(
                component=component,
                stream_name="stdout",
                level="INFO",
                original_stream=_ORIGINAL_STDOUT,
            )
            sys.stderr = _AppEventStream(
                component=component,
                stream_name="stderr",
                level="ERROR",
                original_stream=_ORIGINAL_STDERR,
            )
            _STDIO_REDIRECTED = True

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        if not root_logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                stream=sys.stdout,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            )
        else:
            for handler in root_logger.handlers:
                if not isinstance(handler, logging.StreamHandler):
                    continue
                stream = getattr(handler, "stream", None)
                if stream is _ORIGINAL_STDOUT:
                    handler.setStream(sys.stdout)
                elif stream is _ORIGINAL_STDERR:
                    handler.setStream(sys.stderr)

        append_app_event(
            component=component,
            event="process_logging_configured",
            level="INFO",
            message=f"{component} logging configured",
            log_path=str(get_app_event_log_path()),
            configured_at_ms=round(time.time() * 1000),
        )
        _CONFIGURED_COMPONENTS.add(component)
        return get_app_event_log_path()
