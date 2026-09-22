import pytest
from pydantic import ValidationError

from server_api.workflows.agent_actions import (
    resolve_agent_action,
    validate_agent_proposal,
)


def test_runtime_action_registry_owns_risk_and_approval_policy():
    action = resolve_agent_action(
        "launch-model",
        {
            "navigate_to": "training",
            "runtime_action": {"kind": "start_training"},
        },
    )

    assert action.action_type == "start_training"
    assert action.risk_level == "runs_job"
    assert action.requires_approval is True
    assert action.execution_owner == "server_runtime"
    assert action.specialist_agent_type == "training_agent"


def test_navigation_action_remains_browser_owned_and_read_only():
    action = resolve_agent_action("show-files", {"navigate_to": "files"})

    assert action.action_type == "open_files"
    assert action.risk_level == "read_only"
    assert action.requires_approval is False
    assert action.execution_owner == "browser_navigation"
    assert action.specialist_agent_type == "data_agent"


def test_prefill_action_is_typed_without_becoming_domain_execution():
    action = resolve_agent_action(
        "prepare-training",
        {
            "navigate_to": "training",
            "set_training_image_path": "/data/image.zarr",
            "set_training_label_path": "/data/labels.zarr",
        },
    )

    assert action.risk_level == "prefills_form"
    assert action.requires_approval is False
    assert action.execution_owner == "browser_navigation"


def test_unknown_client_effect_cannot_bypass_registry_validation():
    with pytest.raises(ValidationError):
        resolve_agent_action("mystery", {"silently_delete_project": True})


def test_registered_runtime_kind_rejects_unregistered_parameters():
    with pytest.raises(ValidationError):
        resolve_agent_action(
            "launch-model",
            {
                "runtime_action": {
                    "kind": "start_inference",
                    "shell_command": "rm -rf /",
                }
            },
        )


def test_registered_workflow_kind_rejects_unregistered_parameters():
    with pytest.raises(ValidationError):
        resolve_agent_action(
            "export",
            {
                "workflow_action": {
                    "kind": "export_bundle",
                    "destination": "/unapproved/path",
                }
            },
        )


def test_persisted_client_effect_proposal_is_validated_before_approval():
    action = validate_agent_proposal(
        "run_client_effects",
        {
            "client_effects": {
                "navigate_to": "inference",
                "runtime_action": {"kind": "start_inference"},
            }
        },
    )

    assert action.action_type == "start_inference"
    assert action.execution_owner == "server_runtime"


def test_unknown_persisted_proposal_type_is_rejected():
    with pytest.raises(ValueError, match="Unsupported agent proposal action"):
        validate_agent_proposal("invented_action", {})
