import pathlib
import tempfile
import unittest

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from server_api.auth import database as auth_database
from server_api.auth import models
import server_api.main as server_api_main
from server_api.main import app as server_api_app


class WorkflowSpineSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "workflow-spine-smoke.db"
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

    def test_chatbot_backend_import_contract_is_available(self):
        self.assertIsNotNone(server_api_main.build_chain)

    def test_spine_loop_load_proofread_stage_and_export_evidence(self):
        workflow_response = self.client.get("/api/workflows/current")
        self.assertEqual(workflow_response.status_code, 200)
        workflow = workflow_response.json()["workflow"]
        workflow_id = workflow["id"]

        export_path = pathlib.Path(self.temp_dir.name) / "corrected-mask.tif"
        export_path.write_text("mask", encoding="utf-8")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "mito25-paper-loop-smoke",
                "stage": "proofreading",
                "image_path": "/projects/mito25/data/image/mito25_im.h5",
                "corrected_mask_path": str(export_path),
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "proofreading.masks_exported",
                "stage": "proofreading",
                "summary": "Corrected masks exported.",
                "payload": {"written_path": str(export_path), "region_id": "z:12"},
            },
        )

        query_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "stage corrected masks for retraining"},
        )
        self.assertEqual(query_response.status_code, 200)
        query_payload = query_response.json()
        proposals = query_payload["proposals"]
        self.assertEqual(len(proposals), 1)
        self.assertGreaterEqual(len(query_payload["actions"]), 1)
        self.assertGreaterEqual(len(query_payload["commands"]), 1)
        self.assertEqual(
            query_payload["actions"][0]["client_effects"]["navigate_to"],
            "training",
        )
        proposal_id = proposals[0]["id"]

        approve_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions/{proposal_id}/approve"
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(
            approve_response.json()["workflow"]["stage"], "retraining_staged"
        )

        launch_query_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "start training"},
        )
        self.assertEqual(launch_query_response.status_code, 200)
        launch_query_payload = launch_query_response.json()
        self.assertEqual(
            launch_query_payload["commands"][0]["client_effects"]["runtime_action"][
                "kind"
            ],
            "start_training",
        )
        training_effects = launch_query_payload["commands"][0]["client_effects"]
        self.assertEqual(
            training_effects["set_training_config_preset"],
            "configs/MitoEM/Mito25-Local-Smoke-BC.yaml",
        )
        self.assertEqual(
            training_effects["set_training_image_path"],
            "/projects/mito25/data/image/mito25_im.h5",
        )
        self.assertTrue(
            training_effects["runtime_action"]["autopick_parameters"],
        )
        self.assertEqual(
            launch_query_payload["commands"][0]["client_effects"]["navigate_to"],
            "training",
        )

        hotspots_response = self.client.get(f"/api/workflows/{workflow_id}/hotspots")
        impact_response = self.client.get(
            f"/api/workflows/{workflow_id}/impact-preview"
        )
        metrics_response = self.client.get(f"/api/workflows/{workflow_id}/metrics")
        bundle_response = self.client.post(
            f"/api/workflows/{workflow_id}/export-bundle"
        )

        self.assertEqual(hotspots_response.status_code, 200)
        self.assertEqual(impact_response.status_code, 200)
        self.assertEqual(metrics_response.status_code, 200)
        self.assertEqual(bundle_response.status_code, 200)
        self.assertEqual(
            bundle_response.json()["schema_version"], "workflow-export-bundle/v1"
        )


if __name__ == "__main__":
    unittest.main()
