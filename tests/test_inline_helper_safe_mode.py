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
