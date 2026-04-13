from datetime import datetime, timezone
import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server_api.auth.database import get_db
from server_api.auth.models import User
from server_api.auth.router import get_current_user
from server_api.ehtool.db_models import EHToolLayer, EHToolSession

from .models import (
    ArtifactReference,
    WorkflowEvent,
    WorkflowExportBundle,
    WorkflowSessionSnapshot,
)

router = APIRouter(prefix="/api/workflows", tags=["workflow"])

SCHEMA_VERSION = "1.0"


def _to_iso(ts):
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()


@router.post("/{workflow_id}/export-bundle", response_model=WorkflowExportBundle)
async def export_workflow_bundle(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = (
        db.query(EHToolSession)
        .filter(EHToolSession.id == workflow_id, EHToolSession.user_id == current_user.id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    layers = (
        db.query(EHToolLayer)
        .filter(EHToolLayer.session_id == workflow.id)
        .order_by(EHToolLayer.layer_index.asc(), EHToolLayer.id.asc())
        .all()
    )

    events: List[WorkflowEvent] = [
        WorkflowEvent(
            event_type="workflow.created",
            event_time=_to_iso(workflow.created_at),
            payload={
                "workflow_id": workflow.id,
                "project_name": workflow.project_name,
                "workflow_type": workflow.workflow_type,
            },
        )
    ]

    for layer in layers:
        events.append(
            WorkflowEvent(
                event_type="layer.indexed",
                event_time=_to_iso(layer.created_at),
                payload={
                    "layer_id": layer.id,
                    "layer_index": layer.layer_index,
                    "layer_name": layer.layer_name,
                    "classification": layer.classification,
                },
            )
        )
        if layer.updated_at is not None:
            events.append(
                WorkflowEvent(
                    event_type="layer.updated",
                    event_time=_to_iso(layer.updated_at),
                    payload={
                        "layer_id": layer.id,
                        "classification": layer.classification,
                    },
                )
            )

    events.sort(
        key=lambda item: (
            item.event_time is None,
            item.event_time or "",
            item.event_type,
            item.payload.get("layer_id", -1),
            item.payload.get("layer_index", -1),
        )
    )

    artifact_paths = []
    for path in [workflow.dataset_path, workflow.mask_path]:
        if path:
            artifact_paths.append(path)
    for layer in layers:
        for path in [layer.image_path, layer.mask_path]:
            if path:
                artifact_paths.append(path)

    deduped_paths = sorted(set(artifact_paths))
    artifacts = [
        ArtifactReference(path=path, exists=os.path.exists(path)) for path in deduped_paths
    ]

    return WorkflowExportBundle(
        schema_version=SCHEMA_VERSION,
        exported_at=datetime.now(timezone.utc).isoformat(),
        workflow_session=WorkflowSessionSnapshot(
            id=workflow.id,
            user_id=workflow.user_id,
            project_name=workflow.project_name,
            workflow_type=workflow.workflow_type,
            dataset_path=workflow.dataset_path,
            mask_path=workflow.mask_path,
            total_layers=workflow.total_layers,
            created_at=_to_iso(workflow.created_at),
            updated_at=_to_iso(workflow.updated_at),
        ),
        events=events,
        artifacts=artifacts,
    )
