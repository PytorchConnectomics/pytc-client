import pathlib
import tempfile
import unittest

import numpy as np
import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("fastapi")
pytest.importorskip("tifffile")
import tifffile
from fastapi.testclient import TestClient

from server_api.auth import database as auth_database
from server_api.auth import models
from server_api.main import app as server_api_app


class AgentEvaluationExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp_dir.name)
        self.db_path = self.root / "agent-evaluation.db"
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

    def _volume_paths(self):
        ground_truth_path = self.root / "ground-truth.tif"
        baseline_path = self.root / "baseline.tif"
        candidate_path = self.root / "candidate.tif"
        ground_truth = np.zeros((1, 4, 4), dtype=np.uint8)
        ground_truth[:, 1:3, 1:3] = 1
        baseline = np.zeros_like(ground_truth)
        baseline[:, 1:2, 1:2] = 1
        tifffile.imwrite(str(ground_truth_path), ground_truth)
        tifffile.imwrite(str(baseline_path), baseline)
        tifffile.imwrite(str(candidate_path), ground_truth)
        return baseline_path, candidate_path, ground_truth_path

    def _workflow_action(self, **overrides):
        baseline, candidate, ground_truth = self._volume_paths()
        action = {
            "kind": "compute_evaluation",
            "name": "agent-before-after",
            "baseline_prediction_path": str(baseline),
            "candidate_prediction_path": str(candidate),
            "ground_truth_path": str(ground_truth),
            "report_path": str(self.root / "agent-evaluation-report.json"),
            "metadata": {"source": "typed-agent-action-test"},
        }
        action.update(overrides)
        return action

    def _propose(self, workflow_action, correlation_id="proposal-correlation-7"):
        response = self.client.post(
            f"/api/workflows/{self.workflow_id}/agent-actions",
            json={
                "action": "run_client_effects",
                "summary": "Compute approved before/after evaluation.",
                "payload": {
                    "correlation_id": correlation_id,
                    "client_effects": {
                        "navigate_to": "project-progress",
                        "workflow_action": workflow_action,
                    },
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _envelope(self, proposal_id, workflow_action, approval):
        return {
            "action_id": f"proposal:{proposal_id}:compute_evaluation",
            "kind": "compute_evaluation",
            "workflow_id": self.workflow_id,
            "requested_by": "agent",
            "idempotency_key": f"agent-proposal:{proposal_id}:compute_evaluation",
            "correlation_id": "proposal-correlation-7",
            "execution_owner": "server_workflow",
            "policy": {
                "risk_level": "writes_workflow_record",
                "requires_approval": True,
            },
            "approval": approval,
            **{key: value for key, value in workflow_action.items() if key != "kind"},
        }

    def test_approval_executes_once_and_returns_terminal_typed_evidence(self):
        workflow_action = self._workflow_action()
        proposal = self._propose(workflow_action)

        approved = self.client.post(
            f"/api/workflows/{self.workflow_id}/agent-actions/"
            f"{proposal['id']}/approve"
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        payload = approved.json()

        receipt = payload["receipt"]
        operation = payload["operation"]
        approval_event = payload["events"][0]
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(receipt["kind"], "compute_evaluation")
        self.assertEqual(receipt["correlation_id"], "proposal-correlation-7")
        self.assertEqual(receipt["operation_id"], operation["id"])
        self.assertEqual(operation["status"], "succeeded")
        self.assertEqual(operation["correlation_id"], receipt["correlation_id"])
        self.assertEqual(
            operation["result"]["receipt"]["evaluation_result_id"],
            receipt["evaluation_result_id"],
        )
        self.assertEqual(approval_event["event_type"], "agent.proposal_approved")
        self.assertEqual(
            payload["events"][1]["event_type"],
            "evaluation.agent_action_approved",
        )
        self.assertIn("server execution", payload["events"][1]["summary"])
        self.assertEqual(
            operation["input"]["approval"]["event_id"], approval_event["id"]
        )
        self.assertNotEqual(approval_event["id"], proposal["id"])
        self.assertNotIn("workflow_action", payload["client_effects"])
        self.assertTrue(pathlib.Path(workflow_action["report_path"]).exists())

        approval_retry = self.client.post(
            f"/api/workflows/{self.workflow_id}/agent-actions/"
            f"{proposal['id']}/approve"
        )
        self.assertEqual(approval_retry.status_code, 200, approval_retry.text)
        self.assertEqual(approval_retry.json()["operation"]["id"], operation["id"])
        self.assertEqual(approval_retry.json()["receipt"], receipt)
        self.assertNotIn("workflow_action", approval_retry.json()["client_effects"])

        stage_url = f"/api/workflows/{self.workflow_id}/action-operations"
        duplicate_stage = self.client.post(stage_url, json=operation["input"])
        self.assertEqual(duplicate_stage.status_code, 202, duplicate_stage.text)
        self.assertEqual(duplicate_stage.json()["id"], operation["id"])
        tampered_stage = self.client.post(
            stage_url,
            json={
                **operation["input"],
                "baseline_prediction_path": str(self.root / "different-baseline.tif"),
            },
        )
        self.assertEqual(tampered_stage.status_code, 409)
        self.assertIn("parameters do not match", tampered_stage.json()["detail"])

        execute_url = (
            f"/api/workflows/{self.workflow_id}/action-operations/"
            f"{operation['id']}/execute"
        )
        first_retry = self.client.post(execute_url)
        second_retry = self.client.post(execute_url)
        self.assertEqual(first_retry.status_code, 200, first_retry.text)
        self.assertEqual(second_retry.status_code, 200, second_retry.text)
        self.assertEqual(first_retry.json(), receipt)
        self.assertEqual(second_retry.json(), receipt)

        evaluations = self.client.get(
            f"/api/workflows/{self.workflow_id}/evaluation-results"
        )
        self.assertEqual(evaluations.status_code, 200)
        self.assertEqual(len(evaluations.json()), 1)

    def test_pending_or_missing_approval_cannot_stage_evaluation(self):
        workflow_action = self._workflow_action()
        proposal = self._propose(workflow_action)
        stage_url = f"/api/workflows/{self.workflow_id}/action-operations"

        pending = self.client.post(
            stage_url,
            json=self._envelope(proposal["id"], workflow_action, {"status": "pending"}),
        )
        self.assertEqual(pending.status_code, 409)
        self.assertIn("approved", pending.json()["detail"])

        fabricated = self.client.post(
            stage_url,
            json=self._envelope(
                proposal["id"],
                workflow_action,
                {
                    "status": "approved",
                    "event_id": proposal["id"],
                    "decided_by": "user:1",
                },
            ),
        )
        self.assertEqual(fabricated.status_code, 409)
        self.assertIn("persisted and approved", fabricated.json()["detail"])

    def test_handler_failure_is_terminal_correlated_and_idempotent(self):
        workflow_action = self._workflow_action(
            baseline_prediction_path=str(self.root / "missing-baseline.tif"),
            report_path=None,
        )
        proposal = self._propose(
            workflow_action, correlation_id="proposal-correlation-failure"
        )

        approved = self.client.post(
            f"/api/workflows/{self.workflow_id}/agent-actions/"
            f"{proposal['id']}/approve"
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        payload = approved.json()
        receipt = payload["receipt"]
        operation = payload["operation"]

        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["error"]["code"], "evaluation_input_invalid")
        self.assertEqual(receipt["correlation_id"], "proposal-correlation-failure")
        self.assertEqual(operation["status"], "failed")
        self.assertEqual(operation["result"]["receipt"], receipt)
        self.assertEqual(operation["error"]["code"], receipt["error"]["code"])
        self.assertNotIn("workflow_action", payload["client_effects"])

        execute_url = (
            f"/api/workflows/{self.workflow_id}/action-operations/"
            f"{operation['id']}/execute"
        )
        duplicate = self.client.post(execute_url)
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json(), receipt)

        evaluations = self.client.get(
            f"/api/workflows/{self.workflow_id}/evaluation-results"
        )
        self.assertEqual(evaluations.status_code, 200)
        self.assertEqual(evaluations.json(), [])


if __name__ == "__main__":
    unittest.main()
