"""Project correlated PyTC runtime snapshots onto durable workflow operations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .db_models import WorkflowOperation, WorkflowSession
from .operation_service import (
    TERMINAL_OPERATION_STATUSES,
    operation_to_dict,
    transition_workflow_operation,
)
from .service import (
    append_event_for_workflow_if_present,
    decode_json,
    update_workflow_fields,
)

RUNTIME_OPERATION_KINDS = {
    "start_training": "training",
    "start_inference": "inference",
}


def runtime_kind_for_operation(operation: WorkflowOperation) -> Optional[str]:
    return RUNTIME_OPERATION_KINDS.get(operation.operation_type)


def _metadata_value(metadata: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _snapshot_metadata(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    metadata = snapshot.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _is_correlated(
    operation: WorkflowOperation,
    workflow: WorkflowSession,
    snapshot: Dict[str, Any],
) -> bool:
    metadata = _snapshot_metadata(snapshot)
    operation_metadata = decode_json(operation.metadata_json)
    expected_run_id = _metadata_value(operation_metadata, "run_id", "runId")
    actual_workflow_id = _metadata_value(metadata, "workflowId", "workflow_id")
    actual_command_id = _metadata_value(metadata, "commandId", "command_id")
    actual_run_id = _metadata_value(metadata, "runId", "run_id")

    # A worker snapshot without all identifiers may belong to an older direct
    # browser launch. Never project that global process state onto this command.
    return (
        actual_workflow_id == str(workflow.id)
        and actual_command_id == str(operation.command_id)
        and bool(expected_run_id)
        and actual_run_id == expected_run_id
    )


def _runtime_details(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _snapshot_metadata(snapshot)
    return {
        "runtimePhase": snapshot.get("phase"),
        "runtimePid": snapshot.get("pid"),
        "runtimeExitCode": snapshot.get("exitCode"),
        "runtimeStartedAt": snapshot.get("startedAt"),
        "runtimeEndedAt": snapshot.get("endedAt"),
        "runtimeLastError": snapshot.get("lastError"),
        "runtimeLineCount": snapshot.get("lineCount"),
        "runtimeMetadata": metadata,
    }


def _terminal_status(
    operation: WorkflowOperation, snapshot: Dict[str, Any]
) -> Optional[str]:
    phase = str(snapshot.get("phase") or "").lower()
    exit_code = snapshot.get("exitCode")
    if phase == "finished" and exit_code == 0:
        return "succeeded"
    if phase == "stopped":
        return "cancelled" if operation.cancellation_requested_at else "failed"
    if phase == "failed" or (exit_code is not None and exit_code != 0):
        return "failed"
    return None


def reconcile_runtime_operation(
    db: Session,
    *,
    workflow: WorkflowSession,
    operation: WorkflowOperation,
    snapshot: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Idempotently reconcile one worker snapshot into a durable operation.

    The caller owns worker transport. This module intentionally accepts snapshots
    only after verifying all durable correlators, preventing a process-global
    worker state from completing an unrelated workflow command.
    """
    runtime_kind = runtime_kind_for_operation(operation)
    if runtime_kind is None:
        return {"operation": operation, "reconciled": False, "reason": "unsupported"}
    if operation.status in TERMINAL_OPERATION_STATUSES:
        return {"operation": operation, "reconciled": False, "reason": "terminal"}
    if not isinstance(snapshot, dict):
        return {
            "operation": operation,
            "reconciled": False,
            "reason": "invalid_snapshot",
        }
    if not _is_correlated(operation, workflow, snapshot):
        return {
            "operation": operation,
            "reconciled": False,
            "reason": "correlation_mismatch",
        }

    terminal_status = _terminal_status(operation, snapshot)
    if terminal_status is None:
        return {
            "operation": operation,
            "reconciled": False,
            "reason": "runtime_not_terminal",
        }

    details = _runtime_details(snapshot)
    metadata = _snapshot_metadata(snapshot)
    operation_metadata = decode_json(operation.metadata_json)
    run_id = _metadata_value(operation_metadata, "run_id", "runId")
    output_directory = _metadata_value(metadata, "outputPath", "output_path")
    checkpoint_path = _metadata_value(
        metadata, "checkpointPath", "latestCheckpointPath", "checkpoint"
    )
    prediction_path = _metadata_value(
        metadata,
        "predictionPath",
        "latestPredictionPath",
        "outputPredictionPath",
    )
    output_path = prediction_path if runtime_kind == "inference" else output_directory
    event_suffix = {
        "succeeded": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
    }[terminal_status]
    event_type = f"{runtime_kind}.{event_suffix}"
    event_payload = {
        "source": "runtime_reconciliation",
        "operation_id": operation.id,
        "command_id": operation.command_id,
        "run_id": run_id,
        "outputPath": output_path,
        "outputDirectory": output_directory,
        "checkpointPath": checkpoint_path,
        "predictionPath": prediction_path,
        **details,
    }
    error_payload = None
    if terminal_status == "failed":
        error_payload = {
            "error": (
                "RuntimeStopped"
                if snapshot.get("phase") == "stopped"
                else "RuntimeFailed"
            ),
            "detail": snapshot.get("lastError")
            or f"{runtime_kind} runtime ended with phase {snapshot.get('phase')!r}",
            "exit_code": snapshot.get("exitCode"),
        }
    terminal_event_payload = (
        event_payload
        if terminal_status == "succeeded"
        else {**event_payload, **(error_payload or {})}
    )

    operation = transition_workflow_operation(
        db,
        operation,
        status=terminal_status,
        expected_status=operation.status,
        result_payload=event_payload if terminal_status == "succeeded" else None,
        error_payload=error_payload,
        metadata={"runtime_terminal": details},
        lease_owner=operation.lease_owner,
        commit=False,
    )
    updates: Dict[str, Any] = {}
    if runtime_kind == "training":
        if output_directory:
            updates["training_output_path"] = output_directory
        if checkpoint_path:
            updates["checkpoint_path"] = checkpoint_path
    elif prediction_path:
        updates["inference_output_path"] = prediction_path
    if updates:
        update_workflow_fields(db, workflow, updates, commit=False)

    append_event_for_workflow_if_present(
        db,
        workflow_id=workflow.id,
        actor="system",
        event_type=event_type,
        stage=workflow.stage,
        summary=f"Synchronized {terminal_status} {runtime_kind} runtime.",
        payload=terminal_event_payload,
        idempotency_key=f"workflow-operation:{operation.id}:runtime-terminal",
    )
    db.refresh(operation)
    return {"operation": operation, "reconciled": True, "reason": "terminal"}


def reconciliation_response(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "operation": operation_to_dict(result["operation"]),
        "reconciled": bool(result["reconciled"]),
        "reason": result["reason"],
    }
