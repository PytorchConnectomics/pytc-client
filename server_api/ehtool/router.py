"""
FastAPI router for EHTool detection workflow
Handles error detection endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import math
import logging

logger = logging.getLogger(__name__)

from auth.database import get_db
from auth.router import get_current_user
from auth.models import User

from .models import (
    DetectionLoadRequest,
    DetectionLoadResponse,
    LayerClassifyRequest,
    ClassifyResponse,
    LayersPageResponse,
    LayerInfo,
    DetectionStatsResponse
)
from .db_models import EHToolSession, EHToolLayer
from .data_manager import DataManager

router = APIRouter()

# DIAGNOSTIC: This should print when the module is loaded
print("=" * 80)
print("EHTOOL ROUTER MODULE LOADED - VERSION: DEBUG v2")
print("=" * 80)

# In-memory cache for DataManagers (session_id -> DataManager)
# In production, consider using Redis or similar
_data_managers = {}


def get_data_manager(session_id: int, db: Session) -> DataManager:
    """Get or create DataManager for a session"""
    if session_id not in _data_managers:
        # Try to reload from database
        db_session = db.query(EHToolSession).filter(EHToolSession.id == session_id).first()
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        # Recreate DataManager from stored paths
        data_manager = DataManager()
        try:
            data_manager.load_dataset(
                dataset_path=db_session.dataset_path,
                mask_path=db_session.mask_path
            )
            # Cache it
            _data_managers[session_id] = data_manager
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reload session data: {str(e)}"
            )
    
    return _data_managers[session_id]


@router.post("/detection/load", response_model=DetectionLoadResponse)
async def load_detection_dataset(
    request: DetectionLoadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Load a dataset for error detection workflow
    
    Creates a new session and initializes layers
    """
    try:
        # Create DataManager and load dataset
        data_manager = DataManager()
        dataset_info = data_manager.load_dataset(
            dataset_path=request.dataset_path,
            mask_path=request.mask_path
        )
        
        # Create session in database
        db_session = EHToolSession(
            user_id=current_user.id,
            project_name=request.project_name,
            workflow_type="detection",
            dataset_path=request.dataset_path,
            mask_path=request.mask_path,
            total_layers=dataset_info["total_layers"]
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        # Create layer records
        for i in range(dataset_info["total_layers"]):
            layer_name = data_manager.get_layer_name(i)
            db_layer = EHToolLayer(
                session_id=db_session.id,
                layer_index=i,
                layer_name=layer_name,
                classification="error"  # Default to 'error' (unreviewed)
            )
            db.add(db_layer)
        
        db.commit()
        
        # Cache DataManager
        _data_managers[db_session.id] = data_manager
        
        return DetectionLoadResponse(
            session_id=db_session.id,
            total_layers=dataset_info["total_layers"],
            project_name=request.project_name
        )
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dataset: {str(e)}"
        )


@router.get("/detection/layers", response_model=LayersPageResponse)
async def get_detection_layers(
    session_id: int,
    page: int = 1,
    page_size: int = 12,
    include_images: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get paginated layers for detection workflow
    
    Args:
        session_id: Session ID
        page: Page number (1-indexed)
        page_size: Number of layers per page (default 12)
        include_images: Whether to include base64-encoded images
    """
    # Verify session belongs to user
    db_session = db.query(EHToolSession).filter(
        EHToolSession.id == session_id,
        EHToolSession.user_id == current_user.id
    ).first()
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Get DataManager
    data_manager = get_data_manager(session_id, db)
    
    # Calculate pagination
    total_layers = db_session.total_layers
    total_pages = math.ceil(total_layers / page_size)
    
    if page < 1 or page > total_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid page number. Must be between 1 and {total_pages}"
        )
    
    # Get layers for this page
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_layers)
    
    # Force refresh of session to ensure we see latest updates
    db.expire_all()
    
    # Query database for layer info
    db_layers = db.query(EHToolLayer).filter(
        EHToolLayer.session_id == session_id,
        EHToolLayer.layer_index >= start_idx,
        EHToolLayer.layer_index < end_idx
    ).order_by(EHToolLayer.layer_index).all()
    
    # Build response
    layers = []
    for db_layer in db_layers:
        # DIAGNOSTIC: Log incorrect layers to verify what we see
        if db_layer.classification == 'incorrect':
            print(f"[GET_LAYERS] Found incorrect layer: id={db_layer.id}, index={db_layer.layer_index}")
            
        layer_info = LayerInfo(
            id=db_layer.id,
            layer_index=db_layer.layer_index,
            layer_name=db_layer.layer_name,
            classification=db_layer.classification
        )
        
        # Include images if requested
        if include_images:
            try:
                image_base64, mask_base64 = data_manager.get_layer_base64(
                    db_layer.layer_index,
                    enhance=True
                )
                layer_info.image_base64 = image_base64
                layer_info.mask_base64 = mask_base64
                if image_base64:
                    print(f"[GET_LAYERS] Loaded image for layer {db_layer.layer_index}, size: {len(image_base64)}")
                else:
                    print(f"[GET_LAYERS] Image is None for layer {db_layer.layer_index}")
            except Exception as e:
                print(f"[GET_LAYERS] Warning: Failed to load image for layer {db_layer.layer_index}: {e}")
        
        layers.append(layer_info)
    
    return LayersPageResponse(
        layers=layers,
        total=total_layers,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.post("/detection/classify", response_model=ClassifyResponse)
async def classify_layers(
    request: LayerClassifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Classify one or more layers
    
    Args:
        request: Classification request with layer IDs and classification
    """
    # Verify session belongs to user
    db_session = db.query(EHToolSession).filter(
        EHToolSession.id == request.session_id,
        EHToolSession.user_id == current_user.id
    ).first()
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Validate classification
    valid_classifications = ['correct', 'incorrect', 'unsure', 'error']
    if request.classification not in valid_classifications:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid classification. Must be one of: {', '.join(valid_classifications)}"
        )
    
    print(f"[CLASSIFY] Session: {request.session_id}, Layer IDs: {request.layer_ids}, Classification: {request.classification}")
    
    # Update layers
    updated_count = 0
    for layer_id in request.layer_ids:
        db_layer = db.query(EHToolLayer).filter(
            EHToolLayer.id == layer_id,
            EHToolLayer.session_id == request.session_id
        ).first()
        
        if db_layer:
            print(f"[CLASSIFY] Updating layer {layer_id}: {db_layer.classification} -> {request.classification}")
            db_layer.classification = request.classification
            updated_count += 1
        else:
            print(f"[CLASSIFY] Layer {layer_id} not found in session {request.session_id}")
    
    # Flush changes to database
    db.flush()
    print(f"[CLASSIFY] Flushed {updated_count} layer updates to database")
    
    # Commit the transaction
    db.commit()
    print(f"[CLASSIFY] Committed {updated_count} layers to database")
    
    # Verify the changes were persisted
    for layer_id in request.layer_ids:
        verify_layer = db.query(EHToolLayer).filter(EHToolLayer.id == layer_id).first()
        if verify_layer:
            print(f"[CLASSIFY] VERIFY: Layer {layer_id} classification is now: {verify_layer.classification}")
    
    return ClassifyResponse(
        updated_count=updated_count,
        message=f"[DEBUG v2] Successfully classified {updated_count} layer(s) as '{request.classification}'"
    )


@router.get("/detection/stats", response_model=DetectionStatsResponse)
async def get_detection_stats(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics for detection workflow
    
    Returns counts for each classification type
    """
    # Verify session belongs to user
    db_session = db.query(EHToolSession).filter(
        EHToolSession.id == session_id,
        EHToolSession.user_id == current_user.id
    ).first()
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Count classifications
    layers = db.query(EHToolLayer).filter(
        EHToolLayer.session_id == session_id
    ).all()
    
    correct = sum(1 for l in layers if l.classification == 'correct')
    incorrect = sum(1 for l in layers if l.classification == 'incorrect')
    unsure = sum(1 for l in layers if l.classification == 'unsure')
    error = sum(1 for l in layers if l.classification == 'error')
    total = len(layers)
    reviewed = total - error
    progress_percent = (reviewed / total * 100) if total > 0 else 0
    
    return DetectionStatsResponse(
        correct=correct,
        incorrect=incorrect,
        unsure=unsure,
        error=error,
        total=total,
        reviewed=reviewed,
        progress_percent=round(progress_percent, 2)
    )


@router.delete("/detection/session/{session_id}")
async def delete_detection_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a detection session and all its layers
    """
    # Verify session belongs to user
    db_session = db.query(EHToolSession).filter(
        EHToolSession.id == session_id,
        EHToolSession.user_id == current_user.id
    ).first()
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Remove from cache
    if session_id in _data_managers:
        del _data_managers[session_id]
    
    # Delete from database (cascade will delete layers)
    db.delete(db_session)
    db.commit()
    
    return {"message": f"Session {session_id} deleted successfully"}
