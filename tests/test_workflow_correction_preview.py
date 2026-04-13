import unittest

from server_api.workflow.proposals import (
    HIGH_CORRECTION_THRESHOLD,
    LOW_CORRECTION_THRESHOLD,
    PROPOSAL_TYPE_PREVIEW_CORRECTION_IMPACT,
    build_preview_correction_impact_proposal,
)


class CorrectionImpactPreviewTests(unittest.TestCase):
    def test_low_correction_scenario_recommends_proceed(self):
        events = [
            {"type": "correction_saved", "timestamp": "2026-04-13T12:00:00Z"},
            {"type": "mask_edited", "timestamp": "2026-04-13T12:05:00Z"},
            {
                "type": "export_masks",
                "timestamp": "2026-04-13T12:10:00Z",
                "target": "session_a",
            },
        ]

        proposal = build_preview_correction_impact_proposal(events)

        self.assertEqual(proposal["type"], PROPOSAL_TYPE_PREVIEW_CORRECTION_IMPACT)
        self.assertEqual(proposal["recommendation"], "proceed")
        self.assertIn(str(LOW_CORRECTION_THRESHOLD), proposal["rationale"])
        self.assertEqual(proposal["summary"]["total_correction_events"], 2)
        self.assertEqual(len(proposal["summary"]["recent_exports"]), 1)

    def test_high_correction_scenario_recommends_continue_proofreading(self):
        events = [
            {"type": "correction_saved", "timestamp": f"2026-04-13T12:{index:02d}:00Z"}
            for index in range(HIGH_CORRECTION_THRESHOLD + 2)
        ] + [
            {
                "type": "export_completed",
                "timestamp": "2026-04-13T13:00:00Z",
                "target": "session_b",
            }
        ]

        original_events_snapshot = [dict(event) for event in events]
        proposal = build_preview_correction_impact_proposal(events)

        self.assertEqual(proposal["type"], PROPOSAL_TYPE_PREVIEW_CORRECTION_IMPACT)
        self.assertEqual(proposal["recommendation"], "continue_proofreading")
        self.assertIn(str(HIGH_CORRECTION_THRESHOLD), proposal["rationale"])
        self.assertEqual(
            proposal["summary"]["total_correction_events"],
            HIGH_CORRECTION_THRESHOLD + 2,
        )
        self.assertEqual(events, original_events_snapshot)


if __name__ == "__main__":
    unittest.main()
