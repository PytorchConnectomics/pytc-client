from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from .db_models import WorkflowEvent


def _to_iso8601(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def compute_workflow_metrics(events: List[WorkflowEvent]) -> Dict[str, Any]:
    event_type_counts: Counter[str] = Counter()
    stage_transition_counts: Counter[str] = Counter()

    approvals = 0
    rejections = 0
    first_timestamp: Any = None
    last_timestamp: Any = None
    last_stage: str | None = None

    for event in events:
        event_type = event.event_type or "unknown"
        event_type_counts[event_type] += 1

        if event_type == "agent.proposal_approved":
            approvals += 1
        if event_type == "agent.proposal_rejected":
            rejections += 1

        stage = event.stage
        if stage:
            if last_stage and last_stage != stage:
                stage_transition_counts[f"{last_stage}->{stage}"] += 1
            last_stage = stage

        timestamp = event.created_at
        if first_timestamp is None or (timestamp and timestamp < first_timestamp):
            first_timestamp = timestamp
        if last_timestamp is None or (timestamp and timestamp > last_timestamp):
            last_timestamp = timestamp

    total_decisions = approvals + rejections
    approval_rate = (approvals / total_decisions) if total_decisions else 0.0
    rejection_rate = (rejections / total_decisions) if total_decisions else 0.0

    return {
        "event_counts": dict(event_type_counts),
        "decision_metrics": {
            "approvals": approvals,
            "rejections": rejections,
            "approval_rate": approval_rate,
            "rejection_rate": rejection_rate,
            "total_decisions": total_decisions,
        },
        "stage_transition_counts": dict(stage_transition_counts),
        "timestamps": {
            "first_event_at": _to_iso8601(first_timestamp),
            "last_event_at": _to_iso8601(last_timestamp),
        },
        "total_events": len(events),
    }
