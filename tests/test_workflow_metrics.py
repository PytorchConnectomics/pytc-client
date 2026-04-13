import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server_api.workflow.metrics import router as workflow_metrics_router


class WorkflowMetricsRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(workflow_metrics_router)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.state.workflow_events = {}

    def test_metrics_endpoint_returns_safe_defaults_for_empty_workflow(self):
        self.app.state.workflow_events = {"wf-empty": []}

        response = self.client.get("/api/workflows/wf-empty/metrics")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow_id"], "wf-empty")
        self.assertEqual(payload["event_total"], 0)

        metrics = payload["metrics"]
        self.assertEqual(metrics["event_counts"], {})
        self.assertEqual(metrics["stage_transitions"], {})
        self.assertEqual(
            metrics["approvals"],
            {
                "count": 0,
                "rejections": 0,
                "total": 0,
                "approval_rate": 0.0,
                "rejection_rate": 0.0,
            },
        )
        self.assertIsNone(metrics["timeline"]["first_event_at"])
        self.assertIsNone(metrics["timeline"]["last_event_at"])

    def test_metrics_endpoint_matches_seeded_events(self):
        self.app.state.workflow_events = {
            "wf-123": [
                {
                    "type": "stage_transition",
                    "from_stage": "draft",
                    "to_stage": "review",
                    "timestamp": "2026-04-10T10:00:00Z",
                },
                {
                    "type": "agent_action",
                    "timestamp": "2026-04-10T10:05:00Z",
                },
                {
                    "type": "approval",
                    "decision": "approved",
                    "timestamp": "2026-04-10T10:06:00Z",
                },
                {
                    "type": "approval",
                    "decision": "rejected",
                    "timestamp": "2026-04-10T10:07:00Z",
                },
                {
                    "type": "stage_transition",
                    "from_stage": "review",
                    "to_stage": "done",
                    "timestamp": "2026-04-10T10:08:00Z",
                },
            ]
        }

        response = self.client.get("/api/workflows/wf-123/metrics")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow_id"], "wf-123")
        self.assertEqual(payload["event_total"], 5)

        metrics = payload["metrics"]
        self.assertEqual(
            metrics["event_counts"],
            {
                "agent_action": 1,
                "approval": 2,
                "stage_transition": 2,
            },
        )
        self.assertEqual(
            metrics["stage_transitions"],
            {
                "draft->review": 1,
                "review->done": 1,
            },
        )
        self.assertEqual(metrics["approvals"]["count"], 1)
        self.assertEqual(metrics["approvals"]["rejections"], 1)
        self.assertEqual(metrics["approvals"]["total"], 2)
        self.assertEqual(metrics["approvals"]["approval_rate"], 0.5)
        self.assertEqual(metrics["approvals"]["rejection_rate"], 0.5)

        self.assertEqual(metrics["timeline"]["first_event_at"], "2026-04-10T10:00:00+00:00")
        self.assertEqual(metrics["timeline"]["last_event_at"], "2026-04-10T10:08:00+00:00")


if __name__ == "__main__":
    unittest.main()
