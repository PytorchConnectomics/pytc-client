from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app_event_logger import append_app_event
from server_api.auth import models as auth_models
from server_api.auth.database import get_db
from server_api.auth.router import get_current_user

from .db_models import (
    WorkflowAgentPlan,
    WorkflowAgentStep,
    WorkflowArtifact,
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
    correction_set_to_dict,
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


class AgentActionResult(BaseModel):
    workflow: WorkflowResponse
    proposal: WorkflowEventResponse
    events: List[WorkflowEventResponse]
    client_effects: Dict[str, Any] = Field(default_factory=dict)


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

    runtime_action = client_effects.get("runtime_action") or {}
    runtime_kind = runtime_action.get("kind")
    if runtime_kind == "start_inference":
        lines.append("app inference run")
    elif runtime_kind == "start_training":
        lines.append("app training run")
    elif runtime_kind == "start_proofreading":
        lines.append("app proofreading start")

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
    if runtime_kind == "start_proofreading":
        return "loads_editor"
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
        "loads_editor",
        "exports_evidence",
        "writes_workflow_record",
    }


def _build_agent_chat_action(
    action_id: str,
    label: str,
    description: str,
    *,
    variant: str = "default",
    client_effects: Optional[Dict[str, Any]] = None,
    risk_level: Optional[str] = None,
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
    if workflow.inference_output_path:
        effects["set_inference_output_path"] = workflow.inference_output_path
    if workflow.checkpoint_path:
        effects["set_inference_checkpoint_path"] = workflow.checkpoint_path
    return effects


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
        return "configs/MitoEM/Mito25-Local-Smoke-BC.yaml"
    if "snemi" in haystack:
        return "configs/SNEMI/SNEMI-Affinity-UNet.yaml"
    if "cremi" in haystack:
        return "configs/CREMI/CREMI-Foreground-UNet.yaml"
    return "configs/Lucchi-Mitochondria.yaml"


def _build_start_training_effects(
    workflow: WorkflowSession, corrected_mask_path: Optional[str]
) -> Dict[str, Any]:
    output_path = _derive_training_output_path(workflow)
    image_path = workflow.image_path or workflow.dataset_path or ""
    effects: Dict[str, Any] = {
        "navigate_to": "training",
        "runtime_action": {
            "kind": "start_training",
            "autopick_parameters": True,
            "parameter_mode": "agent_default",
        },
        "set_training_config_preset": _choose_training_config_preset(workflow),
    }
    if image_path:
        effects["set_training_image_path"] = image_path
    if corrected_mask_path:
        effects["set_training_label_path"] = corrected_mask_path
    if output_path:
        effects["set_training_output_path"] = output_path
        effects["set_training_log_path"] = output_path
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
    effects: Dict[str, Any] = {"navigate_to": "visualization"}
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
                client_effects={"navigate_to": "files"},
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
                    client_effects={"navigate_to": "files"},
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
    return (
        f"Hi. You are in {recommendation.stage.replace('_', ' ')}.\n"
        f"Next: {recommendation.decision}\n"
        "Tell me the job when you want me to act."
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
    lines = [
        f"Do this: {recommendation.decision}",
        f"Why: {recommendation.rationale}",
    ]
    if total_count:
        lines.append(f"Ready: {ready_count}/{total_count} loop checks pass.")
    if recommendation.blockers:
        lines.append(f"Watch out: {recommendation.blockers[0]}")
    return "\n".join(lines)


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


def _workflow_project_context(workflow: WorkflowSession) -> Dict[str, Any]:
    metadata = decode_json(workflow.metadata_json)
    context = metadata.get("project_context") if isinstance(metadata, dict) else {}
    return context if isinstance(context, dict) else {}


def _format_scale_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _format_scales(scales: List[float]) -> str:
    return ",".join(_format_scale_number(value) for value in scales)


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
    project_context["voxel_size_source"] = "workflow_agent"
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

    if any(term in lower for term in ["fast", "quick", "smoke", "prototype"]):
        context["optimization_priority"] = "speed"
    elif any(term in lower for term in ["accurate", "accuracy", "quality", "best"]):
        context["optimization_priority"] = "accuracy"

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
    return "\n".join(
        [
            f"Before I {action_label}, I need project context.",
            f"Tell me: {', '.join(missing[:3])}.",
            "Example: EM mitochondria; prioritize accuracy. Or say: use defaults.",
        ]
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
    missing = _project_context_missing_fields(workflow)
    if missing:
        return "\n".join(
            [
                f"Saved context: {', '.join(summary) or 'partial'}.",
                f"Still need: {', '.join(missing)}.",
                "Then I can choose the model/preset and run the next app step.",
            ]
        )
    return "\n".join(
        [
            f"Saved context: {', '.join(summary)}.",
            f"Next: {recommendation.decision}",
            "Tell me the workflow job when you want me to act.",
        ]
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
        ]
        lines.append(
            "Context: " + ", ".join(str(bit) for bit in context_bits if bit) + "."
        )
    lines.append(f"Next: {recommendation.decision}")
    return "\n".join(lines)



def _format_needed_from_user_response(
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    if recommendation.stage == "proofreading":
        gap = recommendation.blockers[0] if recommendation.blockers else "Save edits."
        return "\n".join(
            [
                "I need your mask judgment.",
                "Do this: proofread likely mistakes, save fixes, then export masks.",
                f"Current gap: {gap}",
            ]
        )

    blocker = recommendation.blockers[0] if recommendation.blockers else None
    if blocker:
        return "\n".join(
            [
                "I need one missing workflow input.",
                f"Do this: {recommendation.decision}",
                f"Current gap: {blocker}",
            ]
        )
    return "\n".join(
        [
            "I need your approval before changing artifacts.",
            f"Do this: {recommendation.decision}",
            "I can run the in-app step when you approve it.",
        ]
    )


def _format_capabilities_response() -> str:
    return "\n".join(
        [
            "I can run approved app steps: infer, proofread, train on saved edits, compare metrics, export evidence, and move screens.",
            "Ask for a concrete job, e.g. 'run inference', 'proofread this result', or 'compare results'.",
            "I will ask approval before long runs or artifact changes.",
        ]
    )


def _format_repair_response(
    recommendation: WorkflowAgentRecommendationResponse,
) -> str:
    return "\n".join(
        [
            "That was too generic.",
            "Tell me the workflow job you want, or ask 'status' for what is ready.",
            f"Current next step: {recommendation.decision}",
        ]
    )


def _format_unknown_workflow_query_response() -> str:
    return "\n".join(
        [
            "I did not understand that as a workflow job.",
            "Try: run inference, proofread, train on saved edits, compare metrics, export evidence, or status.",
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

    if action != "stage_retraining_from_corrections":
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

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
    conversation: auth_models.Conversation,
    query: str,
    response: str,
    actions: List[AgentChatAction],
    commands: List[AgentCommandBlock],
    proposals: List[WorkflowEventResponse],
) -> None:
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(
        auth_models.ChatMessage(
            conversation_id=conversation.id,
            role="user",
            content=query,
        )
    )
    db.add(
        auth_models.ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=response,
            source="workflow_orchestrator",
            actions_json=_jsonable_agent_items(actions),
            commands_json=_jsonable_agent_items(commands),
            proposals_json=_jsonable_agent_items(proposals),
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
    wants_greeting = _is_greeting_query(lower_query)
    wants_repair = _is_repair_query(lower_query)
    wants_incomplete_intent = _is_incomplete_work_intent(lower_query)
    target_tab = _target_tab_from_query(lower_query)
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
    )
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
    )
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
    )
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
    )
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
    )
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
    )
    wants_visualization_launch = _query_has(
        lower_query,
        [
            "visualize",
            "visualization",
            "view data",
            "view volume",
            "view volumes",
            "show data",
            "show volume",
            "inspect data",
            "inspect volume",
            "look at data",
            "look at volume",
        ],
    )
    wants_visualization_scales = _query_wants_visualization_scales(lower_query)
    wants_retraining = any(
        term in lower_query for term in ["retrain", "training", "stage", "corrected"]
    )
    wants_training_launch = any(
        term in lower_query
        for term in [
            "start training",
            "run training",
            "launch training",
            "retrain now",
            "train the model",
            "train for me",
            "run a training job",
            "run training job",
        ]
    )
    wants_inference_launch = any(
        term in lower_query
        for term in [
            "start inference",
            "run inference",
            "launch inference",
            "run model",
            "start model",
            "launch model",
        ]
    )
    wants_segmentation_launch = _query_has(
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
        ],
    )
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
    )
    wants_failure_analysis = any(
        term in lower_query for term in ["fail", "failure", "error", "hotspot", "where"]
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
    context_update = _extract_project_context_from_query(query)
    if wants_use_defaults:
        context_update = {
            **context_update,
            "use_defaults": True,
            "freeform_note": query[:500],
        }
    if context_update:
        _merge_project_context(db, workflow, context_update)
    action_needs_context = (
        wants_training_launch or wants_inference_launch or wants_segmentation_launch
    )
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
                        client_effects={"navigate_to": "files"},
                    )
                )
            commands = []
    elif action_needs_context and _project_context_missing_fields(workflow):
        intent = "collect_project_context"
        response = _format_project_context_prompt(workflow, context_action_label)
        actions = []
        commands = []
    elif context_update and not action_needs_context:
        intent = "project_context_updated"
        response = _format_project_context_saved_response(
            workflow,
            agent_recommendation,
        )
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
            "Do this: choose one workflow job.\n"
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
        image_path = workflow.image_path or workflow.dataset_path or ""
        label_path = (
            workflow.label_path
            or workflow.mask_path
            or workflow.inference_output_path
            or workflow.corrected_mask_path
            or ""
        )
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
                    client_effects={"navigate_to": "files"},
                )
            ]
            commands = []
        else:
            pair_discovery = _workflow_volume_pair_discovery(workflow)
            detected_pairs = pair_discovery.get("pairs") or []
            selected_pair = detected_pairs[0] if detected_pairs else None
            selected_image_path = (
                selected_pair.get("image_path") if selected_pair else image_path
            )
            selected_label_path = (
                selected_pair.get("label_path") if selected_pair else label_path
            )
            view_effects = _build_view_data_effects(
                workflow,
                image_path=selected_image_path,
                label_path=selected_label_path,
            )
            pair_count = int(pair_discovery.get("pair_count") or 0)
            pair_line = ""
            if pair_count > 1:
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
        training_effects = _build_start_training_effects(workflow, corrected_mask_path)
        response = (
            "Do this: train on the saved edits.\n"
            "Why: I can choose the preset and safe defaults from the current image/mask paths."
        )
        actions = [
            _build_agent_chat_action(
                "start-training",
                "Train on edits",
                "Start training with the saved mask edits.",
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
                "Run this in-app command block to launch retraining from chat.",
                training_effects,
            )
        ]
    elif wants_inference_launch:
        intent = "start_inference"
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
                    client_effects={"navigate_to": "files"},
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
        response = _format_unknown_workflow_query_response()
        actions = []
        commands = []

    _persist_workflow_agent_chat_exchange(
        db,
        conversation=conversation,
        query=raw_query,
        response=response,
        actions=actions,
        commands=commands,
        proposals=proposals,
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
    )
