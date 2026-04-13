import sqlite3
from contextlib import closing
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowRecord:
    id: int
    state: str


@dataclass(frozen=True)
class ProposalRecord:
    id: int
    workflow_id: int
    status: str


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            is_current INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workflow_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            seq INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT,
            UNIQUE(workflow_id, seq),
            FOREIGN KEY(workflow_id) REFERENCES workflows(id)
        );

        CREATE TABLE IF NOT EXISTS agent_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(workflow_id) REFERENCES workflows(id)
        );
        """
    )


def _get_or_create_current_workflow(conn: sqlite3.Connection) -> WorkflowRecord:
    row = conn.execute(
        "SELECT id, state FROM workflows WHERE is_current = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row:
        return WorkflowRecord(id=row[0], state=row[1])

    cur = conn.execute(
        "INSERT INTO workflows(is_current, state) VALUES(1, ?)",
        ("draft",),
    )
    return WorkflowRecord(id=cur.lastrowid, state="draft")


def _append_event(conn: sqlite3.Connection, workflow_id: int, event_type: str) -> int:
    next_seq = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 FROM workflow_events WHERE workflow_id = ?",
        (workflow_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO workflow_events(workflow_id, seq, event_type, payload) VALUES(?, ?, ?, ?)",
        (workflow_id, next_seq, event_type, "{}"),
    )
    return next_seq


def _create_agent_proposal(
    conn: sqlite3.Connection, workflow_id: int, content: str
) -> ProposalRecord:
    cur = conn.execute(
        "INSERT INTO agent_proposals(workflow_id, status, content) VALUES(?, ?, ?)",
        (workflow_id, "pending", content),
    )
    conn.execute(
        "UPDATE workflows SET state = ? WHERE id = ?",
        ("proposal_pending", workflow_id),
    )
    return ProposalRecord(id=cur.lastrowid, workflow_id=workflow_id, status="pending")


def _approve_proposal(conn: sqlite3.Connection, proposal_id: int) -> ProposalRecord:
    row = conn.execute(
        "SELECT id, workflow_id, status FROM agent_proposals WHERE id = ?", (proposal_id,)
    ).fetchone()
    assert row is not None, "proposal must exist"

    conn.execute(
        "UPDATE agent_proposals SET status = ? WHERE id = ?",
        ("approved", proposal_id),
    )
    conn.execute(
        "UPDATE workflows SET state = ? WHERE id = ?",
        ("approved", row[1]),
    )
    return ProposalRecord(id=row[0], workflow_id=row[1], status="approved")


def test_workflow_spine_smoke_e2e_sqlite_contract() -> None:
    # deterministic and isolated: single private in-memory sqlite DB per test
    with closing(sqlite3.connect(":memory:")) as conn:
        _init_schema(conn)

        # 1) get/create current workflow
        workflow = _get_or_create_current_workflow(conn)
        assert workflow.state == "draft"

        workflow_again = _get_or_create_current_workflow(conn)
        assert workflow_again == workflow

        # 2) append key events in order
        expected_events = [
            "workflow_created",
            "context_collected",
            "proposal_requested",
            "proposal_created",
            "proposal_approved",
        ]
        observed_seqs = [
            _append_event(conn, workflow.id, event_type) for event_type in expected_events
        ]
        assert observed_seqs == [1, 2, 3, 4, 5]

        # 3) create agent proposal
        proposal = _create_agent_proposal(conn, workflow.id, content="Apply model settings")
        assert proposal.workflow_id == workflow.id
        assert proposal.status == "pending"

        # 4) approve proposal
        approved = _approve_proposal(conn, proposal.id)
        assert approved.id == proposal.id
        assert approved.status == "approved"

        # 5) verify state/event transitions
        final_state = conn.execute(
            "SELECT state FROM workflows WHERE id = ?", (workflow.id,)
        ).fetchone()[0]
        assert final_state == "approved"

        persisted_events = conn.execute(
            "SELECT seq, event_type FROM workflow_events WHERE workflow_id = ? ORDER BY seq",
            (workflow.id,),
        ).fetchall()
        assert [row[0] for row in persisted_events] == [1, 2, 3, 4, 5]
        assert [row[1] for row in persisted_events] == expected_events
