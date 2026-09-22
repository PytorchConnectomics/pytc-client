import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from server_api.errors import PROBLEM_JSON_MEDIA_TYPE, install_error_handlers


class ExamplePayload(BaseModel):
    count: int


def build_test_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="Dataset was not found")

    @app.post("/validate")
    def validate(payload: ExamplePayload):
        return payload

    @app.get("/upstream")
    def upstream():
        raise HTTPException(
            status_code=503,
            detail={
                "user_message": "The model worker is offline",
                "error": "ConnectionError",
            },
        )

    @app.get("/failure")
    def failure():
        raise RuntimeError("private implementation detail")

    return app


class ErrorContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(build_test_app(), raise_server_exceptions=False)

    def test_http_error_preserves_detail_and_adds_recovery_contract(self):
        response = self.client.get("/missing", headers={"x-request-id": "req-123"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["x-request-id"], "req-123")
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertIn("Accept", response.headers["vary"])
        self.assertEqual(response.json()["detail"], "Dataset was not found")
        self.assertEqual(response.json()["status"], 404)
        self.assertEqual(response.json()["type"], "https://seg.bio/problems/not-found")
        self.assertEqual(response.json()["title"], "Resource not found")
        self.assertEqual(response.json()["instance"], "/missing#request-req-123")
        self.assertEqual(
            response.json()["error"],
            {
                "schema_version": 1,
                "code": "not_found",
                "category": "resource",
                "title": "Resource not found",
                "retryable": False,
                "recovery_actions": ["go_back"],
                "message": "Dataset was not found",
                "request_id": "req-123",
            },
        )

    def test_validation_error_includes_field_diagnostics(self):
        response = self.client.post("/validate", json={"count": "invalid"})

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["error"]["code"], "validation_failed")
        self.assertEqual(body["detail"], body["error"]["validation_errors"])
        self.assertTrue(body["error"]["request_id"])

    def test_problem_json_representation_is_rfc_9457_compatible(self):
        response = self.client.get(
            "/upstream",
            headers={
                "accept": PROBLEM_JSON_MEDIA_TYPE,
                "x-request-id": "problem-503",
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["content-type"], PROBLEM_JSON_MEDIA_TYPE)
        body = response.json()
        self.assertEqual(
            {
                "type": body["type"],
                "title": body["title"],
                "status": body["status"],
                "detail": body["detail"],
                "instance": body["instance"],
            },
            {
                "type": "https://seg.bio/problems/service-unavailable",
                "title": "Service temporarily unavailable",
                "status": 503,
                "detail": "The model worker is offline",
                "instance": "/upstream#request-problem-503",
            },
        )
        self.assertEqual(
            body["legacy_detail"],
            {
                "user_message": "The model worker is offline",
                "error": "ConnectionError",
            },
        )
        self.assertEqual(body["error"]["code"], "service_unavailable")

    def test_problem_json_validation_detail_is_string_with_extensions(self):
        response = self.client.post(
            "/validate",
            json={"count": "invalid"},
            headers={"accept": PROBLEM_JSON_MEDIA_TYPE},
        )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertIsInstance(body["detail"], str)
        self.assertEqual(body["legacy_detail"], body["validation_errors"])
        self.assertEqual(body["validation_errors"], body["error"]["validation_errors"])

    def test_default_representation_preserves_non_string_detail(self):
        response = self.client.get("/upstream")

        self.assertEqual(
            response.json()["detail"],
            {
                "user_message": "The model worker is offline",
                "error": "ConnectionError",
            },
        )

    def test_problem_json_must_be_explicitly_acceptable(self):
        response = self.client.get(
            "/missing", headers={"accept": "application/problem+json;q=0, */*"}
        )

        self.assertEqual(response.headers["content-type"], "application/json")

    def test_invalid_caller_request_id_is_not_reflected(self):
        response = self.client.get(
            "/missing", headers={"x-request-id": "invalid request id"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(response.headers["x-request-id"], "invalid request id")
        self.assertEqual(
            response.headers["x-request-id"], response.json()["error"]["request_id"]
        )

    def test_unexpected_error_does_not_expose_exception_text(self):
        response = self.client.get("/failure")

        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["error"]["code"], "internal_error")
        self.assertNotIn("private implementation detail", response.text)
        self.assertEqual(response.headers["x-request-id"], body["error"]["request_id"])


if __name__ == "__main__":
    unittest.main()
