from __future__ import annotations

from fastapi import APIRouter

from .models import WorkflowMetricsResponse
from .service import compute_metrics
from .store import get_events

router = APIRouter(prefix="/api/workflows", tags=["workflow"])


@router.get("/{workflow_id}/metrics", response_model=WorkflowMetricsResponse)
async def get_workflow_metrics(workflow_id: str):
    events = get_events(workflow_id)
    return compute_metrics(workflow_id=workflow_id, events=events)
