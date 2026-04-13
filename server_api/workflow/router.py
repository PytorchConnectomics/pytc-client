from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from .models import WorkflowExportBundle
from .service import build_export_bundle

router = APIRouter()


# Placeholder repository interface. Tests patch this for deterministic fixtures.
def get_workflow_export_record(workflow_id: int) -> Optional[Dict[str, Any]]:
    return None


@router.post("/api/workflows/{workflow_id}/export-bundle", response_model=WorkflowExportBundle)
def export_workflow_bundle(workflow_id: int):
    record = get_workflow_export_record(workflow_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    bundle = build_export_bundle(workflow_id, record)
    return bundle
