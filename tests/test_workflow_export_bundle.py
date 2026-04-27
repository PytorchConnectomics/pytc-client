import pathlib
import tempfile
import unittest
from unittest.mock import patch

import pytest
pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from server_api.auth import database as auth_database
from server_api.auth import models
from server_api.main import app as server_api_app


class WorkflowExportBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "workflow-export-test.db"
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

    def tearDown(self):
        server_api_app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _current_workflow_id(self) -> int:
        response = self.client.get("/api/workflows/current")
        self.assertEqual(response.status_code, 200)
        return response.json()["workflow"]["id"]

    def test_export_bundle_sorts_events_and_reports_artifact_existence(self):
        workflow_id = self._current_workflow_id()
        existing_path = pathlib.Path(self.temp_dir.name) / "existing-mask.tif"
        existing_path.write_text("ok", encoding="utf-8")
        missing_path = pathlib.Path(self.temp_dir.name) / "missing-mask.tif"

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "image_path": str(existing_path),
                "corrected_mask_path": str(missing_path),
                "stage": "proofreading",
            },
        )

        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "proofreading.masks_exported",
                "stage": "proofreading",
                "summary": "Masks exported",
                "payload": {"output_path": str(existing_path)},
            },
        )

        bundle_root = pathlib.Path(self.temp_dir.name) / "bundles"
        with patch.dict(
            "os.environ",
            {"PYTC_WORKFLOW_BUNDLE_DIR": str(bundle_root)},
        ):
            response = self.client.post(f"/api/workflows/{workflow_id}/export-bundle")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["schema_version"], "workflow-export-bundle/v1")
        self.assertEqual(payload["workflow_id"], workflow_id)
        self.assertIsInstance(payload["events"], list)
        self.assertGreaterEqual(len(payload["events"]), 2)  # includes workflow.created

        artifacts = {entry["path"]: entry["exists"] for entry in payload["artifact_paths"]}
        self.assertIn(str(existing_path), artifacts)
        self.assertIn(str(missing_path), artifacts)
        self.assertTrue(artifacts[str(existing_path)])
        self.assertFalse(artifacts[str(missing_path)])
        manifest_path = pathlib.Path(payload["bundle_manifest_path"])
        self.assertTrue(manifest_path.exists())
        self.assertEqual(manifest_path.name, "workflow-bundle.json")
        self.assertTrue((manifest_path.parent / "README.md").exists())
        self.assertTrue((manifest_path.parent / "artifact-paths.json").exists())
        copied_paths = {
            pathlib.Path(entry["bundle_path"]).name
            for entry in payload["copied_artifacts"]
        }
        self.assertTrue(any("existing-mask.tif" in name for name in copied_paths))

        events = self.client.get(f"/api/workflows/{workflow_id}/events").json()
        export_event = [
            event
            for event in events
            if event["event_type"] == "workflow.bundle_exported"
        ][-1]
        self.assertEqual(
            export_event["payload"]["bundle_manifest_path"],
            payload["bundle_manifest_path"],
        )


if __name__ == "__main__":
    unittest.main()
