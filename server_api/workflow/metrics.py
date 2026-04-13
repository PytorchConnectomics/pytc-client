from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


def _parse_timestamp(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _isoformat_z(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_workflow_metrics(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    event_list: List[Dict[str, Any]] = list(events)

    event_type_counts: Counter[str] = Counter()
    transition_counts: Counter[str] = Counter()
    timestamps: List[datetime] = []
    approvals = 0
    rejections = 0

    for event in event_list:
        event_type = event.get("type")
        if isinstance(event_type, str) and event_type:
            event_type_counts[event_type] += 1

        outcome = event.get("outcome")
        if outcome == "approved":
            approvals += 1
        elif outcome == "rejected":
            rejections += 1

        from_stage = event.get("from_stage")
        to_stage = event.get("to_stage")
        if isinstance(from_stage, str) and from_stage and isinstance(to_stage, str) and to_stage:
            transition_counts[f"{from_stage}->{to_stage}"] += 1

        parsed_ts = _parse_timestamp(event.get("timestamp"))
        if parsed_ts is not None:
            timestamps.append(parsed_ts)

    decisions_total = approvals + rejections
    approval_rate = approvals / decisions_total if decisions_total else 0.0
    rejection_rate = rejections / decisions_total if decisions_total else 0.0

    first_ts = min(timestamps) if timestamps else None
    last_ts = max(timestamps) if timestamps else None

    return {
        "event_counts_by_type": dict(sorted(event_type_counts.items())),
        "approvals": {
            "count": approvals,
            "rate": approval_rate,
        },
        "rejections": {
            "count": rejections,
            "rate": rejection_rate,
        },
        "stage_transitions": dict(sorted(transition_counts.items())),
        "first_event_timestamp": _isoformat_z(first_ts),
        "last_event_timestamp": _isoformat_z(last_ts),
        "total_events": len(event_list),
    }
