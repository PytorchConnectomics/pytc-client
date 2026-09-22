from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .db_models import WorkflowEvaluationResult
from .evaluation import compute_before_after_evaluation, write_evaluation_report
from .service import create_workflow_artifact, encode_json


def create_computed_evaluation_result(
    db: Session,
    *,
    workflow_id: int,
    baseline_prediction_path: str,
    candidate_prediction_path: str,
    ground_truth_path: str,
    baseline_dataset: Optional[str] = None,
    candidate_dataset: Optional[str] = None,
    ground_truth_dataset: Optional[str] = None,
    crop: Optional[str] = None,
    baseline_channel: Optional[int] = None,
    candidate_channel: Optional[int] = None,
    ground_truth_channel: Optional[int] = None,
    name: Optional[str] = None,
    baseline_run_id: Optional[int] = None,
    candidate_run_id: Optional[int] = None,
    model_version_id: Optional[int] = None,
    report_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> WorkflowEvaluationResult:
    """Compute and persist the canonical before/after evaluation record."""

    metrics = compute_before_after_evaluation(
        baseline_prediction_path=baseline_prediction_path,
        candidate_prediction_path=candidate_prediction_path,
        ground_truth_path=ground_truth_path,
        baseline_dataset=baseline_dataset,
        candidate_dataset=candidate_dataset,
        ground_truth_dataset=ground_truth_dataset,
        crop=crop,
        baseline_channel=baseline_channel,
        candidate_channel=candidate_channel,
        ground_truth_channel=ground_truth_channel,
    )
    evaluation_metadata = {
        **(metadata or {}),
        "baseline_prediction_path": baseline_prediction_path,
        "candidate_prediction_path": candidate_prediction_path,
        "ground_truth_path": ground_truth_path,
        "baseline_dataset": baseline_dataset,
        "candidate_dataset": candidate_dataset,
        "ground_truth_dataset": ground_truth_dataset,
        "crop": crop,
        "baseline_channel": baseline_channel,
        "candidate_channel": candidate_channel,
        "ground_truth_channel": ground_truth_channel,
    }
    summary = (
        "Before/after evaluation computed. "
        f"Dice delta: {metrics.get('summary', {}).get('dice_delta')}."
    )

    persisted_report_path = report_path
    if persisted_report_path:
        report_payload = {
            "workflow_id": workflow_id,
            "name": name,
            "summary": summary,
            "metrics": metrics,
            "metadata": evaluation_metadata,
        }
        persisted_report_path = write_evaluation_report(
            persisted_report_path, report_payload
        )

    report_artifact = None
    if persisted_report_path:
        report_artifact = create_workflow_artifact(
            db,
            workflow_id=workflow_id,
            artifact_type="evaluation_report",
            role="case_study_evidence",
            path=persisted_report_path,
            metadata={"source": "computed_evaluation_result"},
            commit=False,
        )

    result = WorkflowEvaluationResult(
        workflow_id=workflow_id,
        name=name or "before-after-evaluation",
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        model_version_id=model_version_id,
        report_artifact_id=report_artifact.id if report_artifact else None,
        report_path=persisted_report_path,
        summary=summary,
        metrics_json=encode_json(metrics),
        metadata_json=encode_json(evaluation_metadata),
    )
    db.add(result)
    db.flush()
    if commit:
        db.commit()
        db.refresh(result)
    return result
