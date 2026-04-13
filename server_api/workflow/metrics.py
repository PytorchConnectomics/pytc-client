from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


def _to_iso8601(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.isoformat().replace("+00:00", "Z")


def compute_workflow_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate workflow metrics from a list of event dicts."""

    event_type_counts: Counter[str] = Counter()
    stage_transition_counts: Counter[str] = Counter()

    approval_count = 0
    rejection_count = 0
    timestamps: list[datetime] = []

    for event in events:
        event_type = str(event.get("type") or "unknown")
        event_type_counts[event_type] += 1

        ts = event.get("timestamp")
        if isinstance(ts, str):
            timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))

        action = str(event.get("action") or "").lower()
        outcome = str(event.get("outcome") or "").lower()
        if event_type == "approval" or action == "approve" or outcome == "approved":
            approval_count += 1
        if (
            event_type == "rejection"
            or action == "reject"
            or outcome == "rejected"
        ):
            rejection_count += 1

        from_stage = event.get("from_stage")
        to_stage = event.get("to_stage")
        if from_stage and to_stage:
            transition_key = f"{from_stage}->{to_stage}"
            stage_transition_counts[transition_key] += 1

    total_decisions = approval_count + rejection_count
    approval_rate = (approval_count / total_decisions) if total_decisions else 0.0
    rejection_rate = (rejection_count / total_decisions) if total_decisions else 0.0

    first_timestamp = min(timestamps).isoformat().replace("+00:00", "Z") if timestamps else None
    last_timestamp = max(timestamps).isoformat().replace("+00:00", "Z") if timestamps else None

    return {
        "event_counts": dict(event_type_counts),
        "decision_metrics": {
            "approvals": approval_count,
            "rejections": rejection_count,
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
