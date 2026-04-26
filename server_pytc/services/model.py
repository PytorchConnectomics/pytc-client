import atexit
import pathlib
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any
from urllib import error as urllib_error, request as urllib_request

import psutil
from app_event_logger import append_app_event

# Track spawned processes so we can stop/poll cleanly.
_training_process = None
_inference_process = None
_tensorboard_process = None
_temp_files = {
    "training": [],
    "inference": [],
}
_RUNTIME_LOG_LIMIT = 2000
_TENSORBOARD_LOG_LIMIT = 200
_TENSORBOARD_HOST = "127.0.0.1"
_TENSORBOARD_BIND_HOST = "0.0.0.0"
_TENSORBOARD_PREFERRED_PORT = 6006
_TENSORBOARD_START_TIMEOUT_SECONDS = 15.0
_TENSORBOARD_POLL_INTERVAL_SECONDS = 0.25
_runtime_lock = threading.Lock()
_tensorboard_lock = threading.Lock()


def _new_runtime_state():
    return {
        "lines": deque(maxlen=_RUNTIME_LOG_LIMIT),
        "lineCount": 0,
        "phase": "idle",
        "pid": None,
        "exitCode": None,
        "command": None,
        "cwd": None,
        "configPath": None,
        "configOriginPath": None,
        "startedAt": None,
        "endedAt": None,
        "lastUpdatedAt": None,
        "lastError": None,
        "metadata": {},
    }


_runtime_state = {
    "training": _new_runtime_state(),
    "inference": _new_runtime_state(),
}


def _new_tensorboard_state():
    return {
        "phase": "idle",
        "pid": None,
        "port": None,
        "url": None,
        "command": None,
        "logdirSpec": None,
        "startedAt": None,
        "endedAt": None,
        "lastUpdatedAt": None,
        "lastError": None,
        "lineCount": 0,
        "lines": deque(maxlen=_TENSORBOARD_LOG_LIMIT),
    }


_tensorboard_state = _new_tensorboard_state()
_tensorboard_sources: dict[str, dict[str, str]] = {}
_DIRECT_VOLUME_SUFFIXES = (
    ".h5",
    ".hdf5",
    ".hdf",
    ".tif",
    ".tiff",
    ".ome.tif",
    ".ome.tiff",
    ".zarr",
    ".n5",
    ".npy",
    ".npz",
    ".nii",
    ".nii.gz",
    ".mrc",
    ".map",
    ".rec",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
)
_PREDICTION_OUTPUT_SUFFIXES = (
    ".h5",
    ".hdf5",
    ".hdf",
    ".tif",
    ".tiff",
    ".ome.tif",
    ".ome.tiff",
    ".zarr",
    ".n5",
    ".npy",
    ".npz",
    ".nii",
    ".nii.gz",
    ".mrc",
    ".map",
    ".rec",
)
_DIRECT_VOLUME_CONFIG_PATHS = {
    ("DATASET", "IMAGE_NAME"): "image",
    ("DATASET", "LABEL_NAME"): "label",
    ("DATASET", "VALID_MASK_NAME"): "label",
    ("INFERENCE", "IMAGE_NAME"): "image",
}
_FRACTIONAL_FLOAT_CONFIG_PATHS = {
    ("DATASET", "VALID_RATIO"),
    ("DATASET", "REJECT_SAMPLING", "P"),
    ("DATASET", "MEAN"),
    ("DATASET", "STD"),
    ("SOLVER", "BASE_LR"),
    ("SOLVER", "WEIGHT_DECAY"),
    ("SOLVER", "MOMENTUM"),
    ("SOLVER", "WARMUP_FACTOR"),
}
_VALID_INFERENCE_AUG_NUMS = (4, 8, 16)


def _project_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent.parent


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _level_for_log_text(text: str | None, *, default: str = "INFO") -> str:
    normalized = (text or "").upper()
    if any(
        needle in normalized
        for needle in (
            "TRACEBACK",
            "EXCEPTION",
            "ERROR",
            "FAILED",
            "UNICODEDECODEERROR",
        )
    ):
        return "ERROR"
    if "WARN" in normalized:
        return "WARNING"
    return default


def _get_runtime_process(kind: str):
    if kind == "training":
        return _training_process
    return _inference_process


def _clear_runtime_process(kind: str, process=None):
    global _training_process, _inference_process

    if kind == "training":
        if process is None or _training_process is process:
            _training_process = None
        return

    if process is None or _inference_process is process:
        _inference_process = None


def _reset_runtime_state(kind: str, *, phase: str = "idle", metadata: dict | None = None):
    state = _new_runtime_state()
    timestamp = _utc_now()
    state["phase"] = phase
    state["startedAt"] = timestamp if phase != "idle" else None
    state["lastUpdatedAt"] = timestamp
    state["metadata"] = metadata or {}
    with _runtime_lock:
        _runtime_state[kind] = state


def _update_runtime_state(kind: str, **updates):
    with _runtime_lock:
        state = _runtime_state[kind]
        for key, value in updates.items():
            if key == "metadata" and isinstance(value, dict):
                state["metadata"] = value
            else:
                state[key] = value
        state["lastUpdatedAt"] = _utc_now()


def _merge_runtime_metadata(kind: str, **updates) -> dict[str, Any]:
    clean_updates = {
        key: value
        for key, value in updates.items()
        if value is not None and value != ""
    }
    with _runtime_lock:
        state = _runtime_state[kind]
        metadata = dict(state.get("metadata") or {})
        metadata.update(clean_updates)
        state["metadata"] = metadata
        state["lastUpdatedAt"] = _utc_now()
        return dict(metadata)


def _runtime_event_fields(kind: str) -> dict[str, Any]:
    with _runtime_lock:
        state = _runtime_state[kind]
        return {
            "runtime_kind": kind,
            "runtime_phase": state["phase"],
            "runtime_pid": state["pid"],
            "runtime_exit_code": state["exitCode"],
            "runtime_config_path": state["configPath"],
            "runtime_config_origin_path": state["configOriginPath"],
        }


def _emit_runtime_app_event(
    kind: str,
    event: str,
    message: str,
    *,
    level: str | None = None,
    **fields,
):
    append_app_event(
        component="server_pytc",
        event=event,
        level=level or _level_for_log_text(message),
        message=message,
        **_runtime_event_fields(kind),
        **fields,
    )


def _append_runtime_log(
    kind: str,
    line: str,
    *,
    event: str = "runtime_log_line",
    level: str | None = None,
    source: str = "runtime",
    **fields,
):
    timestamp = _utc_now()
    text = "" if line is None else str(line).rstrip("\n")
    effective_level = level or _level_for_log_text(text)
    entry = f"[{timestamp}] {text}" if text else f"[{timestamp}]"
    line_index = None
    with _runtime_lock:
        state = _runtime_state[kind]
        state["lines"].append(entry)
        state["lineCount"] += 1
        state["lastUpdatedAt"] = timestamp
        if text and effective_level == "ERROR":
            state["lastError"] = text
        line_index = state["lineCount"]

    if text:
        _emit_runtime_app_event(
            kind,
            event,
            text,
            level=effective_level,
            source=source,
            runtime_line_index=line_index,
            runtime_line_timestamp=timestamp,
            **fields,
        )


def _append_runtime_event(
    kind: str,
    message: str,
    *,
    event: str = "runtime_event",
    level: str = "INFO",
    **fields,
):
    _append_runtime_log(
        kind,
        f"[MODEL.PY] {message}",
        event=event,
        level=level,
        source="model",
        **fields,
    )


def _set_runtime_error(kind: str, message: str):
    _update_runtime_state(kind, lastError=message)
    _append_runtime_event(
        kind,
        f"ERROR: {message}",
        event="runtime_error",
        level="ERROR",
    )


def _get_runtime_snapshot(kind: str) -> dict[str, Any]:
    process = _get_runtime_process(kind)
    is_running = bool(process and process.poll() is None)
    with _runtime_lock:
        state = _runtime_state[kind]
        phase = state["phase"]
        exit_code = state["exitCode"]
        ended_at = state["endedAt"]

        # Reconcile: if the process has exited but the log-reader thread
        # hasn't updated the state yet, derive phase from the process itself.
        if not is_running and phase == "running" and process is not None:
            rc = process.returncode
            phase = "finished" if rc == 0 else "failed"
            exit_code = rc
            ended_at = state["endedAt"] or _utc_now()

        lines = list(state["lines"])
        snapshot = {
            "isRunning": is_running,
            "phase": phase,
            "pid": process.pid if is_running else state["pid"],
            "exitCode": exit_code,
            "command": state["command"],
            "cwd": state["cwd"],
            "configPath": state["configPath"],
            "configOriginPath": state["configOriginPath"],
            "startedAt": state["startedAt"],
            "endedAt": ended_at,
            "lastUpdatedAt": state["lastUpdatedAt"],
            "lineCount": state["lineCount"],
            "lastError": state["lastError"],
            "metadata": dict(state["metadata"]),
            "lines": lines,
            "text": "\n".join(lines),
        }
    if kind == "training" and not snapshot["isRunning"]:
        metadata = snapshot.get("metadata") or {}
        if not metadata.get("checkpointPath"):
            latest_checkpoint = _find_latest_checkpoint(metadata.get("outputPath"))
            if latest_checkpoint:
                metadata = _merge_runtime_metadata(
                    kind,
                    checkpointPath=latest_checkpoint,
                    latestCheckpointPath=latest_checkpoint,
                    latestCheckpointName=pathlib.Path(latest_checkpoint).name,
                )
                snapshot["metadata"] = metadata
    if kind == "inference" and not snapshot["isRunning"]:
        metadata = snapshot.get("metadata") or {}
        if not (metadata.get("predictionPath") or metadata.get("latestPredictionPath")):
            latest_prediction = _find_latest_prediction_output(metadata.get("outputPath"))
            if latest_prediction:
                metadata = _merge_runtime_metadata(
                    kind,
                    predictionPath=latest_prediction,
                    latestPredictionPath=latest_prediction,
                    latestPredictionName=pathlib.Path(latest_prediction).name,
                )
                snapshot["metadata"] = metadata
    return snapshot


def _tensorboard_sources_payload() -> dict[str, dict[str, str | bool]]:
    payload: dict[str, dict[str, str | bool]] = {}
    for name, source in _tensorboard_sources.items():
        path = pathlib.Path(source["path"])
        payload[name] = {
            "name": source["name"],
            "path": str(path),
            "exists": path.exists(),
            "registeredAt": source["registeredAt"],
        }
    return payload


def _update_tensorboard_state(**updates):
    with _tensorboard_lock:
        for key, value in updates.items():
            if key == "lines":
                _tensorboard_state["lines"] = deque(
                    value,
                    maxlen=_TENSORBOARD_LOG_LIMIT,
                )
            else:
                _tensorboard_state[key] = value
        _tensorboard_state["lastUpdatedAt"] = _utc_now()


def _append_tensorboard_log(line: str):
    timestamp = _utc_now()
    text = "" if line is None else str(line).rstrip("\n")
    entry = f"[{timestamp}] {text}" if text else f"[{timestamp}]"
    line_index = None
    phase = None
    pid = None
    port = None
    url = None
    with _tensorboard_lock:
        _tensorboard_state["lines"].append(entry)
        _tensorboard_state["lineCount"] += 1
        _tensorboard_state["lastUpdatedAt"] = timestamp
        line_index = _tensorboard_state["lineCount"]
        phase = _tensorboard_state["phase"]
        pid = _tensorboard_state["pid"]
        port = _tensorboard_state["port"]
        url = _tensorboard_state["url"]

    if text:
        append_app_event(
            component="server_pytc",
            event="tensorboard_log_line",
            level=_level_for_log_text(text),
            message=text,
            source="tensorboard",
            tensorboard_phase=phase,
            tensorboard_pid=pid,
            tensorboard_port=port,
            tensorboard_url=url,
            tensorboard_line_index=line_index,
            tensorboard_line_timestamp=timestamp,
        )


def _set_tensorboard_error(message: str):
    _update_tensorboard_state(lastError=message)
    _append_tensorboard_log(f"[TENSORBOARD] ERROR: {message}")


def _load_yaml_config(config_text: str) -> dict[str, Any]:
    yaml = _load_yaml_module()
    if yaml is None:
        return {}

    try:
        config_obj = yaml.safe_load(config_text) or {}
    except Exception:
        return {}

    return config_obj if isinstance(config_obj, dict) else {}


def _load_yaml_module():
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    return yaml


def _load_yaml_config_from_path(path_value: pathlib.Path | None) -> dict[str, Any]:
    if path_value is None or not path_value.exists():
        return {}
    try:
        return _load_yaml_config(path_value.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_nested_value(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    cursor: Any = data
    for key in path:
        if not isinstance(cursor, dict) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


def _set_nested_value(data: dict[str, Any], path: tuple[str, ...], value: Any) -> bool:
    if not path:
        return False
    cursor: Any = data
    for key in path[:-1]:
        if not isinstance(cursor, dict):
            return False
        if key not in cursor or not isinstance(cursor[key], dict):
            cursor[key] = {}
        cursor = cursor[key]
    if not isinstance(cursor, dict):
        return False
    cursor[path[-1]] = value
    return True


def _path_label(path: tuple[str, ...]) -> str:
    return ".".join(path)


def _config_path_exists(path_value: Any) -> bool:
    if not isinstance(path_value, str) or not path_value.strip():
        return False
    try:
        return pathlib.Path(path_value).expanduser().exists()
    except Exception:
        return False


def _resolve_missing_direct_volume_path(path_value: Any, role: str) -> str | None:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    candidate = pathlib.Path(path_value).expanduser()
    if candidate.exists():
        return str(candidate.resolve())

    suffix = candidate.suffix.lower()
    if suffix not in _DIRECT_VOLUME_SUFFIXES:
        return None

    parent = candidate.parent
    stem = candidate.stem
    if not parent.exists():
        return None

    role_suffixes = (
        ("_im", "_img", "_image")
        if role == "image"
        else ("_seg", "_mask", "_label", "_gt", "_consensus")
    )

    for extra in role_suffixes:
        maybe = parent / f"{stem}{extra}{suffix}"
        if maybe.exists():
            return str(maybe.resolve())

    matches = sorted(parent.glob(f"{stem}_*{suffix}"))
    if not matches:
        return None

    preferred = []
    for extra in role_suffixes:
        preferred.extend([match for match in matches if match.stem.endswith(extra)])
    unique_preferred = list(dict.fromkeys(preferred))
    if len(unique_preferred) == 1:
        return str(unique_preferred[0].resolve())
    if len(matches) == 1:
        return str(matches[0].resolve())
    return None


def _sanitize_fractional_float_paths(
    config_obj: dict[str, Any],
    origin_obj: dict[str, Any],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    if not origin_obj:
        return changes

    for path in _FRACTIONAL_FLOAT_CONFIG_PATHS:
        current_value = _get_nested_value(config_obj, path)
        origin_value = _get_nested_value(origin_obj, path)
        if not isinstance(origin_value, float) or isinstance(current_value, bool):
            continue
        if not isinstance(current_value, int):
            continue
        if float(origin_value).is_integer():
            continue
        if float(current_value) == float(origin_value):
            continue
        _set_nested_value(config_obj, path, float(origin_value))
        changes.append(
            {
                "path": _path_label(path),
                "old_value": current_value,
                "new_value": float(origin_value),
                "reason": "restored_fractional_origin_value",
            }
        )

    return changes


def _sanitize_direct_volume_paths(
    config_obj: dict[str, Any],
    origin_obj: dict[str, Any],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    for path, role in _DIRECT_VOLUME_CONFIG_PATHS.items():
        current_value = _get_nested_value(config_obj, path)
        if not isinstance(current_value, str) or not current_value.strip():
            continue
        if _config_path_exists(current_value):
            continue

        origin_value = _get_nested_value(origin_obj, path)
        replacement = None
        reason = None
        if isinstance(origin_value, str) and origin_value.strip() and _config_path_exists(
            origin_value
        ):
            replacement = origin_value
            reason = "restored_existing_origin_path"
        else:
            resolved = _resolve_missing_direct_volume_path(current_value, role)
            if resolved:
                replacement = resolved
                reason = "resolved_missing_direct_volume_path"

        if replacement and replacement != current_value:
            _set_nested_value(config_obj, path, replacement)
            changes.append(
                {
                    "path": _path_label(path),
                    "old_value": current_value,
                    "new_value": replacement,
                    "reason": reason,
                }
            )

    return changes


def _sanitize_inference_aug_num(
    config_obj: dict[str, Any],
    origin_obj: dict[str, Any],
) -> list[dict[str, Any]]:
    path = ("INFERENCE", "AUG_NUM")
    current_value = _get_nested_value(config_obj, path)
    if not isinstance(current_value, int) or current_value in _VALID_INFERENCE_AUG_NUMS:
        return []

    origin_value = _get_nested_value(origin_obj, path)
    if isinstance(origin_value, int) and origin_value in _VALID_INFERENCE_AUG_NUMS:
        replacement = origin_value
        reason = "restored_valid_origin_aug_num"
    else:
        replacement = min(
            _VALID_INFERENCE_AUG_NUMS,
            key=lambda option: abs(option - current_value),
        )
        reason = "coerced_to_supported_aug_num"

    _set_nested_value(config_obj, path, replacement)
    return [
        {
            "path": _path_label(path),
            "old_value": current_value,
            "new_value": replacement,
            "reason": reason,
        }
    ]


def _sanitize_runtime_config_text(
    config_text: str,
    config_origin_path: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    yaml = _load_yaml_module()
    if yaml is None:
        return config_text, []

    config_obj = _load_yaml_config(config_text)
    if not config_obj:
        return config_text, []

    origin_obj = _load_yaml_config_from_path(
        _resolve_config_origin_path(config_origin_path)
    )
    changes: list[dict[str, Any]] = []
    changes.extend(_sanitize_fractional_float_paths(config_obj, origin_obj))
    changes.extend(_sanitize_direct_volume_paths(config_obj, origin_obj))
    changes.extend(_sanitize_inference_aug_num(config_obj, origin_obj))

    if not changes:
        return config_text, []

    sanitized_text = yaml.safe_dump(
        config_obj,
        sort_keys=False,
        allow_unicode=False,
    )
    return sanitized_text, changes


def _looks_like_direct_volume(path_value: Any) -> bool:
    text = str(path_value or "").strip().lower()
    return bool(text) and text.endswith(_DIRECT_VOLUME_SUFFIXES)


def _detect_chunk_tile_mismatch(config_text: str) -> dict[str, Any] | None:
    config_obj = _load_yaml_config(config_text)
    dataset = config_obj.get("DATASET") or {}
    if not isinstance(dataset, dict):
        return None

    do_chunk_title = dataset.get("DO_CHUNK_TITLE")
    if do_chunk_title in (None, False, 0, "0", "false", "False"):
        return None

    image_name = dataset.get("IMAGE_NAME")
    label_name = dataset.get("LABEL_NAME")
    if not any(_looks_like_direct_volume(value) for value in (image_name, label_name)):
        return None

    return {
        "code": "tile_dataset_direct_volume_mismatch",
        "message": (
            "DATASET.DO_CHUNK_TITLE is enabled, so PyTC will use TileDataset and expect "
            "JSON tile manifests, but IMAGE_NAME/LABEL_NAME point to direct volume files. "
            "That leads to json.load(...) on the H5/TIFF path and crashes with a decode error."
        ),
        "do_chunk_title": do_chunk_title,
        "image_name": image_name,
        "label_name": label_name,
    }


def _resolve_tensorboard_log_dir(path_value: str | None) -> pathlib.Path | None:
    if not path_value or not str(path_value).strip():
        return None

    candidate = pathlib.Path(str(path_value).strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (_project_root() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _register_tensorboard_source(source_key: str, log_dir: str) -> str:
    resolved = _resolve_tensorboard_log_dir(log_dir)
    if resolved is None:
        raise ValueError("TensorBoard log directory is required")

    _tensorboard_sources[source_key] = {
        "name": source_key,
        "path": str(resolved),
        "registeredAt": _utc_now(),
    }
    _append_tensorboard_log(
        f"[TENSORBOARD] Watching {source_key} logs at {resolved}"
    )
    append_app_event(
        component="server_pytc",
        event="tensorboard_source_registered",
        level="INFO",
        message=f"Registered TensorBoard source {source_key}",
        source="tensorboard",
        tensorboard_source_key=source_key,
        tensorboard_source_path=str(resolved),
    )
    return str(resolved)


def _build_tensorboard_logdir_spec() -> str | None:
    parts: list[str] = []
    for source_key in sorted(_tensorboard_sources):
        source = _tensorboard_sources[source_key]
        parts.append(f"{source['name']}:{source['path']}")
    return ",".join(parts) if parts else None


def _is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((_TENSORBOARD_HOST, port))
        except OSError:
            return False
    return True


def _pick_tensorboard_port(preferred: int | None = None) -> int:
    candidate_ports = []
    if preferred:
        candidate_ports.append(int(preferred))
    if _TENSORBOARD_PREFERRED_PORT not in candidate_ports:
        candidate_ports.append(_TENSORBOARD_PREFERRED_PORT)

    for port in candidate_ports:
        if _is_port_available(port):
            return port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((_TENSORBOARD_HOST, 0))
        return int(sock.getsockname()[1])


def _tensorboard_url_for_port(port: int | None) -> str | None:
    if not port:
        return None
    return f"http://{_TENSORBOARD_HOST}:{int(port)}/"


def _wait_for_tensorboard_ready(port: int, process: subprocess.Popen) -> bool:
    url = _tensorboard_url_for_port(port)
    deadline = time.monotonic() + _TENSORBOARD_START_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False

        try:
            with urllib_request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return True
        except urllib_error.URLError:
            pass
        except Exception:
            pass

        time.sleep(_TENSORBOARD_POLL_INTERVAL_SECONDS)

    return False


def _terminate_managed_tensorboard():
    global _tensorboard_process

    process = _tensorboard_process
    if process is None:
        return

    try:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    except Exception as exc:
        _append_tensorboard_log(
            f"[TENSORBOARD] Error terminating existing process: {exc}"
        )
    finally:
        if _tensorboard_process is process:
            _tensorboard_process = None


def _watch_tensorboard_process(process: subprocess.Popen):
    global _tensorboard_process

    try:
        if process.stdout is not None:
            for line in process.stdout:
                _append_tensorboard_log(line.rstrip())
        process.wait()
    except Exception as exc:
        _append_tensorboard_log(
            f"[TENSORBOARD] Error reading TensorBoard output: {exc}"
        )
        return

    exit_code = process.returncode
    with _tensorboard_lock:
        current_pid = _tensorboard_state["pid"]
        is_current = _tensorboard_process is process
        if is_current:
            _tensorboard_process = None

    if current_pid != process.pid and not is_current:
        return

    updates = {
        "phase": "finished" if exit_code == 0 else "failed",
        "pid": None,
        "endedAt": _utc_now(),
    }
    if exit_code not in (None, 0):
        updates["lastError"] = f"TensorBoard exited with code {exit_code}"
    _update_tensorboard_state(**updates)
    append_app_event(
        component="server_pytc",
        event="tensorboard_process_finished",
        level="INFO" if exit_code == 0 else "ERROR",
        message="TensorBoard process exited",
        source="tensorboard",
        tensorboard_exit_code=exit_code,
        tensorboard_pid=process.pid,
    )


def _get_tensorboard_snapshot() -> dict[str, Any]:
    process = _tensorboard_process
    is_running = bool(process and process.poll() is None)
    with _tensorboard_lock:
        phase = _tensorboard_state["phase"]
        pid = _tensorboard_state["pid"]
        ended_at = _tensorboard_state["endedAt"]
        last_error = _tensorboard_state["lastError"]
        lines = list(_tensorboard_state["lines"])
        line_count = _tensorboard_state["lineCount"]
        port = _tensorboard_state["port"]

        if not is_running and phase in {"starting", "running"} and process is not None:
            exit_code = process.returncode
            phase = "finished" if exit_code == 0 else "failed"
            pid = None
            ended_at = ended_at or _utc_now()
            if exit_code not in (None, 0) and not last_error:
                last_error = f"TensorBoard exited with code {exit_code}"

        snapshot = {
            "isRunning": is_running,
            "phase": phase,
            "pid": process.pid if is_running else pid,
            "port": port,
            "url": _tensorboard_state["url"] or _tensorboard_url_for_port(port),
            "command": _tensorboard_state["command"],
            "logdirSpec": _tensorboard_state["logdirSpec"],
            "startedAt": _tensorboard_state["startedAt"],
            "endedAt": ended_at,
            "lastUpdatedAt": _tensorboard_state["lastUpdatedAt"],
            "lastError": last_error,
            "lineCount": line_count,
            "lines": lines,
            "text": "\n".join(lines),
            "sources": _tensorboard_sources_payload(),
        }
    return snapshot


def _pytc_script_path() -> pathlib.Path:
    script_path = _project_root() / "pytorch_connectomics" / "scripts" / "main.py"
    if not script_path.exists():
        raise FileNotFoundError(f"PyTC script not found at {script_path}")
    return script_path


def _resolve_config_origin_path(config_origin_path: str | None) -> pathlib.Path | None:
    if not config_origin_path:
        return None

    candidate = pathlib.Path(str(config_origin_path).strip())
    if not str(candidate):
        return None

    if candidate.is_absolute():
        resolved = candidate.resolve()
        return resolved if resolved.exists() else None

    pytc_root = _project_root() / "pytorch_connectomics"
    resolved = (pytc_root / candidate).resolve()
    try:
        resolved.relative_to(pytc_root.resolve())
    except ValueError:
        return None
    return resolved if resolved.exists() else None


def _write_temp_config(
    config_text: str, label: str, config_origin_path: str | None = None
) -> str:
    if not config_text or not str(config_text).strip():
        raise ValueError(f"{label} config is required")

    origin = _resolve_config_origin_path(config_origin_path)
    suffix = origin.suffix if origin and origin.suffix else ".yaml"
    temp_kwargs = {"delete": False, "mode": "w", "suffix": suffix}
    if origin is not None:
        temp_kwargs["dir"] = str(origin.parent)
        temp_kwargs["prefix"] = f".__pytc_runtime_{label}_"

    try:
        with tempfile.NamedTemporaryFile(**temp_kwargs) as tmp:
            tmp.write(config_text)
            path = tmp.name
    except OSError:
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=suffix) as tmp:
            tmp.write(config_text)
            path = tmp.name

    _temp_files[label].append(path)
    return path


def _build_cli_arguments(
    arguments: dict[str, Any], blocked_flags: set[str] | None = None
) -> list[str]:
    blocked = {flag.lower().replace("_", "-") for flag in (blocked_flags or set())}
    cli_args: list[str] = []

    for key, value in (arguments or {}).items():
        if value is None or value == "":
            continue

        flag_name = str(key).strip().replace("_", "-").lower()
        if not flag_name or flag_name in blocked:
            continue
        flag = f"--{flag_name}"

        if isinstance(value, bool):
            if value:
                cli_args.append(flag)
            continue

        if isinstance(value, (list, tuple)):
            for item in value:
                cli_args.extend([flag, str(item)])
            continue

        cli_args.extend([flag, str(value)])

    return cli_args


def _start_logged_process(command: list[str], cwd: pathlib.Path, label: str, kind: str):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(cwd),
    )
    _update_runtime_state(
        kind,
        phase="running",
        pid=process.pid,
        command=" ".join(command),
        cwd=str(cwd),
        exitCode=None,
        endedAt=None,
        lastError=None,
    )
    _append_runtime_event(kind, f"Spawned {label.lower()} process PID {process.pid}")
    _emit_runtime_app_event(
        kind,
        "runtime_process_spawned",
        f"{label} subprocess spawned",
        level="INFO",
        source="subprocess",
        command=command,
        cwd=str(cwd),
        subprocess_pid=process.pid,
        subprocess_label=label,
    )

    def _log_subprocess_output():
        print(f"[MODEL.PY] === {label} subprocess output (PID {process.pid}) ===")
        try:
            if process.stdout is not None:
                for line in process.stdout:
                    _append_runtime_log(
                        kind,
                        line.rstrip(),
                        event="runtime_output_line",
                        source="subprocess",
                        stream="stdout",
                        subprocess_label=label,
                        subprocess_pid=process.pid,
                    )
                    print(f"[{label}:{process.pid}] {line.rstrip()}")
            process.wait()
            exit_code = process.returncode
            if exit_code == 0:
                discovered_artifacts = _discover_runtime_artifacts(kind)
                if discovered_artifacts:
                    merged_metadata = _merge_runtime_metadata(
                        kind,
                        **discovered_artifacts,
                    )
                    artifact_path = (
                        discovered_artifacts.get("latestCheckpointPath")
                        or discovered_artifacts.get("latestPredictionPath")
                    )
                    artifact_label = (
                        "checkpoint" if kind == "training" else "prediction output"
                    )
                    _append_runtime_event(
                        kind,
                        f"Latest {artifact_label} discovered: {artifact_path}",
                        event="runtime_artifact_discovered",
                        checkpoint_path=discovered_artifacts.get("latestCheckpointPath"),
                        prediction_path=discovered_artifacts.get("latestPredictionPath"),
                        output_path=merged_metadata.get("outputPath"),
                    )
                elif kind == "training":
                    output_path = (_get_runtime_snapshot(kind).get("metadata") or {}).get(
                        "outputPath"
                    )
                    _append_runtime_event(
                        kind,
                        f"No checkpoint artifact was found in {output_path or 'the training output directory'}.",
                        event="runtime_artifact_missing",
                        level="WARNING",
                        output_path=output_path,
                    )
            _update_runtime_state(
                kind,
                phase="finished" if exit_code == 0 else "failed",
                exitCode=exit_code,
                endedAt=_utc_now(),
            )
            _append_runtime_event(
                kind,
                f"{label} subprocess finished with exit code: {exit_code}",
                event="runtime_process_finished",
            )
            _emit_runtime_app_event(
                kind,
                "runtime_process_finished",
                f"{label} subprocess exited",
                level="INFO" if exit_code == 0 else "ERROR",
                source="subprocess",
                subprocess_label=label,
                subprocess_pid=process.pid,
                exit_code=exit_code,
            )
            _clear_runtime_process(kind, process)
            print(
                f"[MODEL.PY] === {label} subprocess finished with exit code: {process.returncode} ==="
            )
        except Exception as exc:
            _set_runtime_error(kind, f"Error reading {label} subprocess output: {exc}")
            print(f"[MODEL.PY] Error reading {label} subprocess output: {exc}")

    threading.Thread(target=_log_subprocess_output, daemon=True).start()
    return process


def _extract_output_path_from_yaml(config_text: str, mode: str) -> str | None:
    config_obj = _load_yaml_config(config_text)
    if not config_obj:
        return None

    if mode == "train":
        legacy = config_obj.get("DATASET", {}).get("OUTPUT_PATH")
        if legacy:
            return str(legacy)

        modern_dir = config_obj.get("monitor", {}).get("checkpoint", {}).get("dirpath")
        if modern_dir:
            return str(pathlib.Path(str(modern_dir)).parent)

    if mode == "test":
        legacy = config_obj.get("INFERENCE", {}).get("OUTPUT_PATH")
        if legacy:
            return str(legacy)

        modern_dir = (
            config_obj.get("inference", {})
            .get("save_prediction", {})
            .get("output_path")
        )
        if modern_dir:
            return str(modern_dir)

    return None


def _resolve_runtime_output_dir(path_value: str | None) -> pathlib.Path | None:
    if not path_value or not str(path_value).strip():
        return None

    candidate = pathlib.Path(str(path_value).strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (_project_root() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if candidate.is_file():
        return candidate.parent
    if candidate.exists():
        return candidate
    return None


def _find_latest_checkpoint(output_path: str | None) -> str | None:
    output_dir = _resolve_runtime_output_dir(output_path)
    if output_dir is None or not output_dir.exists():
        return None

    candidates: list[pathlib.Path] = []
    for pattern in ("checkpoint_*.pth.tar", "checkpoint_*.pth", "*.ckpt"):
        candidates.extend(path for path in output_dir.glob(pattern) if path.is_file())

    if not candidates:
        return None

    latest = max(candidates, key=lambda path: (path.stat().st_mtime, path.name))
    return str(latest.resolve())


def _path_has_prediction_suffix(path: pathlib.Path) -> bool:
    lower_name = path.name.lower()
    lower_path = str(path).lower()
    return lower_name.endswith(_PREDICTION_OUTPUT_SUFFIXES) or lower_path.endswith(
        (".ome.tif", ".ome.tiff", ".nii.gz")
    )


def _is_prediction_output_candidate(path: pathlib.Path) -> bool:
    if path.name.startswith("."):
        return False
    if not _path_has_prediction_suffix(path):
        return False
    if path.is_dir():
        return path.name.lower().endswith((".zarr", ".n5"))
    return path.is_file()


def _prediction_output_priority(path: pathlib.Path) -> tuple[float, int, str]:
    name = path.name.lower()
    preferred = 0
    if name.startswith("result_xy"):
        preferred = 3
    elif name.startswith("result"):
        preferred = 2
    elif "prediction" in name or "pred" in name:
        preferred = 1
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (mtime, preferred, path.name)


def _resolve_prediction_search_dir(path_value: str | None) -> pathlib.Path | None:
    if not path_value or not str(path_value).strip():
        return None

    candidate = pathlib.Path(str(path_value).strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (_project_root() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if _is_prediction_output_candidate(candidate):
        return candidate.parent
    if candidate.is_dir():
        return candidate
    if candidate.parent.exists():
        return candidate.parent
    return None


def _find_latest_prediction_output(output_path: str | None) -> str | None:
    if not output_path or not str(output_path).strip():
        return None

    requested = pathlib.Path(str(output_path).strip()).expanduser()
    if not requested.is_absolute():
        requested = (_project_root() / requested).resolve()
    else:
        requested = requested.resolve()
    if _is_prediction_output_candidate(requested):
        return str(requested)

    output_dir = _resolve_prediction_search_dir(output_path)
    if output_dir is None or not output_dir.exists():
        return None

    candidates: list[pathlib.Path] = []
    for child in output_dir.rglob("*"):
        if _is_prediction_output_candidate(child):
            candidates.append(child)

    if not candidates:
        return None

    latest = max(candidates, key=_prediction_output_priority)
    return str(latest.resolve())


def _discover_runtime_artifacts(kind: str) -> dict[str, Any]:
    snapshot = _get_runtime_snapshot(kind)
    metadata = snapshot.get("metadata") or {}
    output_path = metadata.get("outputPath")

    if kind == "inference":
        latest_prediction = _find_latest_prediction_output(output_path)
        if not latest_prediction:
            return {}
        return {
            "predictionPath": latest_prediction,
            "latestPredictionPath": latest_prediction,
            "latestPredictionName": pathlib.Path(latest_prediction).name,
        }

    if kind != "training":
        return {}

    latest_checkpoint = _find_latest_checkpoint(output_path)
    if not latest_checkpoint:
        return {}

    return {
        "checkpointPath": latest_checkpoint,
        "latestCheckpointPath": latest_checkpoint,
        "latestCheckpointName": pathlib.Path(latest_checkpoint).name,
    }


def _launch_tensorboard(log_dir: str | None, config_text: str, mode: str):
    resolved = log_dir or _extract_output_path_from_yaml(config_text, mode)
    if resolved:
        source_key = "training" if mode == "train" else "inference"
        try:
            status = initialize_tensorboard(resolved, source_key=source_key)
            _append_runtime_event(
                source_key,
                f"TensorBoard available at {status['url']}",
                event="tensorboard_ready",
                tensorboard_url=status["url"],
                tensorboard_port=status["port"],
            )
        except Exception as exc:
            _append_runtime_event(
                source_key,
                f"TensorBoard could not be started automatically: {exc}",
                event="tensorboard_error",
                level="ERROR",
            )
    return resolved


def start_training(payload: dict):
    print("\n========== MODEL.PY: START_TRAINING FUNCTION CALLED ==========")
    global _training_process

    print(f"[MODEL.PY] Input dict keys: {list(payload.keys())}")
    print(f"[MODEL.PY] Arguments: {payload.get('arguments', {})}")

    if _training_process and _training_process.poll() is None:
        print("[MODEL.PY] Existing training process detected, stopping it first...")
        stop_training()

    config_text = payload.get("trainingConfig", "")
    temp_filepath = None
    config_origin_path = payload.get("configOriginPath")
    config_corrections: list[dict[str, Any]] = []
    _reset_runtime_state(
        "training",
        phase="starting",
        metadata={
            "label": "training",
            "outputPath": payload.get("outputPath"),
            "logPath": payload.get("logPath"),
        },
    )

    try:
        current_dir = _project_root()
        script_path = _pytc_script_path()
        config_text, config_corrections = _sanitize_runtime_config_text(
            config_text,
            config_origin_path,
        )
        temp_filepath = _write_temp_config(
            config_text,
            "training",
            config_origin_path=config_origin_path,
        )
        _update_runtime_state(
            "training",
            configPath=temp_filepath,
            configOriginPath=config_origin_path,
        )
        _append_runtime_event("training", f"Config origin: {config_origin_path or 'none'}")
        _append_runtime_event("training", f"Staged config path: {temp_filepath}")
        if config_corrections:
            _append_runtime_event(
                "training",
                f"Sanitized staged training config with {len(config_corrections)} correction(s)",
                event="runtime_config_sanitized",
                level="WARNING",
                corrections=config_corrections,
            )

        command = [
            sys.executable,
            str(script_path),
            "--config-file",
            temp_filepath,
        ]
        command.extend(
            _build_cli_arguments(
                payload.get("arguments", {}),
                blocked_flags={"config", "config-file", "mode", "inference"},
            )
        )

        print(f"[MODEL.PY] Final training command: {' '.join(command)}")
        _append_runtime_event("training", f"Final training command: {' '.join(command)}")
        _emit_runtime_app_event(
            "training",
            "runtime_config_snapshot",
            "Training config staged",
            level="INFO",
            source="model",
            config_origin_path=config_origin_path,
            staged_config_path=temp_filepath,
            command=command,
            arguments=payload.get("arguments", {}) or {},
            output_path=payload.get("outputPath"),
            log_path=payload.get("logPath"),
            config_text=config_text,
            config_text_length=len(config_text or ""),
            config_line_count=(config_text or "").count("\n") + (1 if config_text else 0),
            config_sanitized=bool(config_corrections),
            config_corrections=config_corrections,
        )
        config_diagnostic = _detect_chunk_tile_mismatch(config_text)
        if config_diagnostic:
            _append_runtime_event(
                "training",
                config_diagnostic["message"],
                event="runtime_config_warning",
                level="WARNING",
                diagnostic=config_diagnostic,
            )
        _training_process = _start_logged_process(
            command,
            current_dir,
            "TRAINING",
            "training",
        )

        log_dir = _launch_tensorboard(payload.get("outputPath"), config_text, "train")
        if log_dir:
            _append_runtime_event("training", f"TensorBoard log dir: {log_dir}")
            print(f"[MODEL.PY] TensorBoard monitoring directory: {log_dir}")

        result = {"status": "started", "pid": _training_process.pid}
        print(f"[MODEL.PY] Returning: {result}")
        print("========== MODEL.PY: END OF START_TRAINING ==========\n")
        return result
    except Exception as exc:
        if temp_filepath and temp_filepath in _temp_files["training"]:
            cleanup_temp_files("training")
        _update_runtime_state("training", phase="failed", endedAt=_utc_now())
        _set_runtime_error("training", str(exc))
        print(f"[MODEL.PY] ✗ ERROR starting training process: {exc}")
        raise


def _stop_processes(matcher, description: str):
    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info["cmdline"] or []
                if not matcher(cmdline):
                    continue
                print(
                    f"Terminating process {proc.info['pid']}: {' '.join(cmdline)}"
                )
                proc.terminate()
                proc.wait(timeout=10)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
    except Exception as exc:
        print(f"Error stopping processes for '{description}': {exc}")


def _matches_pytc_mode_process(cmdline: list[str], mode: str) -> bool:
    try:
        script_path = str(_pytc_script_path())
    except FileNotFoundError:
        return False

    normalized = [str(part) for part in cmdline]
    if script_path not in normalized:
        return False

    # Support both the legacy "--mode train/test" CLI and the newer
    # "--inference" flag that PyTC now uses to switch the entrypoint into test mode.
    if "--mode" in normalized:
        mode_index = normalized.index("--mode")
        return mode_index + 1 < len(normalized) and normalized[mode_index + 1] == mode

    is_inference = "--inference" in normalized
    if mode == "test":
        return is_inference
    if mode == "train":
        return not is_inference
    return False


def stop_pytc_processes(mode: str):
    _stop_processes(
        lambda cmdline: _matches_pytc_mode_process(cmdline, mode),
        f"pytorch_connectomics mode={mode}",
    )


def stop_process_by_name(process_name):
    _stop_processes(
        lambda cmdline: process_name in " ".join(cmdline),
        process_name,
    )


def cleanup_temp_files(kind: str | None = None):
    """Clean up temporary files created during training/inference."""
    kinds = [kind] if kind else list(_temp_files.keys())
    for state_kind in kinds:
        for temp_file in _temp_files[state_kind][:]:
            try:
                pathlib.Path(temp_file).unlink(missing_ok=True)
                _temp_files[state_kind].remove(temp_file)
            except Exception as exc:
                print(f"Error cleaning up temp file {temp_file}: {exc}")


def stop_training():
    global _training_process

    if _training_process and _training_process.poll() is None:
        try:
            _append_runtime_event(
                "training", f"Terminating training process PID: {_training_process.pid}"
            )
            print(f"Terminating training process PID: {_training_process.pid}")
            _training_process.terminate()
            _training_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _append_runtime_event("training", "Force killing training process")
            print("Force killing training process...")
            _training_process.kill()
            _training_process.wait()
        except Exception as exc:
            _set_runtime_error("training", f"Error stopping training process: {exc}")
            print(f"Error stopping training process: {exc}")
        finally:
            _training_process = None

    stop_pytc_processes("train")
    cleanup_temp_files("training")
    _update_runtime_state("training", phase="stopped", endedAt=_utc_now())
    _append_runtime_event("training", "Training stop requested")
    return {"status": "stopped"}


def initialize_tensorboard(logPath: str | None = None, source_key: str = "manual"):
    global _tensorboard_process

    if logPath:
        resolved = _register_tensorboard_source(source_key, logPath)
    else:
        resolved = None

    logdir_spec = _build_tensorboard_logdir_spec()
    if not logdir_spec:
        raise ValueError(
            "No TensorBoard log directory is registered yet. Start a training or inference job first."
        )

    snapshot = _get_tensorboard_snapshot()
    if snapshot["isRunning"] and snapshot["logdirSpec"] == logdir_spec:
        return snapshot

    if snapshot["isRunning"] or snapshot["phase"] in {"starting", "failed", "finished"}:
        _terminate_managed_tensorboard()

    port = _pick_tensorboard_port(snapshot.get("port"))
    command = [
        sys.executable,
        "-m",
        "tensorboard.main",
        "--logdir_spec",
        logdir_spec,
        "--host",
        _TENSORBOARD_BIND_HOST,
        "--port",
        str(port),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(_project_root()),
    )
    _tensorboard_process = process
    _update_tensorboard_state(
        phase="starting",
        pid=process.pid,
        port=port,
        url=_tensorboard_url_for_port(port),
        command=" ".join(command),
        logdirSpec=logdir_spec,
        startedAt=_utc_now(),
        endedAt=None,
        lastError=None,
    )
    _append_tensorboard_log(
        f"[TENSORBOARD] Launching with logdir spec: {logdir_spec}"
    )
    append_app_event(
        component="server_pytc",
        event="tensorboard_launch",
        level="INFO",
        message="Launching TensorBoard",
        source="tensorboard",
        command=command,
        tensorboard_port=port,
        tensorboard_url=_tensorboard_url_for_port(port),
        tensorboard_logdir_spec=logdir_spec,
    )
    threading.Thread(
        target=_watch_tensorboard_process,
        args=(process,),
        daemon=True,
    ).start()

    if not _wait_for_tensorboard_ready(port, process):
        _terminate_managed_tensorboard()
        error_message = "TensorBoard did not become ready before the startup timeout."
        _update_tensorboard_state(
            phase="failed",
            pid=None,
            port=None,
            endedAt=_utc_now(),
        )
        _set_tensorboard_error(error_message)
        raise RuntimeError(error_message)

    _update_tensorboard_state(phase="running")
    if resolved:
        _append_tensorboard_log(
            f"[TENSORBOARD] Ready and watching {source_key} at {resolved}"
        )
    append_app_event(
        component="server_pytc",
        event="tensorboard_ready",
        level="INFO",
        message="TensorBoard is ready",
        source="tensorboard",
        tensorboard_port=port,
        tensorboard_url=_tensorboard_url_for_port(port),
        tensorboard_logdir_spec=logdir_spec,
    )
    return _get_tensorboard_snapshot()


def get_tensorboard():
    snapshot = _get_tensorboard_snapshot()
    return snapshot["url"] if snapshot["isRunning"] else None


def get_tensorboard_status():
    return _get_tensorboard_snapshot()


def stop_tensorboard(clear_sources: bool = False):
    _terminate_managed_tensorboard()
    if clear_sources:
        _tensorboard_sources.clear()
    _update_tensorboard_state(
        phase="stopped",
        pid=None,
        port=None,
        url=None,
        endedAt=_utc_now(),
        lastError=None,
    )


def start_inference(payload: dict):
    print("\n========== MODEL.PY: START_INFERENCE FUNCTION CALLED ==========")
    global _inference_process

    if _inference_process and _inference_process.poll() is None:
        print("[MODEL.PY] Existing inference process detected, stopping it first...")
        stop_inference()

    config_text = payload.get("inferenceConfig", "")
    temp_filepath = None
    config_origin_path = payload.get("configOriginPath")
    config_corrections: list[dict[str, Any]] = []
    _reset_runtime_state(
        "inference",
        phase="starting",
        metadata={
            "label": "inference",
            "outputPath": payload.get("outputPath"),
            "checkpointPath": payload.get("checkpointPath")
            or (payload.get("arguments") or {}).get("checkpoint"),
            "configOriginPath": config_origin_path,
            "workflowId": payload.get("workflow_id") or payload.get("workflowId"),
        },
    )

    try:
        current_dir = _project_root()
        script_path = _pytc_script_path()
        config_text, config_corrections = _sanitize_runtime_config_text(
            config_text,
            config_origin_path,
        )
        temp_filepath = _write_temp_config(
            config_text,
            "inference",
            config_origin_path=config_origin_path,
        )
        _update_runtime_state(
            "inference",
            configPath=temp_filepath,
            configOriginPath=config_origin_path,
        )
        _append_runtime_event(
            "inference", f"Config origin: {config_origin_path or 'none'}"
        )
        _append_runtime_event("inference", f"Staged config path: {temp_filepath}")
        if config_corrections:
            _append_runtime_event(
                "inference",
                f"Sanitized staged inference config with {len(config_corrections)} correction(s)",
                event="runtime_config_sanitized",
                level="WARNING",
                corrections=config_corrections,
            )

        arguments = dict(payload.get("arguments") or {})
        if payload.get("checkpointPath") and not arguments.get("checkpoint"):
            arguments["checkpoint"] = payload["checkpointPath"]

        command = [
            sys.executable,
            str(script_path),
            "--config-file",
            temp_filepath,
            "--inference",
        ]
        command.extend(
            _build_cli_arguments(
                arguments,
                blocked_flags={"config", "config-file", "mode", "inference"},
            )
        )

        print(f"[MODEL.PY] Final inference command: {' '.join(command)}")
        _append_runtime_event("inference", f"Final inference command: {' '.join(command)}")
        _emit_runtime_app_event(
            "inference",
            "runtime_config_snapshot",
            "Inference config staged",
            level="INFO",
            source="model",
            config_origin_path=config_origin_path,
            staged_config_path=temp_filepath,
            command=command,
            arguments=arguments,
            output_path=payload.get("outputPath"),
            checkpoint_path=payload.get("checkpointPath"),
            config_text=config_text,
            config_text_length=len(config_text or ""),
            config_line_count=(config_text or "").count("\n") + (1 if config_text else 0),
            config_sanitized=bool(config_corrections),
            config_corrections=config_corrections,
        )
        config_diagnostic = _detect_chunk_tile_mismatch(config_text)
        if config_diagnostic:
            _append_runtime_event(
                "inference",
                config_diagnostic["message"],
                event="runtime_config_warning",
                level="WARNING",
                diagnostic=config_diagnostic,
            )
        _inference_process = _start_logged_process(
            command,
            current_dir,
            "INFERENCE",
            "inference",
        )
        log_dir = _launch_tensorboard(payload.get("outputPath"), config_text, "test")
        if log_dir:
            _append_runtime_event("inference", f"TensorBoard log dir: {log_dir}")
            print(f"[MODEL.PY] TensorBoard monitoring directory: {log_dir}")
        result = {"status": "started", "pid": _inference_process.pid}
        print(f"[MODEL.PY] Returning: {result}")
        print("========== MODEL.PY: END OF START_INFERENCE ==========\n")
        return result
    except Exception as exc:
        if temp_filepath and temp_filepath in _temp_files["inference"]:
            cleanup_temp_files("inference")
        _update_runtime_state("inference", phase="failed", endedAt=_utc_now())
        _set_runtime_error("inference", str(exc))
        print(f"[MODEL.PY] ✗ ERROR starting inference process: {exc}")
        raise


def get_training_status():
    snapshot = _get_runtime_snapshot("training")
    return {
        "isRunning": snapshot["isRunning"],
        "pid": snapshot["pid"],
        "exitCode": snapshot["exitCode"],
        "phase": snapshot["phase"],
        "lastError": snapshot["lastError"],
    }


def get_inference_status():
    snapshot = _get_runtime_snapshot("inference")
    return {
        "isRunning": snapshot["isRunning"],
        "pid": snapshot["pid"],
        "exitCode": snapshot["exitCode"],
        "phase": snapshot["phase"],
        "lastError": snapshot["lastError"],
    }


def get_training_logs():
    return _get_runtime_snapshot("training")


def get_inference_logs():
    return _get_runtime_snapshot("inference")


def stop_inference():
    global _inference_process

    if _inference_process and _inference_process.poll() is None:
        try:
            _append_runtime_event(
                "inference", f"Terminating inference process PID: {_inference_process.pid}"
            )
            print(f"Terminating inference process PID: {_inference_process.pid}")
            _inference_process.terminate()
            _inference_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _append_runtime_event("inference", "Force killing inference process")
            print("Force killing inference process...")
            _inference_process.kill()
            _inference_process.wait()
        except Exception as exc:
            _set_runtime_error("inference", f"Error stopping inference process: {exc}")
            print(f"Error stopping inference process: {exc}")
        finally:
            _inference_process = None

    stop_pytc_processes("test")
    cleanup_temp_files("inference")
    _update_runtime_state("inference", phase="stopped", endedAt=_utc_now())
    _append_runtime_event("inference", "Inference stop requested")
    return {"status": "stopped"}


atexit.register(stop_tensorboard)
atexit.register(cleanup_temp_files)
