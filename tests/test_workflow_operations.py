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


class WorkflowOperationRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "operation-test.db"
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
        response = self.client.get("/api/workflows/current")
        self.assertEqual(response.status_code, 200)
        self.workflow_id = response.json()["workflow"]["id"]

    def tearDown(self):
        server_api_app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _create_operation(self, key="train:dataset-a:v1", **overrides):
        body = {
            "operation_type": "training",
            "idempotency_key": key,
            "actor": "user",
            "input": {"config_path": "/tmp/config.yaml"},
            "metadata": {"source": "test"},
            **overrides,
        }
        return self.client.post(
            f"/api/workflows/{self.workflow_id}/operations",
            json=body,
        )

    def _training_action(self, **overrides):
        body = {
            "action_id": "action-training-1",
            "kind": "start_training",
            "workflow_id": self.workflow_id,
            "requested_by": "agent",
            "idempotency_key": "action:start-training:1",
            "correlation_id": "conversation-1",
            "execution_owner": "server_runtime",
            "policy": {
                "risk_level": "runs_job",
                "requires_approval": True,
                "approval_reason": "Training consumes compute resources.",
            },
            "approval": {
                "status": "approved",
                "event_id": 1,
                "decided_by": "test-user",
            },
            "input_artifacts": [
                {
                    "logical_name": "synthetic-training-config",
                    "role": "config",
                    "path": "configs/Synthetic-Core-Loop-BC.yaml",
                }
            ],
            "preconditions": [
                {
                    "kind": "workflow_stage",
                    "allowed_stages": ["training_ready"],
                }
            ],
            "autopick_parameters": True,
        }
        body.update(overrides)
        return body

    def test_approved_action_envelope_stages_one_idempotent_operation(self):
        url = f"/api/workflows/{self.workflow_id}/action-operations"
        body = self._training_action()

        first_response = self.client.post(url, json=body)
        second_response = self.client.post(url, json=body)

        self.assertEqual(first_response.status_code, 202)
        self.assertEqual(second_response.status_code, 202)
        first = first_response.json()
        self.assertEqual(second_response.json()["id"], first["id"])
        self.assertEqual(first["status"], "queued")
        self.assertEqual(first["operation_type"], "agent_action:start_training")
        self.assertEqual(first["input"]["kind"], "start_training")
        self.assertEqual(first["metadata"]["action_id"], "action-training-1")
        self.assertEqual(first["correlation_id"], "conversation-1")

    def test_action_operation_rejects_unapproved_and_wrong_workflow_envelopes(self):
        url = f"/api/workflows/{self.workflow_id}/action-operations"
        unapproved = self._training_action(
            approval={"status": "pending"},
            idempotency_key="action:start-training:pending",
        )
        unapproved_response = self.client.post(url, json=unapproved)
        self.assertEqual(unapproved_response.status_code, 409)
        self.assertIn("approved", unapproved_response.json()["detail"])

        wrong_workflow = self._training_action(
            workflow_id=self.workflow_id + 1,
            idempotency_key="action:start-training:wrong-workflow",
        )
        wrong_response = self.client.post(url, json=wrong_workflow)
        self.assertEqual(wrong_response.status_code, 409)
        self.assertIn("workflow_id", wrong_response.json()["detail"])

    def test_action_operation_rejects_browser_owned_actions(self):
        url = f"/api/workflows/{self.workflow_id}/action-operations"
        body = {
            **self._training_action(),
            "action_id": "action-choose-project-1",
            "kind": "choose_project_data",
            "idempotency_key": "action:choose-project:1",
            "execution_owner": "browser_navigation",
            "policy": {
                "risk_level": "prefills_form",
                "requires_approval": False,
            },
            "approval": {"status": "not_required"},
        }
        body.pop("autopick_parameters")
        response = self.client.post(url, json=body)
        self.assertEqual(response.status_code, 409)
        self.assertIn("Browser-owned", response.json()["detail"])

    def test_action_envelope_schema_is_exposed_with_a_discriminator(self):
        response = self.client.get("/api/workflows/action-envelopes/schema")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["discriminator"]["propertyName"], "kind")
        self.assertGreaterEqual(len(schema["oneOf"]), 10)

    def test_operation_lifecycle_is_persisted_and_queryable(self):
        created_response = self._create_operation()
        self.assertEqual(created_response.status_code, 200)
        created = created_response.json()
        self.assertEqual(created["status"], "queued")
        self.assertEqual(created["attempt_count"], 0)
        self.assertTrue(created["correlation_id"])

        running_response = self.client.post(
            (
                f"/api/workflows/{self.workflow_id}/operations/"
                f"{created['id']}/transitions"
            ),
            json={
                "status": "running",
                "expected_status": "queued",
                "lease_owner": "worker-1",
                "progress": 0.1,
            },
        )
        self.assertEqual(running_response.status_code, 200)
        running = running_response.json()
        self.assertEqual(running["status"], "running")
        self.assertEqual(running["attempt_count"], 1)
        self.assertEqual(running["lease_owner"], "worker-1")
        self.assertIsNotNone(running["started_at"])
        self.assertIsNotNone(running["heartbeat_at"])

        heartbeat_response = self.client.post(
            (
                f"/api/workflows/{self.workflow_id}/operations/"
                f"{created['id']}/heartbeat"
            ),
            json={
                "lease_owner": "worker-1",
                "progress": 0.55,
                "metadata": {"runtime": {"pid": 123}},
            },
        )
        self.assertEqual(heartbeat_response.status_code, 200)
        heartbeat = heartbeat_response.json()
        self.assertEqual(heartbeat["progress"], 0.55)
        self.assertEqual(heartbeat["metadata"]["runtime"]["pid"], 123)

        succeeded_response = self.client.post(
            (
                f"/api/workflows/{self.workflow_id}/operations/"
                f"{created['id']}/transitions"
            ),
            json={
                "status": "succeeded",
                "expected_status": "running",
                "lease_owner": "worker-1",
                "result": {"checkpoint_path": "/tmp/model.pth"},
            },
        )
        self.assertEqual(succeeded_response.status_code, 200)
        succeeded = succeeded_response.json()
        self.assertEqual(succeeded["status"], "succeeded")
        self.assertEqual(succeeded["progress"], 1.0)
        self.assertEqual(succeeded["result"]["checkpoint_path"], "/tmp/model.pth")
        self.assertIsNone(succeeded["lease_owner"])
        self.assertIsNotNone(succeeded["completed_at"])

        get_response = self.client.get(
            f"/api/workflows/{self.workflow_id}/operations/{created['id']}"
        )
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["status"], "succeeded")

        list_response = self.client.get(
            f"/api/workflows/{self.workflow_id}/operations",
            params={"status": "succeeded", "operation_type": "training"},
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.json()], [created["id"]])

    def test_creation_is_idempotent_and_rejects_key_reuse(self):
        first = self._create_operation().json()
        second_response = self._create_operation()
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["id"], first["id"])
        self.assertEqual(
            second_response.json()["correlation_id"], first["correlation_id"]
        )

        conflict_response = self._create_operation(
            input={"config_path": "/tmp/different.yaml"}
        )
        self.assertEqual(conflict_response.status_code, 409)
        self.assertIn("idempotency_key", conflict_response.json()["detail"])

    def test_running_cancellation_is_requested_before_worker_acknowledgement(self):
        operation = self._create_operation(key="inference:dataset-b:v1").json()
        transition_url = (
            f"/api/workflows/{self.workflow_id}/operations/"
            f"{operation['id']}/transitions"
        )
        start_response = self.client.post(
            transition_url,
            json={"status": "running", "expected_status": "queued"},
        )
        self.assertEqual(start_response.status_code, 200)

        cancel_response = self.client.post(
            (
                f"/api/workflows/{self.workflow_id}/operations/"
                f"{operation['id']}/cancel"
            ),
            json={"reason": "User selected another checkpoint."},
        )
        self.assertEqual(cancel_response.status_code, 200)
        cancellation_requested = cancel_response.json()
        self.assertEqual(cancellation_requested["status"], "running")
        self.assertIsNotNone(cancellation_requested["cancellation_requested_at"])
        self.assertEqual(
            cancellation_requested["metadata"]["cancellation"]["reason"],
            "User selected another checkpoint.",
        )

        acknowledged_response = self.client.post(
            transition_url,
            json={"status": "cancelled", "expected_status": "running"},
        )
        self.assertEqual(acknowledged_response.status_code, 200)
        self.assertEqual(acknowledged_response.json()["status"], "cancelled")

        invalid_response = self.client.post(
            transition_url,
            json={"status": "succeeded"},
        )
        self.assertEqual(invalid_response.status_code, 409)

    def test_queued_cancellation_is_immediately_terminal(self):
        operation = self._create_operation(key="evaluation:cancel-before-start").json()
        response = self.client.post(
            (
                f"/api/workflows/{self.workflow_id}/operations/"
                f"{operation['id']}/cancel"
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertIsNotNone(response.json()["completed_at"])

    def test_expected_status_and_lease_owner_prevent_stale_updates(self):
        operation = self._create_operation(key="export:evidence:v1").json()
        transition_url = (
            f"/api/workflows/{self.workflow_id}/operations/"
            f"{operation['id']}/transitions"
        )
        stale_response = self.client.post(
            transition_url,
            json={"status": "running", "expected_status": "running"},
        )
        self.assertEqual(stale_response.status_code, 409)

        self.client.post(
            transition_url,
            json={"status": "running", "lease_owner": "worker-1"},
        )
        heartbeat_response = self.client.post(
            (
                f"/api/workflows/{self.workflow_id}/operations/"
                f"{operation['id']}/heartbeat"
            ),
            json={"lease_owner": "worker-2", "progress": 0.5},
        )
        self.assertEqual(heartbeat_response.status_code, 409)

        bad_progress_response = self.client.post(
            (
                f"/api/workflows/{self.workflow_id}/operations/"
                f"{operation['id']}/heartbeat"
            ),
            json={"lease_owner": "worker-1", "progress": 1.5},
        )
        self.assertEqual(bad_progress_response.status_code, 400)
