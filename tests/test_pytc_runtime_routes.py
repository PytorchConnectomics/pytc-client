import json
import pathlib
import unittest
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient

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

    def test_inference_status_route_returns_worker_payload(self):
        payload = {"isRunning": True, "pid": 1234, "exitCode": None}
        with patch("server_pytc.main.get_inference_status", return_value=payload):
            response = self.client.get("/inference_status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def test_start_tensorboard_without_log_path_returns_400(self):
        response = self.client.get("/start_tensorboard")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"], "Missing required query parameter: logPath"
        )

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
        worker_payload = {"detail": "Missing required query parameter: logPath"}
        with patch(
            "server_api.main.requests.request",
            return_value=FakeResponse(400, payload=worker_payload),
        ):
            response = self.client.get("/start_tensorboard")

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["upstream_status"], 400)
        self.assertEqual(detail["upstream_body"], worker_payload)

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


class ModelServiceTests(unittest.TestCase):
    def tearDown(self):
        model_service.cleanup_temp_files()

    def test_write_temp_config_uses_origin_parent_for_relative_bases(self):
        config_path = model_service._write_temp_config(
            "foo: bar\n",
            "training",
            config_origin_path="tutorials/neuron_snemi.yaml",
        )
        written_path = pathlib.Path(config_path)
        expected_parent = (
            model_service._project_root() / "pytorch_connectomics" / "tutorials"
        )

        self.assertTrue(written_path.exists())
        self.assertEqual(written_path.parent, expected_parent)


if __name__ == "__main__":
    unittest.main()
