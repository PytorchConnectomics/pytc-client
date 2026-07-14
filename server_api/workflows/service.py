import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

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
ALLOWED_COMMAND_STATUSES = {
    "queued",
    "claimed",
    "running",
    "submitted",
    "completed",
    "failed",
    "canceled",
    "retry_pending",
}
DEFAULT_EVENT_SCHEMA_VERSION = 1

INITIAL_PROJECT_ROOT = os.getenv("PYTC_INITIAL_PROJECT_ROOT", "").rstrip("/")


def _initial_project_defaults() -> Dict[str, Any]:
    if not INITIAL_PROJECT_ROOT:
        return {}
    normalized_root = INITIAL_PROJECT_ROOT.lower()
    if "yixiao" in normalized_root or "tapereader" in normalized_root or "xri" in normalized_root:
        image_path = os.getenv(
            "PYTC_INITIAL_IMAGE_PATH",
            os.path.join(INITIAL_PROJECT_ROOT, "data/raw/1/1-xri_raw.tif"),
        )
        label_path = os.getenv(
            "PYTC_INITIAL_LABEL_PATH",
            os.path.join(INITIAL_PROJECT_ROOT, "data/seg/1/1-mask.tif"),
        )
        config_path = os.getenv(
            "PYTC_INITIAL_CONFIG_PATH",
            os.path.join(
                INITIAL_PROJECT_ROOT,
                "configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml",
            ),
        )
        return {
            "title": os.getenv(
                "PYTC_INITIAL_PROJECT_TITLE",
                "Yixiao TapeReader XRI Case Study",
            ),
            "dataset_path": INITIAL_PROJECT_ROOT,
            "image_path": image_path,
            "label_path": label_path,
            "mask_path": os.getenv("PYTC_INITIAL_MASK_PATH", label_path),
            "config_path": config_path,
            "metadata": {
                "created_from": "initial_project_default",
                "project_context": {
                    "imaging_modality": "X-ray / XRI volumetric microscopy",
                    "target_structure": "CytoTape fibres",
                    "task_family": "XRI fibre instance segmentation",
                    "task_goal": "instance segmentation, proofreading, and model retraining",
                    "optimization_priority": "paper-faithful workflow coordination",
                    "mask_status": "6 confirmed ground-truth volumes, 2 draft masks for proofreading, 2 image-only inference targets",
                    "training_policy": "train only on confirmed ground-truth masks",
                    "image_only_strategy": "run inference on image-only volumes later",
                    "voxel_size_nm": [40, 16.3, 16.3],
                    "voxel_size_source": "project_manifest.json",
                },
                "visualization_scales": [40, 16.3, 16.3],
                "visualization_scales_source": "project_manifest.json",
            },
        }
    return {
        "title": os.getenv("PYTC_INITIAL_PROJECT_TITLE", "MitoEM2.0 Progress Demo"),
        "dataset_path": INITIAL_PROJECT_ROOT,
        "image_path": os.getenv(
            "PYTC_INITIAL_IMAGE_PATH",
            os.path.join(INITIAL_PROJECT_ROOT, "data/image"),
        ),
        "label_path": os.getenv(
            "PYTC_INITIAL_LABEL_PATH",
            os.path.join(INITIAL_PROJECT_ROOT, "data/seg"),
        ),
        "mask_path": os.getenv(
            "PYTC_INITIAL_MASK_PATH",
            os.path.join(INITIAL_PROJECT_ROOT, "data/seg"),
        ),
        "config_path": os.getenv(
            "PYTC_INITIAL_CONFIG_PATH",
            os.path.join(
                INITIAL_PROJECT_ROOT,
                "configs/MitoEM2-Pyra-Demo-BC.yaml",
            ),
        ),
        "metadata": {
            "created_from": "initial_project_default",
            "project_context": {
                "imaging_modality": "EM / ssSEM",
                "target_structure": "mitochondria",
                "task_goal": "segmentation",
                "optimization_priority": "accuracy",
                "voxel_size_nm": [30, 8, 8],
                "voxel_size_source": "MitoEM2.0 Dataset006_ME2-Pyra metadata",
            },
            "visualization_scales": [30, 8, 8],
            "visualization_scales_source": "initial_project_default",
        },
    }


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _merge_dicts(base: Optional[Dict[str, Any]], patch: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(base or {})
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _basename(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return os.path.basename(str(value).rstrip("/")) or str(value)


def _path_size(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return os.path.getsize(value)
    except OSError:
        return None


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


def validate_command_status(status: str) -> str:
    if status not in ALLOWED_COMMAND_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "command status must be one of: "
                f"{', '.join(sorted(ALLOWED_COMMAND_STATUSES))}"
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
        "schema_version": getattr(event, "schema_version", DEFAULT_EVENT_SCHEMA_VERSION),
        "idempotency_key": getattr(event, "idempotency_key", None),
        "approval_status": event.approval_status,
        "created_at": event.created_at,
    }


def artifact_to_dict(artifact: WorkflowArtifact) -> Dict[str, Any]:
    return {
        "id": artifact.id,
        "workflow_id": artifact.workflow_id,
        "artifact_type": artifact.artifact_type,
        "role": artifact.role,
        "name": artifact.name,
        "path": artifact.path,
        "uri": artifact.uri,
        "checksum": artifact.checksum,
        "size_bytes": artifact.size_bytes,
        "source_event_id": artifact.source_event_id,
        "metadata_json": artifact.metadata_json,
        "metadata": decode_json(artifact.metadata_json),
        "created_at": artifact.created_at,
        "exists": bool(artifact.path and os.path.exists(artifact.path)),
    }


def volume_state_to_dict(volume_state: WorkflowVolumeState) -> Dict[str, Any]:
    return {
        "id": volume_state.id,
        "workflow_id": volume_state.workflow_id,
        "volume_id": volume_state.volume_id,
        "name": volume_state.name,
        "status": volume_state.status,
        "annotation_state": getattr(volume_state, "annotation_state", None),
        "role_state": getattr(volume_state, "role_state", None),
        "execution_state": getattr(volume_state, "execution_state", None),
        "region_scope_json": getattr(volume_state, "region_scope_json", None),
        "region_scope": decode_json(getattr(volume_state, "region_scope_json", None)),
        "state_schema_version": getattr(volume_state, "state_schema_version", None),
        "status_source": volume_state.status_source,
        "status_confidence": volume_state.status_confidence,
        "project_root": volume_state.project_root,
        "volume_set_id": volume_state.volume_set_id,
        "volume_set_name": volume_state.volume_set_name,
        "image_path": volume_state.image_path,
        "label_path": volume_state.label_path,
        "prediction_path": volume_state.prediction_path,
        "corrected_mask_path": volume_state.corrected_mask_path,
        "eligible_for_training": bool(volume_state.eligible_for_training),
        "eligible_for_inference": bool(volume_state.eligible_for_inference),
        "note": volume_state.note,
        "metadata_json": volume_state.metadata_json,
        "metadata": decode_json(volume_state.metadata_json),
        "source_event_id": volume_state.source_event_id,
        "created_at": volume_state.created_at,
        "updated_at": volume_state.updated_at,
    }


def model_run_to_dict(run: WorkflowModelRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "run_id": getattr(run, "run_id", None),
        "run_type": run.run_type,
        "status": run.status,
        "name": run.name,
        "config_path": run.config_path,
        "log_path": run.log_path,
        "output_path": run.output_path,
        "checkpoint_path": run.checkpoint_path,
        "input_artifact_id": run.input_artifact_id,
        "output_artifact_id": run.output_artifact_id,
        "source_event_id": run.source_event_id,
        "metrics_json": run.metrics_json,
        "metrics": decode_json(run.metrics_json),
        "metadata_json": run.metadata_json,
        "metadata": decode_json(run.metadata_json),
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def model_version_to_dict(version: WorkflowModelVersion) -> Dict[str, Any]:
    return {
        "id": version.id,
        "workflow_id": version.workflow_id,
        "version_label": version.version_label,
        "status": version.status,
        "checkpoint_path": version.checkpoint_path,
        "training_run_id": version.training_run_id,
        "checkpoint_artifact_id": version.checkpoint_artifact_id,
        "correction_set_id": version.correction_set_id,
        "metrics_json": version.metrics_json,
        "metrics": decode_json(version.metrics_json),
        "metadata_json": version.metadata_json,
        "metadata": decode_json(version.metadata_json),
        "created_at": version.created_at,
    }


def correction_set_to_dict(correction_set: WorkflowCorrectionSet) -> Dict[str, Any]:
    return {
        "id": correction_set.id,
        "workflow_id": correction_set.workflow_id,
        "artifact_id": correction_set.artifact_id,
        "corrected_mask_path": correction_set.corrected_mask_path,
        "source_mask_path": correction_set.source_mask_path,
        "proofreading_session_id": correction_set.proofreading_session_id,
        "edit_count": correction_set.edit_count,
        "region_count": correction_set.region_count,
        "source_event_id": correction_set.source_event_id,
        "metadata_json": correction_set.metadata_json,
        "metadata": decode_json(correction_set.metadata_json),
        "created_at": correction_set.created_at,
    }


def evaluation_result_to_dict(
    result: WorkflowEvaluationResult,
) -> Dict[str, Any]:
    return {
        "id": result.id,
        "workflow_id": result.workflow_id,
        "name": result.name,
        "baseline_run_id": result.baseline_run_id,
        "candidate_run_id": result.candidate_run_id,
        "model_version_id": result.model_version_id,
        "report_artifact_id": result.report_artifact_id,
        "report_path": result.report_path,
        "summary": result.summary,
        "metrics_json": result.metrics_json,
        "metrics": decode_json(result.metrics_json),
        "metadata_json": result.metadata_json,
        "metadata": decode_json(result.metadata_json),
        "created_at": result.created_at,
    }


def region_hotspot_to_dict(hotspot: WorkflowRegionHotspot) -> Dict[str, Any]:
    return {
        "id": hotspot.id,
        "workflow_id": hotspot.workflow_id,
        "region_key": hotspot.region_key,
        "score": hotspot.score,
        "severity": hotspot.severity,
        "status": hotspot.status,
        "source": hotspot.source,
        "evidence_json": hotspot.evidence_json,
        "evidence": decode_json(hotspot.evidence_json),
        "created_at": hotspot.created_at,
        "updated_at": hotspot.updated_at,
    }


def agent_step_to_dict(step: WorkflowAgentStep) -> Dict[str, Any]:
    return {
        "id": step.id,
        "plan_id": step.plan_id,
        "step_index": step.step_index,
        "action": step.action,
        "status": step.status,
        "requires_approval": step.requires_approval,
        "summary": step.summary,
        "params_json": step.params_json,
        "params": decode_json(step.params_json),
        "result_json": step.result_json,
        "result": decode_json(step.result_json),
        "created_at": step.created_at,
        "updated_at": step.updated_at,
    }


def agent_plan_to_dict(plan: WorkflowAgentPlan) -> Dict[str, Any]:
    return {
        "id": plan.id,
        "workflow_id": plan.workflow_id,
        "title": plan.title,
        "status": plan.status,
        "risk_level": plan.risk_level,
        "approval_status": plan.approval_status,
        "goal": plan.goal,
        "graph_json": plan.graph_json,
        "graph": decode_json(plan.graph_json),
        "metadata_json": plan.metadata_json,
        "metadata": decode_json(plan.metadata_json),
        "source_event_id": plan.source_event_id,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "steps": [agent_step_to_dict(step) for step in getattr(plan, "steps", [])],
    }


def command_to_dict(command: WorkflowCommand) -> Dict[str, Any]:
    return {
        "id": command.id,
        "workflow_id": command.workflow_id,
        "command_type": command.command_type,
        "status": command.status,
        "idempotency_key": command.idempotency_key,
        "actor": command.actor,
        "source_event_id": command.source_event_id,
        "approval_event_id": command.approval_event_id,
        "input_json": command.input_json,
        "input": decode_json(command.input_json),
        "result_json": command.result_json,
        "result": decode_json(command.result_json),
        "error_json": command.error_json,
        "error": decode_json(command.error_json),
        "attempt_count": command.attempt_count,
        "lease_owner": command.lease_owner,
        "lease_expires_at": command.lease_expires_at,
        "started_at": command.started_at,
        "completed_at": command.completed_at,
        "created_at": command.created_at,
        "updated_at": command.updated_at,
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
        "config_path": workflow.config_path,
        "proofreading_session_id": workflow.proofreading_session_id,
        "corrected_mask_path": workflow.corrected_mask_path,
        "training_output_path": workflow.training_output_path,
        "metadata_json": workflow.metadata_json,
        "metadata": decode_json(workflow.metadata_json),
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
    }


def create_workflow_artifact(
    db: Session,
    *,
    workflow_id: int,
    artifact_type: str,
    role: Optional[str] = None,
    path: Optional[str] = None,
    uri: Optional[str] = None,
    name: Optional[str] = None,
    checksum: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    source_event_id: Optional[int] = None,
    commit: bool = False,
) -> WorkflowArtifact:
    normalized_path = str(path) if path else None
    existing = None
    if normalized_path:
        existing = (
            db.query(WorkflowArtifact)
            .filter(
                WorkflowArtifact.workflow_id == workflow_id,
                WorkflowArtifact.artifact_type == artifact_type,
                WorkflowArtifact.role == role,
                WorkflowArtifact.path == normalized_path,
            )
            .order_by(WorkflowArtifact.id.desc())
            .first()
        )
    if existing:
        changed = False
        if metadata:
            merged = _merge_dicts(decode_json(existing.metadata_json), metadata)
            existing.metadata_json = encode_json(merged)
            changed = True
        if source_event_id and not existing.source_event_id:
            existing.source_event_id = source_event_id
            changed = True
        if changed:
            db.flush()
            if commit:
                db.commit()
                db.refresh(existing)
        return existing

    artifact = WorkflowArtifact(
        workflow_id=workflow_id,
        artifact_type=artifact_type,
        role=role,
        name=name or _basename(normalized_path or uri),
        path=normalized_path,
        uri=uri,
        checksum=checksum,
        size_bytes=_path_size(normalized_path),
        source_event_id=source_event_id,
        metadata_json=encode_json(metadata),
    )
    db.add(artifact)
    db.flush()
    if commit:
        db.commit()
        db.refresh(artifact)
    return artifact


def _correction_region_key(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("region_key", "region_id", "region"):
        value = payload.get(key)
        if isinstance(value, (str, int, float)):
            return str(value)
    instance_id = payload.get("instance_id")
    if isinstance(instance_id, (str, int)):
        return f"instance:{instance_id}"
    z_index = payload.get("z_index")
    if z_index is not None:
        axis = payload.get("axis") or "z"
        return f"{axis}:{z_index}"
    return None


def _correction_stats_from_events(
    db: Session,
    *,
    workflow_id: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    def to_int(value: Any, fallback: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    metadata = metadata or {}
    explicit_edit_count = metadata.get("edit_count")
    explicit_region_count = metadata.get("region_count")
    if explicit_edit_count is not None and explicit_region_count is not None:
        return {
            "edit_count": int(explicit_edit_count or 0),
            "region_count": int(explicit_region_count or 0),
        }

    events = (
        db.query(WorkflowEvent)
        .filter(
            WorkflowEvent.workflow_id == workflow_id,
            WorkflowEvent.event_type.in_(
                [
                    "proofreading.instance_classified",
                    "proofreading.mask_saved",
                    "proofreading.masks_exported",
                ]
            ),
        )
        .all()
    )
    edit_count = 0
    region_keys = set()
    for event in events:
        payload = decode_json(event.payload_json)
        region_key = _correction_region_key(payload)
        if region_key:
            region_keys.add(region_key)
        if event.event_type == "proofreading.mask_saved":
            edit_count += 1

    return {
        "edit_count": to_int(explicit_edit_count, edit_count)
        if explicit_edit_count is not None
        else edit_count,
        "region_count": to_int(explicit_region_count, len(region_keys))
        if explicit_region_count is not None
        else len(region_keys),
    }


def create_or_update_correction_set(
    db: Session,
    *,
    workflow: WorkflowSession,
    corrected_mask_path: str,
    source_event_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> WorkflowCorrectionSet:
    correction_stats = _correction_stats_from_events(
        db,
        workflow_id=workflow.id,
        metadata=metadata,
    )
    artifact = create_workflow_artifact(
        db,
        workflow_id=workflow.id,
        artifact_type="correction_set",
        role="corrected_mask",
        path=corrected_mask_path,
        metadata=metadata,
        source_event_id=source_event_id,
        commit=False,
    )
    existing = (
        db.query(WorkflowCorrectionSet)
        .filter(
            WorkflowCorrectionSet.workflow_id == workflow.id,
            WorkflowCorrectionSet.corrected_mask_path == corrected_mask_path,
        )
        .order_by(WorkflowCorrectionSet.id.desc())
        .first()
    )
    if existing:
        existing.artifact_id = artifact.id
        existing.source_mask_path = workflow.mask_path
        existing.proofreading_session_id = workflow.proofreading_session_id
        existing.source_event_id = existing.source_event_id or source_event_id
        existing.edit_count = correction_stats["edit_count"]
        existing.region_count = correction_stats["region_count"]
        existing.metadata_json = encode_json(
            _merge_dicts(decode_json(existing.metadata_json), metadata)
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(existing)
        return existing

    correction_set = WorkflowCorrectionSet(
        workflow_id=workflow.id,
        artifact_id=artifact.id,
        corrected_mask_path=corrected_mask_path,
        source_mask_path=workflow.mask_path,
        proofreading_session_id=workflow.proofreading_session_id,
        edit_count=correction_stats["edit_count"],
        region_count=correction_stats["region_count"],
        source_event_id=source_event_id,
        metadata_json=encode_json(metadata),
    )
    db.add(correction_set)
    db.flush()
    if commit:
        db.commit()
        db.refresh(correction_set)
    return correction_set


def _latest_incomplete_run(
    db: Session, *, workflow_id: int, run_type: str
) -> Optional[WorkflowModelRun]:
    return (
        db.query(WorkflowModelRun)
        .filter(
            WorkflowModelRun.workflow_id == workflow_id,
            WorkflowModelRun.run_type == run_type,
            WorkflowModelRun.status.in_(["pending", "running"]),
        )
        .order_by(WorkflowModelRun.created_at.desc(), WorkflowModelRun.id.desc())
        .first()
    )


def _payload_run_id(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("run_id", "runId", "job_id", "jobId", "execution_id", "executionId"):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return None


def _find_model_run_for_event(
    db: Session,
    *,
    workflow_id: int,
    run_type: str,
    run_id: Optional[str],
    output_path: Optional[str],
    fallback_latest: bool = True,
) -> Optional[WorkflowModelRun]:
    if run_id:
        run = (
            db.query(WorkflowModelRun)
            .filter(
                WorkflowModelRun.workflow_id == workflow_id,
                WorkflowModelRun.run_id == run_id,
            )
            .first()
        )
        if run:
            return run
    if output_path:
        run = (
            db.query(WorkflowModelRun)
            .filter(
                WorkflowModelRun.workflow_id == workflow_id,
                WorkflowModelRun.run_type == run_type,
                WorkflowModelRun.status.in_(["pending", "running"]),
                WorkflowModelRun.output_path == output_path,
            )
            .order_by(WorkflowModelRun.created_at.desc(), WorkflowModelRun.id.desc())
            .first()
        )
        if run:
            return run
    if not fallback_latest:
        return None
    return _latest_incomplete_run(db, workflow_id=workflow_id, run_type=run_type)


def create_or_update_model_run_from_event(
    db: Session,
    *,
    workflow: WorkflowSession,
    event: WorkflowEvent,
    payload: Dict[str, Any],
) -> Optional[WorkflowModelRun]:
    event_type = event.event_type
    run_type = None
    status = None
    if event_type == "training.started":
        run_type, status = "training", "running"
    elif event_type == "training.completed":
        run_type, status = "training", "completed"
    elif event_type == "training.failed":
        run_type, status = "training", "failed"
    elif event_type == "inference.started":
        run_type, status = "inference", "running"
    elif event_type == "inference.completed":
        run_type, status = "inference", "completed"
    elif event_type == "inference.failed":
        run_type, status = "inference", "failed"
    if not run_type:
        return None

    output_path = (
        payload.get("outputPath")
        or payload.get("output_path")
        or payload.get("training_output_path")
        or payload.get("inference_output_path")
    )
    checkpoint_path = (
        payload.get("checkpointPath")
        or payload.get("checkpoint_path")
        or payload.get("checkpoint")
    )
    config_path = payload.get("configOriginPath") or payload.get("config_path")
    log_path = payload.get("logPath") or payload.get("log_path")
    now = _now()
    run_id = _payload_run_id(payload)

    run = (
        _find_model_run_for_event(
            db,
            workflow_id=workflow.id,
            run_type=run_type,
            run_id=run_id,
            output_path=output_path,
            fallback_latest=not bool(run_id),
        )
        if status in {"completed", "failed"}
        else None
    )
    if status == "running" and run_id:
        run = _find_model_run_for_event(
            db,
            workflow_id=workflow.id,
            run_type=run_type,
            run_id=run_id,
            output_path=output_path,
            fallback_latest=False,
        )
    if run is None:
        run_id = run_id or f"{run_type}-{event.id}"
        run = WorkflowModelRun(
            workflow_id=workflow.id,
            run_id=run_id,
            run_type=run_type,
            status=status,
            source_event_id=event.id,
            started_at=now if status == "running" else None,
        )
        db.add(run)
    elif run_id and not getattr(run, "run_id", None):
        run.run_id = run_id
    run_id = getattr(run, "run_id", None) or run_id
    if run_id and payload.get("run_id") != run_id:
        payload["run_id"] = run_id
        event.payload_json = encode_json(payload)

    run.status = status
    run.config_path = config_path or run.config_path
    run.log_path = log_path or run.log_path
    run.output_path = output_path or run.output_path
    run.checkpoint_path = checkpoint_path or run.checkpoint_path
    run.source_event_id = run.source_event_id or event.id
    run.metadata_json = encode_json(
        _merge_dicts(
            decode_json(run.metadata_json),
            {
                "last_event_type": event_type,
                "last_event_id": event.id,
                "run_id": run_id,
            },
        )
    )
    if status == "running" and not run.started_at:
        run.started_at = now
    if status in {"completed", "failed"}:
        run.completed_at = now

    if output_path and run_type == "inference":
        run.output_artifact = create_workflow_artifact(
            db,
            workflow_id=workflow.id,
            artifact_type="inference_output",
            role="prediction",
            path=output_path,
            source_event_id=event.id,
            metadata={"run_type": run_type, "status": status},
            commit=False,
        )
    elif output_path and run_type == "training":
        run.output_artifact = create_workflow_artifact(
            db,
            workflow_id=workflow.id,
            artifact_type="training_output",
            role="run_directory",
            path=output_path,
            source_event_id=event.id,
            metadata={"run_type": run_type, "status": status},
            commit=False,
        )

    db.flush()

    if run_type == "training" and status == "completed" and checkpoint_path:
        checkpoint_artifact = create_workflow_artifact(
            db,
            workflow_id=workflow.id,
            artifact_type="model_checkpoint",
            role="candidate_checkpoint",
            path=checkpoint_path,
            source_event_id=event.id,
            metadata={"model_run_id": run.id},
            commit=False,
        )
        label = payload.get("checkpointName") or _basename(checkpoint_path)
        version = WorkflowModelVersion(
            workflow_id=workflow.id,
            version_label=label or f"model-run-{run.id}",
            status="candidate",
            checkpoint_path=checkpoint_path,
            training_run_id=run.id,
            checkpoint_artifact_id=checkpoint_artifact.id,
            metrics_json=encode_json(payload.get("metrics") or {}),
            metadata_json=encode_json({"source_event_id": event.id}),
        )
        db.add(version)
        db.flush()

    return run


def _artifact_specs_for_event(
    event_type: str, payload: Dict[str, Any]
) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []

    def add_non_copy_path(path_key: str, artifact_type: str, role: str) -> None:
        path = payload.get(path_key)
        if path:
            specs.append(
                {
                    "artifact_type": artifact_type,
                    "role": role,
                    "path": str(path),
                    "metadata": {
                        "source_payload_key": path_key,
                        "allow_copy_in_bundle": False,
                        "copy_reason": "external_reference_path",
                    },
                }
            )

    def add(path_key: str, artifact_type: str, role: str) -> None:
        path = payload.get(path_key)
        if path:
            specs.append(
                {
                    "artifact_type": artifact_type,
                    "role": role,
                    "path": str(path),
                    "metadata": {"source_payload_key": path_key},
                }
            )

    if event_type in {"dataset.loaded", "viewer.created"}:
        add("dataset_path", "dataset", "source_dataset")
        add("image_path", "image_volume", "image")
        add("label_path", "label_volume", "label")
        add("mask_path", "mask_volume", "mask")
        add("ground_truth_path", "label_volume", "ground_truth")
        add("source_ground_truth_path", "label_volume", "ground_truth")
        add_non_copy_path("withheld_ground_truth", "label_volume", "withheld_ground_truth")
        add_non_copy_path("source_ground_truth", "label_volume", "ground_truth")
        add_non_copy_path(
            "withheld_ground_truth_path", "label_volume", "withheld_ground_truth"
        )
    if event_type in {"proofreading.masks_exported", "retraining.staged"}:
        add("written_path", "correction_set", "corrected_mask")
        add("output_path", "correction_set", "corrected_mask")
        add("corrected_mask_path", "correction_set", "corrected_mask")
        add("backup_path", "mask_volume", "backup_mask")
    if event_type.startswith("training."):
        add("outputPath", "training_output", "run_directory")
        add("output_path", "training_output", "run_directory")
        add("checkpointPath", "model_checkpoint", "candidate_checkpoint")
        add("checkpoint_path", "model_checkpoint", "candidate_checkpoint")
    if event_type.startswith("inference."):
        add("outputPath", "inference_output", "prediction")
        add("output_path", "inference_output", "prediction")
        add("checkpointPath", "model_checkpoint", "input_checkpoint")
        add("checkpoint_path", "model_checkpoint", "input_checkpoint")
    return specs


def materialize_event_artifacts(
    db: Session,
    *,
    workflow: WorkflowSession,
    event: WorkflowEvent,
    payload: Dict[str, Any],
) -> None:
    for spec in _artifact_specs_for_event(event.event_type, payload):
        create_workflow_artifact(
            db,
            workflow_id=workflow.id,
            source_event_id=event.id,
            commit=False,
            **spec,
        )

    corrected_mask_path = (
        payload.get("corrected_mask_path")
        or payload.get("written_path")
        or payload.get("output_path")
    )
    if (
        event.event_type in {"proofreading.masks_exported", "retraining.staged"}
        and corrected_mask_path
    ):
        create_or_update_correction_set(
            db,
            workflow=workflow,
            corrected_mask_path=str(corrected_mask_path),
            source_event_id=event.id,
            metadata={"source_event_type": event.event_type},
            commit=False,
        )

    create_or_update_model_run_from_event(
        db, workflow=workflow, event=event, payload=payload
    )


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

    return create_workflow_session(db, user_id=user_id)


def create_workflow_session(
    db: Session,
    *,
    user_id: int,
    title: str = "Segmentation Workflow",
    metadata: Optional[Dict[str, Any]] = None,
) -> WorkflowSession:
    initial_defaults = _initial_project_defaults()
    initial_metadata = {
        **initial_defaults.get("metadata", {}),
        **(metadata or {}),
    }
    workflow_title = title or "Segmentation Workflow"
    if initial_defaults and workflow_title == "Segmentation Workflow":
        workflow_title = initial_defaults.get("title") or workflow_title

    workflow = WorkflowSession(
        user_id=user_id,
        title=workflow_title,
        stage="setup",
        dataset_path=initial_defaults.get("dataset_path"),
        image_path=initial_defaults.get("image_path"),
        label_path=initial_defaults.get("label_path"),
        mask_path=initial_defaults.get("mask_path"),
        config_path=initial_defaults.get("config_path"),
        metadata_json=encode_json(initial_metadata),
    )
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
    "config_path",
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
            patch = value if isinstance(value, dict) else {}
            workflow.metadata_json = encode_json(
                _merge_dicts(decode_json(workflow.metadata_json), patch)
            )
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


def create_workflow_command(
    db: Session,
    *,
    workflow_id: int,
    command_type: str,
    idempotency_key: str,
    actor: str = "agent",
    source_event_id: Optional[int] = None,
    approval_event_id: Optional[int] = None,
    input_payload: Optional[Dict[str, Any]] = None,
    status: str = "queued",
    commit: bool = False,
) -> WorkflowCommand:
    actor = validate_actor(actor)
    status = validate_command_status(status)
    existing = (
        db.query(WorkflowCommand)
        .filter(
            WorkflowCommand.workflow_id == workflow_id,
            WorkflowCommand.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing:
        return existing
    command = WorkflowCommand(
        workflow_id=workflow_id,
        command_type=command_type,
        status=status,
        idempotency_key=idempotency_key,
        actor=actor,
        source_event_id=source_event_id,
        approval_event_id=approval_event_id,
        input_json=encode_json(input_payload or {}),
    )
    db.add(command)
    db.flush()
    if commit:
        db.commit()
        db.refresh(command)
    return command


def mark_workflow_command_running(
    db: Session,
    command: WorkflowCommand,
    *,
    lease_owner: str = "server_api",
    input_payload: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> WorkflowCommand:
    if command.status not in {"queued", "claimed", "retry_pending", "failed"}:
        raise HTTPException(
            status_code=409,
            detail=f"Command cannot be run from status: {command.status}",
        )
    now = _now()
    command.status = "running"
    command.attempt_count = int(command.attempt_count or 0) + 1
    command.lease_owner = lease_owner
    command.started_at = now
    command.completed_at = None
    command.error_json = None
    if input_payload is not None:
        command.input_json = encode_json(input_payload)
    db.flush()
    if commit:
        db.commit()
        db.refresh(command)
    return command


def complete_workflow_command(
    db: Session,
    command: WorkflowCommand,
    *,
    result_payload: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> WorkflowCommand:
    command.status = "completed"
    command.result_json = encode_json(result_payload or {})
    command.error_json = None
    command.lease_owner = None
    command.lease_expires_at = None
    command.completed_at = _now()
    db.flush()
    if commit:
        db.commit()
        db.refresh(command)
    return command


def submit_workflow_command(
    db: Session,
    command: WorkflowCommand,
    *,
    result_payload: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> WorkflowCommand:
    command.status = "submitted"
    command.result_json = encode_json(result_payload or {})
    command.error_json = None
    command.lease_owner = None
    command.lease_expires_at = None
    command.completed_at = None
    db.flush()
    if commit:
        db.commit()
        db.refresh(command)
    return command


def fail_workflow_command(
    db: Session,
    command: WorkflowCommand,
    *,
    error_payload: Optional[Dict[str, Any]] = None,
    retryable: bool = False,
    commit: bool = False,
) -> WorkflowCommand:
    command.status = "retry_pending" if retryable else "failed"
    command.error_json = encode_json(error_payload or {})
    command.lease_owner = None
    command.lease_expires_at = None
    command.completed_at = _now()
    db.flush()
    if commit:
        db.commit()
        db.refresh(command)
    return command


def append_workflow_event(
    db: Session,
    *,
    workflow_id: Optional[int],
    actor: str,
    event_type: str,
    summary: str,
    stage: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    schema_version: int = DEFAULT_EVENT_SCHEMA_VERSION,
    idempotency_key: Optional[str] = None,
    approval_status: str = "not_required",
    commit: bool = True,
) -> Optional[WorkflowEvent]:
    if not workflow_id:
        return None
    actor = validate_actor(actor)
    approval_status = validate_approval_status(approval_status)
    stage = validate_stage(stage) if stage else stage
    if idempotency_key:
        existing = (
            db.query(WorkflowEvent)
            .filter(
                WorkflowEvent.workflow_id == workflow_id,
                WorkflowEvent.idempotency_key == idempotency_key,
            )
            .order_by(WorkflowEvent.id.desc())
            .first()
        )
        if existing:
            return existing
    event = WorkflowEvent(
        workflow_id=workflow_id,
        actor=actor,
        event_type=event_type,
        stage=stage,
        summary=summary,
        payload_json=encode_json(payload),
        schema_version=schema_version or DEFAULT_EVENT_SCHEMA_VERSION,
        idempotency_key=idempotency_key,
        approval_status=approval_status,
    )
    db.add(event)
    db.flush()
    workflow = (
        db.query(WorkflowSession).filter(WorkflowSession.id == workflow_id).first()
    )
    if workflow:
        materialize_event_artifacts(
            db,
            workflow=workflow,
            event=event,
            payload=payload or {},
        )
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
    schema_version: int = DEFAULT_EVENT_SCHEMA_VERSION,
    idempotency_key: Optional[str] = None,
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
        schema_version=schema_version,
        idempotency_key=idempotency_key,
        commit=True,
    )
