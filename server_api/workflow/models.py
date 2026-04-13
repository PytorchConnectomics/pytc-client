from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class WorkflowEvent(BaseModel):
    event_type: str = Field(alias="type")
    created_at: datetime
    action: Optional[str] = None
    from_stage: Optional[str] = None
    to_stage: Optional[str] = None


class WorkflowMetricsResponse(BaseModel):
    workflow_id: str
    total_events: int
    event_counts_by_type: Dict[str, int]
    approvals_count: int
    rejections_count: int
    approvals_rate: float
    rejections_rate: float
    stage_transition_counts: Dict[str, int]
    first_event_at: Optional[datetime]
    last_event_at: Optional[datetime]
