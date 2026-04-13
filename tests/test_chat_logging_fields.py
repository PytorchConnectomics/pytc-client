import re
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import APIRouter

ehtool_router_stub = types.ModuleType("server_api.ehtool.router")
ehtool_router_stub.router = APIRouter()
sys.modules.setdefault("server_api.ehtool.router", ehtool_router_stub)
sys.modules.setdefault("server_api.ehtool", types.SimpleNamespace(router=ehtool_router_stub))

from server_api.auth.router import get_current_user
from server_api.main import app


class ChatLoggingFieldsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides[get_current_user] = (
            lambda: SimpleNamespace(id=999, username="test")
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_chat_query_success_emits_standard_summary_fields(self):
        class DummyChain:
            def invoke(self, payload):
                return {"messages": [SimpleNamespace(content="assistant response")]}

        with patch("server_api.main._ensure_chatbot", return_value=True), patch(
            "server_api.main.chain", DummyChain()
        ), patch(
            "server_api.main._reset_search", None
        ), self.assertLogs(
            "server_api.chat_observability", level="INFO"
        ) as captured:
            response = self.client.post("/chat/query", json={"query": "my secret prompt"})

        self.assertEqual(response.status_code, 200)
        log_line = captured.output[-1]
        self.assertIn("request_id=", log_line)
        self.assertIn("endpoint=/chat/query", log_line)
        self.assertIn("latency_ms=", log_line)
        self.assertIn("status=ok", log_line)
        self.assertIn("error_type=", log_line)
        self.assertNotIn("my secret prompt", log_line)

    def test_chat_helper_query_error_emits_standard_summary_fields(self):
        with patch("server_api.main._ensure_helper_chat", return_value=False), self.assertLogs(
            "server_api.chat_observability", level="INFO"
        ) as captured:
            response = self.client.post(
                "/chat/helper/query",
                json={"taskKey": "workflow_agent", "query": "help me"},
            )

        self.assertEqual(response.status_code, 503)
        log_line = captured.output[-1]
        self.assertIn("request_id=", log_line)
        self.assertIn("endpoint=/chat/helper/query", log_line)
        self.assertIn("latency_ms=", log_line)
        self.assertIn("status=error", log_line)
        self.assertIn("error_type=HTTPException", log_line)
        self.assertNotIn("help me", log_line)

    def test_chat_status_failure_includes_error_type_field(self):
        with patch("server_api.main._ensure_chatbot", return_value=False), patch(
            "server_api.main._chatbot_error", Exception("down")
        ), self.assertLogs("server_api.chat_observability", level="INFO") as captured:
            response = self.client.get("/chat/status")

        self.assertEqual(response.status_code, 200)
        log_line = captured.output[-1]
        self.assertIn("endpoint=/chat/status", log_line)
        self.assertIn("status=error", log_line)
        self.assertIn("error_type=ChatbotUnavailable", log_line)
        self.assertRegex(log_line, r"request_id=[0-9a-f-]{36}")


if __name__ == "__main__":
    unittest.main()
