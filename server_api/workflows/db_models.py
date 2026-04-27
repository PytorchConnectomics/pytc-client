from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
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
    config_path = Column(String, nullable=True)
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
    artifacts = relationship(
        "WorkflowArtifact",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowArtifact.created_at",
    )
    model_runs = relationship(
        "WorkflowModelRun",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowModelRun.created_at",
    )
    model_versions = relationship(
        "WorkflowModelVersion",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowModelVersion.created_at",
    )
    correction_sets = relationship(
        "WorkflowCorrectionSet",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowCorrectionSet.created_at",
    )
    evaluation_results = relationship(
        "WorkflowEvaluationResult",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowEvaluationResult.created_at",
    )
    region_hotspots = relationship(
        "WorkflowRegionHotspot",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowRegionHotspot.updated_at",
    )
    agent_plans = relationship(
        "WorkflowAgentPlan",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowAgentPlan.updated_at",
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


class WorkflowArtifact(Base):
    __tablename__ = "workflow_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        Integer, ForeignKey("workflow_sessions.id"), nullable=False, index=True
    )
    artifact_type = Column(String, nullable=False, index=True)
    role = Column(String, nullable=True, index=True)
    name = Column(String, nullable=True)
    path = Column(Text, nullable=True)
    uri = Column(Text, nullable=True)
    checksum = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    source_event_id = Column(Integer, ForeignKey("workflow_events.id"), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("WorkflowSession", back_populates="artifacts")
    source_event = relationship("WorkflowEvent")


class WorkflowModelRun(Base):
    __tablename__ = "workflow_model_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        Integer, ForeignKey("workflow_sessions.id"), nullable=False, index=True
    )
    run_type = Column(String, nullable=False, index=True)
    status = Column(String, default="pending", index=True)
    name = Column(String, nullable=True)
    config_path = Column(Text, nullable=True)
    log_path = Column(Text, nullable=True)
    output_path = Column(Text, nullable=True)
    checkpoint_path = Column(Text, nullable=True)
    input_artifact_id = Column(
        Integer, ForeignKey("workflow_artifacts.id"), nullable=True
    )
    output_artifact_id = Column(
        Integer, ForeignKey("workflow_artifacts.id"), nullable=True
    )
    source_event_id = Column(Integer, ForeignKey("workflow_events.id"), nullable=True)
    metrics_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workflow = relationship("WorkflowSession", back_populates="model_runs")
    input_artifact = relationship(
        "WorkflowArtifact", foreign_keys=[input_artifact_id]
    )
    output_artifact = relationship(
        "WorkflowArtifact", foreign_keys=[output_artifact_id]
    )
    source_event = relationship("WorkflowEvent")


class WorkflowModelVersion(Base):
    __tablename__ = "workflow_model_versions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        Integer, ForeignKey("workflow_sessions.id"), nullable=False, index=True
    )
    version_label = Column(String, nullable=False, index=True)
    status = Column(String, default="candidate", index=True)
    checkpoint_path = Column(Text, nullable=True)
    training_run_id = Column(Integer, ForeignKey("workflow_model_runs.id"), nullable=True)
    checkpoint_artifact_id = Column(
        Integer, ForeignKey("workflow_artifacts.id"), nullable=True
    )
    correction_set_id = Column(
        Integer, ForeignKey("workflow_correction_sets.id"), nullable=True
    )
    metrics_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("WorkflowSession", back_populates="model_versions")
    training_run = relationship("WorkflowModelRun")
    checkpoint_artifact = relationship("WorkflowArtifact")


class WorkflowCorrectionSet(Base):
    __tablename__ = "workflow_correction_sets"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        Integer, ForeignKey("workflow_sessions.id"), nullable=False, index=True
    )
    artifact_id = Column(Integer, ForeignKey("workflow_artifacts.id"), nullable=True)
    corrected_mask_path = Column(Text, nullable=False)
    source_mask_path = Column(Text, nullable=True)
    proofreading_session_id = Column(Integer, nullable=True, index=True)
    edit_count = Column(Integer, default=0)
    region_count = Column(Integer, default=0)
    source_event_id = Column(Integer, ForeignKey("workflow_events.id"), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("WorkflowSession", back_populates="correction_sets")
    artifact = relationship("WorkflowArtifact")
    source_event = relationship("WorkflowEvent")


class WorkflowEvaluationResult(Base):
    __tablename__ = "workflow_evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        Integer, ForeignKey("workflow_sessions.id"), nullable=False, index=True
    )
    name = Column(String, nullable=True)
    baseline_run_id = Column(Integer, ForeignKey("workflow_model_runs.id"), nullable=True)
    candidate_run_id = Column(Integer, ForeignKey("workflow_model_runs.id"), nullable=True)
    model_version_id = Column(
        Integer, ForeignKey("workflow_model_versions.id"), nullable=True
    )
    report_artifact_id = Column(
        Integer, ForeignKey("workflow_artifacts.id"), nullable=True
    )
    report_path = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("WorkflowSession", back_populates="evaluation_results")
    baseline_run = relationship("WorkflowModelRun", foreign_keys=[baseline_run_id])
    candidate_run = relationship("WorkflowModelRun", foreign_keys=[candidate_run_id])
    model_version = relationship("WorkflowModelVersion")
    report_artifact = relationship("WorkflowArtifact")


class WorkflowRegionHotspot(Base):
    __tablename__ = "workflow_region_hotspots"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        Integer, ForeignKey("workflow_sessions.id"), nullable=False, index=True
    )
    region_key = Column(String, nullable=False, index=True)
    score = Column(Float, default=0.0, index=True)
    severity = Column(String, default="low", index=True)
    status = Column(String, default="open", index=True)
    source = Column(String, default="event_heuristic", index=True)
    evidence_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workflow = relationship("WorkflowSession", back_populates="region_hotspots")


class WorkflowAgentPlan(Base):
    __tablename__ = "workflow_agent_plans"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        Integer, ForeignKey("workflow_sessions.id"), nullable=False, index=True
    )
    title = Column(String, nullable=False)
    status = Column(String, default="draft", index=True)
    risk_level = Column(String, default="medium", index=True)
    approval_status = Column(String, default="pending", index=True)
    goal = Column(Text, nullable=True)
    graph_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    source_event_id = Column(Integer, ForeignKey("workflow_events.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source_event = relationship("WorkflowEvent")
    workflow = relationship("WorkflowSession", back_populates="agent_plans")
    steps = relationship(
        "WorkflowAgentStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="WorkflowAgentStep.step_index",
    )


class WorkflowAgentStep(Base):
    __tablename__ = "workflow_agent_steps"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("workflow_agent_plans.id"), nullable=False)
    step_index = Column(Integer, nullable=False)
    action = Column(String, nullable=False, index=True)
    status = Column(String, default="pending", index=True)
    requires_approval = Column(Boolean, default=True, index=True)
    summary = Column(Text, nullable=True)
    params_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    plan = relationship("WorkflowAgentPlan", back_populates="steps")
