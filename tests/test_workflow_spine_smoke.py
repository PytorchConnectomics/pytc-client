import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Workflow(Base):
    __tablename__ = "workflow_spine_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_key: Mapped[str] = mapped_column(String, unique=True, index=True)
    state: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    events: Mapped[list["WorkflowEvent"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", order_by="WorkflowEvent.id"
    )
    proposals: Mapped[list["AgentProposal"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", order_by="AgentProposal.id"
    )


class WorkflowEvent(Base):
    __tablename__ = "workflow_spine_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflow_spine_workflows.id"), index=True)
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    workflow: Mapped[Workflow] = relationship(back_populates="events")


class AgentProposal(Base):
    __tablename__ = "workflow_spine_agent_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflow_spine_workflows.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    workflow: Mapped[Workflow] = relationship(back_populates="proposals")


def _get_or_create_current_workflow(db: Session, external_key: str) -> Workflow:
    wf = db.query(Workflow).filter(Workflow.external_key == external_key).first()
    if wf is None:
        wf = Workflow(external_key=external_key, state="draft")
        db.add(wf)
        db.flush()
    return wf


def _append_event(db: Session, workflow: Workflow, event_type: str, payload: dict) -> WorkflowEvent:
    event = WorkflowEvent(workflow_id=workflow.id, event_type=event_type, payload=payload)
    db.add(event)
    return event


def _create_agent_proposal(db: Session, workflow: Workflow, content: dict) -> AgentProposal:
    proposal = AgentProposal(workflow_id=workflow.id, status="pending", content=content)
    db.add(proposal)
    workflow.state = "proposal_pending"
    return proposal


def _approve_proposal(db: Session, workflow: Workflow, proposal: AgentProposal) -> None:
    proposal.status = "approved"
    workflow.state = "approved"
    _append_event(
        db,
        workflow,
        "proposal_approved",
        {"proposal_id": proposal.id, "approved": True},
    )


def test_workflow_spine_smoke_e2e_sequence():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        # 1) get/create current workflow
        workflow = _get_or_create_current_workflow(db, external_key="smoke-workflow")

        # 2) append key events in order
        _append_event(db, workflow, "workflow_created", {"source": "smoke_test"})
        _append_event(db, workflow, "inputs_validated", {"valid": True})
        _append_event(db, workflow, "ready_for_proposal", {"ready": True})

        # 3) create agent proposal
        proposal = _create_agent_proposal(
            db,
            workflow,
            {"summary": "Run canonical workflow spine action", "risk": "low"},
        )
        db.flush()
        _append_event(db, workflow, "proposal_created", {"proposal_id": proposal.id})

        # 4) approve proposal
        _approve_proposal(db, workflow, proposal)
        db.commit()

        # 5) verify state/event transitions
        stored = db.query(Workflow).filter(Workflow.external_key == "smoke-workflow").one()
        events = [e.event_type for e in stored.events]

        assert stored.state == "approved"
        assert len(stored.proposals) == 1
        assert stored.proposals[0].status == "approved"
        assert events == [
            "workflow_created",
            "inputs_validated",
            "ready_for_proposal",
            "proposal_created",
            "proposal_approved",
        ]

        approved_payload = stored.events[-1].payload
        assert approved_payload["approved"] is True
        assert approved_payload["proposal_id"] == stored.proposals[0].id
