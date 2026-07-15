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
    WorkflowVolumeState,
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
    volume_state_to_dict,
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


class AgentActionApprovalRequest(BaseModel):
    overrides: Dict[str, Any] = Field(default_factory=dict)


class AgentQueryRequest(BaseModel):
    query: str
    conversation_id: Optional[int] = None
    conversationId: Optional[int] = None


class AgentChatAction(BaseModel):
    id: str
    label: str
    description: str
    orchestrator_agent: Dict[str, Any] = Field(default_factory=dict)
    specialist_agent: Dict[str, Any] = Field(default_factory=dict)
    agent_type: str = "project_manager"
    agent_label: str = "Project Manager"
    agent_color: str = "#111827"
    agent_icon_key: str = "project"
    agent_border_style: str = "solid"
    action_type: str = "workflow_action"
    card_type: str = "workflow.action_card/v2"
    target: Optional[str] = None
    variant: str = "default"
    run_label: str = "Run in app"
    risk_level: str = "read_only"
    risk_tier: str = "R0_view"
    requires_approval: bool = False
    approval_reason: Optional[str] = None
    summary_fields: List[Dict[str, Any]] = Field(default_factory=list)
    input_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    output_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    expected_effects: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    action_card: Dict[str, Any] = Field(default_factory=dict)
    disabled_reason: Optional[str] = None
    client_effects: Dict[str, Any] = Field(default_factory=dict)
    policy_decision: Optional[Dict[str, Any]] = None
    blocking_reasons: List[Dict[str, Any]] = Field(default_factory=list)
    freshness: Dict[str, Any] = Field(default_factory=dict)


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
    category: str = "checked"
    agent_type: str = "project_manager"
    agent_label: str = "Project Manager"
    agent_color: str = "#111827"
    agent_icon_key: str = "project"
    agent_border_style: str = "solid"
    data: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)


class AgentQueryResponse(BaseModel):
    response: str
    source: str = "workflow_orchestrator"
    intent: str = "recommendation"
    permission_mode: str = "approval_required_for_runtime"
    orchestrator_agent: Dict[str, Any] = Field(default_factory=dict)
    subagents: List[Dict[str, Any]] = Field(default_factory=list)
    conversation_id: Optional[int] = None
    conversationId: Optional[int] = None
    proposals: List[WorkflowEventResponse] = Field(default_factory=list)
    actions: List[AgentChatAction] = Field(default_factory=list)
    commands: List[AgentCommandBlock] = Field(default_factory=list)
    tasks: List[AgentTaskItem] = Field(default_factory=list)
    policy_decision: Optional[Dict[str, Any]] = None
    blocking_reasons: List[Dict[str, Any]] = Field(default_factory=list)
    freshness: Optional[Dict[str, Any]] = None
    trace_schema_version: str = "agent_trace/v1"
    trace: List[AgentTraceItem] = Field(default_factory=list)


class AgentConversationMessage(BaseModel):
    id: int
    workflow_id: Optional[int] = None
    role: str
    content: str
    source: Optional[str] = None
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    commands: List[Dict[str, Any]] = Field(default_factory=list)
    proposals: List[Dict[str, Any]] = Field(default_factory=list)
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Any


class AgentConversationResponse(BaseModel):
    conversation_id: Optional[int] = None
    conversationId: Optional[int] = None
    title: Optional[str] = None
    messages: List[AgentConversationMessage] = Field(default_factory=list)


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
    policy_decision: Optional[Dict[str, Any]] = None
    blocking_reasons: List[Dict[str, Any]] = Field(default_factory=list)
    freshness: Dict[str, Any] = Field(default_factory=dict)


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
    legacy_status: Optional[str] = None
    canonical_status: Optional[str] = None
    canonical_status_label: Optional[str] = None
    annotation_state: Optional[str] = None
    annotation_state_label: Optional[str] = None
    role_state: Optional[str] = None
    role_state_label: Optional[str] = None
    execution_state: Optional[str] = None
    execution_state_label: Optional[str] = None
    region_scope: Dict[str, Any] = Field(default_factory=dict)
    state_schema_version: Optional[str] = None
    status_source: str
    volume_state_id: Optional[int] = None
    project_root: Optional[str] = None
    volume_set_id: Optional[str] = None
    volume_set_name: Optional[str] = None
    image_path: Optional[str] = None
    segmentation_path: Optional[str] = None
    segmentation_kind: Optional[str] = None
    eligible_for_training: bool = False
    eligible_for_inference: bool = False
    evidence: List[str] = Field(default_factory=list)
    note: Optional[str] = None


class WorkflowProjectProgressResponse(BaseModel):
    workflow_id: int
    generated_at: str
    project_name: Optional[str] = None
    project_roots: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    status_definitions: Dict[str, str] = Field(default_factory=dict)
    composite_state_definitions: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    volumes: List[WorkflowProjectProgressVolume] = Field(default_factory=list)


class WorkflowProjectProgressVolumeUpdate(BaseModel):
    volume_id: str
    status: Optional[str] = None
    note: Optional[str] = None


class WorkflowOverviewStage(BaseModel):
    id: str
    label: str
    target_view: str
    complete: bool = False
    current: bool = False
    blocked: bool = False
    detail: Optional[str] = None


class WorkflowOverviewBlocker(BaseModel):
    id: str
    label: str
    detail: str
    severity: str = "warning"
    target_view: Optional[str] = None


class WorkflowOverviewAction(BaseModel):
    id: str
    label: str
    detail: str
    target_view: str
    priority: str = "normal"
    client_effects: Dict[str, Any] = Field(default_factory=dict)


class WorkflowOverviewRun(BaseModel):
    id: int
    run_id: Optional[str] = None
    run_type: str
    status: str
    output_path: Optional[str] = None
    checkpoint_path: Optional[str] = None
    summary: Optional[str] = None
    started_at: Any = None
    completed_at: Any = None
    updated_at: Any = None


class WorkflowOverviewResponse(BaseModel):
    workflow_id: int
    generated_at: str
    project_name: Optional[str] = None
    workflow_stage: str
    phase: str
    phase_label: str
    phase_reason: str
    phase_index: int
    volume_summary: Dict[str, Any] = Field(default_factory=dict)
    project_progress: Optional[WorkflowProjectProgressResponse] = None
    stages: List[WorkflowOverviewStage] = Field(default_factory=list)
    blockers: List[WorkflowOverviewBlocker] = Field(default_factory=list)
    recommended_next_actions: List[WorkflowOverviewAction] = Field(default_factory=list)
    active_runs: List[WorkflowOverviewRun] = Field(default_factory=list)
    recent_events: List[WorkflowEventResponse] = Field(default_factory=list)


class WorkflowVolumeStateResponse(BaseModel):
    id: int
    workflow_id: int
    volume_id: str
    name: Optional[str] = None
    status: str
    status_label: str
    legacy_status: Optional[str] = None
    canonical_status: Optional[str] = None
    canonical_status_label: Optional[str] = None
    annotation_state: Optional[str] = None
    annotation_state_label: Optional[str] = None
    role_state: Optional[str] = None
    role_state_label: Optional[str] = None
    execution_state: Optional[str] = None
    execution_state_label: Optional[str] = None
    region_scope: Dict[str, Any] = Field(default_factory=dict)
    state_schema_version: Optional[str] = None
    status_source: str
    status_confidence: Optional[float] = None
    project_root: Optional[str] = None
    volume_set_id: Optional[str] = None
    volume_set_name: Optional[str] = None
    image_path: Optional[str] = None
    label_path: Optional[str] = None
    prediction_path: Optional[str] = None
    corrected_mask_path: Optional[str] = None
    eligible_for_training: bool = False
    eligible_for_inference: bool = False
    note: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any
    updated_at: Any


class WorkflowVolumeStateListResponse(BaseModel):
    workflow_id: int
    generated_at: str
    summary: Dict[str, Any] = Field(default_factory=dict)
    volumes: List[WorkflowVolumeStateResponse] = Field(default_factory=list)


class WorkflowVolumeStateUpdateRequest(BaseModel):
    volume_id: str
    status: Optional[str] = None
    annotation_state: Optional[str] = None
    role_state: Optional[str] = None
    execution_state: Optional[str] = None
    region_scope: Optional[Dict[str, Any]] = None
    note: Optional[str] = None
    image_path: Optional[str] = None
    label_path: Optional[str] = None
    prediction_path: Optional[str] = None
    corrected_mask_path: Optional[str] = None
    eligible_for_training: Optional[bool] = None
    eligible_for_inference: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


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
    volume_states: List[Dict[str, Any]] = Field(default_factory=list)
    project_memory: Dict[str, Any] = Field(default_factory=dict)
    project_memory_summary: Dict[str, Any] = Field(default_factory=dict)
    agent_plans: List[Dict[str, Any]] = Field(default_factory=list)
    agent_messages: List[Dict[str, Any]] = Field(default_factory=list)
    action_card_index: List[Dict[str, Any]] = Field(default_factory=list)
    trace_index: List[Dict[str, Any]] = Field(default_factory=list)
    artifact_paths: List[Dict[str, Any]] = Field(default_factory=list)
    copy_settings: Dict[str, Any] = Field(default_factory=dict)
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
            "app files mount " f"{json.dumps(str(mount_project.get('directory_path')))}"
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
        lines.append(
            f"app inference labels set {json.dumps(str(inference_label_path))}"
        )

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


def _action_risk_tier(risk_level: str) -> str:
    return {
        "read_only": "R0_view",
        "prefills_form": "R1_prefill",
        "loads_editor": "R2_manual_handoff",
        "writes_workflow_record": "R3_workflow_write",
        "modifies_workspace": "R3_workflow_write",
        "runs_job": "R4_runtime_job",
        "controls_job": "R4_runtime_job",
        "exports_evidence": "R5_export_or_workspace",
    }.get(risk_level, "R0_view")


ORCHESTRATOR_AGENT = {
    "type": "project_manager",
    "label": "Project Manager",
    "short_label": "PM",
    "color": "#111827",
    "icon_key": "project",
    "border_style": "solid",
    "role": "Keeps project memory coherent, routes work to specialists, and gates risky actions.",
}

WORKFLOW_SUBAGENTS = {
    "project_manager": ORCHESTRATOR_AGENT,
    "data_agent": {
        "type": "data_agent",
        "label": "Data Scout",
        "short_label": "Data",
        "color": "#00843D",
        "icon_key": "folder",
        "border_style": "dotted",
        "role": "Inspects mounted folders, pairs image/label artifacts, and refreshes project context.",
    },
    "visualization_agent": {
        "type": "visualization_agent",
        "label": "Visualization Agent",
        "short_label": "Vis",
        "color": "#0057B8",
        "icon_key": "eye",
        "border_style": "double",
        "role": "Opens volumes, validates viewer paths, and checks spatial context.",
    },
    "proofreading_agent": {
        "type": "proofreading_agent",
        "label": "Proofreading Agent",
        "short_label": "Proof",
        "color": "#E0007A",
        "icon_key": "bug",
        "border_style": "dashed",
        "role": "Queues draft masks and tracks review-to-ground-truth promotion.",
    },
    "training_agent": {
        "type": "training_agent",
        "label": "Training Agent",
        "short_label": "Train",
        "color": "#7B2CBF",
        "icon_key": "experiment",
        "border_style": "thick",
        "role": "Builds trainable subsets, stages configs, and launches approved training jobs.",
    },
    "inference_agent": {
        "type": "inference_agent",
        "label": "Inference Agent",
        "short_label": "Infer",
        "color": "#D55E00",
        "icon_key": "thunderbolt",
        "border_style": "dashdot",
        "role": "Runs checkpoints over image-only or selected target volumes.",
    },
    "evaluation_agent": {
        "type": "evaluation_agent",
        "label": "Evaluation Agent",
        "short_label": "Eval",
        "color": "#B58900",
        "icon_key": "bar_chart",
        "border_style": "top",
        "role": "Compares predictions, metrics, and case-study evidence.",
    },
    "evidence_agent": {
        "type": "evidence_agent",
        "label": "Evidence Agent",
        "short_label": "Evidence",
        "color": "#00A6A6",
        "icon_key": "file_done",
        "border_style": "rail",
        "role": "Exports provenance bundles and preserves action traces.",
    },
}


def _agent_descriptor(agent_type: Optional[str]) -> Dict[str, Any]:
    return dict(WORKFLOW_SUBAGENTS.get(str(agent_type or ""), ORCHESTRATOR_AGENT))


def _agent_trace_kwargs(agent: Dict[str, Any]) -> Dict[str, str]:
    return {
        "agent_type": str(agent.get("type") or ORCHESTRATOR_AGENT["type"]),
        "agent_label": str(agent.get("label") or ORCHESTRATOR_AGENT["label"]),
        "agent_color": str(agent.get("color") or ORCHESTRATOR_AGENT["color"]),
        "agent_icon_key": str(agent.get("icon_key") or ORCHESTRATOR_AGENT["icon_key"]),
        "agent_border_style": str(
            agent.get("border_style") or ORCHESTRATOR_AGENT["border_style"]
        ),
    }


def _specialist_agent_for_action(
    action_type: str, client_effects: Dict[str, Any]
) -> Dict[str, Any]:
    navigate_to = str((client_effects or {}).get("navigate_to") or "")
    if action_type in {"start_training", "open_training"} or "training" in navigate_to:
        return _agent_descriptor("training_agent")
    if (
        action_type in {"start_inference", "open_inference"}
        or "inference" in navigate_to
    ):
        return _agent_descriptor("inference_agent")
    if action_type in {"start_proofreading"} or "proofreading" in navigate_to:
        return _agent_descriptor("proofreading_agent")
    if "visualization" in navigate_to or action_type.startswith("open_visualization"):
        return _agent_descriptor("visualization_agent")
    if action_type in {"export_bundle"}:
        return _agent_descriptor("evidence_agent")
    if action_type in {"compute_evaluation"}:
        return _agent_descriptor("evaluation_agent")
    if (
        action_type in {"mount_project", "choose_project_data"}
        or navigate_to == "files"
    ):
        return _agent_descriptor("data_agent")
    if action_type in {
        "show_workflow_context",
        "refresh_context",
        "open_project-progress",
    }:
        return _agent_descriptor("project_manager")
    return _agent_descriptor("project_manager")


def _action_type_from_effects(
    action_id: str,
    client_effects: Optional[Dict[str, Any]],
) -> str:
    effects = client_effects or {}
    runtime_kind = (effects.get("runtime_action") or {}).get("kind")
    workflow_kind = (effects.get("workflow_action") or {}).get("kind")
    if runtime_kind:
        return str(runtime_kind)
    if workflow_kind:
        return str(workflow_kind)
    if effects.get("mount_project"):
        return "mount_project"
    if effects.get("start_new_workflow"):
        return "start_new_workflow"
    if effects.get("show_workflow_context"):
        return "show_workflow_context"
    if effects.get("refresh_insights"):
        return "refresh_context"
    if effects.get("navigate_to"):
        return f"open_{effects.get('navigate_to')}"
    return action_id


def _action_target_from_effects(
    client_effects: Optional[Dict[str, Any]],
) -> Optional[str]:
    effects = client_effects or {}
    runtime_action = effects.get("runtime_action") or {}
    workflow_action = effects.get("workflow_action") or {}
    for key in [
        "set_training_image_path",
        "set_training_label_path",
        "set_inference_image_path",
        "set_inference_label_path",
        "set_visualization_image_path",
        "set_visualization_label_path",
        "set_proofreading_image_path",
        "set_proofreading_label_path",
    ]:
        if effects.get(key):
            return str(effects[key])
    for source in [runtime_action, workflow_action, effects.get("mount_project") or {}]:
        if isinstance(source, dict):
            for key in ["image_path", "label_path", "corrected_mask_path", "path"]:
                if source.get(key):
                    return str(source[key])
    return str(effects.get("navigate_to")) if effects.get("navigate_to") else None


def _artifact_entries_from_effects(
    client_effects: Optional[Dict[str, Any]],
    *,
    direction: str,
) -> List[Dict[str, Any]]:
    effects = client_effects or {}
    input_keys = {
        "set_training_config_preset": "config",
        "set_training_image_path": "image",
        "set_training_label_path": "label",
        "set_inference_config_preset": "config",
        "set_inference_checkpoint_path": "checkpoint",
        "set_inference_image_path": "image",
        "set_inference_label_path": "label",
        "set_visualization_image_path": "image",
        "set_visualization_label_path": "label",
        "set_proofreading_image_path": "image",
        "set_proofreading_label_path": "label",
    }
    output_keys = {
        "set_training_output_path": "training_output",
        "set_training_log_path": "training_log",
        "set_inference_output_path": "prediction",
    }
    key_map = input_keys if direction == "input" else output_keys
    entries = [
        {"role": role, "path": str(value)}
        for key, role in key_map.items()
        for value in [effects.get(key)]
        if value
    ]
    subset = effects.get("training_volume_subset")
    if direction == "input" and isinstance(subset, dict):
        manifest_path = subset.get("manifest_path")
        if manifest_path:
            entries.append(
                {"role": "training_subset_manifest", "path": str(manifest_path)}
            )
    return entries


def _summary_fields_from_effects(
    client_effects: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    effects = client_effects or {}
    fields: List[Dict[str, Any]] = []
    for key, label in [
        ("navigate_to", "Opens"),
        ("set_training_config_preset", "Config"),
        ("set_training_image_path", "Images"),
        ("set_training_label_path", "Labels"),
        ("set_training_output_path", "Output"),
        ("set_inference_checkpoint_path", "Checkpoint"),
        ("set_inference_image_path", "Images"),
        ("set_inference_output_path", "Output"),
    ]:
        if effects.get(key):
            fields.append({"label": label, "value": str(effects[key])})
    subset = effects.get("training_volume_subset")
    if isinstance(subset, dict):
        fields.extend(
            [
                {
                    "label": "Training set",
                    "value": f"{subset.get('train_volume_count', 0)} trusted volume(s)",
                },
                {
                    "label": "Targets after training",
                    "value": f"{subset.get('target_volume_count', 0)} image-only volume(s)",
                },
                {
                    "label": "Left out",
                    "value": f"{subset.get('review_volume_count', 0)} draft mask(s)",
                },
            ]
        )
    return fields


def _expected_effects_from_client_effects(
    client_effects: Optional[Dict[str, Any]],
) -> List[str]:
    effects = client_effects or {}
    expected: List[str] = []
    if effects.get("navigate_to"):
        expected.append(f"Open the {effects['navigate_to']} view.")
    if any(key.startswith("set_training_") for key in effects):
        expected.append("Prefill the training form from project memory.")
    if any(key.startswith("set_inference_") for key in effects):
        expected.append("Prefill the inference form from project memory.")
    runtime_kind = (effects.get("runtime_action") or {}).get("kind")
    if runtime_kind == "start_training":
        expected.append("Launch a training process after approval.")
    elif runtime_kind == "start_inference":
        expected.append("Launch an inference process after approval.")
    elif runtime_kind == "start_proofreading":
        expected.append("Open a proofreading session.")
    workflow_kind = (effects.get("workflow_action") or {}).get("kind")
    if workflow_kind == "export_bundle":
        expected.append("Write a reproducibility bundle.")
    if effects.get("refresh_insights"):
        expected.append("Refresh project memory and recommendations.")
    return expected or ["Perform the selected app step."]


def _approval_reason_for_risk(risk_level: str) -> Optional[str]:
    return {
        "runs_job": "This starts compute and writes run artifacts.",
        "controls_job": "This changes a running process.",
        "loads_editor": "This opens an editing workflow that can produce new masks.",
        "exports_evidence": "This writes an evidence bundle to disk.",
        "writes_workflow_record": "This changes workflow state.",
        "modifies_workspace": "This changes the active project/workspace.",
    }.get(risk_level)


def _reason_code_from_label(label: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(label).strip().lower())
    return normalized.strip("_") or "item"


def _policy_blocking_reason(
    code: str,
    message: str,
    *,
    scope: str = "input",
    field: Optional[str] = None,
    value: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "code": code,
        "message": message,
        "scope": scope,
    }
    if field:
        payload["field"] = field
    if value:
        payload["value"] = value
    return payload


def _policy_decision_payload(
    decision: str,
    *,
    requires_approval: bool,
    reason_code: Optional[str] = None,
    reason: Optional[str] = None,
    blocking_reasons: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "decision": decision,
        "requires_approval": bool(requires_approval),
        "reason_code": reason_code,
        "reason": reason,
        "blocking_reasons": blocking_reasons or [],
    }


def _resource_freshness_payload(
    *,
    scope: str,
    required_fields: List[str],
    missing_fields: List[str],
    source: str = "workflow_state",
) -> Dict[str, Any]:
    return {
        "scope": scope,
        "state": "ready" if not missing_fields else "missing",
        "required": required_fields,
        "missing": missing_fields,
        "source": source,
    }


def _project_context_freshness(workflow: WorkflowSession) -> Dict[str, Any]:
    required_fields = ["imaging_modality", "target_structure"]
    context = _workflow_project_context(workflow)
    missing_fields = [field for field in required_fields if not context.get(field)]
    if not missing_fields:
        state = "fresh"
        if (
            not context.get("updated_at")
            or context.get("source") == "initial_project_default"
        ):
            state = "stale"
    else:
        state = "missing"
    return {
        "scope": "project_context",
        "state": state,
        "required": required_fields,
        "missing": missing_fields,
        "present": [field for field in required_fields if context.get(field)],
        "source": context.get("source")
        or context.get("updated_at")
        and "workflow_agent_context",
    }


def _build_action_card_payload(
    *,
    action_id: str,
    label: str,
    description: str,
    client_effects: Dict[str, Any],
    risk_level: str,
    requires_approval: bool,
    disabled_reason: Optional[str],
) -> Dict[str, Any]:
    action_type = _action_type_from_effects(action_id, client_effects)
    specialist_agent = _specialist_agent_for_action(action_type, client_effects)
    blockers = [disabled_reason] if disabled_reason else []
    return {
        "schema_version": "workflow.action_card/v2",
        "action_id": action_id,
        "action_type": action_type,
        "orchestrator_agent": ORCHESTRATOR_AGENT,
        "specialist_agent": specialist_agent,
        "title": label,
        "rationale": description,
        "target": _action_target_from_effects(client_effects),
        "risk_level": risk_level,
        "risk_tier": _action_risk_tier(risk_level),
        "requires_approval": requires_approval,
        "approval_reason": _approval_reason_for_risk(risk_level),
        "blockers": blockers,
        "input_artifacts": _artifact_entries_from_effects(
            client_effects, direction="input"
        ),
        "output_artifacts": _artifact_entries_from_effects(
            client_effects, direction="output"
        ),
        "summary_fields": _summary_fields_from_effects(client_effects),
        "expected_effects": _expected_effects_from_client_effects(client_effects),
        "executor": "bounded_app_routine",
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
    question_like = "?" in stripped or stripped.startswith(
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
    policy_decision: Optional[Dict[str, Any]] = None,
    blocking_reasons: Optional[List[Dict[str, Any]]] = None,
    freshness: Optional[Dict[str, Any]] = None,
) -> AgentChatAction:
    effects = client_effects or {}
    inferred_risk = risk_level or _infer_action_risk(effects)
    approval_required = (
        _requires_action_approval(effects)
        if requires_approval is None
        else requires_approval
    )
    computed_reasons = blocking_reasons or []
    policy = policy_decision
    if policy is None:
        policy = _policy_decision_payload(
            "allowed" if not computed_reasons else "blocked",
            requires_approval=approval_required,
            reason_code=(
                _reason_code_from_label(inferred_risk) if computed_reasons else None
            ),
            reason=_approval_reason_for_risk(inferred_risk),
            blocking_reasons=computed_reasons,
        )
    action_card = _build_action_card_payload(
        action_id=action_id,
        label=label,
        description=description,
        client_effects=effects,
        risk_level=inferred_risk,
        requires_approval=approval_required,
        disabled_reason=disabled_reason,
    )
    specialist_agent = action_card.get("specialist_agent") or ORCHESTRATOR_AGENT
    return AgentChatAction(
        id=action_id,
        label=label,
        description=description,
        orchestrator_agent=action_card.get("orchestrator_agent") or ORCHESTRATOR_AGENT,
        specialist_agent=specialist_agent,
        agent_type=str(specialist_agent.get("type") or "project_manager"),
        agent_label=str(specialist_agent.get("label") or "Project Manager"),
        agent_color=str(specialist_agent.get("color") or "#111827"),
        agent_icon_key=str(specialist_agent.get("icon_key") or "project"),
        agent_border_style=str(specialist_agent.get("border_style") or "solid"),
        action_type=str(action_card.get("action_type") or action_id),
        target=action_card.get("target"),
        variant=variant,
        run_label=run_label,
        risk_level=inferred_risk,
        risk_tier=str(action_card.get("risk_tier") or _action_risk_tier(inferred_risk)),
        requires_approval=approval_required,
        approval_reason=action_card.get("approval_reason"),
        summary_fields=action_card.get("summary_fields") or [],
        input_artifacts=action_card.get("input_artifacts") or [],
        output_artifacts=action_card.get("output_artifacts") or [],
        expected_effects=action_card.get("expected_effects") or [],
        blockers=action_card.get("blockers") or [],
        action_card=action_card,
        disabled_reason=disabled_reason,
        client_effects=effects,
        policy_decision=policy,
        blocking_reasons=computed_reasons,
        freshness=freshness or {},
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
        effects["set_inference_image_path"] = (
            workflow.image_path or workflow.dataset_path
        )
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
        return "configs/MitoEM/Mito25-Local-BC.yaml"
    if "snemi" in haystack:
        return "configs/SNEMI/SNEMI-Affinity-UNet.yaml"
    if "cremi" in haystack:
        return "configs/CREMI/CREMI-Foreground-UNet.yaml"
    return "configs/Lucchi-Mitochondria.yaml"


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
        (
            str(volume_subset_plan.get("image_path") or "")
            if isinstance(volume_subset_plan, dict)
            else ""
        )
        or workflow.image_path
        or workflow.dataset_path
        or ""
    )
    label_path = (
        (
            str(volume_subset_plan.get("label_path") or "")
            if isinstance(volume_subset_plan, dict)
            else ""
        )
        or corrected_mask_path
        or ""
    )
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


def _workflow_requires_trusted_masks(workflow: WorkflowSession) -> bool:
    project_context = _workflow_project_context(workflow)
    if not isinstance(project_context, dict):
        return False
    preset = _task_family_preset_for_context(project_context)
    if preset.get("id") == "tapereader_xri_fiber":
        return True
    policy = str(project_context.get("training_policy") or "").lower()
    if "confirmed" in policy and "ground" in policy:
        return True
    task_family = str(project_context.get("task_family") or "").lower()
    return "xri" in task_family and "tape" in task_family


def _preferred_training_mask_path(
    workflow: WorkflowSession,
    *,
    require_trusted: bool = False,
) -> Optional[str]:
    if workflow.corrected_mask_path:
        return workflow.corrected_mask_path
    if workflow.label_path:
        return workflow.label_path
    if require_trusted:
        return None
    return workflow.mask_path


def _training_run_effects_from_proposal(
    workflow: WorkflowSession,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    client_effects = params.get("client_effects")
    if (
        isinstance(client_effects, dict)
        and (client_effects.get("runtime_action") or {}).get("kind") == "start_training"
    ):
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
    if isinstance(client_effects, dict):
        for key, value in client_effects.items():
            if key.startswith("set_training_") or key in {
                "runtime_action",
                "training_volume_subset",
                "refresh_project_progress",
            }:
                effects[key] = value
    return effects


AGENT_ACTION_CLIENT_EFFECT_OVERRIDES: Dict[str, str] = {
    "config_preset": "set_training_config_preset",
    "image_path": "set_training_image_path",
    "label_path": "set_training_label_path",
    "output_path": "set_training_output_path",
    "log_path": "set_training_log_path",
    "inference_config_preset": "set_inference_config_preset",
    "checkpoint_path": "set_inference_checkpoint_path",
    "inference_image_path": "set_inference_image_path",
    "inference_label_path": "set_inference_label_path",
    "inference_output_path": "set_inference_output_path",
    "visualization_image_path": "set_visualization_image_path",
    "visualization_label_path": "set_visualization_label_path",
    "visualization_scales": "set_visualization_scales",
    "proofreading_dataset_path": "set_proofreading_dataset_path",
    "proofreading_mask_path": "set_proofreading_mask_path",
    "proofreading_project_name": "set_proofreading_project_name",
}

AGENT_ACTION_PARAM_OVERRIDES = set(AGENT_ACTION_CLIENT_EFFECT_OVERRIDES).union(
    {
        "corrected_mask_path",
        "written_path",
        "training_output_path",
        "parameter_mode",
        "autopick_parameters",
    }
)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _clean_agent_action_overrides(
    overrides: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(overrides, dict):
        return {}
    cleaned: Dict[str, Any] = {}
    for key, value in overrides.items():
        if key not in AGENT_ACTION_PARAM_OVERRIDES:
            continue
        if isinstance(value, str):
            cleaned[key] = value.strip()
        else:
            cleaned[key] = value
    return cleaned


def _apply_agent_action_overrides(
    action: str,
    params: Dict[str, Any],
    overrides: Optional[Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    applied = _clean_agent_action_overrides(overrides)
    if not applied:
        return params, {}

    next_params = dict(params or {})
    for key, value in applied.items():
        next_params[key] = value

    effects = dict(next_params.get("client_effects") or {})
    for key, value in applied.items():
        effect_key = AGENT_ACTION_CLIENT_EFFECT_OVERRIDES.get(key)
        if effect_key:
            effects[effect_key] = value

    if action == "start_training_run":
        if "output_path" in applied and "log_path" not in applied:
            effects["set_training_log_path"] = applied["output_path"]
        runtime_action = dict(effects.get("runtime_action") or {})
        if runtime_action.get("kind") == "start_training":
            if "parameter_mode" in applied:
                runtime_action["parameter_mode"] = applied["parameter_mode"]
            if "autopick_parameters" in applied:
                runtime_action["autopick_parameters"] = _coerce_bool(
                    applied["autopick_parameters"]
                )
            effects["runtime_action"] = runtime_action
    if effects:
        next_params["client_effects"] = effects
    return next_params, applied


def _agent_action_approval_payload(
    proposal_id: int,
    action: str,
    user_edits: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"proposal_event_id": proposal_id, "action": action}
    if user_edits:
        payload["user_edits"] = user_edits
    return payload


def _build_start_proofreading_effects(workflow: WorkflowSession) -> Dict[str, Any]:
    dataset_path = workflow.image_path or workflow.dataset_path or ""
    mask_path = (
        workflow.corrected_mask_path
        or workflow.inference_output_path
        or workflow.mask_path
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
    return workflow.image_path or workflow.dataset_path or ""


def _workflow_mask_like_path(workflow: WorkflowSession) -> str:
    return (
        workflow.corrected_mask_path
        or workflow.inference_output_path
        or workflow.mask_path
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
    policy_decision: Optional[Dict[str, Any]] = None,
    blocking_reasons: Optional[List[Dict[str, Any]]] = None,
    freshness: Optional[Dict[str, Any]] = None,
) -> AgentChatAction:
    return _build_agent_chat_action(
        "start-proofreading",
        label,
        "Open the image and mask in the proofreading workbench.",
        variant=variant,
        client_effects=_build_start_proofreading_effects(workflow),
        policy_decision=policy_decision,
        blocking_reasons=blocking_reasons,
        freshness=freshness,
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
            ),
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
                "open-training-runtime",
                "View training log",
                "Open Train Model runtime details.",
                client_effects={"navigate_to": "training"},
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
            [
                "project progress",
                "progress tracker",
                "project tracker",
                "volume tracker",
                "progress",
            ],
            {
                "tab": "project-progress",
                "label": "Open Workflow",
                "description": "Open the workflow overview and volume tracker.",
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
                "tab": "training",
                "label": "Open Train Model",
                "description": "Open training runtime details and logs.",
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


SEMANTIC_WORKFLOW_INTENT_ORDER = (
    "greeting",
    "status",
    "capabilities",
    "style_feedback",
    "project_context",
    "project_context_update",
    "project_files",
    "project_progress",
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
)

SEMANTIC_WORKFLOW_INTENTS = set(SEMANTIC_WORKFLOW_INTENT_ORDER)


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
    project_progress = (
        metadata.get("project_progress_snapshot") if isinstance(metadata, dict) else {}
    )
    if not isinstance(project_progress, dict):
        project_progress = {}
    progress_summary = project_progress.get("summary")
    if not isinstance(progress_summary, dict):
        progress_summary = {}
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
            "task_family": project_context.get("task_family"),
            "mask_status": project_context.get("mask_status"),
            "image_only_strategy": project_context.get("image_only_strategy"),
            "training_policy": project_context.get("training_policy"),
            "optimization_priority": project_context.get("optimization_priority"),
            "voxel_size_nm": project_context.get("voxel_size_nm"),
        },
        "project_progress": {
            "total": progress_summary.get("tracked_total")
            or progress_summary.get("total"),
            "ground_truth": progress_summary.get("ground_truth"),
            "needs_proofreading": progress_summary.get("needs_proofreading"),
            "missing_segmentation": progress_summary.get("missing_segmentation"),
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
{", ".join(SEMANTIC_WORKFLOW_INTENT_ORDER)}.

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

Tabs for navigate: files, visualization, inference, training, project-progress, mask-proofreading.
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
        "monitoring": ("Open Train Model", "Open training runtime details and logs."),
        "project-progress": (
            "Open Workflow",
            "Open the workflow overview and volume tracker.",
        ),
        "progress": ("Open Workflow", "Open the workflow overview and volume tracker."),
        "mask-proofreading": (
            "Open Proofread",
            "Open the mask proofreading workbench.",
        ),
        "proofreading": ("Open Proofread", "Open the mask proofreading workbench."),
    }
    if tab not in tab_specs:
        return None
    normalized_tab = (
        "mask-proofreading"
        if tab == "proofreading"
        else (
            "project-progress"
            if tab == "progress"
            else "training" if tab == "monitoring" else tab
        )
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
    ground_truth_path = (
        workflow.corrected_mask_path or workflow.label_path or workflow.mask_path
    )
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
    decision = _lower_first(_strip_sentence_period(recommendation.decision))
    return (
        f"Hey. We are still in {stage}. "
        f"I would probably {decision}. "
        "I can open the right screen, walk through what I am seeing, or help decide the next step."
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
        key=lambda row: (
            row.created_at or datetime.min.replace(tzinfo=timezone.utc),
            row.id,
        ),
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
        key=lambda row: (
            row.created_at or datetime.min.replace(tzinfo=timezone.utc),
            row.id,
        ),
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
    policy_decision: Optional[Dict[str, Any]] = None,
    blocking_reasons: Optional[List[Dict[str, Any]]] = None,
    freshness: Optional[Dict[str, Any]] = None,
) -> WorkflowPreflightItem:
    missing = missing or []
    resolved_status = status or ("ready" if can_run else "needs_input")
    reasons = blocking_reasons or []
    decision = policy_decision
    if decision is None:
        policy_blocking_required_approval = risk_level in {
            "runs_job",
            "controls_job",
            "loads_editor",
            "exports_evidence",
            "writes_workflow_record",
            "modifies_workspace",
        }
        decision = _policy_decision_payload(
            "allowed" if can_run else "blocked",
            requires_approval=policy_blocking_required_approval,
            reason_code="ready" if can_run else "missing_inputs",
            reason=(
                "This action is ready" if can_run else "Required inputs are missing."
            ),
            blocking_reasons=reasons,
        )
    return WorkflowPreflightItem(
        id=item_id,
        label=label,
        status=resolved_status,
        can_run=can_run,
        missing=missing,
        action=action,
        risk_level=risk_level,
        policy_decision=decision,
        blocking_reasons=reasons,
        freshness=freshness or {},
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
        .order_by(
            WorkflowCorrectionSet.created_at.asc(), WorkflowCorrectionSet.id.asc()
        )
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
        or (
            completed_inference_runs[-1].output_path
            if completed_inference_runs
            else None
        )
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
            if workflow.inference_output_path
            and workflow.inference_output_path != baseline_path
            else None
        )
    )
    ground_truth_path = reference_path or corrected_mask_path

    has_image = _workflow_path_present(image_path)
    requires_trusted_training = _workflow_requires_trusted_masks(workflow)
    has_reference = _workflow_path_present(reference_path)
    training_reference = _preferred_training_mask_path(
        workflow,
        require_trusted=requires_trusted_training,
    )
    has_mask_like = has_reference or _workflow_path_present(prediction_path)
    has_checkpoint = _workflow_path_present(checkpoint_path)
    has_correction = _workflow_path_present(corrected_mask_path)
    has_training_target = _workflow_path_present(training_reference)
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

    def _missing_reasons(
        item_id: str, missing_fields: List[str]
    ) -> List[Dict[str, Any]]:
        return [
            _policy_blocking_reason(
                f"{item_id}.missing_{_reason_code_from_label(field)}",
                f"{field.capitalize()} is required.",
                scope="workflow_state",
                field=field,
            )
            for field in missing_fields
        ]

    items = [
        _preflight_item(
            "project_setup",
            "Project data",
            can_run=has_image,
            missing=[] if has_image else ["image volume"],
            policy_decision=_policy_decision_payload(
                "allowed" if has_image else "blocked",
                requires_approval=False,
                reason_code=(
                    "project_data_ready" if has_image else "project_data_missing"
                ),
                reason=(
                    "Project source is configured."
                    if has_image
                    else "Project image input is missing."
                ),
                blocking_reasons=_missing_reasons(
                    "project_setup", [] if has_image else ["image volume"]
                ),
            ),
            blocking_reasons=_missing_reasons(
                "project_setup", [] if has_image else ["image volume"]
            ),
            freshness=_resource_freshness_payload(
                scope="project_data",
                required_fields=["image volume"],
                missing_fields=[] if has_image else ["image volume"],
            ),
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
            policy_decision=_policy_decision_payload(
                "allowed" if has_image else "blocked",
                requires_approval=False,
                reason_code=(
                    "visualization_ready"
                    if has_image
                    else "visualization_missing_inputs"
                ),
                reason=(
                    "Visualization inputs are available."
                    if has_image
                    else "Image input is missing for visualization."
                ),
                blocking_reasons=_missing_reasons(
                    "visualization", [] if has_image else ["image volume"]
                ),
            ),
            blocking_reasons=_missing_reasons(
                "visualization", [] if has_image else ["image volume"]
            ),
            freshness=_resource_freshness_payload(
                scope="visualization",
                required_fields=["image volume"],
                missing_fields=[] if has_image else ["image volume"],
            ),
            action="Open the image volume for inspection.",
            risk_level="view_only",
        ),
        _preflight_item(
            "inference",
            "Run model",
            can_run=has_image and has_checkpoint,
            missing=inference_missing,
            policy_decision=_policy_decision_payload(
                "allowed" if has_image and has_checkpoint else "blocked",
                requires_approval=True,
                reason_code=(
                    "inference_ready"
                    if has_image and has_checkpoint
                    else "inference_missing_inputs"
                ),
                reason=(
                    "Inference inputs are complete."
                    if has_image and has_checkpoint
                    else "Image volume and checkpoint are required."
                ),
                blocking_reasons=_missing_reasons("inference", inference_missing),
            ),
            blocking_reasons=_missing_reasons("inference", inference_missing),
            freshness=_resource_freshness_payload(
                scope="inference",
                required_fields=["image volume", "checkpoint"],
                missing_fields=inference_missing,
            ),
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
            policy_decision=_policy_decision_payload(
                "allowed" if has_image and has_mask_like else "blocked",
                requires_approval=False,
                reason_code=(
                    "proofreading_ready"
                    if has_image and has_mask_like
                    else "proofreading_missing_inputs"
                ),
                reason=(
                    "Image and mask data are available for proofreading."
                    if has_image and has_mask_like
                    else "Image and mask-like input are required."
                ),
                blocking_reasons=_missing_reasons("proofreading", proofreading_missing),
            ),
            blocking_reasons=_missing_reasons("proofreading", proofreading_missing),
            freshness=_resource_freshness_payload(
                scope="proofreading",
                required_fields=["image volume", "mask, label, or prediction"],
                missing_fields=proofreading_missing,
            ),
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
            policy_decision=_policy_decision_payload(
                "allowed" if has_image and has_training_target else "blocked",
                requires_approval=True,
                reason_code=(
                    "training_ready"
                    if has_image and has_training_target
                    else "training_missing_inputs"
                ),
                reason=(
                    "Training inputs are complete."
                    if has_image and has_training_target
                    else "Image and labels or corrected masks are required."
                ),
                blocking_reasons=_missing_reasons("training", training_missing),
            ),
            blocking_reasons=_missing_reasons("training", training_missing),
            freshness=_resource_freshness_payload(
                scope="training",
                required_fields=["image volume", "label or corrected mask"],
                missing_fields=training_missing,
            ),
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
            policy_decision=_policy_decision_payload(
                (
                    "allowed"
                    if has_baseline and has_candidate and has_ground_truth
                    else "blocked"
                ),
                requires_approval=True,
                reason_code=(
                    "evaluation_ready"
                    if has_baseline and has_candidate and has_ground_truth
                    else "evaluation_missing_inputs"
                ),
                reason=(
                    "Evaluation inputs are available."
                    if has_baseline and has_candidate and has_ground_truth
                    else "Previous result, new result, and reference mask are required."
                ),
                blocking_reasons=_missing_reasons("evaluation", evaluation_missing),
            ),
            blocking_reasons=_missing_reasons("evaluation", evaluation_missing),
            freshness=_resource_freshness_payload(
                scope="evaluation",
                required_fields=["previous result", "new result", "reference mask"],
                missing_fields=evaluation_missing,
            ),
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
    lines = [f"I would probably start with {decision}."]
    if rationale:
        lines.append(f"That fits because {rationale}.")
    if total_count:
        lines.append(
            f"I checked the workflow state: {ready_count}/{total_count} pieces look ready."
        )
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

    if not any(
        buckets[key]
        for key in ("action", "why", "current", "blocker", "watch", "ready")
    ):
        return response

    parts: List[str] = []
    if buckets["current"]:
        current = _lower_first(_strip_sentence_period(buckets["current"][0]))
        parts.append(f"Right now I would focus on {current}.")
    if buckets["action"]:
        action = _strip_sentence_period(buckets["action"][0])
        if action.lower().startswith(
            (
                "open ",
                "show ",
                "view ",
                "run ",
                "proofread ",
                "train ",
                "compute ",
                "export ",
                "stop ",
            )
        ):
            parts.append(f"I can {_lower_first(action)}.")
        else:
            parts.append(f"I would probably start with {action}.")
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


def _normalize_volume_path_for_match(path_value: Optional[str]) -> str:
    if not path_value:
        return ""
    return os.path.normcase(os.path.abspath(str(path_value)))


def _looks_like_file_path(path_value: Optional[str]) -> bool:
    text = str(path_value or "").strip()
    if not text or text.endswith("/"):
        return False
    suffix = pathlib.Path(text).suffix
    return bool(suffix)


def _find_matching_volume_pair(
    pairs: List[Dict[str, Any]],
    *,
    image_path: Optional[str],
    label_path: Optional[str],
) -> Optional[Dict[str, Any]]:
    image_norm = _normalize_volume_path_for_match(image_path)
    label_norm = _normalize_volume_path_for_match(label_path)
    for pair in pairs:
        pair_image = _normalize_volume_path_for_match(pair.get("image_path"))
        pair_label = _normalize_volume_path_for_match(pair.get("label_path"))
        if image_norm and pair_image and image_norm == pair_image:
            return pair
        if label_norm and pair_label and label_norm == pair_label:
            return pair
    return None


def _select_visualization_pair(
    workflow: WorkflowSession,
    pair_discovery: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    pairs = pair_discovery.get("pairs") or []
    image_path = workflow.image_path or workflow.dataset_path
    label_path = (
        workflow.label_path
        or workflow.mask_path
        or workflow.inference_output_path
        or workflow.corrected_mask_path
    )
    if _looks_like_file_path(image_path) and _looks_like_file_path(label_path):
        return {"image_path": str(image_path), "label_path": str(label_path)}
    if _looks_like_file_path(image_path):
        matched_pair = _find_matching_volume_pair(
            pairs,
            image_path=str(image_path),
            label_path=label_path if _looks_like_file_path(label_path) else None,
        )
        if matched_pair:
            return matched_pair
        return {"image_path": str(image_path), "label_path": label_path}
    if _looks_like_file_path(label_path):
        matched_pair = _find_matching_volume_pair(
            pairs,
            image_path=image_path,
            label_path=str(label_path),
        )
        if matched_pair:
            return matched_pair
        return {"image_path": image_path, "label_path": str(label_path)}
    return _find_matching_volume_pair(
        pairs,
        image_path=image_path,
        label_path=label_path,
    ) or (pairs[0] if pairs else None)


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


def _mounted_project_roots(db: Session, user_id: int) -> List[Dict[str, Any]]:
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

    if workflow.dataset_path and os.path.isdir(
        _normalize_absolute_path(workflow.dataset_path)
    ):
        add_candidate(workflow.dataset_path, "workflow_dataset_path")

    derived_root = _derive_mount_project_path(workflow)
    if derived_root and os.path.isdir(_normalize_absolute_path(derived_root)):
        add_candidate(derived_root, "derived_workflow_root")

    mounted_roots = _mounted_project_roots(db, user_id)
    workflow_paths = [
        _normalize_absolute_path(path) for path in _workflow_path_values(workflow)
    ]
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


def _project_top_level_entries(
    root_path: str, *, max_entries: int = 12
) -> List[Dict[str, Any]]:
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
        return _path_is_within(
            image_path, volume_set.get("image_root_path")
        ) or _normalize_absolute_path(image_path) == _normalize_absolute_path(
            volume_set.get("image_path")
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
        or re.search(
            r"\b(?:list|show|describe|explain)\b.{0,40}\bfiles?\b", lower_query
        )
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
        (
            f"{entry.get('name')}/"
            if entry.get("kind") == "folder"
            else str(entry.get("name"))
        )
        for entry in entries[:8]
        if entry.get("name")
    ]
    counts = root.get("counts") or {}

    lines = [
        f"I checked `{root_name}`. At the top level I see {', '.join(entry_names) or 'no indexed files yet'}."
    ]
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
        lines.append(
            "The useful workflow pieces look like " + ", ".join(useful_bits) + "."
        )

    if volume_sets:
        set_summaries = []
        for item in volume_sets[:3]:
            set_summaries.append(
                f"{item.get('name') or 'volume set'}"
                f" ({item.get('image_count') or 0} images, {item.get('label_count') or 0} labels)"
            )
        lines.append("I also found " + "; ".join(set_summaries) + ".")
    lines.append(
        "Ask me to open one of those sets and I can route it straight into Visualize."
    )
    return "\n".join(lines)


PROJECT_PROGRESS_STATUS_DEFINITIONS = {
    "ground_truth": "Fully good: has a proofread, corrected, curated, or ground-truth segmentation.",
    "needs_proofreading": "Has a segmentation or mask, but it is not confirmed as proofread ground truth.",
    "missing_segmentation": "Has image data, but no matching segmentation was found.",
    "ignored": "Excluded from the active progress denominator.",
}
PROJECT_PROGRESS_CANONICAL_STATUS = {
    "ground_truth": {
        "status": "proofread_ground_truth",
        "label": "Proofread ground truth",
    },
    "needs_proofreading": {
        "status": "draft_needs_proofreading",
        "label": "Draft mask needs proofreading",
    },
    "missing_segmentation": {
        "status": "image_only",
        "label": "Image only",
    },
    "ignored": {
        "status": "ignored",
        "label": "Ignored",
    },
}
WORKFLOW_VOLUME_STATE_SCHEMA_VERSION = "workflow-volume-state/v2"
WORKFLOW_VOLUME_ANNOTATION_STATES = {
    "proofread_ground_truth": "Proofread ground truth",
    "draft_needs_proofreading": "Draft mask needs proofreading",
    "image_only": "Image only",
    "prediction_available": "Prediction available",
    "ignored": "Ignored",
}
WORKFLOW_VOLUME_ROLE_STATES = {
    "training_source": "Training source",
    "proofreading_target": "Proofreading target",
    "inference_target": "Inference target",
    "evaluation_target": "Evaluation target",
    "excluded": "Excluded",
    "unassigned": "Unassigned",
}
WORKFLOW_VOLUME_EXECUTION_STATES = {
    "idle": "Idle",
    "ready": "Ready",
    "queued": "Queued",
    "running": "Running",
    "completed": "Completed",
    "failed": "Failed",
    "blocked": "Blocked",
}
PROJECT_PROGRESS_LEGACY_TO_COMPOSITE = {
    "ground_truth": {
        "annotation_state": "proofread_ground_truth",
        "role_state": "training_source",
        "execution_state": "ready",
    },
    "needs_proofreading": {
        "annotation_state": "draft_needs_proofreading",
        "role_state": "proofreading_target",
        "execution_state": "ready",
    },
    "missing_segmentation": {
        "annotation_state": "image_only",
        "role_state": "inference_target",
        "execution_state": "ready",
    },
    "ignored": {
        "annotation_state": "ignored",
        "role_state": "excluded",
        "execution_state": "idle",
    },
}
PROJECT_PROGRESS_COMPOSITE_TO_LEGACY = {
    "proofread_ground_truth": "ground_truth",
    "draft_needs_proofreading": "needs_proofreading",
    "image_only": "missing_segmentation",
    "prediction_available": "needs_proofreading",
    "ignored": "ignored",
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
        image_parent = pathlib.Path(image_relative).parent.name.lower()
        segmentation_parent = pathlib.Path(segmentation_relative).parent.name.lower()
        if (
            image_parent
            and image_parent not in {".", "image", "images", "raw", "volume", "volumes"}
            and image_parent == segmentation_parent
        ):
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
    if (
        normalized_segmentation in correction_paths
        or segmentation_key in correction_keys
    ):
        evidence.append("Matches a saved proofreading correction set.")
        return "ground_truth", "correction_set", evidence
    if image_key and image_key in correction_keys:
        evidence.append("Image volume has a saved correction-set key.")
        return "ground_truth", "correction_set", evidence
    if _project_progress_has_ground_truth_marker(segmentation_path):
        evidence.append("Segmentation path looks like ground truth or proofread data.")
        return "ground_truth", "path_marker", evidence
    evidence.append(
        "Segmentation exists, but it is not marked as proofread ground truth."
    )
    return "needs_proofreading", "derived", evidence


def _project_progress_status_label(status: str) -> str:
    return {
        "ground_truth": "Fully good",
        "needs_proofreading": "Needs proofreading",
        "missing_segmentation": "No segmentation",
        "ignored": "Ignored",
    }.get(status, status.replace("_", " ").title())


def _canonical_project_progress_status(status: Optional[str]) -> Dict[str, str]:
    if status in PROJECT_PROGRESS_CANONICAL_STATUS:
        return PROJECT_PROGRESS_CANONICAL_STATUS[str(status)]
    fallback = str(status or "unknown")
    return {
        "status": fallback,
        "label": fallback.replace("_", " ").title(),
    }


def _state_label(value: Optional[str], labels: Dict[str, str]) -> str:
    text = str(value or "unknown")
    return labels.get(text, text.replace("_", " ").title())


def _composite_state_from_legacy_status(status: Optional[str]) -> Dict[str, str]:
    legacy = str(status or "missing_segmentation")
    state = PROJECT_PROGRESS_LEGACY_TO_COMPOSITE.get(legacy)
    if state:
        return dict(state)
    return dict(PROJECT_PROGRESS_LEGACY_TO_COMPOSITE["missing_segmentation"])


def _legacy_status_from_composite_state(
    annotation_state: Optional[str],
    role_state: Optional[str] = None,
) -> str:
    annotation = str(annotation_state or "")
    if annotation in PROJECT_PROGRESS_COMPOSITE_TO_LEGACY:
        return PROJECT_PROGRESS_COMPOSITE_TO_LEGACY[annotation]
    if role_state == "excluded":
        return "ignored"
    if role_state == "training_source":
        return "ground_truth"
    if role_state == "proofreading_target":
        return "needs_proofreading"
    if role_state == "inference_target":
        return "missing_segmentation"
    return "missing_segmentation"


def _normalize_region_scope(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    scope = value if isinstance(value, dict) else {}
    scope_type = str(scope.get("scope_type") or "full_volume")
    normalized = {
        "scope_type": scope_type,
        "coordinate_space": str(scope.get("coordinate_space") or "voxel"),
        "bounds": scope.get("bounds"),
        "regions": (
            scope.get("regions") if isinstance(scope.get("regions"), list) else []
        ),
        "source": str(scope.get("source") or "project_scan"),
    }
    return normalized


def _row_region_scope(row: WorkflowVolumeState) -> Dict[str, Any]:
    return _normalize_region_scope(decode_json(getattr(row, "region_scope_json", None)))


def _set_row_composite_state(
    row: WorkflowVolumeState,
    *,
    status: Optional[str] = None,
    annotation_state: Optional[str] = None,
    role_state: Optional[str] = None,
    execution_state: Optional[str] = None,
    region_scope: Optional[Dict[str, Any]] = None,
) -> None:
    legacy_status = status or row.status or None
    composite = _composite_state_from_legacy_status(legacy_status)
    if annotation_state:
        composite["annotation_state"] = annotation_state
    if role_state:
        composite["role_state"] = role_state
    if execution_state:
        composite["execution_state"] = execution_state
    if status is None and annotation_state:
        legacy_status = _legacy_status_from_composite_state(
            composite.get("annotation_state"),
            composite.get("role_state"),
        )
    row.status = legacy_status or _legacy_status_from_composite_state(
        composite.get("annotation_state"),
        composite.get("role_state"),
    )
    row.annotation_state = composite.get("annotation_state")
    row.role_state = composite.get("role_state")
    row.execution_state = composite.get("execution_state")
    if region_scope is not None or not getattr(row, "region_scope_json", None):
        row.region_scope_json = encode_json(_normalize_region_scope(region_scope))
    row.state_schema_version = WORKFLOW_VOLUME_STATE_SCHEMA_VERSION


def _ensure_row_composite_state(row: WorkflowVolumeState) -> None:
    if (
        row.annotation_state
        and row.role_state
        and row.execution_state
        and row.region_scope_json
        and row.state_schema_version
    ):
        return
    _set_row_composite_state(
        row, status=row.status, region_scope=_row_region_scope(row)
    )


def _validate_composite_status_patch(
    *,
    status: Optional[str],
    annotation_state: Optional[str],
    role_state: Optional[str],
    execution_state: Optional[str],
) -> None:
    if annotation_state and annotation_state not in WORKFLOW_VOLUME_ANNOTATION_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"annotation_state must be one of {sorted(WORKFLOW_VOLUME_ANNOTATION_STATES)}",
        )
    if role_state and role_state not in WORKFLOW_VOLUME_ROLE_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"role_state must be one of {sorted(WORKFLOW_VOLUME_ROLE_STATES)}",
        )
    if execution_state and execution_state not in WORKFLOW_VOLUME_EXECUTION_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"execution_state must be one of {sorted(WORKFLOW_VOLUME_EXECUTION_STATES)}",
        )
    if status and annotation_state:
        projected = _legacy_status_from_composite_state(annotation_state, role_state)
        if projected != status:
            raise HTTPException(
                status_code=400,
                detail=(
                    "status and annotation_state disagree: "
                    f"{status!r} does not match {annotation_state!r}"
                ),
            )


def _volume_eligible_for_training_state(
    *,
    annotation_state: Optional[str],
    role_state: Optional[str],
    label_path: Optional[str],
    corrected_mask_path: Optional[str] = None,
) -> bool:
    return (
        annotation_state == "proofread_ground_truth"
        and role_state == "training_source"
        and bool(label_path or corrected_mask_path)
    )


def _volume_eligible_for_inference_state(
    *,
    annotation_state: Optional[str],
    role_state: Optional[str],
    image_path: Optional[str],
) -> bool:
    return (
        annotation_state == "image_only"
        and role_state == "inference_target"
        and bool(image_path)
    )


def _canonical_volume_state_item(row: WorkflowVolumeState) -> Dict[str, Any]:
    _ensure_row_composite_state(row)
    item = volume_state_to_dict(row)
    canonical = _canonical_project_progress_status(item.get("status"))
    item["legacy_status"] = item.get("status")
    item["canonical_status"] = canonical["status"]
    item["canonical_status_label"] = canonical["label"]
    item["annotation_state_label"] = _state_label(
        item.get("annotation_state"),
        WORKFLOW_VOLUME_ANNOTATION_STATES,
    )
    item["role_state_label"] = _state_label(
        item.get("role_state"),
        WORKFLOW_VOLUME_ROLE_STATES,
    )
    item["execution_state_label"] = _state_label(
        item.get("execution_state"),
        WORKFLOW_VOLUME_EXECUTION_STATES,
    )
    return item


def _canonical_volume_state_summary(rows: List[WorkflowVolumeState]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    labels: Dict[str, str] = {}
    for row in rows:
        _ensure_row_composite_state(row)
        status = (
            row.annotation_state
            or _canonical_project_progress_status(row.status)["status"]
        )
        counts[status] = counts.get(status, 0) + 1
        labels[status] = _state_label(status, WORKFLOW_VOLUME_ANNOTATION_STATES)
    return {
        "counts": counts,
        "labels": labels,
        "training_ready": sum(1 for row in rows if row.eligible_for_training),
        "inference_ready": sum(1 for row in rows if row.eligible_for_inference),
    }


VOLUME_STATE_MANUAL_SOURCES = {
    "manual",
    "manual_override",
    "user",
    "proofreading",
    "agent_confirmed",
}


def _workflow_volume_state_map(
    db: Session,
    workflow_id: int,
) -> Dict[str, WorkflowVolumeState]:
    rows = (
        db.query(WorkflowVolumeState)
        .filter(WorkflowVolumeState.workflow_id == workflow_id)
        .all()
    )
    return {row.volume_id: row for row in rows}


def _workflow_volume_state_is_manual(row: Optional[WorkflowVolumeState]) -> bool:
    if not row:
        return False
    return str(row.status_source or "").lower() in VOLUME_STATE_MANUAL_SOURCES


def _status_confidence_for_source(status_source: Optional[str]) -> float:
    source = str(status_source or "").lower()
    if source in VOLUME_STATE_MANUAL_SOURCES:
        return 1.0
    if source in {"correction_set", "path_marker"}:
        return 0.9
    return 0.65


def _volume_eligible_for_training(
    status: str,
    *,
    label_path: Optional[str],
    corrected_mask_path: Optional[str] = None,
) -> bool:
    composite = _composite_state_from_legacy_status(status)
    return _volume_eligible_for_training_state(
        annotation_state=composite.get("annotation_state"),
        role_state=composite.get("role_state"),
        label_path=label_path,
        corrected_mask_path=corrected_mask_path,
    )


def _volume_eligible_for_inference(
    status: str,
    *,
    image_path: Optional[str],
) -> bool:
    composite = _composite_state_from_legacy_status(status)
    return _volume_eligible_for_inference_state(
        annotation_state=composite.get("annotation_state"),
        role_state=composite.get("role_state"),
        image_path=image_path,
    )


def _volume_state_response(row: WorkflowVolumeState) -> WorkflowVolumeStateResponse:
    data = _canonical_volume_state_item(row)
    return WorkflowVolumeStateResponse(
        **data,
        status_label=_project_progress_status_label(row.status),
    )


def _volume_state_summary(rows: List[WorkflowVolumeState]) -> Dict[str, Any]:
    counts = {status: 0 for status in PROJECT_PROGRESS_STATUS_DEFINITIONS}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    tracked_total = len(rows) - counts.get("ignored", 0)
    return {
        "total": len(rows),
        "tracked_total": tracked_total,
        "ground_truth": counts.get("ground_truth", 0),
        "needs_proofreading": counts.get("needs_proofreading", 0),
        "missing_segmentation": counts.get("missing_segmentation", 0),
        "ignored": counts.get("ignored", 0),
        "training_ready": sum(1 for row in rows if row.eligible_for_training),
        "inference_ready": sum(1 for row in rows if row.eligible_for_inference),
        "canonical": _canonical_volume_state_summary(rows),
    }


def _volume_state_metadata_from_progress(volume: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": WORKFLOW_VOLUME_STATE_SCHEMA_VERSION,
        "status_label": volume.get("status_label"),
        "annotation_state": volume.get("annotation_state"),
        "role_state": volume.get("role_state"),
        "execution_state": volume.get("execution_state"),
        "region_scope": volume.get("region_scope"),
        "segmentation_kind": volume.get("segmentation_kind"),
        "evidence": volume.get("evidence") or [],
        "volume_set_id": volume.get("volume_set_id"),
        "volume_set_name": volume.get("volume_set_name"),
        "last_synced_from": "project_progress",
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
    }


def _apply_persisted_volume_state(
    volume: Dict[str, Any],
    persisted_states: Dict[str, WorkflowVolumeState],
) -> Dict[str, Any]:
    row = persisted_states.get(volume.get("id"))
    if not row:
        composite = _composite_state_from_legacy_status(volume.get("status"))
        volume["legacy_status"] = volume.get("status")
        canonical = _canonical_project_progress_status(volume.get("status"))
        volume["canonical_status"] = canonical["status"]
        volume["canonical_status_label"] = canonical["label"]
        volume["annotation_state"] = composite.get("annotation_state")
        volume["annotation_state_label"] = _state_label(
            volume.get("annotation_state"),
            WORKFLOW_VOLUME_ANNOTATION_STATES,
        )
        volume["role_state"] = composite.get("role_state")
        volume["role_state_label"] = _state_label(
            volume.get("role_state"),
            WORKFLOW_VOLUME_ROLE_STATES,
        )
        volume["execution_state"] = composite.get("execution_state")
        volume["execution_state_label"] = _state_label(
            volume.get("execution_state"),
            WORKFLOW_VOLUME_EXECUTION_STATES,
        )
        volume["region_scope"] = _normalize_region_scope(volume.get("region_scope"))
        volume["state_schema_version"] = WORKFLOW_VOLUME_STATE_SCHEMA_VERSION
        volume["eligible_for_training"] = _volume_eligible_for_training(
            volume.get("status"),
            label_path=volume.get("segmentation_path"),
        )
        volume["eligible_for_inference"] = _volume_eligible_for_inference(
            volume.get("status"),
            image_path=volume.get("image_path"),
        )
        return volume

    _ensure_row_composite_state(row)
    volume["volume_state_id"] = row.id
    if _workflow_volume_state_is_manual(row):
        volume["status"] = row.status
        volume["status_label"] = _project_progress_status_label(row.status)
        volume["status_source"] = row.status_source
    volume["legacy_status"] = volume.get("status")
    canonical = _canonical_project_progress_status(volume.get("status"))
    volume["canonical_status"] = canonical["status"]
    volume["canonical_status_label"] = canonical["label"]
    volume["annotation_state"] = row.annotation_state
    volume["annotation_state_label"] = _state_label(
        row.annotation_state,
        WORKFLOW_VOLUME_ANNOTATION_STATES,
    )
    volume["role_state"] = row.role_state
    volume["role_state_label"] = _state_label(
        row.role_state, WORKFLOW_VOLUME_ROLE_STATES
    )
    volume["execution_state"] = row.execution_state
    volume["execution_state_label"] = _state_label(
        row.execution_state,
        WORKFLOW_VOLUME_EXECUTION_STATES,
    )
    volume["region_scope"] = _row_region_scope(row)
    volume["state_schema_version"] = row.state_schema_version
    volume["eligible_for_training"] = bool(row.eligible_for_training)
    volume["eligible_for_inference"] = bool(row.eligible_for_inference)
    if row.note:
        volume["note"] = row.note
    return volume


def _sync_volume_states_from_progress(
    db: Session,
    workflow: WorkflowSession,
    progress: Dict[str, Any],
) -> Dict[str, WorkflowVolumeState]:
    existing = _workflow_volume_state_map(db, workflow.id)
    synced: Dict[str, WorkflowVolumeState] = dict(existing)
    for volume in progress.get("volumes") or []:
        volume_id = str(volume.get("id") or "")
        if not volume_id:
            continue
        row = existing.get(volume_id)
        if row is None:
            row = WorkflowVolumeState(
                workflow_id=workflow.id,
                volume_id=volume_id,
            )
            db.add(row)
            db.flush()
        manual_status = _workflow_volume_state_is_manual(row)
        status_source = str(volume.get("status_source") or "derived")
        if not manual_status:
            _set_row_composite_state(
                row,
                status=volume.get("status") or "missing_segmentation",
                annotation_state=volume.get("annotation_state"),
                role_state=volume.get("role_state"),
                execution_state=volume.get("execution_state"),
                region_scope=volume.get("region_scope"),
            )
            row.status_source = status_source
            row.status_confidence = _status_confidence_for_source(status_source)
        else:
            _ensure_row_composite_state(row)
        row.name = volume.get("name")
        row.project_root = volume.get("project_root")
        row.volume_set_id = volume.get("volume_set_id")
        row.volume_set_name = volume.get("volume_set_name")
        row.image_path = volume.get("image_path")

        segmentation_path = volume.get("segmentation_path")
        if volume.get("segmentation_kind") == "prediction":
            row.prediction_path = segmentation_path
        else:
            row.label_path = segmentation_path
        metadata = decode_json(row.metadata_json)
        metadata = {
            **metadata,
            **_volume_state_metadata_from_progress(volume),
        }
        if "note" in volume and volume.get("note") is not None and not row.note:
            row.note = str(volume.get("note") or "")
        if metadata.get("eligibility_source") != "manual":
            _ensure_row_composite_state(row)
            row.eligible_for_training = _volume_eligible_for_training_state(
                annotation_state=row.annotation_state,
                role_state=row.role_state,
                label_path=row.label_path,
                corrected_mask_path=row.corrected_mask_path,
            )
            row.eligible_for_inference = _volume_eligible_for_inference_state(
                annotation_state=row.annotation_state,
                role_state=row.role_state,
                image_path=row.image_path,
            )
        row.metadata_json = encode_json(metadata)
        synced[volume_id] = row
    return synced


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
    observation = project_observation or _observe_workflow_project(
        db, workflow, user_id
    )
    metadata = decode_json(workflow.metadata_json)
    overrides = metadata.get("project_progress_overrides")
    overrides = overrides if isinstance(overrides, dict) else {}
    correction_evidence = _project_progress_correction_evidence(db, workflow)
    persisted_states = _workflow_volume_state_map(db, workflow.id)
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
                **_composite_state_from_legacy_status(status),
                "region_scope": _normalize_region_scope(None),
                "state_schema_version": WORKFLOW_VOLUME_STATE_SCHEMA_VERSION,
                "project_root": project_root,
                "volume_set_id": volume_set.get("id"),
                "volume_set_name": volume_set.get("name"),
                "image_path": image_path,
                "segmentation_path": segmentation_path,
                "segmentation_kind": segmentation_kind,
                "evidence": evidence,
                "note": None,
            }
            volume = _apply_project_progress_overrides(volume, overrides)
            volume = _apply_persisted_volume_state(volume, persisted_states)
            volumes.append(volume)

    if not volumes and (workflow.image_path or workflow.dataset_path):
        image_path = _normalize_absolute_path(
            workflow.image_path or workflow.dataset_path
        )
        project_root = _normalize_absolute_path(workflow.dataset_path) or str(
            pathlib.Path(image_path).parent
        )
        segmentation_path = (
            workflow.label_path or workflow.mask_path or workflow.inference_output_path
        )
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
            **_composite_state_from_legacy_status(status),
            "region_scope": _normalize_region_scope(None),
            "state_schema_version": WORKFLOW_VOLUME_STATE_SCHEMA_VERSION,
            "project_root": project_root,
            "volume_set_id": "workflow-current",
            "volume_set_name": "Current workflow",
            "image_path": image_path,
            "segmentation_path": segmentation_path,
            "segmentation_kind": "label" if segmentation_path else None,
            "evidence": evidence,
            "note": None,
        }
        fallback = _apply_project_progress_overrides(fallback, overrides)
        fallback = _apply_persisted_volume_state(fallback, persisted_states)
        volumes.append(fallback)

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
        "completion_pct": (
            round((good_count / tracked_total) * 100, 1) if tracked_total else 0
        ),
        "segmentation_coverage_pct": (
            round((segmented_count / tracked_total) * 100, 1) if tracked_total else 0
        ),
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
        "composite_state_definitions": {
            "annotation_state": WORKFLOW_VOLUME_ANNOTATION_STATES,
            "role_state": WORKFLOW_VOLUME_ROLE_STATES,
            "execution_state": WORKFLOW_VOLUME_EXECUTION_STATES,
        },
        "volumes": volumes,
    }
    if persist_snapshot:
        persisted_states = _sync_volume_states_from_progress(db, workflow, progress)
        for volume in volumes:
            _apply_persisted_volume_state(volume, persisted_states)
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
                        "annotation_state",
                        "role_state",
                        "execution_state",
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
            "then the workflow overview can count proofread, unproofread, and missing segmentations."
        )
    volumes = progress.get("volumes") or []

    def names_for(status: str, limit: int = 8) -> str:
        names = [
            str(volume.get("name") or volume.get("id") or "").strip()
            for volume in volumes
            if volume.get("status") == status
        ]
        names = [name for name in names if name]
        if not names:
            return ""
        suffix = "" if len(names) <= limit else f", plus {len(names) - limit} more"
        return ", ".join(names[:limit]) + suffix

    ground_truth_names = names_for("ground_truth")
    proofread_names = names_for("needs_proofreading")
    missing_names = names_for("missing_segmentation")
    grouped = []
    if ground_truth_names:
        grouped.append(f"ready for training: {ground_truth_names}")
    if proofread_names:
        grouped.append(f"proofread before training: {proofread_names}")
    if missing_names:
        grouped.append(f"image-only/inference targets: {missing_names}")
    grouped_text = " " + "; ".join(grouped) + "." if grouped else ""
    return (
        "I checked the workflow overview. "
        f"It has {total} tracked image volume(s): "
        f"{summary.get('ground_truth', 0)} fully good ground-truth volume(s), "
        f"{summary.get('needs_proofreading', 0)} with segmentations that still need proofreading, "
        f"and {summary.get('missing_segmentation', 0)} with no segmentation yet. "
        f"Completion is {summary.get('completion_pct', 0)}%."
        f"{grouped_text}"
    )


WORKFLOW_OVERVIEW_PHASES = [
    ("setup", "Setup", "files"),
    ("inspect", "Inspect", "visualization"),
    ("proofread", "Proofread", "mask-proofreading"),
    ("train", "Train", "training"),
    ("infer", "Infer", "inference"),
    ("evaluate", "Evaluate", "project-progress"),
]


def _workflow_overview_active_runs(
    db: Session,
    workflow_id: int,
) -> List[WorkflowModelRun]:
    return (
        db.query(WorkflowModelRun)
        .filter(
            WorkflowModelRun.workflow_id == workflow_id,
            WorkflowModelRun.status.in_(["pending", "running", "submitted"]),
        )
        .order_by(WorkflowModelRun.updated_at.desc(), WorkflowModelRun.id.desc())
        .all()
    )


def _workflow_overview_recent_events(
    db: Session,
    workflow_id: int,
    *,
    limit: int = 8,
) -> List[WorkflowEvent]:
    return (
        db.query(WorkflowEvent)
        .filter(WorkflowEvent.workflow_id == workflow_id)
        .order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc())
        .limit(limit)
        .all()
    )


def _workflow_overview_phase(
    workflow: WorkflowSession,
    progress: Dict[str, Any],
    active_runs: List[WorkflowModelRun],
    events: List[WorkflowEvent],
) -> Dict[str, Any]:
    summary = progress.get("summary") or {}
    total = int(summary.get("tracked_total") or summary.get("total") or 0)
    ground_truth = int(summary.get("ground_truth") or 0)
    needs_proofreading = int(summary.get("needs_proofreading") or 0)
    missing_segmentation = int(summary.get("missing_segmentation") or 0)

    active_training = next(
        (run for run in active_runs if run.run_type == "training"),
        None,
    )
    active_inference = next(
        (run for run in active_runs if run.run_type == "inference"),
        None,
    )
    if active_training:
        return {
            "phase": "train",
            "reason": "A training run is active.",
        }
    if active_inference:
        return {
            "phase": "infer",
            "reason": "An inference run is active.",
        }

    if not (workflow.dataset_path or workflow.image_path):
        return {
            "phase": "setup",
            "reason": "No project data is mounted yet.",
        }
    if total <= 0:
        return {
            "phase": "inspect",
            "reason": "Project data is mounted, but no tracked volumes are confirmed yet.",
        }
    if workflow.stage == "proofreading" or needs_proofreading > 0:
        return {
            "phase": "proofread",
            "reason": f"{needs_proofreading} volume(s) still need proofreading.",
        }
    if workflow.stage == "retraining_staged" or (
        ground_truth > 0 and missing_segmentation > 0
    ):
        return {
            "phase": "train",
            "reason": f"{ground_truth} ground-truth volume(s) can train a model for {missing_segmentation} image-only target(s).",
        }
    if workflow.stage == "inference" or missing_segmentation > 0:
        return {
            "phase": "infer",
            "reason": f"{missing_segmentation} volume(s) need model predictions.",
        }
    if workflow.stage == "evaluation" or any(
        event.event_type.startswith("evaluation.") for event in events
    ):
        return {
            "phase": "evaluate",
            "reason": "Predictions and workflow evidence are ready to compare.",
        }
    return {
        "phase": "inspect",
        "reason": "The project has tracked volumes and is ready for inspection.",
    }


def _workflow_overview_blockers(
    workflow: WorkflowSession,
    progress: Dict[str, Any],
    active_runs: List[WorkflowModelRun],
) -> List[WorkflowOverviewBlocker]:
    summary = progress.get("summary") or {}
    total = int(summary.get("tracked_total") or summary.get("total") or 0)
    ground_truth = int(summary.get("ground_truth") or 0)
    needs_proofreading = int(summary.get("needs_proofreading") or 0)
    missing_segmentation = int(summary.get("missing_segmentation") or 0)
    blockers: List[WorkflowOverviewBlocker] = []

    if not (workflow.dataset_path or workflow.image_path):
        blockers.append(
            WorkflowOverviewBlocker(
                id="project_missing",
                label="No project mounted",
                detail="Mount or choose a project directory before the workflow can inspect volumes.",
                severity="blocking",
                target_view="files",
            )
        )
    elif total <= 0:
        blockers.append(
            WorkflowOverviewBlocker(
                id="no_tracked_volumes",
                label="No tracked volumes",
                detail="The mounted project did not produce volume-level image entries yet.",
                severity="blocking",
                target_view="files",
            )
        )
    if missing_segmentation > 0 and not workflow.checkpoint_path and ground_truth <= 0:
        blockers.append(
            WorkflowOverviewBlocker(
                id="no_checkpoint_or_training_data",
                label="Missing checkpoint or ground truth",
                detail="Image-only volumes need either a checkpoint for inference or proofread ground truth for training.",
                severity="blocking",
                target_view="training",
            )
        )
    elif missing_segmentation > 0 and not workflow.checkpoint_path:
        blockers.append(
            WorkflowOverviewBlocker(
                id="checkpoint_missing",
                label="No checkpoint selected",
                detail="Train a model or select a checkpoint before running inference on image-only volumes.",
                severity="warning",
                target_view="training",
            )
        )
    if needs_proofreading > 0:
        blockers.append(
            WorkflowOverviewBlocker(
                id="draft_masks_need_review",
                label="Draft masks need review",
                detail=f"{needs_proofreading} volume(s) have masks or segmentations that are not marked ground truth.",
                severity="warning",
                target_view="mask-proofreading",
            )
        )
    if active_runs:
        blockers.append(
            WorkflowOverviewBlocker(
                id="runtime_active",
                label="Run in progress",
                detail="Wait for the active run to finish before launching another expensive job.",
                severity="info",
                target_view=(
                    "training" if active_runs[0].run_type == "training" else "inference"
                ),
            )
        )
    return blockers


def _workflow_overview_actions(
    workflow: WorkflowSession,
    progress: Dict[str, Any],
    active_runs: List[WorkflowModelRun],
) -> List[WorkflowOverviewAction]:
    if active_runs:
        target_view = (
            "training" if active_runs[0].run_type == "training" else "inference"
        )
        return [
            WorkflowOverviewAction(
                id="check-active-run",
                label="Check active run",
                detail=f"Open {active_runs[0].run_type} runtime details.",
                target_view=target_view,
                priority="high",
                client_effects={"navigate_to": target_view},
            )
        ]
    summary = progress.get("summary") or {}
    total = int(summary.get("tracked_total") or summary.get("total") or 0)
    ground_truth = int(summary.get("ground_truth") or 0)
    needs_proofreading = int(summary.get("needs_proofreading") or 0)
    missing_segmentation = int(summary.get("missing_segmentation") or 0)
    actions: List[WorkflowOverviewAction] = []
    if not (workflow.dataset_path or workflow.image_path):
        actions.append(
            WorkflowOverviewAction(
                id="mount-project",
                label="Mount a project",
                detail="Choose a project directory so the app can inspect images, masks, and configs.",
                target_view="files",
                priority="high",
                client_effects={"navigate_to": "files"},
            )
        )
    elif total <= 0:
        actions.append(
            WorkflowOverviewAction(
                id="inspect-files",
                label="Inspect files",
                detail="Open the file view and confirm which folders contain image and mask data.",
                target_view="files",
                priority="high",
                client_effects={"navigate_to": "files"},
            )
        )
    if needs_proofreading > 0:
        actions.append(
            WorkflowOverviewAction(
                id="proofread-draft-masks",
                label="Proofread draft masks",
                detail=f"Review {needs_proofreading} volume(s) before treating them as ground truth.",
                target_view="mask-proofreading",
                priority="high" if ground_truth <= 0 else "normal",
                client_effects={"navigate_to": "mask-proofreading"},
            )
        )
    if ground_truth > 0 and missing_segmentation > 0:
        actions.append(
            WorkflowOverviewAction(
                id="train-from-ground-truth",
                label="Train from ground truth",
                detail=f"Use {ground_truth} ground-truth volume(s), then infer {missing_segmentation} image-only target(s).",
                target_view="training",
                priority="high",
                client_effects={"navigate_to": "training"},
            )
        )
    if workflow.checkpoint_path and missing_segmentation > 0:
        actions.append(
            WorkflowOverviewAction(
                id="run-inference-on-missing",
                label="Run inference on missing masks",
                detail=f"Use the selected checkpoint for {missing_segmentation} image-only volume(s).",
                target_view="inference",
                priority="high",
                client_effects={"navigate_to": "inference"},
            )
        )
    if total > 0:
        actions.append(
            WorkflowOverviewAction(
                id="review-workflow-map",
                label="Review workflow map",
                detail="Open the volume table and update statuses or next actions.",
                target_view="project-progress",
                priority="normal",
                client_effects={"navigate_to": "project-progress"},
            )
        )
    return actions[:4]


def _workflow_overview_stages(
    phase: str,
    workflow: WorkflowSession,
    progress: Dict[str, Any],
    active_runs: List[WorkflowModelRun],
    events: List[WorkflowEvent],
) -> List[WorkflowOverviewStage]:
    summary = progress.get("summary") or {}
    total = int(summary.get("tracked_total") or summary.get("total") or 0)
    ground_truth = int(summary.get("ground_truth") or 0)
    missing_segmentation = int(summary.get("missing_segmentation") or 0)
    needs_proofreading = int(summary.get("needs_proofreading") or 0)
    phase_ids = [item[0] for item in WORKFLOW_OVERVIEW_PHASES]
    current_index = phase_ids.index(phase) if phase in phase_ids else 0
    training_seen = any(
        run.run_type == "training" and run.status in {"running", "completed"}
        for run in active_runs
    ) or any(event.event_type.startswith("training.") for event in events)
    inference_seen = (
        any(
            run.run_type == "inference" and run.status in {"running", "completed"}
            for run in active_runs
        )
        or bool(workflow.inference_output_path)
        or any(event.event_type.startswith("inference.") for event in events)
    )
    evaluation_seen = any(
        event.event_type.startswith("evaluation.") for event in events
    )
    complete_by_phase = {
        "setup": bool(workflow.dataset_path or workflow.image_path),
        "inspect": total > 0,
        "proofread": total > 0 and needs_proofreading == 0 and ground_truth > 0,
        "train": bool(
            workflow.checkpoint_path or workflow.training_output_path or training_seen
        ),
        "infer": missing_segmentation == 0 or inference_seen,
        "evaluate": evaluation_seen,
    }
    stages: List[WorkflowOverviewStage] = []
    for index, (stage_id, label, target_view) in enumerate(WORKFLOW_OVERVIEW_PHASES):
        complete = bool(complete_by_phase.get(stage_id))
        blocked = index < current_index and not complete
        stages.append(
            WorkflowOverviewStage(
                id=stage_id,
                label=label,
                target_view=target_view,
                complete=complete,
                current=stage_id == phase,
                blocked=blocked,
                detail=None,
            )
        )
    return stages


def _build_workflow_overview(
    db: Session,
    workflow: WorkflowSession,
    *,
    user_id: int,
    refresh: bool = True,
) -> WorkflowOverviewResponse:
    progress = _build_workflow_project_progress(
        db,
        workflow,
        user_id=user_id,
        persist_snapshot=refresh,
    )
    active_runs = _workflow_overview_active_runs(db, workflow.id)
    recent_events = _workflow_overview_recent_events(db, workflow.id)
    phase_data = _workflow_overview_phase(
        workflow, progress, active_runs, recent_events
    )
    phase = phase_data["phase"]
    phase_lookup = {item[0]: item for item in WORKFLOW_OVERVIEW_PHASES}
    phase_item = phase_lookup.get(phase, WORKFLOW_OVERVIEW_PHASES[0])
    phase_index = [item[0] for item in WORKFLOW_OVERVIEW_PHASES].index(phase_item[0])
    return WorkflowOverviewResponse(
        workflow_id=workflow.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        project_name=progress.get("project_name") or workflow.title,
        workflow_stage=workflow.stage,
        phase=phase,
        phase_label=phase_item[1],
        phase_reason=phase_data["reason"],
        phase_index=phase_index,
        volume_summary=progress.get("summary") or {},
        project_progress=WorkflowProjectProgressResponse(**progress),
        stages=_workflow_overview_stages(
            phase,
            workflow,
            progress,
            active_runs,
            recent_events,
        ),
        blockers=_workflow_overview_blockers(workflow, progress, active_runs),
        recommended_next_actions=_workflow_overview_actions(
            workflow,
            progress,
            active_runs,
        ),
        active_runs=[
            WorkflowOverviewRun(**model_run_to_dict(run)) for run in active_runs
        ],
        recent_events=[_event_response(event) for event in reversed(recent_events)],
    )


TASK_FAMILY_PRESETS = {
    "tapereader_xri_fiber": {
        "label": "TapeReader XRI fibre instance segmentation",
        "aliases": ["xri fibre", "xri fiber", "cytotape", "tapereader"],
        "expected_inputs": ["XRI raw TIFF stacks", "fibre instance masks"],
        "workflow_loop": [
            "inspect XRI volumes",
            "train on confirmed fibre masks",
            "infer image-only volumes",
            "proofread draft or predicted masks",
            "promote proofread masks back to training",
        ],
        "training_rule": "Use only confirmed ground-truth/proofread masks as labels.",
        "caveat": "The paper-faithful PyTC barcode target requires the TapeReader barcode branch.",
    },
    "mitoem_instance": {
        "label": "Mitochondria instance segmentation",
        "aliases": ["mitochondria instance", "mitoem", "mitochondria"],
        "expected_inputs": ["EM raw volumes", "mitochondria instance masks"],
        "workflow_loop": [
            "inspect raw and mask pairs",
            "train on ground-truth masks",
            "run inference on image-only volumes",
            "proofread instance errors",
            "evaluate and retrain",
        ],
        "training_rule": "Use ground-truth or explicitly proofread masks as labels.",
    },
    "generic_volumetric": {
        "label": "Volumetric segmentation",
        "aliases": [],
        "expected_inputs": ["image volumes", "optional labels or predictions"],
        "workflow_loop": [
            "inspect files",
            "confirm labels",
            "visualize data",
            "train or infer after approval",
        ],
        "training_rule": "Ask the user before treating masks as training labels.",
    },
}


def _task_family_preset_for_context(context: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join(
        str(context.get(key) or "")
        for key in (
            "task_family",
            "target_structure",
            "imaging_modality",
            "freeform_note",
        )
    ).lower()
    for key, preset in TASK_FAMILY_PRESETS.items():
        if any(alias in text for alias in preset.get("aliases", [])):
            return {"id": key, **preset}
    return {"id": "generic_volumetric", **TASK_FAMILY_PRESETS["generic_volumetric"]}


def _workflow_memory_artifact_index(workflow: WorkflowSession) -> Dict[str, Any]:
    paths = {
        "dataset": workflow.dataset_path,
        "image": workflow.image_path,
        "label": workflow.label_path,
        "mask": workflow.mask_path,
        "prediction": workflow.inference_output_path,
        "checkpoint": workflow.checkpoint_path,
        "config": workflow.config_path,
        "corrected_mask": workflow.corrected_mask_path,
        "training_output": workflow.training_output_path,
    }
    return {
        "canonical_paths": {key: value for key, value in paths.items() if value},
        "registered_artifacts": [
            artifact_to_dict(artifact)
            for artifact in getattr(workflow, "artifacts", []) or []
        ],
    }


def _dedupe_user_status_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    last_stage: Optional[str] = None
    for event in events:
        stage = event.get("stage")
        if stage == last_stage:
            continue
        deduped.append(event)
        last_stage = stage
    return deduped


def _build_workflow_project_memory(
    db: Session,
    workflow: WorkflowSession,
    *,
    user_id: int,
    refresh: bool = True,
) -> Dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    progress = _build_workflow_project_progress(
        db,
        workflow,
        user_id=user_id,
        persist_snapshot=refresh,
    )
    volume_rows = (
        db.query(WorkflowVolumeState)
        .filter(WorkflowVolumeState.workflow_id == workflow.id)
        .order_by(WorkflowVolumeState.volume_id.asc())
        .all()
    )
    runs = (
        db.query(WorkflowModelRun)
        .filter(WorkflowModelRun.workflow_id == workflow.id)
        .order_by(WorkflowModelRun.created_at.asc(), WorkflowModelRun.id.asc())
        .all()
    )
    versions = (
        db.query(WorkflowModelVersion)
        .filter(WorkflowModelVersion.workflow_id == workflow.id)
        .order_by(WorkflowModelVersion.created_at.asc(), WorkflowModelVersion.id.asc())
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
    recent_events = _workflow_overview_recent_events(db, workflow.id, limit=20)
    metadata = decode_json(workflow.metadata_json)
    project_context = _workflow_project_context(workflow)
    preset = _task_family_preset_for_context(project_context)
    recent_event_dicts = [event_to_dict(event) for event in reversed(recent_events)]
    recent_event_ids = [
        int(event.get("id"))
        for event in recent_event_dicts
        if isinstance(event.get("id"), int)
    ]
    progress_generated_at = (
        progress.get("generated_at") if isinstance(progress, dict) else None
    )
    memory = {
        "schema_version": "pytc-project-memory/v1",
        "workflow_id": workflow.id,
        "generated_at": generated_at,
        "freshness": {
            "project_progress": {
                "state": "fresh" if refresh else "read_only",
                "generated_at": progress_generated_at or generated_at,
                "source": "project_progress_builder",
            },
            "volume_states": {
                "state": "fresh",
                "generated_at": generated_at,
                "row_count": len(volume_rows),
                "source": "workflow_volume_states",
            },
            "assistant_context": {
                "state": "fresh",
                "generated_at": generated_at,
                "recent_event_count": len(recent_event_dicts),
                "source_event_high_watermark": (
                    max(recent_event_ids) if recent_event_ids else None
                ),
            },
        },
        "project_facts": {
            "project_name": workflow.title,
            "stage": workflow.stage,
            "dataset_path": workflow.dataset_path,
            "project_context": project_context,
            "task_family_preset": preset,
            "context_facts": metadata.get("context_facts") or [],
            "project_audit": metadata.get("project_audit"),
        },
        "artifact_index": _workflow_memory_artifact_index(workflow),
        "volume_states": {
            "summary": _volume_state_summary(volume_rows),
            "items": [_canonical_volume_state_item(row) for row in volume_rows],
            "progress_snapshot": progress,
        },
        "run_history": [model_run_to_dict(run) for run in runs],
        "model_versions": [model_version_to_dict(version) for version in versions],
        "evaluation_results": [
            evaluation_result_to_dict(result) for result in evaluation_results
        ],
        "user_status_changes": [
            {
                "at": event["at"],
                "event_id": event["event_id"],
                "stage": event["stage"],
                "event_type": event["event_type"],
                "summary": event["summary"],
            }
            for event in _dedupe_user_status_events(
                [
                    {
                        "at": (
                            event.created_at.isoformat()
                            if hasattr(event, "created_at")
                            else None
                        ),
                        "event_id": event.id,
                        "stage": event.stage,
                        "event_type": event.event_type,
                        "summary": event.summary,
                    }
                    for event in reversed(
                        sorted(
                            recent_events,
                            key=lambda item: (item.created_at or datetime.min, item.id),
                        )
                    )
                    if event.actor == "user" and event.stage
                ]
            )
        ],
        "evidence_events": recent_event_dicts,
    }
    return memory


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
    configured = os.getenv("PYTC_TRAINING_SUBSET_ROOT")
    if not configured:
        return pathlib.Path(project_root).expanduser() / ".pytc_training_subsets"
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
    output_path.mkdir(parents=True, exist_ok=True)
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
            category="checked",
            **_agent_trace_kwargs(ORCHESTRATOR_AGENT),
            data={
                "schema_version": "agent_trace/v1",
                "workflow_id": workflow.id,
                "stage": workflow.stage,
                "has_image": bool(workflow.image_path or workflow.dataset_path),
                "has_label": bool(workflow.label_path or workflow.mask_path),
                "has_checkpoint": bool(workflow.checkpoint_path),
                "config_path": workflow.config_path,
            },
            evidence_refs=[
                {"kind": "workflow_session", "id": workflow.id},
            ],
        )
    ]
    roots = project_observation.get("roots") or []
    volume_sets = project_observation.get("volume_sets") or []
    if roots:
        root_names = ", ".join(
            str(root.get("name") or root.get("path")) for root in roots[:2]
        )
        trace.append(
            AgentTraceItem(
                label="Checked project files",
                detail=(
                    f"Scanned {root_names}; found {len(volume_sets)} image/seg set(s)."
                ),
                category="checked",
                **_agent_trace_kwargs(WORKFLOW_SUBAGENTS["data_agent"]),
                data={
                    "root_count": len(roots),
                    "roots": [
                        {
                            "name": root.get("name"),
                            "path": root.get("path"),
                            "entry_count": root.get("entry_count"),
                        }
                        for root in roots[:5]
                    ],
                    "volume_set_count": len(volume_sets),
                    "volume_sets": [
                        {
                            "id": item.get("id"),
                            "name": item.get("name"),
                            "image_count": item.get("image_count"),
                            "label_count": item.get("label_count"),
                        }
                        for item in volume_sets[:5]
                    ],
                },
                evidence_refs=[
                    {"kind": "project_observation", "path": root.get("path")}
                    for root in roots[:5]
                    if root.get("path")
                ],
            )
        )
    elif project_observation.get("errors"):
        trace.append(
            AgentTraceItem(
                label="Checked project files",
                detail="Tried to inspect the project folder, but the scan failed.",
                status="warning",
                category="blocked_by",
                **_agent_trace_kwargs(WORKFLOW_SUBAGENTS["data_agent"]),
                data={"errors": project_observation.get("errors") or []},
            )
        )
    else:
        trace.append(
            AgentTraceItem(
                label="Checked project files",
                detail="No mounted project root was available to scan.",
                status="missing",
                category="blocked_by",
                **_agent_trace_kwargs(WORKFLOW_SUBAGENTS["data_agent"]),
                data={"reason": "no_mounted_project_root"},
            )
        )
    trace.append(
        AgentTraceItem(
            label="Prepared response",
            detail=(
                f"Intent: {intent}; " f"{len(actions)} runnable app card(s) prepared."
            ),
            category="proposed" if actions else "inferred",
            **_agent_trace_kwargs(ORCHESTRATOR_AGENT),
            data={
                "intent": intent,
                "orchestrator_agent": ORCHESTRATOR_AGENT,
                "action_count": len(actions),
                "actions": [
                    {
                        "id": action.id,
                        "specialist_agent": action.specialist_agent,
                        "action_type": action.action_type,
                        "risk_tier": action.risk_tier,
                        "requires_approval": action.requires_approval,
                        "target": action.target,
                    }
                    for action in actions
                ],
            },
            evidence_refs=[
                {"kind": "action_card", "id": action.id} for action in actions
            ],
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
        return (
            " x ".join(_format_scale_number(float(item)) for item in value[:3]) + " nm"
        )
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


def _query_mentions_volume_id(lower_query: str) -> bool:
    return bool(re.search(r"\b\d+_\d+\b", lower_query))


def _query_explicitly_mutates_project_context(lower_query: str) -> bool:
    explicit_phrases = [
        "set project context",
        "update project context",
        "change project context",
        "save project context",
        "use project context",
        "set context",
        "update context",
        "change context",
        "save context",
        "set voxel",
        "update voxel",
        "change voxel",
        "use voxel",
        "voxel size is",
        "voxel spacing is",
        "resolution is",
        "set resolution",
        "update resolution",
        "change resolution",
        "use resolution",
        "this is ",
        "these are ",
        "we are ",
        "we're ",
        "the dataset is",
        "the project is",
    ]
    return any(phrase in lower_query for phrase in explicit_phrases)


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
    project_context = metadata.get("project_context")
    if not isinstance(project_context, dict):
        project_context = {}
    project_context["voxel_size_nm"] = scales_nm
    project_context["voxel_size_source"] = "workflow_agent_visualization_scales"
    metadata["project_context"] = project_context
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
        ("X-ray / XRI volumetric microscopy", ["xri", "x-ray", "xray"]),
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
        ("CytoTape fibres", ["cytotape", "fiber", "fibers", "fibre", "fibres"]),
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

    if any(term in lower for term in ["xri", "x-ray", "xray"]) and any(
        term in lower for term in ["cytotape", "fiber", "fibers", "fibre", "fibres"]
    ):
        context["task_family"] = "XRI fibre instance segmentation"
    elif any(term in lower for term in ["mitochondria", "mitochondrion", "mito"]):
        context["task_family"] = "mitochondria instance segmentation"
    elif any(term in lower for term in ["synapse", "synapses", "cleft", "clefts"]):
        context["task_family"] = "synapse segmentation"
    elif any(term in lower for term in ["nucleus", "nuclei"]):
        context["task_family"] = "nuclei instance segmentation"

    if any(
        phrase in lower
        for phrase in [
            "mixed masks",
            "some masks",
            "some image-only",
            "some image only",
            "partial masks",
            "partially labeled",
            "partially labelled",
        ]
    ):
        context["mask_status"] = "mixed: some masks, some image-only volumes"
    elif any(
        phrase in lower
        for phrase in [
            "ground truth",
            "ground-truth",
            "fully proofread",
            "curated masks",
        ]
    ):
        context["mask_status"] = "ground-truth masks available"

    if any(
        phrase in lower
        for phrase in [
            "train only on ground truth",
            "train only on ground-truth",
            "only train on confirmed",
            "only use confirmed",
        ]
    ):
        context["training_policy"] = "train only on confirmed ground-truth masks"

    if any(
        term in lower
        for term in ["fast", "quick", "smoke", "prototype", "speed", "care about speed"]
    ):
        context["optimization_priority"] = "speed"
    elif any(term in lower for term in ["accurate", "accuracy", "quality", "best"]):
        context["optimization_priority"] = "accuracy"

    voxel_size_nm = (
        _parse_visualization_scales_from_query(query)
        if _query_wants_visualization_scales(lower)
        or _query_explicitly_mutates_project_context(lower)
        else None
    )
    if voxel_size_nm and not _query_mentions_volume_id(lower):
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
            "workflow type",
        ]
    return (
        f"Before I {action_label}, I need one or two project details first: "
        f"{', '.join(missing[:3])}. "
        "A casual answer is fine, like: XRI fibres at 40 x 16.3 x 16.3 nm, "
        "or EM mitochondria instance masks."
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
    if context.get("task_family"):
        summary.append(context["task_family"])
    voxel_size = _format_voxel_size_nm(context.get("voxel_size_nm"))
    if voxel_size:
        summary.append(f"{voxel_size} resolution")
    missing = _project_context_missing_fields(workflow)
    if missing:
        return (
            f"Got it, I saved {', '.join(summary) or 'that partial context'}. "
            f"I still need {', '.join(missing)} before I choose the next workflow step."
        )
    summary_text = ", ".join(summary) if summary else "the project defaults"
    return (
        f"Got it, I saved {summary_text}. "
        f"From here I would probably {_lower_first(_strip_sentence_period(recommendation.decision))}."
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
    lines = [f"We are working in `{project_name}`."]
    if image_label != "not set":
        if mask_label != "not set":
            lines.append(
                f"I have image data at `{image_label}` and mask/result data at `{mask_label}`."
            )
        else:
            lines.append(
                f"I have image data at `{image_label}`, but no mask/result path is set yet."
            )
    if project_context.get("imaging_modality") or project_context.get(
        "target_structure"
    ):
        context_bits = [
            project_context.get("imaging_modality"),
            project_context.get("target_structure"),
            project_context.get("task_family"),
            project_context.get("optimization_priority"),
            _format_voxel_size_nm(project_context.get("voxel_size_nm")),
        ]
        lines.append(
            "The project context I am using is "
            + ", ".join(str(bit) for bit in context_bits if bit)
            + "."
        )
    metadata = decode_json(workflow.metadata_json)
    progress = (
        metadata.get("project_progress_snapshot") if isinstance(metadata, dict) else {}
    )
    summary = progress.get("summary") if isinstance(progress, dict) else {}
    if isinstance(summary, dict) and (
        summary.get("tracked_total") or summary.get("total")
    ):
        total = summary.get("tracked_total") or summary.get("total")
        lines.append(
            f"The workflow tracker has {total} volume(s): "
            f"{summary.get('ground_truth', 0)} fully good, "
            f"{summary.get('needs_proofreading', 0)} needing proofreading, "
            f"{summary.get('missing_segmentation', 0)} without segmentation."
        )
    lines.append(
        f"My next useful move would be to {_lower_first(_strip_sentence_period(recommendation.decision))}."
    )
    return "\n".join(lines)


def _format_informational_followup_response(
    workflow: WorkflowSession,
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    context = _workflow_project_context(workflow)
    lines = [
        f"I would probably {_lower_first(_strip_sentence_period(recommendation.decision))}.",
    ]
    if recommendation.rationale:
        lines.append(
            f"The reason is pretty simple: {_lower_first(_strip_sentence_period(recommendation.rationale))}."
        )
    context_bits = [
        context.get("imaging_modality"),
        context.get("target_structure"),
        context.get("task_family"),
        context.get("optimization_priority"),
        _format_voxel_size_nm(context.get("voxel_size_nm")),
    ]
    if any(context_bits):
        lines.append(
            "I am using: " + ", ".join(str(bit) for bit in context_bits if bit) + "."
        )
    if recommendation.blockers:
        lines.append(
            f"The current blocker is {_lower_first(_strip_sentence_period(recommendation.blockers[0]))}."
        )
    lines.append("When you want, I can turn that into a reviewable app action.")
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
            "Yeah, agreed. I will keep the chat answer more conversational and put the mechanical stuff behind the trace. "
            f"For this {context_text} project, I would probably {next_step} next."
        )
    return (
        "Yeah, agreed. I will keep the chat answer more conversational and put the mechanical stuff behind the trace. "
        f"I would probably {next_step} next."
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
            f"Once that is set, I would probably {_lower_first(_strip_sentence_period(recommendation.decision))}."
        )
    return (
        "I need your approval before changing artifacts. "
        f"The app step I would run is {_lower_first(_strip_sentence_period(recommendation.decision))}."
    )


def _format_capabilities_response() -> str:
    return "\n".join(
        [
            "I can run approved app steps: open data, infer, proofread, train on curated masks, compare metrics, export evidence, and move screens.",
            "You can ask naturally, like 'show me another volume', 'train on the good masks', or 'segment the image-only volumes'.",
            "For anything expensive or project-changing, I will stage a card first so you can review it.",
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


@router.get(
    "/{workflow_id}/memory",
    response_model=Dict[str, Any],
)
def get_workflow_project_memory(
    workflow_id: int,
    refresh: bool = True,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    memory = _build_workflow_project_memory(
        db,
        workflow,
        user_id=user.id,
        refresh=refresh,
    )
    if refresh:
        db.commit()
    append_app_event(
        component="workflow_project_memory",
        event="project_memory_refreshed",
        level="INFO",
        message="Workflow project memory refreshed.",
        workflow_id=workflow.id,
        user_id=user.id,
        task_family=memory["project_facts"]["task_family_preset"].get("id"),
        tracked_total=memory["volume_states"]["summary"].get("total"),
        event_count=len(memory["evidence_events"]),
    )
    return memory


@router.get(
    "/{workflow_id}/overview",
    response_model=WorkflowOverviewResponse,
)
def get_workflow_overview(
    workflow_id: int,
    refresh: bool = True,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    overview = _build_workflow_overview(
        db,
        workflow,
        user_id=user.id,
        refresh=refresh,
    )
    if refresh:
        db.commit()
    append_app_event(
        component="workflow_overview",
        event="workflow_overview_refreshed",
        level="INFO",
        message="Workflow overview refreshed.",
        workflow_id=workflow.id,
        user_id=user.id,
        phase=overview.phase,
        tracked_total=overview.volume_summary.get("tracked_total"),
        blockers=len(overview.blockers),
        active_runs=len(overview.active_runs),
    )
    return overview


@router.get(
    "/{workflow_id}/volumes",
    response_model=WorkflowVolumeStateListResponse,
)
def list_workflow_volume_states(
    workflow_id: int,
    refresh: bool = True,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    if refresh:
        _build_workflow_project_progress(db, workflow, user_id=user.id)
        db.commit()
    rows = (
        db.query(WorkflowVolumeState)
        .filter(WorkflowVolumeState.workflow_id == workflow.id)
        .order_by(WorkflowVolumeState.volume_id.asc())
        .all()
    )
    return WorkflowVolumeStateListResponse(
        workflow_id=workflow.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=_volume_state_summary(rows),
        volumes=[_volume_state_response(row) for row in rows],
    )


@router.patch(
    "/{workflow_id}/volumes",
    response_model=WorkflowVolumeStateResponse,
)
def update_workflow_volume_state(
    workflow_id: int,
    body: WorkflowVolumeStateUpdateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    if not body.volume_id:
        raise HTTPException(status_code=400, detail="volume_id is required")
    provided_fields = getattr(body, "model_fields_set", set()) or getattr(
        body,
        "__fields_set__",
        set(),
    )
    if (
        "status" in provided_fields
        and body.status not in PROJECT_PROGRESS_STATUS_DEFINITIONS
    ):
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(PROJECT_PROGRESS_STATUS_DEFINITIONS)}",
        )
    _validate_composite_status_patch(
        status=body.status if "status" in provided_fields else None,
        annotation_state=(
            body.annotation_state if "annotation_state" in provided_fields else None
        ),
        role_state=body.role_state if "role_state" in provided_fields else None,
        execution_state=(
            body.execution_state if "execution_state" in provided_fields else None
        ),
    )

    row = (
        db.query(WorkflowVolumeState)
        .filter(
            WorkflowVolumeState.workflow_id == workflow.id,
            WorkflowVolumeState.volume_id == body.volume_id,
        )
        .first()
    )
    if row is None:
        row = WorkflowVolumeState(
            workflow_id=workflow.id,
            volume_id=body.volume_id,
            status=body.status or "missing_segmentation",
            status_source="manual",
            status_confidence=1.0,
        )
        db.add(row)
        db.flush()

    if "status" in provided_fields and body.status:
        _set_row_composite_state(
            row,
            status=body.status,
            annotation_state=(
                body.annotation_state if "annotation_state" in provided_fields else None
            ),
            role_state=body.role_state if "role_state" in provided_fields else None,
            execution_state=(
                body.execution_state if "execution_state" in provided_fields else None
            ),
            region_scope=(
                body.region_scope if "region_scope" in provided_fields else None
            ),
        )
        row.status_source = "manual"
        row.status_confidence = 1.0
    elif any(
        field in provided_fields
        for field in [
            "annotation_state",
            "role_state",
            "execution_state",
            "region_scope",
        ]
    ):
        _set_row_composite_state(
            row,
            annotation_state=(
                body.annotation_state if "annotation_state" in provided_fields else None
            ),
            role_state=body.role_state if "role_state" in provided_fields else None,
            execution_state=(
                body.execution_state if "execution_state" in provided_fields else None
            ),
            region_scope=(
                body.region_scope if "region_scope" in provided_fields else None
            ),
        )
        row.status_source = "manual"
        row.status_confidence = 1.0
    else:
        _ensure_row_composite_state(row)
    if "note" in provided_fields:
        row.note = body.note or ""
    if "image_path" in provided_fields:
        row.image_path = _normalize_absolute_path(body.image_path)
    if "label_path" in provided_fields:
        row.label_path = _normalize_absolute_path(body.label_path)
    if "prediction_path" in provided_fields:
        row.prediction_path = _normalize_absolute_path(body.prediction_path)
    if "corrected_mask_path" in provided_fields:
        row.corrected_mask_path = _normalize_absolute_path(body.corrected_mask_path)

    metadata = decode_json(row.metadata_json)
    if body.metadata is not None:
        metadata = {**metadata, **body.metadata}
    if "eligible_for_training" in provided_fields:
        row.eligible_for_training = bool(body.eligible_for_training)
        metadata["eligibility_source"] = "manual"
    elif metadata.get("eligibility_source") != "manual":
        _ensure_row_composite_state(row)
        row.eligible_for_training = _volume_eligible_for_training_state(
            annotation_state=row.annotation_state,
            role_state=row.role_state,
            label_path=row.label_path,
            corrected_mask_path=row.corrected_mask_path,
        )
    if "eligible_for_inference" in provided_fields:
        row.eligible_for_inference = bool(body.eligible_for_inference)
        metadata["eligibility_source"] = "manual"
    elif metadata.get("eligibility_source") != "manual":
        _ensure_row_composite_state(row)
        row.eligible_for_inference = _volume_eligible_for_inference_state(
            annotation_state=row.annotation_state,
            role_state=row.role_state,
            image_path=row.image_path,
        )
    metadata["updated_from"] = "volume_state_api"
    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    row.metadata_json = encode_json(metadata)

    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="user",
        event_type="project_volume.state_updated",
        stage=workflow.stage,
        summary=f"Updated project volume state for {body.volume_id}.",
        payload={
            "volume_id": body.volume_id,
            "status": row.status,
            "annotation_state": row.annotation_state,
            "role_state": row.role_state,
            "execution_state": row.execution_state,
            "eligible_for_training": row.eligible_for_training,
            "eligible_for_inference": row.eligible_for_inference,
            "source": "volume_state_api",
        },
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return _volume_state_response(row)


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
    if (
        "status" in provided_fields
        and body.status not in PROJECT_PROGRESS_STATUS_DEFINITIONS
    ):
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

    row = (
        db.query(WorkflowVolumeState)
        .filter(
            WorkflowVolumeState.workflow_id == workflow.id,
            WorkflowVolumeState.volume_id == body.volume_id,
        )
        .first()
    )
    if row is None:
        row = WorkflowVolumeState(
            workflow_id=workflow.id,
            volume_id=body.volume_id,
            status=body.status or "missing_segmentation",
            status_source="manual_override",
            status_confidence=1.0,
        )
        db.add(row)
        db.flush()
    if "status" in provided_fields and body.status:
        _set_row_composite_state(row, status=body.status)
        row.status_source = "manual_override"
        row.status_confidence = 1.0
    else:
        _ensure_row_composite_state(row)
    if "note" in provided_fields:
        row.note = body.note or ""

    progress = _build_workflow_project_progress(db, workflow, user_id=user.id)
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="user",
        event_type="project_volume.status_updated",
        stage=workflow.stage,
        summary=f"Updated project volume {body.volume_id} status.",
        payload={
            "volume_id": body.volume_id,
            "status": row.status,
            "annotation_state": row.annotation_state,
            "role_state": row.role_state,
            "execution_state": row.execution_state,
            "note": row.note,
            "source": "progress_page",
        },
        commit=False,
    )
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
    copy_max_bytes: int | None = None,
    raw_copy_max_bytes: int | None = None,
    copy_manifest_only: bool = False,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    events = _event_rows(db, workflow.id)
    bundle = build_export_bundle(workflow, events)
    bundle["project_memory"] = json.loads(
        json.dumps(
            _build_workflow_project_memory(
                db,
                workflow,
                user_id=user.id,
                refresh=False,
            ),
            default=str,
        )
    )
    agent_messages = (
        db.query(auth_models.ChatMessage)
        .filter(auth_models.ChatMessage.workflow_id == workflow.id)
        .order_by(
            auth_models.ChatMessage.created_at.asc(), auth_models.ChatMessage.id.asc()
        )
        .all()
    )
    bundle["agent_messages"] = [
        {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "role": message.role,
            "source": message.source,
            "content": message.content,
            "actions": message.actions,
            "commands": message.commands,
            "proposals": message.proposals,
            "trace": message.trace,
            "created_at": (
                message.created_at.isoformat()
                if hasattr(message.created_at, "isoformat")
                else message.created_at
            ),
        }
        for message in agent_messages
    ]
    bundle["action_card_index"] = [
        {
            "message_id": message.id,
            "conversation_id": message.conversation_id,
            "action_id": action.get("id"),
            "action_type": action.get("action_type"),
            "risk_tier": action.get("risk_tier"),
            "requires_approval": action.get("requires_approval"),
            "action_card": action.get("action_card") or {},
        }
        for message in agent_messages
        for action in (message.actions or [])
    ]
    bundle["trace_index"] = [
        {
            "message_id": message.id,
            "conversation_id": message.conversation_id,
            "label": item.get("label"),
            "category": item.get("category"),
            "status": item.get("status"),
            "data": item.get("data") or {},
            "evidence_refs": item.get("evidence_refs") or [],
        }
        for message in agent_messages
        for item in (message.trace or [])
    ]
    try:
        bundle = write_export_bundle_directory(
            bundle,
            copy_max_bytes=copy_max_bytes,
            raw_copy_max_bytes=raw_copy_max_bytes,
            copy_manifest_only=copy_manifest_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
            "copy_settings": bundle.get("copy_settings") or {},
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
    body: Optional[AgentActionApprovalRequest] = None,
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
    if not isinstance(params, dict):
        params = {}
    params, applied_overrides = _apply_agent_action_overrides(
        str(action or ""),
        params,
        body.overrides if body else None,
    )

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
            payload=_agent_action_approval_payload(
                proposal.id,
                action,
                applied_overrides,
            ),
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
                "user_edits": applied_overrides,
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
            payload=_agent_action_approval_payload(
                proposal.id,
                action,
                applied_overrides,
            ),
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
                "user_edits": applied_overrides,
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
        payload=_agent_action_approval_payload(
            proposal.id,
            action,
            applied_overrides,
        ),
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
            "user_edits": applied_overrides,
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


def _agent_conversation_message_response(
    message: auth_models.ChatMessage,
) -> AgentConversationMessage:
    return AgentConversationMessage(
        id=message.id,
        workflow_id=message.workflow_id,
        role=message.role,
        content=message.content,
        source=message.source,
        actions=message.actions,
        commands=message.commands,
        proposals=message.proposals,
        trace=message.trace,
        created_at=message.created_at,
    )


@router.get(
    "/{workflow_id}/agent/conversation",
    response_model=AgentConversationResponse,
)
def get_workflow_agent_conversation(
    workflow_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    latest_message = (
        db.query(auth_models.ChatMessage)
        .join(auth_models.Conversation)
        .filter(
            auth_models.ChatMessage.workflow_id == workflow.id,
            auth_models.Conversation.user_id == user.id,
        )
        .order_by(
            auth_models.ChatMessage.created_at.desc(), auth_models.ChatMessage.id.desc()
        )
        .first()
    )
    if not latest_message:
        return AgentConversationResponse()

    conversation = (
        db.query(auth_models.Conversation)
        .filter(
            auth_models.Conversation.id == latest_message.conversation_id,
            auth_models.Conversation.user_id == user.id,
        )
        .first()
    )
    if not conversation:
        return AgentConversationResponse()

    messages = (
        db.query(auth_models.ChatMessage)
        .filter(
            auth_models.ChatMessage.conversation_id == conversation.id,
            auth_models.ChatMessage.workflow_id == workflow.id,
        )
        .order_by(auth_models.ChatMessage.created_at, auth_models.ChatMessage.id)
        .all()
    )
    return AgentConversationResponse(
        conversation_id=conversation.id,
        conversationId=conversation.id,
        title=conversation.title,
        messages=[
            _agent_conversation_message_response(message) for message in messages
        ],
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
    semantic_intent = {} if command_alias else _semantic_intent_payload(query, workflow)
    semantic_name = semantic_intent.get("intent")
    semantic_tab = semantic_intent.get("tab")
    wants_greeting = _is_greeting_query(lower_query) or semantic_name == "greeting"
    wants_style_feedback = (
        _query_has(
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
        )
        or semantic_name == "style_feedback"
    )
    wants_repair = _is_repair_query(lower_query) or semantic_name == "repair"
    wants_informational_followup = _query_is_informational_followup(lower_query)
    wants_incomplete_intent = (
        _is_incomplete_work_intent(lower_query) or semantic_name == "clarify_next_job"
    )
    target_tab = _target_tab_from_query(lower_query) or _target_tab_from_semantic(
        semantic_name,
        semantic_tab,
    )
    wants_capabilities = (
        any(
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
        )
        or semantic_name == "capabilities"
    )
    wants_project_context = (
        any(
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
        )
        or semantic_name == "project_context"
    )
    wants_project_files = (
        _query_wants_project_file_overview(lower_query)
        or semantic_name == "project_files"
    )
    wants_project_progress = (
        _query_has(
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
                "ready for training",
                "left out",
                "leave out",
                "excluded",
                "exclude",
                "human attention",
                "need attention",
                "needs attention",
                "need human",
                "needs human",
                "what is left",
                "what's left",
                "what remains",
                "remaining",
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
        )
        or semantic_name == "project_progress"
    )
    wants_user_need = (
        any(
            phrase in lower_query
            for phrase in [
                "what do you need",
                "what you need",
                "need from me",
                "need me to",
                "what should i provide",
                "what should i do for you",
            ]
        )
        or semantic_name == "needed_from_user"
    )
    wants_status = (
        _query_has(
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
        )
        or semantic_name == "status"
    )
    wants_evaluation = (
        _query_has(
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
        )
        or semantic_name == "compute_evaluation"
    )
    wants_export = (
        _query_has(
            lower_query,
            [
                "export bundle",
                "export evidence",
                "export report",
                "evidence bundle",
                "research bundle",
                "download bundle",
            ],
        )
        or semantic_name == "export_evidence"
    )
    wants_visualization_launch = (
        _query_wants_visualization_launch(lower_query) or semantic_name == "view_data"
    )
    wants_alternate_volume_set = _query_wants_alternate_volume_set(lower_query)
    if wants_alternate_volume_set:
        wants_visualization_launch = True
    wants_visualization_scales = (
        _query_wants_visualization_scales(lower_query)
        or semantic_name == "set_visualization_scales"
    )
    wants_retraining = (
        any(
            term in lower_query
            for term in ["retrain", "training", "stage", "corrected"]
        )
        or semantic_name == "stage_retraining"
    )
    wants_training_launch = (
        _query_has(
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
        )
        or semantic_name == "start_training"
    )
    wants_inference_launch = (
        _query_wants_inference_launch(lower_query) or semantic_name == "start_inference"
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
    wants_proofreading_launch = (
        _query_has(
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
        )
        or semantic_name == "start_proofreading"
    )
    wants_failure_analysis = (
        any(
            term in lower_query
            for term in ["fail", "failure", "error", "hotspot", "where"]
        )
        or semantic_name == "inspect_failure"
    )
    wants_mount_project = (
        _query_has(
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
        )
        or semantic_name == "mount_project"
    )
    wants_reset_workspace = (
        _query_has(
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
        )
        or semantic_name == "reset_workspace"
    )
    if wants_reset_workspace:
        wants_mount_project = False
    wants_validate_project = (
        _query_has(
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
        )
        or semantic_name == "validate_project"
    )
    if wants_project_files and semantic_name != "validate_project":
        wants_validate_project = False
    wants_prepare_data = (
        _query_has(
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
        )
        or semantic_name == "prepare_data"
    )
    wants_configure_training = (
        _query_has(
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
        )
        or semantic_name == "configure_training"
    )
    wants_configure_inference = (
        _query_has(
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
        )
        or semantic_name == "configure_inference"
    )
    wants_monitor_jobs = (
        _query_has(
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
        )
        or semantic_name == "monitor_jobs"
    )
    wants_stop_runtime = (
        _query_has(
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
        )
        or semantic_name == "stop_runtime"
    )
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
    explicit_context_mutation = _query_explicitly_mutates_project_context(lower_query)
    protected_volume_question = _query_mentions_volume_id(lower_query) and any(
        marker in lower_query
        for marker in [
            "why",
            "which",
            "what",
            "how",
            "leave out",
            "left out",
            "exclude",
            "excluded",
            "training",
            "train",
        ]
    )
    context_should_update = bool(context_update) and (
        not command_alias
        and not protected_volume_question
        and (
            explicit_context_mutation
            or semantic_name == "project_context_update"
            or wants_use_defaults
            or action_needs_context
        )
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
    query_policy_decision: Optional[Dict[str, Any]] = None
    query_blocking_reasons: List[Dict[str, Any]] = []
    query_freshness: Optional[Dict[str, Any]] = None

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
        missing_context_fields = _project_context_missing_fields(workflow)
        query_blocking_reasons = [
            _policy_blocking_reason(
                f"project_context.missing_{_reason_code_from_label(field)}",
                f"Project context is missing: {field}.",
                scope="project_context",
                field=field,
            )
            for field in missing_context_fields
        ]
        query_policy_decision = _policy_decision_payload(
            "blocked",
            requires_approval=False,
            reason_code="project_context_missing",
            reason="Project context fields are required before this action.",
            blocking_reasons=query_blocking_reasons,
        )
        query_freshness = _project_context_freshness(workflow)
        response = _format_project_context_prompt(workflow, context_action_label)
        actions = []
        commands = []
    elif (
        context_should_update
        and not action_needs_context
        and not workflow_action_requested
    ):
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
        training_requires_trusted_masks = _workflow_requires_trusted_masks(workflow)
        training_label_path = _preferred_training_mask_path(
            workflow,
            require_trusted=training_requires_trusted_masks,
        )
        effects = _build_start_training_effects(workflow, training_label_path)
        if (
            training_requires_trusted_masks
            and not training_label_path
            and not corrected_mask_path
        ):
            effects = {
                "navigate_to": "training",
                "set_training_config_preset": _choose_training_config_preset(workflow),
            }
            if workflow.image_path or workflow.dataset_path:
                effects["set_training_image_path"] = (
                    workflow.image_path or workflow.dataset_path
                )
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
            "Do this: open Train Model.\n"
            "Why: training logs, TensorBoard links, runtime status, and job health live with the training run now."
        )
        actions = [
            _build_agent_chat_action(
                "open-training-runtime",
                "Open Train Model",
                "Open training runtime details and logs.",
                variant="primary",
                client_effects={"navigate_to": "training"},
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
                "open-training-runtime",
                "Open Train Model",
                "Check runtime state after stopping.",
                client_effects={"navigate_to": "training"},
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
        query_policy_decision = _policy_decision_payload(
            "allowed",
            requires_approval=True,
            reason_code="export_ready",
            reason="An evidence export action is ready.",
            blocking_reasons=[],
        )
        query_freshness = {"scope": "export", "state": "ready"}
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
                policy_decision=query_policy_decision,
                freshness={"scope": "export", "state": "ready"},
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
        eval_blocking_reasons = [
            _policy_blocking_reason(
                f"evaluation.missing_{_reason_code_from_label(field)}",
                f"Evaluation is blocked because {field} is missing.",
                scope="evaluation_inputs",
                field=field,
            )
            for field in missing_eval_inputs
        ]
        if missing_eval_inputs:
            query_blocking_reasons = eval_blocking_reasons
            query_policy_decision = _policy_decision_payload(
                "blocked",
                requires_approval=False,
                reason_code="evaluation_missing_inputs",
                reason="Evaluation input artifacts are incomplete.",
                blocking_reasons=query_blocking_reasons,
            )
            query_freshness = _resource_freshness_payload(
                scope="evaluation",
                required_fields=[
                    "previous result",
                    "new result",
                    "reference mask",
                ],
                missing_fields=missing_eval_inputs,
            )
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
                    policy_decision=_policy_decision_payload(
                        "blocked",
                        requires_approval=False,
                        reason_code="evaluation_missing_inputs",
                        reason="Evaluation inputs are incomplete.",
                        blocking_reasons=eval_blocking_reasons,
                    ),
                    freshness=_resource_freshness_payload(
                        scope="evaluation",
                        required_fields=[
                            "previous result",
                            "new result",
                            "reference mask",
                        ],
                        missing_fields=missing_eval_inputs,
                    ),
                ),
                _build_agent_chat_action(
                    "open-inference",
                    "Open Run Model",
                    "Run or register model outputs for comparison.",
                    client_effects={"navigate_to": "inference"},
                    policy_decision=_policy_decision_payload(
                        "blocked",
                        requires_approval=False,
                        reason_code="evaluation_missing_inputs",
                        reason="Evaluation inputs are incomplete.",
                        blocking_reasons=eval_blocking_reasons,
                    ),
                    freshness=_resource_freshness_payload(
                        scope="evaluation",
                        required_fields=[
                            "previous result",
                            "new result",
                            "reference mask",
                        ],
                        missing_fields=missing_eval_inputs,
                    ),
                ),
            ]
            commands = []
        else:
            eval_freshness = _resource_freshness_payload(
                scope="evaluation",
                required_fields=[
                    "previous result",
                    "new result",
                    "reference mask",
                ],
                missing_fields=[],
            )
            response = (
                "Do this: compute before/after metrics.\n"
                "Why: this checks whether the new result improved against the reference mask."
            )
            query_policy_decision = _policy_decision_payload(
                "allowed",
                requires_approval=True,
                reason_code="evaluation_ready",
                reason="Evaluation inputs are complete.",
                blocking_reasons=[],
            )
            query_freshness = _resource_freshness_payload(
                scope="evaluation",
                required_fields=[
                    "previous result",
                    "new result",
                    "reference mask",
                ],
                missing_fields=[],
            )
            actions = [
                _build_agent_chat_action(
                    "compute-evaluation",
                    "Compute metrics",
                    "Compare the previous and new segmentation results.",
                    variant="primary",
                    client_effects=evaluation_effects,
                    policy_decision=_policy_decision_payload(
                        "allowed",
                        requires_approval=True,
                        reason_code="evaluation_ready",
                        reason="All comparison inputs are available.",
                        blocking_reasons=[],
                    ),
                    freshness=eval_freshness,
                ),
                _build_agent_chat_action(
                    "export-workflow-bundle",
                    "Export evidence",
                    "Export the workflow evidence bundle after metrics are recorded.",
                    client_effects=_build_export_bundle_effects(),
                    policy_decision=_policy_decision_payload(
                        "allowed",
                        requires_approval=True,
                        reason_code="export_ready",
                        reason="Evidence export requires approval before creating the bundle.",
                        blocking_reasons=[],
                    ),
                    freshness={"scope": "export", "state": "ready"},
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
        if observed_volume_set and (wants_alternate_volume_set or not image_path):
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
            selected_pair = _select_visualization_pair(workflow, pair_discovery)
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
                pair_count = max(
                    pair_count, int(observed_volume_set.get("pair_count") or 0)
                )
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
        training_requires_trusted_masks = _workflow_requires_trusted_masks(workflow)
        training_label_path = _preferred_training_mask_path(
            workflow,
            require_trusted=training_requires_trusted_masks,
        )
        training_missing = []
        if not (workflow.image_path or workflow.dataset_path):
            training_missing.append("image volume")
        if not training_label_path:
            training_missing.append("labels")
        training_blocking_reasons = [
            _policy_blocking_reason(
                f"training.missing_{_reason_code_from_label(field)}",
                f"Training is blocked because {field} is missing.",
                scope="training_inputs",
                field=field,
            )
            for field in training_missing
        ]
        if training_missing:
            query_blocking_reasons = training_blocking_reasons
            query_policy_decision = _policy_decision_payload(
                "blocked",
                requires_approval=False,
                reason_code="training_missing_inputs",
                reason="Training inputs are incomplete.",
                blocking_reasons=query_blocking_reasons,
            )
            query_freshness = _resource_freshness_payload(
                scope="training",
                required_fields=["image volume", "label path"],
                missing_fields=training_missing,
            )
            response = (
                "I can train from the saved edits, but I need image and labels first.\n"
                "Do this: choose the image and label folders in Files."
            )
            actions = [
                _build_agent_chat_action(
                    "open-files",
                    "Choose data",
                    "Select image and label data needed for retraining.",
                    variant="primary",
                    client_effects=_build_choose_data_effects(),
                    policy_decision=query_policy_decision,
                    freshness=query_freshness,
                )
            ]
            commands = []
        else:
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
                    include_segment_rest=_query_wants_segment_remaining_after_training(
                        lower_query
                    ),
                )
                if subset_plan
                else (
                    "Yes. I can train from the saved edits with the current image and mask paths. "
                    "I’ll use the project config and safe defaults, then you can review the run before it launches."
                )
            )
            query_policy_decision = _policy_decision_payload(
                "allowed",
                requires_approval=True,
                reason_code="training_ready",
                reason="Training inputs are available.",
                blocking_reasons=[],
            )
            query_freshness = _resource_freshness_payload(
                scope="training",
                required_fields=["image volume", "label path"],
                missing_fields=[],
            )
            actions = [
                _build_agent_chat_action(
                    "start-training",
                    "Train on edits",
                    "Start training with the selected labels and safe defaults.",
                    variant="primary",
                    client_effects=training_effects,
                    policy_decision=query_policy_decision,
                    freshness=query_freshness,
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
        training_requires_trusted_masks = _workflow_requires_trusted_masks(workflow)
        training_label_path = _preferred_training_mask_path(
            workflow,
            require_trusted=training_requires_trusted_masks,
        )
        image_path = workflow.image_path or workflow.dataset_path or ""
        if not image_path:
            query_blocking_reasons = [
                _policy_blocking_reason(
                    "training.missing_image_volume",
                    "Training is blocked because image data is missing.",
                    scope="training_inputs",
                    field="image volume",
                )
            ]
            query_policy_decision = _policy_decision_payload(
                "blocked",
                requires_approval=False,
                reason_code="training_missing_inputs",
                reason="Training inputs are incomplete.",
                blocking_reasons=query_blocking_reasons,
            )
            query_freshness = _resource_freshness_payload(
                scope="training",
                required_fields=["image volume", "label path"],
                missing_fields=["image volume"],
            )
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
                    policy_decision=query_policy_decision,
                    freshness=query_freshness,
                    blocking_reasons=query_blocking_reasons,
                )
            ]
            commands = []
        elif not training_label_path:
            if training_requires_trusted_masks:
                response = (
                    "I can train a model, but this project needs confirmed labels or saved proofreading edits first.\n"
                    "Do this: choose corrected labels, run proofreading, or restore a ground-truth mask."
                )
            else:
                response = (
                    "I can train a model, but I need labels or saved proofreading edits first.\n"
                    "Do this: choose label data, proofread a mask, or run the model to create a prediction."
                )
            training_blocking_reasons = [
                _policy_blocking_reason(
                    "training.missing_labels",
                    "Training is blocked because labels are missing.",
                    scope="training_inputs",
                    field="labels",
                )
            ]
            query_blocking_reasons = training_blocking_reasons
            query_policy_decision = _policy_decision_payload(
                "blocked",
                requires_approval=False,
                reason_code="training_missing_inputs",
                reason="Training inputs are incomplete.",
                blocking_reasons=query_blocking_reasons,
            )
            query_freshness = _resource_freshness_payload(
                scope="training",
                required_fields=["image volume", "label path"],
                missing_fields=["labels"],
            )
            actions = [
                _build_agent_chat_action(
                    "open-files",
                    "Choose labels",
                    "Select label data or saved edits for training.",
                    variant="primary",
                    client_effects=_build_choose_data_effects(),
                    policy_decision=query_policy_decision,
                    freshness=query_freshness,
                    blocking_reasons=training_blocking_reasons,
                ),
                _build_agent_chat_action(
                    "open-proofreading",
                    "Proofread",
                    "Create saved edits before training.",
                    client_effects={"navigate_to": "mask-proofreading"},
                    policy_decision=_policy_decision_payload(
                        "allowed",
                        requires_approval=True,
                        reason_code="training_can_start_after_proofreading",
                        reason="Proofreading is available to produce trusted masks.",
                        blocking_reasons=[],
                    ),
                    freshness=_resource_freshness_payload(
                        scope="proofreading",
                        required_fields=["image volume", "mask, label, or prediction"],
                        missing_fields=[],
                    ),
                ),
            ]
            commands = []
        else:
            query_policy_decision = _policy_decision_payload(
                "allowed",
                requires_approval=True,
                reason_code="training_ready",
                reason="Training inputs are available.",
                blocking_reasons=[],
            )
            query_freshness = _resource_freshness_payload(
                scope="training",
                required_fields=["image volume", "label path"],
                missing_fields=[],
            )
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
                    include_segment_rest=_query_wants_segment_remaining_after_training(
                        lower_query
                    ),
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
                    policy_decision=query_policy_decision,
                    freshness=query_freshness,
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
            inference_blocking_reasons = [
                _policy_blocking_reason(
                    f"inference.missing_{_reason_code_from_label(field)}",
                    f"Inference is blocked because {field} is missing.",
                    scope="inference_inputs",
                    field=field,
                )
                for field in inference_blockers
            ]
            query_blocking_reasons = inference_blocking_reasons
            query_policy_decision = _policy_decision_payload(
                "blocked",
                requires_approval=False,
                reason_code="inference_missing_inputs",
                reason="Inference inputs are incomplete.",
                blocking_reasons=query_blocking_reasons,
            )
            query_freshness = _resource_freshness_payload(
                scope="inference",
                required_fields=["image volume", "model checkpoint"],
                missing_fields=inference_blockers,
            )
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
                    policy_decision=_policy_decision_payload(
                        "blocked",
                        requires_approval=False,
                        reason_code="inference_missing_inputs",
                        reason="Inference inputs are incomplete.",
                        blocking_reasons=inference_blocking_reasons,
                    ),
                    freshness=_resource_freshness_payload(
                        scope="inference",
                        required_fields=["image volume", "model checkpoint"],
                        missing_fields=inference_blockers,
                    ),
                )
            ]
            if not (workflow.image_path or workflow.dataset_path):
                actions.append(
                    _build_agent_chat_action(
                        "open-files",
                        "Choose data",
                        "Pick an image volume before running a model.",
                        client_effects=_build_choose_data_effects(),
                        policy_decision=_policy_decision_payload(
                            "blocked",
                            requires_approval=False,
                            reason_code="inference_missing_inputs",
                            reason="Inference inputs are incomplete.",
                            blocking_reasons=inference_blocking_reasons,
                        ),
                        freshness=_resource_freshness_payload(
                            scope="inference",
                            required_fields=["image volume", "model checkpoint"],
                            missing_fields=inference_blockers,
                        ),
                    )
                )
            if not proofreading_blockers:
                actions.append(
                    _build_proofreading_action(
                        workflow,
                        variant="default",
                        policy_decision=_policy_decision_payload(
                            "allowed",
                            requires_approval=True,
                            reason_code="proofreading_ready",
                            reason="Proofreading is available with existing inputs.",
                            blocking_reasons=[],
                        ),
                        freshness=_resource_freshness_payload(
                            scope="proofreading",
                            required_fields=[
                                "image volume",
                                "mask, label, or prediction",
                            ],
                            missing_fields=[],
                        ),
                    )
                )
            commands = []
        else:
            inference_effects = _build_start_inference_effects(workflow)
            response = (
                "Do this: run the model.\n"
                "Why: this creates the mask result you can inspect and fix."
            )
            query_policy_decision = _policy_decision_payload(
                "allowed",
                requires_approval=True,
                reason_code="inference_ready",
                reason="Inference inputs are complete.",
                blocking_reasons=[],
            )
            query_freshness = _resource_freshness_payload(
                scope="inference",
                required_fields=["image volume", "model checkpoint"],
                missing_fields=[],
            )
            actions = [
                _build_agent_chat_action(
                    "start-inference",
                    "Run model",
                    "Start the model run with the current settings.",
                    variant="primary",
                    policy_decision=_policy_decision_payload(
                        "allowed",
                        requires_approval=True,
                        reason_code="inference_ready",
                        reason="Inference inputs are available.",
                        blocking_reasons=[],
                    ),
                    freshness=_resource_freshness_payload(
                        scope="inference",
                        required_fields=["image volume", "model checkpoint"],
                        missing_fields=[],
                    ),
                    client_effects=inference_effects,
                ),
                _build_agent_chat_action(
                    "start-proofreading",
                    "Proofread this data",
                    "Open the image and mask in the proofreading workbench.",
                    client_effects=_build_start_proofreading_effects(workflow),
                    policy_decision=_policy_decision_payload(
                        "allowed",
                        requires_approval=True,
                        reason_code="proofreading_ready",
                        reason="Proofreading is available with existing inputs.",
                        blocking_reasons=[],
                    ),
                    freshness=_resource_freshness_payload(
                        scope="proofreading",
                        required_fields=["image volume", "mask, label, or prediction"],
                        missing_fields=[],
                    ),
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
            segmentation_blocking_reasons = [
                _policy_blocking_reason(
                    f"inference.missing_{_reason_code_from_label(field)}",
                    f"Segmentation is blocked because {field} is required for inference.",
                    scope="inference_inputs",
                    field=field,
                )
                for field in inference_blockers
            ]
            query_blocking_reasons = segmentation_blocking_reasons
            query_policy_decision = _policy_decision_payload(
                "blocked",
                requires_approval=False,
                reason_code="segmentation_blocked",
                reason="Segmentation requires a complete inference setup.",
                blocking_reasons=query_blocking_reasons,
            )
            query_freshness = _resource_freshness_payload(
                scope="inference",
                required_fields=["image volume", "model checkpoint"],
                missing_fields=inference_blockers,
            )
            response = (
                f"I can help segment this data, but running inference needs {missing}.\n"
                "Why: a checkpoint is required to produce a new model prediction. Useful next step: use the existing labels for proofreading or training, or add a checkpoint before running inference."
            )
            actions = []
            if not proofreading_blockers:
                actions.append(
                    _build_proofreading_action(
                        workflow,
                        variant="primary",
                        policy_decision=_policy_decision_payload(
                            "allowed",
                            requires_approval=True,
                            reason_code="proofreading_ready",
                            reason="Proofreading is available with existing inputs.",
                            blocking_reasons=[],
                        ),
                        freshness=_resource_freshness_payload(
                            scope="proofreading",
                            required_fields=[
                                "image volume",
                                "mask, label, or prediction",
                            ],
                            missing_fields=[],
                        ),
                    )
                )
            training_requires_trusted_masks = _workflow_requires_trusted_masks(workflow)
            training_label_path = _preferred_training_mask_path(
                workflow,
                require_trusted=training_requires_trusted_masks,
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
                        policy_decision=_policy_decision_payload(
                            "allowed",
                            requires_approval=True,
                            reason_code="training_ready",
                            reason="Training inputs are available.",
                            blocking_reasons=[],
                        ),
                        freshness=_resource_freshness_payload(
                            scope="training",
                            required_fields=["image volume", "label path"],
                            missing_fields=[],
                        ),
                    )
                )
            actions.append(
                _build_agent_chat_action(
                    "open-inference",
                    "Check Run Model",
                    f"Running segmentation needs {missing}.",
                    variant="primary" if not actions else "default",
                    client_effects={"navigate_to": "inference"},
                    policy_decision=query_policy_decision,
                    freshness=query_freshness,
                    blocking_reasons=segmentation_blocking_reasons,
                )
            )
            if not (workflow.image_path or workflow.dataset_path):
                actions.append(
                    _build_agent_chat_action(
                        "open-files",
                        "Choose data",
                        "Pick an image volume before segmenting.",
                        client_effects=_build_choose_data_effects(),
                        policy_decision=_policy_decision_payload(
                            "blocked",
                            requires_approval=False,
                            reason_code="inference_missing_inputs",
                            reason="Inference inputs are incomplete.",
                            blocking_reasons=segmentation_blocking_reasons,
                        ),
                        freshness=query_freshness,
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
            query_policy_decision = _policy_decision_payload(
                "allowed",
                requires_approval=True,
                reason_code="segmentation_ready",
                reason="Segmentation is ready to run with inference inputs.",
                blocking_reasons=[],
            )
            query_freshness = _resource_freshness_payload(
                scope="inference",
                required_fields=["image volume", "model checkpoint"],
                missing_fields=[],
            )
            actions = [
                _build_agent_chat_action(
                    "start-inference",
                    "Run model",
                    "Start segmentation from the current inference settings.",
                    variant="primary",
                    client_effects=inference_effects,
                    policy_decision=_policy_decision_payload(
                        "allowed",
                        requires_approval=True,
                        reason_code="inference_ready",
                        reason="Inference inputs are available.",
                        blocking_reasons=[],
                    ),
                    freshness=_resource_freshness_payload(
                        scope="inference",
                        required_fields=["image volume", "model checkpoint"],
                        missing_fields=[],
                    ),
                ),
                _build_agent_chat_action(
                    "start-proofreading",
                    "Proofread this data",
                    "Open the current image/mask pair in proofreading.",
                    client_effects=proofreading_effects,
                    policy_decision=_policy_decision_payload(
                        "allowed",
                        requires_approval=True,
                        reason_code="proofreading_ready",
                        reason="Proofreading is available with existing inputs.",
                        blocking_reasons=[],
                    ),
                    freshness=_resource_freshness_payload(
                        scope="proofreading",
                        required_fields=["image volume", "mask, label, or prediction"],
                        missing_fields=[],
                    ),
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
        orchestrator_agent=ORCHESTRATOR_AGENT,
        subagents=list(WORKFLOW_SUBAGENTS.values()),
        policy_decision=query_policy_decision,
        blocking_reasons=query_blocking_reasons,
        freshness=query_freshness,
        conversation_id=conversation.id,
        conversationId=conversation.id,
        proposals=proposals,
        actions=actions,
        commands=commands,
        tasks=tasks,
        trace=trace,
    )
