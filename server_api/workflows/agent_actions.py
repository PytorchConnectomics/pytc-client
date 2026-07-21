from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    model_validator,
)

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


NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
IdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
CorrelationId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
ApprovalStatus = Literal["not_required", "pending", "approved", "rejected"]
ExecutionOwner = Literal["browser_navigation", "server_workflow", "server_runtime"]
OperationStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
ReceiptStatus = Literal["accepted", "running", "succeeded", "failed", "cancelled"]


class _StrictBoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ArtifactReference(_StrictBoundaryModel):
    """Stable artifact identity used at the action execution boundary."""

    artifact_id: Optional[int] = Field(default=None, gt=0)
    logical_name: Optional[NonEmptyString] = None
    artifact_type: Optional[NonEmptyString] = None
    role: Optional[NonEmptyString] = None
    path: Optional[NonEmptyString] = None
    uri: Optional[NonEmptyString] = None
    checksum: Optional[NonEmptyString] = None
    media_type: Optional[NonEmptyString] = None
    immutable: bool = True

    @model_validator(mode="after")
    def require_identity(self) -> "ArtifactReference":
        if not any(
            (
                self.artifact_id,
                self.logical_name,
                self.path,
                self.uri,
                self.checksum,
            )
        ):
            raise ValueError(
                "artifact reference requires artifact_id, logical_name, path, uri, "
                "or checksum"
            )
        return self


class WorkflowStagePrecondition(_StrictBoundaryModel):
    kind: Literal["workflow_stage"]
    allowed_stages: List[NonEmptyString] = Field(min_length=1)


class ArtifactAvailablePrecondition(_StrictBoundaryModel):
    kind: Literal["artifact_available"]
    artifact: ArtifactReference


class WorkflowFieldPrecondition(_StrictBoundaryModel):
    kind: Literal["workflow_field_present"]
    field_name: NonEmptyString


class OperationStatusPrecondition(_StrictBoundaryModel):
    kind: Literal["operation_status"]
    operation_id: int = Field(gt=0)
    allowed_statuses: List[OperationStatus] = Field(min_length=1)


ActionPrecondition = Annotated[
    Union[
        WorkflowStagePrecondition,
        ArtifactAvailablePrecondition,
        WorkflowFieldPrecondition,
        OperationStatusPrecondition,
    ],
    Field(discriminator="kind"),
]


class ActionPolicy(_StrictBoundaryModel):
    risk_level: RiskLevel
    requires_approval: bool
    approval_reason: Optional[NonEmptyString] = None


class ActionApproval(_StrictBoundaryModel):
    status: ApprovalStatus
    event_id: Optional[int] = Field(default=None, gt=0)
    decided_by: Optional[NonEmptyString] = None
    decided_at: Optional[datetime] = None

    @model_validator(mode="after")
    def require_decision_evidence(self) -> "ActionApproval":
        if self.status in {"approved", "rejected"}:
            if self.event_id is None or self.decided_by is None:
                raise ValueError(
                    "approved or rejected actions require event_id and decided_by"
                )
        elif any((self.event_id, self.decided_by, self.decided_at)):
            raise ValueError(
                "approval decision evidence is only valid for approved or rejected "
                "actions"
            )
        return self


ALL_ACTION_DEFINITIONS: Dict[str, AgentActionDefinition] = {
    **RUNTIME_ACTIONS,
    **WORKFLOW_ACTIONS,
}


class _ActionEnvelopeBase(_StrictBoundaryModel):
    schema_version: Literal["workflow.action/v1"] = "workflow.action/v1"
    action_id: NonEmptyString
    kind: str
    workflow_id: int = Field(gt=0)
    requested_by: Literal["user", "agent", "system"]
    idempotency_key: IdempotencyKey
    correlation_id: CorrelationId
    execution_owner: ExecutionOwner
    policy: ActionPolicy
    approval: ActionApproval
    input_artifacts: List[ArtifactReference] = Field(default_factory=list)
    expected_output_artifacts: List[ArtifactReference] = Field(default_factory=list)
    preconditions: List[ActionPrecondition] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    @model_validator(mode="after")
    def enforce_registry_policy(self) -> "_ActionEnvelopeBase":
        definition = ALL_ACTION_DEFINITIONS.get(self.kind)
        if definition is None:
            raise ValueError(f"Unsupported action envelope kind: {self.kind}")
        if self.policy.risk_level != definition.risk_level:
            raise ValueError(
                f"risk_level for {self.kind} must be {definition.risk_level}"
            )
        if self.policy.requires_approval != definition.requires_approval:
            raise ValueError(
                f"requires_approval for {self.kind} must be "
                f"{definition.requires_approval}"
            )
        if self.execution_owner != definition.execution_owner:
            raise ValueError(
                f"execution_owner for {self.kind} must be "
                f"{definition.execution_owner}"
            )
        if definition.requires_approval:
            if self.approval.status == "not_required":
                raise ValueError(f"{self.kind} requires an approval status")
        elif self.approval.status != "not_required":
            raise ValueError(f"{self.kind} does not accept an approval decision")
        return self


class ChooseProjectDataAction(_ActionEnvelopeBase):
    kind: Literal["choose_project_data"]


class LoadVisualizationAction(_ActionEnvelopeBase):
    kind: Literal["load_visualization"]


class StartInferenceAction(_ActionEnvelopeBase):
    kind: Literal["start_inference"]


class StopInferenceAction(_ActionEnvelopeBase):
    kind: Literal["stop_inference"]
    operation_id: Optional[int] = Field(default=None, gt=0)


class StartProofreadingAction(_ActionEnvelopeBase):
    kind: Literal["start_proofreading"]


class TrainingVolumeSubset(_StrictBoundaryModel):
    selection_basis: Optional[NonEmptyString] = None
    training_statuses: List[NonEmptyString] = Field(default_factory=list)
    train_volume_count: Optional[int] = Field(default=None, ge=0)
    target_volume_count: Optional[int] = Field(default=None, ge=0)
    review_volume_count: Optional[int] = Field(default=None, ge=0)
    manifest_path: Optional[NonEmptyString] = None


class StartTrainingAction(_ActionEnvelopeBase):
    kind: Literal["start_training"]
    autopick_parameters: Optional[bool] = None
    parameter_mode: Optional[NonEmptyString] = None
    volume_subset: Optional[TrainingVolumeSubset] = None


class StopTrainingAction(_ActionEnvelopeBase):
    kind: Literal["stop_training"]
    operation_id: Optional[int] = Field(default=None, gt=0)


class ComputeEvaluationAction(_ActionEnvelopeBase):
    kind: Literal["compute_evaluation"]
    name: Optional[NonEmptyString] = None
    baseline_prediction_path: Optional[NonEmptyString] = None
    candidate_prediction_path: Optional[NonEmptyString] = None
    ground_truth_path: Optional[NonEmptyString] = None
    baseline_run_id: Optional[int] = Field(default=None, gt=0)
    candidate_run_id: Optional[int] = Field(default=None, gt=0)
    model_version_id: Optional[int] = Field(default=None, gt=0)


class ExportBundleAction(_ActionEnvelopeBase):
    kind: Literal["export_bundle"]


class ProposeRetrainingStageAction(_ActionEnvelopeBase):
    kind: Literal["propose_retraining_stage"]
    corrected_mask_path: Optional[NonEmptyString] = None


AgentActionEnvelope = Annotated[
    Union[
        ChooseProjectDataAction,
        LoadVisualizationAction,
        StartInferenceAction,
        StopInferenceAction,
        StartProofreadingAction,
        StartTrainingAction,
        StopTrainingAction,
        ComputeEvaluationAction,
        ExportBundleAction,
        ProposeRetrainingStageAction,
    ],
    Field(discriminator="kind"),
]


class AgentActionError(_StrictBoundaryModel):
    code: NonEmptyString
    message: NonEmptyString
    retryable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class _ActionReceiptBase(_StrictBoundaryModel):
    schema_version: Literal["workflow.action-receipt/v1"] = "workflow.action-receipt/v1"
    receipt_id: NonEmptyString
    action_id: NonEmptyString
    kind: str
    workflow_id: int = Field(gt=0)
    idempotency_key: IdempotencyKey
    correlation_id: CorrelationId
    status: ReceiptStatus
    operation_id: Optional[int] = Field(default=None, gt=0)
    produced_artifacts: List[ArtifactReference] = Field(default_factory=list)
    error: Optional[AgentActionError] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_receipt_state(self) -> "_ActionReceiptBase":
        if self.status == "failed" and self.error is None:
            raise ValueError("failed action receipts require an error")
        if self.status != "failed" and self.error is not None:
            raise ValueError("error is only valid for failed action receipts")
        if self.status in {"succeeded", "failed", "cancelled"}:
            if self.completed_at is None:
                raise ValueError("terminal action receipts require completed_at")
        elif self.completed_at is not None:
            raise ValueError("non-terminal action receipts cannot have completed_at")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at cannot precede started_at")

        success_fields = {
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
        }
        success_field = success_fields.get(self.kind)
        if self.status == "succeeded" and success_field:
            if not getattr(self, success_field, None):
                raise ValueError(
                    f"succeeded {self.kind} receipts require {success_field}"
                )
        return self


class ChooseProjectDataReceipt(_ActionReceiptBase):
    kind: Literal["choose_project_data"]
    selected_artifacts: List[ArtifactReference] = Field(default_factory=list)


class LoadVisualizationReceipt(_ActionReceiptBase):
    kind: Literal["load_visualization"]
    viewer_url: Optional[NonEmptyString] = None


class StartInferenceReceipt(_ActionReceiptBase):
    kind: Literal["start_inference"]
    run_id: Optional[NonEmptyString] = None


class StopInferenceReceipt(_ActionReceiptBase):
    kind: Literal["stop_inference"]
    stopped: Optional[bool] = None


class StartProofreadingReceipt(_ActionReceiptBase):
    kind: Literal["start_proofreading"]
    proofreading_session_id: Optional[int] = Field(default=None, gt=0)
    viewer_url: Optional[NonEmptyString] = None


class StartTrainingReceipt(_ActionReceiptBase):
    kind: Literal["start_training"]
    run_id: Optional[NonEmptyString] = None


class StopTrainingReceipt(_ActionReceiptBase):
    kind: Literal["stop_training"]
    stopped: Optional[bool] = None


class ComputeEvaluationReceipt(_ActionReceiptBase):
    kind: Literal["compute_evaluation"]
    evaluation_result_id: Optional[int] = Field(default=None, gt=0)
    metrics: Dict[str, float] = Field(default_factory=dict)


class ExportBundleReceipt(_ActionReceiptBase):
    kind: Literal["export_bundle"]
    bundle_artifact: Optional[ArtifactReference] = None


class ProposeRetrainingStageReceipt(_ActionReceiptBase):
    kind: Literal["propose_retraining_stage"]
    workflow_event_id: Optional[int] = Field(default=None, gt=0)
    staged_workflow_stage: Literal["retraining_staged"] = "retraining_staged"


AgentActionReceipt = Annotated[
    Union[
        ChooseProjectDataReceipt,
        LoadVisualizationReceipt,
        StartInferenceReceipt,
        StopInferenceReceipt,
        StartProofreadingReceipt,
        StartTrainingReceipt,
        StopTrainingReceipt,
        ComputeEvaluationReceipt,
        ExportBundleReceipt,
        ProposeRetrainingStageReceipt,
    ],
    Field(discriminator="kind"),
]


_ACTION_ENVELOPE_ADAPTER = TypeAdapter(AgentActionEnvelope)
_ACTION_RECEIPT_ADAPTER = TypeAdapter(AgentActionReceipt)


def canonical_action_policy(kind: str) -> ActionPolicy:
    definition = ALL_ACTION_DEFINITIONS.get(kind)
    if definition is None:
        raise ValueError(f"Unsupported action envelope kind: {kind}")
    return ActionPolicy(
        risk_level=definition.risk_level,
        requires_approval=definition.requires_approval,
    )


def validate_action_envelope(payload: Any) -> AgentActionEnvelope:
    return _ACTION_ENVELOPE_ADAPTER.validate_python(payload)


def validate_action_for_execution(payload: Any) -> AgentActionEnvelope:
    envelope = validate_action_envelope(payload)
    if envelope.policy.requires_approval and envelope.approval.status != "approved":
        raise ValueError(
            f"{envelope.kind} cannot execute without an approved action envelope"
        )
    return envelope


def validate_action_receipt(payload: Any) -> AgentActionReceipt:
    return _ACTION_RECEIPT_ADAPTER.validate_python(payload)


def validate_receipt_for_action(
    action_payload: Any, receipt_payload: Any
) -> AgentActionReceipt:
    action = validate_action_envelope(action_payload)
    receipt = validate_action_receipt(receipt_payload)
    matching_fields = (
        "action_id",
        "kind",
        "workflow_id",
        "idempotency_key",
        "correlation_id",
    )
    mismatches = [
        field
        for field in matching_fields
        if getattr(action, field) != getattr(receipt, field)
    ]
    if mismatches:
        raise ValueError(
            "action receipt does not match its envelope: " + ", ".join(mismatches)
        )
    return receipt


def dump_action_envelope_json(payload: Any) -> bytes:
    return _ACTION_ENVELOPE_ADAPTER.dump_json(validate_action_envelope(payload))


def load_action_envelope_json(payload: Union[str, bytes]) -> AgentActionEnvelope:
    return _ACTION_ENVELOPE_ADAPTER.validate_json(payload)


def dump_action_receipt_json(payload: Any) -> bytes:
    return _ACTION_RECEIPT_ADAPTER.dump_json(validate_action_receipt(payload))


def load_action_receipt_json(payload: Union[str, bytes]) -> AgentActionReceipt:
    return _ACTION_RECEIPT_ADAPTER.validate_json(payload)


def action_envelope_json_schema() -> Dict[str, Any]:
    return _ACTION_ENVELOPE_ADAPTER.json_schema()


def action_receipt_json_schema() -> Dict[str, Any]:
    return _ACTION_RECEIPT_ADAPTER.json_schema()


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
