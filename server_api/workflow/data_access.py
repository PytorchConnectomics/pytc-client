from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class WorkflowDataError(ValueError):
    """Raised when workflow payloads cannot be parsed."""


def load_workflow_payload(workflow_path: str | Path) -> Dict[str, Any]:
    """Load a workflow JSON payload from disk.

    The returned value is always a dictionary with an ``events`` key.
    """

    path = Path(workflow_path)
    if not path.exists():
        raise WorkflowDataError(f"Workflow file does not exist: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowDataError(f"Workflow file is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise WorkflowDataError("Workflow payload must be a JSON object")

    events = payload.get("events", [])
    if not isinstance(events, list):
        raise WorkflowDataError("Workflow payload 'events' field must be a list")

    normalized_events: List[Dict[str, Any]] = []
    for event in events:
        if isinstance(event, dict):
            normalized_events.append(event)

    payload["events"] = normalized_events
    return payload
