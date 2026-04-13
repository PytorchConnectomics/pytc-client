import pathlib
import tempfile
import unittest

import numpy as np
import tifffile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database as auth_database
from server_api.auth import models
import server_api.ehtool.router as ehtool_router_module
from server_api.ehtool.utils import array_to_base64
from server_api.main import app as server_api_app


class WorkflowRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "workflow-test.db"
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
        ehtool_router_module._data_managers.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _current_workflow(self):
        response = self.client.get("/api/workflows/current")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return payload["workflow"], payload["events"]

    def test_current_workflow_create_update_and_events(self):
        workflow, events = self._current_workflow()

        self.assertEqual(workflow["stage"], "setup")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "workflow.created")

        second_workflow, second_events = self._current_workflow()
        self.assertEqual(second_workflow["id"], workflow["id"])
        self.assertEqual(len(second_events), 1)

        patch_response = self.client.patch(
            f"/api/workflows/{workflow['id']}",
            json={"stage": "visualization", "image_path": "/tmp/image.tif"},
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["stage"], "visualization")

        event_response = self.client.post(
            f"/api/workflows/{workflow['id']}/events",
            json={
                "actor": "user",
                "event_type": "dataset.loaded",
                "stage": "visualization",
                "summary": "Loaded a test dataset.",
                "payload": {"image_path": "/tmp/image.tif"},
            },
        )
        self.assertEqual(event_response.status_code, 200)

        events_response = self.client.get(f"/api/workflows/{workflow['id']}/events")
        self.assertEqual(events_response.status_code, 200)
        event_types = [event["event_type"] for event in events_response.json()]
        self.assertEqual(event_types, ["workflow.created", "dataset.loaded"])

    def test_agent_action_approve_and_reject_flow(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]

        reject_proposal = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions",
            json={
                "action": "stage_retraining_from_corrections",
                "summary": "Rejectable staging proposal.",
                "payload": {"corrected_mask_path": "/tmp/rejected.tif"},
            },
        )
        self.assertEqual(reject_proposal.status_code, 200)
        self.assertEqual(reject_proposal.json()["approval_status"], "pending")

        reject_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions/"
            f"{reject_proposal.json()['id']}/reject"
        )
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.json()["event_type"], "agent.proposal_rejected")

        approve_proposal = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions",
            json={
                "action": "stage_retraining_from_corrections",
                "summary": "Stage corrected masks.",
                "payload": {"corrected_mask_path": "/tmp/corrected.tif"},
            },
        )
        self.assertEqual(approve_proposal.status_code, 200)

        approve_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions/"
            f"{approve_proposal.json()['id']}/approve"
        )
        self.assertEqual(approve_response.status_code, 200)
        approve_payload = approve_response.json()
        self.assertEqual(approve_payload["workflow"]["stage"], "retraining_staged")
        self.assertEqual(
            approve_payload["workflow"]["corrected_mask_path"], "/tmp/corrected.tif"
        )
        self.assertEqual(
            approve_payload["client_effects"]["set_training_label_path"],
            "/tmp/corrected.tif",
        )

        events_response = self.client.get(f"/api/workflows/{workflow_id}/events")
        event_types = [event["event_type"] for event in events_response.json()]
        self.assertIn("agent.proposal_approved", event_types)
        self.assertIn("agent.proposal_rejected", event_types)
        self.assertIn("retraining.staged", event_types)

    def test_ehtool_load_classify_save_and_export_append_workflow_events(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        data_root = pathlib.Path(self.temp_dir.name) / "volumes"
        data_root.mkdir()
        image_path = data_root / "image.tif"
        mask_path = data_root / "mask.tif"
        export_path = data_root / "corrected-mask.tif"

        image = np.arange(2 * 6 * 6, dtype=np.uint8).reshape(2, 6, 6)
        mask = np.zeros((2, 6, 6), dtype=np.uint16)
        mask[0, 0:2, 0:2] = 1
        mask[0, 2:4, 2:4] = 2
        mask[1, 4:6, 4:6] = 3
        tifffile.imwrite(str(image_path), image)
        tifffile.imwrite(str(mask_path), mask)

        load_response = self.client.post(
            "/eh/detection/load",
            json={
                "dataset_path": str(image_path),
                "mask_path": str(mask_path),
                "project_name": "Workflow EHTool",
                "workflow_id": workflow_id,
            },
        )
        self.assertEqual(load_response.status_code, 200)
        session_id = load_response.json()["session_id"]

        workflow_response = self.client.get("/api/workflows/current")
        updated_workflow = workflow_response.json()["workflow"]
        self.assertEqual(updated_workflow["stage"], "proofreading")
        self.assertEqual(updated_workflow["proofreading_session_id"], session_id)

        instances_response = self.client.get(
            "/eh/detection/instances", params={"session_id": session_id}
        )
        self.assertEqual(instances_response.status_code, 200)
        instance_id = instances_response.json()["instances"][0]["id"]

        classify_response = self.client.post(
            "/eh/detection/instance-classify",
            json={
                "session_id": session_id,
                "instance_ids": [instance_id],
                "classification": "correct",
            },
        )
        self.assertEqual(classify_response.status_code, 200)
        self.assertEqual(classify_response.json()["updated_count"], 1)

        edited_mask = np.ones((6, 6), dtype=np.uint8) * 255
        save_response = self.client.post(
            "/eh/detection/instance-mask",
            json={
                "session_id": session_id,
                "instance_id": instance_id,
                "axis": "xy",
                "z_index": 0,
                "mask_base64": array_to_base64(edited_mask, format="PNG"),
            },
        )
        self.assertEqual(save_response.status_code, 200)

        export_response = self.client.post(
            "/eh/detection/export-masks",
            json={
                "session_id": session_id,
                "mode": "new_file",
                "output_path": str(export_path),
                "create_backup": True,
            },
        )
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response.json()["written_path"], str(export_path))

        events_response = self.client.get(f"/api/workflows/{workflow_id}/events")
        self.assertEqual(events_response.status_code, 200)
        event_types = [event["event_type"] for event in events_response.json()]
        self.assertIn("dataset.loaded", event_types)
        self.assertIn("proofreading.session_loaded", event_types)
        self.assertIn("proofreading.instance_classified", event_types)
        self.assertIn("proofreading.mask_saved", event_types)
        self.assertIn("proofreading.masks_exported", event_types)


if __name__ == "__main__":
    unittest.main()
