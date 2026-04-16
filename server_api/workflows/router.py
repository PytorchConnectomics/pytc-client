from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server_api.auth import models as auth_models
from server_api.auth.database import get_db
from server_api.auth.router import get_current_user

from .db_models import WorkflowEvent, WorkflowSession
from .service import (
    append_workflow_event,
    decode_json,
    event_to_dict,
    get_current_or_create_workflow,
    get_user_workflow_or_404,
    update_workflow_fields,
    validate_stage,
    workflow_to_dict,
)
from .bundle_export import build_export_bundle
from .metrics import compute_workflow_metrics

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
    proofreading_session_id: Optional[int] = None
    corrected_mask_path: Optional[str] = None
    training_output_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


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


class AgentQueryResponse(BaseModel):
    response: str
    proposals: List[WorkflowEventResponse] = Field(default_factory=list)


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


class WorkflowMetricsResponse(BaseModel):
    workflow_id: int
    metrics: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExportBundleResponse(BaseModel):
    schema_version: str
    exported_at: str
    workflow_id: int
    session_snapshot: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    artifact_paths: List[Dict[str, Any]] = Field(default_factory=list)


def _workflow_response(workflow: WorkflowSession) -> WorkflowResponse:
    return WorkflowResponse(**workflow_to_dict(workflow))


def _event_response(event: WorkflowEvent) -> WorkflowEventResponse:
    return WorkflowEventResponse(**event_to_dict(event))


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
        return "Open this region in proofreading and apply mask corrections."
    if severity == "high":
        return "Prioritize this region for proofreading before the next training iteration."
    if workflow.stage in {"visualization", "inference"}:
        return "Inspect this region in visualization and route it into proofreading."
    return "Inspect this region and log whether model output is acceptable."


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
            recommended_action = (
                "Corrections already exist; stage this region's masks for retraining."
            )

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
        next_actions.append("Approve or trigger retraining staging from corrected masks.")
    if workflow.stage == "retraining_staged":
        next_actions.append(
            "Open Model Training and launch the next experiment using staged labels."
        )

    if confidence == "low":
        summary = (
            "Correction evidence is still sparse; prioritize proofreading edits before retraining."
        )
    elif can_stage_retraining:
        summary = (
            "Corrections are substantial enough to justify retraining staging for the next model iteration."
        )
    else:
        summary = (
            "Correction evidence is accumulating; compare outcomes after the next staged loop."
        )

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
        return "The next useful step is to run inference or open proofreading on the current result."
    if workflow.stage == "inference":
        return "Review the inference output and send likely failure regions into proofreading."
    if workflow.stage == "proofreading":
        has_export = any(
            event.event_type == "proofreading.masks_exported" for event in events
        )
        if has_export or workflow.corrected_mask_path:
            return "Corrected masks are available. Stage them for retraining so the next model iteration is linked to the edits."
        return "Continue classifying instances and save or export corrected masks before retraining."
    if workflow.stage == "retraining_staged":
        return "The corrected masks are staged. Review the training configuration before launching retraining."
    return "Review the workflow timeline and compare results before starting another iteration."


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
    return WorkflowExportBundleResponse(**build_export_bundle(workflow, events))


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


@router.post("/{workflow_id}/agent/query", response_model=AgentQueryResponse)
async def query_workflow_agent(
    workflow_id: int,
    body: AgentQueryRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query must be non-empty")

    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    event_rows = _event_rows(db, workflow.id)
    events = _event_list(db, workflow.id)
    recommendation = _recommendation_for_workflow(workflow, events)
    proposals: List[WorkflowEventResponse] = []
    lower_query = body.query.lower()
    wants_retraining = any(
        term in lower_query for term in ["retrain", "training", "stage", "corrected"]
    )
    wants_failure_analysis = any(
        term in lower_query for term in ["fail", "failure", "error", "hotspot", "where"]
    )
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

    if wants_retraining and corrected_mask_path:
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
            "I found a corrected mask artifact and prepared a retraining-stage "
            "proposal. Approve it when you want the app to link those corrections "
            "to the next training configuration."
        )
    elif wants_failure_analysis and hotspots:
        top_hotspot = hotspots[0]
        response = (
            f"Top hotspot: {top_hotspot.summary} "
            f"Recommended action: {top_hotspot.recommended_action} "
            f"Impact preview: {impact.summary}"
        )
    else:
        response = recommendation

    return AgentQueryResponse(response=response, proposals=proposals)
