import json
import tempfile
import unittest
from pathlib import Path

from server_api.workflow.evidence_export import (
    EVIDENCE_EXPORT_VERSION,
    build_workflow_evidence_export,
    export_workflow_evidence,
)


class WorkflowEvidenceExportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.fixture_path = self.temp_path / "seeded-workflow.json"
        self.output_path = self.temp_path / "exports" / "workflow-evidence.json"

        fixture = {
            "workflow_id": "wf-seeded-001",
            "stages": ["intake", "analysis", "draft", "review"],
            "events": [
                {
                    "timestamp": "2026-03-01T10:00:00Z",
                    "type": "stage_entered",
                    "stage": "intake",
                    "agent": "orchestrator",
                },
                {
                    "timestamp": "2026-03-01T10:02:00Z",
                    "type": "proposal_submitted",
                    "stage": "analysis",
                    "proposal_id": "p-1",
                    "agent": "agent-alpha",
                },
                {
                    "timestamp": "2026-03-01T10:03:00Z",
                    "type": "proposal_approved",
                    "stage": "analysis",
                    "proposal_id": "p-1",
                    "agent": "reviewer-1",
                    "status": "approved",
                },
                {
                    "timestamp": "2026-03-01T10:05:00Z",
                    "type": "stage_changed",
                    "stage": "analysis",
                    "agent": "orchestrator",
                },
                {
                    "timestamp": "2026-03-01T10:08:00Z",
                    "type": "proposal_submitted",
                    "stage": "draft",
                    "proposal_id": "p-2",
                    "agent": "agent-beta",
                },
                {
                    "timestamp": "2026-03-01T10:09:00Z",
                    "type": "proposal_rejected",
                    "stage": "draft",
                    "proposal_id": "p-2",
                    "agent": "reviewer-2",
                    "status": "rejected",
                },
            ],
        }
        self.fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_export_contains_required_sections(self):
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        evidence = build_workflow_evidence_export(payload)

        self.assertEqual(evidence["version"], EVIDENCE_EXPORT_VERSION)
        self.assertIn("stage_progression_summary", evidence)
        self.assertIn("agent_proposal_approval_summary", evidence)
        self.assertIn("key_event_timeline_snippet", evidence)

        stage_summary = evidence["stage_progression_summary"]
        self.assertEqual(stage_summary["completed_stages"], ["intake", "analysis"])
        self.assertIn("draft", stage_summary["pending_stages"])

        proposal_summary = evidence["agent_proposal_approval_summary"]
        self.assertEqual(proposal_summary["proposal_count"], 2)
        self.assertEqual(proposal_summary["approved_count"], 1)
        self.assertEqual(proposal_summary["rejected_count"], 1)

        timeline = evidence["key_event_timeline_snippet"]
        self.assertGreaterEqual(len(timeline), 3)
        self.assertIn("event_type", timeline[0])

    def test_export_writes_output_file_for_seeded_fixture(self):
        result_path = export_workflow_evidence(self.fixture_path, self.output_path)
        self.assertEqual(result_path, self.output_path)
        self.assertTrue(self.output_path.exists())

        written = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(written["workflow_id"], "wf-seeded-001")
        self.assertEqual(written["version"], EVIDENCE_EXPORT_VERSION)


if __name__ == "__main__":
    unittest.main()
