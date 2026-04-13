import pytest

from server_api.chatbot.chatbot import LLMConfigurationError, get_ollama_config


def test_ollama_config_requires_explicit_environment(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_EMBED_MODEL", raising=False)

    with pytest.raises(LLMConfigurationError) as exc_info:
        get_ollama_config()

    message = str(exc_info.value)
    assert "OLLAMA_BASE_URL" in message
    assert "OLLAMA_MODEL" in message
    assert "OLLAMA_EMBED_MODEL" in message


def test_ollama_base_url_must_include_port(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")

    with pytest.raises(LLMConfigurationError) as exc_info:
        get_ollama_config()

    assert "must include the LLM service port" in str(exc_info.value)


def test_ollama_config_accepts_url_model_and_embed_model(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")

    assert get_ollama_config() == (
        "http://localhost:11434",
        "llama3.1:8b",
        "qwen3-embedding:8b",
    )
