import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import requests
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database as auth_database
from server_api.auth import models
from server_api.main import app as server_api_app
from server_api.main import (
    UM_NEUROGLANCER_MASK_RED_SHADER,
    UM_NEUROGLANCER_RAW_IMAGE_SHADER,
    _build_neuroglancer_layer,
    _has_single_neuroglancer_main,
    _resolve_mask_image_shader,
    _resolve_raw_image_shader,
)
from server_api.main import _coerce_neuroglancer_scales
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


class DummyLocalVolume:
    def __init__(self, data, dimensions, volume_type, voxel_offset, **_kwargs):
        self.data = data
        self.dimensions = dimensions
        self.volume_type = volume_type
        self.voxel_offset = tuple(voxel_offset)
        self.shader = None


class DummyImageLayer:
    def __init__(self, source, shader=None, **_kwargs):
        self.source = source
        self.shader = shader


class DummySegmentationLayer:
    def __init__(self, source, **kwargs):
        self.source = source
        self.kwargs = kwargs


class DummyNeuroglancerModule:
    def __init__(self, include_image_layer=True):
        self.LocalVolume = DummyLocalVolume
        self.SegmentationLayer = DummySegmentationLayer
        if include_image_layer:
            self.ImageLayer = DummyImageLayer


class NeuroglancerShaderBehaviorTests(unittest.TestCase):
    def test_raw_image_shader_resolver_matches_constant(self):
        self.assertEqual(_resolve_raw_image_shader(), UM_NEUROGLANCER_RAW_IMAGE_SHADER)

    def test_mask_shader_resolver_matches_constant(self):
        self.assertEqual(_resolve_mask_image_shader(), UM_NEUROGLANCER_MASK_RED_SHADER)

    def test_raw_um_shader_shape_and_controls(self):
        self.assertIn("#uicontrol invlerp normalized", UM_NEUROGLANCER_RAW_IMAGE_SHADER)
        self.assertIn(
            "#uicontrol float contrast slider(min=-3, max=3, step=0.01)",
            UM_NEUROGLANCER_RAW_IMAGE_SHADER,
        )
        self.assertIn("emitGrayscale((normalized() + brightness) * exp(contrast));", UM_NEUROGLANCER_RAW_IMAGE_SHADER)
        self.assertTrue(_has_single_neuroglancer_main(UM_NEUROGLANCER_RAW_IMAGE_SHADER))

    def test_mask_red_shader_shape_and_controls(self):
        self.assertIn("emitRGB(vec3(1.0, 0.0, 0.0));", UM_NEUROGLANCER_MASK_RED_SHADER)
        self.assertTrue(_has_single_neuroglancer_main(UM_NEUROGLANCER_MASK_RED_SHADER))

    def test_shader_builder_keeps_segmentation_layers_without_image_shader(self):
        module = DummyNeuroglancerModule()
        source = _build_neuroglancer_layer(
            module,
            data="mask",
            dimensions=(40, 16, 16),
            volume_type="segmentation",
            segmentation_kwargs={"object_alpha": 0.4},
        )
        self.assertIsInstance(source, DummySegmentationLayer)
        self.assertEqual(source.source.volume_type, "segmentation")
        self.assertEqual(source.source.shader, None)

    def test_shader_builder_uses_red_mask_shader_for_image_like_mask_layer(self):
        module = DummyNeuroglancerModule(include_image_layer=True)
        source = _build_neuroglancer_layer(
            module,
            data="mask",
            dimensions=(40, 16, 16),
            volume_type="image",
            image_shader=UM_NEUROGLANCER_MASK_RED_SHADER,
        )
        self.assertIsInstance(source, DummyImageLayer)
        self.assertEqual(source.shader, UM_NEUROGLANCER_MASK_RED_SHADER)

    def test_shader_builder_fallback_to_source_shader_when_imagelayer_missing(self):
        module = DummyNeuroglancerModule(include_image_layer=False)
        source = _build_neuroglancer_layer(
            module,
            data="mask",
            dimensions=(40, 16, 16),
            volume_type="image",
            image_shader=UM_NEUROGLANCER_MASK_RED_SHADER,
        )
        self.assertIsInstance(source, DummyLocalVolume)
        self.assertEqual(source.shader, UM_NEUROGLANCER_MASK_RED_SHADER)
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

    def test_neuroglancer_scale_validation_requires_finite_positive_zyx(self):
        self.assertEqual(
            _coerce_neuroglancer_scales(["40", 4, 4.0]),
            [40.0, 4.0, 4.0],
        )

        for invalid_scales in (None, [1, 1], [1, 1, 0], [1, -1, 1], [1, 1, "nan"]):
            with self.subTest(scales=invalid_scales):
                with self.assertRaises(HTTPException):
                    _coerce_neuroglancer_scales(invalid_scales)

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

    def test_pytc_config_route_allows_project_config_under_allowed_root(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_root = pathlib.Path(tmp_dir) / "demo-project"
            config_path = config_root / "configs" / "Project.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("DATASET: {}\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {"PYTC_ADDITIONAL_CONFIG_ROOTS": str(config_root)},
            ):
                response = self.client.get(
                    "/pytc/config",
                    params={"path": str(config_path)},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["path"], str(config_path))
        self.assertEqual(response.json()["content"], "DATASET: {}\n")

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

    def test_worker_proxy_logs_connection_failures(self):
        with patch(
            "server_api.main.requests.request",
            side_effect=requests.exceptions.ConnectionError("connection refused"),
        ), patch("server_api.main.append_app_event") as log_event:
            response = self.client.get("/training_status")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["error"], "ConnectionError")
        failure_events = [
            call.kwargs
            for call in log_event.call_args_list
            if call.kwargs.get("event") == "worker_proxy_request_failed"
        ]
        self.assertTrue(failure_events)
        self.assertEqual(failure_events[-1]["error"], "ConnectionError")
        self.assertIn("/training_status", failure_events[-1]["path"])

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

    def test_start_training_uses_workflow_paths_when_explicit_paths_are_stale(self):
        workflow_id = self._workflow_id()
        project_root = pathlib.Path(self.temp_dir.name) / "project"
        image_path = project_root / "data" / "image" / "test_im.h5"
        label_path = project_root / "data" / "seg" / "test_mito.h5"
        output_path = project_root / "outputs" / "training"
        image_path.parent.mkdir(parents=True)
        label_path.parent.mkdir(parents=True)
        output_path.mkdir(parents=True)
        image_path.write_text("image", encoding="utf-8")
        label_path.write_text("label", encoding="utf-8")

        update_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "image_path": str(image_path),
                "label_path": str(label_path),
            },
        )
        self.assertEqual(update_response.status_code, 200)

        captured = {}

        def fake_worker(method, endpoint, json_body=None, **_kwargs):
            captured["method"] = method
            captured["endpoint"] = endpoint
            captured["json_body"] = json_body
            return {"phase": "starting"}

        with patch("server_api.main._proxy_to_worker", side_effect=fake_worker):
            response = self.client.post(
                "/start_model_training",
                json={
                    "workflowId": workflow_id,
                    "trainingConfig": "DATASET: {}\n",
                    "inputImagePath": str(project_root / "data" / "image" / "old.h5"),
                    "inputLabelPath": str(
                        project_root / "data" / "seg" / ".pytc_instance_labels.tif"
                    ),
                    "outputPath": str(output_path),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["method"], "post")
        self.assertEqual(captured["endpoint"], "/start_model_training")
        self.assertEqual(
            captured["json_body"]["inputImagePath"], str(image_path.resolve())
        )
        self.assertEqual(
            captured["json_body"]["inputLabelPath"], str(label_path.resolve())
        )

    def test_durable_training_command_runner_launches_worker_and_records_state(self):
        workflow_id = self._workflow_id()
        project_root = pathlib.Path(self.temp_dir.name) / "project"
        image_path = project_root / "data" / "image" / "train_im.h5"
        label_path = project_root / "data" / "seg" / "corrected.tif"
        output_path = project_root / "outputs" / "training"
        image_path.parent.mkdir(parents=True)
        label_path.parent.mkdir(parents=True)
        output_path.mkdir(parents=True)
        image_path.write_text("image", encoding="utf-8")
        label_path.write_text("label", encoding="utf-8")

        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "stage": "retraining_staged",
                "image_path": str(image_path),
                "corrected_mask_path": str(label_path),
            },
        )
        self.assertEqual(patch_response.status_code, 200)
        client_effects = {
            "runtime_action": {
                "kind": "start_training",
                "autopick_parameters": True,
                "parameter_mode": "agent_default",
            },
            "set_training_config_preset": "configs/MitoEM/Mito-CaseStudy-BC.yaml",
            "set_training_image_path": str(image_path),
            "set_training_label_path": str(label_path),
            "set_training_output_path": str(output_path),
            "set_training_log_path": str(output_path),
        }
        proposal = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions",
            json={
                "action": "start_training_run",
                "payload": {
                    "client_effects": client_effects,
                    "config_preset": client_effects["set_training_config_preset"],
                    "image_path": str(image_path),
                    "label_path": str(label_path),
                    "output_path": str(output_path),
                },
            },
        )
        self.assertEqual(proposal.status_code, 200)
        approval = self.client.post(
            f"/api/workflows/{workflow_id}/agent-actions/"
            f"{proposal.json()['id']}/approve"
        )
        self.assertEqual(approval.status_code, 200)
        command = approval.json()["commands"][0]
        captured = {}

        def fake_worker(method, endpoint, json_body=None, **_kwargs):
            captured["method"] = method
            captured["endpoint"] = endpoint
            captured["json_body"] = json_body
            return {"status": "started", "pid": 4242}

        with patch("server_api.main._proxy_to_worker", side_effect=fake_worker):
            run_response = self.client.post(
                f"/api/workflows/{workflow_id}/commands/{command['id']}/run"
            )

        self.assertEqual(run_response.status_code, 200)
        payload = run_response.json()
        self.assertEqual(payload["command"]["status"], "submitted")
        self.assertEqual(payload["command"]["attempt_count"], 1)
        self.assertEqual(payload["worker"]["pid"], 4242)
        self.assertEqual(captured["method"], "post")
        self.assertEqual(captured["endpoint"], "/start_model_training")
        self.assertEqual(captured["json_body"]["workflowId"], workflow_id)
        self.assertEqual(captured["json_body"]["command_id"], command["id"])
        self.assertEqual(
            captured["json_body"]["run_id"],
            f"workflow-command-{command['id']}",
        )
        self.assertIn("DATASET", captured["json_body"]["trainingConfig"])
        self.assertEqual(captured["json_body"]["inputImagePath"], str(image_path))
        self.assertEqual(captured["json_body"]["inputLabelPath"], str(label_path))

        commands_response = self.client.get(f"/api/workflows/{workflow_id}/commands")
        self.assertEqual(commands_response.status_code, 200)
        self.assertEqual(commands_response.json()[0]["status"], "submitted")

        events_response = self.client.get(f"/api/workflows/{workflow_id}/events")
        self.assertEqual(events_response.status_code, 200)
        started_events = [
            event
            for event in events_response.json()
            if event["event_type"] == "training.started"
        ]
        self.assertEqual(len(started_events), 1)
        self.assertEqual(started_events[0]["payload"]["command_id"], command["id"])
        self.assertEqual(
            started_events[0]["payload"]["run_id"],
            f"workflow-command-{command['id']}",
        )


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
            self.assertGreaterEqual(len(changes), 4)

    def test_runtime_path_overrides_update_inference_image_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            image_path = tmp_root / "test_im.h5"
            image_path.write_text("placeholder", encoding="utf-8")
            output_path = tmp_root / "outputs"

            config_text = "\n".join(
                [
                    "DATASET:",
                    "  INPUT_PATH: ''",
                    "  IMAGE_NAME: img/test_im.tif",
                    "INFERENCE:",
                    "  INPUT_PATH: null",
                    "  IMAGE_NAME: img/test_im.tif",
                    "  OUTPUT_PATH: outputs/Lucchi_UNet/test",
                    "",
                ]
            )

            rewritten_text, changes = model_service._apply_runtime_path_overrides(
                config_text,
                {
                    "inputImagePath": str(image_path),
                    "outputPath": str(output_path),
                },
                kind="inference",
            )
            rewritten = model_service._load_yaml_config(rewritten_text)

            self.assertEqual(rewritten["DATASET"]["IMAGE_NAME"], str(image_path))
            self.assertEqual(rewritten["INFERENCE"]["IMAGE_NAME"], str(image_path))
            self.assertEqual(rewritten["INFERENCE"]["OUTPUT_PATH"], str(output_path))
            self.assertEqual(rewritten["DATASET"]["INPUT_PATH"], "")
            self.assertEqual(rewritten["INFERENCE"]["INPUT_PATH"], "")
            self.assertGreaterEqual(len(changes), 4)

    def test_runtime_path_overrides_resolve_mounted_project_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir) / "prepilot_lucchi_pp"
            image_path = tmp_root / "data" / "image" / "test_im.h5"
            image_path.parent.mkdir(parents=True)
            image_path.write_text("placeholder", encoding="utf-8")
            previous_roots = model_service._DEFAULT_MOUNTED_PROJECT_ROOTS
            model_service._DEFAULT_MOUNTED_PROJECT_ROOTS = (tmp_root,)
            try:
                rewritten_text, _changes = model_service._apply_runtime_path_overrides(
                    "INFERENCE:\n  IMAGE_NAME: img/test_im.tif\n",
                    {
                        "inputImagePath": "prepilot_lucchi_pp/data/image/test_im.h5",
                    },
                    kind="inference",
                )
            finally:
                model_service._DEFAULT_MOUNTED_PROJECT_ROOTS = previous_roots

            rewritten = model_service._load_yaml_config(rewritten_text)
            self.assertEqual(
                rewritten["INFERENCE"]["IMAGE_NAME"],
                str(image_path.resolve()),
            )

    def test_runtime_path_overrides_expand_training_subset_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            image_dir = tmp_root / "subset" / "image"
            label_dir = tmp_root / "subset" / "seg"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            image_a = image_dir / "a_im.h5"
            image_b = image_dir / "b_im.h5"
            label_a = label_dir / "a_seg.h5"
            label_b = label_dir / "b_seg.h5"
            for path in (image_a, image_b, label_a, label_b):
                path.write_text("placeholder", encoding="utf-8")
            manifest_path = tmp_root / "subset" / "volume_subset_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "train_pairs": [
                            {
                                "subset_image_path": str(image_b),
                                "subset_segmentation_path": str(label_b),
                            },
                            {
                                "subset_image_path": str(image_a),
                                "subset_segmentation_path": str(label_a),
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            rewritten_text, changes = model_service._apply_runtime_path_overrides(
                "DATASET:\n  INPUT_PATH: .\n  IMAGE_NAME: old/image\n  LABEL_NAME: old/seg\n",
                {
                    "inputImagePath": str(image_dir),
                    "inputLabelPath": str(label_dir),
                },
                kind="training",
            )
            rewritten = model_service._load_yaml_config(rewritten_text)

            self.assertEqual(
                rewritten["DATASET"]["IMAGE_NAME"],
                [str(image_b.resolve()), str(image_a.resolve())],
            )
            self.assertEqual(
                rewritten["DATASET"]["LABEL_NAME"],
                [str(label_b.resolve()), str(label_a.resolve())],
            )
            self.assertEqual(rewritten["DATASET"]["INPUT_PATH"], "")
            self.assertTrue(
                any(
                    change["reason"] == "runtime_request_training_subset_manifest"
                    for change in changes
                )
            )

    def test_runtime_launch_validation_rejects_missing_training_label(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = pathlib.Path(tmpdir) / "train_im.h5"
            image_path.write_text("placeholder", encoding="utf-8")
            config_text = "\n".join(
                [
                    "DATASET:",
                    f"  IMAGE_NAME: {image_path}",
                    f"  LABEL_NAME: {pathlib.Path(tmpdir) / 'missing_label.tif'}",
                    "",
                ]
            )

            with self.assertRaises(FileNotFoundError):
                model_service._validate_runtime_launch_inputs(
                    config_text,
                    kind="training",
                )

    def test_runtime_launch_validation_accepts_existing_training_inputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = pathlib.Path(tmpdir) / "train_im.h5"
            label_path = pathlib.Path(tmpdir) / "train_mito.h5"
            image_path.write_text("placeholder", encoding="utf-8")
            label_path.write_text("placeholder", encoding="utf-8")
            config_text = "\n".join(
                [
                    "DATASET:",
                    f"  IMAGE_NAME: {image_path}",
                    f"  LABEL_NAME: {label_path}",
                    "",
                ]
            )

            model_service._validate_runtime_launch_inputs(
                config_text,
                kind="training",
            )

    def test_runtime_launch_validation_accepts_training_input_lists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            image_paths = [tmp_root / "train_a_im.h5", tmp_root / "train_b_im.h5"]
            label_paths = [tmp_root / "train_a_seg.h5", tmp_root / "train_b_seg.h5"]
            for path in [*image_paths, *label_paths]:
                path.write_text("placeholder", encoding="utf-8")
            config_text = "\n".join(
                [
                    "DATASET:",
                    "  IMAGE_NAME:",
                    *[f"    - {path}" for path in image_paths],
                    "  LABEL_NAME:",
                    *[f"    - {path}" for path in label_paths],
                    "",
                ]
            )

            model_service._validate_runtime_launch_inputs(
                config_text,
                kind="training",
            )

    def test_runtime_launch_validation_rejects_unexpanded_training_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_dir = pathlib.Path(tmpdir) / "image"
            label_dir = pathlib.Path(tmpdir) / "seg"
            image_dir.mkdir()
            label_dir.mkdir()
            config_text = "\n".join(
                [
                    "DATASET:",
                    f"  IMAGE_NAME: {image_dir}",
                    f"  LABEL_NAME: {label_dir}",
                    "",
                ]
            )

            with self.assertRaises(FileNotFoundError):
                model_service._validate_runtime_launch_inputs(
                    config_text,
                    kind="training",
                )

    def test_sanitize_runtime_config_applies_safe_training_defaults(self):
        config_text = "\n".join(
            [
                "MODEL:",
                "  INPUT_SIZE: [112, 112, 112]",
                "  OUTPUT_SIZE: [112, 112, 112]",
                "  FILTERS: [28, 36, 48, 64, 80]",
                "DATASET:",
                "  PAD_SIZE: [8, 28, 28]",
                "INFERENCE:",
                "  INPUT_SIZE: [112, 112, 112]",
                "  OUTPUT_SIZE: [112, 112, 112]",
                "  STRIDE: [56, 56, 56]",
                "  SAMPLES_PER_BATCH: 4",
                "  PAD_SIZE: [8, 28, 28]",
                "SOLVER:",
                "  SAMPLES_PER_BATCH: 2",
                "  ITERATION_SAVE: 5000",
                "  ITERATION_TOTAL: 100000",
                "SYSTEM:",
                "  NUM_CPUS: 1",
                "  NUM_GPUS: 1",
                "",
            ]
        )

        sanitized_text, changes = model_service._sanitize_runtime_config_text(
            config_text,
            None,
            auto_parameters=True,
        )
        sanitized = model_service._load_yaml_config(sanitized_text)

        self.assertEqual(sanitized["SOLVER"]["SAMPLES_PER_BATCH"], 1)
        self.assertEqual(sanitized["SOLVER"]["ITERATION_SAVE"], 80)
        self.assertEqual(sanitized["SOLVER"]["ITERATION_TOTAL"], 80)
        self.assertEqual(sanitized["SOLVER"]["ITERATION_VAL"], 80)
        self.assertEqual(sanitized["SYSTEM"]["NUM_CPUS"], 2)
        self.assertEqual(sanitized["SYSTEM"]["NUM_GPUS"], 1)
        self.assertEqual(sanitized["MODEL"]["INPUT_SIZE"], [65, 65, 65])
        self.assertEqual(sanitized["MODEL"]["OUTPUT_SIZE"], [65, 65, 65])
        self.assertEqual(sanitized["MODEL"]["FILTERS"], [8, 12, 16, 24, 32])
        self.assertEqual(sanitized["DATASET"]["PAD_SIZE"], [4, 16, 16])
        self.assertEqual(sanitized["INFERENCE"]["STRIDE"], [32, 32, 32])
        self.assertTrue(
            any(change["reason"] == "agent_safe_training_default" for change in changes)
        )

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
