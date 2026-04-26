"""
FastAPI router for EHTool detection workflow
Handles error detection endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional
import math
import logging
import time

logger = logging.getLogger(__name__)

from server_api.auth.database import get_db
from server_api.auth.router import get_current_user
from server_api.auth.models import User

from .models import (
    DetectionLoadRequest,
    DetectionLoadResponse,
    LayerClassifyRequest,
    ClassifyResponse,
    LayersPageResponse,
    LayerInfo,
    DetectionStatsResponse,
    MaskSaveRequest,
    InstanceMaskSaveRequest,
    InstanceClassifyRequest,
    InstancesResponse,
    InstanceInfo,
    InstanceViewResponse,
    PersistenceStatusResponse,
    ExportMasksRequest,
    ExportMasksResponse,
)
from .db_models import EHToolSession, EHToolLayer
from .data_manager import DataManager
from .utils import array_to_base64, glasbey_color
from server_api.workflows.service import (
    append_event_for_workflow_if_present,
    append_workflow_event,
    get_user_workflow_or_404,
    update_workflow_fields,
)
from app_event_logger import append_app_event

router = APIRouter()

# DIAGNOSTIC: This should print when the module is loaded
print("=" * 80)
print("EHTOOL ROUTER MODULE LOADED - VERSION: DEBUG v2")
print("=" * 80)

# In-memory cache for DataManagers (session_id -> DataManager)
_data_managers = {}


def _append_ehtool_event(event: str, level: str = "INFO", **fields):
    try:
        append_app_event(
            component="ehtool.router",
            event=event,
            level=level,
            **fields,
        )
    except Exception:
        logger.debug("Failed to append EHTool app event", exc_info=True)


def get_data_manager(session_id: int, db: Session) -> DataManager:
    """Get or create DataManager for a session"""
    if session_id not in _data_managers:
        # Try to reload from database
        db_session = (
            db.query(EHToolSession).filter(EHToolSession.id == session_id).first()
        )
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        # Recreate DataManager from stored paths
        data_manager = DataManager()
        try:
            data_manager.load_dataset(
                dataset_path=db_session.dataset_path, mask_path=db_session.mask_path
            )
            data_manager.project_name = db_session.project_name
            # Cache it
            _data_managers[session_id] = data_manager
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reload session data: {str(e)}",
            )

    return _data_managers[session_id]


@router.post("/detection/load", response_model=DetectionLoadResponse)
async def load_detection_dataset(
    request: DetectionLoadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        workflow = None
        if request.workflow_id:
            workflow = get_user_workflow_or_404(
                db, workflow_id=request.workflow_id, user_id=current_user.id
            )

        _append_ehtool_event(
            "proofreading_load_requested",
            dataset_path=request.dataset_path,
            mask_path=request.mask_path,
            project_name=request.project_name,
            workflow_id=request.workflow_id,
        )

        # Create DataManager and load dataset
        data_manager = DataManager()
        dataset_info = data_manager.load_dataset(
            dataset_path=request.dataset_path, mask_path=request.mask_path
        )
        data_manager.project_name = request.project_name

        # Create session in database
        db_session = EHToolSession(
            user_id=current_user.id,
            project_name=request.project_name,
            workflow_type="detection",
            dataset_path=request.dataset_path,
            mask_path=request.mask_path,
            total_layers=dataset_info["total_layers"],
            workflow_id=request.workflow_id,
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
                classification="error",  # Default to 'error' (unreviewed)
            )
            db.add(db_layer)

        db.commit()

        # Cache DataManager
        _data_managers[db_session.id] = data_manager

        if workflow:
            update_workflow_fields(
                db,
                workflow,
                {
                    "stage": "proofreading",
                    "title": request.project_name or workflow.title,
                    "dataset_path": request.dataset_path,
                    "image_path": request.dataset_path,
                    "mask_path": request.mask_path,
                    "proofreading_session_id": db_session.id,
                },
                commit=True,
            )
            append_workflow_event(
                db,
                workflow_id=workflow.id,
                actor="user",
                event_type="dataset.loaded",
                stage="proofreading",
                summary=f"Loaded dataset for proofreading: {request.project_name}",
                payload={
                    "dataset_path": request.dataset_path,
                    "mask_path": request.mask_path,
                    "total_layers": dataset_info["total_layers"],
                    "ehtool_session_id": db_session.id,
                },
            )
            append_workflow_event(
                db,
                workflow_id=workflow.id,
                actor="system",
                event_type="proofreading.session_loaded",
                stage="proofreading",
                summary="Mask proofreading session linked to workflow.",
                payload={
                    "ehtool_session_id": db_session.id,
                    "project_name": request.project_name,
                },
            )

        _append_ehtool_event(
            "proofreading_load_completed",
            session_id=db_session.id,
            total_layers=dataset_info["total_layers"],
            project_name=request.project_name,
            workflow_id=request.workflow_id,
        )

        return DetectionLoadResponse(
            session_id=db_session.id,
            total_layers=dataset_info["total_layers"],
            project_name=request.project_name,
        )

    except FileNotFoundError as e:
        _append_ehtool_event("proofreading_load_failed", level="ERROR", error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        _append_ehtool_event("proofreading_load_failed", level="ERROR", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _append_ehtool_event("proofreading_load_failed", level="ERROR", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dataset: {str(e)}",
        )


@router.get("/detection/layers", response_model=LayersPageResponse)
async def get_detection_layers(
    session_id: int,
    page: int = 1,
    page_size: int = 12,
    include_images: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify session belongs to user
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == session_id, EHToolSession.user_id == current_user.id
        )
        .first()
    )

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    data_manager = get_data_manager(session_id, db)

    total_layers = db_session.total_layers
    total_pages = math.ceil(total_layers / page_size)

    if page < 1 or page > total_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid page number. Must be between 1 and {total_pages}",
        )

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_layers)

    db.expire_all()

    db_layers = (
        db.query(EHToolLayer)
        .filter(
            EHToolLayer.session_id == session_id,
            EHToolLayer.layer_index >= start_idx,
            EHToolLayer.layer_index < end_idx,
        )
        .order_by(EHToolLayer.layer_index)
        .all()
    )

    layers = []
    for db_layer in db_layers:
        layer_info = LayerInfo(
            id=db_layer.id,
            layer_index=db_layer.layer_index,
            layer_name=db_layer.layer_name,
            classification=db_layer.classification,
        )

        if include_images:
            try:
                image_base64, mask_base64 = data_manager.get_layer_base64(
                    db_layer.layer_index, enhance=True
                )
                layer_info.image_base64 = image_base64
                layer_info.mask_base64 = mask_base64
            except Exception as e:
                print(
                    f"[GET_LAYERS] Warning: Failed to load image for layer {db_layer.layer_index}: {e}"
                )

        layers.append(layer_info)

    return LayersPageResponse(
        layers=layers,
        total=total_layers,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/detection/classify", response_model=ClassifyResponse)
async def classify_layers(
    request: LayerClassifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == request.session_id,
            EHToolSession.user_id == current_user.id,
        )
        .first()
    )

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    valid_classifications = ["correct", "incorrect", "unsure", "error"]
    if request.classification not in valid_classifications:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid classification. Must be one of: {', '.join(valid_classifications)}",
        )

    updated_count = 0
    for layer_id in request.layer_ids:
        db_layer = (
            db.query(EHToolLayer)
            .filter(
                EHToolLayer.id == layer_id, EHToolLayer.session_id == request.session_id
            )
            .first()
        )

        if db_layer:
            db_layer.classification = request.classification
            updated_count += 1

    db.commit()

    return ClassifyResponse(
        updated_count=updated_count,
        message=f"Successfully classified {updated_count} layer(s) as '{request.classification}'",
    )


@router.get("/detection/instances", response_model=InstancesResponse)
async def list_instances(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == session_id, EHToolSession.user_id == current_user.id
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    data_manager = get_data_manager(session_id, db)
    data_manager.ensure_instances()

    instances = data_manager.instances or []
    instance_mode = data_manager.instance_mode or "none"

    response_instances = [
        InstanceInfo(
            id=inst["id"],
            voxel_count=inst["voxel_count"],
            com_z=inst["com_z"],
            com_y=inst["com_y"],
            com_x=inst["com_x"],
            classification=data_manager.instance_classification.get(
                inst["id"], "error"
            ),
        )
        for inst in instances
    ]

    return InstancesResponse(
        instances=response_instances,
        instance_mode=instance_mode,
        total_instances=len(response_instances),
        total_layers=data_manager.total_layers,
        ui_state=data_manager.ui_state or None,
        persistence=data_manager.get_persistence_status(),
    )


@router.get("/detection/persistence-status", response_model=PersistenceStatusResponse)
async def get_persistence_status(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == session_id, EHToolSession.user_id == current_user.id
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    data_manager = get_data_manager(session_id, db)
    data_manager.ensure_instances()
    return PersistenceStatusResponse(persistence=data_manager.get_persistence_status())


@router.get("/detection/instance-view", response_model=InstanceViewResponse)
async def get_instance_view(
    session_id: int,
    instance_id: int,
    z_index: Optional[int] = None,
    include_raw_mask: bool = False,
    axis: str = "xy",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == session_id, EHToolSession.user_id == current_user.id
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    data_manager = get_data_manager(session_id, db)
    data_manager.ensure_instances()

    if data_manager.instance_volume is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No instance data available for this session",
        )

    view_data = data_manager.get_instance_view_data(
        instance_id=instance_id,
        z_index=z_index,
        include_raw_mask=include_raw_mask,
        axis=axis,
    )

    return InstanceViewResponse(
        instance_id=instance_id,
        axis=view_data["axis"],
        z_index=view_data["z_index"],
        total_layers=view_data["total"],
        image_base64=view_data["image_base64"],
        mask_raw_base64=view_data["mask_raw_base64"],
        mask_all_base64=view_data["mask_all_base64"],
        mask_active_base64=view_data["mask_active_base64"],
    )


@router.get("/detection/instance-image")
async def get_instance_image(
    session_id: int,
    instance_id: int,
    kind: str,
    z_index: Optional[int] = None,
    axis: str = "xy",
    max_dim: Optional[int] = None,
    quality: str = "full",
    format: str = "png",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == session_id, EHToolSession.user_id == current_user.id
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    data_manager = get_data_manager(session_id, db)
    data_manager.ensure_instances()

    if data_manager.instance_volume is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No instance data available for this session",
        )

    started_at = time.perf_counter()
    try:
        (
            image_bytes,
            resolved_index,
            total,
            resolved_axis,
            media_type,
            perf_meta,
        ) = data_manager.get_instance_image_bytes(
            instance_id=instance_id,
            z_index=z_index,
            axis=axis,
            kind=kind,
            max_dim=max_dim,
            quality=quality,
            format=format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _append_ehtool_event(
        "proofreading_instance_image_served",
        session_id=session_id,
        instance_id=instance_id,
        kind=kind,
        axis=resolved_axis,
        z_index=resolved_index,
        total_layers=total,
        quality=quality,
        format=format,
        max_dim=max_dim,
        bytes=len(image_bytes),
        elapsed_ms=round(elapsed_ms, 2),
        cache_hit=bool(perf_meta.get("cache_hit")),
        decode_ms=round(float(perf_meta.get("decode_ms", 0.0)), 2),
        resize_ms=round(float(perf_meta.get("resize_ms", 0.0)), 2),
    )

    headers = {
        "X-Z-Index": str(resolved_index),
        "X-Total-Layers": str(total),
        "X-Axis": resolved_axis,
        "X-Cache-Hit": "1" if perf_meta.get("cache_hit") else "0",
        "X-Decode-MS": f"{float(perf_meta.get('decode_ms', 0.0)):.2f}",
        "X-Resize-MS": f"{float(perf_meta.get('resize_ms', 0.0)):.2f}",
    }
    return Response(content=image_bytes, media_type=media_type, headers=headers)


@router.get("/detection/instance-filmstrip")
async def get_instance_filmstrip(
    session_id: int,
    instance_id: int,
    kind: str,
    z_start: int = 0,
    z_count: int = 16,
    axis: str = "xy",
    max_dim: Optional[int] = None,
    quality: str = "preview",
    format: str = "png",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == session_id, EHToolSession.user_id == current_user.id
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    data_manager = get_data_manager(session_id, db)
    data_manager.ensure_instances()

    if data_manager.instance_volume is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No instance data available for this session",
        )

    started_at = time.perf_counter()
    try:
        (
            image_bytes,
            resolved_start,
            resolved_count,
            total,
            resolved_axis,
            frame_height,
            media_type,
            perf_meta,
        ) = data_manager.get_instance_filmstrip_bytes(
            instance_id=instance_id,
            axis=axis,
            z_start=z_start,
            z_count=z_count,
            kind=kind,
            max_dim=max_dim,
            quality=quality,
            format=format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _append_ehtool_event(
        "proofreading_instance_filmstrip_served",
        session_id=session_id,
        instance_id=instance_id,
        kind=kind,
        axis=resolved_axis,
        z_start=resolved_start,
        z_count=resolved_count,
        total_layers=total,
        quality=quality,
        format=format,
        max_dim=max_dim,
        bytes=len(image_bytes),
        frame_height=frame_height,
        elapsed_ms=round(elapsed_ms, 2),
        cache_hit=bool(perf_meta.get("cache_hit")),
        decode_ms=round(float(perf_meta.get("decode_ms", 0.0)), 2),
        resize_ms=round(float(perf_meta.get("resize_ms", 0.0)), 2),
    )

    headers = {
        "X-Z-Start": str(resolved_start),
        "X-Z-Count": str(resolved_count),
        "X-Total-Layers": str(total),
        "X-Axis": resolved_axis,
        "X-Frame-Height": str(frame_height),
        "X-Cache-Hit": "1" if perf_meta.get("cache_hit") else "0",
        "X-Decode-MS": f"{float(perf_meta.get('decode_ms', 0.0)):.2f}",
        "X-Resize-MS": f"{float(perf_meta.get('resize_ms', 0.0)):.2f}",
    }
    return Response(content=image_bytes, media_type=media_type, headers=headers)


@router.get("/detection/instance-mask-sparse")
async def get_instance_mask_sparse(
    session_id: int,
    instance_id: int,
    z_index: Optional[int] = None,
    axis: str = "xy",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == session_id, EHToolSession.user_id == current_user.id
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    data_manager = get_data_manager(session_id, db)
    data_manager.ensure_instances()

    if data_manager.instance_volume is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No instance data available for this session",
        )

    sparse = data_manager.get_sparse_active_mask(
        instance_id=instance_id, z_index=z_index, axis=axis
    )
    color = glasbey_color(instance_id)
    mask_base64 = array_to_base64(sparse["mask_crop"], format="PNG")

    return {
        "bbox": sparse["bbox"],
        "mask_base64": mask_base64,
        "color": list(color),
        "width": sparse["width"],
        "height": sparse["height"],
        "z_index": sparse["z_index"],
        "total_layers": sparse["total"],
        "axis": sparse["axis"],
    }


@router.post("/detection/instance-classify", response_model=ClassifyResponse)
async def classify_instances(
    request: InstanceClassifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == request.session_id,
            EHToolSession.user_id == current_user.id,
        )
        .first()
    )

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    valid_classifications = ["correct", "incorrect", "unsure", "error"]
    if request.classification not in valid_classifications:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid classification. Must be one of: {', '.join(valid_classifications)}",
        )

    data_manager = get_data_manager(request.session_id, db)
    data_manager.ensure_instances()

    updated = 0
    for instance_id in request.instance_ids:
        if instance_id in data_manager.instance_classification:
            data_manager.instance_classification[instance_id] = request.classification
            updated += 1

    ui_state = request.ui_state.dict() if request.ui_state else None
    data_manager.save_progress(ui_state=ui_state)
    append_event_for_workflow_if_present(
        db,
        workflow_id=db_session.workflow_id,
        actor="user",
        event_type="proofreading.instance_classified",
        stage="proofreading",
        summary=f"Classified {updated} instance(s) as {request.classification}.",
        payload={
            "ehtool_session_id": request.session_id,
            "instance_ids": request.instance_ids,
            "classification": request.classification,
            "updated_count": updated,
        },
    )

    return ClassifyResponse(
        updated_count=updated,
        message=f"Updated {updated} instance(s)",
    )


@router.get("/detection/stats", response_model=DetectionStatsResponse)
async def get_detection_stats(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == session_id, EHToolSession.user_id == current_user.id
        )
        .first()
    )

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    layers = db.query(EHToolLayer).filter(EHToolLayer.session_id == session_id).all()

    correct = sum(1 for l in layers if l.classification == "correct")
    incorrect = sum(1 for l in layers if l.classification == "incorrect")
    unsure = sum(1 for l in layers if l.classification == "unsure")
    error = sum(1 for l in layers if l.classification == "error")
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
        progress_percent=round(progress_percent, 2),
    )


@router.delete("/detection/session/{session_id}")
async def delete_detection_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == session_id, EHToolSession.user_id == current_user.id
        )
        .first()
    )

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    if session_id in _data_managers:
        del _data_managers[session_id]

    db.delete(db_session)
    db.commit()

    return {"message": f"Session {session_id} deleted successfully"}


@router.post("/detection/mask")
async def save_mask(
    request: MaskSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save updated mask for a layer"""
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == request.session_id,
            EHToolSession.user_id == current_user.id,
        )
        .first()
    )

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    try:
        data_manager = get_data_manager(request.session_id, db)
        data_manager.save_mask(request.layer_index, request.mask_base64)
        return {"message": "Mask saved successfully"}
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save mask: {str(e)}",
        )


@router.post("/detection/instance-mask")
async def save_instance_mask(
    request: InstanceMaskSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save updated mask for an instance on a slice."""
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == request.session_id,
            EHToolSession.user_id == current_user.id,
        )
        .first()
    )

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    try:
        data_manager = get_data_manager(request.session_id, db)
        _append_ehtool_event(
            "proofreading_mask_save_requested",
            session_id=request.session_id,
            instance_id=request.instance_id,
            axis=request.axis,
            z_index=request.z_index,
        )
        save_result = data_manager.save_instance_mask_slice(
            instance_id=request.instance_id,
            axis=request.axis,
            index=request.z_index,
            mask_base64=request.mask_base64,
        )
        if request.ui_state:
            data_manager.save_progress(ui_state=request.ui_state.dict())
        append_event_for_workflow_if_present(
            db,
            workflow_id=db_session.workflow_id,
            actor="user",
            event_type="proofreading.mask_saved",
            stage="proofreading",
            summary=f"Saved mask edit for instance {request.instance_id}.",
            payload={
                "ehtool_session_id": request.session_id,
                "instance_id": request.instance_id,
                "axis": request.axis,
                "z_index": request.z_index,
            },
        )
        persistence = data_manager.get_persistence_status()
        _append_ehtool_event(
            "proofreading_mask_save_completed",
            session_id=request.session_id,
            instance_id=request.instance_id,
            axis=request.axis,
            z_index=request.z_index,
            pixels_changed=save_result.get("pixels_changed"),
            pixels_blocked=save_result.get("pixels_blocked"),
            artifact_path=persistence.get("artifact_path"),
            artifact_exists=persistence.get("artifact_exists"),
            last_saved_at=persistence.get("last_saved_at"),
        )
        return {
            "message": "Instance mask saved successfully",
            "edit": save_result,
            "persistence": persistence,
        }
    except ValueError as exc:
        _append_ehtool_event(
            "proofreading_mask_save_failed",
            level="ERROR",
            session_id=request.session_id,
            instance_id=request.instance_id,
            axis=request.axis,
            z_index=request.z_index,
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        import traceback

        traceback.print_exc()
        _append_ehtool_event(
            "proofreading_mask_save_failed",
            level="ERROR",
            session_id=request.session_id,
            instance_id=request.instance_id,
            axis=request.axis,
            z_index=request.z_index,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save instance mask: {str(e)}",
        )


@router.post("/detection/export-masks", response_model=ExportMasksResponse)
async def export_masks(
    request: ExportMasksRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_session = (
        db.query(EHToolSession)
        .filter(
            EHToolSession.id == request.session_id,
            EHToolSession.user_id == current_user.id,
        )
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    try:
        data_manager = get_data_manager(request.session_id, db)
        data_manager.ensure_instances()
        result = data_manager.export_masks(
            mode=request.mode,
            output_path=request.output_path,
            create_backup=request.create_backup,
        )
        append_event_for_workflow_if_present(
            db,
            workflow_id=db_session.workflow_id,
            actor="user",
            event_type="proofreading.masks_exported",
            stage="proofreading",
            summary=f"Exported edited masks to {result['written_path']}.",
            payload={
                "ehtool_session_id": request.session_id,
                "mode": request.mode,
                "written_path": result["written_path"],
                "backup_path": result.get("backup_path"),
                "timestamp": result["timestamp"],
            },
        )
        return ExportMasksResponse(
            message=result["message"],
            written_path=result["written_path"],
            backup_path=result.get("backup_path"),
            timestamp=result["timestamp"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to export masks")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export masks: {exc}",
        ) from exc
