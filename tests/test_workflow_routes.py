import pathlib
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("fastapi")
tifffile = pytest.importorskip("tifffile")
from fastapi.testclient import TestClient

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

    def test_current_workflow_reset_starts_clean_session(self):
        workflow, _ = self._current_workflow()
        patch_response = self.client.patch(
            f"/api/workflows/{workflow['id']}",
            json={
                "stage": "proofreading",
                "image_path": "/tmp/old-image.h5",
                "mask_path": "/tmp/old-mask.h5",
                "metadata": {"session_onboarding": {"goals": "old goal"}},
            },
        )
        self.assertEqual(patch_response.status_code, 200)

        reset_response = self.client.post(
            "/api/workflows/current/reset",
            json={"metadata": {"created_from": "test_reset"}},
        )
        self.assertEqual(reset_response.status_code, 200)
        reset_payload = reset_response.json()
        reset_workflow = reset_payload["workflow"]
        self.assertNotEqual(reset_workflow["id"], workflow["id"])
        self.assertEqual(reset_workflow["stage"], "setup")
        self.assertIsNone(reset_workflow["image_path"])
        self.assertEqual(reset_workflow["metadata"]["created_from"], "test_reset")
        self.assertEqual(reset_payload["events"][0]["event_type"], "workflow.created")

        current_workflow, _ = self._current_workflow()
        self.assertEqual(current_workflow["id"], reset_workflow["id"])

    def test_workflow_preflight_accepts_image_only_project_start(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]

        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "dataset_path": "/tmp/new-project",
                "image_path": "/tmp/new-project/image/sample.ome.tif",
            },
        )
        self.assertEqual(patch_response.status_code, 200)

        response = self.client.get(f"/api/workflows/{workflow_id}/preflight")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["overall_status"], "image_only")
        self.assertIn("checkpoint or mask/label", payload["summary"])

        items = {item["id"]: item for item in payload["items"]}
        self.assertTrue(items["project_setup"]["can_run"])
        self.assertTrue(items["visualization"]["can_run"])
        self.assertFalse(items["inference"]["can_run"])
        self.assertEqual(items["inference"]["missing"], ["checkpoint"])
        self.assertFalse(items["proofreading"]["can_run"])
        self.assertIn("mask, label, or prediction", items["proofreading"]["missing"])

        recommendation_response = self.client.get(
            f"/api/workflows/{workflow_id}/agent/recommendation"
        )
        self.assertEqual(recommendation_response.status_code, 200)
        self.assertEqual(
            recommendation_response.json()["decision"],
            "Add a checkpoint or mask/label.",
        )

        quick_next_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "What should I do next?"},
        )
        self.assertEqual(quick_next_response.status_code, 200)
        quick_next_payload = quick_next_response.json()
        self.assertEqual(quick_next_payload["intent"], "status")
        self.assertIn("Add a checkpoint", quick_next_payload["response"])
        self.assertTrue(quick_next_payload["actions"])

    def test_workflow_preflight_treats_config_as_agent_inferred_detail(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]

        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "image_path": "/tmp/project/raw-volume.h5",
                "label_path": "/tmp/project/labels-volume.h5",
                "mask_path": "/tmp/project/labels-volume.h5",
                "config_path": "/tmp/project/configs/custom.yaml",
            },
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(
            patch_response.json()["config_path"], "/tmp/project/configs/custom.yaml"
        )

        response = self.client.get(f"/api/workflows/{workflow_id}/preflight")
        self.assertEqual(response.status_code, 200)
        items = {item["id"]: item for item in response.json()["items"]}

        self.assertEqual(response.json()["overall_status"], "ready_to_proofread")
        self.assertTrue(items["proofreading"]["can_run"])
        self.assertTrue(items["training"]["can_run"])
        self.assertEqual(items["training"]["missing"], [])
        self.assertIn("inferred defaults", items["training"]["action"])
        self.assertEqual(items["inference"]["missing"], ["checkpoint"])

    def test_agent_training_prefers_confirmed_project_config_path(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "custom-connectomics-project",
                "stage": "retraining_staged",
                "image_path": "/projects/custom/data/raw.h5",
                "corrected_mask_path": "/projects/custom/data/corrected.tif",
                "config_path": "/projects/custom/configs/custom-training.yaml",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "membranes",
                        "optimization_priority": "accuracy",
                    }
                },
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "train the model"},
        )
        self.assertEqual(response.status_code, 200)
        effects = response.json()["commands"][0]["client_effects"]
        self.assertEqual(
            effects["set_training_config_preset"],
            "/projects/custom/configs/custom-training.yaml",
        )

    def test_workflow_preflight_reports_compare_ready_from_two_outputs(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]

        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "image_path": "/tmp/project/raw-volume.h5",
                "label_path": "/tmp/project/reference.h5",
                "checkpoint_path": "/tmp/project/checkpoint.pth.tar",
                "inference_output_path": "/tmp/project/candidate.h5",
            },
        )
        self.assertEqual(patch_response.status_code, 200)
        for name, output_path in [
            ("baseline", "/tmp/project/baseline.h5"),
            ("candidate", "/tmp/project/candidate.h5"),
        ]:
            run_response = self.client.post(
                f"/api/workflows/{workflow_id}/model-runs",
                json={
                    "run_type": "inference",
                    "status": "completed",
                    "name": name,
                    "output_path": output_path,
                },
            )
            self.assertEqual(run_response.status_code, 200)

        response = self.client.get(f"/api/workflows/{workflow_id}/preflight")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        items = {item["id"]: item for item in payload["items"]}
        self.assertEqual(payload["overall_status"], "ready_to_compare")
        self.assertTrue(items["inference"]["can_run"])
        self.assertTrue(items["evaluation"]["can_run"])
        self.assertEqual(items["evaluation"]["missing"], [])

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
        self.assertEqual(
            reject_response.json()["event_type"], "agent.proposal_rejected"
        )

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

    def test_agent_plan_preview_control_and_bundle_export(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]

        plan_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent-plans",
            json={
                "title": "Case-study acceptance loop",
                "goal": "Drive a bounded closed-loop segmentation study.",
            },
        )
        self.assertEqual(plan_response.status_code, 200)
        plan = plan_response.json()
        self.assertEqual(plan["title"], "Case-study acceptance loop")
        self.assertEqual(plan["approval_status"], "pending")
        self.assertGreaterEqual(len(plan["steps"]), 8)
        self.assertEqual(
            plan["graph"]["execution_model"]["mode"],
            "bounded_human_approved_plan_preview",
        )
        self.assertIn(
            plan["graph"]["execution_model"]["langgraph"]["status"],
            {"available_not_executing", "available_compile_failed", "unavailable"},
        )

        approval_step = next(
            step for step in plan["steps"] if step["requires_approval"]
        )
        step_approval = self.client.post(
            f"/api/workflows/{workflow_id}/agent-plans/{plan['id']}/steps/"
            f"{approval_step['id']}/approve"
        )
        self.assertEqual(step_approval.status_code, 200)
        self.assertEqual(step_approval.json()["status"], "approved")

        approve_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent-plans/{plan['id']}/approve"
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["status"], "approved")
        self.assertEqual(approve_response.json()["approval_status"], "approved")

        interrupt_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent-plans/{plan['id']}/interrupt"
        )
        self.assertEqual(interrupt_response.status_code, 200)
        self.assertEqual(interrupt_response.json()["status"], "interrupted")

        resume_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent-plans/{plan['id']}/resume"
        )
        self.assertEqual(resume_response.status_code, 200)
        self.assertEqual(resume_response.json()["status"], "approved")

        readiness_response = self.client.get(
            f"/api/workflows/{workflow_id}/case-study-readiness"
        )
        self.assertEqual(readiness_response.status_code, 200)
        readiness_gates = {
            gate["id"]: gate for gate in readiness_response.json()["gates"]
        }
        self.assertTrue(readiness_gates["agent_plan_preview"]["complete"])
        self.assertTrue(readiness_gates["agent_audit"]["complete"])

        bundle_response = self.client.post(
            f"/api/workflows/{workflow_id}/export-bundle"
        )
        self.assertEqual(bundle_response.status_code, 200)
        self.assertEqual(len(bundle_response.json()["agent_plans"]), 1)

    def test_hotspots_and_impact_preview(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={"stage": "proofreading"},
        )
        self.assertEqual(patch_response.status_code, 200)

        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "inference.failed",
                "stage": "inference",
                "summary": "Inference failed on z:12",
                "payload": {"region_id": "z:12"},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "proofreading.instance_classified",
                "stage": "proofreading",
                "summary": "Classified uncertain instances.",
                "payload": {
                    "region_id": "z:12",
                    "classification": "incorrect",
                    "instance_ids": [101, 202],
                },
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "proofreading.mask_saved",
                "stage": "proofreading",
                "summary": "Saved corrected mask for z:12",
                "payload": {"region_id": "z:12", "instance_id": 101},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "proofreading.masks_exported",
                "stage": "proofreading",
                "summary": "Exported corrected masks.",
                "payload": {"written_path": "/tmp/corrected-z12.tif"},
            },
        )

        hotspot_response = self.client.get(f"/api/workflows/{workflow_id}/hotspots")
        self.assertEqual(hotspot_response.status_code, 200)
        hotspot_payload = hotspot_response.json()
        self.assertEqual(hotspot_payload["workflow_id"], workflow_id)
        self.assertGreaterEqual(len(hotspot_payload["hotspots"]), 1)
        self.assertEqual(hotspot_payload["hotspots"][0]["region_key"], "z:12")
        self.assertIn(
            hotspot_payload["hotspots"][0]["severity"],
            {"low", "medium", "high"},
        )

        impact_response = self.client.get(
            f"/api/workflows/{workflow_id}/impact-preview"
        )
        self.assertEqual(impact_response.status_code, 200)
        impact_payload = impact_response.json()
        self.assertTrue(impact_payload["can_stage_retraining"])
        self.assertEqual(
            impact_payload["corrected_mask_path"], "/tmp/corrected-z12.tif"
        )
        self.assertIn(impact_payload["confidence"], {"low", "medium", "high"})
        self.assertIn("proofreading_mask_saved", impact_payload["signals"])

        recommendation_response = self.client.get(
            f"/api/workflows/{workflow_id}/agent/recommendation"
        )
        self.assertEqual(recommendation_response.status_code, 200)
        recommendation = recommendation_response.json()
        self.assertEqual(recommendation["stage"], "proofreading")
        self.assertIn("training", recommendation["decision"].lower())
        self.assertEqual(
            recommendation["impact_preview"]["corrected_mask_path"],
            "/tmp/corrected-z12.tif",
        )
        action_ids = {action["id"] for action in recommendation["actions"]}
        self.assertIn("propose-retraining-handoff", action_ids)
        readiness = {item["id"]: item for item in recommendation["readiness"]}
        self.assertTrue(readiness["corrections"]["complete"])
        self.assertGreaterEqual(len(recommendation["commands"]), 1)

    def test_agent_can_start_proofreading_from_current_image_mask_pair(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        image_path = "/tmp/mito-image.h5"
        mask_path = "/tmp/mito-seg.h5"
        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "Mito proofread",
                "stage": "visualization",
                "image_path": image_path,
                "mask_path": mask_path,
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                        "optimization_priority": "accuracy",
                    }
                },
            },
        )
        self.assertEqual(patch_response.status_code, 200)

        recommendation_response = self.client.get(
            f"/api/workflows/{workflow_id}/agent/recommendation"
        )
        self.assertEqual(recommendation_response.status_code, 200)
        recommendation = recommendation_response.json()
        primary = next(
            action
            for action in recommendation["actions"]
            if action["variant"] == "primary"
        )
        self.assertEqual(primary["id"], "start-proofreading")
        effects = primary["client_effects"]
        self.assertEqual(effects["navigate_to"], "mask-proofreading")
        self.assertEqual(effects["runtime_action"]["kind"], "start_proofreading")
        self.assertEqual(effects["set_proofreading_dataset_path"], image_path)
        self.assertEqual(effects["set_proofreading_mask_path"], mask_path)
        self.assertEqual(effects["set_proofreading_project_name"], "Mito proofread")

        query_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "proofread this data"},
        )
        self.assertEqual(query_response.status_code, 200)
        query_payload = query_response.json()
        self.assertIn("proofread this data", query_payload["response"].lower())
        self.assertEqual(
            query_payload["commands"][0]["client_effects"]["runtime_action"]["kind"],
            "start_proofreading",
        )

    def test_agent_visualize_request_populates_viewer_paths_not_status(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "image_path": "/projects/sample/data/image/train",
                "label_path": "/projects/sample/data/labels/train",
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={
                "query": "can you visualize some combination of volumes in my data? "
                "i have images and segmentations where the names should already align"
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "view_data")
        self.assertIn("view train", payload["response"].lower())
        self.assertEqual(payload["actions"][0]["id"], "open-visualization")
        self.assertEqual(payload["commands"], [])
        effects = payload["actions"][0]["client_effects"]
        self.assertEqual(effects["navigate_to"], "visualization")
        self.assertEqual(
            effects["set_visualization_image_path"],
            "/projects/sample/data/image/train",
        )
        self.assertEqual(
            effects["set_visualization_label_path"],
            "/projects/sample/data/labels/train",
        )

    def test_agent_visualize_request_discovers_directory_pairs_and_asks_for_more(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        project_root = pathlib.Path(self.temp_dir.name) / "batch-project"
        image_dir = project_root / "Image" / "train"
        label_dir = project_root / "Label" / "train"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        (image_dir / "img_000_604_576.h5").write_bytes(b"")
        (image_dir / "img_508_604_200.h5").write_bytes(b"")
        (label_dir / "seg_508_604_200.h5").write_bytes(b"")
        (label_dir / "seg_000_604_576.h5").write_bytes(b"")
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "image_path": str(image_dir),
                "label_path": str(label_dir),
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "can we visualize my existing segs?"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "view_data")
        self.assertIn("I found 2 clear image/seg pairs", payload["response"])
        self.assertIn("Tell me if there are more folders", payload["response"])
        effects = payload["actions"][0]["client_effects"]
        self.assertEqual(
            effects["set_visualization_image_path"],
            str(image_dir / "img_000_604_576.h5"),
        )
        self.assertEqual(
            effects["set_visualization_label_path"],
            str(label_dir / "seg_000_604_576.h5"),
        )
        self.assertEqual(payload["commands"], [])

    def test_agent_scale_update_persists_project_context_and_offers_reload(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "visualization",
                "image_path": "/projects/sample/data/image/train",
                "label_path": "/projects/sample/data/labels/train",
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "the scales are off; can we reload with 1-1-1?"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "set_visualization_scales")
        self.assertIn("1,1,1 nm", payload["response"])
        self.assertEqual(payload["actions"][0]["id"], "reload-visualization-scales")
        effects = payload["actions"][0]["client_effects"]
        self.assertEqual(effects["navigate_to"], "visualization")
        self.assertEqual(effects["set_visualization_scales"], [1.0, 1.0, 1.0])
        self.assertEqual(effects["runtime_action"]["kind"], "load_visualization")
        self.assertEqual(
            effects["set_visualization_image_path"],
            "/projects/sample/data/image/train",
        )
        self.assertEqual(
            effects["set_visualization_label_path"],
            "/projects/sample/data/labels/train",
        )

        current_workflow, _ = self._current_workflow()
        self.assertEqual(
            current_workflow["metadata"]["visualization_scales"],
            [1.0, 1.0, 1.0],
        )
        self.assertEqual(
            current_workflow["metadata"]["project_context"]["voxel_size_nm"],
            [1.0, 1.0, 1.0],
        )

        events_response = self.client.get(f"/api/workflows/{workflow_id}/events")
        event_types = [event["event_type"] for event in events_response.json()]
        self.assertIn("visualization.scales_updated", event_types)

    def test_agent_scale_update_requires_three_axis_values(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "reload with 1-1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "set_visualization_scales")
        self.assertIn("I need three values", payload["response"])
        self.assertEqual(payload["actions"][0]["id"], "open-visualization")

    def test_agent_proofread_request_from_setup_offers_runnable_action(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "image_path": "/projects/sample/data/image/train",
                "label_path": "/projects/sample/data/labels/train",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                        "optimization_priority": "accuracy",
                    }
                },
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={
                "query": "can you proofread my data? I have images and segmentations"
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_proofreading")
        self.assertEqual(payload["actions"][0]["id"], "start-proofreading")
        self.assertEqual(payload["commands"][0]["id"], "start-proofreading-command")
        self.assertEqual(
            payload["commands"][0]["client_effects"]["runtime_action"]["kind"],
            "start_proofreading",
        )

    def test_agent_proofread_request_names_blocker_when_inputs_missing(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "visualization",
                "image_path": "/projects/sample/data/image/train",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                        "optimization_priority": "accuracy",
                    }
                },
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "proofread this data"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_proofreading")
        self.assertIn("I can proofread this, but I need", payload["response"])
        self.assertIn("mask, label, or prediction", payload["response"])
        self.assertEqual(payload["commands"], [])
        self.assertEqual(payload["actions"][0]["id"], "open-files")

    def test_agent_routes_segmentation_and_capability_requests_to_app_actions(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "inference",
                "image_path": "/tmp/image.h5",
                "mask_path": "/tmp/mask.h5",
                "checkpoint_path": "/tmp/checkpoint.pth.tar",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                        "optimization_priority": "speed",
                    }
                },
            },
        )

        segment_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "I want to get my volume segmented"},
        )
        self.assertEqual(segment_response.status_code, 200)
        segment_payload = segment_response.json()
        self.assertIn("run the model", segment_payload["response"].lower())
        conversation_id = segment_payload["conversationId"]
        self.assertIsInstance(conversation_id, int)
        self.assertEqual(segment_payload["actions"][0]["label"], "Run model")
        self.assertEqual(
            segment_payload["commands"][0]["client_effects"]["runtime_action"]["kind"],
            "start_inference",
        )
        conversation_response = self.client.get(
            f"/chat/conversations/{conversation_id}"
        )
        self.assertEqual(conversation_response.status_code, 200)
        messages = conversation_response.json()["messages"]
        self.assertEqual(
            [message["role"] for message in messages], ["user", "assistant"]
        )
        self.assertEqual(messages[0]["content"], "I want to get my volume segmented")
        self.assertIn("run the model", messages[1]["content"].lower())
        self.assertEqual(messages[1]["source"], "workflow_orchestrator")
        self.assertEqual(messages[1]["actions"][0]["label"], "Run model")
        self.assertEqual(
            messages[1]["commands"][0]["client_effects"]["runtime_action"]["kind"],
            "start_inference",
        )

        capabilities_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={
                "query": "what can the agent do then? can it run things?",
                "conversation_id": conversation_id,
            },
        )
        self.assertEqual(capabilities_response.status_code, 200)
        capabilities_payload = capabilities_response.json()
        self.assertEqual(capabilities_payload["conversationId"], conversation_id)
        self.assertEqual(capabilities_payload["intent"], "capabilities")
        self.assertIn("run approved app steps", capabilities_payload["response"])
        self.assertEqual(capabilities_payload["actions"], [])
        updated_conversation_response = self.client.get(
            f"/chat/conversations/{conversation_id}"
        )
        self.assertEqual(updated_conversation_response.status_code, 200)
        self.assertEqual(len(updated_conversation_response.json()["messages"]), 4)

    def test_agent_handles_repair_language_without_repeating_recommendation_cards(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "proofreading",
                "image_path": "/tmp/image.h5",
                "mask_path": "/tmp/mask.h5",
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "bruh"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "repair")
        self.assertIn("too generic", payload["response"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["commands"], [])

    def test_agent_handles_unknown_text_without_recommendation_cards(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "proofreading",
                "image_path": "/tmp/image.h5",
                "mask_path": "/tmp/mask.h5",
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "mmajkf,ansdjs"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "clarify_next_job")
        self.assertIn("did not understand", payload["response"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["commands"], [])

    def test_agent_answers_current_workflow_context_instead_of_repeating_next_step(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "mito25-paper-loop-smoke",
                "stage": "proofreading",
                "image_path": "/projects/mito25/data/image/mito25_im.h5",
                "mask_path": "/projects/mito25/data/seg/mito25_seg.h5",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                        "optimization_priority": "accuracy",
                    }
                },
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "what exactly is the project I am on right now?"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "project_context")
        self.assertIn("mito25-paper-loop-smoke", payload["response"])
        self.assertIn("EM", payload["response"])
        self.assertIn("mitochondria", payload["response"])
        self.assertIn("accuracy", payload["response"])
        self.assertIn("proofreading", payload["response"])
        self.assertIn("mito25_im.h5", payload["response"])
        self.assertNotIn("0 inference failures", payload["response"])

    def test_agent_asks_for_biological_context_before_running_inference(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "inference",
                "image_path": "/projects/unknown/image.tif",
                "checkpoint_path": "/projects/unknown/checkpoint.pth.tar",
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "run inference"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "collect_project_context")
        self.assertIn("imaging modality", payload["response"])
        self.assertIn("target structure", payload["response"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["commands"], [])

    def test_agent_stores_context_and_then_runs_inference(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "inference",
                "image_path": "/projects/unknown/image.tif",
                "checkpoint_path": "/projects/unknown/checkpoint.pth.tar",
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={
                "query": "run inference on EM mitochondria; prioritize accuracy"
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_inference")
        self.assertTrue(payload["actions"])

        current_workflow, _ = self._current_workflow()
        project_context = current_workflow["metadata"]["project_context"]
        self.assertEqual(project_context["imaging_modality"], "EM")
        self.assertEqual(project_context["target_structure"], "mitochondria")
        self.assertEqual(project_context["optimization_priority"], "accuracy")

    def test_agent_start_training_uses_data_derived_defaults(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "mito25-paper-loop-smoke",
                "stage": "retraining_staged",
                "image_path": "/projects/mito25/data/image/mito25_im.h5",
                "corrected_mask_path": "/projects/mito25/data/seg/corrected.tif",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                        "optimization_priority": "accuracy",
                    }
                },
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "train the model for me"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_training")
        self.assertIn("safe defaults", payload["response"])
        effects = payload["commands"][0]["client_effects"]
        self.assertEqual(effects["navigate_to"], "training")
        self.assertEqual(
            effects["set_training_image_path"],
            "/projects/mito25/data/image/mito25_im.h5",
        )
        self.assertEqual(
            effects["set_training_label_path"],
            "/projects/mito25/data/seg/corrected.tif",
        )
        self.assertEqual(
            effects["set_training_config_preset"],
            "configs/MitoEM/Mito25-Local-Smoke-BC.yaml",
        )
        self.assertTrue(effects["runtime_action"]["autopick_parameters"])
        self.assertEqual(
            effects["runtime_action"]["parameter_mode"],
            "agent_default",
        )

    def test_general_chat_direct_guard_answers_meta_run_questions(self):
        with patch("server_api.main._ensure_chatbot") as ensure_chatbot:
            response = self.client.post(
                "/chat/query",
                json={"query": "how do you run so quickly?"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "direct_guard")
        self.assertIn("did not run training or inference", payload["response"])
        ensure_chatbot.assert_not_called()

        conversation_response = self.client.get(
            f"/chat/conversations/{payload['conversationId']}"
        )
        self.assertEqual(conversation_response.status_code, 200)
        messages = conversation_response.json()["messages"]
        self.assertEqual(
            [message["role"] for message in messages], ["user", "assistant"]
        )
        self.assertEqual(messages[1]["source"], "direct_guard")

    def test_general_chat_direct_guard_handles_gibberish_without_llm(self):
        with patch("server_api.main._ensure_chatbot") as ensure_chatbot:
            response = self.client.post(
                "/chat/query",
                json={"query": "mmajkf,ansdjs"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "direct_guard")
        self.assertIn("did not understand", payload["response"])
        ensure_chatbot.assert_not_called()

    def test_agent_handles_greetings_without_prompt_leakage(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "proofreading",
                "image_path": "/tmp/image.h5",
                "mask_path": "/tmp/mask.h5",
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "hi!"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("Hi.", payload["response"])
        self.assertIn("Next:", payload["response"])
        self.assertNotIn("Supervisor Agent", payload["response"])
        self.assertNotIn("RESPONSE STYLE", payload["response"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["commands"], [])
        self.assertEqual(payload["intent"], "greeting")

    def test_agent_can_offer_evaluation_and_export_actions(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "evaluation",
                "label_path": "/tmp/ground-truth.tif",
                "inference_output_path": "/tmp/candidate.tif",
            },
        )
        baseline_run = self.client.post(
            f"/api/workflows/{workflow_id}/model-runs",
            json={
                "run_type": "inference",
                "status": "completed",
                "output_path": "/tmp/baseline.tif",
            },
        )
        self.assertEqual(baseline_run.status_code, 200)
        candidate_run = self.client.post(
            f"/api/workflows/{workflow_id}/model-runs",
            json={
                "run_type": "inference",
                "status": "completed",
                "output_path": "/tmp/candidate.tif",
            },
        )
        self.assertEqual(candidate_run.status_code, 200)

        evaluation_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "compare results and compute metrics"},
        )
        self.assertEqual(evaluation_response.status_code, 200)
        evaluation_payload = evaluation_response.json()
        self.assertIn("compute before/after metrics", evaluation_payload["response"])
        compute_action = evaluation_payload["actions"][0]
        self.assertEqual(compute_action["id"], "compute-evaluation")
        self.assertEqual(compute_action["risk_level"], "writes_workflow_record")
        self.assertTrue(compute_action["requires_approval"])
        self.assertEqual(
            compute_action["client_effects"]["workflow_action"]["kind"],
            "compute_evaluation",
        )
        self.assertEqual(
            compute_action["client_effects"]["workflow_action"][
                "baseline_prediction_path"
            ],
            "/tmp/baseline.tif",
        )

        export_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "export evidence bundle"},
        )
        self.assertEqual(export_response.status_code, 200)
        export_payload = export_response.json()
        self.assertEqual(export_payload["actions"][0]["id"], "export-workflow-bundle")
        self.assertEqual(export_payload["actions"][0]["risk_level"], "exports_evidence")
        self.assertTrue(export_payload["actions"][0]["requires_approval"])
        self.assertEqual(
            export_payload["actions"][0]["client_effects"]["workflow_action"]["kind"],
            "export_bundle",
        )

    def test_agent_slash_command_aliases_route_to_actions(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "inference",
                "image_path": "/tmp/image.h5",
                "checkpoint_path": "/tmp/checkpoint.pth.tar",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                        "optimization_priority": "accuracy",
                    }
                },
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "/infer"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_inference")
        self.assertEqual(payload["actions"][0]["id"], "start-inference")
        self.assertEqual(payload["actions"][0]["risk_level"], "runs_job")
        self.assertTrue(payload["actions"][0]["requires_approval"])
        self.assertTrue(payload["tasks"])

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
