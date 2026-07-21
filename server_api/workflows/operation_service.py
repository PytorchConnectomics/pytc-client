from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db_models import (
    WorkflowCommand,
    WorkflowModelRun,
    WorkflowOperation,
)
from .service import decode_json, encode_json, validate_actor

OPERATION_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}
TERMINAL_OPERATION_STATUSES = {"succeeded", "failed", "cancelled"}
OPERATION_TRANSITIONS = {
    "queued": {"running", "failed", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _merge_dicts(
    base: Optional[Dict[str, Any]], patch: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    merged = dict(base or {})
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_progress(progress: Optional[float]) -> Optional[float]:
    if progress is None:
        return None
    value = float(progress)
    if value < 0 or value > 1:
        raise HTTPException(status_code=400, detail="progress must be between 0 and 1")
    return value


def operation_to_dict(operation: WorkflowOperation) -> Dict[str, Any]:
    return {
        "id": operation.id,
        "workflow_id": operation.workflow_id,
        "operation_type": operation.operation_type,
        "status": operation.status,
        "idempotency_key": operation.idempotency_key,
        "correlation_id": operation.correlation_id,
        "actor": operation.actor,
        "command_id": operation.command_id,
        "model_run_id": operation.model_run_id,
        "input": decode_json(operation.input_json),
        "result": decode_json(operation.result_json),
        "error": decode_json(operation.error_json),
        "metadata": decode_json(operation.metadata_json),
        "progress": operation.progress,
        "attempt_count": operation.attempt_count,
        "lease_owner": operation.lease_owner,
        "lease_expires_at": operation.lease_expires_at,
        "heartbeat_at": operation.heartbeat_at,
        "cancellation_requested_at": operation.cancellation_requested_at,
        "started_at": operation.started_at,
        "completed_at": operation.completed_at,
        "created_at": operation.created_at,
        "updated_at": operation.updated_at,
    }


def get_workflow_operation_or_404(
    db: Session, *, workflow_id: int, operation_id: int
) -> WorkflowOperation:
    operation = (
        db.query(WorkflowOperation)
        .filter(
            WorkflowOperation.id == operation_id,
            WorkflowOperation.workflow_id == workflow_id,
        )
        .first()
    )
    if operation is None:
        raise HTTPException(status_code=404, detail="Workflow operation not found")
    return operation


def _validate_linked_record(
    db: Session,
    *,
    model: Any,
    record_id: Optional[int],
    workflow_id: int,
    label: str,
) -> None:
    if record_id is None:
        return
    record = db.query(model).filter(model.id == record_id).first()
    if record is None or record.workflow_id != workflow_id:
        raise HTTPException(
            status_code=400,
            detail=f"{label} must belong to the workflow",
        )


def _assert_idempotent_match(
    operation: WorkflowOperation,
    *,
    operation_type: str,
    actor: str,
    command_id: Optional[int],
    model_run_id: Optional[int],
    input_payload: Dict[str, Any],
    metadata: Dict[str, Any],
) -> WorkflowOperation:
    expected = {
        "operation_type": operation_type,
        "actor": actor,
        "command_id": command_id,
        "model_run_id": model_run_id,
        "input": input_payload,
        "metadata": metadata,
    }
    actual = {
        "operation_type": operation.operation_type,
        "actor": operation.actor,
        "command_id": operation.command_id,
        "model_run_id": operation.model_run_id,
        "input": decode_json(operation.input_json),
        "metadata": decode_json(operation.metadata_json),
    }
    if actual != expected:
        raise HTTPException(
            status_code=409,
            detail="idempotency_key is already used by a different operation request",
        )
    return operation


def create_workflow_operation(
    db: Session,
    *,
    workflow_id: int,
    operation_type: str,
    idempotency_key: str,
    correlation_id: Optional[str] = None,
    actor: str = "system",
    command_id: Optional[int] = None,
    model_run_id: Optional[int] = None,
    input_payload: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> WorkflowOperation:
    operation_type = operation_type.strip()
    idempotency_key = idempotency_key.strip()
    if not operation_type:
        raise HTTPException(status_code=400, detail="operation_type is required")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="idempotency_key is required")
    correlation_id = (correlation_id or str(uuid4())).strip()
    if not correlation_id:
        raise HTTPException(status_code=400, detail="correlation_id cannot be blank")
    actor = validate_actor(actor)
    input_payload = input_payload or {}
    metadata = metadata or {}
    _validate_linked_record(
        db,
        model=WorkflowCommand,
        record_id=command_id,
        workflow_id=workflow_id,
        label="command_id",
    )
    _validate_linked_record(
        db,
        model=WorkflowModelRun,
        record_id=model_run_id,
        workflow_id=workflow_id,
        label="model_run_id",
    )

    existing = (
        db.query(WorkflowOperation)
        .filter(
            WorkflowOperation.workflow_id == workflow_id,
            WorkflowOperation.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing is not None:
        return _assert_idempotent_match(
            existing,
            operation_type=operation_type,
            actor=actor,
            command_id=command_id,
            model_run_id=model_run_id,
            input_payload=input_payload,
            metadata=metadata,
        )

    operation = WorkflowOperation(
        workflow_id=workflow_id,
        operation_type=operation_type,
        status="queued",
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        actor=actor,
        command_id=command_id,
        model_run_id=model_run_id,
        input_json=encode_json(input_payload),
        metadata_json=encode_json(metadata),
    )
    try:
        with db.begin_nested():
            db.add(operation)
            db.flush()
    except IntegrityError:
        existing = (
            db.query(WorkflowOperation)
            .filter(
                WorkflowOperation.workflow_id == workflow_id,
                WorkflowOperation.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is None:
            raise
        operation = _assert_idempotent_match(
            existing,
            operation_type=operation_type,
            actor=actor,
            command_id=command_id,
            model_run_id=model_run_id,
            input_payload=input_payload,
            metadata=metadata,
        )
    if commit:
        db.commit()
        db.refresh(operation)
    return operation


def transition_workflow_operation(
    db: Session,
    operation: WorkflowOperation,
    *,
    status: str,
    expected_status: Optional[str] = None,
    result_payload: Optional[Dict[str, Any]] = None,
    error_payload: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    progress: Optional[float] = None,
    lease_owner: Optional[str] = None,
    lease_expires_at: Optional[datetime] = None,
    commit: bool = False,
) -> WorkflowOperation:
    if status not in OPERATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "operation status must be one of: "
                f"{', '.join(sorted(OPERATION_STATUSES))}"
            ),
        )
    if expected_status is not None and operation.status != expected_status:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Operation status changed: expected {expected_status}, "
                f"found {operation.status}"
            ),
        )
    if (
        operation.status == "running"
        and operation.lease_owner
        and status in TERMINAL_OPERATION_STATUSES
        and lease_owner != operation.lease_owner
    ):
        raise HTTPException(
            status_code=409, detail="Operation is leased by another worker"
        )
    if operation.status == status and status in TERMINAL_OPERATION_STATUSES:
        return operation
    if status not in OPERATION_TRANSITIONS[operation.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Operation cannot transition from {operation.status} to {status}",
        )

    now = _now()
    operation.status = status
    if metadata is not None:
        operation.metadata_json = encode_json(
            _merge_dicts(decode_json(operation.metadata_json), metadata)
        )
    if progress is not None:
        operation.progress = _validate_progress(progress)

    if status == "running":
        operation.attempt_count = int(operation.attempt_count or 0) + 1
        operation.started_at = operation.started_at or now
        operation.completed_at = None
        operation.heartbeat_at = now
        operation.lease_owner = lease_owner
        operation.lease_expires_at = lease_expires_at
        operation.error_json = None
    else:
        operation.completed_at = now
        operation.lease_owner = None
        operation.lease_expires_at = None
        if status == "succeeded":
            operation.progress = 1.0
            operation.result_json = encode_json(result_payload or {})
            operation.error_json = None
        elif status == "failed":
            if result_payload is not None:
                operation.result_json = encode_json(result_payload)
            operation.error_json = encode_json(error_payload or {})
        elif status == "cancelled" and error_payload is not None:
            operation.error_json = encode_json(error_payload)

    db.flush()
    if commit:
        db.commit()
        db.refresh(operation)
    return operation


def heartbeat_workflow_operation(
    db: Session,
    operation: WorkflowOperation,
    *,
    progress: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    lease_owner: Optional[str] = None,
    lease_expires_at: Optional[datetime] = None,
    commit: bool = False,
) -> WorkflowOperation:
    if operation.status != "running":
        raise HTTPException(
            status_code=409,
            detail="Only running operations can receive heartbeats",
        )
    if lease_owner and operation.lease_owner and lease_owner != operation.lease_owner:
        raise HTTPException(
            status_code=409, detail="Operation is leased by another worker"
        )
    operation.heartbeat_at = _now()
    if progress is not None:
        operation.progress = _validate_progress(progress)
    if metadata is not None:
        operation.metadata_json = encode_json(
            _merge_dicts(decode_json(operation.metadata_json), metadata)
        )
    if lease_owner is not None:
        operation.lease_owner = lease_owner
    if lease_expires_at is not None:
        operation.lease_expires_at = lease_expires_at
    db.flush()
    if commit:
        db.commit()
        db.refresh(operation)
    return operation


def request_workflow_operation_cancellation(
    db: Session,
    operation: WorkflowOperation,
    *,
    reason: Optional[str] = None,
    commit: bool = False,
) -> WorkflowOperation:
    if operation.status in TERMINAL_OPERATION_STATUSES:
        return operation
    now = _now()
    operation.cancellation_requested_at = operation.cancellation_requested_at or now
    if reason:
        operation.metadata_json = encode_json(
            _merge_dicts(
                decode_json(operation.metadata_json),
                {"cancellation": {"reason": reason}},
            )
        )
    if operation.status == "queued":
        operation.status = "cancelled"
        operation.completed_at = now
    db.flush()
    if commit:
        db.commit()
        db.refresh(operation)
    return operation
