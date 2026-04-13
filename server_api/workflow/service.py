from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def _event_sort_key(event: Dict[str, Any]) -> Tuple[datetime, str]:
    timestamp = str(event.get("timestamp") or "1970-01-01T00:00:00+00:00")
    event_id = str(event.get("id") or "")
    return (_parse_timestamp(timestamp), event_id)


def _collect_paths(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, inner in value.items():
            if isinstance(inner, str) and key.endswith("_path"):
                yield inner
            if key == "path" and isinstance(inner, str):
                yield inner
            yield from _collect_paths(inner)
    elif isinstance(value, list):
        for item in value:
            yield from _collect_paths(item)


def build_export_bundle(workflow_id: int, record: Dict[str, Any]) -> Dict[str, Any]:
    session_snapshot = dict(record.get("session_snapshot") or {})
    events = list(record.get("events") or [])
    ordered_events = sorted(events, key=_event_sort_key)

    explicit_paths = record.get("artifact_paths")
    if explicit_paths is None:
        discovered = set(_collect_paths(session_snapshot))
        for event in ordered_events:
            discovered.update(_collect_paths(event))
        artifact_paths = sorted(path for path in discovered if path)
    else:
        artifact_paths = sorted({str(path) for path in explicit_paths if path})

    artifacts = [{"path": path, "exists": os.path.exists(path)} for path in artifact_paths]

    return {
        "schema_version": "workflow-export-bundle/v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "workflow_id": workflow_id,
        "session_snapshot": session_snapshot,
        "events": ordered_events,
        "artifact_paths": artifacts,
    }
