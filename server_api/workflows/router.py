from __future__ import annotations

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
    events = _event_list(db, workflow.id)
    recommendation = _recommendation_for_workflow(workflow, events)
    proposals: List[WorkflowEventResponse] = []
    lower_query = body.query.lower()
    wants_retraining = any(
        term in lower_query for term in ["retrain", "training", "stage", "corrected"]
    )
    corrected_mask_path = workflow.corrected_mask_path or _latest_exported_mask_path(
        db, workflow.id
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
    else:
        response = recommendation

    return AgentQueryResponse(response=response, proposals=proposals)
