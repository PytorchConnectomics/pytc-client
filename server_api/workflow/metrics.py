from collections import Counter
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Request

router = APIRouter()


def _to_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None

    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _as_iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _compute_workflow_metrics(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    normalized_events: List[Dict[str, Any]] = [event for event in events if isinstance(event, dict)]

    event_type_counts: Counter = Counter()
    stage_transition_counts: Counter = Counter()
    approvals = 0
    rejections = 0
    timestamps: List[datetime] = []

    for event in normalized_events:
        event_type = str(event.get("type") or "unknown")
        event_type_counts[event_type] += 1

        decision = str(event.get("decision") or "").strip().lower()
        if decision == "approved":
            approvals += 1
        elif decision == "rejected":
            rejections += 1

        from_stage = event.get("from_stage")
        to_stage = event.get("to_stage")
        if from_stage is not None and to_stage is not None:
            stage_transition_counts[f"{from_stage}->{to_stage}"] += 1

        ts = _to_datetime(event.get("timestamp"))
        if ts:
            timestamps.append(ts)

    decision_total = approvals + rejections
    approval_rate = (approvals / decision_total) if decision_total else 0.0
    rejection_rate = (rejections / decision_total) if decision_total else 0.0

    first_ts = min(timestamps) if timestamps else None
    last_ts = max(timestamps) if timestamps else None

    return {
        "event_counts": dict(sorted(event_type_counts.items())),
        "approvals": {
            "count": approvals,
            "rejections": rejections,
            "total": decision_total,
            "approval_rate": approval_rate,
            "rejection_rate": rejection_rate,
        },
        "stage_transitions": dict(sorted(stage_transition_counts.items())),
        "timeline": {
            "first_event_at": _as_iso(first_ts),
            "last_event_at": _as_iso(last_ts),
        },
    }


@router.get("/api/workflows/{workflow_id}/metrics")
def get_workflow_metrics(workflow_id: str, request: Request):
    workflow_events = getattr(request.app.state, "workflow_events", {}) or {}
    events = workflow_events.get(workflow_id, [])
    metrics = _compute_workflow_metrics(events)

    return {
        "workflow_id": workflow_id,
        "event_total": len([event for event in events if isinstance(event, dict)]),
        "metrics": metrics,
    }
