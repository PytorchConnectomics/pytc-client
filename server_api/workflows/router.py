from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app_event_logger import append_app_event
from server_api.auth import models as auth_models
from server_api.auth.database import get_db
from server_api.auth.router import (
    get_current_user,
    _looks_like_image_label_pair,
    _project_extension,
    _role_for_project_file,
    _scan_project_profile,
)

from .db_models import (
    WorkflowAgentPlan,
    WorkflowAgentStep,
    WorkflowArtifact,
    WorkflowCommand,
    WorkflowCorrectionSet,
    WorkflowEvaluationResult,
    WorkflowEvent,
    WorkflowModelRun,
    WorkflowModelVersion,
    WorkflowRegionHotspot,
    WorkflowSession,
)
from .service import (
    agent_plan_to_dict,
    agent_step_to_dict,
    append_workflow_event,
    artifact_to_dict,
    command_to_dict,
    correction_set_to_dict,
    create_workflow_command,
    create_workflow_session,
    create_workflow_artifact,
    decode_json,
    encode_json,
    evaluation_result_to_dict,
    event_to_dict,
    get_current_or_create_workflow,
    get_user_workflow_or_404,
    model_run_to_dict,
    model_version_to_dict,
    region_hotspot_to_dict,
    update_workflow_fields,
    validate_stage,
    workflow_to_dict,
)
from .bundle_export import build_export_bundle, write_export_bundle_directory
from .agent_plan import build_case_study_plan_graph
from .evaluation import compute_before_after_evaluation, write_evaluation_report
from .metrics import compute_workflow_metrics
from .volume_pairs import discover_neuroglancer_volume_pairs

router = APIRouter()


class WorkflowResponse(BaseModel):
    id: int
    user_id: int
    title: Optional[str] = None
    stage: str
    dataset_path: Optional[str] = None
    image_path: Optional[str] = None
    label_path: Optional[str] = None
    mask_path: Optional[str] = None
    neuroglancer_url: Optional[str] = None
    inference_output_path: Optional[str] = None
    checkpoint_path: Optional[str] = None
    config_path: Optional[str] = None
    proofreading_session_id: Optional[int] = None
    corrected_mask_path: Optional[str] = None
    training_output_path: Optional[str] = None
    metadata_json: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any
    updated_at: Any


class WorkflowEventResponse(BaseModel):
    id: int
    workflow_id: int
    actor: str
    event_type: str
    stage: Optional[str] = None
    summary: str
    payload_json: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1
    idempotency_key: Optional[str] = None
    approval_status: str
    created_at: Any


class WorkflowDetailResponse(BaseModel):
    workflow: WorkflowResponse
    events: List[WorkflowEventResponse]


class WorkflowUpdateRequest(BaseModel):
    title: Optional[str] = None
    stage: Optional[str] = None
    dataset_path: Optional[str] = None
    image_path: Optional[str] = None
    label_path: Optional[str] = None
    mask_path: Optional[str] = None
    neuroglancer_url: Optional[str] = None
    inference_output_path: Optional[str] = None
    checkpoint_path: Optional[str] = None
    config_path: Optional[str] = None
    proofreading_session_id: Optional[int] = None
    corrected_mask_path: Optional[str] = None
    training_output_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkflowResetRequest(BaseModel):
    title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowEventCreateRequest(BaseModel):
    actor: str = "system"
    event_type: str
    stage: Optional[str] = None
    summary: str
    payload: Optional[Dict[str, Any]] = None
    schema_version: int = 1
    idempotency_key: Optional[str] = None
    approval_status: str = "not_required"


class AgentActionCreateRequest(BaseModel):
    action: str
    summary: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentQueryRequest(BaseModel):
    query: str
    conversation_id: Optional[int] = None
    conversationId: Optional[int] = None


class AgentChatAction(BaseModel):
    id: str
    label: str
    description: str
    variant: str = "default"
    run_label: str = "Run in app"
    risk_level: str = "read_only"
    requires_approval: bool = False
    disabled_reason: Optional[str] = None
    client_effects: Dict[str, Any] = Field(default_factory=dict)


class AgentCommandBlock(BaseModel):
    id: str
    title: str
    description: str
    command: str
    run_label: str = "Execute"
    risk_level: str = "read_only"
    requires_approval: bool = False
    client_effects: Dict[str, Any] = Field(default_factory=dict)


class AgentTaskItem(BaseModel):
    id: str
    label: str
    status: str
    detail: str
    priority: str = "normal"


class AgentTraceItem(BaseModel):
    label: str
    detail: str
    status: str = "checked"


class AgentQueryResponse(BaseModel):
    response: str
    source: str = "workflow_orchestrator"
    intent: str = "recommendation"
    permission_mode: str = "approval_required_for_runtime"
    conversation_id: Optional[int] = None
    conversationId: Optional[int] = None
    proposals: List[WorkflowEventResponse] = Field(default_factory=list)
    actions: List[AgentChatAction] = Field(default_factory=list)
    commands: List[AgentCommandBlock] = Field(default_factory=list)
    tasks: List[AgentTaskItem] = Field(default_factory=list)
    trace: List[AgentTraceItem] = Field(default_factory=list)


class WorkflowCommandResponse(BaseModel):
    id: int
    workflow_id: int
    command_type: str
    status: str
    idempotency_key: str
    actor: str
    source_event_id: Optional[int] = None
    approval_event_id: Optional[int] = None
    input_json: Optional[str] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    result_json: Optional[str] = None
    result: Dict[str, Any] = Field(default_factory=dict)
    error_json: Optional[str] = None
    error: Dict[str, Any] = Field(default_factory=dict)
    attempt_count: int = 0
    lease_owner: Optional[str] = None
    lease_expires_at: Any = None
    started_at: Any = None
    completed_at: Any = None
    created_at: Any
    updated_at: Any


class AgentActionResult(BaseModel):
    workflow: WorkflowResponse
    proposal: WorkflowEventResponse
    events: List[WorkflowEventResponse]
    client_effects: Dict[str, Any] = Field(default_factory=dict)
    commands: List[WorkflowCommandResponse] = Field(default_factory=list)


class WorkflowHotspotItem(BaseModel):
    rank: int
    region_key: str
    score: float
    severity: str
    summary: str
    recommended_action: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class WorkflowHotspotsResponse(BaseModel):
    workflow_id: int
    generated_at: str
    hotspots: List[WorkflowHotspotItem] = Field(default_factory=list)


class WorkflowImpactPreviewResponse(BaseModel):
    workflow_id: int
    generated_at: str
    can_stage_retraining: bool
    recommended_stage: str
    corrected_mask_path: Optional[str] = None
    confidence: str
    projected_improvement: float
    summary: str
    signals: Dict[str, int] = Field(default_factory=dict)
    next_actions: List[str] = Field(default_factory=list)


class WorkflowReadinessItem(BaseModel):
    id: str
    label: str
    complete: bool
    detail: str
    severity: str = "default"


class WorkflowAgentRecommendationResponse(BaseModel):
    workflow_id: int
    generated_at: str
    stage: str
    decision: str
    rationale: str
    confidence: str
    next_stage: str
    can_act: bool = True
    blockers: List[str] = Field(default_factory=list)
    readiness: List[WorkflowReadinessItem] = Field(default_factory=list)
    top_hotspot: Optional[WorkflowHotspotItem] = None
    impact_preview: Optional[WorkflowImpactPreviewResponse] = None
    actions: List[AgentChatAction] = Field(default_factory=list)
    commands: List[AgentCommandBlock] = Field(default_factory=list)


class WorkflowPreflightItem(BaseModel):
    id: str
    label: str
    status: str
    can_run: bool = False
    missing: List[str] = Field(default_factory=list)
    action: str
    risk_level: str = "normal"


class WorkflowPreflightResponse(BaseModel):
    workflow_id: int
    generated_at: str
    overall_status: str
    summary: str
    items: List[WorkflowPreflightItem] = Field(default_factory=list)


class WorkflowMetricsResponse(BaseModel):
    workflow_id: int
    metrics: Dict[str, Any] = Field(default_factory=dict)


class WorkflowProjectProgressVolume(BaseModel):
    id: str
    name: str
    status: str
    status_label: str
    status_source: str
    project_root: Optional[str] = None
    volume_set_id: Optional[str] = None
    volume_set_name: Optional[str] = None
    image_path: Optional[str] = None
    segmentation_path: Optional[str] = None
    segmentation_kind: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    note: Optional[str] = None


class WorkflowProjectProgressResponse(BaseModel):
    workflow_id: int
    generated_at: str
    project_name: Optional[str] = None
    project_roots: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    status_definitions: Dict[str, str] = Field(default_factory=dict)
    volumes: List[WorkflowProjectProgressVolume] = Field(default_factory=list)


class WorkflowProjectProgressVolumeUpdate(BaseModel):
    volume_id: str
    status: Optional[str] = None
    note: Optional[str] = None


class WorkflowExportBundleResponse(BaseModel):
    schema_version: str
    exported_at: str
    workflow_id: int
    session_snapshot: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    model_runs: List[Dict[str, Any]] = Field(default_factory=list)
    model_versions: List[Dict[str, Any]] = Field(default_factory=list)
    correction_sets: List[Dict[str, Any]] = Field(default_factory=list)
    evaluation_results: List[Dict[str, Any]] = Field(default_factory=list)
    persisted_hotspots: List[Dict[str, Any]] = Field(default_factory=list)
    agent_plans: List[Dict[str, Any]] = Field(default_factory=list)
    artifact_paths: List[Dict[str, Any]] = Field(default_factory=list)
    bundle_directory: Optional[str] = None
    bundle_manifest_path: Optional[str] = None
    copied_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    skipped_artifacts: List[Dict[str, Any]] = Field(default_factory=list)


class WorkflowArtifactCreateRequest(BaseModel):
    artifact_type: str
    role: Optional[str] = None
    path: Optional[str] = None
    uri: Optional[str] = None
    name: Optional[str] = None
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowArtifactResponse(BaseModel):
    id: int
    workflow_id: int
    artifact_type: str
    role: Optional[str] = None
    name: Optional[str] = None
    path: Optional[str] = None
    uri: Optional[str] = None
    checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    source_event_id: Optional[int] = None
    metadata_json: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any
    exists: bool = False


class WorkflowModelRunCreateRequest(BaseModel):
    run_id: Optional[str] = None
    run_type: str
    status: str = "pending"
    name: Optional[str] = None
    config_path: Optional[str] = None
    log_path: Optional[str] = None
    output_path: Optional[str] = None
    checkpoint_path: Optional[str] = None
    input_artifact_id: Optional[int] = None
    output_artifact_id: Optional[int] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowModelRunResponse(BaseModel):
    id: int
    workflow_id: int
    run_id: Optional[str] = None
    run_type: str
    status: str
    name: Optional[str] = None
    config_path: Optional[str] = None
    log_path: Optional[str] = None
    output_path: Optional[str] = None
    checkpoint_path: Optional[str] = None
    input_artifact_id: Optional[int] = None
    output_artifact_id: Optional[int] = None
    source_event_id: Optional[int] = None
    metrics_json: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    started_at: Any = None
    completed_at: Any = None
    created_at: Any
    updated_at: Any


class WorkflowModelVersionCreateRequest(BaseModel):
    version_label: str
    status: str = "candidate"
    checkpoint_path: Optional[str] = None
    training_run_id: Optional[int] = None
    checkpoint_artifact_id: Optional[int] = None
    correction_set_id: Optional[int] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowModelVersionResponse(BaseModel):
    id: int
    workflow_id: int
    version_label: str
    status: str
    checkpoint_path: Optional[str] = None
    training_run_id: Optional[int] = None
    checkpoint_artifact_id: Optional[int] = None
    correction_set_id: Optional[int] = None
    metrics_json: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any


class WorkflowCorrectionSetResponse(BaseModel):
    id: int
    workflow_id: int
    artifact_id: Optional[int] = None
    corrected_mask_path: str
    source_mask_path: Optional[str] = None
    proofreading_session_id: Optional[int] = None
    edit_count: int = 0
    region_count: int = 0
    source_event_id: Optional[int] = None
    metadata_json: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any


class WorkflowEvaluationCreateRequest(BaseModel):
    name: Optional[str] = None
    baseline_run_id: Optional[int] = None
    candidate_run_id: Optional[int] = None
    model_version_id: Optional[int] = None
    report_path: Optional[str] = None
    summary: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowEvaluationComputeRequest(BaseModel):
    baseline_prediction_path: str
    candidate_prediction_path: str
    ground_truth_path: str
    baseline_dataset: Optional[str] = None
    candidate_dataset: Optional[str] = None
    ground_truth_dataset: Optional[str] = None
    crop: Optional[str] = None
    baseline_channel: Optional[int] = None
    candidate_channel: Optional[int] = None
    ground_truth_channel: Optional[int] = None
    name: Optional[str] = None
    baseline_run_id: Optional[int] = None
    candidate_run_id: Optional[int] = None
    model_version_id: Optional[int] = None
    report_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowEvaluationResponse(BaseModel):
    id: int
    workflow_id: int
    name: Optional[str] = None
    baseline_run_id: Optional[int] = None
    candidate_run_id: Optional[int] = None
    model_version_id: Optional[int] = None
    report_artifact_id: Optional[int] = None
    report_path: Optional[str] = None
    summary: Optional[str] = None
    metrics_json: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any


class WorkflowRegionHotspotResponse(BaseModel):
    id: int
    workflow_id: int
    region_key: str
    score: float
    severity: str
    status: str
    source: str
    evidence_json: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any
    updated_at: Any


class WorkflowAgentStepResponse(BaseModel):
    id: int
    plan_id: int
    step_index: int
    action: str
    status: str
    requires_approval: bool
    summary: Optional[str] = None
    params_json: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    result_json: Optional[str] = None
    result: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any
    updated_at: Any


class WorkflowAgentPlanResponse(BaseModel):
    id: int
    workflow_id: int
    title: str
    status: str
    risk_level: str
    approval_status: str
    goal: Optional[str] = None
    graph_json: Optional[str] = None
    graph: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_event_id: Optional[int] = None
    created_at: Any
    updated_at: Any
    steps: List[WorkflowAgentStepResponse] = Field(default_factory=list)


class WorkflowAgentPlanCreateRequest(BaseModel):
    title: Optional[str] = None
    goal: Optional[str] = None
    plan_type: str = "case_study_closed_loop"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowAgentStepCompleteRequest(BaseModel):
    status: str = "completed"
    result: Dict[str, Any] = Field(default_factory=dict)


class WorkflowReadinessResponse(BaseModel):
    workflow_id: int
    ready_for_case_study: bool
    completed_count: int
    total_count: int
    gates: List[Dict[str, Any]] = Field(default_factory=list)
    next_required_items: List[str] = Field(default_factory=list)


def _workflow_response(workflow: WorkflowSession) -> WorkflowResponse:
    return WorkflowResponse(**workflow_to_dict(workflow))


def _event_response(event: WorkflowEvent) -> WorkflowEventResponse:
    return WorkflowEventResponse(**event_to_dict(event))


def _artifact_response(artifact: WorkflowArtifact) -> WorkflowArtifactResponse:
    return WorkflowArtifactResponse(**artifact_to_dict(artifact))


def _model_run_response(run: WorkflowModelRun) -> WorkflowModelRunResponse:
    return WorkflowModelRunResponse(**model_run_to_dict(run))


def _model_version_response(
    version: WorkflowModelVersion,
) -> WorkflowModelVersionResponse:
    return WorkflowModelVersionResponse(**model_version_to_dict(version))


def _correction_set_response(
    correction_set: WorkflowCorrectionSet,
) -> WorkflowCorrectionSetResponse:
    return WorkflowCorrectionSetResponse(**correction_set_to_dict(correction_set))


def _evaluation_response(
    result: WorkflowEvaluationResult,
) -> WorkflowEvaluationResponse:
    return WorkflowEvaluationResponse(**evaluation_result_to_dict(result))


def _region_hotspot_response(
    hotspot: WorkflowRegionHotspot,
) -> WorkflowRegionHotspotResponse:
    return WorkflowRegionHotspotResponse(**region_hotspot_to_dict(hotspot))


def _agent_step_response(step: WorkflowAgentStep) -> WorkflowAgentStepResponse:
    return WorkflowAgentStepResponse(**agent_step_to_dict(step))


def _agent_plan_response(plan: WorkflowAgentPlan) -> WorkflowAgentPlanResponse:
    return WorkflowAgentPlanResponse(**agent_plan_to_dict(plan))


def _command_response(command: WorkflowCommand) -> WorkflowCommandResponse:
    return WorkflowCommandResponse(**command_to_dict(command))


def _event_list(db: Session, workflow_id: int) -> List[WorkflowEventResponse]:
    events = (
        db.query(WorkflowEvent)
        .filter(WorkflowEvent.workflow_id == workflow_id)
        .order_by(WorkflowEvent.created_at.asc(), WorkflowEvent.id.asc())
        .all()
    )
    return [_event_response(event) for event in events]


def _event_rows(db: Session, workflow_id: int) -> List[WorkflowEvent]:
    return (
        db.query(WorkflowEvent)
        .filter(WorkflowEvent.workflow_id == workflow_id)
        .order_by(WorkflowEvent.created_at.asc(), WorkflowEvent.id.asc())
        .all()
    )


def _get_pending_proposal_or_404(
    db: Session, *, workflow_id: int, event_id: int
) -> WorkflowEvent:
    event = (
        db.query(WorkflowEvent)
        .filter(
            WorkflowEvent.id == event_id,
            WorkflowEvent.workflow_id == workflow_id,
            WorkflowEvent.event_type == "agent.proposal_created",
        )
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Agent proposal not found")
    if event.approval_status != "pending":
        raise HTTPException(status_code=400, detail="Agent proposal is not pending")
    return event


def _get_agent_plan_or_404(
    db: Session, *, workflow_id: int, plan_id: int
) -> WorkflowAgentPlan:
    plan = (
        db.query(WorkflowAgentPlan)
        .filter(
            WorkflowAgentPlan.id == plan_id,
            WorkflowAgentPlan.workflow_id == workflow_id,
        )
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Agent plan not found")
    return plan


def _get_agent_step_or_404(
    db: Session, *, plan_id: int, step_id: int
) -> WorkflowAgentStep:
    step = (
        db.query(WorkflowAgentStep)
        .filter(
            WorkflowAgentStep.id == step_id,
            WorkflowAgentStep.plan_id == plan_id,
        )
        .first()
    )
    if not step:
        raise HTTPException(status_code=404, detail="Agent plan step not found")
    return step


def _latest_exported_mask_path(db: Session, workflow_id: int) -> Optional[str]:
    event = (
        db.query(WorkflowEvent)
        .filter(
            WorkflowEvent.workflow_id == workflow_id,
            WorkflowEvent.event_type == "proofreading.masks_exported",
        )
        .order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc())
        .first()
    )
    if not event:
        return None
    payload = decode_json(event.payload_json)
    return payload.get("written_path") or payload.get("output_path")


def _proposal_action_payload(proposal: WorkflowEvent) -> Dict[str, Any]:
    payload = decode_json(proposal.payload_json)
    params = payload.get("params")
    if not isinstance(params, dict):
        params = {}
    return {"action": payload.get("action"), "params": params}


NEGATIVE_CLASSIFICATIONS = {
    "incorrect",
    "uncertain",
    "error",
    "false_positive",
    "false_negative",
    "needs_review",
}


def _region_key_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("region_key", "region_id", "region"):
        value = payload.get(key)
        if isinstance(value, (str, int, float)):
            return str(value)

    instance_id = payload.get("instance_id")
    if isinstance(instance_id, (str, int)):
        return f"instance:{instance_id}"

    instance_ids = payload.get("instance_ids")
    if isinstance(instance_ids, list) and instance_ids:
        first = instance_ids[0]
        if isinstance(first, (str, int)):
            return f"instance:{first}"

    axis = payload.get("axis")
    z_index = payload.get("z_index")
    if axis is not None and z_index is not None:
        return f"{axis}:{z_index}"
    if z_index is not None:
        return f"z:{z_index}"
    return None


def _hotspot_severity(score: float) -> str:
    if score >= 8:
        return "high"
    if score >= 4:
        return "medium"
    return "low"


def _default_region_action(workflow: WorkflowSession, severity: str) -> str:
    if workflow.stage == "proofreading":
        return "Proofread this likely mistake."
    if severity == "high":
        return "Proofread this region before training again."
    if workflow.stage in {"visualization", "inference"}:
        return "Inspect this region, then proofread it if the mask looks wrong."
    return "Check this region and mark whether the mask is usable."


def _compute_hotspots(
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
) -> List[WorkflowHotspotItem]:
    region_stats: Dict[str, Dict[str, Any]] = {}

    def ensure_region(region_key: str) -> Dict[str, Any]:
        stat = region_stats.get(region_key)
        if stat:
            return stat
        stat = {
            "raw_score": 0.0,
            "inference_failures": 0,
            "classifications": 0,
            "negative_classifications": 0,
            "mask_saves": 0,
            "exports": 0,
            "last_event_index": -1,
        }
        region_stats[region_key] = stat
        return stat

    for index, event in enumerate(events):
        payload = decode_json(event.payload_json)
        region_key = _region_key_from_payload(payload)
        stat = ensure_region(region_key) if region_key else None

        if event.event_type == "inference.failed" and stat:
            stat["raw_score"] += 4.0
            stat["inference_failures"] += 1
            stat["last_event_index"] = index

        if event.event_type == "proofreading.instance_classified" and stat:
            classification = str(payload.get("classification") or "").lower()
            if classification in NEGATIVE_CLASSIFICATIONS:
                stat["raw_score"] += 2.5
                stat["negative_classifications"] += 1
            else:
                stat["raw_score"] += 1.0
            stat["classifications"] += 1
            stat["last_event_index"] = index

        if event.event_type == "proofreading.mask_saved" and stat:
            stat["raw_score"] += 3.0
            stat["mask_saves"] += 1
            stat["last_event_index"] = index

        if event.event_type == "proofreading.masks_exported":
            if stat:
                stat["raw_score"] += 1.0
                stat["exports"] += 1
                stat["last_event_index"] = index
            else:
                # Export happened without region metadata; keep evidence visible.
                global_region = ensure_region("current_view")
                global_region["raw_score"] += 1.0
                global_region["exports"] += 1
                global_region["last_event_index"] = index

    if not region_stats:
        region_stats["current_view"] = {
            "raw_score": 1.0,
            "inference_failures": 0,
            "classifications": 0,
            "negative_classifications": 0,
            "mask_saves": 0,
            "exports": 0,
            "last_event_index": len(events) - 1,
        }

    total_events = max(len(events), 1)
    ranked: List[WorkflowHotspotItem] = []
    for region_key, stat in region_stats.items():
        distance = max(0, (total_events - 1) - stat["last_event_index"])
        recency_bonus = max(0.0, 1.5 - (distance * 0.25))
        score = round(float(stat["raw_score"] + recency_bonus), 2)
        severity = _hotspot_severity(score)

        summary = (
            f"{region_key}: {stat['inference_failures']} inference failures, "
            f"{stat['mask_saves']} mask edits, "
            f"{stat['negative_classifications']} uncertain/incorrect classifications."
        )
        recommended_action = _default_region_action(workflow, severity)
        if stat["exports"] > 0 and workflow.stage != "retraining_staged":
            recommended_action = "Use these saved edits for training."

        ranked.append(
            WorkflowHotspotItem(
                rank=0,
                region_key=region_key,
                score=score,
                severity=severity,
                summary=summary,
                recommended_action=recommended_action,
                evidence={
                    "inference_failures": stat["inference_failures"],
                    "classifications": stat["classifications"],
                    "negative_classifications": stat["negative_classifications"],
                    "mask_saves": stat["mask_saves"],
                    "exports": stat["exports"],
                },
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    return [
        item.model_copy(update={"rank": index + 1}) for index, item in enumerate(ranked)
    ]


def _persist_computed_hotspots(
    db: Session,
    *,
    workflow_id: int,
    hotspots: List[WorkflowHotspotItem],
) -> None:
    for item in hotspots:
        existing = (
            db.query(WorkflowRegionHotspot)
            .filter(
                WorkflowRegionHotspot.workflow_id == workflow_id,
                WorkflowRegionHotspot.region_key == item.region_key,
            )
            .first()
        )
        evidence = {
            **(item.evidence or {}),
            "summary": item.summary,
            "recommended_action": item.recommended_action,
            "rank": item.rank,
        }
        if existing:
            existing.score = item.score
            existing.severity = item.severity
            existing.evidence_json = encode_json(evidence)
            existing.source = "event_heuristic"
        else:
            db.add(
                WorkflowRegionHotspot(
                    workflow_id=workflow_id,
                    region_key=item.region_key,
                    score=item.score,
                    severity=item.severity,
                    evidence_json=encode_json(evidence),
                    source="event_heuristic",
                )
            )
    db.commit()


def _compute_impact_preview(
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
    hotspots: List[WorkflowHotspotItem],
    corrected_mask_path: Optional[str],
) -> WorkflowImpactPreviewResponse:
    signals = {
        "inference_started": 0,
        "inference_completed": 0,
        "inference_failed": 0,
        "training_completed": 0,
        "training_failed": 0,
        "proofreading_classified": 0,
        "proofreading_mask_saved": 0,
        "proofreading_masks_exported": 0,
        "pending_agent_proposals": 0,
    }
    for event in events:
        if event.event_type == "inference.started":
            signals["inference_started"] += 1
        if event.event_type == "inference.completed":
            signals["inference_completed"] += 1
        if event.event_type == "inference.failed":
            signals["inference_failed"] += 1
        if event.event_type == "training.completed":
            signals["training_completed"] += 1
        if event.event_type == "training.failed":
            signals["training_failed"] += 1
        if event.event_type == "proofreading.instance_classified":
            signals["proofreading_classified"] += 1
        if event.event_type == "proofreading.mask_saved":
            signals["proofreading_mask_saved"] += 1
        if event.event_type == "proofreading.masks_exported":
            signals["proofreading_masks_exported"] += 1
        if (
            event.event_type == "agent.proposal_created"
            and event.approval_status == "pending"
        ):
            signals["pending_agent_proposals"] += 1

    correction_signal = (
        (signals["proofreading_classified"] * 2)
        + (signals["proofreading_mask_saved"] * 3)
        + (signals["proofreading_masks_exported"] * 5)
    )
    failure_signal = signals["inference_failed"] * 3
    hotspot_signal = len([item for item in hotspots if item.severity == "high"]) * 4
    projected_improvement = min(
        0.95,
        round(
            0.05
            + (correction_signal * 0.03)
            + (failure_signal * 0.02)
            + (hotspot_signal * 0.01),
            3,
        ),
    )

    confidence = "low"
    if correction_signal >= 8 and signals["proofreading_masks_exported"] > 0:
        confidence = "high"
    elif correction_signal >= 3:
        confidence = "medium"

    can_stage_retraining = (
        bool(corrected_mask_path) and workflow.stage != "retraining_staged"
    )
    recommended_stage = workflow.stage
    if can_stage_retraining:
        recommended_stage = "retraining_staged"
    elif workflow.stage == "retraining_staged":
        recommended_stage = "evaluation"

    next_actions: List[str] = []
    if hotspots:
        next_actions.append(hotspots[0].recommended_action)
    if not corrected_mask_path:
        next_actions.append(
            "Export corrected masks from proofreading to create a retraining artifact."
        )
    elif can_stage_retraining:
        next_actions.append(
            "Approve or trigger retraining staging from corrected masks."
        )
    if workflow.stage == "retraining_staged":
        next_actions.append(
            "Open Model Training and launch the next experiment using staged labels."
        )
    if workflow.stage == "evaluation":
        next_actions.append(
            "Run inference with the latest trained checkpoint to evaluate the new model iteration."
        )
        next_actions.append(
            "Open TensorBoard if you want to inspect the completed training run before inference."
        )

    if workflow.stage == "evaluation" and signals["training_completed"] > 0:
        summary = "A new model iteration is ready. Run inference with the latest checkpoint and compare it against the prior result."
    elif workflow.stage == "evaluation" and signals["training_failed"] > 0:
        summary = "The last training run failed. Review the runtime log before launching another iteration."
    elif confidence == "low":
        summary = "Correction evidence is still sparse; prioritize proofreading edits before retraining."
    elif can_stage_retraining:
        summary = "Corrections are substantial enough to justify retraining staging for the next model iteration."
    else:
        summary = "Correction evidence is accumulating; compare outcomes after the next staged loop."

    return WorkflowImpactPreviewResponse(
        workflow_id=workflow.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        can_stage_retraining=can_stage_retraining,
        recommended_stage=recommended_stage,
        corrected_mask_path=corrected_mask_path,
        confidence=confidence,
        projected_improvement=projected_improvement,
        summary=summary,
        signals=signals,
        next_actions=next_actions,
    )


def _recommendation_for_workflow(
    workflow: WorkflowSession,
    events: List[WorkflowEventResponse],
) -> str:
    if workflow.stage == "setup":
        return "Start by loading an image volume and, if available, the current mask or label volume."
    if workflow.stage == "visualization":
        return "Proofread the mask if it is ready; otherwise run the model to make one."
    if workflow.stage == "inference":
        return "Run the model, then proofread the result."
    if workflow.stage == "proofreading":
        has_export = any(
            event.event_type == "proofreading.masks_exported" for event in events
        )
        if has_export or workflow.corrected_mask_path:
            return "Saved edits are available. Ask the agent to train from them."
        return "Keep reviewing instances, then save or export edits before training."
    if workflow.stage == "retraining_staged":
        return "The saved edits are linked. Approve an agent-run training job."
    if workflow.stage == "evaluation":
        return "Training finished successfully. Use the latest checkpoint to run inference, and open TensorBoard only if you want to inspect the run."
    return "Review the workflow timeline and compare results before starting another iteration."


def _client_effects_to_command(client_effects: Dict[str, Any]) -> str:
    lines: List[str] = []
    if client_effects.get("reset_workspace"):
        lines.append("app workspace reset")

    if client_effects.get("start_new_workflow"):
        lines.append("workflow reset current session")

    mount_project = client_effects.get("mount_project") or {}
    if mount_project.get("directory_path"):
        lines.append(
            "app files mount "
            f"{json.dumps(str(mount_project.get('directory_path')))}"
        )

    navigate_to = client_effects.get("navigate_to")
    if navigate_to:
        lines.append(f"app open {navigate_to}")

    training_config_preset = client_effects.get("set_training_config_preset")
    if training_config_preset:
        lines.append(
            f"app training config auto-select {json.dumps(str(training_config_preset))}"
        )

    training_image_path = client_effects.get("set_training_image_path")
    if training_image_path:
        lines.append(f"app training image set {json.dumps(str(training_image_path))}")

    training_label_path = client_effects.get("set_training_label_path")
    if training_label_path:
        lines.append(f"app training labels set {json.dumps(str(training_label_path))}")

    training_output_path = client_effects.get("set_training_output_path")
    if training_output_path:
        lines.append(f"app training output set {json.dumps(str(training_output_path))}")

    training_log_path = client_effects.get("set_training_log_path")
    if training_log_path:
        lines.append(f"app training logs set {json.dumps(str(training_log_path))}")

    inference_output_path = client_effects.get("set_inference_output_path")
    if inference_output_path:
        lines.append(
            f"app inference output set {json.dumps(str(inference_output_path))}"
        )

    inference_checkpoint_path = client_effects.get("set_inference_checkpoint_path")
    if inference_checkpoint_path:
        lines.append(
            f"app inference checkpoint set {json.dumps(str(inference_checkpoint_path))}"
        )

    inference_config_preset = client_effects.get("set_inference_config_preset")
    if inference_config_preset:
        lines.append(
            f"app inference config auto-select {json.dumps(str(inference_config_preset))}"
        )

    inference_image_path = client_effects.get("set_inference_image_path")
    if inference_image_path:
        lines.append(f"app inference image set {json.dumps(str(inference_image_path))}")

    inference_label_path = client_effects.get("set_inference_label_path")
    if inference_label_path:
        lines.append(f"app inference labels set {json.dumps(str(inference_label_path))}")

    runtime_action = client_effects.get("runtime_action") or {}
    runtime_kind = runtime_action.get("kind")
    if runtime_kind == "start_inference":
        lines.append("app inference run")
    elif runtime_kind == "start_training":
        lines.append("app training run")
    elif runtime_kind == "start_proofreading":
        lines.append("app proofreading start")
    elif runtime_kind == "stop_inference":
        lines.append("app inference stop")
    elif runtime_kind == "stop_training":
        lines.append("app training stop")

    workflow_action = client_effects.get("workflow_action") or {}
    workflow_action_kind = workflow_action.get("kind")
    if workflow_action_kind == "compute_evaluation":
        lines.append("workflow metrics compute")
    elif workflow_action_kind == "export_bundle":
        lines.append("workflow evidence export")
    elif workflow_action_kind == "propose_retraining_stage":
        lines.append("workflow retraining handoff propose")

    if client_effects.get("show_workflow_context"):
        lines.append("assistant status show")

    if client_effects.get("refresh_insights"):
        lines.append("workflow insights refresh")

    return "\n".join(lines) or "# No app command is available for this action."


def _infer_action_risk(client_effects: Optional[Dict[str, Any]]) -> str:
    effects = client_effects or {}
    runtime_kind = (effects.get("runtime_action") or {}).get("kind")
    workflow_action_kind = (effects.get("workflow_action") or {}).get("kind")
    if runtime_kind in {"start_inference", "start_training"}:
        return "runs_job"
    if runtime_kind in {"stop_inference", "stop_training"}:
        return "controls_job"
    if runtime_kind == "start_proofreading":
        return "loads_editor"
    if runtime_kind == "choose_project_data":
        return "prefills_form"
    if effects.get("mount_project") or effects.get("reset_workspace"):
        return "modifies_workspace"
    if effects.get("start_new_workflow"):
        return "writes_workflow_record"
    if workflow_action_kind == "export_bundle":
        return "exports_evidence"
    if workflow_action_kind in {"compute_evaluation", "propose_retraining_stage"}:
        return "writes_workflow_record"
    if any(key.startswith("set_") for key in effects):
        return "prefills_form"
    if effects.get("navigate_to") or effects.get("show_workflow_context"):
        return "read_only"
    if effects.get("refresh_insights"):
        return "read_only"
    return "read_only"


def _requires_action_approval(client_effects: Optional[Dict[str, Any]]) -> bool:
    risk = _infer_action_risk(client_effects)
    return risk in {
        "runs_job",
        "controls_job",
        "loads_editor",
        "exports_evidence",
        "writes_workflow_record",
        "modifies_workspace",
    }


def _one_app_suggestion(
    actions: List[AgentChatAction],
    commands: List[AgentCommandBlock],
) -> tuple[List[AgentChatAction], List[AgentCommandBlock]]:
    if actions:
        primary = next(
            (action for action in actions if action.variant == "primary"),
            actions[0],
        )
        return [primary], []
    if commands:
        return [], [commands[0]]
    return actions, commands


def _query_is_informational_followup(lower_query: str) -> bool:
    stripped = lower_query.strip()
    if not stripped:
        return False
    question_like = (
        "?" in stripped
        or stripped.startswith(
            (
                "why ",
                "what ",
                "which ",
                "how ",
                "can you explain",
                "explain ",
                "tell me more",
            )
        )
    )
    if not question_like:
        return False
    imperative_terms = [
        "start ",
        "run ",
        "launch ",
        "open ",
        "show ",
        "go to ",
        "take me ",
        "proofread",
        "train now",
        "start training",
        "run training",
        "segment now",
        "run segmentation",
    ]
    return not any(term in stripped for term in imperative_terms)


def _build_agent_chat_action(
    action_id: str,
    label: str,
    description: str,
    *,
    variant: str = "default",
    client_effects: Optional[Dict[str, Any]] = None,
    risk_level: Optional[str] = None,
    run_label: str = "Run in app",
    requires_approval: Optional[bool] = None,
    disabled_reason: Optional[str] = None,
) -> AgentChatAction:
    effects = client_effects or {}
    inferred_risk = risk_level or _infer_action_risk(effects)
    return AgentChatAction(
        id=action_id,
        label=label,
        description=description,
        variant=variant,
        run_label=run_label,
        risk_level=inferred_risk,
        requires_approval=(
            _requires_action_approval(effects)
            if requires_approval is None
            else requires_approval
        ),
        disabled_reason=disabled_reason,
        client_effects=effects,
    )


def _build_agent_command_block(
    command_id: str,
    title: str,
    description: str,
    client_effects: Dict[str, Any],
    *,
    run_label: str = "Run in app",
) -> AgentCommandBlock:
    risk = _infer_action_risk(client_effects)
    return AgentCommandBlock(
        id=command_id,
        title=title,
        description=description,
        command=_client_effects_to_command(client_effects),
        run_label=run_label,
        risk_level=risk,
        requires_approval=_requires_action_approval(client_effects),
        client_effects=client_effects,
    )


def _workflow_stage_to_tab(stage: Optional[str]) -> str:
    return {
        "setup": "files",
        "visualization": "visualization",
        "inference": "inference",
        "proofreading": "mask-proofreading",
        "retraining_staged": "training",
        "evaluation": "inference",
    }.get(stage or "", "files")


def _build_start_inference_effects(workflow: WorkflowSession) -> Dict[str, Any]:
    effects: Dict[str, Any] = {
        "navigate_to": "inference",
        "runtime_action": {"kind": "start_inference"},
    }
    if workflow.image_path or workflow.dataset_path:
        effects["set_inference_image_path"] = workflow.image_path or workflow.dataset_path
    if workflow.label_path or workflow.mask_path:
        effects["set_inference_label_path"] = workflow.label_path or workflow.mask_path
    config_preset = _choose_training_config_preset(workflow)
    if config_preset:
        effects["set_inference_config_preset"] = config_preset
    if workflow.inference_output_path:
        effects["set_inference_output_path"] = workflow.inference_output_path
    if workflow.checkpoint_path:
        effects["set_inference_checkpoint_path"] = workflow.checkpoint_path
    return effects


def _default_mount_project_path() -> str:
    return os.getenv(
        "PYTC_INITIAL_PROJECT_ROOT",
        "/home/weidf/demo_data/mitoem2_progress_demo",
    )


def _build_mount_project_effects(
    *,
    directory_path: Optional[str] = None,
    mount_name: Optional[str] = None,
) -> Dict[str, Any]:
    project_path = directory_path or _default_mount_project_path()
    project_name = mount_name or os.path.basename(project_path.rstrip(os.sep))
    return {
        "navigate_to": "files",
        "mount_project": {
            "directory_path": project_path,
            "mount_name": project_name or "Mounted project",
            "destination_path": "root",
            "workflow_patch": {
                "title": project_name or "Mounted project",
                "dataset_path": project_path,
                "stage": "setup",
                "metadata": {
                    "project_context": {
                        "project_directory": project_path,
                        "task_goal": "segmentation",
                    }
                },
            },
        },
        "refresh_insights": True,
    }


def _build_reset_workspace_effects() -> Dict[str, Any]:
    return {
        "navigate_to": "files",
        "reset_workspace": True,
        "refresh_insights": True,
    }


def _build_choose_data_effects() -> Dict[str, Any]:
    return {
        "navigate_to": "files",
        "runtime_action": {"kind": "choose_project_data"},
        "refresh_insights": True,
    }


def _split_path_parent(path: Optional[str]) -> str:
    if not path:
        return ""
    normalized = str(path).replace("\\", "/").rstrip("/")
    if not normalized:
        return ""
    if "/" not in normalized:
        return ""
    return normalized.rsplit("/", 1)[0]


def _derive_workflow_root_path(workflow: WorkflowSession) -> str:
    candidates = [
        workflow.dataset_path,
        workflow.image_path,
        workflow.label_path,
        workflow.mask_path,
        workflow.corrected_mask_path,
        workflow.training_output_path,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        normalized = str(candidate).replace("\\", "/")
        if "/data/" in normalized:
            return normalized.split("/data/", 1)[0]
        parent = _split_path_parent(normalized)
        if parent:
            return parent
    return ""


def _derive_mount_project_path(workflow: WorkflowSession) -> str:
    dataset_path = str(workflow.dataset_path or "").replace("\\", "/").rstrip("/")
    if dataset_path and not pathlib.PurePosixPath(dataset_path).suffix:
        return dataset_path
    return _derive_workflow_root_path(workflow) or dataset_path


def _derive_training_output_path(workflow: WorkflowSession) -> str:
    if workflow.training_output_path:
        return workflow.training_output_path
    root = _derive_workflow_root_path(workflow)
    if root:
        return f"{root.rstrip('/')}/outputs/training"
    return ""


def _choose_training_config_preset(workflow: WorkflowSession) -> str:
    if workflow.config_path:
        return workflow.config_path
    project_context = _workflow_project_context(workflow)
    haystack = " ".join(
        str(value or "")
        for value in [
            workflow.title,
            workflow.dataset_path,
            workflow.image_path,
            workflow.label_path,
            workflow.mask_path,
            workflow.corrected_mask_path,
            project_context.get("imaging_modality"),
            project_context.get("target_structure"),
            project_context.get("optimization_priority"),
        ]
    ).lower()
    if "mito" in haystack:
        return "configs/MitoEM/Mito-CaseStudy-BC.yaml"
    if "snemi" in haystack:
        return "configs/SNEMI/SNEMI-Affinity-UNet.yaml"
    if "cremi" in haystack:
        return "configs/CREMI/CREMI-Foreground-UNet.yaml"
    return "configs/Lucchi-Mitochondria-CaseStudy.yaml"


def _build_start_training_effects(
    workflow: WorkflowSession,
    corrected_mask_path: Optional[str],
    *,
    volume_subset_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    output_path = (
        str(volume_subset_plan.get("output_path") or "")
        if isinstance(volume_subset_plan, dict)
        else ""
    ) or _derive_training_output_path(workflow)
    image_path = (
        str(volume_subset_plan.get("image_path") or "")
        if isinstance(volume_subset_plan, dict)
        else ""
    ) or workflow.image_path or workflow.dataset_path or ""
    label_path = (
        str(volume_subset_plan.get("label_path") or "")
        if isinstance(volume_subset_plan, dict)
        else ""
    ) or corrected_mask_path or ""
    runtime_action: Dict[str, Any] = {
        "kind": "start_training",
        "autopick_parameters": True,
        "parameter_mode": "agent_default",
    }
    if isinstance(volume_subset_plan, dict):
        runtime_action["volume_subset"] = {
            key: volume_subset_plan.get(key)
            for key in [
                "selection_basis",
                "training_statuses",
                "train_volume_count",
                "target_volume_count",
                "review_volume_count",
                "manifest_path",
            ]
            if volume_subset_plan.get(key) is not None
        }
    effects: Dict[str, Any] = {
        "navigate_to": "training",
        "runtime_action": runtime_action,
        "set_training_config_preset": _choose_training_config_preset(workflow),
    }
    if image_path:
        effects["set_training_image_path"] = image_path
    if label_path:
        effects["set_training_label_path"] = label_path
    if output_path:
        effects["set_training_output_path"] = output_path
        effects["set_training_log_path"] = output_path
    if isinstance(volume_subset_plan, dict):
        effects["training_volume_subset"] = {
            key: volume_subset_plan.get(key)
            for key in [
                "run_slug",
                "selection_basis",
                "training_statuses",
                "train_volume_count",
                "target_volume_count",
                "review_volume_count",
                "manifest_path",
                "train_pairs",
                "target_images",
                "review_pairs",
            ]
            if volume_subset_plan.get(key) is not None
        }
        effects["refresh_project_progress"] = True
    return effects


def _training_run_effects_from_proposal(
    workflow: WorkflowSession,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    client_effects = params.get("client_effects")
    if isinstance(client_effects, dict) and (
        client_effects.get("runtime_action") or {}
    ).get("kind") == "start_training":
        return client_effects

    corrected_mask_path = (
        params.get("label_path")
        or params.get("corrected_mask_path")
        or workflow.corrected_mask_path
        or workflow.label_path
        or workflow.mask_path
    )
    effects = _build_start_training_effects(workflow, corrected_mask_path)
    if params.get("config_preset"):
        effects["set_training_config_preset"] = params["config_preset"]
    if params.get("image_path"):
        effects["set_training_image_path"] = params["image_path"]
    if params.get("output_path"):
        effects["set_training_output_path"] = params["output_path"]
        effects["set_training_log_path"] = params["output_path"]
    return effects


def _build_start_proofreading_effects(workflow: WorkflowSession) -> Dict[str, Any]:
    dataset_path = (
        workflow.image_path
        or workflow.dataset_path
        or workflow.inference_output_path
        or ""
    )
    mask_path = (
        workflow.mask_path
        or workflow.inference_output_path
        or workflow.corrected_mask_path
        or workflow.label_path
        or ""
    )
    effects: Dict[str, Any] = {
        "navigate_to": "mask-proofreading",
        "runtime_action": {"kind": "start_proofreading"},
        "refresh_insights": True,
    }
    if dataset_path:
        effects["set_proofreading_dataset_path"] = dataset_path
    if mask_path:
        effects["set_proofreading_mask_path"] = mask_path
    if workflow.title:
        effects["set_proofreading_project_name"] = workflow.title
    return effects


def _workflow_source_volume_path(workflow: WorkflowSession) -> str:
    return (
        workflow.image_path
        or workflow.dataset_path
        or workflow.inference_output_path
        or ""
    )


def _workflow_mask_like_path(workflow: WorkflowSession) -> str:
    return (
        workflow.mask_path
        or workflow.inference_output_path
        or workflow.corrected_mask_path
        or workflow.label_path
        or ""
    )


def _proofreading_input_blockers(workflow: WorkflowSession) -> List[str]:
    blockers = []
    if not _workflow_source_volume_path(workflow):
        blockers.append("image volume")
    if not _workflow_mask_like_path(workflow):
        blockers.append("mask, label, or prediction")
    return blockers


def _inference_input_blockers(workflow: WorkflowSession) -> List[str]:
    blockers = []
    if not (workflow.image_path or workflow.dataset_path):
        blockers.append("image volume")
    if not workflow.checkpoint_path:
        blockers.append("model checkpoint")
    return blockers


def _build_view_data_effects(
    workflow: WorkflowSession,
    *,
    image_path: Optional[str] = None,
    label_path: Optional[str] = None,
) -> Dict[str, Any]:
    image_path = image_path or workflow.image_path or workflow.dataset_path or ""
    label_path = label_path or (
        workflow.label_path
        or workflow.mask_path
        or workflow.inference_output_path
        or workflow.corrected_mask_path
        or ""
    )
    effects: Dict[str, Any] = {
        "navigate_to": "visualization",
        "runtime_action": {"kind": "load_visualization"},
    }
    if image_path:
        effects["set_visualization_image_path"] = image_path
    if label_path:
        effects["set_visualization_label_path"] = label_path
    return effects


def _build_proofreading_action(
    workflow: WorkflowSession,
    *,
    label: str = "Proofread this data",
    variant: str = "primary",
) -> AgentChatAction:
    return _build_agent_chat_action(
        "start-proofreading",
        label,
        "Open the image and mask in the proofreading workbench.",
        variant=variant,
        client_effects=_build_start_proofreading_effects(workflow),
    )


def _build_default_agent_actions(
    workflow: WorkflowSession,
    corrected_mask_path: Optional[str],
) -> List[AgentChatAction]:
    proofreading_blockers = _proofreading_input_blockers(workflow)
    can_start_proofreading = not proofreading_blockers

    if workflow.stage == "setup":
        if can_start_proofreading:
            return [
                _build_proofreading_action(workflow, variant="primary"),
                _build_agent_chat_action(
                    "open-visualization",
                    "View data",
                    "Open the current image and mask in the viewer.",
                    client_effects=_build_view_data_effects(workflow),
                ),
                _build_agent_chat_action(
                    "open-inference",
                    "Run Model",
                    "Open model inference setup.",
                    client_effects={"navigate_to": "inference"},
                ),
            ]
        return [
            _build_agent_chat_action(
                "open-files",
                "Choose data",
                "Pick the image and mask for this segmentation loop.",
                variant="primary",
                client_effects=_build_choose_data_effects(),
            ),
            _build_agent_chat_action(
                "open-visualization",
                "View data",
                "Open the image viewer after data is mounted.",
                client_effects=_build_view_data_effects(workflow),
            ),
            _build_agent_chat_action(
                "open-inference",
                "Run Model",
                "Open model inference setup.",
                client_effects={"navigate_to": "inference"},
            ),
        ]

    if workflow.stage == "visualization":
        if not can_start_proofreading:
            return [
            _build_agent_chat_action(
                "open-files",
                "Choose data",
                f"Proofreading needs {', '.join(proofreading_blockers)}.",
                variant="primary",
                client_effects=_build_choose_data_effects(),
            ),
                _build_agent_chat_action(
                    "open-inference",
                    "Run Model",
                    "Make a prediction for the current data.",
                    client_effects={"navigate_to": "inference"},
                ),
            ]
        return [
            _build_proofreading_action(workflow, variant="primary"),
            _build_agent_chat_action(
                "open-inference",
                "Run Model",
                "Make a prediction for the current data.",
                client_effects={"navigate_to": "inference"},
            )
        ]

    if workflow.stage == "inference":
        if not workflow.inference_output_path:
            return [
                _build_agent_chat_action(
                    "start-inference",
                    "Run Model",
                    "Start the model run with the current settings.",
                    variant="primary",
                    client_effects=_build_start_inference_effects(workflow),
                ),
                _build_agent_chat_action(
                    "open-inference",
                    "Check settings",
                    "Review the checkpoint and output path before running.",
                    client_effects={"navigate_to": "inference"},
                ),
            ]
        return [
            _build_proofreading_action(
                workflow,
                label="Proofread this result",
                variant="primary",
            ),
            _build_agent_chat_action(
                "refresh-insights",
                "Refresh",
                "Update the next-step recommendation.",
                client_effects={"refresh_insights": True},
            ),
        ]

    if workflow.stage == "proofreading":
        actions = [
            _build_proofreading_action(
                workflow,
                variant=(
                    "primary" if not workflow.proofreading_session_id else "default"
                ),
            ),
            _build_agent_chat_action(
                "refresh-insights",
                "Refresh",
                "Update the recommendation using the latest edits.",
                client_effects={"refresh_insights": True},
            ),
        ]
        if corrected_mask_path:
            actions.insert(
                1,
                _build_agent_chat_action(
                    "propose-retraining-handoff",
                    "Use edits for training",
                    "Ask for approval before linking the saved edits to training.",
                    variant="primary",
                    client_effects={
                        "workflow_action": {
                            "kind": "propose_retraining_stage",
                            "corrected_mask_path": corrected_mask_path,
                        },
                        "refresh_insights": True,
                    },
                ),
            )
            actions.insert(
                2,
                _build_agent_chat_action(
                    "prime-training",
                    "Set up training",
                    "Open training with the saved edits already selected.",
                    client_effects={
                        "navigate_to": "training",
                        "set_training_label_path": corrected_mask_path,
                    },
                ),
            )
        return actions

    if workflow.stage == "retraining_staged":
        training_effects = _build_start_training_effects(workflow, corrected_mask_path)
        return [
            _build_agent_chat_action(
                "start-training",
                "Train on edits",
                "Start training with the saved mask edits.",
                variant="primary",
                run_label="Review run",
                client_effects=training_effects,
            ),
            _build_agent_chat_action(
                "refresh-insights",
                "Refresh",
                "Update the recommendation before training.",
                client_effects={"refresh_insights": True},
            ),
        ]

    if workflow.stage == "evaluation":
        inference_effects = (
            _build_start_inference_effects(workflow)
            if workflow.checkpoint_path
            else {"navigate_to": "inference"}
        )
        inference_label = "Run model" if workflow.checkpoint_path else "Check inference"
        inference_description = (
            "Run the model with the latest checkpoint."
            if workflow.checkpoint_path
            else "Open inference and review the latest checkpoint."
        )
        return [
            _build_agent_chat_action(
                "open-inference-ready-model",
                inference_label,
                inference_description,
                variant="primary",
                client_effects=inference_effects,
            ),
            _build_agent_chat_action(
                "open-monitoring",
                "View training log",
                "Open the training monitor.",
                client_effects={"navigate_to": "monitoring"},
            ),
        ]

    return [
        _build_agent_chat_action(
            "open-workflow-stage",
            "Go to next step",
            "Open the active workflow screen.",
            variant="primary",
            client_effects={"navigate_to": _workflow_stage_to_tab(workflow.stage)},
        )
    ]


def _query_has(lower_query: str, terms: List[str]) -> bool:
    for term in terms:
        normalized = term.strip().lower()
        if not normalized:
            continue
        if re.search(r"[^\w]", normalized):
            if normalized in lower_query:
                return True
            continue
        if re.search(
            rf"(?<![a-z0-9_]){re.escape(normalized)}(?![a-z0-9_])",
            lower_query,
        ):
            return True
    return False


def _casual_query_variant(lower_query: str) -> str:
    squashed = re.sub(r"([a-z])\1{2,}", r"\1\1", lower_query)
    return squashed.replace("datta", "data")


def _query_has_relaxed(lower_query: str, terms: List[str]) -> bool:
    return _query_has(lower_query, terms) or _query_has(
        _casual_query_variant(lower_query),
        terms,
    )


def _query_wants_inference_launch(lower_query: str) -> bool:
    normalized = _casual_query_variant(lower_query)
    if _query_has_relaxed(
        lower_query,
        [
            "start inference",
            "run inference",
            "launch inference",
            "infer",
            "run model",
            "run the model",
            "start model",
            "launch model",
            "predict",
            "prediction",
            "make a prediction",
            "make predictions",
            "generate predictions",
        ],
    ):
        return True
    return bool(
        re.search(
            r"\b(make|create|generate|predict|produce)\b.{0,32}\b(mask|masks|label|labels|prediction|predictions)\b",
            normalized,
        )
    )


def _query_wants_segmentation_launch(lower_query: str) -> bool:
    normalized = _casual_query_variant(lower_query)
    if _query_has_relaxed(
        lower_query,
        [
            "run segmentation",
            "start segmentation",
            "launch segmentation",
            "segment this",
            "segment my",
            "segment volume",
            "segment the volume",
            "get my volume segmented",
            "process volume",
            "run this volume",
            "predict masks",
            "make a prediction",
            "make predictions",
            "segment data",
            "segment some data",
            "segment the data",
            "segment my data",
            "segment images",
            "segment volume",
            "make masks",
            "create masks",
            "generate masks",
            "find mitochondria",
            "detect mitochondria",
            "label mitochondria",
        ],
    ):
        return True
    if re.search(r"\bseg+(?:ment(?:ation|ed|ing|s)?|mentation|s?)\b", normalized):
        return True
    return bool(
        re.search(
            r"\b(segment|find|detect|label)\b.{0,40}\b(data|volume|image|images|mitochondria|mito|mask|masks)\b",
            normalized,
        )
    )


def _query_wants_visualization_launch(lower_query: str) -> bool:
    normalized = _casual_query_variant(lower_query)
    if _query_has_relaxed(
        lower_query,
        [
            "visualize",
            "visualise",
            "vis data",
            "vis volume",
            "vis volumes",
            "vis labels",
            "vis masks",
            "viz data",
            "viz volume",
            "viz volumes",
            "viz labels",
            "viz masks",
            "visualization",
            "view data",
            "view volume",
            "view volumes",
            "view labels",
            "view masks",
            "view segmentations",
            "look at labels",
            "look at my labels",
            "look at masks",
            "look at my masks",
            "look at segmentations",
            "show data",
            "show volume",
            "show labels",
            "show masks",
            "show segs",
            "show segmentations",
            "inspect data",
            "inspect volume",
            "inspect labels",
            "inspect masks",
            "look at data",
            "look at volume",
            "look at labels",
            "look at masks",
            "look at segs",
            "open viewer",
        ],
    ):
        return True
    return bool(
        re.search(
            r"\b(show|see|view|vis|viz|visuali[sz]e|look at|inspect|open)\b.{0,36}\b(data|volume|volumes|image|images|label|labels|mask|masks|seg|segs|segmentation|segmentations)\b",
            normalized,
        )
    )


def _is_greeting_query(lower_query: str) -> bool:
    stripped = lower_query.strip(" \t\n\r.!?,")
    return stripped in {"hi", "hello", "hey", "yo", "sup", "hiya"}


WORKFLOW_AGENT_COMMAND_ALIASES = {
    "/status": "status",
    "/next": "next step",
    "/help": "what can the agent do",
    "/infer": "run model",
    "/inference": "run model",
    "/segment": "run model to segment this volume",
    "/proofread": "proofread this data",
    "/train": "start training",
    "/compare": "compare results and compute metrics",
    "/metrics": "compare results and compute metrics",
    "/export": "export evidence bundle",
}


def _normalize_workflow_agent_query(query: str) -> tuple[str, Optional[str]]:
    stripped = query.strip()
    if not stripped.startswith("/"):
        return stripped, None
    command, _, tail = stripped.partition(" ")
    alias = WORKFLOW_AGENT_COMMAND_ALIASES.get(command.lower())
    if not alias:
        return stripped, None
    normalized = f"{alias}: {tail.strip()}" if tail.strip() else alias
    return normalized, command.lower()


def _is_incomplete_work_intent(lower_query: str) -> bool:
    stripped = lower_query.strip().lower().rstrip(". ")
    return stripped in {
        "i want",
        "i wanna",
        "i would like",
        "i need",
        "help",
        "help me",
        "what should i",
    }


def _is_repair_query(lower_query: str) -> bool:
    stripped = lower_query.strip().lower().rstrip(".!? ")
    return stripped in {
        "bruh",
        "bro",
        "dude",
        "what",
        "what?",
        "huh",
        "no",
        "nah",
        "that makes no sense",
        "this makes no sense",
        "doesn't make sense",
        "does not make sense",
        "zero sense",
    }


def _build_navigation_action(
    tab_key: str, label: str, description: str
) -> AgentChatAction:
    return _build_agent_chat_action(
        f"open-{tab_key}",
        label,
        description,
        variant="primary",
        client_effects={"navigate_to": tab_key},
    )


def _target_tab_from_query(lower_query: str) -> Optional[Dict[str, str]]:
    targets = [
        (
            ["project progress", "progress tracker", "project tracker", "volume tracker", "progress"],
            {
                "tab": "project-progress",
                "label": "Open Progress",
                "description": "Open the volume-level project progress tracker.",
            },
        ),
        (
            [
                "files",
                "file management",
                "mount",
                "load data",
                "choose data",
                "project",
            ],
            {
                "tab": "files",
                "label": "Open Files",
                "description": "Open project files and mounted datasets.",
            },
        ),
        (
            ["visualize", "visualization", "viewer", "view data"],
            {
                "tab": "visualization",
                "label": "Open Visualize",
                "description": "Open the image/label viewer.",
            },
        ),
        (
            [
                "infer",
                "inference",
                "prediction",
                "predict",
                "run model",
                "segment",
                "segmentation",
            ],
            {
                "tab": "inference",
                "label": "Open Run Model",
                "description": "Open model inference setup.",
            },
        ),
        (
            ["train", "training", "retrain"],
            {
                "tab": "training",
                "label": "Open Train Model",
                "description": "Open model training setup.",
            },
        ),
        (
            ["monitor", "tensorboard", "log"],
            {
                "tab": "monitoring",
                "label": "Open Monitor",
                "description": "Open runtime and training monitoring.",
            },
        ),
        (
            ["proofread", "proofreading", "fix mask", "review mask"],
            {
                "tab": "mask-proofreading",
                "label": "Open Proofread",
                "description": "Open the mask proofreading workbench.",
            },
        ),
    ]
    navigation_words = ["go to", "open", "show", "take me", "move me", "switch"]
    if not _query_has(lower_query, navigation_words):
        return None
    for terms, target in targets:
        if _query_has(lower_query, terms):
            return target
    return None


SEMANTIC_WORKFLOW_INTENTS = {
    "greeting",
    "status",
    "capabilities",
    "project_context",
    "project_context_update",
    "needed_from_user",
    "navigate",
    "export_evidence",
    "compute_evaluation",
    "view_data",
    "set_visualization_scales",
    "start_training",
    "start_inference",
    "start_segmentation",
    "start_proofreading",
    "stage_retraining",
    "inspect_failure",
    "mount_project",
    "reset_workspace",
    "validate_project",
    "prepare_data",
    "configure_training",
    "configure_inference",
    "monitor_jobs",
    "stop_runtime",
    "repair",
    "clarify_next_job",
}


def _semantic_intent_enabled() -> bool:
    if os.getenv("PYTC_WORKFLOW_SEMANTIC_ROUTER", "1").strip().lower() in {
        "0",
        "false",
        "off",
        "no",
    }:
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def _semantic_workflow_state(workflow: WorkflowSession) -> Dict[str, Any]:
    project_context = _workflow_project_context(workflow)
    metadata = decode_json(workflow.metadata_json)
    project_observation = (
        metadata.get("project_observation") if isinstance(metadata, dict) else {}
    )
    if not isinstance(project_observation, dict):
        project_observation = {}
    return {
        "stage": workflow.stage,
        "title": workflow.title,
        "has_image": bool(workflow.image_path or workflow.dataset_path),
        "has_label_or_mask": bool(workflow.label_path or workflow.mask_path),
        "has_checkpoint": bool(workflow.checkpoint_path),
        "has_prediction": bool(workflow.inference_output_path),
        "has_corrected_mask": bool(workflow.corrected_mask_path),
        "project_context": {
            "imaging_modality": project_context.get("imaging_modality"),
            "target_structure": project_context.get("target_structure"),
            "optimization_priority": project_context.get("optimization_priority"),
            "voxel_size_nm": project_context.get("voxel_size_nm"),
        },
        "project_observation": {
            "root_count": len(project_observation.get("roots") or []),
            "volume_set_count": len(project_observation.get("volume_sets") or []),
            "volume_sets": [
                {
                    "name": item.get("name"),
                    "image_root": item.get("image_root"),
                    "label_root": item.get("label_root"),
                    "pair_count": item.get("pair_count"),
                    "is_current": item.get("is_current"),
                }
                for item in (project_observation.get("volume_sets") or [])[:6]
                if isinstance(item, dict)
            ],
        },
    }


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def _semantic_intent_payload(query: str, workflow: WorkflowSession) -> Dict[str, Any]:
    if not _semantic_intent_enabled():
        return {}

    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv(
        "PYTC_WORKFLOW_INTENT_MODEL",
        os.getenv("OLLAMA_MODEL", "qwen3.6:27b"),
    )
    timeout = float(os.getenv("PYTC_WORKFLOW_INTENT_TIMEOUT", "8"))
    workflow_state = _semantic_workflow_state(workflow)
    prompt = f"""
Classify a PyTC Client workflow chat message by meaning. Return ONLY JSON.

Valid intents:
greeting, status, capabilities, style_feedback, project_context, project_context_update,
project_files, project_progress, needed_from_user, navigate, export_evidence, compute_evaluation, view_data,
set_visualization_scales, start_training, start_inference, start_segmentation,
start_proofreading, stage_retraining, inspect_failure, mount_project,
reset_workspace, validate_project, prepare_data, configure_training,
configure_inference, monitor_jobs, stop_runtime, repair, clarify_next_job.

Rules:
- Interpret casual language semantically, not by exact wording.
- "segment my data", "make mitochondria masks", "find cells", "label this volume"
  mean start_segmentation.
- "show/view/look at/see my labels/masks/segs/data" means view_data.
- "fix/clean/check/proofread/review labels or masks" means start_proofreading.
- "train/learn from labels/fit a model/use labels or edits" means start_training.
- "train from ground truth", "use the fully good volumes", or
  "train on good masks to segment the rest" means start_training, not project_progress.
- If training and "segment the rest/remaining/no segmentation" appear together, choose
  start_training and leave the segmentation targets in the reason.
- "run model/infer/predict outputs" means start_inference.
- "did it improve/compare/check metrics/report score" means compute_evaluation.
- "package/export/report/evidence bundle" means export_evidence.
- "mount/remount/open project/lucchi/prepilot/suggested project" means mount_project.
- "what files/folders are here" or "list this directory" means project_files.
- "project progress", "progress tracker", "how many volumes are done", "ground truth vs unproofread vs missing segmentation" means project_progress.
- "reset/clear cached state/workspace/cache/context" means reset_workspace.
- "validate/check folder/inspect project structure" means validate_project.
- "prepare/convert/crop/split/normalize/downsample data" means prepare_data.
- "configure training/training settings/augmentation/batch size" means configure_training.
- "configure inference/inference settings/tiling/threshold" means configure_inference.
- "logs/tensorboard/gpu/job status/monitor" means monitor_jobs.
- "stop/cancel/kill the run/job/training/inference" means stop_runtime.
- "too robotic", "less robotic", "sound more human", or feedback about chat tone
  means style_feedback.
- "go/open/switch to a screen" means navigate and set tab.
- "what next/where are we/status/what is missing" means status.
- If the user is only providing domain/context like "EM mitochondria accuracy",
  use project_context_update and fill context.
- Words like "quick" in "look at labels real quick" do NOT mean speed priority.
- If the message is gibberish or truly unrelated, use clarify_next_job.

Tabs for navigate: files, visualization, inference, training, monitoring, project-progress, mask-proofreading.
Context fields can be null: imaging_modality, target_structure, optimization_priority, voxel_size_nm, use_defaults.
Voxel size is z,y,x nanometers, for example [40,4,4].

Workflow state:
{json.dumps(workflow_state, sort_keys=True)}

User message:
{query[:1000]!r}

JSON schema:
{{"intent":"...", "confidence":0.0, "tab":null, "context":{{"imaging_modality":null,"target_structure":null,"optimization_priority":null,"voxel_size_nm":null,"use_defaults":null}}, "reason":"short"}}
""".strip()
    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "format": "json",
                "options": {"temperature": 0, "num_predict": 180},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        response_payload = response.json()
        parsed = _extract_json_object(str(response_payload.get("response") or ""))
    except Exception as exc:
        append_app_event(
            component="workflow_agent",
            event="semantic_intent_failed",
            level="WARNING",
            message=str(exc),
            workflow_id=workflow.id,
            model=model,
            query_preview=query[:160],
        )
        return {}

    intent = str(parsed.get("intent") or "").strip().lower()
    if intent not in SEMANTIC_WORKFLOW_INTENTS:
        return {}
    try:
        confidence = float(parsed.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < float(os.getenv("PYTC_WORKFLOW_INTENT_MIN_CONFIDENCE", "0.45")):
        return {}
    context = parsed.get("context")
    if not isinstance(context, dict):
        context = {}
    return {
        "intent": intent,
        "confidence": confidence,
        "tab": parsed.get("tab"),
        "context": {
            key: value
            for key, value in context.items()
            if key
            in {
                "imaging_modality",
                "target_structure",
                "optimization_priority",
                "voxel_size_nm",
                "use_defaults",
            }
            and value is not None
            and value != ""
            and value != "null"
        },
        "reason": str(parsed.get("reason") or "")[:240],
    }


def _target_tab_from_semantic(
    semantic_intent: Optional[str],
    semantic_tab: Any,
) -> Optional[Dict[str, str]]:
    if semantic_intent != "navigate":
        return None
    tab = str(semantic_tab or "").strip().lower()
    tab_specs = {
        "files": ("Open Files", "Open project files and mounted datasets."),
        "visualization": ("Open Visualize", "Open the image/label viewer."),
        "inference": ("Open Run Model", "Open model inference setup."),
        "training": ("Open Train Model", "Open model training setup."),
        "monitoring": ("Open Monitor", "Open runtime and training monitoring."),
        "project-progress": ("Open Progress", "Open the volume-level project progress tracker."),
        "progress": ("Open Progress", "Open the volume-level project progress tracker."),
        "mask-proofreading": ("Open Proofread", "Open the mask proofreading workbench."),
        "proofreading": ("Open Proofread", "Open the mask proofreading workbench."),
    }
    if tab not in tab_specs:
        return None
    normalized_tab = (
        "mask-proofreading"
        if tab == "proofreading"
        else "project-progress"
        if tab == "progress"
        else tab
    )
    label, description = tab_specs[tab]
    return {"tab": normalized_tab, "label": label, "description": description}


def _latest_completed_inference_runs(
    db: Session, workflow_id: int
) -> List[WorkflowModelRun]:
    return (
        db.query(WorkflowModelRun)
        .filter(
            WorkflowModelRun.workflow_id == workflow_id,
            WorkflowModelRun.run_type == "inference",
            WorkflowModelRun.status == "completed",
            WorkflowModelRun.output_path.isnot(None),
        )
        .order_by(WorkflowModelRun.created_at.asc(), WorkflowModelRun.id.asc())
        .all()
    )


def _build_compute_evaluation_effects(
    db: Session, workflow: WorkflowSession
) -> tuple[Dict[str, Any], List[str]]:
    inference_runs = _latest_completed_inference_runs(db, workflow.id)
    baseline_run = inference_runs[0] if inference_runs else None
    candidate_run = inference_runs[-1] if len(inference_runs) > 1 else None
    baseline_path = baseline_run.output_path if baseline_run else None
    candidate_path = (
        candidate_run.output_path
        if candidate_run
        else (
            workflow.inference_output_path
            if workflow.inference_output_path != baseline_path
            else None
        )
    )
    ground_truth_path = workflow.label_path or workflow.mask_path
    missing = []
    if not baseline_path:
        missing.append("previous result")
    if not candidate_path:
        missing.append("new result")
    if not ground_truth_path:
        missing.append("reference mask")

    effect = {
        "show_workflow_context": True,
        "workflow_action": {
            "kind": "compute_evaluation",
            "name": "workflow-before-after-evaluation",
            "baseline_prediction_path": baseline_path,
            "candidate_prediction_path": candidate_path,
            "ground_truth_path": ground_truth_path,
            "baseline_run_id": baseline_run.id if baseline_run else None,
            "candidate_run_id": candidate_run.id if candidate_run else None,
            "metadata": {"source": "workflow_agent"},
        },
        "refresh_insights": True,
    }
    return effect, missing


def _build_export_bundle_effects() -> Dict[str, Any]:
    return {
        "show_workflow_context": True,
        "workflow_action": {"kind": "export_bundle"},
        "refresh_insights": True,
    }


def _format_greeting_response(
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    stage = recommendation.stage.replace("_", " ")
    decision = _strip_sentence_period(recommendation.decision)
    return (
        f"Hey, this workflow is in {stage}. "
        f"The next useful move looks like: {decision}. "
        "Ask me what I see here, or tell me what you want to open or run."
    )


def _readiness_item(
    item_id: str,
    label: str,
    complete: bool,
    detail: str,
    *,
    severity: str = "default",
) -> WorkflowReadinessItem:
    return WorkflowReadinessItem(
        id=item_id,
        label=label,
        complete=complete,
        detail=detail,
        severity=severity,
    )


def _event_count(events: List[WorkflowEvent], event_type: str) -> int:
    return sum(1 for event in events if event.event_type == event_type)


def _build_workflow_readiness(
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
    corrected_mask_path: Optional[str],
) -> List[WorkflowReadinessItem]:
    has_dataset = bool(
        workflow.dataset_path
        or workflow.image_path
        or _event_count(events, "dataset.loaded") > 0
    )
    has_inference = bool(
        workflow.inference_output_path
        or _event_count(events, "inference.completed") > 0
    )
    has_proofreading = bool(
        workflow.proofreading_session_id
        or _event_count(events, "proofreading.session_loaded") > 0
    )
    has_edits = bool(
        _event_count(events, "proofreading.mask_saved") > 0
        or _event_count(events, "proofreading.instance_classified") > 0
    )
    has_corrections = bool(
        corrected_mask_path or _event_count(events, "proofreading.masks_exported") > 0
    )
    has_training = bool(
        workflow.training_output_path
        or workflow.checkpoint_path
        or _event_count(events, "training.completed") > 0
    )
    has_evaluation = bool(_event_count(events, "evaluation.completed") > 0)

    return [
        _readiness_item(
            "dataset",
            "Data mounted",
            has_dataset,
            workflow.dataset_path
            or workflow.image_path
            or "No source volume recorded.",
            severity="warning",
        ),
        _readiness_item(
            "inference",
            "Prediction artifact",
            has_inference,
            workflow.inference_output_path or "Run inference or register a prediction.",
            severity="warning",
        ),
        _readiness_item(
            "proofreading",
            "Proofreading session",
            has_proofreading,
            f"{_event_count(events, 'proofreading.instance_classified')} classifications logged.",
        ),
        _readiness_item(
            "edits",
            "Correction evidence",
            has_edits,
            f"{_event_count(events, 'proofreading.mask_saved')} mask saves logged.",
        ),
        _readiness_item(
            "corrections",
            "Corrected masks exported",
            has_corrections,
            corrected_mask_path or "Export masks before retraining.",
            severity="warning",
        ),
        _readiness_item(
            "training",
            "Candidate model",
            has_training,
            workflow.checkpoint_path
            or workflow.training_output_path
            or "Launch retraining after corrections are staged.",
        ),
        _readiness_item(
            "evaluation",
            "Before/after evidence",
            has_evaluation,
            (
                "Evaluation report recorded."
                if has_evaluation
                else "Run candidate inference and compare metrics."
            ),
        ),
    ]


def _workflow_agent_decision(
    workflow: WorkflowSession,
    readiness: List[WorkflowReadinessItem],
    impact: WorkflowImpactPreviewResponse,
    hotspots: List[WorkflowHotspotItem],
    corrected_mask_path: Optional[str],
) -> Dict[str, Any]:
    incomplete = {item.id for item in readiness if not item.complete}
    top_hotspot = hotspots[0] if hotspots else None
    has_source_volume = bool(workflow.dataset_path or workflow.image_path)
    has_mask_like = bool(
        workflow.mask_path or workflow.label_path or workflow.inference_output_path
    )
    has_checkpoint = bool(workflow.checkpoint_path)

    if "dataset" in incomplete and workflow.stage in {"setup", "visualization"}:
        return {
            "decision": "Choose the image and mask first.",
            "rationale": "I need the data pair before I can route the next step.",
            "next_stage": "setup",
            "confidence": "high",
        }
    if workflow.stage in {"setup", "visualization"}:
        if has_source_volume and has_mask_like:
            return {
                "decision": "Proofread this data.",
                "rationale": "Image and mask-like data are ready for human review.",
                "next_stage": "proofreading",
                "confidence": "medium",
            }
        if has_source_volume and has_checkpoint:
            return {
                "decision": "Run the model on this image.",
                "rationale": "Image and checkpoint are ready; I can infer routine settings.",
                "next_stage": "inference",
                "confidence": "medium",
            }
        if has_source_volume:
            return {
                "decision": "Add a checkpoint or mask/label.",
                "rationale": "The project has an image volume, but no model output or editable mask yet.",
                "next_stage": "setup",
                "confidence": "high",
            }
        return {
            "decision": "Proofread this data if the mask is ready.",
            "rationale": "A human review pass is the fastest way to create useful edits.",
            "next_stage": "proofreading",
            "confidence": "medium",
        }
    if workflow.stage == "inference":
        if "inference" in incomplete:
            return {
                "decision": "Run the model on this data.",
                "rationale": "No prediction is recorded yet.",
                "next_stage": "inference",
                "confidence": "medium",
            }
        return {
            "decision": "Proofread the model result.",
            "rationale": "A prediction exists, so the useful next step is to review and fix it.",
            "next_stage": "proofreading",
            "confidence": "medium",
        }
    if workflow.stage == "proofreading":
        if corrected_mask_path or impact.can_stage_retraining:
            return {
                "decision": "Use your saved edits for training.",
                "rationale": "I can prepare the training step, but you approve it first.",
                "next_stage": "retraining_staged",
                "confidence": impact.confidence,
            }
        if top_hotspot:
            return {
                "decision": "Keep proofreading likely mistakes.",
                "rationale": top_hotspot.summary,
                "next_stage": "proofreading",
                "confidence": impact.confidence,
            }
        return {
            "decision": "Save or export edits before training.",
            "rationale": "Training needs saved mask edits, not just a viewed slice.",
            "next_stage": "proofreading",
            "confidence": "low",
        }
    if workflow.stage == "retraining_staged":
        return {
            "decision": "Train on the saved edits.",
            "rationale": "The edited masks are linked to the training screen.",
            "next_stage": "evaluation",
            "confidence": "medium",
        }
    if workflow.stage == "evaluation":
        return {
            "decision": "Compare the new result.",
            "rationale": "The new checkpoint only matters if its prediction improves.",
            "next_stage": "inference",
            "confidence": "medium" if workflow.checkpoint_path else "low",
        }
    return {
        "decision": "Check what is ready and choose the next step.",
        "rationale": impact.summary,
        "next_stage": workflow.stage,
        "confidence": impact.confidence,
    }


def _build_workflow_agent_recommendation(
    db: Session,
    workflow: WorkflowSession,
) -> WorkflowAgentRecommendationResponse:
    event_rows = _event_rows(db, workflow.id)
    event_responses = _event_list(db, workflow.id)
    corrected_mask_path = workflow.corrected_mask_path or _latest_exported_mask_path(
        db, workflow.id
    )
    hotspots = _compute_hotspots(workflow, event_rows)
    impact = _compute_impact_preview(
        workflow,
        event_rows,
        hotspots,
        corrected_mask_path,
    )
    readiness = _build_workflow_readiness(workflow, event_rows, corrected_mask_path)
    decision = _workflow_agent_decision(
        workflow,
        readiness,
        impact,
        hotspots,
        corrected_mask_path,
    )
    actions = _build_default_agent_actions(workflow, corrected_mask_path)
    primary_action = next(
        (
            action
            for action in actions
            if action.client_effects and action.variant == "primary"
        ),
        next((action for action in actions if action.client_effects), None),
    )
    commands = []
    if primary_action:
        commands.append(
            _build_agent_command_block(
                f"{primary_action.id}-command",
                primary_action.label,
                primary_action.description,
                primary_action.client_effects,
            )
        )

    blockers = [
        item.detail
        for item in readiness
        if not item.complete and item.severity == "warning"
    ]
    if workflow.stage == "proofreading" and corrected_mask_path:
        blockers = []
    if workflow.stage == "retraining_staged":
        blockers = []

    return WorkflowAgentRecommendationResponse(
        workflow_id=workflow.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        stage=workflow.stage,
        decision=decision["decision"],
        rationale=decision["rationale"],
        confidence=decision["confidence"],
        next_stage=decision["next_stage"],
        can_act=bool(actions),
        blockers=blockers[:3],
        readiness=readiness,
        top_hotspot=hotspots[0] if hotspots else None,
        impact_preview=impact,
        actions=actions,
        commands=commands,
    )


def _workflow_path_present(value: Optional[str]) -> bool:
    return bool(value and str(value).strip())


def _latest_artifact_path(
    artifacts: List[WorkflowArtifact],
    *,
    roles: Optional[set[str]] = None,
    artifact_types: Optional[set[str]] = None,
) -> Optional[str]:
    for artifact in sorted(
        artifacts,
        key=lambda row: (row.created_at or datetime.min.replace(tzinfo=timezone.utc), row.id),
        reverse=True,
    ):
        if roles and artifact.role not in roles:
            continue
        if artifact_types and artifact.artifact_type not in artifact_types:
            continue
        if artifact.path:
            return artifact.path
        if artifact.uri:
            return artifact.uri
    return None


def _latest_model_checkpoint(
    model_versions: List[WorkflowModelVersion],
    artifacts: List[WorkflowArtifact],
) -> Optional[str]:
    for version in sorted(
        model_versions,
        key=lambda row: (row.created_at or datetime.min.replace(tzinfo=timezone.utc), row.id),
        reverse=True,
    ):
        if version.checkpoint_path:
            return version.checkpoint_path
    return _latest_artifact_path(
        artifacts,
        roles={"candidate_checkpoint", "checkpoint"},
        artifact_types={"model_checkpoint"},
    )


def _preflight_item(
    item_id: str,
    label: str,
    *,
    can_run: bool,
    missing: Optional[List[str]] = None,
    action: str,
    risk_level: str = "normal",
    status: Optional[str] = None,
) -> WorkflowPreflightItem:
    missing = missing or []
    resolved_status = status or ("ready" if can_run else "needs_input")
    return WorkflowPreflightItem(
        id=item_id,
        label=label,
        status=resolved_status,
        can_run=can_run,
        missing=missing,
        action=action,
        risk_level=risk_level,
    )


def _build_workflow_preflight(
    db: Session,
    workflow: WorkflowSession,
) -> WorkflowPreflightResponse:
    artifacts = (
        db.query(WorkflowArtifact)
        .filter(WorkflowArtifact.workflow_id == workflow.id)
        .order_by(WorkflowArtifact.created_at.asc(), WorkflowArtifact.id.asc())
        .all()
    )
    model_versions = (
        db.query(WorkflowModelVersion)
        .filter(WorkflowModelVersion.workflow_id == workflow.id)
        .order_by(WorkflowModelVersion.created_at.asc(), WorkflowModelVersion.id.asc())
        .all()
    )
    correction_sets = (
        db.query(WorkflowCorrectionSet)
        .filter(WorkflowCorrectionSet.workflow_id == workflow.id)
        .order_by(WorkflowCorrectionSet.created_at.asc(), WorkflowCorrectionSet.id.asc())
        .all()
    )
    evaluation_results = (
        db.query(WorkflowEvaluationResult)
        .filter(WorkflowEvaluationResult.workflow_id == workflow.id)
        .order_by(
            WorkflowEvaluationResult.created_at.asc(), WorkflowEvaluationResult.id.asc()
        )
        .all()
    )

    completed_inference_runs = _latest_completed_inference_runs(db, workflow.id)
    baseline_run = completed_inference_runs[0] if completed_inference_runs else None
    candidate_run = (
        completed_inference_runs[-1] if len(completed_inference_runs) > 1 else None
    )

    image_path = workflow.image_path or workflow.dataset_path
    reference_path = workflow.label_path or workflow.mask_path
    corrected_mask_path = (
        workflow.corrected_mask_path
        or _latest_exported_mask_path(db, workflow.id)
        or (correction_sets[-1].corrected_mask_path if correction_sets else None)
    )
    checkpoint_path = workflow.checkpoint_path or _latest_model_checkpoint(
        model_versions,
        artifacts,
    )
    prediction_path = (
        workflow.inference_output_path
        or (completed_inference_runs[-1].output_path if completed_inference_runs else None)
        or _latest_artifact_path(
            artifacts,
            roles={"prediction"},
            artifact_types={"inference_output"},
        )
    )
    baseline_path = baseline_run.output_path if baseline_run else prediction_path
    candidate_path = (
        candidate_run.output_path
        if candidate_run
        else (
            workflow.inference_output_path
            if workflow.inference_output_path and workflow.inference_output_path != baseline_path
            else None
        )
    )
    ground_truth_path = reference_path or corrected_mask_path

    has_image = _workflow_path_present(image_path)
    has_reference = _workflow_path_present(reference_path)
    has_mask_like = has_reference or _workflow_path_present(prediction_path)
    has_checkpoint = _workflow_path_present(checkpoint_path)
    has_correction = _workflow_path_present(corrected_mask_path)
    has_training_target = has_reference or has_correction
    has_baseline = _workflow_path_present(baseline_path)
    has_candidate = _workflow_path_present(candidate_path)
    has_ground_truth = _workflow_path_present(ground_truth_path)
    has_evaluation = bool(evaluation_results)

    inference_missing = []
    if not has_image:
        inference_missing.append("image volume")
    if not has_checkpoint:
        inference_missing.append("checkpoint")

    proofreading_missing = []
    if not has_image:
        proofreading_missing.append("image volume")
    if not has_mask_like:
        proofreading_missing.append("mask, label, or prediction")

    training_missing = []
    if not has_image:
        training_missing.append("image volume")
    if not has_training_target:
        training_missing.append("label or corrected mask")

    evaluation_missing = []
    if not has_baseline:
        evaluation_missing.append("previous result")
    if not has_candidate:
        evaluation_missing.append("new result")
    if not has_ground_truth:
        evaluation_missing.append("reference mask")

    items = [
        _preflight_item(
            "project_setup",
            "Project data",
            can_run=has_image,
            missing=[] if has_image else ["image volume"],
            action=(
                "Use this project."
                if has_image
                else "Mount a folder or upload an image volume."
            ),
            risk_level="view_only",
        ),
        _preflight_item(
            "visualization",
            "Visualize data",
            can_run=has_image,
            missing=[] if has_image else ["image volume"],
            action="Open the image volume for inspection.",
            risk_level="view_only",
        ),
        _preflight_item(
            "inference",
            "Run model",
            can_run=has_image and has_checkpoint,
            missing=inference_missing,
            action=(
                "Run inference with inferred defaults."
                if has_image and has_checkpoint
                else "Add a checkpoint before running inference."
            ),
            risk_level="runs_job",
        ),
        _preflight_item(
            "proofreading",
            "Proofread masks",
            can_run=has_image and has_mask_like,
            missing=proofreading_missing,
            action=(
                "Open Proofread on the current image/mask pair."
                if has_image and has_mask_like
                else "Add a mask, label, or prediction to proofread."
            ),
            risk_level="writes_record",
        ),
        _preflight_item(
            "training",
            "Use edits for training",
            can_run=has_image and has_training_target,
            missing=training_missing,
            action=(
                "Train with inferred defaults from the current labels/corrections."
                if has_image and has_training_target
                else "Add a label or save corrected masks first."
            ),
            risk_level="runs_job",
        ),
        _preflight_item(
            "evaluation",
            "Compare results",
            can_run=has_baseline and has_candidate and has_ground_truth,
            missing=evaluation_missing,
            action=(
                "Compute before/after metrics."
                if has_baseline and has_candidate and has_ground_truth
                else "Run two model outputs and select a reference mask."
            ),
            risk_level="view_only",
            status="completed" if has_evaluation else None,
        ),
    ]

    if not has_image:
        overall_status = "needs_project"
        summary = "Choose an image volume to start a workable project."
    elif has_evaluation:
        overall_status = "evaluated"
        summary = "Before/after evaluation evidence is recorded."
    elif has_baseline and has_candidate and has_ground_truth:
        overall_status = "ready_to_compare"
        summary = "Ready to compare previous and new segmentation results."
    elif has_correction:
        overall_status = "ready_to_train"
        summary = "Corrected masks are available; training can use them next."
    elif has_image and has_mask_like:
        overall_status = "ready_to_proofread"
        summary = "Image and mask-like data are ready for proofreading."
    elif has_image and has_checkpoint:
        overall_status = "ready_to_infer"
        summary = "Image and checkpoint are ready for inference."
    else:
        overall_status = "image_only"
        summary = "Image volume is loaded; add a checkpoint or mask/label next."

    return WorkflowPreflightResponse(
        workflow_id=workflow.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        overall_status=overall_status,
        summary=summary,
        items=items,
    )


def _format_workflow_agent_response(
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    ready_count = sum(1 for item in recommendation.readiness if item.complete)
    total_count = len(recommendation.readiness)
    decision = _strip_sentence_period(recommendation.decision)
    rationale = _lower_first(_strip_sentence_period(recommendation.rationale))
    lines = [f"I would start here: {decision}."]
    if rationale:
        lines.append(f"That fits because {rationale}.")
    if total_count:
        lines.append(f"{ready_count}/{total_count} workflow checks are ready.")
    if recommendation.blockers:
        lines.append(
            f"The only catch is {_lower_first(_strip_sentence_period(recommendation.blockers[0]))}."
        )
    return " ".join(lines)


def _strip_sentence_period(text: str) -> str:
    return str(text or "").strip().rstrip(".")


def _lower_first(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return text
    return text[:1].lower() + text[1:]


def _humanize_agent_response(response: str) -> str:
    lines = [line.strip() for line in str(response or "").splitlines() if line.strip()]
    if not lines:
        return response

    buckets: Dict[str, List[str]] = {
        "action": [],
        "why": [],
        "current": [],
        "blocker": [],
        "watch": [],
        "ready": [],
        "other": [],
    }
    for line in lines:
        lowered = line.lower()
        if lowered.startswith("do this:"):
            buckets["action"].append(line.split(":", 1)[1].strip())
        elif lowered.startswith("why:"):
            buckets["why"].append(line.split(":", 1)[1].strip())
        elif lowered.startswith("current read:"):
            buckets["current"].append(line.split(":", 1)[1].strip())
        elif lowered.startswith("blocker:") or lowered.startswith("current gap:"):
            buckets["blocker"].append(line.split(":", 1)[1].strip())
        elif lowered.startswith("watch out:"):
            buckets["watch"].append(line.split(":", 1)[1].strip())
        elif lowered.startswith("ready:"):
            buckets["ready"].append(line)
        else:
            buckets["other"].append(line)

    if not any(buckets[key] for key in ("action", "why", "current", "blocker", "watch", "ready")):
        return response

    parts: List[str] = []
    if buckets["current"]:
        current = _lower_first(_strip_sentence_period(buckets["current"][0]))
        parts.append(f"Right now I would treat this as the next step: {current}.")
    if buckets["action"]:
        action = _strip_sentence_period(buckets["action"][0])
        if action.lower().startswith(("open ", "show ", "view ", "run ", "proofread ", "train ", "compute ", "export ", "stop ")):
            parts.append(f"I can {_lower_first(action)}.")
        else:
            parts.append(f"I would start here: {action}.")
    if buckets["why"]:
        parts.append(
            f"That fits because {_lower_first(_strip_sentence_period(buckets['why'][0]))}."
        )
    if buckets["watch"]:
        parts.append(f"One caveat: {_strip_sentence_period(buckets['watch'][0])}.")
    if buckets["blocker"]:
        parts.append(
            f"The thing blocking that is {_lower_first(_strip_sentence_period(buckets['blocker'][0]))}."
        )
    if buckets["ready"]:
        ready = buckets["ready"][0].split(":", 1)[-1].strip()
        parts.append(f"Readiness: {ready}")
    parts.extend(buckets["other"])
    return " ".join(parts)


def _short_path_label(path: Optional[str]) -> str:
    if not path:
        return "not set"
    parts = str(path).rstrip("/").split("/")
    return parts[-1] or str(path)


def _workflow_volume_pair_discovery(workflow: WorkflowSession) -> Dict[str, Any]:
    metadata = decode_json(workflow.metadata_json)
    stored_discovery = (
        metadata.get("volume_pair_discovery") if isinstance(metadata, dict) else None
    )
    image_path = workflow.image_path or workflow.dataset_path
    label_path = (
        workflow.label_path
        or workflow.mask_path
        or workflow.inference_output_path
        or workflow.corrected_mask_path
    )
    if not image_path:
        return {"pair_count": 0, "pairs": []}
    try:
        image = pathlib.Path(str(image_path))
        label = pathlib.Path(str(label_path)) if label_path else None
        if not image.exists() or (label is not None and not label.exists()):
            return (
                stored_discovery
                if isinstance(stored_discovery, dict)
                else {"pair_count": 0, "pairs": []}
            )
        discovery = discover_neuroglancer_volume_pairs(image, label, max_pairs=12)
        if isinstance(discovery, dict) and discovery.get("pair_count"):
            return discovery
        return (
            stored_discovery
            if isinstance(stored_discovery, dict)
            else {"pair_count": 0, "pairs": []}
        )
    except Exception as exc:
        append_app_event(
            component="workflow_agent",
            event="workflow_volume_pair_discovery_failed",
            level="WARNING",
            message=str(exc),
            workflow_id=workflow.id,
            image_path=str(image_path),
            label_path=str(label_path) if label_path else None,
        )
        return (
            stored_discovery
            if isinstance(stored_discovery, dict)
            else {"pair_count": 0, "pairs": []}
        )


def _normalize_absolute_path(value: Optional[str]) -> str:
    if not value:
        return ""
    return os.path.abspath(os.path.expanduser(str(value)))


def _absolute_project_path(root_path: str, path_value: Optional[str]) -> str:
    if not path_value:
        return ""
    text = str(path_value)
    if os.path.isabs(text):
        return _normalize_absolute_path(text)
    return _normalize_absolute_path(os.path.join(root_path, text))


def _path_is_within(path_value: Optional[str], root_value: Optional[str]) -> bool:
    path = _normalize_absolute_path(path_value)
    root = _normalize_absolute_path(root_value)
    if not path or not root:
        return False
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _workflow_path_values(workflow: WorkflowSession) -> List[str]:
    return [
        str(value)
        for value in [
            workflow.dataset_path,
            workflow.image_path,
            workflow.label_path,
            workflow.mask_path,
            workflow.inference_output_path,
            workflow.corrected_mask_path,
            workflow.checkpoint_path,
            workflow.config_path,
        ]
        if value
    ]


def _mounted_project_roots(
    db: Session, user_id: int
) -> List[Dict[str, Any]]:
    rows = (
        db.query(auth_models.File)
        .filter(
            auth_models.File.user_id == user_id,
            auth_models.File.path == "root",
            auth_models.File.is_folder.is_(True),
            auth_models.File.physical_path.isnot(None),
        )
        .order_by(auth_models.File.name.asc())
        .all()
    )
    roots = []
    for row in rows:
        root_path = _normalize_absolute_path(row.physical_path)
        if root_path and os.path.isdir(root_path):
            roots.append(
                {
                    "path": root_path,
                    "name": row.name,
                    "mounted_root_id": row.id,
                    "source": "mounted_root",
                }
            )
    return roots


def _workflow_project_root_candidates(
    db: Session, workflow: WorkflowSession, user_id: int
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen_paths: set[str] = set()

    def add_candidate(path_value: Optional[str], source: str, **extra: Any) -> None:
        root_path = _normalize_absolute_path(path_value)
        if not root_path or root_path in seen_paths or not os.path.isdir(root_path):
            return
        seen_paths.add(root_path)
        candidates.append({"path": root_path, "source": source, **extra})

    if workflow.dataset_path and os.path.isdir(_normalize_absolute_path(workflow.dataset_path)):
        add_candidate(workflow.dataset_path, "workflow_dataset_path")

    derived_root = _derive_mount_project_path(workflow)
    if derived_root and os.path.isdir(_normalize_absolute_path(derived_root)):
        add_candidate(derived_root, "derived_workflow_root")

    mounted_roots = _mounted_project_roots(db, user_id)
    workflow_paths = [_normalize_absolute_path(path) for path in _workflow_path_values(workflow)]
    for root in mounted_roots:
        root_path = root["path"]
        if any(_path_is_within(path, root_path) for path in workflow_paths):
            add_candidate(
                root_path,
                "mounted_root_match",
                name=root.get("name"),
                mounted_root_id=root.get("mounted_root_id"),
            )

    if not candidates and len(mounted_roots) == 1:
        root = mounted_roots[0]
        add_candidate(
            root["path"],
            "single_mounted_root",
            name=root.get("name"),
            mounted_root_id=root.get("mounted_root_id"),
        )

    return candidates[:3]


def _observed_volume_sets_from_profile(
    root_path: str, profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    volume_sets = profile.get("volume_sets") or profile.get("schema", {}).get(
        "volume_sets"
    )
    if not isinstance(volume_sets, list):
        return []

    observed_sets: List[Dict[str, Any]] = []
    for item in volume_sets[:8]:
        if not isinstance(item, dict):
            continue
        examples = []
        for example in item.get("examples") or []:
            if not isinstance(example, dict):
                continue
            image_path = _absolute_project_path(root_path, example.get("image"))
            label_path = _absolute_project_path(root_path, example.get("label"))
            examples.append(
                {
                    "image": example.get("image"),
                    "label": example.get("label"),
                    "image_path": image_path,
                    "label_path": label_path,
                }
            )
        image_root_path = _absolute_project_path(root_path, item.get("image_root"))
        label_root_path = _absolute_project_path(root_path, item.get("label_root"))
        primary_example = examples[0] if examples else {}
        observed_sets.append(
            {
                "id": item.get("id") or f"set-{len(observed_sets) + 1}",
                "name": item.get("name") or item.get("image_root") or "volume set",
                "project_root": root_path,
                "image_root": item.get("image_root"),
                "label_root": item.get("label_root"),
                "image_root_path": image_root_path,
                "label_root_path": label_root_path,
                "image_path": primary_example.get("image_path") or image_root_path,
                "label_path": primary_example.get("label_path") or label_root_path,
                "image_count": int(item.get("image_count") or 0),
                "label_count": int(item.get("label_count") or 0),
                "pair_count": int(item.get("pair_count") or 0),
                "examples": examples[:3],
            }
        )
    return observed_sets


def _project_top_level_entries(root_path: str, *, max_entries: int = 12) -> List[Dict[str, Any]]:
    try:
        children = sorted(
            pathlib.Path(root_path).iterdir(),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        )
    except OSError:
        return []
    entries = []
    for child in children[:max_entries]:
        entries.append(
            {
                "name": child.name,
                "kind": "folder" if child.is_dir() else "file",
            }
        )
    return entries


def _is_current_observed_volume_set(
    workflow: WorkflowSession, volume_set: Dict[str, Any]
) -> bool:
    image_path = workflow.image_path or workflow.dataset_path
    label_path = workflow.label_path or workflow.mask_path
    if image_path:
        return (
            _path_is_within(image_path, volume_set.get("image_root_path"))
            or _normalize_absolute_path(image_path)
            == _normalize_absolute_path(volume_set.get("image_path"))
        )
    if label_path and volume_set.get("label_root_path"):
        return _path_is_within(label_path, volume_set.get("label_root_path"))
    return False


def _observe_workflow_project(
    db: Session, workflow: WorkflowSession, user_id: int
) -> Dict[str, Any]:
    roots = _workflow_project_root_candidates(db, workflow, user_id)
    observed_roots: List[Dict[str, Any]] = []
    observed_sets: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for root in roots:
        root_path = root["path"]
        try:
            profile = _scan_project_profile(root_path)
        except Exception as exc:
            errors.append({"path": root_path, "error": type(exc).__name__})
            append_app_event(
                component="workflow_agent",
                event="project_observation_scan_failed",
                level="WARNING",
                message=str(exc),
                workflow_id=workflow.id,
                project_root=root_path,
            )
            continue

        root_sets = _observed_volume_sets_from_profile(root_path, profile)
        for volume_set in root_sets:
            volume_set["is_current"] = _is_current_observed_volume_set(
                workflow, volume_set
            )
        observed_sets.extend(root_sets)
        observed_roots.append(
            {
                "path": root_path,
                "name": root.get("name") or pathlib.Path(root_path).name,
                "source": root.get("source"),
                "mounted_root_id": root.get("mounted_root_id"),
                "counts": profile.get("counts") or {},
                "volume_set_count": len(root_sets),
                "top_level_entries": _project_top_level_entries(root_path),
                "context_hints": profile.get("context_hints") or {},
            }
        )

    observation = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "roots": observed_roots,
        "volume_sets": observed_sets,
        "errors": errors,
    }
    metadata = decode_json(workflow.metadata_json)
    metadata["project_observation"] = {
        "observed_at": observation["observed_at"],
        "roots": observed_roots,
        "volume_sets": [
            {
                key: volume_set.get(key)
                for key in [
                    "id",
                    "name",
                    "project_root",
                    "image_root",
                    "label_root",
                    "image_path",
                    "label_path",
                    "image_count",
                    "label_count",
                    "pair_count",
                    "is_current",
                ]
            }
            for volume_set in observed_sets[:8]
        ],
        "errors": errors,
    }
    workflow.metadata_json = encode_json(metadata)
    append_app_event(
        component="workflow_agent",
        event="project_observed",
        level="INFO",
        message="Workflow agent refreshed read-only project observation.",
        workflow_id=workflow.id,
        root_count=len(observed_roots),
        volume_set_count=len(observed_sets),
        roots=[root.get("path") for root in observed_roots],
    )
    return observation


def _query_wants_alternate_volume_set(lower_query: str) -> bool:
    if re.search(
        r"\b(?:another|other|different|alternate|next|second)\b.{0,48}\b(?:set|pair|volume set|image/seg|image and seg)\b",
        lower_query,
    ):
        return True
    return _query_has_relaxed(
        lower_query,
        [
            "another set",
            "another pair",
            "other set",
            "other pair",
            "different set",
            "different pair",
            "alternate set",
            "alternate pair",
            "next set",
            "next pair",
            "second set",
            "second pair",
            "look for another",
            "find another",
        ],
    )


def _select_observed_volume_set(
    observation: Dict[str, Any],
    *,
    prefer_alternate: bool = False,
) -> Optional[Dict[str, Any]]:
    volume_sets = [
        item for item in observation.get("volume_sets") or [] if isinstance(item, dict)
    ]
    if not volume_sets:
        return None
    if prefer_alternate:
        for volume_set in volume_sets:
            if not volume_set.get("is_current"):
                return volume_set
        return None
    for volume_set in volume_sets:
        if volume_set.get("is_current"):
            return volume_set
    return volume_sets[0]


def _query_wants_project_file_overview(lower_query: str) -> bool:
    return bool(
        re.search(r"\bwhat\b.{0,40}\bfiles?\b", lower_query)
        or re.search(r"\bwhat\b.{0,40}\b(?:folder|directory)\b", lower_query)
        or re.search(r"\b(?:list|show|describe|explain)\b.{0,40}\bfiles?\b", lower_query)
        or re.search(r"\b(?:inside|in)\b.{0,24}\b(?:folder|directory)\b", lower_query)
    )


def _format_project_files_response(observation: Dict[str, Any]) -> str:
    roots = observation.get("roots") or []
    volume_sets = observation.get("volume_sets") or []
    if not roots:
        return (
            "I do not see a mounted project folder yet. Mount or choose a project "
            "directory and I can inspect the files from there."
        )

    root = roots[0]
    root_name = root.get("name") or pathlib.Path(str(root.get("path") or "")).name
    entries = root.get("top_level_entries") or []
    entry_names = [
        f"{entry.get('name')}/" if entry.get("kind") == "folder" else str(entry.get("name"))
        for entry in entries[:8]
        if entry.get("name")
    ]
    counts = root.get("counts") or {}

    lines = [f"I checked `{root_name}`. At the top level I see {', '.join(entry_names) or 'no indexed files yet'}."]
    useful_bits = []
    if counts.get("image"):
        useful_bits.append(f"{counts.get('image')} image volume(s)")
    if counts.get("label"):
        useful_bits.append(f"{counts.get('label')} mask/label volume(s)")
    if counts.get("prediction"):
        useful_bits.append(f"{counts.get('prediction')} prediction/output file(s)")
    if counts.get("config"):
        useful_bits.append(f"{counts.get('config')} config file(s)")
    if counts.get("checkpoint"):
        useful_bits.append(f"{counts.get('checkpoint')} checkpoint(s)")
    if useful_bits:
        lines.append("The useful workflow pieces look like " + ", ".join(useful_bits) + ".")

    if volume_sets:
        set_summaries = []
        for item in volume_sets[:3]:
            set_summaries.append(
                f"{item.get('name') or 'volume set'}"
                f" ({item.get('image_count') or 0} images, {item.get('label_count') or 0} labels)"
            )
        lines.append("I also found " + "; ".join(set_summaries) + ".")
    lines.append("Ask me to open one of those sets and I can route it straight into Visualize.")
    return "\n".join(lines)


PROJECT_PROGRESS_STATUS_DEFINITIONS = {
    "ground_truth": "Fully good: has a proofread, corrected, curated, or ground-truth segmentation.",
    "needs_proofreading": "Has a segmentation or mask, but it is not confirmed as proofread ground truth.",
    "missing_segmentation": "Has image data, but no matching segmentation was found.",
    "ignored": "Excluded from the active progress denominator.",
}
PROJECT_PROGRESS_GROUND_TRUTH_MARKERS = {
    "corrected",
    "curated",
    "expert",
    "ground",
    "groundtruth",
    "gt",
    "proofread",
    "proofreaded",
    "truth",
    "verified",
}


def _project_progress_pair_key(path_value: Optional[str]) -> str:
    name = pathlib.Path(str(path_value or "")).name.lower()
    extension = _project_extension(name)
    if extension:
        name = name[: -len(extension)]
    replacements = (
        "ground_truth",
        "groundtruth",
        "proofread",
        "corrected",
        "curated",
        "expert",
        "consensus",
        "image",
        "images",
        "im",
        "img",
        "raw",
        "volume",
        "vol",
        "label",
        "labels",
        "mask",
        "masks",
        "segmentation",
        "seg",
        "mito",
        "gt",
    )
    for token in replacements:
        name = re.sub(rf"(^|[_\-\s]){re.escape(token)}([_\-\s]|$)", "_", name)
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def _project_progress_relpath(path_value: str, root_path: str) -> str:
    try:
        return os.path.relpath(path_value, root_path)
    except ValueError:
        return path_value


def _project_progress_volume_id(image_path: str, root_path: str) -> str:
    return _project_progress_relpath(image_path, root_path).replace(os.sep, "/")


def _project_progress_tokens(path_value: Optional[str]) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", str(path_value or "").lower())
        if token
    }


def _project_progress_has_ground_truth_marker(path_value: Optional[str]) -> bool:
    tokens = _project_progress_tokens(path_value)
    normalized = re.sub(r"[^a-z0-9]+", "_", str(path_value or "").lower())
    return bool(
        tokens & PROJECT_PROGRESS_GROUND_TRUTH_MARKERS
        or "ground_truth" in normalized
        or "groundtruth" in normalized
    )


def _project_progress_volume_candidates(
    path_value: Optional[str],
    *,
    project_root: str,
    roles: set[str],
    max_candidates: int = 500,
) -> List[str]:
    if not path_value:
        return []
    absolute = pathlib.Path(path_value)
    if not absolute.is_absolute():
        absolute = pathlib.Path(project_root) / absolute
    try:
        absolute = absolute.expanduser().resolve()
    except OSError:
        absolute = absolute.expanduser()
    if absolute.is_file() or (
        absolute.is_dir() and _project_extension(absolute.name) in {".zarr", ".n5"}
    ):
        relative = _project_progress_relpath(str(absolute), project_root)
        role = _role_for_project_file(relative)
        return [str(absolute)] if role in roles or role == "volume" else []
    if not absolute.is_dir():
        return []

    def is_candidate(child: pathlib.Path) -> bool:
        if any(part.startswith(".") or part == "__pycache__" for part in child.parts):
            return False
        if not child.is_file() and not (
            child.is_dir() and _project_extension(child.name) in {".zarr", ".n5"}
        ):
            return False
        relative = _project_progress_relpath(str(child), project_root)
        role = _role_for_project_file(relative)
        return role in roles or role == "volume"

    direct = [
        str(child)
        for child in sorted(absolute.iterdir(), key=lambda item: item.name.lower())
        if is_candidate(child)
    ]
    if direct:
        return direct[:max_candidates]

    candidates: List[str] = []
    for child in sorted(absolute.rglob("*"), key=lambda item: str(item).lower()):
        if is_candidate(child):
            candidates.append(str(child))
            if len(candidates) >= max_candidates:
                break
    return candidates


def _project_progress_match_segmentation(
    image_path: str,
    segmentation_paths: List[str],
    *,
    project_root: str,
    single_image: bool,
) -> Optional[str]:
    if not segmentation_paths:
        return None
    image_relative = _project_progress_relpath(image_path, project_root)
    image_key = _project_progress_pair_key(image_path)
    by_key = {
        _project_progress_pair_key(segmentation_path): segmentation_path
        for segmentation_path in segmentation_paths
    }
    if image_key and image_key in by_key:
        return by_key[image_key]
    for segmentation_path in segmentation_paths:
        segmentation_relative = _project_progress_relpath(
            segmentation_path,
            project_root,
        )
        if _looks_like_image_label_pair(image_relative, segmentation_relative):
            return segmentation_path
    if single_image and len(segmentation_paths) == 1:
        return segmentation_paths[0]
    return None


def _project_progress_correction_evidence(
    db: Session,
    workflow: WorkflowSession,
) -> Dict[str, Any]:
    paths = {
        _normalize_absolute_path(path)
        for path in [workflow.corrected_mask_path]
        if path
    }
    correction_sets = (
        db.query(WorkflowCorrectionSet)
        .filter(WorkflowCorrectionSet.workflow_id == workflow.id)
        .all()
    )
    for correction_set in correction_sets:
        for value in [
            correction_set.corrected_mask_path,
            correction_set.source_mask_path,
        ]:
            if value:
                paths.add(_normalize_absolute_path(value))
    keys = {_project_progress_pair_key(path) for path in paths if path}
    return {"paths": paths, "keys": {key for key in keys if key}}


def _project_progress_status_for_volume(
    *,
    image_path: str,
    segmentation_path: Optional[str],
    correction_evidence: Dict[str, Any],
) -> tuple[str, str, List[str]]:
    evidence: List[str] = []
    if not segmentation_path:
        return "missing_segmentation", "derived", ["No matching segmentation found."]

    normalized_segmentation = _normalize_absolute_path(segmentation_path)
    segmentation_key = _project_progress_pair_key(segmentation_path)
    image_key = _project_progress_pair_key(image_path)
    correction_paths = correction_evidence.get("paths") or set()
    correction_keys = correction_evidence.get("keys") or set()
    if normalized_segmentation in correction_paths or segmentation_key in correction_keys:
        evidence.append("Matches a saved proofreading correction set.")
        return "ground_truth", "correction_set", evidence
    if image_key and image_key in correction_keys:
        evidence.append("Image volume has a saved correction-set key.")
        return "ground_truth", "correction_set", evidence
    if _project_progress_has_ground_truth_marker(segmentation_path):
        evidence.append("Segmentation path looks like ground truth or proofread data.")
        return "ground_truth", "path_marker", evidence
    evidence.append("Segmentation exists, but it is not marked as proofread ground truth.")
    return "needs_proofreading", "derived", evidence


def _project_progress_status_label(status: str) -> str:
    return {
        "ground_truth": "Fully good",
        "needs_proofreading": "Needs proofreading",
        "missing_segmentation": "No segmentation",
        "ignored": "Ignored",
    }.get(status, status.replace("_", " ").title())


def _apply_project_progress_overrides(
    volume: Dict[str, Any],
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    override = overrides.get(volume["id"])
    if not isinstance(override, dict):
        return volume
    status = override.get("status")
    if status in PROJECT_PROGRESS_STATUS_DEFINITIONS:
        volume["status"] = status
        volume["status_label"] = _project_progress_status_label(status)
        volume["status_source"] = "manual_override"
    if "note" in override:
        volume["note"] = str(override.get("note") or "")
    return volume


def _build_workflow_project_progress(
    db: Session,
    workflow: WorkflowSession,
    *,
    user_id: int,
    project_observation: Optional[Dict[str, Any]] = None,
    persist_snapshot: bool = True,
) -> Dict[str, Any]:
    observation = project_observation or _observe_workflow_project(db, workflow, user_id)
    metadata = decode_json(workflow.metadata_json)
    overrides = metadata.get("project_progress_overrides")
    overrides = overrides if isinstance(overrides, dict) else {}
    correction_evidence = _project_progress_correction_evidence(db, workflow)
    volumes: List[Dict[str, Any]] = []
    seen_volume_ids: set[str] = set()

    for volume_set in observation.get("volume_sets") or []:
        if not isinstance(volume_set, dict):
            continue
        project_root = _normalize_absolute_path(volume_set.get("project_root"))
        if not project_root:
            continue
        image_candidates = _project_progress_volume_candidates(
            volume_set.get("image_root_path") or volume_set.get("image_path"),
            project_root=project_root,
            roles={"image", "volume"},
        )
        segmentation_candidates = _project_progress_volume_candidates(
            volume_set.get("label_root_path") or volume_set.get("label_path"),
            project_root=project_root,
            roles={"label", "prediction"},
        )
        if not image_candidates and volume_set.get("image_path"):
            image_candidates = [volume_set["image_path"]]
        if not segmentation_candidates and volume_set.get("label_path"):
            segmentation_candidates = [volume_set["label_path"]]

        for image_path in image_candidates:
            volume_id = _project_progress_volume_id(image_path, project_root)
            if volume_id in seen_volume_ids:
                continue
            seen_volume_ids.add(volume_id)
            segmentation_path = _project_progress_match_segmentation(
                image_path,
                segmentation_candidates,
                project_root=project_root,
                single_image=len(image_candidates) == 1,
            )
            status, status_source, evidence = _project_progress_status_for_volume(
                image_path=image_path,
                segmentation_path=segmentation_path,
                correction_evidence=correction_evidence,
            )
            segmentation_kind = (
                _role_for_project_file(
                    _project_progress_relpath(segmentation_path, project_root)
                )
                if segmentation_path
                else None
            )
            volume = {
                "id": volume_id,
                "name": pathlib.Path(image_path).name,
                "status": status,
                "status_label": _project_progress_status_label(status),
                "status_source": status_source,
                "project_root": project_root,
                "volume_set_id": volume_set.get("id"),
                "volume_set_name": volume_set.get("name"),
                "image_path": image_path,
                "segmentation_path": segmentation_path,
                "segmentation_kind": segmentation_kind,
                "evidence": evidence,
                "note": None,
            }
            volumes.append(_apply_project_progress_overrides(volume, overrides))

    if not volumes and (workflow.image_path or workflow.dataset_path):
        image_path = _normalize_absolute_path(workflow.image_path or workflow.dataset_path)
        project_root = _normalize_absolute_path(workflow.dataset_path) or str(
            pathlib.Path(image_path).parent
        )
        segmentation_path = workflow.label_path or workflow.mask_path or workflow.inference_output_path
        segmentation_path = (
            _normalize_absolute_path(segmentation_path) if segmentation_path else None
        )
        status, status_source, evidence = _project_progress_status_for_volume(
            image_path=image_path,
            segmentation_path=segmentation_path,
            correction_evidence=correction_evidence,
        )
        fallback = {
            "id": _project_progress_volume_id(image_path, project_root),
            "name": pathlib.Path(image_path).name,
            "status": status,
            "status_label": _project_progress_status_label(status),
            "status_source": status_source,
            "project_root": project_root,
            "volume_set_id": "workflow-current",
            "volume_set_name": "Current workflow",
            "image_path": image_path,
            "segmentation_path": segmentation_path,
            "segmentation_kind": "label" if segmentation_path else None,
            "evidence": evidence,
            "note": None,
        }
        volumes.append(_apply_project_progress_overrides(fallback, overrides))

    counts = {status: 0 for status in PROJECT_PROGRESS_STATUS_DEFINITIONS}
    for volume in volumes:
        counts[volume["status"]] = counts.get(volume["status"], 0) + 1
    tracked_total = len(volumes) - counts.get("ignored", 0)
    good_count = counts.get("ground_truth", 0)
    segmented_count = good_count + counts.get("needs_proofreading", 0)
    summary = {
        "total": len(volumes),
        "tracked_total": tracked_total,
        "ground_truth": good_count,
        "needs_proofreading": counts.get("needs_proofreading", 0),
        "missing_segmentation": counts.get("missing_segmentation", 0),
        "ignored": counts.get("ignored", 0),
        "remaining": counts.get("needs_proofreading", 0)
        + counts.get("missing_segmentation", 0),
        "completion_pct": round((good_count / tracked_total) * 100, 1)
        if tracked_total
        else 0,
        "segmentation_coverage_pct": round((segmented_count / tracked_total) * 100, 1)
        if tracked_total
        else 0,
    }
    project_name = workflow.title
    roots = observation.get("roots") or []
    if roots:
        project_name = project_name or roots[0].get("name")
    generated_at = datetime.now(timezone.utc).isoformat()
    progress = {
        "workflow_id": workflow.id,
        "generated_at": generated_at,
        "project_name": project_name,
        "project_roots": roots,
        "summary": summary,
        "status_definitions": PROJECT_PROGRESS_STATUS_DEFINITIONS,
        "volumes": volumes,
    }
    if persist_snapshot:
        metadata["project_progress_snapshot"] = {
            "generated_at": generated_at,
            "summary": summary,
            "volume_count": len(volumes),
            "volumes": [
                {
                    key: volume.get(key)
                    for key in [
                        "id",
                        "name",
                        "status",
                        "image_path",
                        "segmentation_path",
                        "volume_set_name",
                    ]
                }
                for volume in volumes[:100]
            ],
        }
        workflow.metadata_json = encode_json(metadata)
    return progress


def _format_project_progress_response(progress: Dict[str, Any]) -> str:
    summary = progress.get("summary") or {}
    total = int(summary.get("tracked_total") or summary.get("total") or 0)
    if not total:
        return (
            "I do not see tracked image volumes yet. Mount a project or choose data, "
            "then this tracker can count proofread, unproofread, and missing segmentations."
        )
    return (
        "I checked the project progress tracker. "
        f"It has {total} tracked image volume(s): "
        f"{summary.get('ground_truth', 0)} fully good ground-truth volume(s), "
        f"{summary.get('needs_proofreading', 0)} with segmentations that still need proofreading, "
        f"and {summary.get('missing_segmentation', 0)} with no segmentation yet. "
        f"Completion is {summary.get('completion_pct', 0)}%."
    )


def _query_wants_progress_based_training(lower_query: str) -> bool:
    if not _query_has_relaxed(
        lower_query,
        [
            "train",
            "training",
            "fit model",
            "learn from",
            "use labels",
            "use masks",
            "ground truth",
            "ground-truth",
        ],
    ):
        return False
    return _query_has_relaxed(
        lower_query,
        [
            "ground truth",
            "ground-truth",
            "fully good",
            "good masks",
            "good labels",
            "good volumes",
            "done volumes",
            "proofread",
            "proofreaded",
            "curated",
            "verified",
            "segment the rest",
            "segment rest",
            "remaining volumes",
            "rest of",
            "unsegmented",
            "no segmentation",
            "missing segmentation",
        ],
    )


def _query_wants_train_all_available_labels(lower_query: str) -> bool:
    return _query_has_relaxed(
        lower_query,
        [
            "all labels",
            "all masks",
            "all segmentations",
            "all labeled",
            "include unproofread",
            "include draft",
            "draft masks",
            "draft labels",
            "use every label",
            "use all labels",
        ],
    )


def _query_wants_segment_remaining_after_training(lower_query: str) -> bool:
    return _query_has_relaxed(
        lower_query,
        [
            "segment the rest",
            "segment rest",
            "segment remaining",
            "rest of the volumes",
            "remaining volumes",
            "the rest",
            "unsegmented",
            "no segmentation",
            "missing segmentation",
        ],
    )


def _safe_subset_token(value: Any, *, fallback: str = "item") -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("._-")
    return (token or fallback)[:96]


def _training_subset_base_dir(project_root: str) -> pathlib.Path:
    configured = os.getenv(
        "PYTC_TRAINING_SUBSET_ROOT",
        "/home/weidf/demo_data/.pytc_training_subsets",
    )
    project_token = _safe_subset_token(
        pathlib.Path(project_root).name,
        fallback="project",
    )
    return pathlib.Path(configured).expanduser() / project_token


def _link_or_copy_subset_file(source_path: str, destination_path: pathlib.Path) -> str:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists() or destination_path.is_symlink():
        return str(destination_path)
    try:
        os.symlink(source_path, destination_path)
    except OSError:
        shutil.copy2(source_path, destination_path)
    return str(destination_path)


def _subset_public_volume(volume: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": volume.get("id"),
        "name": volume.get("name"),
        "status": volume.get("status"),
        "image_path": volume.get("image_path"),
        "segmentation_path": volume.get("segmentation_path"),
    }


def _build_progress_training_subset_plan(
    workflow: WorkflowSession,
    progress: Dict[str, Any],
    *,
    lower_query: str,
) -> Optional[Dict[str, Any]]:
    volumes = [
        volume
        for volume in progress.get("volumes") or []
        if isinstance(volume, dict) and volume.get("status") != "ignored"
    ]
    if not volumes:
        return None

    include_draft_labels = _query_wants_train_all_available_labels(lower_query)
    training_statuses = ["ground_truth"]
    if include_draft_labels:
        training_statuses.append("needs_proofreading")

    train_volumes = [
        volume
        for volume in volumes
        if volume.get("status") in training_statuses
        and volume.get("image_path")
        and volume.get("segmentation_path")
    ]
    if not train_volumes and include_draft_labels:
        train_volumes = [
            volume
            for volume in volumes
            if volume.get("status") == "needs_proofreading"
            and volume.get("image_path")
            and volume.get("segmentation_path")
        ]
        training_statuses = ["needs_proofreading"]
    if not train_volumes:
        return None

    target_volumes = [
        volume
        for volume in volumes
        if volume.get("status") == "missing_segmentation" and volume.get("image_path")
    ]
    review_volumes = [
        volume
        for volume in volumes
        if volume.get("status") == "needs_proofreading"
        and volume.get("image_path")
        and volume.get("segmentation_path")
    ]
    if include_draft_labels:
        review_volumes = []

    project_root = (
        _normalize_absolute_path(train_volumes[0].get("project_root"))
        or _derive_workflow_root_path(workflow)
        or _normalize_absolute_path(workflow.dataset_path)
    )
    if not project_root:
        return None

    run_slug = (
        f"workflow_{workflow.id}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    )
    subset_root = _training_subset_base_dir(project_root) / run_slug
    image_dir = subset_root / "image"
    label_dir = subset_root / "seg"
    linked_pairs: List[Dict[str, Any]] = []
    used_image_names: set[str] = set()
    used_label_names: set[str] = set()

    for index, volume in enumerate(train_volumes, start=1):
        image_source = _normalize_absolute_path(volume.get("image_path"))
        label_source = _normalize_absolute_path(volume.get("segmentation_path"))
        if not image_source or not label_source:
            continue
        image_name = pathlib.Path(image_source).name
        label_name = pathlib.Path(label_source).name
        if image_name in used_image_names:
            image_name = f"{index:03d}_{image_name}"
        if label_name in used_label_names:
            label_name = f"{index:03d}_{label_name}"
        used_image_names.add(image_name)
        used_label_names.add(label_name)
        linked_image = _link_or_copy_subset_file(image_source, image_dir / image_name)
        linked_label = _link_or_copy_subset_file(label_source, label_dir / label_name)
        linked_pairs.append(
            {
                **_subset_public_volume(volume),
                "subset_image_path": linked_image,
                "subset_segmentation_path": linked_label,
            }
        )

    if not linked_pairs:
        return None

    output_path = pathlib.Path(project_root) / "outputs" / "training" / run_slug
    manifest_path = subset_root / "volume_subset_manifest.json"
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workflow_id": workflow.id,
        "project_root": project_root,
        "selection_basis": "project_progress",
        "training_statuses": training_statuses,
        "train_pairs": linked_pairs,
        "target_images": [_subset_public_volume(volume) for volume in target_volumes],
        "review_pairs": [_subset_public_volume(volume) for volume in review_volumes],
        "source_progress_summary": progress.get("summary") or {},
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return {
        "run_slug": run_slug,
        "selection_basis": "project_progress",
        "training_statuses": training_statuses,
        "image_path": str(image_dir),
        "label_path": str(label_dir),
        "output_path": str(output_path),
        "manifest_path": str(manifest_path),
        "train_volume_count": len(linked_pairs),
        "target_volume_count": len(target_volumes),
        "review_volume_count": len(review_volumes),
        "train_pairs": linked_pairs[:20],
        "target_images": [
            _subset_public_volume(volume) for volume in target_volumes[:20]
        ],
        "review_pairs": [
            _subset_public_volume(volume) for volume in review_volumes[:20]
        ],
    }


def _format_progress_training_response(
    subset_plan: Dict[str, Any],
    *,
    include_segment_rest: bool,
) -> str:
    train_count = int(subset_plan.get("train_volume_count") or 0)
    target_count = int(subset_plan.get("target_volume_count") or 0)
    review_count = int(subset_plan.get("review_volume_count") or 0)
    statuses = subset_plan.get("training_statuses") or []
    source = (
        "fully good ground-truth volume"
        if statuses == ["ground_truth"]
        else "labeled volume"
    )
    response = (
        f"Yes. I found {train_count} {source}{'' if train_count == 1 else 's'} "
        "that can be used for this training run, and I staged them as a clean subset "
        "so draft or missing masks do not leak into the labels."
    )
    if include_segment_rest and target_count:
        response += (
            f" After training, the {target_count} image-only volume"
            f"{'' if target_count == 1 else 's'} should be the first inference target."
        )
    if review_count:
        response += (
            f" I left {review_count} draft segmentation volume"
            f"{'' if review_count == 1 else 's'} out of training until you mark them good."
        )
    response += " Review the run card before launching it."
    return response


def _build_agent_trace(
    *,
    workflow: WorkflowSession,
    project_observation: Dict[str, Any],
    intent: str,
    actions: List[AgentChatAction],
) -> List[AgentTraceItem]:
    trace: List[AgentTraceItem] = [
        AgentTraceItem(
            label="Read workflow state",
            detail=(
                f"Stage: {workflow.stage}; "
                f"image {'set' if workflow.image_path or workflow.dataset_path else 'missing'}; "
                f"mask/label {'set' if workflow.label_path or workflow.mask_path else 'missing'}."
            ),
        )
    ]
    roots = project_observation.get("roots") or []
    volume_sets = project_observation.get("volume_sets") or []
    if roots:
        root_names = ", ".join(str(root.get("name") or root.get("path")) for root in roots[:2])
        trace.append(
            AgentTraceItem(
                label="Checked project files",
                detail=(
                    f"Scanned {root_names}; found {len(volume_sets)} image/seg set(s)."
                ),
            )
        )
    elif project_observation.get("errors"):
        trace.append(
            AgentTraceItem(
                label="Checked project files",
                detail="Tried to inspect the project folder, but the scan failed.",
                status="warning",
            )
        )
    else:
        trace.append(
            AgentTraceItem(
                label="Checked project files",
                detail="No mounted project root was available to scan.",
                status="missing",
            )
        )
    trace.append(
        AgentTraceItem(
            label="Prepared response",
            detail=(
                f"Intent: {intent}; "
                f"{len(actions)} runnable app card(s) prepared."
            ),
        )
    )
    return trace


def _workflow_project_context(workflow: WorkflowSession) -> Dict[str, Any]:
    metadata = decode_json(workflow.metadata_json)
    context = metadata.get("project_context") if isinstance(metadata, dict) else {}
    return context if isinstance(context, dict) else {}


def _format_scale_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _format_scales(scales: List[float]) -> str:
    return ",".join(_format_scale_number(value) for value in scales)


def _format_voxel_size_nm(value: Any) -> str:
    if not isinstance(value, list) or len(value) < 3:
        return ""
    try:
        return " x ".join(_format_scale_number(float(item)) for item in value[:3]) + " nm"
    except (TypeError, ValueError):
        return ""


def _parse_visualization_scales_from_query(query: str) -> Optional[List[float]]:
    lower = query.lower()
    values = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", query)]
    unit_multiplier = (
        1000.0
        if any(term in lower for term in ["µm", "um", "micron", "microns"])
        else 1.0
    )
    if len(values) >= 3:
        return [value * unit_multiplier for value in values[:3]]
    if len(values) == 1 and any(
        term in lower for term in ["isotropic", "same scale", "same voxel"]
    ):
        value = values[0] * unit_multiplier
        return [value, value, value]
    return None


def _query_wants_visualization_scales(lower_query: str) -> bool:
    if not any(
        term in lower_query
        for term in [
            "reload",
            "load",
            "open",
            "show",
            "view",
            "visualize",
            "visualise",
            "set",
            "change",
            "update viewer",
            "use scales",
            "with scales",
            "with voxel",
            "viewer",
        ]
    ):
        return False
    explicit_scale_language = _query_has(
        lower_query,
        [
            "scales",
            "voxel size",
            "voxel spacing",
            "spacing",
            "resolution",
            "nanometer",
            "nanometers",
            "micron",
            "microns",
        ],
    )
    singular_scale_language = bool(
        re.search(r"(?<![a-z0-9_-])scale(?![a-z0-9_-])", lower_query)
    )
    reload_with_values = (
        "reload" in lower_query
        and bool(re.search(r"\d", lower_query))
        and any(marker in lower_query for marker in [",", "-", "nm", "um", "µm"])
    )
    return explicit_scale_language or singular_scale_language or reload_with_values


def _store_visualization_scales(
    db: Session,
    workflow: WorkflowSession,
    scales_nm: List[float],
    *,
    source_query: str,
) -> None:
    metadata = decode_json(workflow.metadata_json)
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["visualization_scales"] = scales_nm
    metadata["visualization_scales_source"] = "workflow_agent"
    update_workflow_fields(db, workflow, {"metadata": metadata}, commit=True)
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="agent",
        event_type="visualization.scales_updated",
        stage=workflow.stage,
        summary=f"Saved visualization voxel scale {_format_scales(scales_nm)} nm.",
        payload={
            "scales_nm": scales_nm,
            "source": "workflow_agent",
            "query_preview": source_query[:240],
        },
        commit=True,
    )


def _extract_project_context_from_query(query: str) -> Dict[str, Any]:
    lower = query.lower()
    context: Dict[str, Any] = {}
    modality_terms = [
        ("electron microscopy", ["electron microscopy", "electron microscope"]),
        ("EM", [" em ", "em ", "sem", "tem", "fib-sem", "fib sem"]),
        ("confocal microscopy", ["confocal"]),
        ("light-sheet microscopy", ["light sheet", "light-sheet"]),
        ("fluorescence microscopy", ["fluorescence", "fluorescent"]),
        ("brightfield microscopy", ["brightfield", "bright-field"]),
        ("MRI", [" mri ", "mri"]),
        ("CT", [" ct ", "micro-ct", "micro ct"]),
    ]
    padded_lower = f" {lower} "
    for label, terms in modality_terms:
        if any(term in padded_lower for term in terms):
            context["imaging_modality"] = label
            break

    target_terms = [
        ("mitochondria", ["mitochondria", "mitochondrion", "mito"]),
        ("membranes", ["membrane", "membranes"]),
        ("synapses", ["synapse", "synapses"]),
        ("nuclei", ["nucleus", "nuclei"]),
        ("cells", ["cell", "cells"]),
        ("neurites", ["neurite", "neurites", "axon", "dendrite"]),
        ("vasculature", ["vessel", "vasculature", "blood vessel"]),
        ("organelle", ["organelle", "organelles"]),
    ]
    for label, terms in target_terms:
        if any(term in lower for term in terms):
            context["target_structure"] = label
            break

    if any(
        term in lower
        for term in ["fast", "quick", "smoke", "prototype", "speed", "care about speed"]
    ):
        context["optimization_priority"] = "speed"
    elif any(term in lower for term in ["accurate", "accuracy", "quality", "best"]):
        context["optimization_priority"] = "accuracy"

    voxel_size_nm = _parse_visualization_scales_from_query(query)
    if voxel_size_nm:
        context["voxel_size_nm"] = voxel_size_nm
        context["voxel_size_source"] = "workflow_agent_context"

    if context:
        context["freeform_note"] = query[:500]
    return context


def _merge_project_context(
    db: Session,
    workflow: WorkflowSession,
    context_update: Dict[str, Any],
) -> None:
    if not context_update:
        return
    metadata = decode_json(workflow.metadata_json)
    project_context = metadata.get("project_context")
    if not isinstance(project_context, dict):
        project_context = {}
    project_context = {
        **project_context,
        **context_update,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "workflow_agent_context",
    }
    metadata["project_context"] = project_context
    voxel_size_nm = project_context.get("voxel_size_nm")
    if isinstance(voxel_size_nm, list) and len(voxel_size_nm) >= 3:
        metadata["visualization_scales"] = voxel_size_nm[:3]
        metadata["visualization_scales_source"] = project_context.get(
            "voxel_size_source",
            "workflow_agent_context",
        )
    update_workflow_fields(db, workflow, {"metadata": metadata}, commit=False)


def _project_context_missing_fields(workflow: WorkflowSession) -> List[str]:
    context = _workflow_project_context(workflow)
    if context.get("use_defaults"):
        return []
    missing = []
    if not context.get("imaging_modality"):
        missing.append("imaging modality")
    if not context.get("target_structure"):
        missing.append("target structure")
    if not context.get("optimization_priority"):
        missing.append("speed vs accuracy preference")
    return missing


def _format_project_context_prompt(
    workflow: WorkflowSession,
    action_label: str,
) -> str:
    missing = _project_context_missing_fields(workflow)
    if not missing:
        missing = [
            "imaging modality",
            "target structure",
            "speed vs accuracy preference",
        ]
    return (
        f"Before I {action_label}, I need a little project context: "
        f"{', '.join(missing[:3])}. "
        "You can answer casually, like: EM mitochondria, prioritize accuracy. "
        "Or just say to use defaults."
    )


def _format_project_context_saved_response(
    workflow: WorkflowSession,
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    context = _workflow_project_context(workflow)
    summary = []
    if context.get("imaging_modality"):
        summary.append(context["imaging_modality"])
    if context.get("target_structure"):
        summary.append(context["target_structure"])
    if context.get("optimization_priority"):
        summary.append(f"{context['optimization_priority']} priority")
    voxel_size = _format_voxel_size_nm(context.get("voxel_size_nm"))
    if voxel_size:
        summary.append(f"{voxel_size} resolution")
    missing = _project_context_missing_fields(workflow)
    if missing:
        return (
            f"Got it, I saved {', '.join(summary) or 'that partial context'}. "
            f"I still need {', '.join(missing)} before I choose a model or preset."
        )
    return (
        f"Got it, I saved {', '.join(summary)}. "
        f"The next useful move looks like: {_lower_first(_strip_sentence_period(recommendation.decision))}."
    )


def _format_project_context_response(
    workflow: WorkflowSession,
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    project_context = _workflow_project_context(workflow)
    project_name = workflow.title or f"Workflow #{workflow.id}"
    image_label = _short_path_label(workflow.image_path or workflow.dataset_path)
    mask_label = _short_path_label(
        workflow.mask_path or workflow.label_path or workflow.inference_output_path
    )
    lines = [
        f"Project: {project_name}.",
        f"Stage: {workflow.stage.replace('_', ' ')}.",
        f"Image: {image_label}. Mask/result: {mask_label}.",
    ]
    if project_context.get("imaging_modality") or project_context.get(
        "target_structure"
    ):
        context_bits = [
            project_context.get("imaging_modality"),
            project_context.get("target_structure"),
            project_context.get("optimization_priority"),
            _format_voxel_size_nm(project_context.get("voxel_size_nm")),
        ]
        lines.append(
            "Context: " + ", ".join(str(bit) for bit in context_bits if bit) + "."
        )
    lines.append(f"Next: {recommendation.decision}")
    return "\n".join(lines)


def _format_informational_followup_response(
    workflow: WorkflowSession,
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    context = _workflow_project_context(workflow)
    lines = [
        f"I would probably start here: {_lower_first(_strip_sentence_period(recommendation.decision))}.",
    ]
    if recommendation.rationale:
        lines.append(
            f"That makes sense because {_lower_first(_strip_sentence_period(recommendation.rationale))}."
        )
    context_bits = [
        context.get("imaging_modality"),
        context.get("target_structure"),
        context.get("optimization_priority"),
        _format_voxel_size_nm(context.get("voxel_size_nm")),
    ]
    if any(context_bits):
        lines.append(
            "I am using the context we have: "
            + ", ".join(str(bit) for bit in context_bits if bit)
            + "."
        )
    if recommendation.blockers:
        lines.append(
            f"The thing still missing is {_lower_first(_strip_sentence_period(recommendation.blockers[0]))}."
        )
    lines.append("I will not launch an app step unless you ask me to open or run it.")
    return " ".join(lines)


def _format_style_feedback_response(
    workflow: WorkflowSession,
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    context = _workflow_project_context(workflow)
    context_bits = [
        context.get("imaging_modality"),
        context.get("target_structure"),
    ]
    context_text = ", ".join(str(bit) for bit in context_bits if bit)
    next_step = _lower_first(_strip_sentence_period(recommendation.decision))
    if context_text:
        return (
            f"Yeah, agreed. I will keep the visible answer more conversational and leave the mechanical details in What I checked. "
            f"Right now I am treating this as a {context_text} workflow, and the next useful move looks like: {next_step}."
        )
    return (
        "Yeah, agreed. I will keep the visible answer more conversational and leave the mechanical details in What I checked. "
        f"Right now the next useful move looks like: {next_step}."
    )



def _format_needed_from_user_response(
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    if recommendation.stage == "proofreading":
        gap = recommendation.blockers[0] if recommendation.blockers else "Save edits."
        return (
            "I need your mask judgment here. "
            "Proofread the likely mistakes, save the fixes, then export masks. "
            f"The current gap is {_lower_first(_strip_sentence_period(gap))}."
        )

    blocker = recommendation.blockers[0] if recommendation.blockers else None
    if blocker:
        return (
            f"I am missing one workflow input: {_lower_first(_strip_sentence_period(blocker))}. "
            f"After that, the next useful move is {_lower_first(_strip_sentence_period(recommendation.decision))}."
        )
    return (
        "I need your approval before changing artifacts. "
        f"The app step I would run is {_lower_first(_strip_sentence_period(recommendation.decision))}."
    )


def _format_capabilities_response() -> str:
    return "\n".join(
        [
            "I can run approved app steps: infer, proofread, train on saved edits, compare metrics, export evidence, and move screens.",
            "Ask naturally, e.g. 'segment this data', 'proofread this result', or 'compare results'.",
            "I will ask approval before long runs or artifact changes.",
        ]
    )


def _format_repair_response(
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    return "\n".join(
        [
            "That was too generic; I need a little more detail.",
            "Say what you want to do next, or ask 'status' for what is ready.",
            f"Current next step: {recommendation.decision}",
        ]
    )


def _format_unknown_workflow_query_response(
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    return "\n".join(
        [
            "I am not sure which app step that maps to.",
            f"Current next step: {recommendation.decision}",
            "You can say it casually, e.g. 'segment this data', 'show my labels', 'proofread this', or 'train a model'.",
        ]
    )


def _workflow_agent_tasks_from_readiness(
    readiness: List[WorkflowReadinessItem],
) -> List[AgentTaskItem]:
    tasks: List[AgentTaskItem] = []
    for index, item in enumerate(readiness, start=1):
        status = "done" if item.complete else "blocked"
        if not item.complete and item.severity != "warning":
            status = "pending"
        tasks.append(
            AgentTaskItem(
                id=item.id,
                label=item.label,
                status=status,
                detail=item.detail,
                priority="high" if index <= 2 and not item.complete else "normal",
            )
        )
    return tasks


@router.get("/current", response_model=WorkflowDetailResponse)
def get_current_workflow(
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_current_or_create_workflow(db, user_id=user.id)
    return {
        "workflow": _workflow_response(workflow),
        "events": _event_list(db, workflow.id),
    }


@router.post("/current/reset", response_model=WorkflowDetailResponse)
def reset_current_workflow(
    body: Optional[WorkflowResetRequest] = None,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    body = body or WorkflowResetRequest()
    workflow = create_workflow_session(
        db,
        user_id=user.id,
        title=body.title or "Segmentation Workflow",
        metadata={
            **body.metadata,
            "created_from": body.metadata.get("created_from", "workflow_reset"),
        },
    )
    return {
        "workflow": _workflow_response(workflow),
        "events": _event_list(db, workflow.id),
    }


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    body: WorkflowUpdateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    updates = body.model_dump(exclude_unset=True)
    workflow = update_workflow_fields(db, workflow, updates, commit=True)
    return _workflow_response(workflow)


@router.get("/{workflow_id}/events", response_model=List[WorkflowEventResponse])
def list_workflow_events(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    return _event_list(db, workflow_id)


@router.get("/{workflow_id}/commands", response_model=List[WorkflowCommandResponse])
def list_workflow_commands(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    commands = (
        db.query(WorkflowCommand)
        .filter(WorkflowCommand.workflow_id == workflow_id)
        .order_by(WorkflowCommand.created_at.asc(), WorkflowCommand.id.asc())
        .all()
    )
    return [_command_response(command) for command in commands]


@router.get("/{workflow_id}/hotspots", response_model=WorkflowHotspotsResponse)
def get_workflow_hotspots(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    events = _event_rows(db, workflow.id)
    hotspots = _compute_hotspots(workflow, events)
    _persist_computed_hotspots(db, workflow_id=workflow.id, hotspots=hotspots)
    return WorkflowHotspotsResponse(
        workflow_id=workflow.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hotspots=hotspots,
    )


@router.get(
    "/{workflow_id}/impact-preview",
    response_model=WorkflowImpactPreviewResponse,
)
def get_workflow_impact_preview(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    events = _event_rows(db, workflow.id)
    hotspots = _compute_hotspots(workflow, events)
    corrected_mask_path = workflow.corrected_mask_path or _latest_exported_mask_path(
        db, workflow.id
    )
    return _compute_impact_preview(workflow, events, hotspots, corrected_mask_path)


@router.get("/{workflow_id}/metrics", response_model=WorkflowMetricsResponse)
def get_workflow_metrics(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    events = _event_rows(db, workflow.id)
    return WorkflowMetricsResponse(
        workflow_id=workflow.id,
        metrics=compute_workflow_metrics(events),
    )


@router.get(
    "/{workflow_id}/project-progress",
    response_model=WorkflowProjectProgressResponse,
)
def get_workflow_project_progress(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    progress = _build_workflow_project_progress(db, workflow, user_id=user.id)
    db.commit()
    append_app_event(
        component="workflow_project_progress",
        event="project_progress_refreshed",
        level="INFO",
        message="Workflow project progress tracker refreshed.",
        workflow_id=workflow.id,
        user_id=user.id,
        total=progress["summary"].get("total"),
        ground_truth=progress["summary"].get("ground_truth"),
        needs_proofreading=progress["summary"].get("needs_proofreading"),
        missing_segmentation=progress["summary"].get("missing_segmentation"),
    )
    return progress


@router.post(
    "/{workflow_id}/project-progress/volume-status",
    response_model=WorkflowProjectProgressResponse,
)
def update_workflow_project_progress_volume_status(
    workflow_id: int,
    body: WorkflowProjectProgressVolumeUpdate,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    provided_fields = getattr(body, "model_fields_set", set()) or getattr(
        body,
        "__fields_set__",
        set(),
    )
    if not body.volume_id:
        raise HTTPException(status_code=400, detail="volume_id is required")
    if "status" in provided_fields and body.status not in PROJECT_PROGRESS_STATUS_DEFINITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(PROJECT_PROGRESS_STATUS_DEFINITIONS)}",
        )
    metadata = decode_json(workflow.metadata_json)
    overrides = metadata.get("project_progress_overrides")
    overrides = overrides if isinstance(overrides, dict) else {}
    current = overrides.get(body.volume_id)
    current = current if isinstance(current, dict) else {}
    if "status" in provided_fields:
        current["status"] = body.status
    if "note" in provided_fields:
        current["note"] = body.note or ""
    if not current.get("status") and not current.get("note"):
        overrides.pop(body.volume_id, None)
    else:
        overrides[body.volume_id] = current
    metadata["project_progress_overrides"] = overrides
    workflow.metadata_json = encode_json(metadata)
    progress = _build_workflow_project_progress(db, workflow, user_id=user.id)
    db.commit()
    append_app_event(
        component="workflow_project_progress",
        event="project_progress_volume_status_updated",
        level="INFO",
        message="Workflow project progress volume status override updated.",
        workflow_id=workflow.id,
        user_id=user.id,
        volume_id=body.volume_id,
        status=current.get("status"),
    )
    return progress


@router.get(
    "/{workflow_id}/agent/recommendation",
    response_model=WorkflowAgentRecommendationResponse,
)
def get_workflow_agent_recommendation(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    return _build_workflow_agent_recommendation(db, workflow)


@router.get(
    "/{workflow_id}/preflight",
    response_model=WorkflowPreflightResponse,
)
def get_workflow_preflight(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    return _build_workflow_preflight(db, workflow)


@router.get(
    "/{workflow_id}/artifacts",
    response_model=List[WorkflowArtifactResponse],
)
def list_workflow_artifacts(
    workflow_id: int,
    artifact_type: Optional[str] = None,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    query = db.query(WorkflowArtifact).filter(
        WorkflowArtifact.workflow_id == workflow_id
    )
    if artifact_type:
        query = query.filter(WorkflowArtifact.artifact_type == artifact_type)
    rows = query.order_by(
        WorkflowArtifact.created_at.asc(), WorkflowArtifact.id.asc()
    ).all()
    return [_artifact_response(row) for row in rows]


@router.post(
    "/{workflow_id}/artifacts",
    response_model=WorkflowArtifactResponse,
)
def create_artifact(
    workflow_id: int,
    body: WorkflowArtifactCreateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    artifact = create_workflow_artifact(
        db,
        workflow_id=workflow.id,
        artifact_type=body.artifact_type,
        role=body.role,
        path=body.path,
        uri=body.uri,
        name=body.name,
        checksum=body.checksum,
        metadata=body.metadata,
        commit=True,
    )
    return _artifact_response(artifact)


@router.get(
    "/{workflow_id}/model-runs",
    response_model=List[WorkflowModelRunResponse],
)
def list_model_runs(
    workflow_id: int,
    run_type: Optional[str] = None,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    query = db.query(WorkflowModelRun).filter(
        WorkflowModelRun.workflow_id == workflow_id
    )
    if run_type:
        query = query.filter(WorkflowModelRun.run_type == run_type)
    rows = query.order_by(
        WorkflowModelRun.created_at.asc(), WorkflowModelRun.id.asc()
    ).all()
    return [_model_run_response(row) for row in rows]


@router.post(
    "/{workflow_id}/model-runs",
    response_model=WorkflowModelRunResponse,
)
def create_model_run(
    workflow_id: int,
    body: WorkflowModelRunCreateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    run = WorkflowModelRun(
        workflow_id=workflow.id,
        run_id=body.run_id,
        run_type=body.run_type,
        status=body.status,
        name=body.name,
        config_path=body.config_path,
        log_path=body.log_path,
        output_path=body.output_path,
        checkpoint_path=body.checkpoint_path,
        input_artifact_id=body.input_artifact_id,
        output_artifact_id=body.output_artifact_id,
        metrics_json=encode_json(body.metrics),
        metadata_json=encode_json(body.metadata),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _model_run_response(run)


@router.get(
    "/{workflow_id}/model-versions",
    response_model=List[WorkflowModelVersionResponse],
)
def list_model_versions(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    rows = (
        db.query(WorkflowModelVersion)
        .filter(WorkflowModelVersion.workflow_id == workflow_id)
        .order_by(WorkflowModelVersion.created_at.asc(), WorkflowModelVersion.id.asc())
        .all()
    )
    return [_model_version_response(row) for row in rows]


@router.post(
    "/{workflow_id}/model-versions",
    response_model=WorkflowModelVersionResponse,
)
def create_model_version(
    workflow_id: int,
    body: WorkflowModelVersionCreateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    version = WorkflowModelVersion(
        workflow_id=workflow.id,
        version_label=body.version_label,
        status=body.status,
        checkpoint_path=body.checkpoint_path,
        training_run_id=body.training_run_id,
        checkpoint_artifact_id=body.checkpoint_artifact_id,
        correction_set_id=body.correction_set_id,
        metrics_json=encode_json(body.metrics),
        metadata_json=encode_json(body.metadata),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return _model_version_response(version)


@router.get(
    "/{workflow_id}/correction-sets",
    response_model=List[WorkflowCorrectionSetResponse],
)
def list_correction_sets(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    rows = (
        db.query(WorkflowCorrectionSet)
        .filter(WorkflowCorrectionSet.workflow_id == workflow_id)
        .order_by(
            WorkflowCorrectionSet.created_at.asc(), WorkflowCorrectionSet.id.asc()
        )
        .all()
    )
    return [_correction_set_response(row) for row in rows]


@router.get(
    "/{workflow_id}/evaluation-results",
    response_model=List[WorkflowEvaluationResponse],
)
def list_evaluation_results(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    rows = (
        db.query(WorkflowEvaluationResult)
        .filter(WorkflowEvaluationResult.workflow_id == workflow_id)
        .order_by(
            WorkflowEvaluationResult.created_at.asc(),
            WorkflowEvaluationResult.id.asc(),
        )
        .all()
    )
    return [_evaluation_response(row) for row in rows]


@router.post(
    "/{workflow_id}/evaluation-results",
    response_model=WorkflowEvaluationResponse,
)
def create_evaluation_result(
    workflow_id: int,
    body: WorkflowEvaluationCreateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    report_artifact = None
    if body.report_path:
        report_artifact = create_workflow_artifact(
            db,
            workflow_id=workflow.id,
            artifact_type="evaluation_report",
            role="case_study_evidence",
            path=body.report_path,
            metadata={"source": "manual_evaluation_result"},
            commit=False,
        )
    result = WorkflowEvaluationResult(
        workflow_id=workflow.id,
        name=body.name,
        baseline_run_id=body.baseline_run_id,
        candidate_run_id=body.candidate_run_id,
        model_version_id=body.model_version_id,
        report_artifact_id=report_artifact.id if report_artifact else None,
        report_path=body.report_path,
        summary=body.summary,
        metrics_json=encode_json(body.metrics),
        metadata_json=encode_json(body.metadata),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return _evaluation_response(result)


@router.post(
    "/{workflow_id}/evaluation-results/compute",
    response_model=WorkflowEvaluationResponse,
)
def compute_evaluation_result(
    workflow_id: int,
    body: WorkflowEvaluationComputeRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    try:
        metrics = compute_before_after_evaluation(
            baseline_prediction_path=body.baseline_prediction_path,
            candidate_prediction_path=body.candidate_prediction_path,
            ground_truth_path=body.ground_truth_path,
            baseline_dataset=body.baseline_dataset,
            candidate_dataset=body.candidate_dataset,
            ground_truth_dataset=body.ground_truth_dataset,
            crop=body.crop,
            baseline_channel=body.baseline_channel,
            candidate_channel=body.candidate_channel,
            ground_truth_channel=body.ground_truth_channel,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    metadata = {
        **body.metadata,
        "baseline_prediction_path": body.baseline_prediction_path,
        "candidate_prediction_path": body.candidate_prediction_path,
        "ground_truth_path": body.ground_truth_path,
        "baseline_dataset": body.baseline_dataset,
        "candidate_dataset": body.candidate_dataset,
        "ground_truth_dataset": body.ground_truth_dataset,
        "crop": body.crop,
        "baseline_channel": body.baseline_channel,
        "candidate_channel": body.candidate_channel,
        "ground_truth_channel": body.ground_truth_channel,
    }
    summary = (
        "Before/after evaluation computed. "
        f"Dice delta: {metrics.get('summary', {}).get('dice_delta')}."
    )
    report_path = body.report_path
    if report_path:
        report_payload = {
            "workflow_id": workflow.id,
            "name": body.name,
            "summary": summary,
            "metrics": metrics,
            "metadata": metadata,
        }
        report_path = write_evaluation_report(report_path, report_payload)

    report_artifact = None
    if report_path:
        report_artifact = create_workflow_artifact(
            db,
            workflow_id=workflow.id,
            artifact_type="evaluation_report",
            role="case_study_evidence",
            path=report_path,
            metadata={"source": "computed_evaluation_result"},
            commit=False,
        )

    result = WorkflowEvaluationResult(
        workflow_id=workflow.id,
        name=body.name or "before-after-evaluation",
        baseline_run_id=body.baseline_run_id,
        candidate_run_id=body.candidate_run_id,
        model_version_id=body.model_version_id,
        report_artifact_id=report_artifact.id if report_artifact else None,
        report_path=report_path,
        summary=summary,
        metrics_json=encode_json(metrics),
        metadata_json=encode_json(metadata),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return _evaluation_response(result)


@router.get(
    "/{workflow_id}/persisted-hotspots",
    response_model=List[WorkflowRegionHotspotResponse],
)
def list_persisted_hotspots(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    rows = (
        db.query(WorkflowRegionHotspot)
        .filter(WorkflowRegionHotspot.workflow_id == workflow_id)
        .order_by(WorkflowRegionHotspot.score.desc(), WorkflowRegionHotspot.id.asc())
        .all()
    )
    return [_region_hotspot_response(row) for row in rows]


def _has_event(events: List[WorkflowEvent], event_type: str) -> bool:
    return any(event.event_type == event_type for event in events)


def _case_study_readiness_gates(
    workflow: WorkflowSession, events: List[WorkflowEvent]
) -> List[Dict[str, Any]]:
    artifacts = list(getattr(workflow, "artifacts", []) or [])
    runs = list(getattr(workflow, "model_runs", []) or [])
    versions = list(getattr(workflow, "model_versions", []) or [])
    correction_sets = list(getattr(workflow, "correction_sets", []) or [])
    evaluations = list(getattr(workflow, "evaluation_results", []) or [])
    agent_plans = list(getattr(workflow, "agent_plans", []) or [])
    inference_completed = [
        run for run in runs if run.run_type == "inference" and run.status == "completed"
    ]
    proposal_audit_complete = bool(
        _has_event(events, "agent.proposal_created")
        and (
            _has_event(events, "agent.proposal_approved")
            or _has_event(events, "agent.proposal_rejected")
        )
    )
    agent_plan_created = bool(agent_plans or _has_event(events, "agent.plan_created"))
    agent_plan_decisioned = bool(
        any(
            plan.approval_status in {"approved", "rejected"}
            or plan.status in {"approved", "interrupted", "rejected"}
            for plan in agent_plans
        )
        or _has_event(events, "agent.plan_approved")
        or _has_event(events, "agent.plan_rejected")
        or _has_event(events, "agent.plan_interrupted")
        or _has_event(events, "agent.plan_resumed")
    )

    gates = [
        {
            "id": "workflow_context",
            "label": "Workflow context exists",
            "complete": bool(workflow.id and _has_event(events, "workflow.created")),
            "required_for": ["CS1", "CS7"],
        },
        {
            "id": "data_loaded",
            "label": "Dataset/image artifacts are linked",
            "complete": bool(
                workflow.image_path
                or any(
                    a.artifact_type in {"dataset", "image_volume"} for a in artifacts
                )
                or _has_event(events, "dataset.loaded")
                or _has_event(events, "viewer.created")
            ),
            "required_for": ["CS1"],
        },
        {
            "id": "baseline_inference",
            "label": "Baseline inference run/output is captured",
            "complete": bool(
                workflow.inference_output_path
                or any(run.run_type == "inference" for run in runs)
                or _has_event(events, "inference.completed")
            ),
            "required_for": ["CS1", "CS4"],
        },
        {
            "id": "proofreading_corrections",
            "label": "Proofreading corrections are saved/exported",
            "complete": bool(
                workflow.corrected_mask_path
                or correction_sets
                or _has_event(events, "proofreading.masks_exported")
            ),
            "required_for": ["CS2", "CS3"],
        },
        {
            "id": "retraining_handoff",
            "label": "Corrections can be staged for retraining",
            "complete": bool(
                workflow.stage in {"retraining_staged", "evaluation"}
                or _has_event(events, "retraining.staged")
            ),
            "required_for": ["CS3", "CS5"],
        },
        {
            "id": "training_completion",
            "label": "Retraining produces a terminal run record",
            "complete": bool(
                any(
                    run.run_type == "training" and run.status in {"completed", "failed"}
                    for run in runs
                )
                or _has_event(events, "training.completed")
                or _has_event(events, "training.failed")
            ),
            "required_for": ["CS3", "CS6"],
        },
        {
            "id": "model_version",
            "label": "A versioned candidate model exists",
            "complete": bool(versions or workflow.checkpoint_path),
            "required_for": ["CS3", "CS4"],
        },
        {
            "id": "post_retraining_inference",
            "label": "Post-retraining inference is captured",
            "complete": len(inference_completed) >= 2,
            "required_for": ["CS4"],
        },
        {
            "id": "evaluation_result",
            "label": "Before/after evaluation evidence exists",
            "complete": bool(evaluations),
            "required_for": ["CS4", "CS7"],
        },
        {
            "id": "agent_plan_preview",
            "label": "Bounded agent plan is previewed and decisioned",
            "complete": bool(agent_plan_created and agent_plan_decisioned),
            "required_for": ["CS5", "CS6"],
        },
        {
            "id": "agent_audit",
            "label": "Agent proposal decisions are auditable",
            "complete": bool(
                proposal_audit_complete
                or (agent_plan_created and agent_plan_decisioned)
            ),
            "required_for": ["CS5", "CS6"],
        },
    ]
    return gates


@router.get(
    "/{workflow_id}/case-study-readiness",
    response_model=WorkflowReadinessResponse,
)
def get_case_study_readiness(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    events = _event_rows(db, workflow.id)
    gates = _case_study_readiness_gates(workflow, events)
    completed_count = len([gate for gate in gates if gate["complete"]])
    next_required_items = [gate["label"] for gate in gates if not gate["complete"]][:4]
    return WorkflowReadinessResponse(
        workflow_id=workflow.id,
        ready_for_case_study=completed_count == len(gates),
        completed_count=completed_count,
        total_count=len(gates),
        gates=gates,
        next_required_items=next_required_items,
    )


def _create_agent_plan_preview(
    db: Session,
    *,
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
    body: WorkflowAgentPlanCreateRequest,
) -> WorkflowAgentPlan:
    gates = _case_study_readiness_gates(workflow, events)
    graph = build_case_study_plan_graph(
        workflow=workflow,
        events=events,
        gates=gates,
        title=body.title,
        goal=body.goal,
    )
    plan = WorkflowAgentPlan(
        workflow_id=workflow.id,
        title=graph["title"],
        status="draft",
        risk_level="medium",
        approval_status="pending",
        goal=graph["goal"],
        graph_json=encode_json(graph),
        metadata_json=encode_json(
            {
                **body.metadata,
                "plan_type": body.plan_type,
                "source": "case_study_plan_preview",
            }
        ),
    )
    db.add(plan)
    db.flush()

    for node in graph.get("nodes", []):
        step = WorkflowAgentStep(
            plan_id=plan.id,
            step_index=int(node.get("index", 0)),
            action=str(node.get("action")),
            status=str(node.get("status") or "blocked"),
            requires_approval=bool(node.get("requires_approval")),
            summary=node.get("summary"),
            params_json=encode_json(
                {
                    "title": node.get("title"),
                    "stage": node.get("stage"),
                    "gate_id": node.get("gate_id"),
                    "dependencies": node.get("dependencies") or [],
                    "client_effects": node.get("client_effects") or {},
                    "required_for": node.get("required_for") or [],
                }
            ),
        )
        db.add(step)

    db.flush()
    event = append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="agent",
        event_type="agent.plan_created",
        stage=workflow.stage,
        summary=f"Created bounded agent plan: {plan.title}",
        payload={
            "plan_id": plan.id,
            "plan_type": body.plan_type,
            "ready_steps": len(
                [
                    node
                    for node in graph.get("nodes", [])
                    if node.get("status") == "ready"
                ]
            ),
            "blocked_steps": len(
                [
                    node
                    for node in graph.get("nodes", [])
                    if node.get("status") == "blocked"
                ]
            ),
            "graph_spec_version": graph.get("graph_spec_version"),
        },
        approval_status="pending",
        commit=False,
    )
    plan.source_event_id = event.id if event else None
    db.commit()
    db.refresh(plan)
    return plan


@router.get(
    "/{workflow_id}/agent-plans",
    response_model=List[WorkflowAgentPlanResponse],
)
def list_agent_plans(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    rows = (
        db.query(WorkflowAgentPlan)
        .filter(WorkflowAgentPlan.workflow_id == workflow_id)
        .order_by(WorkflowAgentPlan.created_at.asc(), WorkflowAgentPlan.id.asc())
        .all()
    )
    return [_agent_plan_response(row) for row in rows]


@router.post(
    "/{workflow_id}/agent-plans",
    response_model=WorkflowAgentPlanResponse,
)
def create_agent_plan(
    workflow_id: int,
    body: WorkflowAgentPlanCreateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    events = _event_rows(db, workflow.id)
    plan = _create_agent_plan_preview(
        db,
        workflow=workflow,
        events=events,
        body=body,
    )
    return _agent_plan_response(plan)


@router.get(
    "/{workflow_id}/agent-plans/{plan_id}",
    response_model=WorkflowAgentPlanResponse,
)
def get_agent_plan(
    workflow_id: int,
    plan_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    plan = _get_agent_plan_or_404(db, workflow_id=workflow_id, plan_id=plan_id)
    return _agent_plan_response(plan)


@router.post(
    "/{workflow_id}/agent-plans/{plan_id}/approve",
    response_model=WorkflowAgentPlanResponse,
)
def approve_agent_plan(
    workflow_id: int,
    plan_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    plan = _get_agent_plan_or_404(db, workflow_id=workflow.id, plan_id=plan_id)
    if plan.approval_status == "rejected":
        raise HTTPException(status_code=400, detail="Rejected plans cannot be approved")
    plan.approval_status = "approved"
    plan.status = "approved"
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="user",
        event_type="agent.plan_approved",
        stage=workflow.stage,
        summary=f"Approved bounded agent plan: {plan.title}",
        payload={"plan_id": plan.id},
        commit=False,
    )
    db.commit()
    db.refresh(plan)
    return _agent_plan_response(plan)


@router.post(
    "/{workflow_id}/agent-plans/{plan_id}/reject",
    response_model=WorkflowAgentPlanResponse,
)
def reject_agent_plan(
    workflow_id: int,
    plan_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    plan = _get_agent_plan_or_404(db, workflow_id=workflow.id, plan_id=plan_id)
    plan.approval_status = "rejected"
    plan.status = "rejected"
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="user",
        event_type="agent.plan_rejected",
        stage=workflow.stage,
        summary=f"Rejected bounded agent plan: {plan.title}",
        payload={"plan_id": plan.id},
        commit=False,
    )
    db.commit()
    db.refresh(plan)
    return _agent_plan_response(plan)


@router.post(
    "/{workflow_id}/agent-plans/{plan_id}/interrupt",
    response_model=WorkflowAgentPlanResponse,
)
def interrupt_agent_plan(
    workflow_id: int,
    plan_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    plan = _get_agent_plan_or_404(db, workflow_id=workflow.id, plan_id=plan_id)
    if plan.status == "rejected":
        raise HTTPException(
            status_code=400, detail="Rejected plans cannot be interrupted"
        )
    plan.status = "interrupted"
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="user",
        event_type="agent.plan_interrupted",
        stage=workflow.stage,
        summary=f"Interrupted bounded agent plan: {plan.title}",
        payload={"plan_id": plan.id},
        commit=False,
    )
    db.commit()
    db.refresh(plan)
    return _agent_plan_response(plan)


@router.post(
    "/{workflow_id}/agent-plans/{plan_id}/resume",
    response_model=WorkflowAgentPlanResponse,
)
def resume_agent_plan(
    workflow_id: int,
    plan_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    plan = _get_agent_plan_or_404(db, workflow_id=workflow.id, plan_id=plan_id)
    if plan.status != "interrupted":
        raise HTTPException(
            status_code=400, detail="Only interrupted plans can be resumed"
        )
    plan.status = "approved" if plan.approval_status == "approved" else "draft"
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="user",
        event_type="agent.plan_resumed",
        stage=workflow.stage,
        summary=f"Resumed bounded agent plan: {plan.title}",
        payload={"plan_id": plan.id},
        commit=False,
    )
    db.commit()
    db.refresh(plan)
    return _agent_plan_response(plan)


@router.post(
    "/{workflow_id}/agent-plans/{plan_id}/steps/{step_id}/approve",
    response_model=WorkflowAgentStepResponse,
)
def approve_agent_plan_step(
    workflow_id: int,
    plan_id: int,
    step_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    plan = _get_agent_plan_or_404(db, workflow_id=workflow.id, plan_id=plan_id)
    step = _get_agent_step_or_404(db, plan_id=plan.id, step_id=step_id)
    if not step.requires_approval:
        raise HTTPException(
            status_code=400, detail="This step does not require approval"
        )
    if step.status == "completed":
        raise HTTPException(
            status_code=400, detail="Completed steps cannot be approved"
        )
    step.status = "approved"
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="user",
        event_type="agent.plan_step_approved",
        stage=workflow.stage,
        summary=f"Approved plan step: {step.action}",
        payload={"plan_id": plan.id, "step_id": step.id, "action": step.action},
        commit=False,
    )
    db.commit()
    db.refresh(step)
    return _agent_step_response(step)


@router.post(
    "/{workflow_id}/agent-plans/{plan_id}/steps/{step_id}/complete",
    response_model=WorkflowAgentStepResponse,
)
def complete_agent_plan_step(
    workflow_id: int,
    plan_id: int,
    step_id: int,
    body: WorkflowAgentStepCompleteRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    plan = _get_agent_plan_or_404(db, workflow_id=workflow.id, plan_id=plan_id)
    step = _get_agent_step_or_404(db, plan_id=plan.id, step_id=step_id)
    if body.status not in {"completed", "failed", "skipped"}:
        raise HTTPException(
            status_code=400,
            detail="status must be one of: completed, failed, skipped",
        )
    step.status = body.status
    step.result_json = encode_json(body.result)
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="system",
        event_type=f"agent.plan_step_{body.status}",
        stage=workflow.stage,
        summary=f"Plan step {body.status}: {step.action}",
        payload={
            "plan_id": plan.id,
            "step_id": step.id,
            "action": step.action,
            "result": body.result,
        },
        commit=False,
    )
    db.commit()
    db.refresh(step)
    return _agent_step_response(step)


@router.post(
    "/{workflow_id}/export-bundle",
    response_model=WorkflowExportBundleResponse,
)
def export_workflow_bundle(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    events = _event_rows(db, workflow.id)
    bundle = build_export_bundle(workflow, events)
    bundle = write_export_bundle_directory(bundle)
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="system",
        event_type="workflow.bundle_exported",
        stage=workflow.stage,
        summary="Exported workflow evidence bundle.",
        payload={
            "artifact_count": len(bundle.get("artifacts") or []),
            "model_run_count": len(bundle.get("model_runs") or []),
            "model_version_count": len(bundle.get("model_versions") or []),
            "correction_set_count": len(bundle.get("correction_sets") or []),
            "evaluation_result_count": len(bundle.get("evaluation_results") or []),
            "bundle_directory": bundle.get("bundle_directory"),
            "bundle_manifest_path": bundle.get("bundle_manifest_path"),
            "copied_artifact_count": len(bundle.get("copied_artifacts") or []),
            "skipped_artifact_count": len(bundle.get("skipped_artifacts") or []),
            "missing_artifact_path_count": len(
                [
                    path_info
                    for path_info in bundle.get("artifact_paths") or []
                    if not path_info.get("exists")
                ]
            ),
        },
        commit=True,
    )
    return WorkflowExportBundleResponse(**bundle)


@router.post("/{workflow_id}/events", response_model=WorkflowEventResponse)
async def create_workflow_event(
    workflow_id: int,
    body: WorkflowEventCreateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    stage = validate_stage(body.stage or workflow.stage)
    event = append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor=body.actor,
        event_type=body.event_type,
        stage=stage,
        summary=body.summary,
        payload=body.payload,
        schema_version=body.schema_version,
        idempotency_key=body.idempotency_key,
        approval_status=body.approval_status,
        commit=True,
    )
    return _event_response(event)


@router.post("/{workflow_id}/agent-actions", response_model=WorkflowEventResponse)
async def create_agent_action(
    workflow_id: int,
    body: AgentActionCreateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    summary = body.summary or f"Agent proposed: {body.action}"
    event = append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="agent",
        event_type="agent.proposal_created",
        stage=workflow.stage,
        summary=summary,
        payload={"action": body.action, "params": body.payload},
        approval_status="pending",
        commit=True,
    )
    return _event_response(event)


@router.post(
    "/{workflow_id}/agent-actions/{event_id}/approve",
    response_model=AgentActionResult,
)
async def approve_agent_action(
    workflow_id: int,
    event_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    proposal = _get_pending_proposal_or_404(
        db, workflow_id=workflow.id, event_id=event_id
    )
    action_payload = _proposal_action_payload(proposal)
    action = action_payload.get("action")
    params = action_payload.get("params", {})

    if action not in {
        "stage_retraining_from_corrections",
        "start_training_run",
        "run_client_effects",
    }:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

    if action == "start_training_run":
        client_effects = _training_run_effects_from_proposal(workflow, params)
        corrected_mask_path = (
            client_effects.get("set_training_label_path")
            or params.get("label_path")
            or workflow.corrected_mask_path
            or workflow.label_path
            or workflow.mask_path
            or _latest_exported_mask_path(db, workflow.id)
        )
        proposal.approval_status = "approved"
        update_payload: Dict[str, Any] = {"stage": "retraining_staged"}
        if corrected_mask_path:
            update_payload["corrected_mask_path"] = corrected_mask_path
        if client_effects.get("set_training_output_path"):
            update_payload["training_output_path"] = client_effects[
                "set_training_output_path"
            ]
        update_workflow_fields(db, workflow, update_payload, commit=False)
        db.commit()
        db.refresh(workflow)
        db.refresh(proposal)

        approved = append_workflow_event(
            db,
            workflow_id=workflow.id,
            actor="user",
            event_type="agent.proposal_approved",
            stage=workflow.stage,
            summary=f"Approved agent proposal: {proposal.summary}",
            payload={"proposal_event_id": proposal.id, "action": action},
            commit=True,
        )
        staged = append_workflow_event(
            db,
            workflow_id=workflow.id,
            actor="system",
            event_type="training.run_approved",
            stage=workflow.stage,
            summary="Training run approved from chat.",
            payload={
                "proposal_event_id": proposal.id,
                "config_preset": client_effects.get("set_training_config_preset"),
                "image_path": client_effects.get("set_training_image_path"),
                "label_path": client_effects.get("set_training_label_path"),
                "output_path": client_effects.get("set_training_output_path"),
                "runtime_action": client_effects.get("runtime_action"),
            },
            commit=True,
        )
        command = create_workflow_command(
            db,
            workflow_id=workflow.id,
            command_type="start_training",
            idempotency_key=f"agent-proposal:{proposal.id}:start_training",
            actor="agent",
            source_event_id=proposal.id,
            approval_event_id=approved.id,
            input_payload={
                "client_effects": client_effects,
                "workflow_stage": workflow.stage,
                "proposal_event_id": proposal.id,
            },
            commit=True,
        )
        return AgentActionResult(
            workflow=_workflow_response(workflow),
            proposal=_event_response(proposal),
            events=[_event_response(approved), _event_response(staged)],
            client_effects={**client_effects, "workflow_stage": workflow.stage},
            commands=[_command_response(command)],
        )

    if action == "run_client_effects":
        client_effects = params.get("client_effects")
        if not isinstance(client_effects, dict) or not client_effects:
            raise HTTPException(
                status_code=400,
                detail="Approved client-effect action is missing client_effects.",
            )
        proposal.approval_status = "approved"
        db.commit()
        db.refresh(proposal)

        approved = append_workflow_event(
            db,
            workflow_id=workflow.id,
            actor="user",
            event_type="agent.proposal_approved",
            stage=workflow.stage,
            summary=f"Approved agent proposal: {proposal.summary}",
            payload={"proposal_event_id": proposal.id, "action": action},
            commit=True,
        )
        staged = append_workflow_event(
            db,
            workflow_id=workflow.id,
            actor="system",
            event_type="agent.client_effects_approved",
            stage=workflow.stage,
            summary="Approved in-app assistant action for client execution.",
            payload={
                "proposal_event_id": proposal.id,
                "item_id": params.get("item_id"),
                "item_label": params.get("item_label"),
                "risk_level": params.get("risk_level"),
                "runtime_action": client_effects.get("runtime_action"),
                "workflow_action": client_effects.get("workflow_action"),
            },
            commit=True,
        )
        return AgentActionResult(
            workflow=_workflow_response(workflow),
            proposal=_event_response(proposal),
            events=[_event_response(approved), _event_response(staged)],
            client_effects={**client_effects, "workflow_stage": workflow.stage},
            commands=[],
        )

    corrected_mask_path = (
        params.get("corrected_mask_path")
        or params.get("written_path")
        or workflow.corrected_mask_path
        or _latest_exported_mask_path(db, workflow.id)
    )
    if not corrected_mask_path:
        raise HTTPException(
            status_code=400,
            detail="No corrected mask artifact is available to stage for retraining.",
        )

    proposal.approval_status = "approved"
    update_workflow_fields(
        db,
        workflow,
        {
            "stage": "retraining_staged",
            "corrected_mask_path": corrected_mask_path,
            "training_output_path": params.get("training_output_path")
            or workflow.training_output_path,
        },
        commit=False,
    )
    db.commit()
    db.refresh(workflow)
    db.refresh(proposal)

    approved = append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="user",
        event_type="agent.proposal_approved",
        stage=workflow.stage,
        summary=f"Approved agent proposal: {proposal.summary}",
        payload={"proposal_event_id": proposal.id, "action": action},
        commit=True,
    )
    staged = append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="system",
        event_type="retraining.staged",
        stage=workflow.stage,
        summary="Corrected masks staged for retraining.",
        payload={
            "corrected_mask_path": corrected_mask_path,
            "source": "agent_action",
            "proposal_event_id": proposal.id,
        },
        commit=True,
    )
    return AgentActionResult(
        workflow=_workflow_response(workflow),
        proposal=_event_response(proposal),
        events=[_event_response(approved), _event_response(staged)],
        client_effects={
            "navigate_to": "training",
            "set_training_label_path": corrected_mask_path,
            "workflow_stage": workflow.stage,
        },
    )


@router.post(
    "/{workflow_id}/agent-actions/{event_id}/reject",
    response_model=WorkflowEventResponse,
)
async def reject_agent_action(
    workflow_id: int,
    event_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    proposal = _get_pending_proposal_or_404(
        db, workflow_id=workflow.id, event_id=event_id
    )
    proposal.approval_status = "rejected"
    db.commit()
    db.refresh(proposal)
    event = append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="user",
        event_type="agent.proposal_rejected",
        stage=workflow.stage,
        summary=f"Rejected agent proposal: {proposal.summary}",
        payload={"proposal_event_id": proposal.id},
        commit=True,
    )
    return _event_response(event)


def _workflow_agent_conversation_for_query(
    db: Session,
    *,
    user_id: int,
    conversation_id: Optional[int],
    query: str,
) -> auth_models.Conversation:
    if conversation_id:
        conversation = (
            db.query(auth_models.Conversation)
            .filter(
                auth_models.Conversation.id == conversation_id,
                auth_models.Conversation.user_id == user_id,
            )
            .first()
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.title == "New Chat":
            conversation.title = query[:120].strip() or "Workflow assistant"
        return conversation

    conversation = auth_models.Conversation(
        user_id=user_id,
        title=query[:120].strip() or "Workflow assistant",
    )
    db.add(conversation)
    db.flush()
    return conversation


def _jsonable_agent_items(items: List[Any]) -> str:
    encoded_items = []
    for item in items:
        if hasattr(item, "model_dump"):
            encoded_items.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            encoded_items.append(item)
    return json.dumps(encoded_items)


def _persist_workflow_agent_chat_exchange(
    db: Session,
    *,
    workflow_id: int,
    conversation: auth_models.Conversation,
    query: str,
    response: str,
    actions: List[AgentChatAction],
    commands: List[AgentCommandBlock],
    proposals: List[WorkflowEventResponse],
    trace: List[AgentTraceItem],
) -> None:
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(
        auth_models.ChatMessage(
            conversation_id=conversation.id,
            workflow_id=workflow_id,
            role="user",
            content=query,
        )
    )
    db.add(
        auth_models.ChatMessage(
            conversation_id=conversation.id,
            workflow_id=workflow_id,
            role="assistant",
            content=response,
            source="workflow_orchestrator",
            actions_json=_jsonable_agent_items(actions),
            commands_json=_jsonable_agent_items(commands),
            proposals_json=_jsonable_agent_items(proposals),
            trace_json=_jsonable_agent_items(trace),
        )
    )


@router.post("/{workflow_id}/agent/query", response_model=AgentQueryResponse)
async def query_workflow_agent(
    workflow_id: int,
    body: AgentQueryRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_query = body.query.strip()
    if not raw_query:
        raise HTTPException(status_code=400, detail="query must be non-empty")
    query, command_alias = _normalize_workflow_agent_query(raw_query)

    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    conversation = _workflow_agent_conversation_for_query(
        db,
        user_id=user.id,
        conversation_id=body.conversation_id or body.conversationId,
        query=raw_query,
    )
    event_rows = _event_rows(db, workflow.id)
    agent_recommendation = _build_workflow_agent_recommendation(db, workflow)
    proposals: List[WorkflowEventResponse] = []
    actions: List[AgentChatAction] = []
    commands: List[AgentCommandBlock] = []
    tasks = _workflow_agent_tasks_from_readiness(agent_recommendation.readiness)
    intent = "recommendation"
    lower_query = query.lower()
    project_observation = _observe_workflow_project(db, workflow, user.id)
    semantic_intent = (
        {}
        if command_alias
        else _semantic_intent_payload(query, workflow)
    )
    semantic_name = semantic_intent.get("intent")
    semantic_tab = semantic_intent.get("tab")
    wants_greeting = _is_greeting_query(lower_query) or semantic_name == "greeting"
    wants_style_feedback = _query_has(
        lower_query,
        [
            "robotic",
            "less robot",
            "less robotic",
            "too formal",
            "more human",
            "normal chatbot",
            "normal human",
            "sound human",
            "frontfacing language",
            "front-facing language",
            "stiff response",
            "stiff",
        ],
    ) or semantic_name == "style_feedback"
    wants_repair = _is_repair_query(lower_query) or semantic_name == "repair"
    wants_informational_followup = _query_is_informational_followup(lower_query)
    wants_incomplete_intent = (
        _is_incomplete_work_intent(lower_query)
        or semantic_name == "clarify_next_job"
    )
    target_tab = _target_tab_from_query(lower_query) or _target_tab_from_semantic(
        semantic_name,
        semantic_tab,
    )
    wants_capabilities = any(
        phrase in lower_query
        for phrase in [
            "what can you do",
            "what can the agent do",
            "what can the assistant do",
            "what can it do",
            "help me through",
            "run things",
            "guide me",
        ]
    ) or semantic_name == "capabilities"
    wants_project_context = any(
        phrase in lower_query
        for phrase in [
            "what project",
            "which project",
            "current project",
            "project am i",
            "project i am",
            "what data",
            "what dataset",
            "what volume",
        ]
    ) or semantic_name == "project_context"
    wants_project_files = (
        _query_wants_project_file_overview(lower_query)
        or semantic_name == "project_files"
    )
    wants_project_progress = _query_has(
        lower_query,
        [
            "project progress",
            "progress tracker",
            "project tracker",
            "project manager",
            "volume tracker",
            "open progress",
            "show progress",
            "how many volumes",
            "volumes are done",
            "volumes are fully good",
            "fully proofread",
            "ground truth",
            "ground-truth",
            "unproofread",
            "without segmentation",
            "no segmentation",
            "missing segmentation",
        ],
    ) or semantic_name == "project_progress"
    wants_user_need = any(
        phrase in lower_query
        for phrase in [
            "what do you need",
            "what you need",
            "need from me",
            "need me to",
            "what should i provide",
            "what should i do for you",
        ]
    ) or semantic_name == "needed_from_user"
    wants_status = _query_has(
        lower_query,
        [
            "status",
            "where am i",
            "what now",
            "what's next",
            "next step",
            "what should i do",
            "what is left",
            "what remains",
            "missing",
            "blocker",
            "ready",
        ],
    ) or semantic_name == "status"
    wants_evaluation = _query_has(
        lower_query,
        [
            "evaluate",
            "evaluation",
            "compare",
            "comparison",
            "metric",
            "metrics",
            "dice",
            "iou",
            "before after",
            "before/after",
        ],
    ) or semantic_name == "compute_evaluation"
    wants_export = _query_has(
        lower_query,
        [
            "export bundle",
            "export evidence",
            "export report",
            "evidence bundle",
            "research bundle",
            "download bundle",
        ],
    ) or semantic_name == "export_evidence"
    wants_visualization_launch = (
        _query_wants_visualization_launch(lower_query)
        or semantic_name == "view_data"
    )
    wants_alternate_volume_set = _query_wants_alternate_volume_set(lower_query)
    if wants_alternate_volume_set:
        wants_visualization_launch = True
    wants_visualization_scales = (
        _query_wants_visualization_scales(lower_query)
        or semantic_name == "set_visualization_scales"
    )
    wants_retraining = any(
        term in lower_query for term in ["retrain", "training", "stage", "corrected"]
    ) or semantic_name == "stage_retraining"
    wants_training_launch = _query_has(
        lower_query,
        [
            "train",
            "start training",
            "run training",
            "launch training",
            "retrain now",
            "train model",
            "train a model",
            "train the model",
            "train for me",
            "train on saved edits",
            "run a training job",
            "run training job",
        ],
    ) or semantic_name == "start_training"
    wants_inference_launch = (
        _query_wants_inference_launch(lower_query)
        or semantic_name == "start_inference"
    )
    wants_segmentation_launch = (
        _query_wants_segmentation_launch(lower_query)
        or semantic_name == "start_segmentation"
    )
    if wants_visualization_launch and semantic_name != "start_segmentation":
        wants_segmentation_launch = False
        wants_inference_launch = False
    if wants_alternate_volume_set:
        wants_segmentation_launch = False
        wants_inference_launch = False
        wants_training_launch = False
    if wants_segmentation_launch and semantic_name != "start_inference":
        wants_inference_launch = False
    wants_progress_based_training = wants_training_launch and (
        _query_wants_progress_based_training(lower_query)
        or _query_wants_segment_remaining_after_training(lower_query)
    )
    if wants_training_launch:
        wants_project_progress = False
    wants_proofreading_launch = _query_has(
        lower_query,
        [
            "proofread",
            "proofreading",
            "review mask",
            "review masks",
            "review segmentation",
            "review segmentations",
            "fix mask",
            "fix masks",
            "fix segmentation",
            "inspect segmentation",
            "check segmentation",
            "check segmentations",
            "curate segmentation",
            "curate segmentations",
            "human review",
        ],
    ) or semantic_name == "start_proofreading"
    wants_failure_analysis = any(
        term in lower_query for term in ["fail", "failure", "error", "hotspot", "where"]
    ) or semantic_name == "inspect_failure"
    wants_mount_project = _query_has(
        lower_query,
        [
            "mount project",
            "remount",
            "remount project",
            "open project",
            "use suggested project",
            "mount lucchi",
            "open lucchi",
            "prepilot lucchi",
            "lucchi directory",
            "project directory",
        ],
    ) or semantic_name == "mount_project"
    wants_reset_workspace = _query_has(
        lower_query,
        [
            "reset workspace",
            "clear workspace",
            "clear cache",
            "reset cache",
            "clear cached",
            "reset cached",
            "clean state",
            "fresh state",
            "start over",
            "new workflow",
        ],
    ) or semantic_name == "reset_workspace"
    if wants_reset_workspace:
        wants_mount_project = False
    wants_validate_project = _query_has(
        lower_query,
        [
            "validate project",
            "check project",
            "inspect project",
            "project structure",
            "detect roles",
            "role mapping",
            "what files",
            "what volumes",
        ],
    ) or semantic_name == "validate_project"
    if wants_project_files and semantic_name != "validate_project":
        wants_validate_project = False
    wants_prepare_data = _query_has(
        lower_query,
        [
            "prepare data",
            "convert data",
            "normalize",
            "normalise",
            "crop",
            "downsample",
            "split train",
            "train val split",
            "preprocess",
            "pre-process",
        ],
    ) or semantic_name == "prepare_data"
    wants_configure_training = _query_has(
        lower_query,
        [
            "configure training",
            "training settings",
            "training config",
            "batch size",
            "augmentation",
            "epochs",
            "learning rate",
            "pick architecture",
        ],
    ) or semantic_name == "configure_training"
    wants_configure_inference = _query_has(
        lower_query,
        [
            "configure inference",
            "inference settings",
            "inference config",
            "tiling",
            "threshold",
            "checkpoint",
            "set checkpoint",
        ],
    ) or semantic_name == "configure_inference"
    wants_monitor_jobs = _query_has(
        lower_query,
        [
            "monitor",
            "logs",
            "tensorboard",
            "job status",
            "runtime status",
            "gpu",
            "memory",
            "training log",
        ],
    ) or semantic_name == "monitor_jobs"
    wants_stop_runtime = _query_has(
        lower_query,
        [
            "stop",
            "cancel",
            "kill",
            "stop run",
            "stop job",
            "cancel run",
            "cancel job",
            "kill run",
            "kill job",
            "stop training",
            "stop inference",
            "cancel training",
            "cancel inference",
        ],
    ) or semantic_name == "stop_runtime"
    wants_use_defaults = any(
        phrase in lower_query
        for phrase in [
            "use defaults",
            "use safe defaults",
            "default settings",
            "safe defaults",
        ]
    )
    action_needs_context = (
        wants_training_launch or wants_inference_launch or wants_segmentation_launch
    )
    workflow_action_requested = any(
        [
            action_needs_context,
            wants_visualization_launch,
            wants_visualization_scales,
            wants_proofreading_launch,
            wants_evaluation,
            wants_export,
            wants_status,
            wants_capabilities,
            wants_project_context,
            wants_project_files,
            wants_project_progress,
            wants_user_need,
            wants_incomplete_intent,
            wants_failure_analysis,
            wants_mount_project,
            wants_reset_workspace,
            wants_validate_project,
            wants_prepare_data,
            wants_configure_training,
            wants_configure_inference,
            wants_monitor_jobs,
            wants_stop_runtime,
            bool(target_tab),
        ]
    )
    context_update = {
        **_extract_project_context_from_query(query),
        **(semantic_intent.get("context") or {}),
    }
    if wants_use_defaults:
        context_update = {
            **context_update,
            "use_defaults": True,
            "freeform_note": query[:500],
        }
    context_should_update = bool(context_update) and (
        not command_alias
    )
    if context_should_update:
        _merge_project_context(db, workflow, context_update)
    if wants_training_launch:
        context_action_label = "choose a training preset"
    elif wants_inference_launch or wants_segmentation_launch:
        context_action_label = "choose and run a segmentation model"
    else:
        context_action_label = "prioritize proofreading work"
    corrected_mask_path = workflow.corrected_mask_path or _latest_exported_mask_path(
        db, workflow.id
    )
    hotspots = _compute_hotspots(workflow, event_rows)
    impact = _compute_impact_preview(
        workflow,
        event_rows,
        hotspots,
        corrected_mask_path,
    )
    proofreading_blockers = _proofreading_input_blockers(workflow)

    if wants_visualization_scales:
        intent = "set_visualization_scales"
        parsed_scales = _parse_visualization_scales_from_query(query)
        if not parsed_scales:
            response = (
                "I can reload with new voxel scales, but I need three values in z,y,x.\n"
                "Example: reload with 1,1,1 nm."
            )
            actions = [
                _build_agent_chat_action(
                    "open-visualization",
                    "Open viewer",
                    "Open the visualization screen so you can set the voxel scales.",
                    variant="primary",
                    client_effects={"navigate_to": "visualization"},
                )
            ]
            commands = []
        else:
            _store_visualization_scales(
                db,
                workflow,
                parsed_scales,
                source_query=query,
            )
            scale_text = _format_scales(parsed_scales)
            view_effects = _build_view_data_effects(workflow)
            view_effects["set_visualization_scales"] = parsed_scales
            view_effects["runtime_action"] = {"kind": "load_visualization"}
            response = (
                f"Do this: reload the viewer with {scale_text} nm voxel scales.\n"
                "Why: I saved that z,y,x scale in project context for this workflow."
            )
            actions = [
                _build_agent_chat_action(
                    "reload-visualization-scales",
                    "Reload viewer",
                    f"Reload the current volume view with {scale_text} nm scales.",
                    variant="primary",
                    client_effects=view_effects,
                )
            ]
            if not workflow.image_path and not workflow.dataset_path:
                actions.append(
                    _build_agent_chat_action(
                        "choose-data",
                        "Choose data",
                        "Pick an image and mask before loading the viewer.",
                        client_effects=_build_choose_data_effects(),
                    )
                )
            commands = []
    elif (
        wants_informational_followup
        and not command_alias
        and not action_needs_context
        and not any(
            [
                wants_status,
                wants_style_feedback,
                wants_capabilities,
                wants_project_context,
                wants_project_files,
                wants_project_progress,
                wants_user_need,
                wants_visualization_launch,
                wants_visualization_scales,
                wants_evaluation,
                wants_export,
                wants_mount_project,
                wants_reset_workspace,
                wants_validate_project,
                wants_prepare_data,
                wants_configure_training,
                wants_configure_inference,
                wants_monitor_jobs,
                wants_stop_runtime,
            ]
        )
    ):
        intent = "project_context_updated" if context_should_update else "followup"
        response = (
            _format_project_context_saved_response(workflow, agent_recommendation)
            if context_should_update
            else _format_informational_followup_response(workflow, agent_recommendation)
        )
        actions = []
        commands = []
    elif action_needs_context and _project_context_missing_fields(workflow):
        intent = "collect_project_context"
        response = _format_project_context_prompt(workflow, context_action_label)
        actions = []
        commands = []
    elif context_should_update and not action_needs_context and not workflow_action_requested:
        intent = "project_context_updated"
        response = _format_project_context_saved_response(
            workflow,
            agent_recommendation,
        )
        actions = []
        commands = []
    elif wants_style_feedback:
        intent = "style_feedback"
        response = _format_style_feedback_response(workflow, agent_recommendation)
        actions = []
        commands = []
    elif wants_greeting:
        intent = "greeting"
        response = _format_greeting_response(agent_recommendation)
        actions = []
        commands = []
    elif wants_repair:
        intent = "repair"
        response = _format_repair_response(agent_recommendation)
        actions = []
        commands = []
    elif wants_mount_project:
        intent = "mount_project"
        effects = _build_mount_project_effects(
            directory_path=_derive_mount_project_path(workflow)
            or _default_mount_project_path(),
            mount_name=workflow.title,
        )
        response = (
            "Do this: mount the project directory.\n"
            "Why: remote browser access needs the server to mount the project path, then the app can inspect files and roles."
        )
        actions = [
            _build_agent_chat_action(
                "mount-project",
                "Mount project",
                "Mount the current or suggested server-side project directory.",
                variant="primary",
                client_effects=effects,
            ),
            _build_agent_chat_action(
                "open-files",
                "Open Files",
                "Inspect mounted project files.",
                client_effects={"navigate_to": "files"},
            ),
        ]
        commands = [
            _build_agent_command_block(
                "mount-project-command",
                "Mount project in app",
                "Mount the project directory from chat.",
                effects,
            )
        ]
    elif wants_reset_workspace:
        intent = "reset_workspace"
        effects = _build_mount_project_effects(
            directory_path=_derive_mount_project_path(workflow)
            or _default_mount_project_path(),
            mount_name=workflow.title,
        )
        effects["reset_workspace"] = True
        response = (
            "Do this: clear cached workspace file state, then remount the current project.\n"
            "Why: this resets stale client/file indexes while preserving the project directory on disk."
        )
        actions = [
            _build_agent_chat_action(
                "reset-workspace-remount-project",
                "Reset and remount",
                "Clear indexed workspace state and remount the current project directory.",
                variant="primary",
                client_effects=effects,
            ),
            _build_agent_chat_action(
                "show-status",
                "Show status",
                "Inspect workflow state after the reset.",
                client_effects={"show_workflow_context": True},
            ),
        ]
        commands = [
            _build_agent_command_block(
                "reset-workspace-remount-command",
                "Reset workspace in app",
                "Clear cached file state and remount the current project.",
                effects,
            )
        ]
    elif wants_validate_project:
        intent = "validate_project"
        response = (
            "Do this: inspect the mounted project and detected file roles.\n"
            "Why: project validation checks whether image, label/mask, config, checkpoint, and output paths are ready."
        )
        actions = [
            _build_agent_chat_action(
                "open-files",
                "Inspect files",
                "Open Files to review detected project structure and role mapping.",
                variant="primary",
                client_effects={"navigate_to": "files"},
            ),
            _build_agent_chat_action(
                "show-workflow-status",
                "Show status",
                "Open the workflow readiness panel.",
                client_effects={
                    "show_workflow_context": True,
                    "refresh_insights": True,
                },
            ),
        ]
        if workflow.image_path or workflow.dataset_path:
            actions.append(
                _build_agent_chat_action(
                    "open-visualization",
                    "View data",
                    "Open the detected image and mask pair.",
                    client_effects=_build_view_data_effects(workflow),
                )
            )
        commands = []
    elif wants_prepare_data:
        intent = "prepare_data"
        response = (
            "Do this: open Files and verify the data mapping before preprocessing.\n"
            "Why: conversion, cropping, normalization, and train/val splits need explicit source and output choices."
        )
        actions = [
            _build_agent_chat_action(
                "open-files",
                "Prepare data",
                "Open Files to choose sources and inspect project structure.",
                variant="primary",
                client_effects={"navigate_to": "files"},
            ),
            _build_agent_chat_action(
                "show-workflow-status",
                "Show status",
                "Show the current data readiness and blockers.",
                client_effects={
                    "show_workflow_context": True,
                    "refresh_insights": True,
                },
            ),
        ]
        commands = []
    elif wants_configure_training:
        intent = "configure_training"
        training_label_path = corrected_mask_path or workflow.label_path or workflow.mask_path
        effects = _build_start_training_effects(workflow, training_label_path)
        effects.pop("runtime_action", None)
        response = (
            "Do this: open training with inferred defaults filled in.\n"
            "Why: you can review config, image, labels, output, batch settings, and augmentation before launching."
        )
        actions = [
            _build_agent_chat_action(
                "configure-training",
                "Configure training",
                "Prefill training inputs and open the training screen without starting a job.",
                variant="primary",
                client_effects=effects,
            )
        ]
        commands = [
            _build_agent_command_block(
                "configure-training-command",
                "Configure training in app",
                "Open training with agent-inferred paths and preset.",
                effects,
            )
        ]
    elif wants_configure_inference:
        intent = "configure_inference"
        effects = _build_start_inference_effects(workflow)
        effects.pop("runtime_action", None)
        response = (
            "Do this: open Run Model with inferred inputs filled in.\n"
            "Why: you can review checkpoint, config, image, and output settings before launching inference."
        )
        actions = [
            _build_agent_chat_action(
                "configure-inference",
                "Configure inference",
                "Prefill inference settings and open Run Model without starting a job.",
                variant="primary",
                client_effects=effects,
            )
        ]
        commands = [
            _build_agent_command_block(
                "configure-inference-command",
                "Configure inference in app",
                "Open Run Model with agent-inferred paths and preset.",
                effects,
            )
        ]
    elif wants_monitor_jobs:
        intent = "monitor_jobs"
        response = (
            "Do this: open Monitor.\n"
            "Why: logs, TensorBoard, runtime status, and job health belong there."
        )
        actions = [
            _build_agent_chat_action(
                "open-monitoring",
                "Open Monitor",
                "Open runtime and training monitoring.",
                variant="primary",
                client_effects={"navigate_to": "monitoring"},
            ),
            _build_agent_chat_action(
                "show-status",
                "Show status",
                "Show workflow readiness and recent events.",
                client_effects={"show_workflow_context": True},
            ),
        ]
        commands = []
    elif wants_stop_runtime:
        intent = "stop_runtime"
        response = (
            "Do this: stop the active runtime.\n"
            "Why: stopping a run is explicit because it interrupts compute work."
        )
        actions = [
            _build_agent_chat_action(
                "stop-inference",
                "Stop inference",
                "Request cancellation of the current inference process.",
                variant="primary",
                client_effects={"runtime_action": {"kind": "stop_inference"}},
            ),
            _build_agent_chat_action(
                "stop-training",
                "Stop training",
                "Request cancellation of the current training process.",
                client_effects={"runtime_action": {"kind": "stop_training"}},
            ),
            _build_agent_chat_action(
                "open-monitoring",
                "Open Monitor",
                "Check runtime state after stopping.",
                client_effects={"navigate_to": "monitoring"},
            ),
        ]
        commands = []
    elif wants_project_progress:
        intent = "project_progress"
        progress = _build_workflow_project_progress(
            db,
            workflow,
            user_id=user.id,
            project_observation=project_observation,
        )
        response = _format_project_progress_response(progress)
        actions = [
            _build_agent_chat_action(
                "open-project-progress",
                "Open progress",
                "Open the project progress tracker for volume-level ground-truth status.",
                variant="primary",
                client_effects={
                    "navigate_to": "project-progress",
                    "refresh_project_progress": True,
                },
            )
        ]
        commands = []
    elif wants_project_files:
        intent = "project_files"
        response = _format_project_files_response(project_observation)
        actions = []
        commands = []
    elif wants_project_context:
        intent = "project_context"
        response = _format_project_context_response(workflow, agent_recommendation)
        actions = [
            _build_agent_chat_action(
                "show-workflow-status",
                "Show status",
                "Open the workflow evidence and readiness panel.",
                client_effects={
                    "show_workflow_context": True,
                    "refresh_insights": True,
                },
            )
        ]
        commands = []
    elif wants_user_need:
        intent = "needed_from_user"
        response = _format_needed_from_user_response(agent_recommendation)
        actions = agent_recommendation.actions[:2]
        commands = agent_recommendation.commands[:1]
    elif wants_incomplete_intent:
        intent = "clarify_next_job"
        response = (
            "Tell me what you want to do next.\n"
            "Options: run model, proofread, use edits for training, or compare results.\n"
            f"Current suggestion: {agent_recommendation.decision}"
        )
        actions = agent_recommendation.actions
        commands = []
    elif target_tab:
        intent = "navigate"
        navigation_action = _build_navigation_action(
            target_tab["tab"],
            target_tab["label"],
            target_tab["description"],
        )
        response = (
            f"Do this: {target_tab['label']}.\n" f"Why: {target_tab['description']}"
        )
        actions = [navigation_action]
        commands = [
            _build_agent_command_block(
                f"{navigation_action.id}-command",
                target_tab["label"],
                target_tab["description"],
                navigation_action.client_effects,
            )
        ]
    elif wants_export:
        intent = "export_evidence"
        export_effects = _build_export_bundle_effects()
        response = (
            "Do this: export the workflow evidence bundle.\n"
            "Why: it captures the current artifacts, runs, corrections, metrics, and audit trail."
        )
        actions = [
            _build_agent_chat_action(
                "export-workflow-bundle",
                "Export evidence",
                "Export the workflow evidence bundle.",
                variant="primary",
                client_effects=export_effects,
            ),
            _build_agent_chat_action(
                "show-status",
                "Show status",
                "Open the workflow evidence panel first.",
                client_effects={"show_workflow_context": True},
            ),
        ]
        commands = [
            _build_agent_command_block(
                "export-workflow-bundle-command",
                "Export evidence in app",
                "Run this in-app command block to export the workflow evidence bundle.",
                export_effects,
            )
        ]
    elif wants_evaluation:
        intent = "compute_evaluation"
        evaluation_effects, missing_eval_inputs = _build_compute_evaluation_effects(
            db, workflow
        )
        if missing_eval_inputs:
            response = (
                f"Do this: collect {missing_eval_inputs[0]} first.\n"
                "Why: before/after metrics need a previous result, a new result, and a reference mask."
            )
            actions = [
                _build_agent_chat_action(
                    "show-evaluation-status",
                    "Show status",
                    "Open the evidence panel and inspect missing comparison inputs.",
                    variant="primary",
                    client_effects={"show_workflow_context": True},
                ),
                _build_agent_chat_action(
                    "open-inference",
                    "Open Run Model",
                    "Run or register model outputs for comparison.",
                    client_effects={"navigate_to": "inference"},
                ),
            ]
            commands = []
        else:
            response = (
                "Do this: compute before/after metrics.\n"
                "Why: this checks whether the new result improved against the reference mask."
            )
            actions = [
                _build_agent_chat_action(
                    "compute-evaluation",
                    "Compute metrics",
                    "Compare the previous and new segmentation results.",
                    variant="primary",
                    client_effects=evaluation_effects,
                ),
                _build_agent_chat_action(
                    "export-workflow-bundle",
                    "Export evidence",
                    "Export the workflow evidence bundle after metrics are recorded.",
                    client_effects=_build_export_bundle_effects(),
                ),
            ]
            commands = [
                _build_agent_command_block(
                    "compute-evaluation-command",
                    "Compute metrics in app",
                    "Run this in-app command block to compute before/after metrics.",
                    evaluation_effects,
                )
            ]
    elif wants_visualization_launch:
        intent = "view_data"
        observed_volume_set = _select_observed_volume_set(
            project_observation,
            prefer_alternate=wants_alternate_volume_set,
        )
        image_path = workflow.image_path or workflow.dataset_path or ""
        label_path = (
            workflow.label_path
            or workflow.mask_path
            or workflow.inference_output_path
            or workflow.corrected_mask_path
            or ""
        )
        if observed_volume_set and (
            wants_alternate_volume_set or not image_path
        ):
            image_path = observed_volume_set.get("image_path") or image_path
            label_path = observed_volume_set.get("label_path") or label_path
        if not image_path:
            response = (
                "I can visualize this, but I need the image volume first.\n"
                "Do this: confirm the image and mask/label paths in Files."
            )
            actions = [
                _build_agent_chat_action(
                    "open-files",
                    "Choose data",
                    "Confirm the image and mask/label paths before viewing.",
                    variant="primary",
                    client_effects=_build_choose_data_effects(),
                )
            ]
            commands = []
        else:
            pair_discovery = _workflow_volume_pair_discovery(workflow)
            detected_pairs = pair_discovery.get("pairs") or []
            selected_pair = detected_pairs[0] if detected_pairs else None
            selected_image_path = image_path
            selected_label_path = label_path
            if observed_volume_set and (
                wants_alternate_volume_set or not selected_pair
            ):
                selected_image_path = (
                    observed_volume_set.get("image_path") or selected_image_path
                )
                selected_label_path = (
                    observed_volume_set.get("label_path") or selected_label_path
                )
            elif selected_pair:
                selected_image_path = selected_pair.get("image_path") or image_path
                selected_label_path = selected_pair.get("label_path") or label_path
            view_effects = _build_view_data_effects(
                workflow,
                image_path=selected_image_path,
                label_path=selected_label_path,
            )
            observed_set_count = len(project_observation.get("volume_sets") or [])
            pair_count = int(pair_discovery.get("pair_count") or 0)
            if observed_volume_set:
                pair_count = max(pair_count, int(observed_volume_set.get("pair_count") or 0))
            pair_line = ""
            if wants_alternate_volume_set and observed_volume_set:
                pair_line = (
                    f"\nI inspected the project tree and found another image/seg set: "
                    f"{observed_volume_set.get('name') or 'volume set'} "
                    f"({observed_volume_set.get('image_count') or 0} images, "
                    f"{observed_volume_set.get('label_count') or 0} labels"
                    f"{'; ' + str(observed_volume_set.get('pair_count')) + ' matched pairs' if observed_volume_set.get('pair_count') else ''})."
                )
            elif observed_set_count > 1:
                pair_line = (
                    f"\nI inspected the project tree and found {observed_set_count} image/seg sets. "
                    f"I will open {observed_volume_set.get('name') if observed_volume_set else 'the current set'} first."
                )
            elif pair_count > 1:
                pair_line = (
                    f"\nI found {pair_count} clear image/seg pairs and will open "
                    f"{_short_path_label(selected_image_path)} first. "
                    "Tell me if there are more folders or pairs I should include."
                )
            elif pair_count == 1:
                pair_line = (
                    f"\nI found one clear image/seg pair: "
                    f"{_short_path_label(selected_image_path)}"
                    f"{' with ' + _short_path_label(selected_label_path) if selected_label_path else ''}."
                )
            response = (
                f"Do this: view {_short_path_label(selected_image_path)}"
                f"{' with ' + _short_path_label(selected_label_path) if selected_label_path else ''}.\n"
                "Why: the workflow has a source volume"
                f"{' and a mask/label' if selected_label_path else ''} ready for inspection."
                f"{pair_line}"
            )
            actions = [
                _build_agent_chat_action(
                    "open-visualization",
                    "View data",
                    "Open the selected image and mask in the viewer.",
                    variant="primary",
                    client_effects=view_effects,
                )
            ]
            if not proofreading_blockers:
                actions.append(_build_proofreading_action(workflow, variant="default"))
            commands = []
    elif wants_status and not (
        wants_training_launch
        or wants_inference_launch
        or wants_segmentation_launch
        or wants_proofreading_launch
        or wants_visualization_launch
    ):
        intent = "status"
        response = _format_workflow_agent_response(agent_recommendation)
        actions = [
            _build_agent_chat_action(
                "show-workflow-status",
                "Show status",
                "Open the workflow evidence and readiness panel.",
                variant="primary",
                client_effects={
                    "show_workflow_context": True,
                    "refresh_insights": True,
                },
            ),
            *agent_recommendation.actions[:2],
        ]
        commands = []
    elif wants_capabilities:
        intent = "capabilities"
        response = _format_capabilities_response()
        actions = []
        commands = []
    elif wants_training_launch and workflow.stage == "retraining_staged":
        intent = "start_training"
        training_label_path = corrected_mask_path or workflow.label_path or workflow.mask_path
        subset_plan = None
        if wants_progress_based_training:
            progress = _build_workflow_project_progress(
                db,
                workflow,
                user_id=user.id,
                project_observation=project_observation,
            )
            subset_plan = _build_progress_training_subset_plan(
                workflow,
                progress,
                lower_query=lower_query,
            )
        training_effects = _build_start_training_effects(
            workflow,
            training_label_path,
            volume_subset_plan=subset_plan,
        )
        response = (
            _format_progress_training_response(
                subset_plan,
                include_segment_rest=_query_wants_segment_remaining_after_training(lower_query),
            )
            if subset_plan
            else (
                "Yes. I can train from the saved edits with the current image and mask paths. "
                "I’ll use the project config and safe defaults, then you can review the run before it launches."
            )
        )
        actions = [
            _build_agent_chat_action(
                "start-training",
                "Train on edits",
                "Start training with the selected labels and safe defaults.",
                variant="primary",
                client_effects=training_effects,
            ),
            _build_agent_chat_action(
                "refresh-insights",
                "Refresh",
                "Update the recommendation before training.",
                client_effects={"refresh_insights": True},
            ),
        ]
        commands = [
            _build_agent_command_block(
                "start-training-command",
                "Start training in app",
                "Review the proposed preset, inputs, and safe defaults before launching retraining from chat.",
                training_effects,
                run_label="Review run",
            )
        ]
    elif wants_training_launch:
        intent = "start_training"
        training_label_path = corrected_mask_path or workflow.label_path or workflow.mask_path
        image_path = workflow.image_path or workflow.dataset_path or ""
        if not image_path:
            response = (
                "I can train a model, but I need image data first.\n"
                "Do this: choose the project image and label folders in Files."
            )
            actions = [
                _build_agent_chat_action(
                    "open-files",
                    "Choose data",
                    "Select the image and label data needed for training.",
                    variant="primary",
                    client_effects=_build_choose_data_effects(),
                )
            ]
            commands = []
        elif not training_label_path:
            response = (
                "I can train a model, but I need labels or saved proofreading edits first.\n"
                "Do this: choose label data, proofread a mask, or run the model to create a prediction."
            )
            actions = [
                _build_agent_chat_action(
                    "open-files",
                    "Choose labels",
                    "Select label data or saved edits for training.",
                    variant="primary",
                    client_effects=_build_choose_data_effects(),
                ),
                _build_agent_chat_action(
                    "open-proofreading",
                    "Proofread",
                    "Create saved edits before training.",
                    client_effects={"navigate_to": "mask-proofreading"},
                ),
            ]
            commands = []
        else:
            subset_plan = None
            if wants_progress_based_training or project_observation.get("volume_sets"):
                progress = _build_workflow_project_progress(
                    db,
                    workflow,
                    user_id=user.id,
                    project_observation=project_observation,
                )
                subset_plan = _build_progress_training_subset_plan(
                    workflow,
                    progress,
                    lower_query=lower_query,
                )
            training_effects = _build_start_training_effects(
                workflow,
                training_label_path,
                volume_subset_plan=subset_plan,
            )
            response = (
                _format_progress_training_response(
                    subset_plan,
                    include_segment_rest=_query_wants_segment_remaining_after_training(lower_query),
                )
                if subset_plan
                else (
                    "Yes. I found image and label data, so I can train a model "
                    "with the project config and safe defaults. Review the inputs before it launches."
                )
            )
            actions = [
                _build_agent_chat_action(
                    "start-training",
                    "Train model",
                    "Start training with the current image and label data.",
                    variant="primary",
                    run_label="Review run",
                    client_effects=training_effects,
                )
            ]
            commands = [
                _build_agent_command_block(
                    "start-training-command",
                    "Start training in app",
                    "Review the proposed preset, inputs, and safe defaults before launching training from chat.",
                    training_effects,
                    run_label="Review run",
                )
            ]
    elif wants_inference_launch:
        intent = "start_inference"
        inference_blockers = _inference_input_blockers(workflow)
        if inference_blockers:
            missing = ", ".join(inference_blockers)
            response = (
                f"I can run a model, but I need {missing} first.\n"
                "Do this: confirm the input image and checkpoint, or use the existing labels for proofreading/training."
            )
            actions = [
                _build_agent_chat_action(
                    "open-inference",
                    "Check Run Model",
                    f"Inference needs {missing}.",
                    variant="primary",
                    client_effects={"navigate_to": "inference"},
                )
            ]
            if not (workflow.image_path or workflow.dataset_path):
                actions.append(
                    _build_agent_chat_action(
                        "open-files",
                        "Choose data",
                        "Pick an image volume before running a model.",
                        client_effects=_build_choose_data_effects(),
                    )
                )
            if not proofreading_blockers:
                actions.append(_build_proofreading_action(workflow, variant="default"))
            commands = []
        else:
            inference_effects = _build_start_inference_effects(workflow)
            response = (
                "Do this: run the model.\n"
                "Why: this creates the mask result you can inspect and fix."
            )
            actions = [
                _build_agent_chat_action(
                    "start-inference",
                    "Run model",
                    "Start the model run with the current settings.",
                    variant="primary",
                    client_effects=inference_effects,
                ),
                _build_agent_chat_action(
                    "start-proofreading",
                    "Proofread this data",
                    "Open the image and mask in the proofreading workbench.",
                    client_effects=_build_start_proofreading_effects(workflow),
                ),
            ]
            commands = [
                _build_agent_command_block(
                    "start-inference-command",
                    "Start inference in app",
                    "Run this in-app command block to launch inference from chat.",
                    inference_effects,
                )
            ]
    elif wants_proofreading_launch:
        intent = "start_proofreading"
        if proofreading_blockers:
            missing = ", ".join(proofreading_blockers)
            response = (
                f"I can proofread this, but I need {missing} first.\n"
                "Do this: confirm the image and mask/label paths in Files."
            )
            actions = [
                _build_agent_chat_action(
                    "open-files",
                    "Choose data",
                    f"Proofreading needs {missing}.",
                    variant="primary",
                    client_effects=_build_choose_data_effects(),
                )
            ]
            if "mask, label, or prediction" in proofreading_blockers:
                actions.append(
                    _build_agent_chat_action(
                        "open-inference",
                        "Run model",
                        "Create a prediction if no editable mask/label exists.",
                        client_effects={"navigate_to": "inference"},
                    )
                )
            commands = []
        else:
            proofreading_effects = _build_start_proofreading_effects(workflow)
            response = (
                "Do this: proofread this data.\n"
                "Why: I found the current image/mask paths in the workflow."
            )
            actions = [
                _build_proofreading_action(workflow, variant="primary"),
                _build_agent_chat_action(
                    "refresh-insights",
                    "Refresh",
                    "Update the recommendation using the latest edits.",
                    client_effects={"refresh_insights": True},
                ),
            ]
            commands = [
                _build_agent_command_block(
                    "start-proofreading-command",
                    "Start proofreading in app",
                    "Open the current image/mask pair in proofreading.",
                    proofreading_effects,
                )
            ]
    elif wants_segmentation_launch:
        intent = "start_segmentation"
        inference_blockers = _inference_input_blockers(workflow)
        if inference_blockers:
            missing = ", ".join(inference_blockers)
            response = (
                f"I can help segment this data, but running inference needs {missing}.\n"
                "Why: a checkpoint is required to produce a new model prediction. Useful next step: use the existing labels for proofreading or training, or add a checkpoint before running inference."
            )
            actions = []
            if not proofreading_blockers:
                actions.append(_build_proofreading_action(workflow, variant="primary"))
            training_label_path = (
                corrected_mask_path
                or workflow.label_path
                or workflow.mask_path
                or workflow.inference_output_path
            )
            if (workflow.image_path or workflow.dataset_path) and training_label_path:
                training_effects = _build_start_training_effects(
                    workflow,
                    training_label_path,
                )
                actions.append(
                    _build_agent_chat_action(
                        "start-training",
                        "Train model",
                        "Train from the current image and label data.",
                        client_effects=training_effects,
                    )
                )
            actions.append(
                _build_agent_chat_action(
                    "open-inference",
                    "Check Run Model",
                    f"Running segmentation needs {missing}.",
                    variant="primary" if not actions else "default",
                    client_effects={"navigate_to": "inference"},
                )
            )
            if not (workflow.image_path or workflow.dataset_path):
                actions.append(
                    _build_agent_chat_action(
                        "open-files",
                        "Choose data",
                        "Pick an image volume before segmenting.",
                        client_effects=_build_choose_data_effects(),
                    )
                )
            commands = []
        else:
            inference_effects = _build_start_inference_effects(workflow)
            proofreading_effects = _build_start_proofreading_effects(workflow)
            response = (
                "Do this: run the model to segment the volume.\n"
                "Why: inference creates the mask result; proofreading is for fixing it afterward."
            )
            actions = [
                _build_agent_chat_action(
                    "start-inference",
                    "Run model",
                    "Start segmentation from the current inference settings.",
                    variant="primary",
                    client_effects=inference_effects,
                ),
                _build_agent_chat_action(
                    "start-proofreading",
                    "Proofread this data",
                    "Open the current image/mask pair in proofreading.",
                    client_effects=proofreading_effects,
                ),
            ]
            commands = [
                _build_agent_command_block(
                    "start-segmentation-command",
                    "Run model in app",
                    "Run segmentation from chat using the current app settings.",
                    inference_effects,
                )
            ]
    elif wants_retraining and corrected_mask_path:
        intent = "stage_retraining"
        proposal = append_workflow_event(
            db,
            workflow_id=workflow.id,
            actor="agent",
            event_type="agent.proposal_created",
            stage=workflow.stage,
            summary="Stage corrected masks for retraining.",
            payload={
                "action": "stage_retraining_from_corrections",
                "params": {"corrected_mask_path": corrected_mask_path},
            },
            approval_status="pending",
            commit=True,
        )
        proposals.append(_event_response(proposal))
        response = (
            "Do this: approve using these edits for training.\n"
            "Why: I created a reviewable proposal instead of changing state silently."
        )
        training_effects = {
            "navigate_to": "training",
            "set_training_label_path": corrected_mask_path,
        }
        actions = [
            _build_agent_chat_action(
                "open-training",
                "Set up training",
                "Open training with the saved edits selected.",
                variant="primary",
                client_effects=training_effects,
            ),
            _build_agent_chat_action(
                "refresh-insights",
                "Refresh",
                "Update the recommendation before approving training.",
                client_effects={"refresh_insights": True},
            ),
        ]
        commands = [
            _build_agent_command_block(
                "prime-training",
                "Prime the training screen",
                "Run this in-app command block to move directly into the next training setup.",
                training_effects,
            )
        ]
    elif wants_failure_analysis and hotspots:
        intent = "inspect_failure"
        top_hotspot = hotspots[0]
        response = (
            f"Do this: {top_hotspot.recommended_action}\n"
            f"Why: {top_hotspot.summary}\n"
            f"Confidence: {impact.confidence}."
        )
        proofreading_effects = _build_start_proofreading_effects(workflow)
        visualization_effects = {"navigate_to": "visualization"}
        actions = [
            _build_agent_chat_action(
                "start-proofreading",
                "Proofread this data",
                "Open the image and mask in the proofreading workbench.",
                variant="primary",
                client_effects=proofreading_effects,
            ),
            _build_agent_chat_action(
                "open-visualization",
                "View data",
                "Inspect the region before editing.",
                client_effects=visualization_effects,
            ),
        ]
        commands = [
            _build_agent_command_block(
                "inspect-hotspot",
                "Inspect hotspot in app",
                "Run this in-app command block to pivot the UI into hotspot review mode.",
                proofreading_effects,
            )
        ]
    else:
        intent = "clarify_next_job"
        response = _format_unknown_workflow_query_response(agent_recommendation)
        actions = []
        commands = []

    actions, commands = _one_app_suggestion(actions, commands)
    response = _humanize_agent_response(response)
    trace = _build_agent_trace(
        workflow=workflow,
        project_observation=project_observation,
        intent=intent,
        actions=actions,
    )

    _persist_workflow_agent_chat_exchange(
        db,
        workflow_id=workflow.id,
        conversation=conversation,
        query=raw_query,
        response=response,
        actions=actions,
        commands=commands,
        proposals=proposals,
        trace=trace,
    )
    db.commit()
    append_app_event(
        component="workflow_agent",
        event="query_completed",
        level="INFO",
        message="Workflow agent query persisted",
        workflow_id=workflow.id,
        conversation_id=conversation.id,
        user_id=user.id,
        query_preview=raw_query[:160],
        normalized_query_preview=query[:160],
        command_alias=command_alias,
        query_len=len(query),
        response_len=len(response),
        response_source="workflow_orchestrator",
        intent=intent,
        semantic_intent=semantic_name,
        semantic_confidence=semantic_intent.get("confidence"),
        semantic_reason=semantic_intent.get("reason"),
        recommendation_decision=agent_recommendation.decision,
        recommendation_stage=agent_recommendation.next_stage,
        action_ids=[action.id for action in actions],
        action_labels=[action.label for action in actions],
        command_ids=[command.id for command in commands],
        command_titles=[command.title for command in commands],
        proofreading_blockers=proofreading_blockers,
        action_count=len(actions),
        command_count=len(commands),
        proposal_count=len(proposals),
        task_count=len(tasks),
        trace_count=len(trace),
    )

    return AgentQueryResponse(
        response=response,
        source="workflow_orchestrator",
        intent=intent,
        permission_mode="approval_required_for_runtime",
        conversation_id=conversation.id,
        conversationId=conversation.id,
        proposals=proposals,
        actions=actions,
        commands=commands,
        tasks=tasks,
        trace=trace,
    )
