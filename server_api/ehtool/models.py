"""
Pydantic models for EHTool API endpoints
"""

from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
import os


# Request Models
class DetectionLoadRequest(BaseModel):
    """Request to load dataset for error detection"""

    dataset_path: str
    mask_path: Optional[str] = None
    project_name: str = "Untitled Project"

    @field_validator("dataset_path", "mask_path")
    @classmethod
    def validate_path(cls, v):
        """Validate path to prevent directory traversal"""
        if v is None:
            return v

        # Normalize path
        normalized = os.path.normpath(v)

        # Check for directory traversal attempts
        if ".." in normalized:
            raise ValueError(
                "Path cannot contain '..' (directory traversal not allowed)"
            )

        # Ensure path is within uploads directory (or absolute path for testing)
        # Allow absolute paths for now, but in production should restrict to uploads/
        if not os.path.isabs(normalized):
            # Relative paths should be within uploads
            if not normalized.startswith("uploads"):
                raise ValueError("Relative paths must be within 'uploads/' directory")

        return normalized


class LayerClassifyRequest(BaseModel):
    """Request to classify layer(s)"""

    session_id: int
    layer_ids: List[int]
    classification: str  # 'correct', 'incorrect', 'unsure', 'error'


class MaskSaveRequest(BaseModel):
    """Request to save an updated mask for a layer"""

    session_id: int
    layer_index: int
    mask_base64: str


class InstanceClassifyRequest(BaseModel):
    """Request to classify instance(s)"""

    session_id: int
    instance_ids: List[int]
    classification: str  # 'correct', 'incorrect', 'unsure', 'error'


# Response Models
class DetectionLoadResponse(BaseModel):
    """Response after loading detection dataset"""

    session_id: int
    total_layers: int
    project_name: str


class LayerInfo(BaseModel):
    """Information about a single layer"""

    id: int
    layer_index: int
    layer_name: str
    classification: str
    image_base64: Optional[str] = None
    mask_base64: Optional[str] = None


class LayersPageResponse(BaseModel):
    """Paginated response for layers"""

    layers: List[LayerInfo]
    total: int
    page: int
    page_size: int
    total_pages: int


class DetectionStatsResponse(BaseModel):
    """Statistics for detection workflow"""

    correct: int
    incorrect: int
    unsure: int
    error: int
    total: int
    reviewed: int
    progress_percent: float


class ClassifyResponse(BaseModel):
    """Response after classifying layers"""

    updated_count: int
    message: str


class InstanceInfo(BaseModel):
    """Information about a single instance"""

    id: int
    voxel_count: int
    com_z: int
    com_y: int
    com_x: int
    classification: str


class InstancesResponse(BaseModel):
    """Response containing instance list and mode info"""

    instances: List[InstanceInfo]
    instance_mode: str
    total_instances: int
    total_layers: int


class InstanceViewResponse(BaseModel):
    """Response for a single instance view slice"""

    instance_id: int
    axis: str
    z_index: int
    total_layers: int
    image_base64: str
    mask_raw_base64: Optional[str] = None
    mask_all_base64: Optional[str] = None
    mask_active_base64: Optional[str] = None
