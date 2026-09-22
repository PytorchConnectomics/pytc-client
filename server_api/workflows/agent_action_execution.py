from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .agent_actions import (
    AgentActionReceipt,
    ComputeEvaluationAction,
    ComputeEvaluationPayload,
    canonical_action_policy,
    load_action_envelope_json,
    load_action_receipt_json,
    validate_action_for_execution,
    validate_receipt_for_action,
)
from .db_models import WorkflowEvent, WorkflowOperation
from .evaluation_service import create_computed_evaluation_result
from .operation_service import (
    create_workflow_operation,
    get_workflow_operation_or_404,
    transition_workflow_operation,
)
from .service import decode_json

_EXECUTOR_LEASE = "agent-action:compute-evaluation"


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate_persisted_action_approval(
    db: Session, envelope: ComputeEvaluationAction
) -> WorkflowEvent:
    """Bind an approved envelope to the matching persisted agent proposal."""

    decision = (
        db.query(WorkflowEvent)
        .filter(
            WorkflowEvent.id == envelope.approval.event_id,
            WorkflowEvent.workflow_id == envelope.workflow_id,
            WorkflowEvent.event_type == "agent.proposal_approved",
            WorkflowEvent.actor == "user",
        )
        .first()
    )
    decision_payload = decode_json(decision.payload_json) if decision else {}
    proposal_id = decision_payload.get("proposal_event_id")
    proposal = (
        db.query(WorkflowEvent)
        .filter(
            WorkflowEvent.id == proposal_id,
            WorkflowEvent.workflow_id == envelope.workflow_id,
            WorkflowEvent.event_type == "agent.proposal_created",
        )
        .first()
    )
    if decision is None or proposal is None or proposal.approval_status != "approved":
        raise HTTPException(
            status_code=409,
            detail=(
                "compute_evaluation requires a matching persisted and approved "
                "agent proposal"
            ),
        )

    proposal_payload = decode_json(proposal.payload_json)
    registry = proposal_payload.get("registry")
    params = proposal_payload.get("params")
    client_effects = params.get("client_effects") if isinstance(params, dict) else None
    workflow_action = (
        client_effects.get("workflow_action")
        if isinstance(client_effects, dict)
        else None
    )
    if (
        not isinstance(registry, dict)
        or registry.get("action_type") != envelope.kind
        or not isinstance(workflow_action, dict)
        or workflow_action.get("kind") != envelope.kind
    ):
        raise HTTPException(
            status_code=409,
            detail="Approval proposal does not match the compute_evaluation envelope",
        )
    proposal_action = ComputeEvaluationPayload.model_validate(
        workflow_action
    ).model_dump(exclude_none=True)
    action_field_names = set(ComputeEvaluationPayload.model_fields)
    envelope_action = envelope.model_dump(
        include=action_field_names,
        exclude_none=True,
    )
    if not envelope_action.get("metadata"):
        envelope_action.pop("metadata", None)
    if proposal_action != envelope_action:
        raise HTTPException(
            status_code=409,
            detail="Approved proposal parameters do not match the action envelope",
        )
    return decision


def stage_and_execute_compute_evaluation_proposal(
    db: Session,
    *,
    workflow_id: int,
    proposal: WorkflowEvent,
    approval_event: WorkflowEvent,
    workflow_action: Dict[str, Any],
    user_id: int,
    correlation_id: Optional[str] = None,
) -> tuple[WorkflowOperation, AgentActionReceipt]:
    action_parameters = ComputeEvaluationPayload.model_validate(
        workflow_action
    ).model_dump(exclude={"kind"}, exclude_none=True)
    input_artifacts = [
        {
            "logical_name": name,
            "artifact_type": "segmentation_volume",
            "role": role,
            "path": path,
        }
        for name, role, path in (
            (
                "baseline-prediction",
                "baseline_prediction",
                action_parameters.get("baseline_prediction_path"),
            ),
            (
                "candidate-prediction",
                "candidate_prediction",
                action_parameters.get("candidate_prediction_path"),
            ),
            (
                "ground-truth",
                "ground_truth",
                action_parameters.get("ground_truth_path"),
            ),
        )
        if path
    ]
    expected_output_artifacts = []
    if action_parameters.get("report_path"):
        expected_output_artifacts.append(
            {
                "logical_name": "evaluation-report",
                "artifact_type": "evaluation_report",
                "role": "case_study_evidence",
                "path": action_parameters["report_path"],
            }
        )
    resolved_correlation_id = correlation_id or f"agent-proposal:{proposal.id}"
    envelope = validate_action_for_execution(
        {
            "action_id": f"proposal:{proposal.id}:compute_evaluation",
            "kind": "compute_evaluation",
            "workflow_id": workflow_id,
            "requested_by": "agent",
            "idempotency_key": f"agent-proposal:{proposal.id}:compute_evaluation",
            "correlation_id": resolved_correlation_id,
            "execution_owner": "server_workflow",
            "policy": canonical_action_policy("compute_evaluation").model_dump(),
            "approval": {
                "status": "approved",
                "event_id": approval_event.id,
                "decided_by": f"user:{user_id}",
            },
            "input_artifacts": input_artifacts,
            "expected_output_artifacts": expected_output_artifacts,
            **action_parameters,
        }
    )
    if not isinstance(envelope, ComputeEvaluationAction):  # pragma: no cover
        raise TypeError("compute evaluation proposal resolved to another action type")
    validate_persisted_action_approval(db, envelope)
    operation = create_workflow_operation(
        db,
        workflow_id=workflow_id,
        operation_type="agent_action:compute_evaluation",
        idempotency_key=envelope.idempotency_key,
        correlation_id=envelope.correlation_id,
        actor=envelope.requested_by,
        input_payload=envelope.model_dump(mode="json", exclude_none=True),
        metadata={
            "action_id": envelope.action_id,
            "action_schema_version": envelope.schema_version,
            "approval_event_id": approval_event.id,
            "proposal_event_id": proposal.id,
            "execution_owner": envelope.execution_owner,
            "risk_level": envelope.policy.risk_level,
        },
        commit=True,
    )
    receipt = execute_compute_evaluation_operation(db, operation)
    operation = get_workflow_operation_or_404(
        db,
        workflow_id=workflow_id,
        operation_id=operation.id,
    )
    return operation, receipt


def _flatten_receipt_metrics(metrics: Dict[str, Any]) -> Dict[str, float]:
    flattened: Dict[str, float] = {}
    for section in ("baseline", "candidate", "delta"):
        values = metrics.get(section)
        if not isinstance(values, dict):
            continue
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            flattened[f"{section}_{name}"] = float(value)
    return flattened


def _stored_receipt(operation: WorkflowOperation) -> Optional[AgentActionReceipt]:
    payload = decode_json(operation.result_json).get("receipt")
    if not isinstance(payload, dict):
        return None
    action = load_action_envelope_json(operation.input_json or "{}")
    receipt = load_action_receipt_json(json.dumps(payload))
    return validate_receipt_for_action(action, receipt)


def _failure_details(exc: Exception) -> Dict[str, Any]:
    if isinstance(exc, (FileNotFoundError, ValueError)):
        return {
            "code": "evaluation_input_invalid",
            "retryable": False,
        }
    if isinstance(exc, RuntimeError):
        return {
            "code": "evaluation_runtime_failed",
            "retryable": True,
        }
    return {
        "code": "evaluation_handler_failed",
        "retryable": False,
    }


def execute_compute_evaluation_operation(
    db: Session, operation: WorkflowOperation
) -> AgentActionReceipt:
    envelope = load_action_envelope_json(operation.input_json or "{}")
    if envelope.policy.requires_approval and envelope.approval.status != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"{envelope.kind} cannot execute without an approved action envelope",
        )
    if not isinstance(envelope, ComputeEvaluationAction):
        raise HTTPException(
            status_code=409,
            detail="Only compute_evaluation operations are executable on this route",
        )
    if operation.operation_type != "agent_action:compute_evaluation":
        raise HTTPException(
            status_code=409,
            detail="Workflow operation type does not match compute_evaluation",
        )
    validate_persisted_action_approval(db, envelope)

    if operation.status in {"succeeded", "failed", "cancelled"}:
        receipt = _stored_receipt(operation)
        if receipt is None:
            raise HTTPException(
                status_code=409,
                detail="Terminal operation does not contain a typed action receipt",
            )
        return receipt
    if operation.status != "queued":
        raise HTTPException(
            status_code=409,
            detail=f"Operation cannot execute from {operation.status}",
        )

    operation = transition_workflow_operation(
        db,
        operation,
        status="running",
        expected_status="queued",
        progress=0.05,
        lease_owner=_EXECUTOR_LEASE,
        commit=True,
    )
    started_at = _as_utc(operation.started_at) or _now()

    try:
        required_paths = {
            "baseline_prediction_path": envelope.baseline_prediction_path,
            "candidate_prediction_path": envelope.candidate_prediction_path,
            "ground_truth_path": envelope.ground_truth_path,
        }
        missing = [name for name, value in required_paths.items() if not value]
        if missing:
            raise ValueError(
                "compute_evaluation is missing required fields: " + ", ".join(missing)
            )

        evaluation = create_computed_evaluation_result(
            db,
            workflow_id=envelope.workflow_id,
            baseline_prediction_path=envelope.baseline_prediction_path,
            candidate_prediction_path=envelope.candidate_prediction_path,
            ground_truth_path=envelope.ground_truth_path,
            baseline_dataset=envelope.baseline_dataset,
            candidate_dataset=envelope.candidate_dataset,
            ground_truth_dataset=envelope.ground_truth_dataset,
            crop=envelope.crop,
            baseline_channel=envelope.baseline_channel,
            candidate_channel=envelope.candidate_channel,
            ground_truth_channel=envelope.ground_truth_channel,
            name=envelope.name,
            baseline_run_id=envelope.baseline_run_id,
            candidate_run_id=envelope.candidate_run_id,
            model_version_id=envelope.model_version_id,
            report_path=envelope.report_path,
            metadata={
                **envelope.metadata,
                "action_id": envelope.action_id,
                "correlation_id": envelope.correlation_id,
                "operation_id": operation.id,
            },
            commit=False,
        )
        metrics = decode_json(evaluation.metrics_json)
        produced_artifacts = []
        if evaluation.report_artifact_id:
            produced_artifacts.append(
                {
                    "artifact_id": evaluation.report_artifact_id,
                    "artifact_type": "evaluation_report",
                    "role": "case_study_evidence",
                    "path": evaluation.report_path,
                }
            )
        receipt_payload = {
            "receipt_id": f"operation:{operation.id}:receipt",
            "action_id": envelope.action_id,
            "kind": envelope.kind,
            "workflow_id": envelope.workflow_id,
            "idempotency_key": envelope.idempotency_key,
            "correlation_id": envelope.correlation_id,
            "status": "succeeded",
            "operation_id": operation.id,
            "produced_artifacts": produced_artifacts,
            "evaluation_result_id": evaluation.id,
            "metrics": _flatten_receipt_metrics(metrics),
            "started_at": started_at,
            "completed_at": _now(),
        }
        receipt = validate_receipt_for_action(envelope, receipt_payload)
        operation = transition_workflow_operation(
            db,
            operation,
            status="succeeded",
            expected_status="running",
            lease_owner=_EXECUTOR_LEASE,
            result_payload={
                "receipt": receipt.model_dump(mode="json"),
                "evidence": {
                    "evaluation_result_id": evaluation.id,
                    "report_artifact_id": evaluation.report_artifact_id,
                    "report_path": evaluation.report_path,
                    "metrics": metrics,
                },
            },
            commit=True,
        )
        return receipt
    except Exception as exc:
        db.rollback()
        operation = get_workflow_operation_or_404(
            db,
            workflow_id=envelope.workflow_id,
            operation_id=operation.id,
        )
        failure = _failure_details(exc)
        message = str(exc).strip() or "Evaluation handler failed"
        receipt_payload = {
            "receipt_id": f"operation:{operation.id}:receipt",
            "action_id": envelope.action_id,
            "kind": envelope.kind,
            "workflow_id": envelope.workflow_id,
            "idempotency_key": envelope.idempotency_key,
            "correlation_id": envelope.correlation_id,
            "status": "failed",
            "operation_id": operation.id,
            "error": {
                **failure,
                "message": message[:500],
                "details": {"exception_type": type(exc).__name__},
            },
            "started_at": started_at,
            "completed_at": _now(),
        }
        receipt = validate_receipt_for_action(envelope, receipt_payload)
        operation = transition_workflow_operation(
            db,
            operation,
            status="failed",
            expected_status="running",
            lease_owner=_EXECUTOR_LEASE,
            result_payload={"receipt": receipt.model_dump(mode="json")},
            error_payload=receipt.error.model_dump(mode="json"),
            commit=True,
        )
        return receipt
