import pathlib
import tempfile
import unittest

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
from server_api.main import app as server_api_app


class WorkflowCaseStudyAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp_dir.name)
        self.db_path = self.root / "workflow-case-study.db"
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

    def _workflow_id(self):
        response = self.client.get("/api/workflows/current")
        self.assertEqual(response.status_code, 200)
        return response.json()["workflow"]["id"]

    def _write_file(self, name: str, content: str = "artifact") -> str:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_synthetic_closed_loop_reaches_case_study_readiness(self):
        workflow_id = self._workflow_id()
        image_path = self._write_file("image.tif")
        mask_path = self._write_file("mask.tif")
        corrected_path = self._write_file("corrected-mask.tif")
        training_output = self._write_file("training-output")
        checkpoint_path = self._write_file("checkpoint.pth")
        report_path = self.root / "before-after-report.json"

        ground_truth_path = self.root / "ground-truth.tif"
        baseline_path = self.root / "baseline-prediction.tif"
        candidate_path = self.root / "candidate-prediction.tif"
        ground_truth = np.zeros((1, 4, 4), dtype=np.uint8)
        ground_truth[:, 1:3, 1:3] = 1
        baseline = np.zeros_like(ground_truth)
        baseline[:, 1:2, 1:2] = 1
        candidate = ground_truth.copy()
        tifffile.imwrite(str(ground_truth_path), ground_truth)
        tifffile.imwrite(str(baseline_path), baseline)
        tifffile.imwrite(str(candidate_path), candidate)

        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "dataset.loaded",
                "stage": "visualization",
                "summary": "Loaded sample image and mask.",
                "payload": {"image_path": image_path, "mask_path": mask_path},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "inference.completed",
                "stage": "inference",
                "summary": "Baseline inference completed.",
                "payload": {"outputPath": str(baseline_path)},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "proofreading.instance_classified",
                "stage": "proofreading",
                "summary": "Marked a top hotspot as incorrect.",
                "payload": {"region_id": "z:1", "classification": "incorrect"},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "proofreading.mask_saved",
                "stage": "proofreading",
                "summary": "Saved corrected hotspot mask.",
                "payload": {"region_id": "z:1", "instance_id": 42},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "proofreading.masks_exported",
                "stage": "proofreading",
                "summary": "Exported corrected masks.",
                "payload": {"written_path": corrected_path, "region_id": "z:1"},
            },
        )
        self.client.get(f"/api/workflows/{workflow_id}/hotspots")

        proposal = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions",
            json={
                "action": "stage_retraining_from_corrections",
                "summary": "Stage corrections for retraining.",
                "payload": {"corrected_mask_path": corrected_path},
            },
        ).json()
        approve_proposal = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions/{proposal['id']}/approve"
        )
        self.assertEqual(approve_proposal.status_code, 200)

        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "training.completed",
                "stage": "evaluation",
                "summary": "Retraining completed.",
                "payload": {
                    "outputPath": training_output,
                    "checkpointPath": checkpoint_path,
                    "checkpointName": "checkpoint.pth",
                },
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "inference.completed",
                "stage": "evaluation",
                "summary": "Candidate inference completed.",
                "payload": {
                    "outputPath": str(candidate_path),
                    "checkpointPath": checkpoint_path,
                },
            },
        )

        plan = self.client.post(
            f"/api/workflows/{workflow_id}/agent-plans",
            json={"title": "Synthetic case-study loop"},
        ).json()
        approve_plan = self.client.post(
            f"/api/workflows/{workflow_id}/agent-plans/{plan['id']}/approve"
        )
        self.assertEqual(approve_plan.status_code, 200)

        evaluation = self.client.post(
            f"/api/workflows/{workflow_id}/evaluation-results/compute",
            json={
                "name": "case-study-before-after",
                "ground_truth_path": str(ground_truth_path),
                "baseline_prediction_path": str(baseline_path),
                "candidate_prediction_path": str(candidate_path),
                "report_path": str(report_path),
            },
        )
        self.assertEqual(evaluation.status_code, 200)
        self.assertTrue(
            evaluation.json()["metrics"]["summary"]["candidate_improved_dice"]
        )

        readiness = self.client.get(
            f"/api/workflows/{workflow_id}/case-study-readiness"
        )
        self.assertEqual(readiness.status_code, 200)
        readiness_payload = readiness.json()
        self.assertTrue(readiness_payload["ready_for_case_study"])
        self.assertEqual(readiness_payload["next_required_items"], [])

        bundle = self.client.post(f"/api/workflows/{workflow_id}/export-bundle").json()
        self.assertGreaterEqual(len(bundle["events"]), 10)
        self.assertEqual(len(bundle["agent_plans"]), 1)
        self.assertGreaterEqual(len(bundle["model_runs"]), 3)
        self.assertEqual(len(bundle["model_versions"]), 1)
        self.assertEqual(len(bundle["evaluation_results"]), 1)


if __name__ == "__main__":
    unittest.main()
