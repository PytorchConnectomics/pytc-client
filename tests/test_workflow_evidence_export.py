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

        proposal = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions",
            json={
                "action": "start_training_run",
                "summary": "Start training from proposal",
                "payload": {
                    "label_path": "/tmp/project/label.tif",
                    "run_reference": "evidence-run-1",
                },
            },
        )
        self.assertEqual(proposal.status_code, 200)
        proposal_id = proposal.json()["id"]

        approval = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions/{proposal_id}/approve"
        )
        self.assertEqual(approval.status_code, 200)
        run_response = self.client.post(
            f"/api/workflows/{workflow_id}/model-runs",
            json={
                "run_id": "evidence-run-1",
                "run_type": "training",
                "status": "completed",
                "name": "evidence-run-1",
                "config_path": "/tmp/project/config.yaml",
                "output_path": "/tmp/project/train-output",
                "checkpoint_path": "/tmp/project/checkpoint.pt",
                "input_artifact_id": None,
                "output_artifact_id": None,
                "metrics": {},
                "metadata": {},
            },
        )
        self.assertEqual(run_response.status_code, 200)

        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "training.started",
                "stage": "retraining_staged",
                "summary": "Training started",
                "payload": {
                    "run_id": "evidence-run-1",
                    "outputPath": "/tmp/project/train-output",
                    "checkpointPath": "/tmp/project/checkpoint.pt",
                },
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "training.completed",
                "stage": "retraining_staged",
                "summary": "Training completed",
                "payload": {
                    "run_id": "evidence-run-1",
                    "outputPath": "/tmp/project/train-output",
                    "checkpointPath": "/tmp/project/checkpoint.pt",
                    "checkpointName": "checkpoint.pt",
                },
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "inference.failed",
                "stage": "retraining_staged",
                "summary": "Inference failed",
                "payload": {
                    "run_id": "evidence-run-1",
                    "outputPath": "/tmp/project/infer-output",
                    "checkpointPath": "/tmp/project/checkpoint.pt",
                },
            },
        )

        with self.SessionLocal() as db:
            workflow = (
                db.query(WorkflowSession)
                .filter(WorkflowSession.id == workflow_id)
                .first()
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
        self.assertIn("agent_proposal_approval_links", export_payload)
        self.assertIn("agent_proposal_approval_graph", export_payload)
        self.assertIn("user_status_changes", export_payload)
        self.assertIn("key_event_timeline_snippet", export_payload)
        self.assertIn("project_memory_summary", export_payload)
        self.assertGreaterEqual(
            export_payload["agent_proposal_approval_summary"]["approved_count"], 1
        )
        self.assertEqual(
            export_payload["project_memory_summary"]["schema_version"],
            "pytc-project-memory-summary/v1",
        )
        self.assertGreaterEqual(len(export_payload["user_status_changes"]), 1)
        self.assertTrue(
            any(
                change.get("event_type") == "agent.proposal_approved"
                for change in export_payload["user_status_changes"]
            )
        )
        self.assertEqual(
            export_payload["agent_proposal_approval_links"][0]["approval_status"],
            "approved",
        )
        self.assertIn("action", export_payload["agent_proposal_approval_links"][0])
        self.assertIn("model_context", export_payload)

        graph = export_payload["agent_proposal_approval_graph"]
        self.assertEqual(len(graph), 1)
        node = graph[0]
        self.assertEqual(node["proposal"]["action"], "start_training_run")
        self.assertIsNotNone(node["approval"])
        self.assertEqual(node["approval"]["status"], "approved")
        self.assertTrue(
            any(
                item["event_type"] == "training.run_approved"
                for item in node["action_events"]
            )
        )
        self.assertTrue(
            any(
                item.get("command_type") == "start_training"
                for item in node["commands"]
            )
        )
        self.assertEqual(len(node["runs"]), 1)
        run_node = node["runs"][0]
        self.assertEqual(run_node["run_type"], "training")
        self.assertEqual(run_node["run_id"], "evidence-run-1")
        self.assertGreaterEqual(len(run_node["progress_events"]), 2)
        self.assertEqual(
            run_node["progress_events"][0]["event_type"], "training.started"
        )
        self.assertEqual(
            run_node["progress_events"][1]["event_type"], "training.completed"
        )


if __name__ == "__main__":
    unittest.main()
