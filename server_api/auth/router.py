from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import models, utils, database
from jose import JWTError, jwt
from typing import List, Optional
import shutil
import os
import uuid
import mimetypes
from server_api.utils.utils import resolve_existing_path

try:  # Optional preview dependencies
    import cv2
    import numpy as np
    import tifffile
except Exception:  # pragma: no cover - preview is best-effort
    cv2 = None
    np = None
    tifffile = None

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
IGNORED_SYSTEM_FILENAMES = {
    ".ds_store",
    "thumbs.db",
    ".pytc_proofreading.json",
    ".pytc_instance_labels.tif",
}
PROJECT_PROFILE_MAX_FILES = 2500

VOLUME_EXTENSIONS = {
    ".h5",
    ".hdf5",
    ".tif",
    ".tiff",
    ".ome.tif",
    ".ome.tiff",
    ".npy",
    ".npz",
    ".zarr",
    ".n5",
    ".nii",
    ".nii.gz",
    ".mrc",
    ".mrcs",
}
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml"}
CHECKPOINT_EXTENSIONS = {".pt", ".pth", ".pth.tar", ".ckpt", ".onnx"}


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def _is_ignored_system_file(name: Optional[str]) -> bool:
    return str(name or "").strip().lower() in IGNORED_SYSTEM_FILENAMES


def _project_suggestion_candidates() -> List[dict]:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    workspace_root = os.path.abspath(os.path.join(repo_root, ".."))
    return [
        {
            "id": "mito25-paper-loop-smoke",
            "name": "mito25-paper-loop-smoke",
            "directory_path": os.path.join(
                repo_root, "testing_projects", "mito25_paper_loop_smoke"
            ),
            "description": "Curated mito25 smoke project with image/seg, configs, checkpoint, and prediction artifacts.",
            "recommended": True,
        },
        {
            "id": "mito25-raw-data",
            "name": "mito25",
            "directory_path": os.path.join(workspace_root, "testing_data", "mito25"),
            "description": "Raw mito25 image/seg source data.",
            "recommended": False,
        },
        {
            "id": "mito25-smoke-raw-data",
            "name": "mito25-smoke",
            "directory_path": os.path.join(
                workspace_root, "testing_data", "mito25_smoke"
            ),
            "description": "Small paired mito25 HDF5 image/seg volumes for fast smoke testing.",
            "recommended": False,
        },
        {
            "id": "snemi-proofreading-data",
            "name": "snemi-proofreading",
            "directory_path": os.path.join(workspace_root, "testing_data", "snemi"),
            "description": "SNEMI-style TIFF image/label volumes for proofreading-focused testing.",
            "recommended": False,
        },
    ]


def _lower_path_parts(path: str) -> List[str]:
    normalized = os.path.normpath(path).lower()
    return [part for part in normalized.split(os.sep) if part]


def _project_extension(name: str) -> str:
    lower = name.lower()
    for compound in (".ome.tiff", ".ome.tif", ".nii.gz", ".pth.tar"):
        if lower.endswith(compound):
            return compound
    return os.path.splitext(lower)[1]


def _role_for_project_file(relative_path: str) -> Optional[str]:
    parts = _lower_path_parts(relative_path)
    name = parts[-1] if parts else os.path.basename(relative_path).lower()
    stem = name
    extension = _project_extension(name)
    if extension:
        stem = name[: -len(extension)]
    haystack = " ".join(parts + [stem])

    if extension in CHECKPOINT_EXTENSIONS or "checkpoint" in haystack:
        return "checkpoint"
    if extension in CONFIG_EXTENSIONS and (
        "config" in haystack or "mito" in haystack or "pytc" in haystack
    ):
        return "config"
    if extension not in VOLUME_EXTENSIONS:
        if extension in {".md", ".txt"} or "notes" in haystack:
            return "notes"
        return None

    if any(
        token in haystack
        for token in (
            "prediction",
            "predictions",
            "result",
            "inference",
            "candidate",
            "baseline",
        )
    ):
        return "prediction"
    if any(
        token in haystack
        for token in (
            "_seg",
            " seg",
            "segmentation",
            "label",
            "labels",
            "mask",
            "masks",
            "ground",
            "truth",
            "consensus",
            "gt",
        )
    ):
        return "label"
    if any(token in haystack for token in ("image", "images", "_im", "raw")):
        return "image"
    return "volume"


def _looks_like_image_label_pair(image_path: str, label_path: str) -> bool:
    image_name = os.path.basename(image_path).lower()
    label_name = os.path.basename(label_path).lower()
    normalized_image = (
        image_name.replace("_image", "")
        .replace("_images", "")
        .replace("_im", "")
        .replace("-image", "")
    )
    normalized_label = (
        label_name.replace("_seg", "")
        .replace("_label", "")
        .replace("_labels", "")
        .replace("_mask", "")
        .replace("_consensus", "")
        .replace("-seg", "")
    )
    return normalized_image.split(".")[0] == normalized_label.split(".")[0]


def _first_project_path(roles: dict, role: str) -> Optional[str]:
    values = roles.get(role) or []
    return values[0] if values else None


def _project_stage_status(
    *,
    ready: bool,
    missing: Optional[List[str]] = None,
    ready_label: str,
    needed_label: str,
    blocked_label: str = "Add an image volume first.",
) -> dict:
    missing = missing or []
    if ready:
        return {"status": "ready", "label": ready_label, "missing": []}
    if missing:
        return {"status": "needs_input", "label": needed_label, "missing": missing}
    return {"status": "blocked", "label": blocked_label, "missing": []}


def _build_project_workable_schema(
    roles: dict,
    counts: dict,
    paired_examples: List[dict],
    *,
    truncated: bool,
) -> dict:
    primary_image = _first_project_path(roles, "image") or _first_project_path(
        roles, "volume"
    )
    primary_label = (
        paired_examples[0]["label"] if paired_examples else _first_project_path(roles, "label")
    )
    primary_prediction = _first_project_path(roles, "prediction")
    primary_config = _first_project_path(roles, "config")
    primary_checkpoint = _first_project_path(roles, "checkpoint")
    has_image = bool(primary_image)
    has_mask_like = bool(primary_label or primary_prediction)
    has_image_label = bool(primary_image and primary_label)
    # Configs are implementation details the agent can infer from presets. They
    # are tracked for provenance, but should not block a biologist from starting
    # an otherwise valid image/checkpoint or image/label workflow.
    has_inference_inputs = bool(primary_image and primary_checkpoint)
    has_training_inputs = bool(primary_image and primary_label)
    has_evaluation_inputs = bool(
        primary_label and counts.get("prediction", 0) >= 2
    )

    if not has_image:
        mode = "not_workable"
        summary = "No image volume detected yet."
    elif has_evaluation_inputs and has_training_inputs and primary_checkpoint:
        mode = "closed_loop_ready"
        summary = "Ready for visualization, proofreading, training, and before/after checks."
    elif has_image_label:
        mode = "image_mask_pair"
        summary = "Ready to start from an image and mask/label pair."
    else:
        mode = "image_only"
        summary = "Ready to start from an image volume; masks, configs, or checkpoints can be added later."

    inference_missing = []
    if not primary_image:
        inference_missing.append("image volume")
    if not primary_checkpoint:
        inference_missing.append("checkpoint")

    proofreading_missing = []
    if not primary_image:
        proofreading_missing.append("image volume")
    if not has_mask_like:
        proofreading_missing.append("mask, label, or prediction")

    training_missing = []
    if not primary_image:
        training_missing.append("image volume")
    if not primary_label:
        training_missing.append("label or corrected mask")

    evaluation_missing = []
    if counts.get("prediction", 0) < 2:
        evaluation_missing.append("baseline and candidate predictions")
    if not primary_label:
        evaluation_missing.append("reference label or ground truth")

    return {
        "schema_version": "pytc-project-profile/v1",
        "workable": has_image,
        "mode": mode,
        "summary": summary,
        "truncated": truncated,
        "primary_paths": {
            "image": primary_image,
            "label": primary_label,
            "mask": primary_label or primary_prediction,
            "prediction": primary_prediction,
            "config": primary_config,
            "checkpoint": primary_checkpoint,
        },
        "stages": {
            "setup": _project_stage_status(
                ready=has_image,
                ready_label="Image volume detected.",
                needed_label="Choose an image volume.",
            ),
            "visualization": _project_stage_status(
                ready=has_image,
                ready_label="Ready to visualize.",
                needed_label="Choose an image volume.",
            ),
            "inference": _project_stage_status(
                ready=has_inference_inputs,
                ready_label="Ready to run inference.",
                needed_label="Needs inference inputs.",
                missing=inference_missing,
            ),
            "proofreading": _project_stage_status(
                ready=bool(primary_image and has_mask_like),
                ready_label="Ready to proofread masks.",
                needed_label="Needs a mask, label, or prediction.",
                missing=proofreading_missing,
            ),
            "training": _project_stage_status(
                ready=has_training_inputs,
                ready_label="Ready to train from labels/corrections.",
                needed_label="Needs training inputs.",
                missing=training_missing,
            ),
            "evaluation": _project_stage_status(
                ready=has_evaluation_inputs,
                ready_label="Ready to compare before/after predictions.",
                needed_label="Needs comparison inputs.",
                missing=evaluation_missing,
            ),
        },
    }


def _scan_project_profile(directory_path: str) -> dict:
    roles = {
        "image": [],
        "label": [],
        "prediction": [],
        "config": [],
        "checkpoint": [],
        "volume": [],
        "notes": [],
    }
    counts = {role: 0 for role in roles}
    scanned_files = 0
    truncated = False

    for current_dir, dirnames, filenames in os.walk(directory_path):
        dirnames[:] = [
            dirname
            for dirname in sorted(dirnames)
            if not _is_ignored_system_file(dirname)
        ]
        for filename in sorted(filenames):
            if _is_ignored_system_file(filename):
                continue
            scanned_files += 1
            if scanned_files > PROJECT_PROFILE_MAX_FILES:
                truncated = True
                break
            absolute_path = os.path.join(current_dir, filename)
            relative_path = os.path.relpath(absolute_path, directory_path)
            role = _role_for_project_file(relative_path)
            if role and role in roles:
                counts[role] += 1
                if len(roles[role]) < 8:
                    roles[role].append(relative_path)
        if truncated:
            break

    paired_examples = []
    for image_path in roles["image"]:
        for label_path in roles["label"]:
            if _looks_like_image_label_pair(image_path, label_path):
                paired_examples.append(
                    {"image": image_path, "label": label_path}
                )
                break
        if len(paired_examples) >= 4:
            break

    schema = _build_project_workable_schema(
        roles,
        counts,
        paired_examples,
        truncated=truncated,
    )

    required_roles = {
        "image": counts["image"] > 0,
        "label": counts["label"] > 0,
        "config": counts["config"] > 0,
        "checkpoint": counts["checkpoint"] > 0,
        "prediction": counts["prediction"] >= 2,
    }
    missing_roles = [
        role for role, present in required_roles.items() if not present
    ]

    return {
        "scanned_files": min(scanned_files, PROJECT_PROFILE_MAX_FILES),
        "truncated": truncated,
        "counts": counts,
        "examples": roles,
        "paired_examples": paired_examples,
        "ready_for_smoke": not missing_roles,
        "missing_roles": missing_roles,
        "schema": schema,
    }


def _ensure_unique_name(
    db: Session, user_id: int, parent_path: str, base_name: str
) -> str:
    existing_names = {
        row[0]
        for row in db.query(models.File.name).filter(
            models.File.user_id == user_id, models.File.path == parent_path
        )
    }
    if base_name not in existing_names:
        return base_name
    index = 2
    while True:
        candidate = f"{base_name} ({index})"
        if candidate not in existing_names:
            return candidate
        index += 1


def _is_managed_upload_path(user_id: int, physical_path: Optional[str]) -> bool:
    if not physical_path:
        return False
    uploads_root = os.path.abspath(os.path.join("uploads", str(user_id)))
    target = os.path.abspath(os.path.expanduser(physical_path))
    try:
        return os.path.commonpath([uploads_root, target]) == uploads_root
    except ValueError:
        return False


def _repair_stale_mounted_entries(db: Session, user_id: int) -> None:
    candidates = (
        db.query(models.File)
        .filter(
            models.File.user_id == user_id,
            models.File.physical_path.isnot(None),
            models.File.path != "root",
        )
        .all()
    )

    changed = False
    for entry in candidates:
        if not entry.physical_path:
            continue
        if _is_managed_upload_path(user_id, entry.physical_path):
            continue
        if os.path.exists(entry.physical_path):
            continue

        repaired = resolve_existing_path(entry.physical_path)
        if repaired is None or not repaired.exists():
            continue
        if entry.is_folder and not repaired.is_dir():
            continue
        if not entry.is_folder and not repaired.is_file():
            continue

        entry.physical_path = str(repaired)
        entry.name = repaired.name
        if not entry.is_folder:
            entry.type = mimetypes.guess_type(str(repaired))[0] or entry.type
            try:
                entry.size = _format_size(repaired.stat().st_size)
            except OSError:
                pass
        changed = True

    if changed:
        db.commit()


def _prune_missing_managed_upload_entries(db: Session, user_id: int) -> None:
    candidates = (
        db.query(models.File)
        .filter(
            models.File.user_id == user_id,
            models.File.is_folder.is_(False),
            models.File.physical_path.isnot(None),
        )
        .all()
    )

    removed = False
    for entry in candidates:
        if not entry.physical_path:
            continue
        if not _is_managed_upload_path(user_id, entry.physical_path):
            continue
        if os.path.exists(entry.physical_path):
            continue
        db.delete(entry)
        removed = True

    if removed:
        db.commit()


def _delete_file_tree(
    db: Session,
    user_id: int,
    node: models.File,
    delete_disk_files: bool = True,
):
    children = (
        db.query(models.File)
        .filter(models.File.path == str(node.id), models.File.user_id == user_id)
        .all()
    )
    for child in children:
        _delete_file_tree(db, user_id, child, delete_disk_files=delete_disk_files)

    if (
        delete_disk_files
        and not node.is_folder
        and node.physical_path
        and os.path.exists(node.physical_path)
        and _is_managed_upload_path(user_id, node.physical_path)
    ):
        os.remove(node.physical_path)
    db.delete(node)


def _get_or_create_guest_user(db: Session) -> models.User:
    """Return the shared guest user, creating it if needed."""
    guest = db.query(models.User).filter(models.User.username == "guest").first()
    if guest:
        return guest
    guest = models.User(
        username="guest",
        email=None,
        hashed_password=utils.get_password_hash("guest"),
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)
):
    # If no token is provided, fall back to the shared guest account.
    if not token:
        return _get_or_create_guest_user(db)

    try:
        payload = jwt.decode(token, utils.SECRET_KEY, algorithms=[utils.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return _get_or_create_guest_user(db)
        token_data = models.TokenData(username=username)
    except JWTError:
        return _get_or_create_guest_user(db)

    user = (
        db.query(models.User)
        .filter(models.User.username == token_data.username)
        .first()
    )
    if user is None:
        return _get_or_create_guest_user(db)
    return user


@router.post("/register", response_model=models.UserResponse)
def register(user: models.UserCreate, db: Session = Depends(database.get_db)):
    db_user = (
        db.query(models.User).filter(models.User.username == user.username).first()
    )
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = utils.get_password_hash(user.password)
    new_user = models.User(
        username=user.username, email=user.email, hashed_password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/token", response_model=models.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(models.User).filter(models.User.username == form_data.username).first()
    )
    if not user or not utils.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = utils.timedelta(minutes=utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = utils.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=models.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


# File Management Endpoints


@router.get("/files", response_model=List[models.FileResponse])
def get_files(
    parent: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    _repair_stale_mounted_entries(db, current_user.id)
    _prune_missing_managed_upload_entries(db, current_user.id)
    query = db.query(models.File).filter(models.File.user_id == current_user.id)
    if parent is not None:
        query = query.filter(models.File.path == parent)

    return [
        file
        for file in query.order_by(models.File.is_folder.desc(), models.File.name.asc()).all()
        if not _is_ignored_system_file(file.name)
    ]


@router.get("/files/preview/{file_id}")
def file_preview(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    if cv2 is None or np is None:
        raise HTTPException(status_code=500, detail="Preview dependencies missing")

    file = (
        db.query(models.File)
        .filter(models.File.id == file_id, models.File.user_id == current_user.id)
        .first()
    )
    if not file or file.is_folder:
        raise HTTPException(status_code=404, detail="File not found")
    if not file.physical_path or not os.path.exists(file.physical_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    def to_uint8(arr):
        if arr is None:
            return None
        if arr.dtype == np.uint8:
            return arr
        arr = arr.astype(np.float32)
        min_val = np.nanmin(arr)
        max_val = np.nanmax(arr)
        if max_val <= min_val:
            return np.zeros_like(arr, dtype=np.uint8)
        scaled = (arr - min_val) / (max_val - min_val)
        return np.clip(scaled * 255.0, 0, 255).astype(np.uint8)

    def load_image(path: str) -> Optional["np.ndarray"]:
        ext = os.path.splitext(path)[1].lower()
        if ext in {".tif", ".tiff"} and tifffile is not None:
            try:
                img = tifffile.imread(path)
            except Exception:
                img = None
        else:
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None

        img = np.asarray(img)
        if img.ndim == 2:
            return to_uint8(img)
        if img.ndim == 3:
            if img.shape[2] in (3, 4):
                if img.shape[2] == 4:
                    img = img[:, :, :3]
                return to_uint8(img)
            mid = img.shape[0] // 2
            return to_uint8(img[mid])
        if img.ndim == 4:
            mid = img.shape[0] // 2
            img = img[mid]
            if img.ndim == 3 and img.shape[2] == 4:
                img = img[:, :, :3]
            return to_uint8(img)
        return None

    image = load_image(file.physical_path)
    if image is None:
        raise HTTPException(status_code=415, detail="Unsupported image format")

    max_dim = 160
    height, width = image.shape[:2]
    scale = min(1.0, max_dim / max(height, width))
    if scale < 1.0:
        new_size = (int(width * scale), int(height * scale))
        image = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)

    success, buffer = cv2.imencode(".png", image)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode preview")
    return Response(content=buffer.tobytes(), media_type="image/png")


@router.post("/files/upload", response_model=models.FileResponse)
def upload_file(
    path: str = Form(...),
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    if _is_ignored_system_file(file.filename):
        raise HTTPException(
            status_code=400, detail="System metadata files are ignored"
        )

    # Create uploads directory if not exists
    upload_dir = f"uploads/{current_user.id}"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = f"{upload_dir}/{unique_filename}"

    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Calculate size (approx)
    size_bytes = os.path.getsize(file_path)
    size_str = (
        f"{size_bytes / 1024:.1f}KB"
        if size_bytes < 1024 * 1024
        else f"{size_bytes / (1024 * 1024):.1f}MB"
    )

    new_file = models.File(
        user_id=current_user.id,
        name=file.filename,
        path=path,
        is_folder=False,
        size=size_str,
        type=file.content_type or "unknown",
        physical_path=file_path,
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    return new_file


@router.post("/files/folder", response_model=models.FileResponse)
def create_folder(
    file: models.FileCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    new_folder = models.File(
        user_id=current_user.id,
        name=file.name,
        path=file.path,
        is_folder=True,
        size="0KB",
        type="folder",
    )
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return new_folder


@router.post("/files/copy", response_model=models.FileResponse)
def copy_file(
    file_copy: models.FileCopy,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    # Find source file
    source_file = (
        db.query(models.File)
        .filter(
            models.File.id == file_copy.source_id,
            models.File.user_id == current_user.id,
        )
        .first()
    )
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")

    # If it's a folder, we don't support recursive copy yet (or implement it if needed)
    # For now, let's assume file copy only or simple folder entry copy

    new_physical_path = None
    if (
        not source_file.is_folder
        and source_file.physical_path
        and os.path.exists(source_file.physical_path)
    ):
        # Generate new filename
        file_ext = os.path.splitext(source_file.physical_path)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        # Use same upload dir
        upload_dir = os.path.dirname(source_file.physical_path)
        new_physical_path = f"{upload_dir}/{unique_filename}"
        shutil.copy2(source_file.physical_path, new_physical_path)

    new_file = models.File(
        user_id=current_user.id,
        name=f"Copy of {source_file.name}",
        path=file_copy.destination_path,
        is_folder=source_file.is_folder,
        size=source_file.size,
        type=source_file.type,
        physical_path=new_physical_path,
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    return new_file


@router.post("/files/mount")
def mount_directory(
    mount_request: models.MountDirectoryRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    # This endpoint creates an app-managed file index for a project root.
    # The same contract can later be backed by cloud project files/URIs for
    # programmatic access without changing the UI workflow.
    source_dir = os.path.abspath(os.path.expanduser(mount_request.directory_path))
    if not os.path.isdir(source_dir):
        raise HTTPException(status_code=400, detail="Directory does not exist")

    destination_path = mount_request.destination_path or "root"
    if destination_path != "root":
        try:
            destination_id = int(destination_path)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid destination path"
            ) from exc
        destination_folder = (
            db.query(models.File)
            .filter(
                models.File.id == destination_id,
                models.File.user_id == current_user.id,
                models.File.is_folder.is_(True),
            )
            .first()
        )
        if not destination_folder:
            raise HTTPException(status_code=404, detail="Destination folder not found")

    default_name = os.path.basename(source_dir.rstrip(os.sep)) or "mounted-project"
    requested_name = (
        mount_request.mount_name.strip()
        if mount_request.mount_name and mount_request.mount_name.strip()
        else default_name
    )
    root_name = _ensure_unique_name(
        db, current_user.id, destination_path, requested_name
    )
    mounted_root = models.File(
        user_id=current_user.id,
        name=root_name,
        path=destination_path,
        is_folder=True,
        size="0KB",
        type="folder",
        physical_path=source_dir,
    )
    db.add(mounted_root)
    db.flush()

    dir_to_id = {source_dir: str(mounted_root.id)}
    mounted_folders = 1
    mounted_files = 0

    for current_dir, dirnames, filenames in os.walk(source_dir, topdown=True):
        parent_id = dir_to_id.get(current_dir)
        if parent_id is None:
            continue
        dirnames.sort()
        filenames.sort()

        for dirname in dirnames:
            abs_subdir = os.path.join(current_dir, dirname)
            folder_name = _ensure_unique_name(db, current_user.id, parent_id, dirname)
            folder_record = models.File(
                user_id=current_user.id,
                name=folder_name,
                path=parent_id,
                is_folder=True,
                size="0KB",
                type="folder",
                physical_path=abs_subdir,
            )
            db.add(folder_record)
            db.flush()
            dir_to_id[abs_subdir] = str(folder_record.id)
            mounted_folders += 1

        for filename in filenames:
            if _is_ignored_system_file(filename):
                continue
            abs_file = os.path.join(current_dir, filename)
            if not os.path.isfile(abs_file):
                continue
            file_name = _ensure_unique_name(db, current_user.id, parent_id, filename)
            mime_type = mimetypes.guess_type(abs_file)[0] or "application/octet-stream"
            try:
                file_size = _format_size(os.path.getsize(abs_file))
            except OSError:
                file_size = "0B"
            file_record = models.File(
                user_id=current_user.id,
                name=file_name,
                path=parent_id,
                is_folder=False,
                size=file_size,
                type=mime_type,
                physical_path=abs_file,
            )
            db.add(file_record)
            mounted_files += 1

    db.commit()

    return {
        "message": f"Mounted {mounted_files} files from {source_dir}",
        "mounted_root_id": mounted_root.id,
        "mount_name": root_name,
        "mounted_folders": mounted_folders,
        "mounted_files": mounted_files,
        "profile": _scan_project_profile(source_dir),
    }


@router.get("/files/project-suggestions")
def list_project_suggestions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    suggestions = []
    mounted_roots = (
        db.query(models.File)
        .filter(
            models.File.user_id == current_user.id,
            models.File.path == "root",
            models.File.is_folder.is_(True),
            models.File.physical_path.isnot(None),
        )
        .all()
    )
    mounted_by_path = {
        os.path.abspath(os.path.expanduser(root.physical_path)): root
        for root in mounted_roots
        if root.physical_path
    }
    for candidate in _project_suggestion_candidates():
        directory_path = os.path.abspath(
            os.path.expanduser(candidate["directory_path"])
        )
        if not os.path.isdir(directory_path):
            continue
        mounted_root = mounted_by_path.get(directory_path)
        suggestions.append(
            {
                **candidate,
                "directory_path": directory_path,
                "already_mounted": mounted_root is not None,
                "mounted_root_id": mounted_root.id if mounted_root else None,
                "profile": _scan_project_profile(directory_path),
            }
        )
    suggested_paths = {item["directory_path"] for item in suggestions}
    for mounted_path, mounted_root in mounted_by_path.items():
        if mounted_path in suggested_paths or not os.path.isdir(mounted_path):
            continue
        suggestions.append(
            {
                "id": f"mounted-{mounted_root.id}",
                "name": mounted_root.name,
                "directory_path": mounted_path,
                "description": "Mounted project directory.",
                "recommended": False,
                "already_mounted": True,
                "mounted_root_id": mounted_root.id,
                "profile": _scan_project_profile(mounted_path),
            }
        )
    return suggestions


@router.put("/files/{file_id}", response_model=models.FileResponse)
def update_file(
    file_id: int,
    file_update: models.FileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    file = (
        db.query(models.File)
        .filter(models.File.id == file_id, models.File.user_id == current_user.id)
        .first()
    )
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Only update provided fields
    if file_update.name is not None:
        file.name = file_update.name
    if file_update.path is not None:
        file.path = file_update.path

    db.commit()
    db.refresh(file)
    return file


@router.delete("/files/unmount/{file_id}")
def unmount_project(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    folder = (
        db.query(models.File)
        .filter(
            models.File.id == file_id,
            models.File.user_id == current_user.id,
            models.File.is_folder.is_(True),
        )
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Project folder not found")

    # Mounted projects are represented by folder records that reference an external path.
    if not folder.physical_path or _is_managed_upload_path(
        current_user.id, folder.physical_path
    ):
        raise HTTPException(
            status_code=400, detail="This folder is not a mounted project"
        )

    _delete_file_tree(db, current_user.id, folder, delete_disk_files=False)
    db.commit()
    return {"message": "Project unmounted"}


@router.delete("/files/workspace")
def reset_workspace(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    root_nodes = (
        db.query(models.File)
        .filter(models.File.user_id == current_user.id, models.File.path == "root")
        .all()
    )
    total_rows = (
        db.query(models.File).filter(models.File.user_id == current_user.id).count()
    )
    mounted_root_count = 0

    for node in root_nodes:
        delete_disk_files = True
        if node.physical_path and not _is_managed_upload_path(
            current_user.id, node.physical_path
        ):
            mounted_root_count += 1
            delete_disk_files = False

        _delete_file_tree(
            db,
            current_user.id,
            node,
            delete_disk_files=delete_disk_files,
        )

    uploads_root = os.path.abspath(os.path.join("uploads", str(current_user.id)))
    if os.path.isdir(uploads_root):
        shutil.rmtree(uploads_root, ignore_errors=True)
    os.makedirs(uploads_root, exist_ok=True)

    db.commit()
    return {
        "message": "Workspace reset",
        "deleted_count": total_rows,
        "mounted_root_count": mounted_root_count,
    }


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    file = (
        db.query(models.File)
        .filter(models.File.id == file_id, models.File.user_id == current_user.id)
        .first()
    )
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete DB records recursively and only remove files from disk for app-managed uploads.
    _delete_file_tree(db, current_user.id, file, delete_disk_files=True)
    db.commit()
    return {"message": "File deleted"}
