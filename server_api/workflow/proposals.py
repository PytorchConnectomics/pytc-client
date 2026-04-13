"""Workflow-agent proposal helpers.

This module currently exposes a single approval-gated, read-only proposal action
for prioritizing failure hotspots from recent inference/proofreading events.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List

PRIORITIZE_FAILURE_HOTSPOTS = "prioritize_failure_hotspots"

_EVENT_TYPE_FIELDS = (
    "event_type",
    "type",
    "name",
)
_CANDIDATE_ID_FIELDS = (
    "region_id",
    "item_id",
    "instance_id",
    "tile_id",
    "fov_id",
    "object_id",
)


def _normalized_event_type(event: Dict[str, Any]) -> str:
    for field in _EVENT_TYPE_FIELDS:
        value = event.get(field)
        if value:
            return str(value).strip().lower()
    return ""


def _candidate_key(event: Dict[str, Any]) -> str:
    for field in _CANDIDATE_ID_FIELDS:
        value = event.get(field)
        if value not in (None, ""):
            return f"{field}:{value}"

    location = event.get("location")
    if isinstance(location, dict):
        x = location.get("x")
        y = location.get("y")
        z = location.get("z")
        if x is not None and y is not None and z is not None:
            return f"location:{x},{y},{z}"

    if event.get("target"):
        return f"target:{event['target']}"

    return "unknown"


def _event_weight(event: Dict[str, Any], event_type: str) -> int:
    score = 1

    if "proofread" in event_type:
        score += 2
    if "infer" in event_type:
        score += 2
    if any(token in event_type for token in ("fail", "error", "reject", "undo")):
        score += 3

    severity = str(event.get("severity", "")).lower().strip()
    if severity in {"high", "critical"}:
        score += 2
    elif severity == "medium":
        score += 1

    if bool(event.get("requires_rework")):
        score += 1

    return score


def propose_failure_hotspots(
    events: Iterable[Dict[str, Any]],
    *,
    top_k: int = 3,
) -> Dict[str, Any]:
    """Create a read-only hotspot proposal from recent events.

    Heuristic-only ranking is used; no model inference or state mutation occurs.
    """

    ranked = defaultdict(
        lambda: {
            "item": None,
            "score": 0,
            "event_count": 0,
            "proofreading_events": 0,
            "inference_events": 0,
            "failure_events": 0,
        }
    )

    for event in events:
        event_type = _normalized_event_type(event)
        if not event_type:
            continue

        touches_relevant_flow = "proofread" in event_type or "infer" in event_type
        if not touches_relevant_flow:
            continue

        is_failure_signal = any(
            token in event_type for token in ("fail", "error", "reject", "undo")
        ) or bool(event.get("requires_rework"))
        if not is_failure_signal:
            continue

        item = _candidate_key(event)
        group = ranked[item]
        group["item"] = item
        group["score"] += _event_weight(event, event_type)
        group["event_count"] += 1
        group["proofreading_events"] += int("proofread" in event_type)
        group["inference_events"] += int("infer" in event_type)
        group["failure_events"] += int(
            any(token in event_type for token in ("fail", "error", "reject", "undo"))
        )

    ranked_items = sorted(
        ranked.values(),
        key=lambda x: (x["score"], x["failure_events"], x["event_count"]),
        reverse=True,
    )[: max(1, top_k)]

    if ranked_items:
        candidates: List[Dict[str, Any]] = []
        for index, item in enumerate(ranked_items, start=1):
            reason = (
                f"Observed {item['event_count']} failure-linked events "
                f"({item['proofreading_events']} proofreading, "
                f"{item['inference_events']} inference)."
            )
            candidates.append(
                {
                    "rank": index,
                    "item": item["item"],
                    "score": item["score"],
                    "reason": reason,
                }
            )

        explanation = {
            "summary": "Ranked hotspot candidates from recent inference/proofreading failures.",
            "candidates": candidates,
        }
    else:
        explanation = {
            "summary": "Insufficient failure-linked events to rank specific hotspots.",
            "fallback_recommendation": (
                "Start with the most recently edited proofreading region and the latest "
                "inference output tile, then collect additional failure annotations."
            ),
            "candidates": [],
        }

    return {
        "proposal_type": PRIORITIZE_FAILURE_HOTSPOTS,
        "requires_approval": True,
        "mutates_state": False,
        "action": "review_ranked_hotspots",
        "explanation": explanation,
    }
