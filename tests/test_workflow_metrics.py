import unittest

from fastapi.testclient import TestClient

from fastapi import FastAPI
from server_api.workflow.router import router as workflow_router


class WorkflowMetricsEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(workflow_router)
        self.client = TestClient(self.app)
        self.app.state.workflow_events_store = {}

    def test_endpoint_exists_and_returns_stable_schema(self):
        response = self.client.get('/api/workflows/wf-1/metrics')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['workflow_id'], 'wf-1')
        self.assertIn('metrics', payload)

        metrics = payload['metrics']
        self.assertEqual(
            set(metrics.keys()),
            {
                'event_counts_by_type',
                'approvals',
                'rejections',
                'stage_transitions',
                'first_event_timestamp',
                'last_event_timestamp',
                'total_events',
            },
        )

    def test_empty_workflow_events_use_safe_defaults(self):
        self.app.state.workflow_events_store = {'empty': []}

        response = self.client.get('/api/workflows/empty/metrics')
        self.assertEqual(response.status_code, 200)

        metrics = response.json()['metrics']
        self.assertEqual(metrics['event_counts_by_type'], {})
        self.assertEqual(metrics['approvals'], {'count': 0, 'rate': 0.0})
        self.assertEqual(metrics['rejections'], {'count': 0, 'rate': 0.0})
        self.assertEqual(metrics['stage_transitions'], {})
        self.assertIsNone(metrics['first_event_timestamp'])
        self.assertIsNone(metrics['last_event_timestamp'])
        self.assertEqual(metrics['total_events'], 0)

    def test_metrics_align_with_seeded_events(self):
        self.app.state.workflow_events_store = {
            'wf-seeded': [
                {
                    'type': 'stage_transition',
                    'from_stage': 'draft',
                    'to_stage': 'review',
                    'timestamp': '2026-01-01T00:00:00Z',
                },
                {
                    'type': 'agent_action',
                    'outcome': 'approved',
                    'timestamp': '2026-01-01T00:02:00Z',
                },
                {
                    'type': 'agent_action',
                    'outcome': 'rejected',
                    'timestamp': '2026-01-01T00:03:00Z',
                },
                {
                    'type': 'stage_transition',
                    'from_stage': 'review',
                    'to_stage': 'approved',
                    'timestamp': '2026-01-01T00:04:00Z',
                },
                {
                    'type': 'stage_transition',
                    'from_stage': 'draft',
                    'to_stage': 'review',
                    'timestamp': '2026-01-01T00:05:00Z',
                },
            ]
        }

        response = self.client.get('/api/workflows/wf-seeded/metrics')
        self.assertEqual(response.status_code, 200)
        metrics = response.json()['metrics']

        self.assertEqual(metrics['event_counts_by_type'], {'agent_action': 2, 'stage_transition': 3})
        self.assertEqual(metrics['approvals'], {'count': 1, 'rate': 0.5})
        self.assertEqual(metrics['rejections'], {'count': 1, 'rate': 0.5})
        self.assertEqual(
            metrics['stage_transitions'],
            {'draft->review': 2, 'review->approved': 1},
        )
        self.assertEqual(metrics['first_event_timestamp'], '2026-01-01T00:00:00Z')
        self.assertEqual(metrics['last_event_timestamp'], '2026-01-01T00:05:00Z')
        self.assertEqual(metrics['total_events'], 5)


if __name__ == '__main__':
    unittest.main()
