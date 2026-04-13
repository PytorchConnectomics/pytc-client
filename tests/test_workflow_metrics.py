from fastapi import FastAPI
from fastapi.testclient import TestClient

from server_api.workflow.router import router, seed_workflow_events


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_workflow_metrics_empty_events_returns_safe_defaults():
    workflow_id = "wf-empty"
    seed_workflow_events(workflow_id, [])

    response = client.get(f"/api/workflows/{workflow_id}/metrics")

    assert response.status_code == 200
    payload = response.json()
    metrics = payload["metrics"]

    assert payload["workflow_id"] == workflow_id
    assert metrics["event_counts"] == {}
    assert metrics["decision_metrics"] == {
        "approvals": 0,
        "rejections": 0,
        "approval_rate": 0.0,
        "rejection_rate": 0.0,
        "total_decisions": 0,
    }
    assert metrics["stage_transition_counts"] == {}
    assert metrics["timestamps"] == {"first_event_at": None, "last_event_at": None}
    assert metrics["total_events"] == 0


def test_workflow_metrics_matches_seeded_event_analytics():
    workflow_id = "wf-123"
    seed_workflow_events(
        workflow_id,
        [
            {
                "type": "stage_transition",
                "from_stage": "draft",
                "to_stage": "review",
                "timestamp": "2026-04-13T10:00:00Z",
            },
            {
                "type": "approval",
                "action": "approve",
                "outcome": "approved",
                "timestamp": "2026-04-13T10:05:00Z",
            },
            {
                "type": "stage_transition",
                "from_stage": "review",
                "to_stage": "done",
                "timestamp": "2026-04-13T10:10:00Z",
            },
            {
                "type": "rejection",
                "action": "reject",
                "outcome": "rejected",
                "timestamp": "2026-04-13T10:15:00Z",
            },
            {
                "type": "agent_action",
                "action": "annotate",
                "timestamp": "2026-04-13T10:20:00Z",
            },
        ],
    )

    response = client.get(f"/api/workflows/{workflow_id}/metrics")

    assert response.status_code == 200
    payload = response.json()
    metrics = payload["metrics"]

    assert payload["workflow_id"] == workflow_id
    assert metrics["event_counts"] == {
        "stage_transition": 2,
        "approval": 1,
        "rejection": 1,
        "agent_action": 1,
    }
    assert metrics["decision_metrics"] == {
        "approvals": 1,
        "rejections": 1,
        "approval_rate": 0.5,
        "rejection_rate": 0.5,
        "total_decisions": 2,
    }
    assert metrics["stage_transition_counts"] == {
        "draft->review": 1,
        "review->done": 1,
    }
    assert metrics["timestamps"] == {
        "first_event_at": "2026-04-13T10:00:00Z",
        "last_event_at": "2026-04-13T10:20:00Z",
    }
    assert metrics["total_events"] == 5


def test_workflow_metrics_endpoint_uses_stable_schema_for_missing_workflow():
    response = client.get("/api/workflows/does-not-exist/metrics")

    assert response.status_code == 200
    payload = response.json()

    assert payload.keys() == {"workflow_id", "metrics"}
    assert payload["metrics"].keys() == {
        "event_counts",
        "decision_metrics",
        "stage_transition_counts",
        "timestamps",
        "total_events",
    }
