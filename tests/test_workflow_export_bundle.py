import pathlib
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import importlib

workflow_router_module = importlib.import_module("server_api.workflow.router")


class WorkflowExportBundleTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(workflow_router_module.router)
        self.client = TestClient(app)

    def test_export_bundle_happy_path_sorts_events_and_sets_file_flags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = pathlib.Path(tmpdir) / "existing.zarr"
            existing.write_text("ok")
            missing = pathlib.Path(tmpdir) / "missing.zarr"

            record = {
                "session_snapshot": {
                    "id": 7,
                    "name": "proofreading",
                    "primary_artifact_path": str(existing),
                },
                "events": [
                    {
                        "id": "evt-2",
                        "type": "annotation",
                        "timestamp": "2026-04-10T10:00:00+00:00",
                        "payload": {"artifact": {"path": str(missing)}},
                    },
                    {
                        "id": "evt-1",
                        "type": "start",
                        "timestamp": "2026-04-10T09:00:00+00:00",
                        "payload": {},
                    },
                ],
            }

            with patch.object(
                workflow_router_module,
                "get_workflow_export_record",
                return_value=record,
            ):
                response = self.client.post("/api/workflows/7/export-bundle")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["schema_version"], "workflow-export-bundle/v1")
        self.assertEqual(data["workflow_id"], 7)
        self.assertEqual([e["id"] for e in data["events"]], ["evt-1", "evt-2"])

        artifacts = {item["path"]: item["exists"] for item in data["artifact_paths"]}
        self.assertTrue(artifacts[str(existing)])
        self.assertFalse(artifacts[str(missing)])

    def test_export_bundle_uses_explicit_artifact_paths_and_missing_is_safe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = pathlib.Path(tmpdir) / "proofread.tif"
            existing.write_text("ok")
            missing = pathlib.Path(tmpdir) / "not_here.tif"

            record = {
                "session_snapshot": {"id": 10, "name": "workflow"},
                "events": [],
                "artifact_paths": [str(missing), str(existing)],
            }

            with patch.object(
                workflow_router_module,
                "get_workflow_export_record",
                return_value=record,
            ):
                response = self.client.post("/api/workflows/10/export-bundle")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([e for e in data["events"]], [])

        self.assertEqual(
            [entry["path"] for entry in data["artifact_paths"]],
            sorted([str(existing), str(missing)]),
        )
        exists_flags = {entry["path"]: entry["exists"] for entry in data["artifact_paths"]}
        self.assertTrue(exists_flags[str(existing)])
        self.assertFalse(exists_flags[str(missing)])


if __name__ == "__main__":
    unittest.main()
