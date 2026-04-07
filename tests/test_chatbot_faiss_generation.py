from server_api.chatbot import update_faiss


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
    summaries_dir = tmp_path / "summaries"
    faiss_dir = tmp_path / "faiss_index"
    summaries_dir.mkdir()
    faiss_dir.mkdir()
    (faiss_dir / "index.faiss").write_text("stub")
    (faiss_dir / "index.pkl").write_text("stub")

    def fail_build(*args, **kwargs):
        raise AssertionError("build_faiss_index should not be called")

    monkeypatch.setattr(update_faiss, "build_faiss_index", fail_build)

    generated = update_faiss.ensure_faiss_index(
        summaries_directory=summaries_dir,
        faiss_directory=faiss_dir,
    )

    assert generated is False


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
