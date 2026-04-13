import asyncio
import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.modules.setdefault("tifffile", SimpleNamespace())
sys.modules.setdefault("cv2", SimpleNamespace())

import server_api.main as main


class _FakeRequest:
    def __init__(self, payload, path, headers=None):
        self._payload = payload
        self.url = SimpleNamespace(path=path)
        self.headers = headers or {}

    async def json(self):
        return self._payload


class _FakeQuery:
    def __init__(self, convo):
        self._convo = convo

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._convo


class _FakeDB:
    def __init__(self, convo):
        self._convo = convo

    def query(self, model):
        return _FakeQuery(self._convo)

    def add(self, _obj):
        return None

    def commit(self):
        return None


class _FakeAgent:
    def invoke(self, _payload):
        raise RuntimeError("agent stalled")


class ChatLoggingFieldsTests(unittest.TestCase):
    def _extract_summary_payload(self, logs):
        for entry in logs:
            if "chat_request_summary " in entry:
                return json.loads(entry.split("chat_request_summary ", 1)[1])
        self.fail(f"No chat_request_summary line found in logs: {logs}")

    def test_chat_query_logs_standard_fields_on_success(self):
        convo = SimpleNamespace(id=7, title="Existing")
        fake_db = _FakeDB(convo=convo)
        fake_user = SimpleNamespace(id=99)
        request = _FakeRequest(
            payload={"query": "hello", "conversationId": 7},
            path="/chat/query",
            headers={"x-request-id": "req-success"},
        )

        with (
            patch.object(main, "_ensure_chatbot", return_value=True),
            patch.object(main, "_load_history_for_convo", return_value=None),
            patch.object(main, "_chat_history", []),
            patch.object(main, "_reset_search", None),
            patch.object(
                main,
                "chain",
                SimpleNamespace(
                    invoke=lambda _payload: {
                        "messages": [SimpleNamespace(content="assistant response")]
                    }
                ),
            ),
            self.assertLogs("server_api.main", level="INFO") as captured,
        ):
            response = asyncio.run(main.chat_query(request, user=fake_user, db=fake_db))

        self.assertEqual(response, {"response": "assistant response", "conversationId": 7})
        payload = self._extract_summary_payload(captured.output)
        self.assertEqual(payload["request_id"], "req-success")
        self.assertEqual(payload["endpoint"], "/chat/query")
        self.assertEqual(payload["status"], "ok")
        self.assertIsNone(payload["error_type"])
        self.assertIsInstance(payload["latency_ms"], (int, float))

    def test_chat_helper_query_logs_standard_fields_on_error(self):
        request = _FakeRequest(
            payload={"taskKey": "workflow-agent", "query": "help"},
            path="/chat/helper/query",
            headers={"x-request-id": "req-error"},
        )

        with (
            patch.object(main, "_ensure_helper_chat", return_value=True),
            patch.dict(main._helper_chains, {"workflow-agent": (_FakeAgent(), lambda: None)}, clear=True),
            patch.dict(main._helper_histories, {"workflow-agent": []}, clear=True),
            self.assertLogs("server_api.main", level="INFO") as captured,
        ):
            with self.assertRaises(RuntimeError):
                asyncio.run(main.chat_helper_query(request))

        payload = self._extract_summary_payload(captured.output)
        self.assertEqual(payload["request_id"], "req-error")
        self.assertEqual(payload["endpoint"], "/chat/helper/query")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "RuntimeError")
        self.assertIsInstance(payload["latency_ms"], (int, float))


if __name__ == "__main__":
    unittest.main()
