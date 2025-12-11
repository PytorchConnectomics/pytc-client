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
    
    @field_validator('dataset_path', 'mask_path')
    @classmethod
    def validate_path(cls, v):
        """Validate path to prevent directory traversal"""
        if v is None:
            return v
        
        # Normalize path
        normalized = os.path.normpath(v)
        
        # Check for directory traversal attempts
        if '..' in normalized:
            raise ValueError("Path cannot contain '..' (directory traversal not allowed)")
        
        # Ensure path is within uploads directory (or absolute path for testing)
        # Allow absolute paths for now, but in production should restrict to uploads/
        if not os.path.isabs(normalized):
            # Relative paths should be within uploads
            if not normalized.startswith('uploads'):
                raise ValueError("Relative paths must be within 'uploads/' directory")
        
        return normalized


class LayerClassifyRequest(BaseModel):
    """Request to classify layer(s)"""
    session_id: int
    layer_ids: List[int]
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
