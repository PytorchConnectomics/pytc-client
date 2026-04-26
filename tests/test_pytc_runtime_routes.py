import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database as auth_database
from server_api.auth import models
from server_api.main import app as server_api_app
from server_pytc.main import app as server_pytc_app
from server_pytc.services import model as model_service


class FakeResponse:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class ServerPytcRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server_pytc_app)

    def tearDown(self):
        model_service.stop_tensorboard(clear_sources=True)

    def test_inference_status_route_returns_worker_payload(self):
        payload = {"isRunning": True, "pid": 1234, "exitCode": None}
        with patch("server_pytc.main.get_inference_status", return_value=payload):
            response = self.client.get("/inference_status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def test_start_tensorboard_without_registered_sources_returns_400(self):
        with patch(
            "server_pytc.main.initialize_tensorboard",
            side_effect=ValueError("No TensorBoard log directory is registered yet."),
        ):
            response = self.client.get("/start_tensorboard")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"], "No TensorBoard log directory is registered yet."
        )

    def test_tensorboard_status_route_returns_worker_payload(self):
        payload = {
            "isRunning": True,
            "phase": "running",
            "pid": 4321,
            "url": "http://127.0.0.1:6006/",
            "sources": {"training": {"name": "training", "path": "/tmp/out"}},
        }
        with patch("server_pytc.main.get_tensorboard_status", return_value=payload):
            response = self.client.get("/get_tensorboard_status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def test_training_logs_route_returns_worker_payload(self):
        payload = {"phase": "running", "text": "hello", "lines": ["hello"]}
        with patch(
            "server_pytc.main.get_training_process_logs", return_value=payload
        ):
            response = self.client.get("/training_logs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def test_inference_logs_route_returns_worker_payload(self):
        payload = {"phase": "failed", "text": "boom", "lines": ["boom"]}
        with patch("server_pytc.main.get_inference_logs", return_value=payload):
            response = self.client.get("/inference_logs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)


class ServerApiProxyTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server_api_app)

    def test_synanno_route_is_not_mounted(self):
        response = self.client.get("/api/synanno/ng-url/1")

        self.assertEqual(response.status_code, 404)

    def test_inference_status_proxy_returns_worker_payload(self):
        payload = {"isRunning": False, "pid": None, "exitCode": 0}
        with patch(
            "server_api.main.requests.request",
            return_value=FakeResponse(200, payload=payload),
        ) as request_mock:
            response = self.client.get("/inference_status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        request_mock.assert_called_once()

    def test_start_tensorboard_proxy_propagates_worker_client_error(self):
        worker_payload = {
            "detail": "No TensorBoard log directory is registered yet."
        }
        with patch(
            "server_api.main.requests.request",
            return_value=FakeResponse(400, payload=worker_payload),
        ):
            response = self.client.get("/start_tensorboard")

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["upstream_status"], 400)
        self.assertEqual(detail["upstream_body"], worker_payload)

    def test_tensorboard_status_proxy_returns_worker_payload(self):
        payload = {
            "isRunning": False,
            "phase": "stopped",
            "pid": None,
            "url": None,
            "sources": {
                "training": {
                    "name": "training",
                    "path": "/tmp/train",
                    "exists": True,
                }
            },
        }
        with patch(
            "server_api.main.requests.request",
            return_value=FakeResponse(200, payload=payload),
        ):
            response = self.client.get("/get_tensorboard_status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def test_start_model_training_proxy_returns_504_on_timeout(self):
        with patch(
            "server_api.main.requests.request",
            side_effect=requests.exceptions.Timeout(),
        ):
            response = self.client.post(
                "/start_model_training",
                json={"trainingConfig": "DATASET: {}", "outputPath": "/tmp/out"},
            )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["detail"]["error"], "Timeout")

    def test_training_logs_proxy_returns_worker_payload(self):
        payload = {"phase": "running", "text": "runtime", "lines": ["runtime"]}
        with patch(
            "server_api.main.requests.request",
            return_value=FakeResponse(200, payload=payload),
        ):
            response = self.client.get("/training_logs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)


class WorkflowInferenceRuntimeSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "workflow-runtime-sync.db"
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

    def test_sync_completed_inference_runtime_materializes_prediction_run(self):
        workflow_id = self._workflow_id()
        output_dir = pathlib.Path(self.temp_dir.name) / "inference-output"
        output_dir.mkdir()
        prediction = output_dir / "result_xy.h5"
        checkpoint = output_dir / "checkpoint_00001.pth.tar"
        prediction.write_text("prediction", encoding="utf-8")
        checkpoint.write_text("checkpoint", encoding="utf-8")

        runtime_payload = {
            "phase": "finished",
            "pid": None,
            "exitCode": 0,
            "configPath": "/tmp/staged-inference.yaml",
            "configOriginPath": "configs/MitoEM/Mito25-Local-Smoke-BC.yaml",
            "startedAt": "2026-04-25T10:00:00+00:00",
            "endedAt": "2026-04-25T10:01:00+00:00",
            "lineCount": 12,
            "metadata": {
                "outputPath": str(output_dir),
                "checkpointPath": str(checkpoint),
            },
        }

        with patch("server_api.main._proxy_to_worker", return_value=runtime_payload):
            response = self.client.post(
                f"/api/workflows/{workflow_id}/sync-inference-runtime",
                json={},
            )
            duplicate_response = self.client.post(
                f"/api/workflows/{workflow_id}/sync-inference-runtime",
                json={},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["synced"])
        self.assertEqual(payload["outputPath"], str(prediction.resolve()))
        self.assertFalse(payload["deduplicated"])
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertTrue(duplicate_response.json()["deduplicated"])

        runs_response = self.client.get(
            f"/api/workflows/{workflow_id}/model-runs?run_type=inference"
        )
        self.assertEqual(runs_response.status_code, 200)
        runs = runs_response.json()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "completed")
        self.assertEqual(runs[0]["output_path"], str(prediction.resolve()))

        artifacts_response = self.client.get(
            f"/api/workflows/{workflow_id}/artifacts?artifact_type=inference_output"
        )
        self.assertEqual(artifacts_response.status_code, 200)
        artifacts = artifacts_response.json()
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["path"], str(prediction.resolve()))


class ModelServiceTests(unittest.TestCase):
    def tearDown(self):
        model_service.stop_tensorboard(clear_sources=True)
        model_service.cleanup_temp_files()
        model_service._reset_runtime_state("training")
        model_service._reset_runtime_state("inference")

    def test_write_temp_config_uses_origin_parent_for_relative_bases(self):
        config_path = model_service._write_temp_config(
            "foo: bar\n",
            "training",
            config_origin_path="configs/SNEMI/SNEMI-Base.yaml",
        )
        written_path = pathlib.Path(config_path)
        expected_parent = (
            model_service._project_root() / "pytorch_connectomics" / "configs" / "SNEMI"
        )

        self.assertTrue(written_path.exists())
        self.assertEqual(written_path.parent, expected_parent)

    def test_register_tensorboard_source_builds_named_logdir_spec(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            training_dir = pathlib.Path(tmpdir) / "train"
            inference_dir = pathlib.Path(tmpdir) / "infer"

            first = model_service._register_tensorboard_source(
                "training",
                str(training_dir),
            )
            second = model_service._register_tensorboard_source(
                "inference",
                str(inference_dir),
            )

            self.assertTrue(pathlib.Path(first).exists())
            self.assertTrue(pathlib.Path(second).exists())
            self.assertEqual(
                model_service._build_tensorboard_logdir_spec(),
                f"inference:{pathlib.Path(second).resolve()},training:{pathlib.Path(first).resolve()}",
            )

    def test_runtime_log_lines_are_exported_to_app_event_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = pathlib.Path(tmpdir) / "app-events.jsonl"
            previous = os.environ.get("PYTC_APP_EVENT_LOG_PATH")
            os.environ["PYTC_APP_EVENT_LOG_PATH"] = str(log_path)
            try:
                model_service._reset_runtime_state("training", phase="starting")
                model_service._update_runtime_state("training", pid=12345)
                model_service._append_runtime_event("training", "Config origin: foo.yaml")
                model_service._append_runtime_log(
                    "training",
                    "UnicodeDecodeError: invalid start byte",
                    event="runtime_output_line",
                    source="subprocess",
                    stream="stdout",
                )
            finally:
                if previous is None:
                    os.environ.pop("PYTC_APP_EVENT_LOG_PATH", None)
                else:
                    os.environ["PYTC_APP_EVENT_LOG_PATH"] = previous

            records = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(records[0]["event"], "runtime_event")
            self.assertEqual(records[0]["runtime_kind"], "training")
            self.assertEqual(records[0]["runtime_phase"], "starting")
            self.assertEqual(records[0]["runtime_pid"], 12345)
            self.assertEqual(records[1]["event"], "runtime_output_line")
            self.assertEqual(records[1]["level"], "ERROR")
            self.assertEqual(records[1]["source"], "subprocess")
            self.assertEqual(records[1]["stream"], "stdout")

    def test_detect_chunk_tile_mismatch_for_direct_h5_volume(self):
        diagnostic = model_service._detect_chunk_tile_mismatch(
            """
DATASET:
  DO_CHUNK_TITLE: 1
  IMAGE_NAME: /tmp/train-volume.h5
  LABEL_NAME: /tmp/train-label.h5
"""
        )

        self.assertIsNotNone(diagnostic)
        self.assertEqual(
            diagnostic["code"], "tile_dataset_direct_volume_mismatch"
        )
        self.assertIn("TileDataset", diagnostic["message"])
        self.assertEqual(diagnostic["image_name"], "/tmp/train-volume.h5")

    def test_sanitize_runtime_config_restores_fractional_values_and_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            image_path = tmp_root / "pair_im.h5"
            label_path = tmp_root / "pair_seg.h5"
            infer_path = tmp_root / "pair2_im.h5"
            for path in (image_path, label_path, infer_path):
                path.write_text("placeholder", encoding="utf-8")

            origin_config = tmp_root / "origin.yaml"
            origin_config.write_text(
                "\n".join(
                    [
                        "DATASET:",
                        f"  IMAGE_NAME: {image_path}",
                        f"  LABEL_NAME: {label_path}",
                        "  VALID_RATIO: 0.5",
                        "  REJECT_SAMPLING:",
                        "    P: 0.95",
                        "INFERENCE:",
                        f"  IMAGE_NAME: {infer_path}",
                        "  AUG_NUM: 4",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            corrupted_config = "\n".join(
                [
                    "DATASET:",
                    f"  IMAGE_NAME: {image_path.with_name('pair.h5')}",
                    f"  LABEL_NAME: {label_path.with_name('pair.h5')}",
                    "  VALID_RATIO: 0",
                    "  REJECT_SAMPLING:",
                    "    P: 0",
                    "INFERENCE:",
                    f"  IMAGE_NAME: {infer_path.with_name('pair2.h5')}",
                    "  AUG_NUM: 1",
                    "",
                ]
            )

            sanitized_text, changes = model_service._sanitize_runtime_config_text(
                corrupted_config,
                str(origin_config),
            )
            sanitized = model_service._load_yaml_config(sanitized_text)

            self.assertEqual(sanitized["DATASET"]["IMAGE_NAME"], str(image_path))
            self.assertEqual(sanitized["DATASET"]["LABEL_NAME"], str(label_path))
            self.assertEqual(sanitized["INFERENCE"]["IMAGE_NAME"], str(infer_path))
            self.assertEqual(sanitized["DATASET"]["VALID_RATIO"], 0.5)
            self.assertEqual(sanitized["DATASET"]["REJECT_SAMPLING"]["P"], 0.95)
            self.assertEqual(sanitized["INFERENCE"]["AUG_NUM"], 4)
            self.assertGreaterEqual(len(changes), 5)

    def test_runtime_error_lines_update_last_error(self):
        model_service._reset_runtime_state("training", phase="running")
        model_service._append_runtime_log(
            "training",
            "ValueError: boom",
            event="runtime_output_line",
            source="subprocess",
            stream="stdout",
        )

        snapshot = model_service.get_training_status()
        self.assertEqual(snapshot["lastError"], "ValueError: boom")

    def test_find_latest_checkpoint_returns_newest_training_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = pathlib.Path(tmpdir)
            older = output_dir / "checkpoint_00050.pth.tar"
            newer = output_dir / "checkpoint_00200.pth.tar"
            older.write_text("older", encoding="utf-8")
            newer.write_text("newer", encoding="utf-8")

            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))

            latest = model_service._find_latest_checkpoint(str(output_dir))

            self.assertEqual(latest, str(newer.resolve()))

    def test_training_snapshot_backfills_checkpoint_metadata_after_exit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = pathlib.Path(tmpdir)
            checkpoint_path = output_dir / "checkpoint_00010.pth.tar"
            checkpoint_path.write_text("checkpoint", encoding="utf-8")

            model_service._reset_runtime_state(
                "training",
                phase="finished",
                metadata={"outputPath": str(output_dir)},
            )

            snapshot = model_service.get_training_logs()

            self.assertEqual(
                snapshot["metadata"]["checkpointPath"],
                str(checkpoint_path.resolve()),
            )
            self.assertEqual(
                snapshot["metadata"]["latestCheckpointName"],
                checkpoint_path.name,
            )

    def test_find_latest_prediction_output_returns_newest_inference_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = pathlib.Path(tmpdir)
            older = output_dir / "prediction.h5"
            newer = output_dir / "result_xy.h5"
            older.write_text("older", encoding="utf-8")
            newer.write_text("newer", encoding="utf-8")

            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))

            latest = model_service._find_latest_prediction_output(str(output_dir))

            self.assertEqual(latest, str(newer.resolve()))

    def test_inference_snapshot_backfills_prediction_metadata_after_exit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = pathlib.Path(tmpdir)
            prediction_path = output_dir / "result_xy.h5"
            prediction_path.write_text("prediction", encoding="utf-8")

            model_service._reset_runtime_state(
                "inference",
                phase="finished",
                metadata={"outputPath": str(output_dir)},
            )

            snapshot = model_service.get_inference_logs()

            self.assertEqual(
                snapshot["metadata"]["predictionPath"],
                str(prediction_path.resolve()),
            )
            self.assertEqual(
                snapshot["metadata"]["latestPredictionName"],
                prediction_path.name,
            )


if __name__ == "__main__":
    unittest.main()
