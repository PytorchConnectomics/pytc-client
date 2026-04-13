from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WorkflowEvent(BaseModel):
    event_type: str
    event_time: Optional[str] = None
    payload: Dict[str, Any]


class ArtifactReference(BaseModel):
    path: str
    exists: bool


class WorkflowSessionSnapshot(BaseModel):
    id: int
    user_id: int
    project_name: str
    workflow_type: str
    dataset_path: str
    mask_path: Optional[str] = None
    total_layers: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkflowExportBundle(BaseModel):
    schema_version: str
    exported_at: str
    workflow_session: WorkflowSessionSnapshot
    events: List[WorkflowEvent]
    artifacts: List[ArtifactReference]
