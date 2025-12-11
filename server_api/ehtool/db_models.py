"""
Database models for EHTool
SQLAlchemy models for sessions and layers
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from auth.database import Base


class EHToolSession(Base):
    __tablename__ = "ehtool_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    project_name = Column(String, default="Untitled Project")
    workflow_type = Column(String, default="detection")  # 'detection' or 'proofreading'
    dataset_path = Column(String)  # Path to uploaded dataset
    mask_path = Column(String, nullable=True)  # Path to mask dataset (optional)
    total_layers = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to layers (no back_populates to User to avoid circular dependency)
    layers = relationship("EHToolLayer", back_populates="session", cascade="all, delete-orphan")


class EHToolLayer(Base):
    __tablename__ = "ehtool_layers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("ehtool_sessions.id"))
    layer_index = Column(Integer)  # 0-based index in the stack
    layer_name = Column(String)  # Filename or layer identifier
    classification = Column(String, default="error")  # 'correct', 'incorrect', 'unsure', 'error'
    image_path = Column(String, nullable=True)  # Path to cached/processed image
    mask_path = Column(String, nullable=True)  # Path to mask (if exists)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    session = relationship("EHToolSession", back_populates="layers")
