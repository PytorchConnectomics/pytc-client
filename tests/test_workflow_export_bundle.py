import json
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
        agent_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "what should I do next?"},
        )
        self.assertEqual(agent_response.status_code, 200)

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
        self.assertEqual(
            payload["project_memory"]["schema_version"],
            "pytc-project-memory/v1",
        )
        self.assertEqual(
            payload["project_memory_summary"]["schema_version"],
            "pytc-project-memory-summary/v1",
        )
        self.assertEqual(
            payload["project_memory_summary"]["workflow_id"],
            workflow_id,
        )
        self.assertEqual(payload["project_memory"]["workflow_id"], workflow_id)
        self.assertTrue(payload["agent_messages"])
        self.assertTrue(payload["trace_index"])
        self.assertTrue(
            all(entry.get("category") for entry in payload["trace_index"])
        )
        self.assertIn("action_card_index", payload)
        self.assertGreaterEqual(len(payload["events"]), 2)  # includes workflow.created

        artifacts = {entry["path"]: entry["exists"] for entry in payload["artifact_paths"]}
        self.assertIn(str(existing_path), artifacts)
        self.assertIn(str(missing_path), artifacts)
        self.assertTrue(artifacts[str(existing_path)])
        self.assertFalse(artifacts[str(missing_path)])
        missing_skipped = {
            entry["path"]: entry for entry in payload["skipped_artifacts"]
            if entry.get("path")
        }
        self.assertEqual(
            missing_skipped[str(missing_path)]["copy_mode"],
            "missing",
        )
        self.assertEqual(
            missing_skipped[str(missing_path)]["copy_policy"]["allow_copy"],
            False,
        )
        manifest_path = pathlib.Path(payload["bundle_manifest_path"])
        self.assertTrue(manifest_path.exists())
        self.assertEqual(manifest_path.name, "workflow-bundle.json")
        self.assertTrue((manifest_path.parent / "README.md").exists())
        self.assertTrue((manifest_path.parent / "artifact-paths.json").exists())
        persisted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            persisted_manifest["project_memory"]["schema_version"],
            "pytc-project-memory/v1",
        )
        self.assertEqual(
            persisted_manifest["project_memory_summary"]["schema_version"],
            "pytc-project-memory-summary/v1",
        )
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

    def test_export_bundle_raw_copy_limits_and_manifest_only_mode(self):
        workflow_id = self._current_workflow_id()
        raw_image_path = pathlib.Path(self.temp_dir.name) / "data" / "raw" / "image-raw.tif"
        raw_image_path.parent.mkdir(parents=True, exist_ok=True)
        raw_image_path.write_bytes(b"x" * 64)

        config_path = pathlib.Path(self.temp_dir.name) / "configs" / "small-config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("a: 1", encoding="utf-8")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "image_path": str(raw_image_path),
                "config_path": str(config_path),
                "stage": "proofreading",
            },
        )

        bundle_root = pathlib.Path(self.temp_dir.name) / "bundles"
        with patch.dict(
            "os.environ",
            {
                "PYTC_WORKFLOW_BUNDLE_DIR": str(bundle_root),
                "PYTC_WORKFLOW_BUNDLE_RAW_COPY_MAX_BYTES": "0",
            },
        ):
            default_response = self.client.post(
                f"/api/workflows/{workflow_id}/export-bundle",
                params={"copy_max_bytes": 5},
            )
            manifest_response = self.client.post(
                f"/api/workflows/{workflow_id}/export-bundle",
                params={"copy_manifest_only": "true"},
            )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(manifest_response.status_code, 200)

        default_payload = default_response.json()
        skipped_default = {
            entry["path"]: entry for entry in default_payload["skipped_artifacts"]
        }
        copied_default = {
            entry["path"]: entry for entry in default_payload["copied_artifacts"]
        }
        self.assertIn(str(raw_image_path), skipped_default)
        self.assertIn(str(config_path), copied_default)
        self.assertIn(
            skipped_default[str(raw_image_path)]["reason"],
            {"raw_larger_than_copy_limit", "larger_than_copy_limit"},
        )
        self.assertEqual(
            skipped_default[str(raw_image_path)]["copy_mode"],
            "size_limit",
        )
        self.assertIsNotNone(skipped_default[str(raw_image_path)]["copy_policy"])
        self.assertFalse(default_payload["copy_settings"]["copy_manifest_only"])

        manifest_payload = manifest_response.json()
        skipped_manifest = {
            entry["path"]: entry for entry in manifest_payload["skipped_artifacts"]
        }
        self.assertTrue(manifest_payload["copy_settings"]["copy_manifest_only"])
        self.assertEqual(manifest_payload["copied_artifacts"], [])
        self.assertIn(str(raw_image_path), skipped_manifest)
        self.assertIn(str(config_path), skipped_manifest)
        self.assertEqual(skipped_manifest[str(raw_image_path)]["reason"], "manifest_only")
        self.assertEqual(skipped_manifest[str(config_path)]["reason"], "manifest_only")
        self.assertEqual(skipped_manifest[str(raw_image_path)]["copy_mode"], "manifest_only")
        self.assertEqual(skipped_manifest[str(config_path)]["copy_mode"], "manifest_only")

    def test_export_bundle_tracks_holdout_reference_only_artifacts(self):
        workflow_id = self._current_workflow_id()
        dataset_root = pathlib.Path(self.temp_dir.name) / "project"
        holdout_root = pathlib.Path(self.temp_dir.name) / "holdout"
        dataset_root.mkdir()
        holdout_root.mkdir()
        image_path = dataset_root / "image.tif"
        image_path.write_text("image", encoding="utf-8")
        holdout_gt = holdout_root / "6_1-mask.tif"
        holdout_gt.write_text("ground-truth", encoding="utf-8")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "dataset_path": str(dataset_root),
                "image_path": str(image_path),
                "stage": "visualization",
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "dataset.loaded",
                "stage": "visualization",
                "summary": "Loaded image with external holdout mask.",
                "payload": {
                    "image_path": str(image_path),
                    "withheld_ground_truth": str(holdout_gt),
                },
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

        artifact_paths = {
            entry["path"]: entry
            for entry in payload["artifact_paths"]
            if entry.get("path")
        }
        self.assertIn(str(holdout_gt), artifact_paths)
        holdout_entry = artifact_paths[str(holdout_gt)]
        self.assertFalse(holdout_entry["copy_policy"]["allow_copy"])
        self.assertEqual(holdout_entry["copy_policy"]["reason"], "withheld_reference")
        self.assertTrue(
            any(source.get("source_key") == "withheld_ground_truth" for source in holdout_entry.get("sources", []))
        )
        self.assertIn(str(holdout_gt), [entry["path"] for entry in payload["skipped_artifacts"]])
        skipped = {
            entry["path"]: entry for entry in payload["skipped_artifacts"]
            if entry.get("path")
        }
        self.assertEqual(
            skipped[str(holdout_gt)]["reason"],
            "reference_only_policy",
        )
        self.assertEqual(
            skipped[str(holdout_gt)]["copy_mode"],
            "policy",
        )
        self.assertFalse(skipped[str(holdout_gt)]["copy_policy"]["allow_copy"])
        self.assertEqual(
            skipped[str(holdout_gt)]["copy_policy"]["reason"],
            "withheld_reference",
        )
        copied_paths = {entry["path"] for entry in payload["copied_artifacts"]}
        self.assertNotIn(str(holdout_gt), copied_paths)


if __name__ == "__main__":
    unittest.main()
