from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


RiskLevel = Literal[
    "read_only",
    "prefills_form",
    "loads_editor",
    "writes_workflow_record",
    "modifies_workspace",
    "runs_job",
    "controls_job",
    "exports_evidence",
]


class _StrictActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChooseProjectDataPayload(_StrictActionPayload):
    kind: Literal["choose_project_data"]


class LoadVisualizationPayload(_StrictActionPayload):
    kind: Literal["load_visualization"]


class StartInferencePayload(_StrictActionPayload):
    kind: Literal["start_inference"]


class StopInferencePayload(_StrictActionPayload):
    kind: Literal["stop_inference"]


class StartProofreadingPayload(_StrictActionPayload):
    kind: Literal["start_proofreading"]


class StartTrainingPayload(_StrictActionPayload):
    kind: Literal["start_training"]
    autopick_parameters: Optional[bool] = None
    parameter_mode: Optional[str] = None
    volume_subset: Optional[Dict[str, Any]] = None


class StopTrainingPayload(_StrictActionPayload):
    kind: Literal["stop_training"]


RuntimeActionPayload = Annotated[
    Union[
        ChooseProjectDataPayload,
        LoadVisualizationPayload,
        StartInferencePayload,
        StopInferencePayload,
        StartProofreadingPayload,
        StartTrainingPayload,
        StopTrainingPayload,
    ],
    Field(discriminator="kind"),
]


class ComputeEvaluationPayload(_StrictActionPayload):
    kind: Literal["compute_evaluation"]
    name: Optional[str] = None
    baseline_prediction_path: Optional[str] = None
    candidate_prediction_path: Optional[str] = None
    ground_truth_path: Optional[str] = None
    baseline_run_id: Optional[int] = None
    candidate_run_id: Optional[int] = None
    model_version_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ExportBundlePayload(_StrictActionPayload):
    kind: Literal["export_bundle"]


class ProposeRetrainingStagePayload(_StrictActionPayload):
    kind: Literal["propose_retraining_stage"]
    corrected_mask_path: Optional[str] = None


WorkflowActionPayload = Annotated[
    Union[
        ComputeEvaluationPayload,
        ExportBundlePayload,
        ProposeRetrainingStagePayload,
    ],
    Field(discriminator="kind"),
]


class MountProjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory_path: str
    mount_name: Optional[str] = None
    destination_path: Optional[str] = None
    workflow_patch: Optional[Dict[str, Any]] = None


class ClientEffectsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    navigate_to: Optional[str] = None
    runtime_action: Optional[RuntimeActionPayload] = None
    workflow_action: Optional[WorkflowActionPayload] = None
    mount_project: Optional[MountProjectPayload] = None
    reset_workspace: Optional[bool] = None
    start_new_workflow: Optional[Any] = None
    show_workflow_context: Optional[bool] = None
    refresh_insights: Optional[bool] = None
    refresh_project_progress: Optional[bool] = None
    training_volume_subset: Optional[Any] = None
    set_training_config_preset: Optional[str] = None
    set_training_image_path: Optional[str] = None
    set_training_label_path: Optional[str] = None
    set_training_log_path: Optional[str] = None
    set_training_output_path: Optional[str] = None
    set_inference_checkpoint_path: Optional[str] = None
    set_inference_config_preset: Optional[str] = None
    set_inference_image_path: Optional[str] = None
    set_inference_label_path: Optional[str] = None
    set_inference_output_path: Optional[str] = None
    set_visualization_image_path: Optional[str] = None
    set_visualization_label_path: Optional[str] = None
    set_visualization_scales: Optional[Any] = None
    set_proofreading_dataset_path: Optional[str] = None
    set_proofreading_image_path: Optional[str] = None
    set_proofreading_label_path: Optional[str] = None
    set_proofreading_mask_path: Optional[str] = None
    set_proofreading_project_name: Optional[str] = None


class StageRetrainingPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    corrected_mask_path: Optional[str] = None


class StartTrainingRunPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    client_effects: Optional[ClientEffectsPayload] = None


class RunClientEffectsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    client_effects: ClientEffectsPayload


@dataclass(frozen=True)
class AgentActionDefinition:
    action_type: str
    risk_level: RiskLevel
    requires_approval: bool
    execution_owner: Literal["browser_navigation", "server_workflow", "server_runtime"]
    specialist_agent_type: str


RUNTIME_ACTIONS: Dict[str, AgentActionDefinition] = {
    "choose_project_data": AgentActionDefinition(
        "choose_project_data",
        "prefills_form",
        False,
        "browser_navigation",
        "data_agent",
    ),
    "load_visualization": AgentActionDefinition(
        "load_visualization",
        "read_only",
        False,
        "browser_navigation",
        "visualization_agent",
    ),
    "start_inference": AgentActionDefinition(
        "start_inference", "runs_job", True, "server_runtime", "inference_agent"
    ),
    "stop_inference": AgentActionDefinition(
        "stop_inference", "controls_job", True, "server_runtime", "inference_agent"
    ),
    "start_proofreading": AgentActionDefinition(
        "start_proofreading",
        "loads_editor",
        True,
        "server_workflow",
        "proofreading_agent",
    ),
    "start_training": AgentActionDefinition(
        "start_training", "runs_job", True, "server_runtime", "training_agent"
    ),
    "stop_training": AgentActionDefinition(
        "stop_training", "controls_job", True, "server_runtime", "training_agent"
    ),
}


WORKFLOW_ACTIONS: Dict[str, AgentActionDefinition] = {
    "compute_evaluation": AgentActionDefinition(
        "compute_evaluation",
        "writes_workflow_record",
        True,
        "server_workflow",
        "evaluation_agent",
    ),
    "export_bundle": AgentActionDefinition(
        "export_bundle",
        "exports_evidence",
        True,
        "server_workflow",
        "evidence_agent",
    ),
    "propose_retraining_stage": AgentActionDefinition(
        "propose_retraining_stage",
        "writes_workflow_record",
        True,
        "server_workflow",
        "training_agent",
    ),
}


NAVIGATION_SPECIALISTS = {
    "files": "data_agent",
    "visualization": "visualization_agent",
    "mask-proofreading": "proofreading_agent",
    "training": "training_agent",
    "inference": "inference_agent",
    "project-progress": "project_manager",
}


def _validate_effects(client_effects: Dict[str, Any]) -> None:
    validator = getattr(ClientEffectsPayload, "model_validate", None)
    if validator is not None:
        validator(client_effects)
    else:  # pragma: no cover - Pydantic v1 compatibility
        ClientEffectsPayload.parse_obj(client_effects)


def resolve_agent_action(
    action_id: str, client_effects: Optional[Dict[str, Any]]
) -> AgentActionDefinition:
    effects = client_effects or {}
    _validate_effects(effects)

    runtime_action = effects.get("runtime_action") or {}
    runtime_kind = runtime_action.get("kind")
    if runtime_kind:
        return RUNTIME_ACTIONS[str(runtime_kind)]

    workflow_action = effects.get("workflow_action") or {}
    workflow_kind = workflow_action.get("kind")
    if workflow_kind:
        return WORKFLOW_ACTIONS[str(workflow_kind)]

    if effects.get("mount_project"):
        return AgentActionDefinition(
            "mount_project", "modifies_workspace", True, "server_workflow", "data_agent"
        )
    if effects.get("reset_workspace"):
        return AgentActionDefinition(
            "reset_workspace",
            "modifies_workspace",
            True,
            "server_workflow",
            "data_agent",
        )
    if effects.get("start_new_workflow"):
        return AgentActionDefinition(
            "start_new_workflow",
            "writes_workflow_record",
            True,
            "server_workflow",
            "project_manager",
        )

    if any(key.startswith("set_") for key in effects) or effects.get(
        "training_volume_subset"
    ):
        navigate_to = str(effects.get("navigate_to") or "")
        return AgentActionDefinition(
            action_id,
            "prefills_form",
            False,
            "browser_navigation",
            NAVIGATION_SPECIALISTS.get(navigate_to, "project_manager"),
        )

    if effects.get("show_workflow_context") or effects.get("refresh_insights"):
        return AgentActionDefinition(
            (
                "show_workflow_context"
                if effects.get("show_workflow_context")
                else "refresh_context"
            ),
            "read_only",
            False,
            "browser_navigation",
            "project_manager",
        )

    if effects.get("navigate_to"):
        destination = str(effects["navigate_to"])
        return AgentActionDefinition(
            f"open_{destination}",
            "read_only",
            False,
            "browser_navigation",
            NAVIGATION_SPECIALISTS.get(destination, "project_manager"),
        )

    return AgentActionDefinition(
        action_id,
        "read_only",
        False,
        "browser_navigation",
        "project_manager",
    )


def validate_agent_proposal(
    action: str, payload: Optional[Dict[str, Any]]
) -> AgentActionDefinition:
    params = payload or {}
    if action == "stage_retraining_from_corrections":
        StageRetrainingPayload.model_validate(params)
        return AgentActionDefinition(
            action,
            "writes_workflow_record",
            True,
            "server_workflow",
            "training_agent",
        )
    if action == "start_training_run":
        validated = StartTrainingRunPayload.model_validate(params)
        if validated.client_effects is not None:
            return resolve_agent_action(
                action, validated.client_effects.model_dump(exclude_none=True)
            )
        return RUNTIME_ACTIONS["start_training"]
    if action == "run_client_effects":
        validated = RunClientEffectsPayload.model_validate(params)
        return resolve_agent_action(
            action, validated.client_effects.model_dump(exclude_none=True)
        )
    raise ValueError(f"Unsupported agent proposal action: {action}")
