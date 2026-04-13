"""Rule-based workflow proposals for proofreading and retraining decisions."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping, Sequence

PROPOSAL_TYPE_PREVIEW_CORRECTION_IMPACT = "preview_correction_impact"

# Explicit thresholds for transparent recommendation logic.
LOW_CORRECTION_THRESHOLD = 5
HIGH_CORRECTION_THRESHOLD = 20
RECENT_EXPORT_WINDOW = 3

CORRECTION_EVENT_TYPES = {
    "correction_saved",
    "mask_edited",
    "instance_fixed",
    "proofread_correction",
}
EXPORT_EVENT_TYPES = {"mask_exported", "export_masks", "export_completed"}


def _event_type(event: Mapping[str, object]) -> str:
    raw = event.get("type", "")
    return raw if isinstance(raw, str) else ""


def _recent_export_events(events: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    exports = [event for event in events if _event_type(event) in EXPORT_EVENT_TYPES]
    return exports[-RECENT_EXPORT_WINDOW:]


def build_preview_correction_impact_proposal(
    recent_events: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Build a no-side-effect proposal that previews correction impact on retraining.

    Args:
        recent_events: Event dictionaries with a string ``type`` key.

    Returns:
        Proposal payload containing summary, recommendation, and rationale.
    """
    event_list = list(recent_events)
    event_type_counts = Counter(_event_type(event) for event in event_list)

    correction_count = sum(
        event_type_counts[event_type] for event_type in CORRECTION_EVENT_TYPES
    )
    recent_exports = _recent_export_events(event_list)

    if correction_count <= LOW_CORRECTION_THRESHOLD:
        recommendation = "proceed"
        rationale = (
            f"Detected {correction_count} correction events (<= {LOW_CORRECTION_THRESHOLD}); "
            "current proofreading changes are limited, so retraining can proceed."
        )
    elif correction_count >= HIGH_CORRECTION_THRESHOLD:
        recommendation = "continue_proofreading"
        rationale = (
            f"Detected {correction_count} correction events (>= {HIGH_CORRECTION_THRESHOLD}); "
            "large correction volume suggests continuing proofreading before retraining."
        )
    else:
        recommendation = "continue_proofreading"
        rationale = (
            f"Detected {correction_count} correction events between explicit thresholds "
            f"({LOW_CORRECTION_THRESHOLD} and {HIGH_CORRECTION_THRESHOLD}); "
            "collect more proofreading updates before retraining."
        )

    export_summary = [
        {
            "type": _event_type(event),
            "timestamp": event.get("timestamp"),
            "target": event.get("target"),
        }
        for event in recent_exports
    ]

    return {
        "type": PROPOSAL_TYPE_PREVIEW_CORRECTION_IMPACT,
        "summary": {
            "correction_event_counts": {
                event_type: event_type_counts[event_type]
                for event_type in sorted(CORRECTION_EVENT_TYPES)
            },
            "total_correction_events": correction_count,
            "recent_exports": export_summary,
        },
        "recommendation": recommendation,
        "rationale": rationale,
    }
