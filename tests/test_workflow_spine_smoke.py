import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database as auth_database
from server_api.auth import models

pytest.importorskip("tifffile")

from server_api.main import app as server_api_app


class _DeterministicChain:
    def invoke(self, payload):
        messages = payload.get("messages", [])
        latest_user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                latest_user_message = msg.get("content", "")
                break

        if "proposal" in latest_user_message.lower():
            response = "PROPOSAL: apply workflow change"
        elif "approve" in latest_user_message.lower():
            response = "APPROVED: proposal accepted"
        else:
            response = "EVENT_RECORDED"

        return {"messages": [SimpleNamespace(content=response)]}


class WorkflowSpineSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "workflow-spine-test.db"
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

        with self.SessionLocal() as db:
            guest = models.User(username="guest", email=None, hashed_password="guest")
            db.add(guest)
            db.commit()

    def tearDown(self):
        server_api_app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_workflow_spine_smoke_sequence(self):
        # 1) get/create current workflow
        list_before = self.client.get("/chat/conversations")
        self.assertEqual(list_before.status_code, 200)
        self.assertEqual(list_before.json(), [])

        create_response = self.client.post("/chat/conversations")
        self.assertEqual(create_response.status_code, 200)
        workflow = create_response.json()
        workflow_id = workflow["id"]
        self.assertEqual(workflow["title"], "New Chat")
        self.assertEqual(workflow["messages"], [])

        chain = _DeterministicChain()
        with (
            patch("server_api.main._ensure_chatbot", return_value=True),
            patch("server_api.main.chain", chain),
            patch("server_api.main._reset_search", lambda: None),
        ):
            # 2) append key events in order
            event_1 = self.client.post(
                "/chat/query",
                json={"conversationId": workflow_id, "query": "event: workflow_created"},
            )
            self.assertEqual(event_1.status_code, 200)
            self.assertEqual(event_1.json()["response"], "EVENT_RECORDED")

            event_2 = self.client.post(
                "/chat/query",
                json={"conversationId": workflow_id, "query": "event: context_loaded"},
            )
            self.assertEqual(event_2.status_code, 200)
            self.assertEqual(event_2.json()["response"], "EVENT_RECORDED")

            # 3) create agent proposal
            proposal = self.client.post(
                "/chat/query",
                json={"conversationId": workflow_id, "query": "agent proposal: adjust threshold"},
            )
            self.assertEqual(proposal.status_code, 200)
            self.assertEqual(proposal.json()["response"], "PROPOSAL: apply workflow change")

            # 4) approve proposal
            approval = self.client.post(
                "/chat/query",
                json={"conversationId": workflow_id, "query": "approve proposal"},
            )
            self.assertEqual(approval.status_code, 200)
            self.assertEqual(approval.json()["response"], "APPROVED: proposal accepted")

        # 5) verify state/event transitions
        workflow_after = self.client.get(f"/chat/conversations/{workflow_id}")
        self.assertEqual(workflow_after.status_code, 200)
        body = workflow_after.json()
        self.assertEqual(body["title"], "event: workflow_created")

        event_contents = [message["content"] for message in body["messages"]]
        self.assertEqual(
            event_contents,
            [
                "event: workflow_created",
                "EVENT_RECORDED",
                "event: context_loaded",
                "EVENT_RECORDED",
                "agent proposal: adjust threshold",
                "PROPOSAL: apply workflow change",
                "approve proposal",
                "APPROVED: proposal accepted",
            ],
        )


if __name__ == "__main__":
    unittest.main()
