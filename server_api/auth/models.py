from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# SQLAlchemy Model
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    files = relationship("File", back_populates="owner")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, index=True)
    path = Column(String, default="root") # Virtual parent folder key
    is_folder = Column(Boolean, default=False)
    size = Column(String, default="0KB")
    type = Column(String, default="unknown")
    physical_path = Column(String, nullable=True) # Path on disk
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="files")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    neuroglancer_url = Column(String, nullable=True)
    image_path = Column(String, nullable=True)
    label_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Synapse(Base):
    __tablename__ = "synapses"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    pre_neuron_id = Column(Integer, nullable=True)
    post_neuron_id = Column(Integer, nullable=True)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)
    status = Column(String, default="error")  # error, correct, incorrect, unsure
    confidence = Column(Float, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Pydantic Schemas
class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class FileBase(BaseModel):
    name: str
    path: str = "root"
    is_folder: bool = False
    size: str = "0KB"
    type: str = "unknown"

class FileCreate(FileBase):
    pass

class FileUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None

class FileResponse(FileBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Synapse Proofreading Schemas
class SynapseResponse(BaseModel):
    id: int
    project_id: int
    pre_neuron_id: Optional[int]
    post_neuron_id: Optional[int]
    x: float
    y: float
    z: float
    status: str
    confidence: Optional[float]
    
    class Config:
        from_attributes = True

class SynapseUpdate(BaseModel):
    status: Optional[str] = None
    pre_neuron_id: Optional[int] = None
    post_neuron_id: Optional[int] = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    neuroglancer_url: Optional[str]
    
    class Config:
        from_attributes = True
