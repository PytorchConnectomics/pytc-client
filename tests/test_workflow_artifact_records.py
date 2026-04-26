import pathlib
import tempfile
import unittest

import pytest
import numpy as np

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("fastapi")
tifffile = pytest.importorskip("tifffile")
h5py = pytest.importorskip("h5py")
from fastapi.testclient import TestClient

from server_api.auth import database as auth_database
from server_api.auth import models
from server_api.main import app as server_api_app


class WorkflowArtifactRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp_dir.name)
        self.db_path = self.root / "workflow-artifacts-test.db"
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

    def _write_file(self, name: str) -> str:
        path = self.root / name
        path.write_text(name, encoding="utf-8")
        return str(path)

    def test_events_materialize_artifacts_runs_versions_and_corrections(self):
        workflow_id = self._workflow_id()
        image_path = self._write_file("image.tif")
        mask_path = self._write_file("mask.tif")
        ground_truth_path = self._write_file("ground-truth.tif")
        corrected_path = self._write_file("corrected.tif")
        training_output = self._write_file("training-output")
        checkpoint_path = self._write_file("checkpoint.pth")

        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "dataset.loaded",
                "stage": "proofreading",
                "summary": "Loaded dataset.",
                "payload": {
                    "dataset_path": image_path,
                    "image_path": image_path,
                    "mask_path": mask_path,
                    "source_ground_truth_path": ground_truth_path,
                },
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "proofreading.mask_saved",
                "stage": "proofreading",
                "summary": "Saved first correction.",
                "payload": {"instance_id": 12, "z_index": 1},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "proofreading.mask_saved",
                "stage": "proofreading",
                "summary": "Saved second correction.",
                "payload": {"instance_id": 13, "z_index": 2},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "proofreading.masks_exported",
                "stage": "proofreading",
                "summary": "Exported corrections.",
                "payload": {"written_path": corrected_path},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "user",
                "event_type": "training.started",
                "stage": "retraining_staged",
                "summary": "Started training.",
                "payload": {"outputPath": training_output},
            },
        )
        self.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": "system",
                "event_type": "training.completed",
                "stage": "evaluation",
                "summary": "Training completed.",
                "payload": {
                    "outputPath": training_output,
                    "checkpointPath": checkpoint_path,
                    "checkpointName": "checkpoint.pth",
                },
            },
        )

        artifacts = self.client.get(f"/api/workflows/{workflow_id}/artifacts").json()
        artifact_types = {artifact["artifact_type"] for artifact in artifacts}
        self.assertIn("image_volume", artifact_types)
        self.assertIn("mask_volume", artifact_types)
        self.assertIn("correction_set", artifact_types)
        self.assertIn("model_checkpoint", artifact_types)
        ground_truth_artifacts = [
            artifact
            for artifact in artifacts
            if artifact["role"] == "ground_truth"
        ]
        self.assertEqual(ground_truth_artifacts[0]["path"], ground_truth_path)

        correction_sets = self.client.get(
            f"/api/workflows/{workflow_id}/correction-sets"
        ).json()
        self.assertEqual(len(correction_sets), 1)
        self.assertEqual(correction_sets[0]["corrected_mask_path"], corrected_path)
        self.assertEqual(correction_sets[0]["edit_count"], 2)
        self.assertEqual(correction_sets[0]["region_count"], 2)

        model_runs = self.client.get(f"/api/workflows/{workflow_id}/model-runs").json()
        self.assertEqual(len(model_runs), 1)
        self.assertEqual(model_runs[0]["run_type"], "training")
        self.assertEqual(model_runs[0]["status"], "completed")
        self.assertEqual(model_runs[0]["checkpoint_path"], checkpoint_path)

        model_versions = self.client.get(
            f"/api/workflows/{workflow_id}/model-versions"
        ).json()
        self.assertEqual(len(model_versions), 1)
        self.assertEqual(model_versions[0]["version_label"], "checkpoint.pth")

        bundle = self.client.post(f"/api/workflows/{workflow_id}/export-bundle").json()
        self.assertGreaterEqual(len(bundle["artifacts"]), 4)
        self.assertEqual(len(bundle["model_runs"]), 1)
        self.assertEqual(len(bundle["model_versions"]), 1)
        self.assertEqual(len(bundle["correction_sets"]), 1)

        events = self.client.get(f"/api/workflows/{workflow_id}/events").json()
        self.assertIn(
            "workflow.bundle_exported",
            {event["event_type"] for event in events},
        )

    def test_manual_evaluation_records_and_readiness_endpoint(self):
        workflow_id = self._workflow_id()
        report_path = self._write_file("eval-report.json")

        artifact_response = self.client.post(
            f"/api/workflows/{workflow_id}/artifacts",
            json={
                "artifact_type": "evaluation_report",
                "role": "case_study_evidence",
                "path": report_path,
            },
        )
        self.assertEqual(artifact_response.status_code, 200)
        self.assertTrue(artifact_response.json()["exists"])

        run_response = self.client.post(
            f"/api/workflows/{workflow_id}/model-runs",
            json={
                "run_type": "inference",
                "status": "completed",
                "output_path": self._write_file("prediction.tif"),
            },
        )
        self.assertEqual(run_response.status_code, 200)

        evaluation_response = self.client.post(
            f"/api/workflows/{workflow_id}/evaluation-results",
            json={
                "name": "before-after-smoke",
                "candidate_run_id": run_response.json()["id"],
                "report_path": report_path,
                "summary": "Smoke comparison completed.",
                "metrics": {"dice": 0.75},
            },
        )
        self.assertEqual(evaluation_response.status_code, 200)
        self.assertEqual(evaluation_response.json()["metrics"]["dice"], 0.75)

        readiness_response = self.client.get(
            f"/api/workflows/{workflow_id}/case-study-readiness"
        )
        self.assertEqual(readiness_response.status_code, 200)
        readiness = readiness_response.json()
        self.assertEqual(readiness["workflow_id"], workflow_id)
        self.assertEqual(readiness["total_count"], len(readiness["gates"]))
        self.assertIn("next_required_items", readiness)

    def test_compute_evaluation_result_records_before_after_metrics(self):
        workflow_id = self._workflow_id()
        ground_truth_path = self.root / "ground-truth.tif"
        baseline_path = self.root / "baseline-prediction.tif"
        candidate_path = self.root / "candidate-prediction.tif"
        report_path = self.root / "computed-eval.json"

        ground_truth = np.zeros((1, 4, 4), dtype=np.uint8)
        ground_truth[:, 1:3, 1:3] = 1
        baseline = np.zeros_like(ground_truth)
        baseline[:, 1:2, 1:2] = 1
        candidate = ground_truth.copy()
        tifffile.imwrite(str(ground_truth_path), ground_truth)
        tifffile.imwrite(str(baseline_path), baseline)
        tifffile.imwrite(str(candidate_path), candidate)

        response = self.client.post(
            f"/api/workflows/{workflow_id}/evaluation-results/compute",
            json={
                "name": "computed-before-after",
                "ground_truth_path": str(ground_truth_path),
                "baseline_prediction_path": str(baseline_path),
                "candidate_prediction_path": str(candidate_path),
                "report_path": str(report_path),
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "computed-before-after")
        self.assertTrue(payload["metrics"]["summary"]["candidate_improved_dice"])
        self.assertGreater(payload["metrics"]["delta"]["dice"], 0)
        self.assertTrue(report_path.exists())

    def test_compute_evaluation_result_supports_hdf5_dataset_keys_and_crop(self):
        workflow_id = self._workflow_id()
        ground_truth_path = self.root / "ground-truth.h5"
        baseline_path = self.root / "baseline-prediction.h5"
        candidate_path = self.root / "candidate-prediction.h5"

        ground_truth = np.zeros((4, 8, 8), dtype=np.uint16)
        ground_truth[:, 2:6, 2:6] = 1
        baseline = ground_truth.copy()
        baseline[:, :, :3] = 0
        candidate = ground_truth.copy()
        for path, dataset, array in [
            (ground_truth_path, "data", ground_truth),
            (baseline_path, "prediction", baseline),
            (candidate_path, "prediction", candidate),
        ]:
            with h5py.File(path, "w") as handle:
                handle.create_dataset(dataset, data=array)

        response = self.client.post(
            f"/api/workflows/{workflow_id}/evaluation-results/compute",
            json={
                "name": "computed-hdf5-before-after",
                "ground_truth_path": str(ground_truth_path),
                "ground_truth_dataset": "data",
                "baseline_prediction_path": str(baseline_path),
                "baseline_dataset": "prediction",
                "candidate_prediction_path": str(candidate_path),
                "candidate_dataset": "prediction",
                "crop": "0:2,0:8,0:8",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["metrics"]["summary"]["candidate_improved_dice"])
        self.assertEqual(payload["metadata"]["ground_truth_dataset"], "data")
        self.assertEqual(payload["metadata"]["crop"], "0:2,0:8,0:8")

    def test_compute_evaluation_result_supports_prediction_channel_selection(self):
        workflow_id = self._workflow_id()
        ground_truth_path = self.root / "ground-truth.h5"
        baseline_path = self.root / "baseline-result_xy.h5"
        candidate_path = self.root / "candidate-result_xy.h5"

        ground_truth = np.zeros((4, 8, 8), dtype=np.uint16)
        ground_truth[:, 2:6, 2:6] = 1
        baseline_mask = ground_truth.copy()
        baseline_mask[:, :, :4] = 0
        candidate_mask = ground_truth.copy()
        baseline = np.stack([np.zeros_like(ground_truth), baseline_mask])
        candidate = np.stack([np.zeros_like(ground_truth), candidate_mask])
        for path, dataset, array in [
            (ground_truth_path, "data", ground_truth),
            (baseline_path, "vol0", baseline),
            (candidate_path, "vol0", candidate),
        ]:
            with h5py.File(path, "w") as handle:
                handle.create_dataset(dataset, data=array)

        response = self.client.post(
            f"/api/workflows/{workflow_id}/evaluation-results/compute",
            json={
                "name": "computed-channel-before-after",
                "ground_truth_path": str(ground_truth_path),
                "ground_truth_dataset": "data",
                "baseline_prediction_path": str(baseline_path),
                "baseline_dataset": "vol0",
                "baseline_channel": 1,
                "candidate_prediction_path": str(candidate_path),
                "candidate_dataset": "vol0",
                "candidate_channel": 1,
                "crop": "0:2,0:8,0:8",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["metrics"]["summary"]["candidate_improved_dice"])
        self.assertGreater(payload["metrics"]["delta"]["dice"], 0)
        self.assertEqual(payload["metadata"]["baseline_channel"], 1)
        self.assertEqual(payload["metadata"]["candidate_channel"], 1)


if __name__ == "__main__":
    unittest.main()
