from __future__ import annotations

from fastapi import APIRouter, Request

from server_api.workflow.metrics import compute_workflow_metrics

router = APIRouter(prefix="/api/workflows", tags=["workflow"])


@router.get("/{workflow_id}/metrics")
def get_workflow_metrics(workflow_id: str, request: Request):
    store = getattr(request.app.state, "workflow_events_store", {})
    events = store.get(workflow_id, []) if isinstance(store, dict) else []
    if not isinstance(events, list):
        events = []
    return {
        "workflow_id": workflow_id,
        "metrics": compute_workflow_metrics(events),
    }
