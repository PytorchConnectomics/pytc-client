from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from .db_models import WorkflowEvent, WorkflowSession
from .service import event_to_dict, workflow_to_dict


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "1970-01-01T00:00:00+00:00")
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _event_sort_key(event: Dict[str, Any]) -> Tuple[datetime, str]:
    timestamp = event.get("created_at")
    event_id = str(event.get("id") or "")
    return (_parse_timestamp(timestamp), event_id)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


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


def build_export_bundle(
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
) -> Dict[str, Any]:
    session_snapshot = _normalize_value(workflow_to_dict(workflow))
    ordered_events = sorted(
        (_normalize_value(event_to_dict(event)) for event in events),
        key=_event_sort_key,
    )

    discovered = set(_collect_paths(session_snapshot))
    for event in ordered_events:
        discovered.update(_collect_paths(event))
    artifact_paths = sorted(path for path in discovered if path)
    artifacts = [{"path": path, "exists": os.path.exists(path)} for path in artifact_paths]

    return {
        "schema_version": "workflow-export-bundle/v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "workflow_id": workflow.id,
        "session_snapshot": session_snapshot,
        "events": ordered_events,
        "artifact_paths": artifacts,
    }
