from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence

from .models import WorkflowEvent, WorkflowMetricsResponse

_APPROVAL_TYPES = {"approval", "approved", "approval_granted"}
_REJECTION_TYPES = {"rejection", "rejected", "approval_rejected"}
_APPROVAL_ACTIONS = {"approve", "approved"}
_REJECTION_ACTIONS = {"reject", "rejected"}


def _is_approval(event: WorkflowEvent) -> bool:
    if event.event_type.lower() in _APPROVAL_TYPES:
        return True
    if event.action and event.action.lower() in _APPROVAL_ACTIONS:
        return True
    return False


def _is_rejection(event: WorkflowEvent) -> bool:
    if event.event_type.lower() in _REJECTION_TYPES:
        return True
    if event.action and event.action.lower() in _REJECTION_ACTIONS:
        return True
    return False


def compute_metrics(workflow_id: str, events: Sequence[WorkflowEvent]) -> WorkflowMetricsResponse:
    type_counts = Counter(event.event_type for event in events)

    approvals_count = sum(1 for event in events if _is_approval(event))
    rejections_count = sum(1 for event in events if _is_rejection(event))
    review_total = approvals_count + rejections_count

    transition_counts = Counter(
        f"{event.from_stage}->{event.to_stage}"
        for event in events
        if event.from_stage and event.to_stage
    )

    timestamps = [event.created_at for event in events]
    first_event_at = min(timestamps) if timestamps else None
    last_event_at = max(timestamps) if timestamps else None

    return WorkflowMetricsResponse(
        workflow_id=str(workflow_id),
        total_events=len(events),
        event_counts_by_type=dict(type_counts),
        approvals_count=approvals_count,
        rejections_count=rejections_count,
        approvals_rate=(approvals_count / review_total) if review_total else 0.0,
        rejections_rate=(rejections_count / review_total) if review_total else 0.0,
        stage_transition_counts=dict(transition_counts),
        first_event_at=first_event_at,
        last_event_at=last_event_at,
    )
