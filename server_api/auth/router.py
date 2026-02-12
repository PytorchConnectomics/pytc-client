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


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    return current_user.files


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
        "mounted_folders": mounted_folders,
        "mounted_files": mounted_files,
    }


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
