from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import models, utils, database
from jose import JWTError, jwt
from typing import List, Optional
import shutil
import os
import uuid

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, utils.SECRET_KEY, algorithms=[utils.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = models.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=models.UserResponse)
def register(user: models.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = utils.get_password_hash(user.password)
    new_user = models.User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/token", response_model=models.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
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
def get_files(current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    return current_user.files

@router.post("/files/upload", response_model=models.FileResponse)
def upload_file(
    path: str = Form(...),
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
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
    size_str = f"{size_bytes / 1024:.1f}KB" if size_bytes < 1024 * 1024 else f"{size_bytes / (1024 * 1024):.1f}MB"

    new_file = models.File(
        user_id=current_user.id,
        name=file.filename,
        path=path,
        is_folder=False,
        size=size_str,
        type=file.content_type or "unknown",
        physical_path=file_path
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    return new_file

@router.post("/files/folder", response_model=models.FileResponse)
def create_folder(
    file: models.FileCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    new_folder = models.File(
        user_id=current_user.id,
        name=file.name,
        path=file.path,
        is_folder=True,
        size="0KB",
        type="folder"
    )
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return new_folder

@router.post("/files/copy", response_model=models.FileResponse)
def copy_file(
    file_copy: models.FileCopy,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    # Find source file
    source_file = db.query(models.File).filter(models.File.id == file_copy.source_id, models.File.user_id == current_user.id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")

    # If it's a folder, we don't support recursive copy yet (or implement it if needed)
    # For now, let's assume file copy only or simple folder entry copy
    
    new_physical_path = None
    if not source_file.is_folder and source_file.physical_path and os.path.exists(source_file.physical_path):
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
        physical_path=new_physical_path
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    return new_file

@router.put("/files/{file_id}", response_model=models.FileResponse)
def update_file(
    file_id: int,
    file_update: models.FileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    file = db.query(models.File).filter(models.File.id == file_id, models.File.user_id == current_user.id).first()
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

@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    file = db.query(models.File).filter(models.File.id == file_id, models.File.user_id == current_user.id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # If it's a file, delete from disk
    if not file.is_folder and file.physical_path and os.path.exists(file.physical_path):
        os.remove(file.physical_path)
    
    # If it's a folder, we should ideally delete children, but for now let's just delete the folder entry
    # Or better: delete all children recursively
    # Simple recursive delete
    def delete_recursive(parent_key):
        children = db.query(models.File).filter(models.File.path == parent_key, models.File.user_id == current_user.id).all()
        for child in children:
            delete_recursive(str(child.id)) # Assuming key is ID-based
            if not child.is_folder and child.physical_path and os.path.exists(child.physical_path):
                os.remove(child.physical_path)
            db.delete(child)
    
    # Since we use 'folder_{timestamp}' as keys in frontend, but here we might use IDs or keep frontend keys?
    # The frontend uses 'key' which is a string. The backend uses 'id' (int).
    # We need to align this. 
    # Option 1: Frontend uses backend IDs as keys.
    # Option 2: Backend stores frontend keys.
    # Let's go with Option 1: Frontend adapts to use IDs.
    
    # For now, just delete the item itself.
    db.delete(file)
    db.commit()
    return {"message": "File deleted"}
