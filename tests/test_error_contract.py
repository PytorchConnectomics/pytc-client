import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from server_api.errors import install_error_handlers


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
        self.assertEqual(response.json()["detail"], "Dataset was not found")
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
