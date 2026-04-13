"""Rule-based proposal for evaluating correction impact before retraining."""

from __future__ import annotations

from typing import Any

PREVIEW_CORRECTION_IMPACT_PROPOSAL_TYPE = "preview_correction_impact"
RECENT_CORRECTION_EVENT_TYPES = frozenset(
    {
        "correction_applied",
        "instance_corrected",
        "mask_corrected",
        "proofreading_saved",
    }
)
RECENT_EXPORT_EVENT_TYPES = frozenset({"export_created", "masks_exported"})
CORRECTION_RATE_PROCEED_THRESHOLD = 0.10


def _count_events(events: list[dict[str, Any]], event_types: frozenset[str]) -> int:
    return sum(1 for event in events if event.get("event_type") in event_types)


def build_preview_correction_impact_proposal(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a transparent recommendation payload from recent workflow events.

    This helper is intentionally pure: it reads events and returns a proposal payload
    without mutating any external workflow state.
    """

    total_events = len(events)
    correction_events = _count_events(events, RECENT_CORRECTION_EVENT_TYPES)
    export_events = _count_events(events, RECENT_EXPORT_EVENT_TYPES)

    correction_rate = (
        correction_events / total_events if total_events else 0.0
    )
    should_proceed = correction_rate <= CORRECTION_RATE_PROCEED_THRESHOLD
    recommendation = "proceed" if should_proceed else "continue_proofreading"

    rationale = (
        "Proceed because correction activity is at or below the explicit threshold"
        if should_proceed
        else "Continue proofreading because correction activity exceeds the explicit threshold"
    )

    return {
        "type": PREVIEW_CORRECTION_IMPACT_PROPOSAL_TYPE,
        "summary": {
            "total_recent_events": total_events,
            "correction_related_events": correction_events,
            "recent_exports": export_events,
            "correction_rate": round(correction_rate, 4),
        },
        "recommendation": recommendation,
        "rationale": {
            "rule": "correction_rate <= CORRECTION_RATE_PROCEED_THRESHOLD",
            "threshold": CORRECTION_RATE_PROCEED_THRESHOLD,
            "computed": {
                "correction_rate": round(correction_rate, 4),
                "correction_events": correction_events,
                "total_events": total_events,
            },
            "explanation": (
                f"{rationale}. Corrections={correction_events}, total={total_events}, "
                f"rate={round(correction_rate, 4)}, threshold={CORRECTION_RATE_PROCEED_THRESHOLD}."
            ),
        },
    }
