import unittest

from server_api.workflow.proposals import (
    PRIORITIZE_FAILURE_HOTSPOTS,
    propose_failure_hotspots,
)


class WorkflowHotspotProposalTests(unittest.TestCase):
    def test_generates_ranked_candidates_and_reasons(self):
        events = [
            {"event_type": "proofreading_error_marked", "region_id": "r-1"},
            {"event_type": "inference_failure_detected", "region_id": "r-1"},
            {
                "event_type": "proofreading_reject",
                "region_id": "r-2",
                "severity": "high",
            },
            {
                "event_type": "inference_error",
                "region_id": "r-2",
                "requires_rework": True,
            },
        ]

        proposal = propose_failure_hotspots(events, top_k=2)

        self.assertEqual(proposal["proposal_type"], PRIORITIZE_FAILURE_HOTSPOTS)
        self.assertTrue(proposal["requires_approval"])
        self.assertFalse(proposal["mutates_state"])

        candidates = proposal["explanation"]["candidates"]
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["item"], "region_id:r-2")
        self.assertIn("failure-linked events", candidates[0]["reason"])

    def test_fallback_with_limited_events(self):
        events = [{"event_type": "proofreading_viewed", "region_id": "r-1"}]

        proposal = propose_failure_hotspots(events)

        explanation = proposal["explanation"]
        self.assertEqual(explanation["candidates"], [])
        self.assertIn("fallback_recommendation", explanation)
        self.assertIn("Insufficient failure-linked events", explanation["summary"])

    def test_handles_empty_event_stream_without_mutation(self):
        events = []

        proposal = propose_failure_hotspots(events)

        self.assertEqual(proposal["proposal_type"], PRIORITIZE_FAILURE_HOTSPOTS)
        self.assertFalse(proposal["mutates_state"])
        self.assertTrue(proposal["requires_approval"])


if __name__ == "__main__":
    unittest.main()
