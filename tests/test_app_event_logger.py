import json
import io

from app_event_logger import _AppEventStream, append_app_event, get_app_event_log_path


def test_append_app_event_writes_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "app-events.jsonl"
    monkeypatch.setenv("PYTC_APP_EVENT_LOG_PATH", str(log_path))

    record = append_app_event(
        component="test",
        event="unit_test",
        level="warning",
        message="hello world",
        data={"answer": 42},
    )

    assert get_app_event_log_path() == log_path
    assert log_path.is_file()
    assert record["component"] == "test"
    assert record["event"] == "unit_test"
    assert record["level"] == "WARNING"

    written = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert written["component"] == "test"
    assert written["event"] == "unit_test"
    assert written["message"] == "hello world"
    assert written["data"] == {"answer": 42}


def test_app_event_stream_detects_info_lines_on_stderr(tmp_path, monkeypatch):
    log_path = tmp_path / "app-events.jsonl"
    monkeypatch.setenv("PYTC_APP_EVENT_LOG_PATH", str(log_path))

    stream = _AppEventStream(
        component="test",
        stream_name="stderr",
        level="ERROR",
        original_stream=io.StringIO(),
    )
    stream.write("INFO:     Shutting down\n")
    stream.flush()

    written = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert written["event"] == "stderr_line"
    assert written["level"] == "INFO"
    assert written["message"] == "INFO:     Shutting down"
