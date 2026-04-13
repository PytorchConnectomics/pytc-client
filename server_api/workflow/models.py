from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class WorkflowArtifactEntry(BaseModel):
    path: str
    exists: bool


class WorkflowEvent(BaseModel):
    id: str
    type: str
    timestamp: datetime
    payload: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExportBundle(BaseModel):
    schema_version: str
    exported_at: datetime
    workflow_id: int
    session_snapshot: Dict[str, Any]
    events: List[WorkflowEvent]
    artifact_paths: List[WorkflowArtifactEntry]
