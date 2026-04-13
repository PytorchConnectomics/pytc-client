from fastapi import FastAPI
from fastapi.testclient import TestClient

from server_api.workflow.router import router as workflow_router
from server_api.workflow.models import WorkflowEvent
from server_api.workflow.store import clear_events, set_events


def _build_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(workflow_router)
    return TestClient(app)


def teardown_function(_):
    clear_events()


def test_workflow_metrics_returns_safe_defaults_for_empty_workflow():
    client = _build_test_client()

    response = client.get('/api/workflows/empty-workflow/metrics')

    assert response.status_code == 200
    payload = response.json()

    assert payload == {
        'workflow_id': 'empty-workflow',
        'total_events': 0,
        'event_counts_by_type': {},
        'approvals_count': 0,
        'rejections_count': 0,
        'approvals_rate': 0.0,
        'rejections_rate': 0.0,
        'stage_transition_counts': {},
        'first_event_at': None,
        'last_event_at': None,
    }


def test_workflow_metrics_align_with_seeded_events():
    client = _build_test_client()
    workflow_id = 'wf-123'
    set_events(
        workflow_id,
        [
            WorkflowEvent(type='workflow_started', created_at='2026-01-01T10:00:00Z'),
            WorkflowEvent(
                type='stage_transition',
                from_stage='draft',
                to_stage='review',
                created_at='2026-01-01T10:10:00Z',
            ),
            WorkflowEvent(type='agent_action', action='approved', created_at='2026-01-01T10:20:00Z'),
            WorkflowEvent(type='agent_action', action='rejected', created_at='2026-01-01T10:25:00Z'),
            WorkflowEvent(
                type='stage_transition',
                from_stage='review',
                to_stage='done',
                created_at='2026-01-01T10:30:00Z',
            ),
        ],
    )

    response = client.get(f'/api/workflows/{workflow_id}/metrics')

    assert response.status_code == 200
    payload = response.json()

    assert payload['workflow_id'] == workflow_id
    assert payload['total_events'] == 5
    assert payload['event_counts_by_type'] == {
        'workflow_started': 1,
        'stage_transition': 2,
        'agent_action': 2,
    }
    assert payload['approvals_count'] == 1
    assert payload['rejections_count'] == 1
    assert payload['approvals_rate'] == 0.5
    assert payload['rejections_rate'] == 0.5
    assert payload['stage_transition_counts'] == {
        'draft->review': 1,
        'review->done': 1,
    }
    assert payload['first_event_at'] == '2026-01-01T10:00:00Z'
    assert payload['last_event_at'] == '2026-01-01T10:30:00Z'
