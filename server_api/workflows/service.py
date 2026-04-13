import json
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .db_models import WorkflowEvent, WorkflowSession

ALLOWED_STAGES = {
    "setup",
    "visualization",
    "inference",
    "proofreading",
    "retraining_staged",
    "evaluation",
}

ALLOWED_ACTORS = {"user", "agent", "system"}
ALLOWED_APPROVAL_STATUSES = {"not_required", "pending", "approved", "rejected"}


def encode_json(value: Optional[Dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def decode_json(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def validate_stage(stage: Optional[str]) -> Optional[str]:
    if stage is None:
        return None
    if stage not in ALLOWED_STAGES:
        raise HTTPException(
            status_code=400,
            detail=f"stage must be one of: {', '.join(sorted(ALLOWED_STAGES))}",
        )
    return stage


def validate_actor(actor: str) -> str:
    if actor not in ALLOWED_ACTORS:
        raise HTTPException(
            status_code=400,
            detail=f"actor must be one of: {', '.join(sorted(ALLOWED_ACTORS))}",
        )
    return actor


def validate_approval_status(status: str) -> str:
    if status not in ALLOWED_APPROVAL_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "approval_status must be one of: "
                f"{', '.join(sorted(ALLOWED_APPROVAL_STATUSES))}"
            ),
        )
    return status


def event_to_dict(event: WorkflowEvent) -> Dict[str, Any]:
    return {
        "id": event.id,
        "workflow_id": event.workflow_id,
        "actor": event.actor,
        "event_type": event.event_type,
        "stage": event.stage,
        "summary": event.summary,
        "payload_json": event.payload_json,
        "payload": decode_json(event.payload_json),
        "approval_status": event.approval_status,
        "created_at": event.created_at,
    }


def workflow_to_dict(workflow: WorkflowSession) -> Dict[str, Any]:
    return {
        "id": workflow.id,
        "user_id": workflow.user_id,
        "title": workflow.title,
        "stage": workflow.stage,
        "dataset_path": workflow.dataset_path,
        "image_path": workflow.image_path,
        "label_path": workflow.label_path,
        "mask_path": workflow.mask_path,
        "neuroglancer_url": workflow.neuroglancer_url,
        "inference_output_path": workflow.inference_output_path,
        "checkpoint_path": workflow.checkpoint_path,
        "proofreading_session_id": workflow.proofreading_session_id,
        "corrected_mask_path": workflow.corrected_mask_path,
        "training_output_path": workflow.training_output_path,
        "metadata_json": workflow.metadata_json,
        "metadata": decode_json(workflow.metadata_json),
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
    }


def get_user_workflow_or_404(
    db: Session, *, workflow_id: int, user_id: int
) -> WorkflowSession:
    workflow = (
        db.query(WorkflowSession)
        .filter(WorkflowSession.id == workflow_id, WorkflowSession.user_id == user_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


def get_current_or_create_workflow(db: Session, *, user_id: int) -> WorkflowSession:
    workflow = (
        db.query(WorkflowSession)
        .filter(WorkflowSession.user_id == user_id)
        .order_by(WorkflowSession.updated_at.desc(), WorkflowSession.id.desc())
        .first()
    )
    if workflow:
        return workflow

    workflow = WorkflowSession(user_id=user_id, title="Segmentation Workflow")
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    append_workflow_event(
        db,
        workflow_id=workflow.id,
        actor="system",
        event_type="workflow.created",
        stage=workflow.stage,
        summary="Workflow session created.",
        commit=True,
    )
    db.refresh(workflow)
    return workflow


WORKFLOW_PATCH_FIELDS = {
    "title",
    "stage",
    "dataset_path",
    "image_path",
    "label_path",
    "mask_path",
    "neuroglancer_url",
    "inference_output_path",
    "checkpoint_path",
    "proofreading_session_id",
    "corrected_mask_path",
    "training_output_path",
}


def update_workflow_fields(
    db: Session,
    workflow: WorkflowSession,
    updates: Dict[str, Any],
    *,
    commit: bool = True,
) -> WorkflowSession:
    for key, value in updates.items():
        if key == "metadata":
            workflow.metadata_json = encode_json(value if isinstance(value, dict) else {})
            continue
        if key == "metadata_json":
            workflow.metadata_json = value
            continue
        if key not in WORKFLOW_PATCH_FIELDS:
            continue
        if key == "stage":
            if value is None:
                continue
            value = validate_stage(value)
        setattr(workflow, key, value)

    if commit:
        db.commit()
        db.refresh(workflow)
    return workflow


def append_workflow_event(
    db: Session,
    *,
    workflow_id: Optional[int],
    actor: str,
    event_type: str,
    summary: str,
    stage: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    approval_status: str = "not_required",
    commit: bool = True,
) -> Optional[WorkflowEvent]:
    if not workflow_id:
        return None
    actor = validate_actor(actor)
    approval_status = validate_approval_status(approval_status)
    stage = validate_stage(stage) if stage else stage
    event = WorkflowEvent(
        workflow_id=workflow_id,
        actor=actor,
        event_type=event_type,
        stage=stage,
        summary=summary,
        payload_json=encode_json(payload),
        approval_status=approval_status,
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    return event


def append_event_for_workflow_if_present(
    db: Session,
    *,
    workflow_id: Optional[int],
    actor: str,
    event_type: str,
    summary: str,
    stage: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[WorkflowEvent]:
    if not workflow_id:
        return None
    return append_workflow_event(
        db,
        workflow_id=workflow_id,
        actor=actor,
        event_type=event_type,
        summary=summary,
        stage=stage,
        payload=payload,
        commit=True,
    )
