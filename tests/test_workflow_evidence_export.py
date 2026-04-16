import pathlib
import tempfile
import unittest

import pytest
pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from server_api.auth import database as auth_database
from server_api.auth import models
from server_api.main import app as server_api_app
from server_api.workflows.db_models import WorkflowEvent, WorkflowSession
from server_api.workflows.evidence_export import (
    EVIDENCE_EXPORT_VERSION,
    build_workflow_evidence_export,
)


class WorkflowEvidenceExportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "workflow-evidence-test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        models.Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        server_api_app.dependency_overrides[auth_database.get_db] = override_get_db
        self.client = TestClient(server_api_app)

    def tearDown(self):
        server_api_app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_evidence_export_contains_required_sections(self):
        response = self.client.get("/api/workflows/current")
        self.assertEqual(response.status_code, 200)
        workflow_id = response.json()["workflow"]["id"]

        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "agent",
                "event_type": "agent.proposal_created",
                "stage": "proofreading",
                "summary": "Proposal created",
                "approval_status": "pending",
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "agent.proposal_approved",
                "stage": "retraining_staged",
                "summary": "Proposal approved",
            },
        )

        with self.SessionLocal() as db:
            workflow = (
                db.query(WorkflowSession).filter(WorkflowSession.id == workflow_id).first()
            )
            events = (
                db.query(WorkflowEvent)
                .filter(WorkflowEvent.workflow_id == workflow_id)
                .order_by(WorkflowEvent.created_at.asc(), WorkflowEvent.id.asc())
                .all()
            )

        export_payload = build_workflow_evidence_export(workflow, events)
        self.assertEqual(export_payload["version"], EVIDENCE_EXPORT_VERSION)
        self.assertEqual(export_payload["workflow_id"], workflow_id)
        self.assertIn("stage_progression_summary", export_payload)
        self.assertIn("agent_proposal_approval_summary", export_payload)
        self.assertIn("key_event_timeline_snippet", export_payload)
        self.assertGreaterEqual(
            export_payload["agent_proposal_approval_summary"]["approved_count"], 1
        )


if __name__ == "__main__":
    unittest.main()
