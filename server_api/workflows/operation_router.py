from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server_api.auth import models as auth_models
from server_api.auth.database import get_db
from server_api.auth.router import get_current_user

from .db_models import WorkflowOperation
from .operation_service import (
    OPERATION_STATUSES,
    create_workflow_operation,
    get_workflow_operation_or_404,
    heartbeat_workflow_operation,
    operation_to_dict,
    request_workflow_operation_cancellation,
    transition_workflow_operation,
)
from .service import get_user_workflow_or_404

router = APIRouter()


class WorkflowOperationCreateRequest(BaseModel):
    operation_type: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=255)
    correlation_id: Optional[str] = Field(default=None, max_length=255)
    actor: str = "system"
    command_id: Optional[int] = None
    model_run_id: Optional[int] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowOperationTransitionRequest(BaseModel):
    status: str
    expected_status: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    progress: Optional[float] = None
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None


class WorkflowOperationHeartbeatRequest(BaseModel):
    progress: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None


class WorkflowOperationCancellationRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)


class WorkflowOperationResponse(BaseModel):
    id: int
    workflow_id: int
    operation_type: str
    status: str
    idempotency_key: str
    correlation_id: str
    actor: str
    command_id: Optional[int] = None
    model_run_id: Optional[int] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    progress: Optional[float] = None
    attempt_count: int = 0
    lease_owner: Optional[str] = None
    lease_expires_at: Any = None
    heartbeat_at: Any = None
    cancellation_requested_at: Any = None
    started_at: Any = None
    completed_at: Any = None
    created_at: Any
    updated_at: Any


def _response(operation: WorkflowOperation) -> WorkflowOperationResponse:
    return WorkflowOperationResponse(**operation_to_dict(operation))


def _owned_operation(
    db: Session,
    *,
    workflow_id: int,
    operation_id: int,
    user_id: int,
) -> WorkflowOperation:
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user_id)
    return get_workflow_operation_or_404(
        db,
        workflow_id=workflow_id,
        operation_id=operation_id,
    )


@router.post(
    "/{workflow_id}/operations",
    response_model=WorkflowOperationResponse,
)
def create_operation(
    workflow_id: int,
    body: WorkflowOperationCreateRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    operation = create_workflow_operation(
        db,
        workflow_id=workflow.id,
        operation_type=body.operation_type,
        idempotency_key=body.idempotency_key,
        correlation_id=body.correlation_id,
        actor=body.actor,
        command_id=body.command_id,
        model_run_id=body.model_run_id,
        input_payload=body.input,
        metadata=body.metadata,
        commit=True,
    )
    return _response(operation)


@router.get(
    "/{workflow_id}/operations",
    response_model=List[WorkflowOperationResponse],
)
def list_operations(
    workflow_id: int,
    status: Optional[str] = None,
    operation_type: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    if status is not None and status not in OPERATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "operation status must be one of: "
                f"{', '.join(sorted(OPERATION_STATUSES))}"
            ),
        )
    query = db.query(WorkflowOperation).filter(
        WorkflowOperation.workflow_id == workflow_id
    )
    if status is not None:
        query = query.filter(WorkflowOperation.status == status)
    if operation_type is not None:
        query = query.filter(WorkflowOperation.operation_type == operation_type)
    operations = query.order_by(
        WorkflowOperation.created_at.desc(), WorkflowOperation.id.desc()
    ).limit(limit)
    return [_response(operation) for operation in operations]


@router.get(
    "/{workflow_id}/operations/{operation_id}",
    response_model=WorkflowOperationResponse,
)
def get_operation(
    workflow_id: int,
    operation_id: int,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _response(
        _owned_operation(
            db,
            workflow_id=workflow_id,
            operation_id=operation_id,
            user_id=user.id,
        )
    )


@router.post(
    "/{workflow_id}/operations/{operation_id}/transitions",
    response_model=WorkflowOperationResponse,
)
def transition_operation(
    workflow_id: int,
    operation_id: int,
    body: WorkflowOperationTransitionRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    operation = _owned_operation(
        db,
        workflow_id=workflow_id,
        operation_id=operation_id,
        user_id=user.id,
    )
    operation = transition_workflow_operation(
        db,
        operation,
        status=body.status,
        expected_status=body.expected_status,
        result_payload=body.result,
        error_payload=body.error,
        metadata=body.metadata,
        progress=body.progress,
        lease_owner=body.lease_owner,
        lease_expires_at=body.lease_expires_at,
        commit=True,
    )
    return _response(operation)


@router.post(
    "/{workflow_id}/operations/{operation_id}/heartbeat",
    response_model=WorkflowOperationResponse,
)
def heartbeat_operation(
    workflow_id: int,
    operation_id: int,
    body: WorkflowOperationHeartbeatRequest,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    operation = _owned_operation(
        db,
        workflow_id=workflow_id,
        operation_id=operation_id,
        user_id=user.id,
    )
    operation = heartbeat_workflow_operation(
        db,
        operation,
        progress=body.progress,
        metadata=body.metadata,
        lease_owner=body.lease_owner,
        lease_expires_at=body.lease_expires_at,
        commit=True,
    )
    return _response(operation)


@router.post(
    "/{workflow_id}/operations/{operation_id}/cancel",
    response_model=WorkflowOperationResponse,
)
def cancel_operation(
    workflow_id: int,
    operation_id: int,
    body: Optional[WorkflowOperationCancellationRequest] = None,
    user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    operation = _owned_operation(
        db,
        workflow_id=workflow_id,
        operation_id=operation_id,
        user_id=user.id,
    )
    operation = request_workflow_operation_cancellation(
        db,
        operation,
        reason=body.reason if body else None,
        commit=True,
    )
    return _response(operation)
