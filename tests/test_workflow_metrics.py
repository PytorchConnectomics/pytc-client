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


class WorkflowMetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "workflow-metrics-test.db"
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

    def _current_workflow_id(self) -> int:
        response = self.client.get("/api/workflows/current")
        self.assertEqual(response.status_code, 200)
        return response.json()["workflow"]["id"]

    def test_metrics_empty_workflow_returns_stable_shape(self):
        workflow_id = self._current_workflow_id()
        response = self.client.get(f"/api/workflows/{workflow_id}/metrics")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        metrics = payload["metrics"]
        self.assertEqual(payload["workflow_id"], workflow_id)
        self.assertIn("event_counts", metrics)
        self.assertIn("decision_metrics", metrics)
        self.assertIn("stage_transition_counts", metrics)
        self.assertIn("timestamps", metrics)
        self.assertIn("total_events", metrics)

    def test_metrics_aggregates_events_and_decisions(self):
        workflow_id = self._current_workflow_id()
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={"stage": "visualization"},
        )
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={"stage": "inference"},
        )

        events = [
            {
                "actor": "system",
                "event_type": "inference.started",
                "stage": "inference",
                "summary": "Inference started",
            },
            {
                "actor": "agent",
                "event_type": "agent.proposal_created",
                "stage": "proofreading",
                "summary": "Proposal created",
                "approval_status": "pending",
            },
            {
                "actor": "user",
                "event_type": "agent.proposal_approved",
                "stage": "retraining_staged",
                "summary": "Proposal approved",
            },
            {
                "actor": "user",
                "event_type": "agent.proposal_rejected",
                "stage": "proofreading",
                "summary": "Proposal rejected",
            },
        ]
        for event in events:
            response = self.client.post(f"/api/workflows/{workflow_id}/events", json=event)
            self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/api/workflows/{workflow_id}/metrics")
        self.assertEqual(response.status_code, 200)
        metrics = response.json()["metrics"]

        self.assertEqual(metrics["event_counts"]["inference.started"], 1)
        self.assertEqual(metrics["event_counts"]["agent.proposal_created"], 1)
        self.assertEqual(metrics["decision_metrics"]["approvals"], 1)
        self.assertEqual(metrics["decision_metrics"]["rejections"], 1)
        self.assertEqual(metrics["decision_metrics"]["total_decisions"], 2)
        self.assertGreaterEqual(metrics["decision_metrics"]["approval_rate"], 0.0)
        self.assertGreaterEqual(metrics["decision_metrics"]["rejection_rate"], 0.0)
        self.assertGreaterEqual(metrics["total_events"], 5)  # includes workflow.created


if __name__ == "__main__":
    unittest.main()
