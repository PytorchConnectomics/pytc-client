from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any
from requests import exceptions as request_exceptions

from scripts import inspect_demo_instance as diag


def _write_json_lines(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_check_api_health_warns_for_bad_payload(monkeypatch):
    def fake_request_json(*, base_url, path, **kwargs):
        assert path == "/health"
        assert base_url == "https://demo.seg.bio"
        return 500, {"status": "down"}, None

    monkeypatch.setattr(diag, "_http_request_json", fake_request_json)
    result = diag.check_api_health(api_base="https://demo.seg.bio", timeout=1)
    assert result.name == "api.health"
    assert result.status == "warn"
    assert result.details == {"status_code": 500, "payload": {"status": "down"}}


def test_check_workflow_auth_warning(monkeypatch):
    def fake_request_json(*, base_url, path, **kwargs):
        return 401, {"detail": "Unauthorized"}, None

    monkeypatch.setattr(diag, "_http_request_json", fake_request_json)
    result = diag.check_workflow(api_base="http://127.0.0.1:4342", timeout=1)
    assert result.name == "workflow.current"
    assert result.status == "warn"
    assert result.message == "Current workflow endpoint requires authentication"
    assert result.details == {"status_code": 401}


def test_check_runtime_events_reports_worker_mismatch(monkeypatch, tmp_path):
    log_path = tmp_path / "app-events.jsonl"
    _write_json_lines(
        log_path,
        [
            {"event": "worker_proxy_request_started", "component": "server_api"},
            {
                "event": "api_runtime_configured",
                "component": "server_api",
                "worker_url": "http://expected-worker:4243",
                "neuroglancer_port": 4244,
                "neuroglancer_public_base": "https://demo.seg.bio/neuroglancer",
            },
        ],
    )

    results = diag.check_runtime_events(
        app_log_path=log_path,
        timeout_lines=100,
        expected_worker_url="http://wrong-worker:4243",
        neuroglancer_port=4244,
        neuroglancer_public_base="https://demo.seg.bio/neuroglancer",
    )
    assert any(item.name == "api.runtime_config" and item.status == "warn" for item in results)
    assert any(
        item.name == "api.runtime_config_worker_url" and item.status == "warn"
        for item in results
    )
    snapshot = next(item for item in results if item.name == "api.runtime_config")
    assert snapshot.details == {
        "expected": {
            "worker_url": "http://wrong-worker:4243",
            "neuroglancer_port": 4244,
            "neuroglancer_public_base": "https://demo.seg.bio/neuroglancer",
        },
        "observed": {
            "worker_url": "http://expected-worker:4243",
            "neuroglancer_port": 4244,
            "neuroglancer_public_base": "https://demo.seg.bio/neuroglancer",
        },
        "mismatches": ["worker_url"],
    }
    for row in results:
        if row.name == "api.runtime_config_worker_url":
            assert row.details["expected_worker_url"] == "http://wrong-worker:4243"
            assert row.details["configured_worker_url"] == "http://expected-worker:4243"


def test_check_runtime_events_reports_neuroglancer_port_mismatch(monkeypatch, tmp_path):
    log_path = tmp_path / "app-events.jsonl"
    _write_json_lines(
        log_path,
        [
            {
                "event": "api_runtime_configured",
                "component": "server_api",
                "worker_url": "http://worker:4243",
                "neuroglancer_port": 4245,
                "neuroglancer_public_base": "https://demo.seg.bio/neuroglancer",
            },
        ],
    )

    results = diag.check_runtime_events(
        app_log_path=log_path,
        timeout_lines=100,
        expected_worker_url="http://worker:4243",
        neuroglancer_port=4244,
        neuroglancer_public_base="https://demo.seg.bio/neuroglancer",
    )
    snapshot = next(item for item in results if item.name == "api.runtime_config")
    assert snapshot.status == "warn"
    assert snapshot.details["mismatches"] == ["neuroglancer_port"]
    assert snapshot.details["observed"]["neuroglancer_port"] == 4245


def test_check_worker_path_detects_mismatched_proxy_target(monkeypatch, tmp_path):
    log_path = tmp_path / "app-events.jsonl"
    _write_json_lines(
        log_path,
        [
            {
                "component": "server_api",
                "event": "worker_proxy_request_completed",
                "path": "/training_status",
                "worker_url": "http://proxy-target:4243",
            }
        ]
    )

    def fake_request_json(*, base_url, path, **kwargs):
        if path == "/hello":
            return 200, ["hello"], None
        if path == "/training_status":
            return 200, {"worker_url": "http://proxy-target:4243"}, None
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(diag, "_http_request_json", fake_request_json)
    results = diag.check_worker_path(
        api_base="https://demo.seg.bio",
        expected_worker_url="http://expected:4243",
        app_log_path=log_path,
        timeout=1,
    )
    assert len(results) == 4
    assert results[0].name == "worker.hello"
    assert results[0].status == "pass"
    mismatch = next(item for item in results if item.name == "worker.url_mismatch")
    assert mismatch.status == "fail"
    assert mismatch.details["expected_worker_url"] == "http://expected:4243"
    assert mismatch.details["observed_worker_url"] == "http://proxy-target:4243"


def test_check_worker_path_training_status_timeout_is_warning(monkeypatch, tmp_path):
    log_path = tmp_path / "app-events.jsonl"
    _write_json_lines(log_path, [])

    def fake_request_json(*, base_url, path, **kwargs):
        if path == "/hello":
            return 200, ["hello"], None
        if path == "/training_status":
            raise request_exceptions.Timeout("temporary overload")
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(diag, "_http_request_json", fake_request_json)
    results = diag.check_worker_path(
        api_base="https://demo.seg.bio",
        expected_worker_url="http://expected:4243",
        app_log_path=log_path,
        timeout=1,
    )

    training_result = next(item for item in results if item.name == "api.training_status")
    assert training_result.status == "warn"
    assert "temporary overload" in training_result.details["error"]

    mismatch = next(item for item in results if item.name == "worker.url_mismatch")
    assert mismatch.status == "warn"
    assert mismatch.details["expected_worker_url"] == "http://expected:4243"


def test_check_disk_and_errors_uses_tail_for_error_count(tmp_path):
    log_path = tmp_path / "app-events.jsonl"
    rows = [
        {"level": "ERROR", "event": "too_many"},
        {"level": "INFO", "event": "ok"},
        {"level": "ERROR", "event": "still_bad"},
    ]
    _write_json_lines(log_path, rows)
    results = diag.check_disk_and_errors(
        app_log_path=log_path,
        workflow_bundle_dir=tmp_path / "workflow-bundles",
        error_tail_lines=2,
    )

    error_result = next(row for row in results if row.name == "app_error_events")
    assert error_result.status == "warn"
    assert error_result.details["error_count"] == 1


def test_neuroglancer_checks_port_reachability_warning_on_connection_refused(monkeypatch):
    def fake_create_connection(addr, timeout=1):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(diag.socket, "create_connection", fake_create_connection)
    results = diag.check_neuroglancer(
        api_base="https://demo.seg.bio",
        workflow={"id": 7, "neuroglancer_url": "https://demo.seg.bio/neuroglancer/v/abc"},
        neuroglancer_port=4244,
        neuroglancer_public_base="https://demo.seg.bio/neuroglancer",
    )

    status_lookup = {row.name: row.status for row in results}
    assert status_lookup["neuroglancer.port"] == "warn"
    assert status_lookup["neuroglancer.public_base"] == "pass"
    assert status_lookup["neuroglancer.url_match"] == "pass"


def test_run_diagnostics_emits_consistent_reports(monkeypatch, tmp_path):
    def fake_request_json(*, base_url, path, **kwargs):
        if path == "/health":
            return 200, {"status": "ok"}, None
        if path == "/app/log-path":
            return 200, {"path": str(tmp_path / "app-events.jsonl")}, None
        if path == "/api/workflows/current":
            return 200, {"workflow": {"id": 3}, "events": []}, None
        if path == "/training_status":
            return 200, {"worker_url": "http://worker:4243"}, None
        if path == "/chat/status":
            return 200, {"configured": True}, None
        if path == "/hello":
            return 200, ["hello"], None
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(diag, "_http_request_json", fake_request_json)
    monkeypatch.setattr(
        diag,
        "_tail_json_lines",
        lambda *args, **kwargs: [],
    )

    class _NoopConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        diag.socket,
        "create_connection",
        lambda *_args, **_kwargs: _NoopConnection(),
    )

    args = Namespace(
        api_base="https://demo.seg.bio",
        worker_protocol="http",
        worker_url="worker:4243",
        neuroglancer_port=4244,
        neuroglancer_public_base="https://demo.seg.bio/neuroglancer",
        workflow_bundle_dir=str(tmp_path / "workflow-bundles"),
        timeout=1,
        log_tail_lines=50,
    )
    results = diag.run_diagnostics(args)

    names = [check.name for check in results]
    assert "api.health" in names
    assert "api.log_path" in names
    assert "workflow.current" in names
    assert any(name == "worker.url_mismatch" for name in names)
    assert any(check.name == "worker.url_mismatch" and check.status == "pass" for check in results)


def test_run_diagnostics_tolerates_training_status_timeout_as_warning(monkeypatch, tmp_path):
    def fake_request_json(*, base_url, path, **kwargs):
        if path == "/health":
            return 200, {"status": "ok"}, None
        if path == "/app/log-path":
            return 200, {"path": str(tmp_path / "app-events.jsonl")}, None
        if path == "/api/workflows/current":
            return 200, {"workflow": {"id": 3}, "events": []}, None
        if path == "/chat/status":
            return 200, {"configured": True}, None
        if path == "/hello":
            return 200, ["hello"], None
        if path == "/training_status":
            raise request_exceptions.Timeout("temporary overload")
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(diag, "_http_request_json", fake_request_json)
    monkeypatch.setattr(
        diag,
        "_tail_json_lines",
        lambda *args, **kwargs: [],
    )

    class _NoopConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        diag.socket,
        "create_connection",
        lambda *_args, **_kwargs: _NoopConnection(),
    )

    args = Namespace(
        api_base="https://demo.seg.bio",
        worker_protocol="http",
        worker_url="worker:4243",
        neuroglancer_port=4244,
        neuroglancer_public_base="https://demo.seg.bio/neuroglancer",
        workflow_bundle_dir=str(tmp_path / "workflow-bundles"),
        timeout=1,
        log_tail_lines=50,
    )
    results = diag.run_diagnostics(args)

    assert all(check.status != "fail" for check in results)
    timeout_result = next(
        item
        for item in results
        if item.name == "api.training_status" and item.message == "API /training_status request failed"
    )
    assert timeout_result.status == "warn"


def test_demo2_defaults_are_applied_for_demo_host(monkeypatch, tmp_path):
    def fake_request_json(*, base_url, path, **kwargs):
        if path == "/health":
            return 200, {"status": "ok"}, None
        if path == "/app/log-path":
            return 200, {"path": str(tmp_path / "app-events.jsonl")}, None
        if path == "/api/workflows/current":
            return 200, {"workflow": {"id": 3, "neuroglancer_url": "https://demo.seg.bio/neuroglancer/v/abc"}, "events": []}, None
        if path == "/training_status":
            return 200, {"worker_url": "http://localhost:4243"}, None
        if path == "/chat/status":
            return 200, {"configured": True}, None
        if path == "/hello":
            return 200, ["hello"], None
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(diag, "_http_request_json", fake_request_json)
    monkeypatch.setattr(
        diag,
        "_tail_json_lines",
        lambda *args, **kwargs: [],
    )

    class _NoopConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        diag.socket,
        "create_connection",
        lambda *_args, **_kwargs: _NoopConnection(),
    )

    args = Namespace(
        api_base="https://demo.seg.bio",
        worker_protocol="http",
        worker_url="localhost:4243",
        neuroglancer_port=0,
        neuroglancer_public_base="",
        workflow_bundle_dir=str(tmp_path / "workflow-bundles"),
        timeout=1,
        log_tail_lines=120,
    )
    results = diag.run_diagnostics(args)

    names = {check.name: check for check in results}
    assert names["neuroglancer.port"].status == "pass"
    assert names["neuroglancer.public_base"].status == "pass"
