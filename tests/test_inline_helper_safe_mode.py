from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from server_api.main import app as server_api_app


def test_inline_helper_defaults_to_docs_mode_without_building_agent(monkeypatch):
    monkeypatch.delenv("PYTC_INLINE_HELP_MODE", raising=False)
    client = TestClient(server_api_app)

    with patch("server_api.main.build_helper_chain") as build_helper_chain:
        response = client.post(
            "/chat/helper/query",
            json={
                "taskKey": "inference:advanced-config:Augmentations",
                "query": "Explain this setting and recommend a concrete value.",
                "fieldContext": 'Field: "Augmentations". YAML key: INFERENCE.AUG_NUM.',
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "docs"
    assert "test-time transformed predictions" in payload["response"]
    assert "AUG_NUM" in payload["response"]
    build_helper_chain.assert_not_called()


def test_inline_helper_gives_concise_file_picker_guidance(monkeypatch):
    monkeypatch.delenv("PYTC_INLINE_HELP_MODE", raising=False)
    client = TestClient(server_api_app)

    response = client.post(
        "/chat/helper/query",
        json={
            "taskKey": "training:Input Image",
            "query": "What do I put here?",
            "fieldContext": 'Field: "Input Image". YAML key: DATASET.INPUT_PATH.',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "docs"
    assert "folder icon" in payload["response"]
    assert "Relevant local docs" not in payload["response"]
    assert "Model Training Page" not in payload["response"]


def test_inline_helper_followup_uses_same_field_history(monkeypatch):
    monkeypatch.delenv("PYTC_INLINE_HELP_MODE", raising=False)
    client = TestClient(server_api_app)

    response = client.post(
        "/chat/helper/query",
        json={
            "taskKey": "training:Input Image",
            "query": "oooo cool....what does that mean?",
            "fieldContext": 'Field: "Input Image". YAML key: DATASET.INPUT_PATH.',
            "history": [
                {
                    "role": "assistant",
                    "content": (
                        "Select a volume file for H5/TIFF/NIfTI/Zarr-style data, "
                        "or select a folder when the dataset is stored as a directory/stack."
                    ),
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "docs"
    assert "common ways microscopy image volumes are stored" in payload["response"]
    assert "Use the folder icon" not in payload["response"]


def test_inline_helper_casual_message_does_not_dump_docs(monkeypatch):
    monkeypatch.delenv("PYTC_INLINE_HELP_MODE", raising=False)
    client = TestClient(server_api_app)

    response = client.post(
        "/chat/helper/query",
        json={
            "taskKey": "training:Input Image",
            "query": "hi!",
            "fieldContext": 'Field: "Input Image". YAML key: DATASET.INPUT_PATH.',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "docs"
    assert "Ask me about this specific field" in payload["response"]
    assert "Relevant guidance" not in payload["response"]
    assert "PyTC Training Guide" not in payload["response"]


def test_inline_helper_agent_mode_reuses_shared_chain(monkeypatch):
    monkeypatch.setenv("PYTC_INLINE_HELP_MODE", "agent")

    import server_api.main as main

    main._helper_chains.clear()
    main._helper_histories.clear()
    calls = []

    class FakeAgent:
        def invoke(self, payload):
            return {
                "messages": [
                    type(
                        "Message",
                        (),
                        {"content": f"reply {len(payload['messages'])}"},
                    )()
                ]
            }

    def fake_build_helper_chain():
        calls.append("build")
        return FakeAgent(), lambda: None

    monkeypatch.setattr(main, "build_helper_chain", fake_build_helper_chain)
    client = TestClient(server_api_app)

    first = client.post(
        "/chat/helper/query",
        json={
            "taskKey": "training:Input Image",
            "query": "What do I put here?",
            "fieldContext": 'Field: "Input Image".',
        },
    )
    second = client.post(
        "/chat/helper/query",
        json={
            "taskKey": "training:Input Label",
            "query": "What do I put here?",
            "fieldContext": 'Field: "Input Label".',
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == ["build"]
    assert main._SHARED_HELPER_CHAIN_KEY in main._helper_chains
    assert "training:Input Image" in main._helper_histories
    assert "training:Input Label" in main._helper_histories
