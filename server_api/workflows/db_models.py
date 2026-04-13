from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from server_api.auth.database import Base


class WorkflowSession(Base):
    __tablename__ = "workflow_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, default="Segmentation Workflow")
    stage = Column(String, default="setup", index=True)
    dataset_path = Column(String, nullable=True)
    image_path = Column(String, nullable=True)
    label_path = Column(String, nullable=True)
    mask_path = Column(String, nullable=True)
    neuroglancer_url = Column(Text, nullable=True)
    inference_output_path = Column(String, nullable=True)
    checkpoint_path = Column(String, nullable=True)
    proofreading_session_id = Column(Integer, nullable=True, index=True)
    corrected_mask_path = Column(String, nullable=True)
    training_output_path = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events = relationship(
        "WorkflowEvent",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowEvent.created_at",
    )


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        Integer, ForeignKey("workflow_sessions.id"), nullable=False, index=True
    )
    actor = Column(String, default="system", index=True)
    event_type = Column(String, nullable=False, index=True)
    stage = Column(String, nullable=True, index=True)
    summary = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=True)
    approval_status = Column(String, default="not_required", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("WorkflowSession", back_populates="events")

