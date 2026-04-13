from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server_api.workflow.metrics import compute_workflow_metrics

router = APIRouter(prefix="/api/workflows", tags=["workflow"])

_WORKFLOW_EVENTS: dict[str, list[dict[str, Any]]] = {}


def seed_workflow_events(workflow_id: str, events: list[dict[str, Any]]) -> None:
    _WORKFLOW_EVENTS[str(workflow_id)] = events


@router.get("/{workflow_id}/metrics")
def get_workflow_metrics(workflow_id: str):
    events = _WORKFLOW_EVENTS.get(str(workflow_id), [])
    metrics = compute_workflow_metrics(events)
    return {
        "workflow_id": str(workflow_id),
        "metrics": metrics,
    }
