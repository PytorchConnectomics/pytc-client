from server_api.chatbot import update_faiss
from server_api.chatbot.chatbot import (
    AGENT_RESPONSE_STYLE,
    _compact_agent_response,
)


def test_faiss_index_exists_requires_both_files(tmp_path):
    faiss_dir = tmp_path / "faiss_index"
    faiss_dir.mkdir()

    assert update_faiss.faiss_index_exists(faiss_dir) is False

    (faiss_dir / "index.faiss").write_text("stub")
    assert update_faiss.faiss_index_exists(faiss_dir) is False

    (faiss_dir / "index.pkl").write_text("stub")
    assert update_faiss.faiss_index_exists(faiss_dir) is True


def test_ensure_faiss_index_builds_when_missing(tmp_path, monkeypatch):
    summaries_dir = tmp_path / "summaries"
    faiss_dir = tmp_path / "faiss_index"
    summaries_dir.mkdir()
    calls = []

    def fake_build(summaries_directory, target_directory, *, model=None, base_url=None):
        calls.append((summaries_directory, target_directory, model, base_url))
        target_directory.mkdir(parents=True, exist_ok=True)
        (target_directory / "index.faiss").write_text("stub")
        (target_directory / "index.pkl").write_text("stub")

    monkeypatch.setattr(update_faiss, "build_faiss_index", fake_build)

    generated = update_faiss.ensure_faiss_index(
        summaries_directory=summaries_dir,
        faiss_directory=faiss_dir,
        model="embed-model",
        base_url="http://example.test:11434",
    )

    assert generated is True
    assert calls == [
        (summaries_dir, faiss_dir, "embed-model", "http://example.test:11434")
    ]
    assert update_faiss.faiss_index_exists(faiss_dir) is True


def test_ensure_faiss_index_skips_when_present(tmp_path, monkeypatch):
    monkeypatch.delenv("OLLAMA_EMBED_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    summaries_dir = tmp_path / "summaries"
    faiss_dir = tmp_path / "faiss_index"
    summaries_dir.mkdir()
    faiss_dir.mkdir()
    (faiss_dir / "index.faiss").write_text("stub")
    (faiss_dir / "index.pkl").write_text("stub")
    update_faiss.write_index_settings(
        faiss_dir,
        model=update_faiss.DEFAULT_OLLAMA_EMBED_MODEL,
        base_url=update_faiss.DEFAULT_OLLAMA_BASE_URL,
    )

    def fail_build(*args, **kwargs):
        raise AssertionError("build_faiss_index should not be called")

    monkeypatch.setattr(update_faiss, "build_faiss_index", fail_build)

    generated = update_faiss.ensure_faiss_index(
        summaries_directory=summaries_dir,
        faiss_directory=faiss_dir,
    )

    assert generated is False


def test_ensure_faiss_index_rebuilds_when_settings_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("OLLAMA_EMBED_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    summaries_dir = tmp_path / "summaries"
    faiss_dir = tmp_path / "faiss_index"
    summaries_dir.mkdir()
    faiss_dir.mkdir()
    (faiss_dir / "index.faiss").write_text("stub")
    (faiss_dir / "index.pkl").write_text("stub")
    calls = []

    def fake_build(summaries_directory, target_directory, *, model=None, base_url=None):
        calls.append((summaries_directory, target_directory, model, base_url))
        update_faiss.write_index_settings(
            target_directory, model=model, base_url=base_url
        )

    monkeypatch.setattr(update_faiss, "build_faiss_index", fake_build)

    generated = update_faiss.ensure_faiss_index(
        summaries_directory=summaries_dir,
        faiss_directory=faiss_dir,
    )

    assert generated is True
    assert calls == [
        (
            summaries_dir,
            faiss_dir,
            update_faiss.DEFAULT_OLLAMA_EMBED_MODEL,
            update_faiss.DEFAULT_OLLAMA_BASE_URL,
        )
    ]


def test_resolve_ollama_settings_uses_env_defaults(monkeypatch):
    monkeypatch.delenv("OLLAMA_EMBED_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    model, base_url = update_faiss.resolve_ollama_settings()

    assert model == update_faiss.DEFAULT_OLLAMA_EMBED_MODEL
    assert base_url == update_faiss.DEFAULT_OLLAMA_BASE_URL


def test_resolve_ollama_settings_prefers_explicit_values(monkeypatch):
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "env-model")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env.test:9999")

    model, base_url = update_faiss.resolve_ollama_settings(
        model="cli-model",
        base_url="http://cli.test:8888",
    )

    assert model == "cli-model"
    assert base_url == "http://cli.test:8888"


def test_agent_response_style_requires_skimmable_answers():
    assert "Maximum 90 words" in AGENT_RESPONSE_STYLE
    assert "recommended next action first" in AGENT_RESPONSE_STYLE


def test_compact_agent_response_shortens_long_non_code_answers():
    response = "\n".join(
        [
            f"- detail {index} about a long biological workflow explanation"
            for index in range(30)
        ]
    )

    compacted = _compact_agent_response(response, max_words=40)

    assert len(compacted.split()) <= 50
    assert "Ask for details" in compacted


def test_compact_agent_response_preserves_code_blocks():
    response = "Run this:\n```bash\npython scripts/main.py --help\n```"

    assert _compact_agent_response(response, max_words=5) == response
