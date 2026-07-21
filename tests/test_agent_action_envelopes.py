from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from server_api.workflows.agent_actions import (
    ALL_ACTION_DEFINITIONS,
    action_envelope_json_schema,
    action_receipt_json_schema,
    canonical_action_policy,
    dump_action_envelope_json,
    dump_action_receipt_json,
    load_action_envelope_json,
    load_action_receipt_json,
    validate_action_for_execution,
    validate_action_envelope,
    validate_action_receipt,
    validate_receipt_for_action,
)


def _envelope(kind="start_training", **overrides):
    definition = ALL_ACTION_DEFINITIONS[kind]
    payload = {
        "action_id": f"action-{kind}",
        "kind": kind,
        "workflow_id": 17,
        "requested_by": "agent",
        "idempotency_key": f"workflow:17:{kind}:v1",
        "correlation_id": "request-4c0d",
        "execution_owner": definition.execution_owner,
        "policy": {
            "risk_level": definition.risk_level,
            "requires_approval": definition.requires_approval,
        },
        "approval": {
            "status": "pending" if definition.requires_approval else "not_required"
        },
        "input_artifacts": [
            {
                "artifact_id": 9,
                "artifact_type": "volume",
                "role": "training_image",
                "uri": "zarr:///datasets/mito25/image",
                "checksum": "sha256:image-v1",
            }
        ],
        "expected_output_artifacts": [
            {
                "logical_name": "candidate-checkpoint",
                "artifact_type": "model_checkpoint",
                "role": "candidate",
            }
        ],
        "preconditions": [
            {
                "kind": "workflow_stage",
                "allowed_stages": ["proofreading", "retraining_staged"],
            },
            {
                "kind": "artifact_available",
                "artifact": {"artifact_id": 9},
            },
        ],
        **overrides,
    }
    return payload


def _receipt(kind="start_training", **overrides):
    action_fields = {
        "choose_project_data": {
            "selected_artifacts": [{"artifact_id": 2}],
        },
        "load_visualization": {"viewer_url": "https://viewer.test/v/1"},
        "start_inference": {"run_id": "inference-1"},
        "stop_inference": {"stopped": True},
        "start_proofreading": {"proofreading_session_id": 8},
        "start_training": {"run_id": "training-1"},
        "stop_training": {"stopped": True},
        "compute_evaluation": {"evaluation_result_id": 11},
        "export_bundle": {
            "bundle_artifact": {
                "artifact_id": 12,
                "artifact_type": "evidence_bundle",
            }
        },
        "propose_retraining_stage": {"workflow_event_id": 13},
    }
    return {
        "receipt_id": f"receipt-{kind}",
        "action_id": f"action-{kind}",
        "kind": kind,
        "workflow_id": 17,
        "idempotency_key": f"workflow:17:{kind}:v1",
        "correlation_id": "request-4c0d",
        "status": "succeeded",
        "operation_id": 31,
        "produced_artifacts": [{"logical_name": "output"}],
        "started_at": datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc),
        "completed_at": datetime(2026, 7, 21, 13, 5, tzinfo=timezone.utc),
        **action_fields[kind],
        **overrides,
    }


@pytest.mark.parametrize("kind", sorted(ALL_ACTION_DEFINITIONS))
def test_every_registered_core_action_has_a_discriminated_envelope(kind):
    envelope = validate_action_envelope(_envelope(kind))

    assert envelope.kind == kind
    assert envelope.policy == canonical_action_policy(kind)
    assert envelope.execution_owner == ALL_ACTION_DEFINITIONS[kind].execution_owner


def test_action_envelope_schema_exposes_kind_discriminator_and_core_mappings():
    schema = action_envelope_json_schema()

    assert schema["discriminator"]["propertyName"] == "kind"
    assert set(schema["discriminator"]["mapping"]) == set(ALL_ACTION_DEFINITIONS)
    assert len(schema["oneOf"]) == len(ALL_ACTION_DEFINITIONS)


def test_action_receipt_schema_matches_action_discriminator():
    schema = action_receipt_json_schema()

    assert schema["discriminator"]["propertyName"] == "kind"
    assert set(schema["discriminator"]["mapping"]) == set(ALL_ACTION_DEFINITIONS)


def test_action_envelope_json_round_trip_preserves_typed_boundary_fields():
    payload = _envelope(
        "start_training",
        approval={
            "status": "approved",
            "event_id": 21,
            "decided_by": "user:3",
            "decided_at": datetime(2026, 7, 21, 12, 59, tzinfo=timezone.utc),
        },
        autopick_parameters=True,
        parameter_mode="agent_default",
        volume_subset={
            "selection_basis": "project_progress",
            "training_statuses": ["ground_truth"],
            "train_volume_count": 2,
            "target_volume_count": 1,
            "review_volume_count": 0,
            "manifest_path": "/datasets/mito25/volume_subset_manifest.json",
        },
    )

    original = validate_action_envelope(payload)
    restored = load_action_envelope_json(dump_action_envelope_json(original))

    assert type(restored) is type(original)
    assert restored.model_dump() == original.model_dump()
    assert restored.input_artifacts[0].artifact_id == 9
    assert restored.preconditions[1].kind == "artifact_available"


def test_action_receipt_json_round_trip_preserves_typed_result():
    original = validate_action_receipt(
        _receipt(
            "compute_evaluation",
            metrics={"iou": 0.84, "dice": 0.91},
        )
    )
    restored = load_action_receipt_json(dump_action_receipt_json(original))

    assert type(restored) is type(original)
    assert restored.model_dump() == original.model_dump()
    assert restored.evaluation_result_id == 11
    assert restored.metrics["dice"] == pytest.approx(0.91)


def test_envelope_rejects_policy_or_execution_owner_spoofing():
    with pytest.raises(ValidationError, match="risk_level for start_training"):
        validate_action_envelope(
            _envelope(
                policy={
                    "risk_level": "read_only",
                    "requires_approval": True,
                }
            )
        )

    with pytest.raises(ValidationError, match="execution_owner for start_training"):
        validate_action_envelope(_envelope(execution_owner="browser_navigation"))


def test_envelope_rejects_invalid_approval_evidence_and_status():
    with pytest.raises(ValidationError, match="require event_id and decided_by"):
        validate_action_envelope(
            _envelope(approval={"status": "approved", "event_id": 9})
        )

    with pytest.raises(ValidationError, match="does not accept an approval decision"):
        validate_action_envelope(
            _envelope("choose_project_data", approval={"status": "pending"})
        )


def test_execution_gate_requires_approved_envelope_for_risky_actions():
    with pytest.raises(ValueError, match="cannot execute without an approved"):
        validate_action_for_execution(_envelope("start_training"))

    approved = _envelope(
        "start_training",
        approval={
            "status": "approved",
            "event_id": 23,
            "decided_by": "user:4",
        },
    )
    assert validate_action_for_execution(approved).kind == "start_training"
    assert validate_action_for_execution(_envelope("choose_project_data")).kind == (
        "choose_project_data"
    )


def test_envelope_rejects_untyped_artifacts_preconditions_and_action_fields():
    with pytest.raises(ValidationError, match="artifact reference requires"):
        validate_action_envelope(_envelope(input_artifacts=[{"role": "image"}]))

    with pytest.raises(ValidationError, match="precondition"):
        validate_action_envelope(
            _envelope(preconditions=[{"kind": "shell_exit_code", "value": 0}])
        )

    with pytest.raises(ValidationError):
        validate_action_envelope(_envelope(shell_command="rm -rf /"))

    with pytest.raises(ValidationError):
        validate_action_envelope(_envelope(volume_subset={"shell_command": "rm -rf /"}))


def test_failed_receipt_requires_typed_error_and_terminal_timestamp():
    failed_payload = _receipt(
        "start_inference",
        status="failed",
        run_id=None,
        error={
            "code": "worker_unavailable",
            "message": "The inference worker did not respond.",
            "retryable": True,
            "details": {"status_code": 503},
        },
    )
    receipt = validate_action_receipt(failed_payload)

    assert receipt.error.code == "worker_unavailable"
    assert receipt.error.retryable is True

    with pytest.raises(ValidationError, match="require an error"):
        validate_action_receipt({**failed_payload, "error": None})

    with pytest.raises(ValidationError, match="require completed_at"):
        validate_action_receipt({**failed_payload, "completed_at": None})

    with pytest.raises(ValidationError, match="cannot precede started_at"):
        validate_action_receipt(
            {
                **failed_payload,
                "completed_at": datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
            }
        )


def test_receipt_must_match_action_identity_and_correlation():
    action = _envelope(
        "start_training",
        approval={
            "status": "approved",
            "event_id": 23,
            "decided_by": "user:4",
        },
    )
    receipt = _receipt("start_training")

    assert validate_receipt_for_action(action, receipt).run_id == "training-1"
    with pytest.raises(ValueError, match="correlation_id"):
        validate_receipt_for_action(
            action,
            {**receipt, "correlation_id": "different-request"},
        )


@pytest.mark.parametrize("kind", sorted(ALL_ACTION_DEFINITIONS))
def test_succeeded_receipts_require_action_specific_result(kind):
    receipt = validate_action_receipt(_receipt(kind))
    assert receipt.kind == kind

    result_field = {
        "choose_project_data": "selected_artifacts",
        "load_visualization": "viewer_url",
        "start_inference": "run_id",
        "stop_inference": "stopped",
        "start_proofreading": "proofreading_session_id",
        "start_training": "run_id",
        "stop_training": "stopped",
        "compute_evaluation": "evaluation_result_id",
        "export_bundle": "bundle_artifact",
        "propose_retraining_stage": "workflow_event_id",
    }[kind]
    missing_value = [] if result_field == "selected_artifacts" else None
    with pytest.raises(ValidationError, match=f"require {result_field}"):
        validate_action_receipt(_receipt(kind, **{result_field: missing_value}))
