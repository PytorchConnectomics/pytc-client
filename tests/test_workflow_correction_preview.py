from server_api.workflow.correction_preview import (
    CORRECTION_RATE_PROCEED_THRESHOLD,
    PREVIEW_CORRECTION_IMPACT_PROPOSAL_TYPE,
    build_preview_correction_impact_proposal,
)


def test_preview_correction_impact_low_correction_recommends_proceed():
    events = [
        {"event_type": "masks_exported"},
        {"event_type": "model_trained"},
        {"event_type": "evaluation_completed"},
        {"event_type": "correction_applied"},
        {"event_type": "dataset_refreshed"},
        {"event_type": "export_created"},
        {"event_type": "model_trained"},
        {"event_type": "metrics_uploaded"},
        {"event_type": "run_archived"},
        {"event_type": "checkpoint_saved"},
    ]

    original_events = [dict(item) for item in events]
    proposal = build_preview_correction_impact_proposal(events)

    assert proposal["type"] == PREVIEW_CORRECTION_IMPACT_PROPOSAL_TYPE
    assert proposal["summary"]["correction_related_events"] == 1
    assert proposal["summary"]["recent_exports"] == 2
    assert proposal["recommendation"] == "proceed"
    assert (
        proposal["rationale"]["rule"]
        == "correction_rate <= CORRECTION_RATE_PROCEED_THRESHOLD"
    )
    assert proposal["rationale"]["threshold"] == CORRECTION_RATE_PROCEED_THRESHOLD
    assert "threshold" in proposal["rationale"]["explanation"]
    assert events == original_events


def test_preview_correction_impact_high_correction_recommends_continue_proofreading():
    events = [
        {"event_type": "correction_applied"},
        {"event_type": "instance_corrected"},
        {"event_type": "mask_corrected"},
        {"event_type": "proofreading_saved"},
        {"event_type": "masks_exported"},
        {"event_type": "model_trained"},
        {"event_type": "dataset_refreshed"},
        {"event_type": "correction_applied"},
        {"event_type": "instance_corrected"},
        {"event_type": "evaluation_completed"},
    ]

    proposal = build_preview_correction_impact_proposal(events)

    assert proposal["summary"]["correction_related_events"] == 6
    assert proposal["summary"]["recent_exports"] == 1
    assert proposal["recommendation"] == "continue_proofreading"
    assert proposal["rationale"]["computed"]["correction_rate"] > CORRECTION_RATE_PROCEED_THRESHOLD
    assert "Continue proofreading" in proposal["rationale"]["explanation"]
