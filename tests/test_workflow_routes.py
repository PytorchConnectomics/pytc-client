import pathlib
import json
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
import server_api.workflows.router as workflows_router_module


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

    def test_semantic_workflow_intents_have_one_source_of_truth(self):
        prompt_intents = set(workflows_router_module.SEMANTIC_WORKFLOW_INTENT_ORDER)
        self.assertEqual(
            prompt_intents, workflows_router_module.SEMANTIC_WORKFLOW_INTENTS
        )
        self.assertIn("style_feedback", prompt_intents)
        self.assertIn("project_files", prompt_intents)
        self.assertIn("project_progress", prompt_intents)

    def test_project_progress_matches_nested_xri_mask_by_volume_folder(self):
        root = "/demo/yixiao"
        image_path = f"{root}/data/raw/5_1/5_1-xri-raw.tif"
        segmentation_paths = [
            f"{root}/data/seg/4_3/4_3-mask.tif",
            f"{root}/data/seg/5_1/5_1-mask.tif",
        ]

        matched = workflows_router_module._project_progress_match_segmentation(
            image_path,
            segmentation_paths,
            project_root=root,
            single_image=False,
        )

        self.assertEqual(matched, f"{root}/data/seg/5_1/5_1-mask.tif")

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

    def test_metadata_patches_merge_and_event_idempotency_is_stable(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]

        first_patch = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                    },
                    "session_onboarding": {"goals": "draft"},
                },
            },
        )
        self.assertEqual(first_patch.status_code, 200)
        second_patch = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "metadata": {"project_context": {"optimization_priority": "accuracy"}},
            },
        )
        self.assertEqual(second_patch.status_code, 200)
        metadata = second_patch.json()["metadata"]
        self.assertEqual(metadata["project_context"]["imaging_modality"], "EM")
        self.assertEqual(
            metadata["project_context"]["target_structure"], "mitochondria"
        )
        self.assertEqual(
            metadata["project_context"]["optimization_priority"],
            "accuracy",
        )
        self.assertEqual(metadata["session_onboarding"]["goals"], "draft")

        event_body = {
            "actor": "system",
            "event_type": "training.started",
            "stage": "retraining_staged",
            "summary": "Started once.",
            "payload": {"outputPath": "/tmp/training-run"},
            "idempotency_key": "runtime:start-training:abc",
        }
        first_event = self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json=event_body,
        )
        self.assertEqual(first_event.status_code, 200)
        second_event = self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={**event_body, "summary": "Retried request."},
        )
        self.assertEqual(second_event.status_code, 200)
        self.assertEqual(first_event.json()["id"], second_event.json()["id"])
        self.assertEqual(first_event.json()["schema_version"], 1)
        self.assertEqual(
            first_event.json()["idempotency_key"],
            "runtime:start-training:abc",
        )

    def test_project_memory_endpoint_returns_canonical_context(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "Yixiao TapeReader XRI Case Study",
                "stage": "setup",
                "dataset_path": "/projects/yixiao",
                "image_path": "/projects/yixiao/data/raw",
                "label_path": "/projects/yixiao/data/seg",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "X-ray / XRI volumetric microscopy",
                        "target_structure": "CytoTape fibres",
                        "task_family": "XRI fibre instance segmentation",
                        "voxel_size_nm": [40, 16.3, 16.3],
                        "mask_status": "mixed: some masks, some image-only volumes",
                        "training_policy": "train only on confirmed ground-truth masks",
                    }
                },
            },
        )
        self.assertEqual(patch_response.status_code, 200)
        event_response = self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "dataset.loaded",
                "stage": "setup",
                "summary": "Loaded Yixiao case study.",
                "payload": {"source": "test"},
            },
        )
        self.assertEqual(event_response.status_code, 200)

        response = self.client.get(f"/api/workflows/{workflow_id}/memory")
        self.assertEqual(response.status_code, 200)
        memory = response.json()
        self.assertEqual(memory["schema_version"], "pytc-project-memory/v1")
        self.assertEqual(
            memory["project_facts"]["task_family_preset"]["id"],
            "tapereader_xri_fiber",
        )
        self.assertEqual(
            memory["project_facts"]["project_context"]["target_structure"],
            "CytoTape fibres",
        )
        self.assertEqual(
            memory["artifact_index"]["canonical_paths"]["image"],
            "/projects/yixiao/data/raw",
        )
        self.assertEqual(
            memory["volume_states"]["summary"]["total"],
            1,
        )
        canonical_status = memory["volume_states"]["items"][0]["canonical_status"]
        self.assertEqual(
            memory["volume_states"]["summary"]["canonical"]["counts"][canonical_status],
            1,
        )
        self.assertEqual(
            memory["volume_states"]["items"][0]["state_schema_version"],
            "workflow-volume-state/v2",
        )
        self.assertIn(
            memory["volume_states"]["items"][0]["annotation_state"],
            {"draft_needs_proofreading", "image_only", "proofread_ground_truth"},
        )
        self.assertIn(
            canonical_status,
            {"draft_needs_proofreading", "image_only", "proofread_ground_truth"},
        )
        self.assertEqual(
            memory["volume_states"]["items"][0]["image_path"],
            "/projects/yixiao/data/raw",
        )
        self.assertEqual(
            memory["freshness"]["volume_states"]["row_count"],
            1,
        )
        self.assertEqual(
            memory["evidence_events"][-1]["event_type"],
            "dataset.loaded",
        )

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
        effects = response.json()["actions"][0]["client_effects"]
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

        effects_proposal = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions",
            json={
                "action": "run_client_effects",
                "summary": "Approve in-app inference run.",
                "payload": {
                    "item_id": "run-inference",
                    "item_label": "Run inference",
                    "risk_level": "runs_job",
                    "client_effects": {
                        "navigate_to": "inference",
                        "set_inference_output_path": "/tmp/inference-out",
                        "runtime_action": {"kind": "start_inference"},
                    },
                },
            },
        )
        self.assertEqual(effects_proposal.status_code, 200)

        effects_approval = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions/"
            f"{effects_proposal.json()['id']}/approve"
        )
        self.assertEqual(effects_approval.status_code, 200)
        effects_payload = effects_approval.json()
        self.assertEqual(effects_payload["commands"], [])
        self.assertEqual(
            effects_payload["client_effects"]["set_inference_output_path"],
            "/tmp/inference-out",
        )
        self.assertEqual(
            effects_payload["client_effects"]["runtime_action"]["kind"],
            "start_inference",
        )

        events_response = self.client.get(f"/api/workflows/{workflow_id}/events")
        event_types = [event["event_type"] for event in events_response.json()]
        self.assertIn("agent.proposal_approved", event_types)
        self.assertIn("agent.proposal_rejected", event_types)
        self.assertIn("agent.client_effects_approved", event_types)
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
        self.assertEqual(query_payload["actions"][0]["id"], "start-proofreading")
        self.assertEqual(query_payload["commands"], [])

    def test_agent_proofreading_launch_prefers_corrected_or_prediction_masks(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "Corrected proofread",
                "stage": "visualization",
                "image_path": "/tmp/source-image.h5",
                "mask_path": "/tmp/original-mask.h5",
                "inference_output_path": "/tmp/prediction-mask.h5",
                "corrected_mask_path": "/tmp/corrected-mask.tif",
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
            if action["id"] == "start-proofreading"
        )
        self.assertEqual(
            primary["client_effects"]["set_proofreading_dataset_path"],
            "/tmp/source-image.h5",
        )
        self.assertEqual(
            primary["client_effects"]["set_proofreading_mask_path"],
            "/tmp/corrected-mask.tif",
        )

        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={"corrected_mask_path": None},
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
            if action["id"] == "start-proofreading"
        )
        self.assertEqual(
            primary["client_effects"]["set_proofreading_mask_path"],
            "/tmp/prediction-mask.h5",
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
        self.assertEqual(effects["runtime_action"]["kind"], "load_visualization")
        self.assertEqual(
            effects["set_visualization_image_path"],
            "/projects/sample/data/image/train",
        )
        self.assertEqual(
            effects["set_visualization_label_path"],
            "/projects/sample/data/labels/train",
        )

        casual_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "can i look at my labels real quick?"},
        )
        self.assertEqual(casual_response.status_code, 200)
        casual_payload = casual_response.json()
        self.assertEqual(casual_payload["intent"], "view_data")
        self.assertNotIn("did not understand", casual_payload["response"].lower())
        self.assertEqual(casual_payload["actions"][0]["id"], "open-visualization")

        abbreviated_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "can we vis some data"},
        )
        self.assertEqual(abbreviated_response.status_code, 200)
        abbreviated_payload = abbreviated_response.json()
        self.assertEqual(abbreviated_payload["intent"], "view_data")
        self.assertEqual(abbreviated_payload["actions"][0]["id"], "open-visualization")

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

    def test_agent_visualize_request_uses_explicit_selected_pair(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        project_root = pathlib.Path(self.temp_dir.name) / "explicit-pair-project"
        image_dir = project_root / "images"
        label_dir = project_root / "labels"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        selected_image = image_dir / "img_b.h5"
        selected_label = label_dir / "label_b.h5"
        other_image = image_dir / "img_a.h5"
        other_label = label_dir / "label_a.h5"
        other_image.write_bytes(b"")
        other_label.write_bytes(b"")
        selected_image.write_bytes(b"")
        selected_label.write_bytes(b"")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "dataset_path": str(project_root),
                "image_path": str(selected_image),
                "label_path": str(selected_label),
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "can we visualize the selected pair?"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "view_data")
        effects = payload["actions"][0]["client_effects"]
        self.assertEqual(
            effects["set_visualization_image_path"],
            str(selected_image),
        )
        self.assertEqual(
            effects["set_visualization_label_path"],
            str(selected_label),
        )

    def test_agent_inspects_project_tree_for_alternate_volume_set(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        project_root = pathlib.Path(self.temp_dir.name) / "lucchi-project"
        image_dir = project_root / "data" / "image"
        source_dir = project_root / "data" / "source" / "Lucchi++"
        label_dir = project_root / "data" / "seg"
        image_dir.mkdir(parents=True)
        source_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        for stem in ["test", "train"]:
            (image_dir / f"{stem}_im.h5").write_bytes(b"")
            (source_dir / f"{stem}_im.h5").write_bytes(b"")
            (label_dir / f"{stem}_mito.h5").write_bytes(b"")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "visualization",
                "dataset_path": str(project_root),
                "image_path": str(image_dir / "test_im.h5"),
                "label_path": str(label_dir / "test_mito.h5"),
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={
                "query": (
                    "can't you look for another aptly named pair of image and seg? "
                    "there IS another pair in the project"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "view_data")
        self.assertIn("I inspected the project tree", payload["response"])
        self.assertIn("another image/seg set", payload["response"])
        self.assertNotIn("Before I choose", payload["response"])
        effects = payload["actions"][0]["client_effects"]
        self.assertEqual(effects["navigate_to"], "visualization")
        self.assertEqual(effects["runtime_action"]["kind"], "load_visualization")
        self.assertEqual(
            effects["set_visualization_image_path"],
            str(source_dir / "test_im.h5"),
        )
        self.assertEqual(
            effects["set_visualization_label_path"],
            str(label_dir / "test_mito.h5"),
        )

        current_response = self.client.get("/api/workflows/current")
        self.assertEqual(current_response.status_code, 200)
        observation = current_response.json()["workflow"]["metadata"][
            "project_observation"
        ]
        self.assertGreaterEqual(len(observation["volume_sets"]), 2)

    def test_agent_answers_project_file_overview_from_observation(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        project_root = pathlib.Path(self.temp_dir.name) / "overview-project"
        image_dir = project_root / "data" / "image"
        label_dir = project_root / "data" / "seg"
        config_dir = project_root / "configs"
        output_dir = project_root / "outputs"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        config_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)
        (image_dir / "test_im.h5").write_bytes(b"")
        (label_dir / "test_mito.h5").write_bytes(b"")
        (config_dir / "mito.yaml").write_text("MODEL: mito\n")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "visualization",
                "dataset_path": str(project_root),
                "image_path": str(image_dir / "test_im.h5"),
                "label_path": str(label_dir / "test_mito.h5"),
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "what exactly are the files in my lovely directory here?"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "project_files")
        self.assertIn("I checked", payload["response"])
        self.assertIn("At the top level", payload["response"])
        self.assertIn("data/", payload["response"])
        self.assertNotIn("Current read:", payload["response"])
        self.assertNotIn("Do this:", payload["response"])
        self.assertEqual(payload["actions"], [])
        self.assertTrue(
            any(item["label"] == "Checked project files" for item in payload["trace"])
        )

    def test_workflow_agent_conversation_hydrates_latest_workflow_chat(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]

        query_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "what should I do next?"},
        )
        self.assertEqual(query_response.status_code, 200)
        conversation_id = query_response.json()["conversation_id"]

        response = self.client.get(f"/api/workflows/{workflow_id}/agent/conversation")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["conversation_id"], conversation_id)
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["messages"][1]["role"], "assistant")
        self.assertEqual(
            payload["messages"][1]["source"],
            "workflow_orchestrator",
        )
        self.assertIn("trace", payload["messages"][1])
        self.assertTrue(
            all(
                "category" in item and "data" in item
                for item in payload["messages"][1]["trace"]
            )
        )

    def test_project_progress_counts_ground_truth_unproofread_and_missing_volumes(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        project_root = pathlib.Path(self.temp_dir.name) / "progress-project"
        image_dir = project_root / "data" / "image"
        label_dir = project_root / "data" / "seg"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        for stem in ["vol_a", "vol_b", "vol_c"]:
            (image_dir / f"{stem}_im.h5").write_bytes(b"")
        (label_dir / "vol_a_ground_truth.h5").write_bytes(b"")
        (label_dir / "vol_b_seg.h5").write_bytes(b"")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "Progress smoke",
                "stage": "visualization",
                "dataset_path": str(project_root),
                "image_path": str(image_dir / "vol_a_im.h5"),
                "label_path": str(label_dir / "vol_a_ground_truth.h5"),
            },
        )

        response = self.client.get(f"/api/workflows/{workflow_id}/project-progress")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["total"], 3)
        self.assertEqual(payload["summary"]["ground_truth"], 1)
        self.assertEqual(payload["summary"]["needs_proofreading"], 1)
        self.assertEqual(payload["summary"]["missing_segmentation"], 1)
        self.assertEqual(payload["summary"]["remaining"], 2)
        self.assertIn("annotation_state", payload["composite_state_definitions"])
        rows = {row["name"]: row for row in payload["volumes"]}
        self.assertEqual(rows["vol_a_im.h5"]["status"], "ground_truth")
        self.assertEqual(
            rows["vol_a_im.h5"]["annotation_state"],
            "proofread_ground_truth",
        )
        self.assertEqual(rows["vol_a_im.h5"]["role_state"], "training_source")
        self.assertEqual(rows["vol_b_im.h5"]["status"], "needs_proofreading")
        self.assertEqual(
            rows["vol_b_im.h5"]["annotation_state"],
            "draft_needs_proofreading",
        )
        self.assertEqual(rows["vol_c_im.h5"]["status"], "missing_segmentation")
        self.assertEqual(rows["vol_c_im.h5"]["annotation_state"], "image_only")
        self.assertIsInstance(rows["vol_a_im.h5"].get("volume_state_id"), int)
        self.assertTrue(rows["vol_a_im.h5"]["eligible_for_training"])
        self.assertTrue(rows["vol_c_im.h5"]["eligible_for_inference"])

        update_response = self.client.post(
            f"/api/workflows/{workflow_id}/project-progress/volume-status",
            json={
                "volume_id": rows["vol_b_im.h5"]["id"],
                "status": "ground_truth",
                "note": "Reviewed by expert.",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["summary"]["ground_truth"], 2)
        updated_rows = {row["name"]: row for row in updated["volumes"]}
        self.assertEqual(
            updated_rows["vol_b_im.h5"]["status_source"], "manual_override"
        )
        self.assertEqual(
            updated_rows["vol_b_im.h5"]["annotation_state"],
            "proofread_ground_truth",
        )
        self.assertEqual(updated_rows["vol_b_im.h5"]["role_state"], "training_source")
        self.assertEqual(updated_rows["vol_b_im.h5"]["note"], "Reviewed by expert.")

        states_response = self.client.get(f"/api/workflows/{workflow_id}/volumes")
        self.assertEqual(states_response.status_code, 200)
        states = states_response.json()
        self.assertEqual(states["summary"]["total"], 3)
        self.assertEqual(states["summary"]["ground_truth"], 2)
        self.assertEqual(states["summary"]["training_ready"], 2)
        state_by_volume_id = {state["volume_id"]: state for state in states["volumes"]}
        self.assertEqual(
            state_by_volume_id[rows["vol_b_im.h5"]["id"]]["status_source"],
            "manual_override",
        )
        self.assertEqual(
            state_by_volume_id[rows["vol_b_im.h5"]["id"]]["annotation_state"],
            "proofread_ground_truth",
        )
        self.assertEqual(
            state_by_volume_id[rows["vol_b_im.h5"]["id"]]["note"],
            "Reviewed by expert.",
        )

        events_response = self.client.get(f"/api/workflows/{workflow_id}/events")
        self.assertEqual(events_response.status_code, 200)
        self.assertIn(
            "project_volume.status_updated",
            [event["event_type"] for event in events_response.json()],
        )

    def test_workflow_volume_state_api_updates_training_and_inference_flags(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        image_path = pathlib.Path(self.temp_dir.name) / "volume_im.h5"
        label_path = pathlib.Path(self.temp_dir.name) / "volume_seg.h5"
        image_path.write_bytes(b"image")
        label_path.write_bytes(b"label")

        response = self.client.patch(
            f"/api/workflows/{workflow_id}/volumes",
            json={
                "volume_id": "manual/volume_im.h5",
                "status": "ground_truth",
                "image_path": str(image_path),
                "label_path": str(label_path),
                "note": "Confirmed in test.",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ground_truth")
        self.assertEqual(payload["status_source"], "manual")
        self.assertEqual(payload["legacy_status"], "ground_truth")
        self.assertEqual(payload["canonical_status"], "proofread_ground_truth")
        self.assertEqual(payload["annotation_state"], "proofread_ground_truth")
        self.assertEqual(payload["role_state"], "training_source")
        self.assertEqual(payload["execution_state"], "ready")
        self.assertEqual(payload["region_scope"]["scope_type"], "full_volume")
        self.assertEqual(payload["state_schema_version"], "workflow-volume-state/v2")
        self.assertTrue(payload["eligible_for_training"])
        self.assertFalse(payload["eligible_for_inference"])
        self.assertEqual(payload["note"], "Confirmed in test.")

        states_response = self.client.get(
            f"/api/workflows/{workflow_id}/volumes",
            params={"refresh": "false"},
        )
        self.assertEqual(states_response.status_code, 200)
        states = states_response.json()
        self.assertEqual(states["summary"]["training_ready"], 1)
        self.assertEqual(states["volumes"][0]["volume_id"], "manual/volume_im.h5")

        target_response = self.client.patch(
            f"/api/workflows/{workflow_id}/volumes",
            json={
                "volume_id": "manual/target_im.h5",
                "annotation_state": "image_only",
                "role_state": "inference_target",
                "execution_state": "ready",
                "image_path": str(image_path),
            },
        )
        self.assertEqual(target_response.status_code, 200)
        target_payload = target_response.json()
        self.assertEqual(target_payload["status"], "missing_segmentation")
        self.assertTrue(target_payload["eligible_for_inference"])
        self.assertFalse(target_payload["eligible_for_training"])

        contradictory_response = self.client.patch(
            f"/api/workflows/{workflow_id}/volumes",
            json={
                "volume_id": "manual/bad_state.h5",
                "status": "ground_truth",
                "annotation_state": "image_only",
            },
        )
        self.assertEqual(contradictory_response.status_code, 400)

    def test_workflow_overview_summarizes_phase_progress_and_next_actions(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        project_root = pathlib.Path(self.temp_dir.name) / "overview-project"
        image_dir = project_root / "data" / "image"
        label_dir = project_root / "data" / "seg"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        for stem in ["vol_a", "vol_b", "vol_c"]:
            (image_dir / f"{stem}_im.h5").write_bytes(b"")
        (label_dir / "vol_a_ground_truth.h5").write_bytes(b"")
        (label_dir / "vol_b_seg.h5").write_bytes(b"")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "Overview smoke",
                "stage": "visualization",
                "dataset_path": str(project_root),
                "image_path": str(image_dir / "vol_a_im.h5"),
                "label_path": str(label_dir / "vol_a_ground_truth.h5"),
            },
        )

        response = self.client.get(f"/api/workflows/{workflow_id}/overview")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["project_name"], "Overview smoke")
        self.assertEqual(payload["phase"], "proofread")
        self.assertEqual(payload["phase_label"], "Proofread")
        self.assertEqual(payload["volume_summary"]["ground_truth"], 1)
        self.assertEqual(payload["volume_summary"]["needs_proofreading"], 1)
        self.assertEqual(payload["volume_summary"]["missing_segmentation"], 1)
        self.assertEqual(payload["project_progress"]["summary"]["total"], 3)
        stage_by_id = {stage["id"]: stage for stage in payload["stages"]}
        self.assertTrue(stage_by_id["setup"]["complete"])
        self.assertTrue(stage_by_id["inspect"]["complete"])
        self.assertTrue(stage_by_id["proofread"]["current"])
        action_ids = [action["id"] for action in payload["recommended_next_actions"]]
        self.assertIn("proofread-draft-masks", action_ids)
        self.assertIn("train-from-ground-truth", action_ids)
        blocker_ids = [blocker["id"] for blocker in payload["blockers"]]
        self.assertIn("draft_masks_need_review", blocker_ids)

    def test_agent_opens_project_progress_tracker_with_counts(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        project_root = pathlib.Path(self.temp_dir.name) / "agent-progress-project"
        image_dir = project_root / "data" / "image"
        label_dir = project_root / "data" / "seg"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        (image_dir / "vol_a_im.h5").write_bytes(b"")
        (image_dir / "vol_b_im.h5").write_bytes(b"")
        (label_dir / "vol_a_gt.h5").write_bytes(b"")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "visualization",
                "dataset_path": str(project_root),
                "image_path": str(image_dir / "vol_a_im.h5"),
                "label_path": str(label_dir / "vol_a_gt.h5"),
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "open the project progress tracker"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "project_progress")
        self.assertEqual(payload["orchestrator_agent"]["type"], "project_manager")
        self.assertTrue(
            any(agent["type"] == "training_agent" for agent in payload["subagents"])
        )
        self.assertIn("tracked image volume", payload["response"])
        self.assertEqual(payload["trace_schema_version"], "agent_trace/v1")
        self.assertTrue(
            any(item["category"] == "proposed" for item in payload["trace"])
        )
        self.assertTrue(
            any(item["agent_type"] == "project_manager" for item in payload["trace"])
        )
        self.assertEqual(payload["actions"][0]["id"], "open-project-progress")
        self.assertEqual(payload["actions"][0]["agent_type"], "project_manager")
        self.assertEqual(
            payload["actions"][0]["specialist_agent"]["type"],
            "project_manager",
        )
        self.assertEqual(payload["actions"][0]["card_type"], "workflow.action_card/v2")
        self.assertEqual(payload["actions"][0]["risk_tier"], "R0_view")
        self.assertEqual(
            payload["actions"][0]["action_card"]["executor"],
            "bounded_app_routine",
        )
        self.assertEqual(
            payload["actions"][0]["client_effects"]["navigate_to"],
            "project-progress",
        )

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
        self.assertEqual(payload["commands"], [])
        self.assertEqual(
            payload["actions"][0]["client_effects"]["runtime_action"]["kind"],
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
        self.assertEqual(segment_payload["commands"], [])
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
        self.assertEqual(messages[1]["commands"], [])

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

    def test_agent_exposes_workspace_configuration_and_runtime_control_actions(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "Lucchi case study",
                "dataset_path": "/projects/lucchi",
                "image_path": "/projects/lucchi/data/image/test_im.h5",
                "label_path": "/projects/lucchi/data/seg/test_mito.h5",
                "mask_path": "/projects/lucchi/data/seg/test_mito.h5",
                "checkpoint_path": "/projects/lucchi/checkpoints/checkpoint.pth.tar",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                        "optimization_priority": "accuracy",
                    }
                },
            },
        )

        mount_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "remount the lucchi project"},
        )
        self.assertEqual(mount_response.status_code, 200)
        mount_payload = mount_response.json()
        self.assertEqual(mount_payload["intent"], "mount_project")
        self.assertEqual(mount_payload["actions"][0]["id"], "mount-project")
        self.assertEqual(
            mount_payload["actions"][0]["client_effects"]["mount_project"][
                "directory_path"
            ],
            "/projects/lucchi",
        )

        configure_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "configure inference settings before running"},
        )
        self.assertEqual(configure_response.status_code, 200)
        configure_payload = configure_response.json()
        self.assertEqual(configure_payload["intent"], "configure_inference")
        configure_effects = configure_payload["actions"][0]["client_effects"]
        self.assertEqual(configure_effects["navigate_to"], "inference")
        self.assertNotIn("runtime_action", configure_effects)
        self.assertEqual(
            configure_effects["set_inference_image_path"],
            "/projects/lucchi/data/image/test_im.h5",
        )
        self.assertEqual(
            configure_effects["set_inference_checkpoint_path"],
            "/projects/lucchi/checkpoints/checkpoint.pth.tar",
        )

        reset_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "clear cached workspace state and remount"},
        )
        self.assertEqual(reset_response.status_code, 200)
        reset_payload = reset_response.json()
        self.assertEqual(reset_payload["intent"], "reset_workspace")
        reset_effects = reset_payload["actions"][0]["client_effects"]
        self.assertTrue(reset_effects["reset_workspace"])
        self.assertEqual(
            reset_effects["mount_project"]["directory_path"],
            "/projects/lucchi",
        )

        stop_response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "stop the training job"},
        )
        self.assertEqual(stop_response.status_code, 200)
        stop_payload = stop_response.json()
        self.assertEqual(stop_payload["intent"], "stop_runtime")
        action_ids = [action["id"] for action in stop_payload["actions"]]
        self.assertIn("stop-inference", action_ids)
        self.assertEqual(len(action_ids), 1)

    def test_agent_understands_casual_segmentation_language(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "visualization",
                "image_path": "/projects/lucchi/data/image/test_im.h5",
                "label_path": "/projects/lucchi/data/seg/test_mito.h5",
                "mask_path": "/projects/lucchi/data/seg/test_mito.h5",
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
            json={"query": "i wanna segment some dattaaaaaaaaaaa"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_segmentation")
        self.assertNotIn("did not understand", payload["response"].lower())
        self.assertIn("checkpoint", payload["response"].lower())
        action_ids = [action["id"] for action in payload["actions"]]
        self.assertIn("start-proofreading", action_ids)
        self.assertEqual(len(action_ids), 1)

    def test_agent_returns_one_app_suggestion_for_segmentation_blockers(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "visualization",
                "image_path": "/projects/lucchi/data/image/test_im.h5",
                "label_path": "/projects/lucchi/data/seg/test_mito.h5",
                "mask_path": "/projects/lucchi/data/seg/test_mito.h5",
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
            json={"query": "can we segment my data with a model?"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_segmentation")
        self.assertIn("because", payload["response"].lower())
        self.assertEqual(len(payload["actions"]), 1)
        self.assertEqual(payload["commands"], [])

    def test_agent_context_followup_updates_without_action_cards(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "visualization",
                "image_path": "/projects/lucchi/data/image/test_im.h5",
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "what if this is EM mitochondria and we care about speed?"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "project_context_updated")
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["commands"], [])

        current_workflow, _ = self._current_workflow()
        project_context = current_workflow["metadata"]["project_context"]
        self.assertEqual(project_context["imaging_modality"], "EM")
        self.assertEqual(project_context["target_structure"], "mitochondria")
        self.assertEqual(project_context["optimization_priority"], "speed")

    def test_agent_volume_id_question_does_not_mutate_project_context(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "Yixiao TapeReader XRI Case Study",
                "stage": "visualization",
                "dataset_path": "/projects/yixiao",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "X-ray / XRI volumetric microscopy",
                        "target_structure": "CytoTape fibres",
                        "voxel_size_nm": [40, 16.3, 16.3],
                        "training_policy": "train only on confirmed ground-truth masks",
                    }
                },
            },
        )
        self.assertEqual(patch_response.status_code, 200)

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "Why did you leave out 5_1, 5_2, 6_1, and 6_2?"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotEqual(payload["intent"], "project_context_updated")

        current_workflow, _ = self._current_workflow()
        project_context = current_workflow["metadata"]["project_context"]
        self.assertEqual(project_context["voxel_size_nm"], [40, 16.3, 16.3])
        self.assertNotEqual(project_context["voxel_size_nm"], [5, 1, 5])

    def test_project_progress_response_names_volume_groups(self):
        response = workflows_router_module._format_project_progress_response(
            {
                "summary": {
                    "tracked_total": 10,
                    "ground_truth": 6,
                    "needs_proofreading": 2,
                    "missing_segmentation": 2,
                    "completion_pct": 60.0,
                },
                "volumes": [
                    {"name": "1-xri_raw.tif", "status": "ground_truth"},
                    {"name": "5_1-xri-raw.tif", "status": "needs_proofreading"},
                    {"name": "5_2-xri_raw.tif", "status": "needs_proofreading"},
                    {"name": "6_1-xri_raw.tif", "status": "missing_segmentation"},
                    {"name": "6_2-xri-raw.tif", "status": "missing_segmentation"},
                ],
            }
        )

        self.assertIn("ready for training: 1-xri_raw.tif", response)
        self.assertIn(
            "proofread before training: 5_1-xri-raw.tif, 5_2-xri_raw.tif",
            response,
        )
        self.assertIn(
            "image-only/inference targets: 6_1-xri_raw.tif, 6_2-xri-raw.tif",
            response,
        )

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
        self.assertIn("not sure which app step", payload["response"])
        self.assertNotIn("did not understand", payload["response"].lower())
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["commands"], [])

    def test_agent_answers_current_workflow_context_instead_of_repeating_next_step(
        self,
    ):
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
        self.assertEqual(payload["policy_decision"]["decision"], "blocked")
        self.assertFalse(payload["policy_decision"]["requires_approval"])
        self.assertEqual(payload["freshness"]["scope"], "project_context")
        self.assertEqual(payload["freshness"]["state"], "missing")
        self.assertCountEqual(
            payload["freshness"]["missing"],
            ["imaging_modality", "target_structure"],
        )
        self.assertEqual(
            payload["blocking_reasons"][0]["code"],
            "project_context.missing_imaging_modality",
        )
        self.assertEqual(
            payload["blocking_reasons"][1]["code"],
            "project_context.missing_target_structure",
        )
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["commands"], [])

    def test_project_context_freshness_reports_missing_and_stale_states(self):
        missing_context_workflow = type(
            "WorkflowSession",
            (),
            {"metadata_json": json.dumps({"project_context": {}})},
        )()
        missing_freshness = workflows_router_module._project_context_freshness(
            missing_context_workflow
        )
        self.assertEqual(missing_freshness["scope"], "project_context")
        self.assertEqual(missing_freshness["state"], "missing")
        self.assertCountEqual(
            missing_freshness["missing"],
            ["imaging_modality", "target_structure"],
        )

        stale_context_workflow = type(
            "WorkflowSession",
            (),
            {
                "metadata_json": json.dumps(
                    {
                        "project_context": {
                            "imaging_modality": "EM",
                            "target_structure": "mitochondria",
                            "source": "initial_project_default",
                        }
                    }
                )
            },
        )()
        stale_freshness = workflows_router_module._project_context_freshness(
            stale_context_workflow
        )
        self.assertEqual(stale_freshness["scope"], "project_context")
        self.assertEqual(stale_freshness["state"], "stale")
        self.assertEqual(stale_freshness["missing"], [])
        self.assertEqual(
            stale_freshness["present"],
            ["imaging_modality", "target_structure"],
        )

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
            json={"query": "run inference on EM mitochondria; prioritize accuracy"},
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
        self.assertEqual(payload["policy_decision"]["decision"], "allowed")
        self.assertTrue(payload["policy_decision"]["requires_approval"])
        effects = payload["actions"][0]["client_effects"]
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
            "configs/MitoEM/Mito25-Local-BC.yaml",
        )
        self.assertTrue(effects["runtime_action"]["autopick_parameters"])
        self.assertEqual(
            effects["runtime_action"]["parameter_mode"],
            "agent_default",
        )
        self.assertEqual(
            payload["actions"][0]["policy_decision"]["decision"], "allowed"
        )
        self.assertTrue(payload["actions"][0]["policy_decision"]["requires_approval"])
        self.assertEqual(payload["actions"][0]["freshness"]["scope"], "training")
        self.assertEqual(payload["actions"][0]["freshness"]["state"], "ready")

    def test_approved_training_run_proposal_returns_runtime_launch_effects(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "retraining_staged",
                "image_path": "/projects/mito25/data/image/mito25_im.h5",
                "corrected_mask_path": "/projects/mito25/data/seg/corrected.tif",
            },
        )
        client_effects = {
            "navigate_to": "training",
            "runtime_action": {
                "kind": "start_training",
                "autopick_parameters": True,
                "parameter_mode": "agent_default",
            },
            "set_training_config_preset": "configs/MitoEM/Mito25-Local-BC.yaml",
            "set_training_image_path": "/projects/mito25/data/image/mito25_im.h5",
            "set_training_label_path": "/projects/mito25/data/seg/corrected.tif",
            "set_training_output_path": "/projects/mito25/outputs/training",
            "set_training_log_path": "/projects/mito25/outputs/training",
        }

        proposal = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions",
            json={
                "action": "start_training_run",
                "summary": "Approve training run.",
                "payload": {
                    "client_effects": client_effects,
                    "config_preset": client_effects["set_training_config_preset"],
                    "image_path": client_effects["set_training_image_path"],
                    "label_path": client_effects["set_training_label_path"],
                    "output_path": client_effects["set_training_output_path"],
                    "parameter_mode": "agent_default",
                    "autopick_parameters": True,
                },
            },
        )
        self.assertEqual(proposal.status_code, 200)

        approval = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions/"
            f"{proposal.json()['id']}/approve"
        )
        self.assertEqual(approval.status_code, 200)
        payload = approval.json()
        self.assertEqual(payload["workflow"]["stage"], "retraining_staged")
        self.assertEqual(
            payload["client_effects"]["runtime_action"]["kind"], "start_training"
        )
        self.assertEqual(len(payload["commands"]), 1)
        self.assertEqual(payload["commands"][0]["command_type"], "start_training")
        self.assertEqual(payload["commands"][0]["status"], "queued")
        self.assertEqual(
            payload["commands"][0]["input"]["client_effects"]["runtime_action"]["kind"],
            "start_training",
        )
        self.assertTrue(
            payload["client_effects"]["runtime_action"]["autopick_parameters"]
        )
        self.assertEqual(
            payload["client_effects"]["set_training_config_preset"],
            "configs/MitoEM/Mito25-Local-BC.yaml",
        )
        self.assertEqual(
            payload["client_effects"]["set_training_output_path"],
            "/projects/mito25/outputs/training",
        )

        command_list = self.client.get(f"/api/workflows/{workflow_id}/commands")
        self.assertEqual(command_list.status_code, 200)
        self.assertEqual(len(command_list.json()), 1)
        self.assertEqual(command_list.json()[0]["id"], payload["commands"][0]["id"])

    def test_approved_training_run_applies_user_field_overrides(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "retraining_staged",
                "image_path": "/projects/mito25/data/image/original_im.h5",
                "corrected_mask_path": "/projects/mito25/data/seg/original_seg.h5",
            },
        )
        client_effects = {
            "navigate_to": "training",
            "runtime_action": {
                "kind": "start_training",
                "autopick_parameters": True,
                "parameter_mode": "agent_default",
            },
            "set_training_config_preset": "configs/original.yaml",
            "set_training_image_path": "/projects/mito25/subsets/original_image",
            "set_training_label_path": "/projects/mito25/subsets/original_seg",
            "set_training_output_path": "/projects/mito25/outputs/original",
            "set_training_log_path": "/projects/mito25/outputs/original",
        }
        proposal = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions",
            json={
                "action": "start_training_run",
                "summary": "Approve training run.",
                "payload": {
                    "client_effects": client_effects,
                    "config_preset": client_effects["set_training_config_preset"],
                    "image_path": client_effects["set_training_image_path"],
                    "label_path": client_effects["set_training_label_path"],
                    "output_path": client_effects["set_training_output_path"],
                },
            },
        )
        self.assertEqual(proposal.status_code, 200)

        approval = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions/"
            f"{proposal.json()['id']}/approve",
            json={
                "overrides": {
                    "config_preset": "configs/edited.yaml",
                    "image_path": "/projects/mito25/subsets/edited_image",
                    "label_path": "/projects/mito25/subsets/edited_seg",
                    "output_path": "/projects/mito25/outputs/edited",
                }
            },
        )
        self.assertEqual(approval.status_code, 200)
        payload = approval.json()
        self.assertEqual(
            payload["client_effects"]["set_training_config_preset"],
            "configs/edited.yaml",
        )
        self.assertEqual(
            payload["client_effects"]["set_training_image_path"],
            "/projects/mito25/subsets/edited_image",
        )
        self.assertEqual(
            payload["client_effects"]["set_training_label_path"],
            "/projects/mito25/subsets/edited_seg",
        )
        self.assertEqual(
            payload["client_effects"]["set_training_output_path"],
            "/projects/mito25/outputs/edited",
        )
        self.assertEqual(
            payload["commands"][0]["input"]["client_effects"][
                "set_training_output_path"
            ],
            "/projects/mito25/outputs/edited",
        )
        approved_payload = payload["events"][0]["payload"]
        self.assertEqual(
            approved_payload["user_edits"]["output_path"],
            "/projects/mito25/outputs/edited",
        )

    def test_agent_train_short_phrases_do_not_fall_to_unknown(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "train"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "collect_project_context")
        self.assertIn("Before I choose a training preset", payload["response"])
        self.assertNotIn("did not understand", payload["response"].lower())

    def test_agent_train_model_from_current_labels(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "image_path": "/projects/sample/data/image/train",
                "label_path": "/projects/sample/data/labels/train",
                "metadata": {"project_context": {"use_defaults": True}},
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "can we train a model for this?"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_training")
        self.assertIn("train a model", payload["response"].lower())
        self.assertEqual(payload["policy_decision"]["decision"], "allowed")
        self.assertTrue(payload["policy_decision"]["requires_approval"])
        self.assertEqual(payload["actions"][0]["id"], "start-training")
        effects = payload["actions"][0]["client_effects"]
        self.assertEqual(effects["navigate_to"], "training")
        self.assertEqual(
            effects["set_training_image_path"],
            "/projects/sample/data/image/train",
        )
        self.assertEqual(
            effects["set_training_label_path"],
            "/projects/sample/data/labels/train",
        )
        self.assertEqual(effects["runtime_action"]["kind"], "start_training")
        self.assertEqual(
            payload["actions"][0]["policy_decision"]["decision"], "allowed"
        )
        self.assertTrue(payload["actions"][0]["policy_decision"]["requires_approval"])
        self.assertEqual(payload["actions"][0]["freshness"]["scope"], "training")
        self.assertEqual(payload["actions"][0]["freshness"]["state"], "ready")

    def test_agent_train_model_uses_ground_truth_progress_subset(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        project_root = pathlib.Path(self.temp_dir.name) / "progress-training-project"
        image_dir = project_root / "data" / "image"
        label_dir = project_root / "data" / "seg"
        config_path = project_root / "configs" / "MitoEM2-Pyra-Demo-BC.yaml"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        config_path.parent.mkdir(parents=True)
        config_path.write_text("SYSTEM: PyTC\n", encoding="utf-8")
        for stem in ["vol_a", "vol_b", "vol_c"]:
            (image_dir / f"{stem}_im.h5").write_bytes(b"")
        (label_dir / "vol_a_curated_seg.h5").write_bytes(b"")
        (label_dir / "vol_b_seg.h5").write_bytes(b"")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "dataset_path": str(project_root),
                "image_path": str(image_dir),
                "label_path": str(label_dir),
                "config_path": str(config_path),
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
                "query": "can we train a model on my ground truth to segment the rest"
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_training")
        self.assertIn("ground-truth", payload["response"])
        self.assertNotEqual(payload["intent"], "project_progress")
        action = payload["actions"][0]
        self.assertEqual(action["card_type"], "workflow.action_card/v2")
        self.assertEqual(action["agent_type"], "training_agent")
        self.assertEqual(action["specialist_agent"]["label"], "Training Agent")
        self.assertEqual(action["agent_icon_key"], "experiment")
        self.assertEqual(action["agent_border_style"], "thick")
        self.assertEqual(action["specialist_agent"]["icon_key"], "experiment")
        self.assertEqual(action["risk_tier"], "R4_runtime_job")
        self.assertTrue(action["requires_approval"])
        self.assertIn("input_artifacts", action)
        self.assertTrue(action["input_artifacts"])
        self.assertTrue(action["output_artifacts"])
        self.assertEqual(action["action_card"]["action_type"], "start_training")
        self.assertEqual(
            action["action_card"]["orchestrator_agent"]["type"],
            "project_manager",
        )
        self.assertEqual(
            action["action_card"]["specialist_agent"]["type"],
            "training_agent",
        )
        effects = action["client_effects"]
        subset = effects["training_volume_subset"]
        self.assertEqual(subset["train_volume_count"], 1)
        self.assertEqual(subset["target_volume_count"], 1)
        self.assertEqual(subset["review_volume_count"], 1)
        self.assertEqual(subset["training_statuses"], ["ground_truth"])
        self.assertEqual(effects["set_training_config_preset"], str(config_path))
        self.assertTrue(pathlib.Path(effects["set_training_image_path"]).is_dir())
        self.assertTrue(pathlib.Path(effects["set_training_label_path"]).is_dir())
        self.assertTrue(pathlib.Path(subset["manifest_path"]).is_file())
        self.assertIn(
            "volume_subset",
            effects["runtime_action"],
        )
        self.assertEqual(
            effects["runtime_action"]["volume_subset"]["train_volume_count"],
            1,
        )

    def test_agent_train_model_names_missing_label_blocker(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "image_path": "/projects/sample/data/image/train",
                "metadata": {"project_context": {"use_defaults": True}},
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "train on saved edits"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_training")
        self.assertIn("need labels or saved proofreading edits", payload["response"])
        self.assertEqual(payload["commands"], [])
        self.assertEqual(payload["actions"][0]["risk_level"], "prefills_form")
        self.assertFalse(payload["actions"][0]["requires_approval"])
        self.assertEqual(payload["policy_decision"]["decision"], "blocked")
        self.assertFalse(payload["policy_decision"]["requires_approval"])
        self.assertEqual(
            payload["actions"][0]["policy_decision"]["decision"],
            "blocked",
        )
        self.assertFalse(payload["actions"][0]["policy_decision"]["requires_approval"])
        self.assertEqual(
            payload["actions"][0]["policy_decision"]["blocking_reasons"][0]["code"],
            "training.missing_labels",
        )
        self.assertEqual(payload["actions"][0]["freshness"]["scope"], "training")
        self.assertEqual(payload["actions"][0]["freshness"]["state"], "missing")
        self.assertEqual(
            payload["actions"][0]["client_effects"]["runtime_action"]["kind"],
            "choose_project_data",
        )

    def test_agent_train_on_trusted_masks_only_for_tapereader_context(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "image_path": "/tmp/yixiao/image.h5",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "X-ray / XRI volumetric microscopy",
                        "target_structure": "CytoTape fibres",
                        "training_policy": "train only on confirmed ground-truth masks",
                    }
                },
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "train the model now"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_training")
        self.assertIn(
            "confirmed labels or saved proofreading edits", payload["response"].lower()
        )
        self.assertEqual(payload["policy_decision"]["decision"], "blocked")
        self.assertFalse(payload["policy_decision"]["requires_approval"])
        self.assertEqual(
            payload["actions"][0]["policy_decision"]["reason_code"],
            "training_missing_inputs",
        )
        self.assertEqual(payload["actions"][0]["id"], "open-files")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={"corrected_mask_path": "/tmp/yixiao/saved-edits.tif"},
        )
        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "train this image"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_training")
        self.assertEqual(payload["policy_decision"]["decision"], "allowed")
        self.assertTrue(payload["policy_decision"]["requires_approval"])
        self.assertEqual(
            payload["actions"][0]["policy_decision"]["decision"], "allowed"
        )
        self.assertTrue(payload["actions"][0]["policy_decision"]["requires_approval"])
        self.assertEqual(payload["actions"][0]["id"], "start-training")
        self.assertEqual(
            payload["actions"][0]["client_effects"]["set_training_label_path"],
            "/tmp/yixiao/saved-edits.tif",
        )

    def test_agent_infer_on_image_only_projects_only_with_checkpoint(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "image_path": "/tmp/yixiao/image-only-project.tif",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "X-ray / XRI volumetric microscopy",
                        "target_structure": "CytoTape fibres",
                    }
                },
            },
        )

        checkpoint_missing = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "run inference"},
        )
        self.assertEqual(checkpoint_missing.status_code, 200)
        checkpoint_payload = checkpoint_missing.json()
        self.assertEqual(checkpoint_payload["intent"], "start_inference")
        self.assertIn("need model checkpoint", checkpoint_payload["response"].lower())
        self.assertEqual(checkpoint_payload["policy_decision"]["decision"], "blocked")
        self.assertFalse(checkpoint_payload["policy_decision"]["requires_approval"])
        self.assertEqual(checkpoint_payload["freshness"]["scope"], "inference")
        self.assertEqual(checkpoint_payload["freshness"]["state"], "missing")
        self.assertEqual(
            checkpoint_payload["actions"][0]["policy_decision"]["decision"],
            "blocked",
        )
        self.assertFalse(
            checkpoint_payload["actions"][0]["policy_decision"]["requires_approval"]
        )
        self.assertEqual(checkpoint_payload["actions"][0]["id"], "open-inference")

        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={"checkpoint_path": "/tmp/yixiao/model-checkpoint.pt"},
        )
        checkpoint_present = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "run model"},
        )
        self.assertEqual(checkpoint_present.status_code, 200)
        ready_payload = checkpoint_present.json()
        self.assertEqual(ready_payload["intent"], "start_inference")
        self.assertEqual(ready_payload["policy_decision"]["decision"], "allowed")
        self.assertTrue(ready_payload["policy_decision"]["requires_approval"])
        self.assertEqual(ready_payload["freshness"]["scope"], "inference")
        self.assertEqual(ready_payload["freshness"]["state"], "ready")
        self.assertEqual(ready_payload["actions"][0]["id"], "start-inference")
        self.assertEqual(
            ready_payload["actions"][0]["policy_decision"]["decision"],
            "allowed",
        )
        self.assertTrue(
            ready_payload["actions"][0]["policy_decision"]["requires_approval"]
        )

    def test_agent_segment_request_does_not_retrain_from_untrusted_prediction(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "image_path": "/tmp/yixiao/tape-seg-image.h5",
                "inference_output_path": "/tmp/yixiao/untrusted-prediction.tif",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "X-ray / XRI volumetric microscopy",
                        "target_structure": "CytoTape fibres",
                    }
                },
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "segment this dataset"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "start_segmentation")
        self.assertIn("running inference needs model checkpoint", payload["response"])
        action_ids = [action["id"] for action in payload["actions"]]
        self.assertNotIn("start-training", action_ids)

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

    def test_general_chat_llm_unavailable_returns_degraded_response(self):
        import server_api.main as server_api_main

        original_error = server_api_main._chatbot_error
        server_api_main._chatbot_error = RuntimeError('model "missing-model" not found')
        try:
            with patch("server_api.main._ensure_chatbot", return_value=False):
                response = self.client.post(
                    "/chat/query",
                    json={"query": "how do I configure the docs assistant?"},
                )
        finally:
            server_api_main._chatbot_error = original_error

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "llm_unavailable")
        self.assertIn("documentation assistant", payload["response"])
        self.assertNotIn("missing-model", payload["response"])

        conversation_response = self.client.get(
            f"/chat/conversations/{payload['conversationId']}"
        )
        self.assertEqual(conversation_response.status_code, 200)
        messages = conversation_response.json()["messages"]
        self.assertEqual(messages[1]["source"], "llm_unavailable")

    def test_clear_chat_does_not_initialize_llm(self):
        import server_api.main as server_api_main

        original_history = list(server_api_main._chat_history)
        original_active_convo_id = server_api_main._active_convo_id
        server_api_main._chat_history[:] = [{"role": "user", "content": "status"}]
        server_api_main._active_convo_id = 123
        try:
            with patch(
                "server_api.main._ensure_chatbot",
                side_effect=AssertionError("clear should not initialize chat"),
            ) as ensure_chatbot:
                response = self.client.post("/chat/clear")
        finally:
            server_api_main._chat_history[:] = original_history
            server_api_main._active_convo_id = original_active_convo_id

        self.assertEqual(response.status_code, 200)
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
        self.assertIn("Hey", payload["response"])
        self.assertIn("I would probably", payload["response"])
        self.assertNotIn("Next:", payload["response"])
        self.assertNotIn("Tell me the job", payload["response"])
        self.assertNotIn("Supervisor Agent", payload["response"])
        self.assertNotIn("RESPONSE STYLE", payload["response"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["commands"], [])
        self.assertEqual(payload["intent"], "greeting")

    def test_agent_acknowledges_chat_tone_feedback_without_status_template(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "setup",
                "image_path": "/tmp/image.h5",
                "mask_path": "/tmp/mask.h5",
                "metadata": {
                    "project_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                    }
                },
            },
        )

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "ok cool, a bit of a robotic response though"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "style_feedback")
        self.assertIn("Yeah, agreed", payload["response"])
        self.assertIn("more conversational", payload["response"])
        self.assertIn("EM", payload["response"])
        self.assertIn("mitochondria", payload["response"])
        self.assertNotIn("My read:", payload["response"])
        self.assertNotIn("Current read:", payload["response"])
        self.assertNotIn("Why this fits:", payload["response"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["commands"], [])

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
        self.assertEqual(evaluation_payload["policy_decision"]["decision"], "allowed")
        self.assertTrue(evaluation_payload["policy_decision"]["requires_approval"])
        self.assertEqual(evaluation_payload["freshness"]["scope"], "evaluation")
        self.assertEqual(evaluation_payload["freshness"]["state"], "ready")
        compute_action = evaluation_payload["actions"][0]
        self.assertEqual(compute_action["id"], "compute-evaluation")
        self.assertEqual(compute_action["risk_level"], "writes_workflow_record")
        self.assertTrue(compute_action["requires_approval"])
        self.assertEqual(compute_action["policy_decision"]["decision"], "allowed")
        self.assertTrue(compute_action["policy_decision"]["requires_approval"])
        self.assertEqual(compute_action["freshness"]["scope"], "evaluation")
        self.assertEqual(compute_action["freshness"]["state"], "ready")
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

    def test_agent_evaluation_blocks_when_reference_mask_missing(self):
        workflow, _ = self._current_workflow()
        workflow_id = workflow["id"]
        self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "evaluation",
                "image_path": "/tmp/yixiao/eval-image.h5",
            },
        )

        baseline_response = self.client.post(
            f"/api/workflows/{workflow_id}/model-runs",
            json={
                "run_type": "inference",
                "status": "completed",
                "output_path": "/tmp/baseline-reference-case.tif",
            },
        )
        self.assertEqual(baseline_response.status_code, 200)
        candidate_response = self.client.post(
            f"/api/workflows/{workflow_id}/model-runs",
            json={
                "run_type": "inference",
                "status": "completed",
                "output_path": "/tmp/candidate-reference-case.tif",
            },
        )
        self.assertEqual(candidate_response.status_code, 200)

        response = self.client.post(
            f"/api/workflows/{workflow_id}/agent/query",
            json={"query": "compare results and compute metrics"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "compute_evaluation")
        self.assertIn("collect reference mask first.", payload["response"])
        self.assertEqual(payload["policy_decision"]["decision"], "blocked")
        self.assertFalse(payload["policy_decision"]["requires_approval"])
        self.assertEqual(
            payload["policy_decision"]["reason_code"],
            "evaluation_missing_inputs",
        )
        self.assertEqual(payload["actions"][0]["id"], "show-evaluation-status")
        self.assertEqual(
            payload["actions"][0]["policy_decision"]["decision"],
            "blocked",
        )
        self.assertFalse(payload["actions"][0]["policy_decision"]["requires_approval"])
        self.assertEqual(
            payload["blocking_reasons"][0]["code"],
            "evaluation.missing_reference_mask",
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
            export_payload["actions"][0]["policy_decision"]["decision"], "allowed"
        )
        self.assertTrue(
            export_payload["actions"][0]["policy_decision"]["requires_approval"]
        )
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
