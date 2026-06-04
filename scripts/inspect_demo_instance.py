#!/usr/bin/env python3
"""Operator-focused runtime diagnostics for the demo deployment.

The checks are read-only and designed to answer:
- Can API and worker be reached?
- Is the worker URL aligned with expectation and runtime logs?
- Is Neuroglancer reachable and reasonably configured?
- Are Ollama/chat endpoints reachable?
- How big are recent logs/bundles and are there recent ERROR events?
"""

from __future__ import annotations

import argparse
import json
import os
import socket
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests


DEMO_SEG_HOSTS = {"demo.seg.bio", "www.demo.seg.bio"}
DEMO_SEG_PUBLIC_BASE = "https://demo.seg.bio/neuroglancer"
DEMO_SEG_NEUROGLANCER_PORT = 4244
DEMO_SEG_LOG_TAIL_LINES = 5000


def _demo_seg_defaults(
    *,
    api_base: str,
    neuroglancer_port: int,
    neuroglancer_public_base: str,
    log_tail_lines: int,
) -> tuple[int, str, int]:
    host = (urlsplit(api_base).hostname or "").lower()
    if host in DEMO_SEG_HOSTS:
        resolved_public_base = (
            neuroglancer_public_base.strip() or DEMO_SEG_PUBLIC_BASE
        )
        resolved_port = neuroglancer_port or DEMO_SEG_NEUROGLANCER_PORT
        resolved_log_tail_lines = (
            DEMO_SEG_LOG_TAIL_LINES if log_tail_lines == 120 else log_tail_lines
        )
        return resolved_port, resolved_public_base, resolved_log_tail_lines
    return neuroglancer_port, neuroglancer_public_base, log_tail_lines


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str
    details: dict[str, Any] | None = None


def _safe_json_loads(line: str) -> Any | None:
    text = (line or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _normalize_base_url(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text if "://" in text else f"http://{text}")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _normalize_worker_url(protocol: str, worker_url: str) -> str:
    text = (worker_url or "").strip().rstrip("/")
    if not text:
        return ""
    parsed = urlsplit(text if "://" in text else f"{(protocol or 'http')}://{text}")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _host_and_port(value: str) -> tuple[str | None, int | None]:
    parsed = urlsplit(value if "://" in value else f"http://{value}")
    return parsed.hostname, parsed.port


def _tail_json_lines(path: Path, max_lines: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=max_lines)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = _safe_json_loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return list(rows)


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                continue
    return total


def _humanize_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _http_request_json(
    *,
    base_url: str,
    path: str,
    method: str = "GET",
    timeout: int = 3,
    json_payload: Any = None,
    raise_for_status: bool = True,
) -> tuple[int, Any, requests.Response]:
    url = f"{base_url.rstrip('/')}{path}"
    response = requests.request(
        method=method.upper(),
        url=url,
        json=json_payload,
        timeout=timeout,
        headers={"Accept": "application/json"},
    )
    if raise_for_status:
        response.raise_for_status()
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        text = (response.text or "").strip()
        body = text or None
    return response.status_code, body, response


def _record_result(
    checks: list[CheckResult],
    status: str,
    name: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> CheckResult:
    result = CheckResult(name=name, status=status, message=message, details=details)
    checks.append(result)
    return result


def check_api_health(*, api_base: str, timeout: int) -> CheckResult:
    try:
        status, payload, _ = _http_request_json(
            base_url=api_base,
            path="/health",
            timeout=timeout,
            raise_for_status=False,
        )
    except Exception as exc:
        return CheckResult(
            name="api.health",
            status="fail",
            message="API /health request failed",
            details={"error": str(exc)},
        )

    if status != 200:
        return CheckResult(
            name="api.health",
            status="warn",
            message="API /health returned non-200",
            details={"status_code": status, "payload": payload},
        )

    if payload != {"status": "ok"}:
        return CheckResult(
            name="api.health",
            status="warn",
            message="API /health returned unexpected payload",
            details={"status_code": status, "payload": payload},
        )

    return CheckResult(
        name="api.health",
        status="pass",
        message="API /health is OK",
        details={"status_code": status},
    )


def check_app_log_path(*, api_base: str, timeout: int) -> tuple[CheckResult, Path | None]:
    try:
        status, payload, _ = _http_request_json(
            base_url=api_base,
            path="/app/log-path",
            timeout=timeout,
            raise_for_status=False,
        )
        if status != 200:
            return (
                CheckResult(
                    name="api.log_path",
                    status="warn",
                    message="Could not read /app/log-path",
                    details={"status_code": status, "payload": payload},
                ),
                None,
            )
        if not isinstance(payload, dict) or not payload.get("path"):
            return (
                CheckResult(
                    name="api.log_path",
                    status="warn",
                    message="Unexpected /app/log-path payload",
                    details={"payload": payload},
                ),
                None,
            )
        return (
            CheckResult(
                name="api.log_path",
                status="pass",
                message="Read API app log path",
                details={"path": payload.get("path")},
            ),
            Path(str(payload.get("path"))),
        )
    except Exception as exc:
        return (
            CheckResult(
                name="api.log_path",
                status="warn",
                message="Could not read /app/log-path",
                details={"error": str(exc)},
            ),
            None,
        )


def _collect_worker_proxy_urls(
    *,
    app_log_rows: list[dict[str, Any]],
    worker_endpoint: str,
) -> list[str]:
    matches = []
    for row in app_log_rows:
        if row.get("component") != "server_api":
            continue
        event = row.get("event")
        if event not in {
            "worker_proxy_request_started",
            "worker_proxy_request_completed",
            "worker_proxy_request_failed",
        }:
            continue
        if row.get("path") == worker_endpoint and row.get("worker_url"):
            matches.append(str(row.get("worker_url")))
    return matches


def check_runtime_events(
    *,
    app_log_path: Path | None,
    timeout_lines: int,
    expected_worker_url: str,
    neuroglancer_port: int,
    neuroglancer_public_base: str | None = None,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    expected_worker = _normalize_worker_url("http", expected_worker_url)
    expected_public_base = (neuroglancer_public_base or "").strip().rstrip("/")
    expected_ng_port = int(neuroglancer_port)

    if not app_log_path:
        _record_result(
            checks,
            "warn",
            "api.runtime_config_log",
            "Could not inspect runtime config from logs without /app/log-path",
            {"reason": "log-path-unavailable"},
        )
        return checks

    rows = _tail_json_lines(app_log_path, max_lines=timeout_lines)
    configured_rows = [row for row in rows if row.get("event") == "api_runtime_configured"]
    if not configured_rows:
        _record_result(
            checks,
            "warn",
            "api.runtime_config_log",
            "No api_runtime_configured event in recent app log",
            {"path": str(app_log_path)},
        )
        _record_result(
            checks,
            "warn",
            "api.runtime_config",
            "Could not compare runtime config against expected values",
            {
                "expected": {
                    "worker_url": expected_worker,
                    "neuroglancer_port": expected_ng_port,
                    "neuroglancer_public_base": expected_public_base,
                },
            },
        )
        return checks

    configured = configured_rows[-1]
    configured_worker_url = _normalize_worker_url(
        protocol="",
        worker_url=str(configured.get("worker_url") or ""),
    )
    configured_ng_port = configured.get("neuroglancer_port")
    try:
        configured_ng_port_int = (
            int(configured_ng_port) if configured_ng_port is not None else None
        )
    except (TypeError, ValueError):
        configured_ng_port_int = None
    configured_public_base = str(configured.get("neuroglancer_public_base", "")).strip().rstrip("/")

    mismatches: list[str] = []
    if expected_worker:
        if configured_worker_url:
            if configured_worker_url != expected_worker:
                mismatches.append("worker_url")
        else:
            mismatches.append("worker_url")
    if expected_ng_port and configured_ng_port_int is not None:
        if configured_ng_port_int != expected_ng_port:
            mismatches.append("neuroglancer_port")
    elif expected_ng_port:
        mismatches.append("neuroglancer_port")
    if expected_public_base and configured_public_base:
        if configured_public_base != expected_public_base:
            mismatches.append("neuroglancer_public_base")
    elif expected_public_base:
        mismatches.append("neuroglancer_public_base")
    _record_result(
        checks,
        "pass" if not mismatches else "warn",
        "api.runtime_config",
        "Runtime config in api log matches operator expectations"
        if not mismatches
        else "Runtime config in api log differs from operator expectations",
        {
            "expected": {
                "worker_url": expected_worker,
                "neuroglancer_port": expected_ng_port,
                "neuroglancer_public_base": expected_public_base,
            },
            "observed": {
                "worker_url": configured_worker_url,
                "neuroglancer_port": configured_ng_port_int,
                "neuroglancer_public_base": configured_public_base,
            },
            "mismatches": mismatches,
        },
    )

    _record_result(
        checks,
        "pass",
        "api.runtime_config_log",
        "Read api_runtime_configured event from app log",
        {
            "path": str(app_log_path),
            "api_host": configured.get("api_host"),
            "api_port": configured.get("api_port"),
            "neuroglancer_port": configured.get("neuroglancer_port"),
            "worker_url": configured.get("worker_url"),
        },
    )

    if configured_worker_url and expected_worker:
        _record_result(
            checks,
            "pass" if configured_worker_url == expected_worker else "warn",
            "api.runtime_config_worker_url",
            "Configured worker URL aligns with expected worker URL"
            if configured_worker_url == expected_worker
            else "Configured worker URL differs from expected worker URL",
            {
                "expected_worker_url": expected_worker,
                "configured_worker_url": configured_worker_url,
            },
        )

    configured_ng_port = configured.get("neuroglancer_port")
    try:
        configured_ng_port_int = int(configured_ng_port) if configured_ng_port is not None else None
    except (TypeError, ValueError):
        configured_ng_port_int = None
    if configured_ng_port_int is not None:
        _record_result(
            checks,
            "pass" if configured_ng_port_int == int(neuroglancer_port) else "warn",
            "api.runtime_config_neuroglancer_port",
            "Configured neuroglancer port aligns with expected value"
            if configured_ng_port_int == int(neuroglancer_port)
            else "Configured neuroglancer port differs from expected value",
            {
                "expected_neuroglancer_port": int(neuroglancer_port),
                "configured_neuroglancer_port": configured_ng_port_int,
            },
        )
    elif configured_ng_port is not None:
        _record_result(
            checks,
            "warn",
            "api.runtime_config_neuroglancer_port",
            "Could not parse configured neuroglancer port from runtime log",
            {
                "expected_neuroglancer_port": int(neuroglancer_port),
                "configured_neuroglancer_port": configured_ng_port,
            },
        )

    public_base = (neuroglancer_public_base or "").strip()
    if public_base:
        configured_public_base = str(configured.get("neuroglancer_public_base", "")).strip()
        if configured_public_base:
            _record_result(
                checks,
                "pass"
                if configured_public_base.rstrip("/") == public_base.rstrip("/")
                else "warn",
                "api.runtime_config_neuroglancer_public_base",
                "Configured neuroglancer public base aligns with expected value"
                if configured_public_base.rstrip("/") == public_base.rstrip("/")
                else "Configured neuroglancer public base differs from expected value",
                {
                    "expected_neuroglancer_public_base": public_base,
                    "configured_neuroglancer_public_base": configured_public_base,
                },
            )
        else:
            _record_result(
                checks,
                "warn",
                "api.runtime_config_neuroglancer_public_base",
                "No configured public base found in runtime log",
                {"reason": "missing_log_field"},
            )

    return checks


def check_worker_path(
    *,
    api_base: str,
    expected_worker_url: str,
    app_log_path: Path | None,
    timeout: int,
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    worker_url = _normalize_worker_url("http", expected_worker_url)

    try:
        status, payload, _ = _http_request_json(
            base_url=worker_url,
            path="/hello",
            timeout=timeout,
            raise_for_status=False,
        )
        if status == 200:
            _record_result(
                checks,
                "pass",
                "worker.hello",
                "Direct worker hello probe succeeded",
                {"status_code": status, "url": worker_url, "payload": payload},
            )
        else:
            _record_result(
                checks,
                "warn",
                "worker.hello",
                "Direct worker hello probe returned non-200",
                {"status_code": status, "url": worker_url, "payload": payload},
            )
    except Exception as exc:
        _record_result(
            checks,
            "warn",
            "worker.hello",
            "Direct worker hello probe failed",
            {"url": worker_url, "error": str(exc)},
        )

    response_status = None
    api_training_status = None
    observed_worker_url: str | None = None
    try:
        response_status, api_training_status, _ = _http_request_json(
            base_url=api_base,
            path="/training_status",
            timeout=timeout,
            raise_for_status=False,
        )

        if response_status == 200:
            _record_result(
                checks,
                "pass",
                "api.training_status",
                "API /training_status reached worker endpoint",
                {"status_code": response_status, "payload": api_training_status},
            )
            if isinstance(api_training_status, dict):
                observed_worker_url = str(
                    api_training_status.get("worker_url") or ""
                ).strip()
        else:
            _record_result(
                checks,
                "warn",
                "api.training_status",
                "API /training_status returned an error",
                {"status_code": response_status, "payload": api_training_status},
            )
            if isinstance(api_training_status, dict):
                detail = api_training_status.get("detail")
                if isinstance(detail, dict):
                    observed_worker_url = str(detail.get("worker_url") or "").strip()
                else:
                    observed_worker_url = str(api_training_status.get("worker_url") or "").strip()
    except Exception as exc:
        _record_result(
            checks,
            "warn",
            "api.training_status",
            "API /training_status request failed",
            {"error": str(exc)},
        )

    if app_log_path:
        log_rows = _tail_json_lines(app_log_path, max_lines=250)
        worker_urls = _collect_worker_proxy_urls(
            app_log_rows=log_rows,
            worker_endpoint="/training_status",
        )
        if worker_urls:
            observed_worker_url = worker_urls[-1]
            _record_result(
                checks,
                "pass",
                "api.proxy_log",
                "Read worker target from API proxy log",
                {
                    "observed_worker_url": observed_worker_url,
                    "log_path": str(app_log_path),
                },
            )
        else:
            _record_result(
                checks,
                "warn",
                "api.proxy_log",
                "No matching worker proxy events found in app log tail",
                {"log_path": str(app_log_path)},
            )
    else:
        _record_result(
            checks,
            "warn",
            "api.proxy_log",
            "No app log path available for worker proxy target check",
            {"reason": "log-path-unavailable"},
        )

    if observed_worker_url:
        observed_normalized = _normalize_worker_url(
            protocol=(
                urlsplit(observed_worker_url).scheme or "http"
            ),
            worker_url=observed_worker_url,
        )
        mismatch = observed_normalized != worker_url
        _record_result(
            checks,
            "pass" if not mismatch else "fail",
            "worker.url_mismatch",
            "Worker URL matches API proxy target"
            if not mismatch
            else "Worker URL mismatch: API appears to proxy a different target",
            {
                "expected_worker_url": worker_url,
                "observed_worker_url": observed_worker_url,
            },
        )
    else:
        _record_result(
            checks,
            "warn",
            "worker.url_mismatch",
            "Could not determine API proxy target worker URL",
            {"expected_worker_url": worker_url},
        )

    return checks


def check_workflow(api_base: str, timeout: int) -> CheckResult:
    try:
        status, payload, _ = _http_request_json(
            base_url=api_base,
            path="/api/workflows/current",
            timeout=timeout,
            raise_for_status=False,
        )
    except Exception as exc:
        return CheckResult(
            name="workflow.current",
            status="warn",
            message="Could not read current workflow",
            details={"error": str(exc)},
        )

    if status in {401, 403}:
        return CheckResult(
            name="workflow.current",
            status="warn",
            message="Current workflow endpoint requires authentication",
            details={"status_code": status},
        )
    if status != 200 or not isinstance(payload, dict):
        return CheckResult(
            name="workflow.current",
            status="warn",
            message="Current workflow endpoint returned unexpected payload/status",
            details={"status_code": status, "payload": payload},
        )

    workflow = payload.get("workflow") if isinstance(payload, dict) else None
    events = payload.get("events", [])
    if not isinstance(workflow, dict):
        return CheckResult(
            name="workflow.current",
            status="warn",
            message="Current workflow payload is missing workflow object",
            details={"payload": payload},
        )

    return CheckResult(
        name="workflow.current",
        status="pass",
        message="Current workflow endpoint is reachable",
        details={
            "workflow": workflow,
            "workflow_id": workflow.get("id"),
            "title": workflow.get("title"),
            "stage": workflow.get("stage"),
            "events": len(events) if isinstance(events, list) else 0,
        },
    )


def check_neuroglancer(
    *,
    api_base: str,
    workflow: dict[str, Any] | None,
    neuroglancer_port: int,
    neuroglancer_public_base: str | None,
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    if not workflow:
        _record_result(
            checks,
            "warn",
            "neuroglancer",
            "Skipping Neuroglancer checks: no workflow available",
            {"reason": "workflow_not_available"},
        )
        return checks

    host, _ = _host_and_port(api_base)
    if host is None:
        host = "127.0.0.1"

    if neuroglancer_port <= 0:
        _record_result(
            checks,
            "warn",
            "neuroglancer.port",
            "Configured Neuroglancer bind port is not positive",
            {"port": neuroglancer_port},
        )
    else:
        try:
            with socket.create_connection((host, neuroglancer_port), timeout=1):
                pass
            _record_result(
                checks,
                "pass",
                "neuroglancer.port",
                "Neuroglancer port is reachable",
                {
                    "host": host,
                    "port": neuroglancer_port,
                    "reachable": True,
                },
            )
        except Exception:
            _record_result(
                checks,
                "warn",
                "neuroglancer.port",
                "Neuroglancer port is not reachable from this operator node",
                {
                    "host": host,
                    "port": neuroglancer_port,
                    "reachable": False,
                },
            )

    public_base = (neuroglancer_public_base or "").strip().rstrip("/")
    if not public_base:
        _record_result(
            checks,
            "warn",
            "neuroglancer.public_base",
            "No Neuroglancer public base provided",
            {"hint": "set PYTC_NEUROGLANCER_PUBLIC_BASE in operator env"},
        )
    else:
        parsed = urlsplit(public_base)
        _record_result(
            checks,
            "pass" if parsed.scheme else "warn",
            "neuroglancer.public_base",
            "Neuroglancer public base URL format is valid"
            if parsed.scheme
            else "Neuroglancer public base is not absolute",
            {
                "value": public_base,
                "has_scheme": bool(parsed.scheme),
            },
        )

    neuroglancer_url = workflow.get("neuroglancer_url")
    if neuroglancer_url and public_base:
        if str(neuroglancer_url).startswith(public_base):
            _record_result(
                checks,
                "pass",
                "neuroglancer.url_match",
                "Workflow neuroglancer_url starts with configured public base",
                {
                    "neuroglancer_url": neuroglancer_url,
                    "public_base": public_base,
                },
            )
        else:
            _record_result(
                checks,
                "warn",
                "neuroglancer.url_match",
                "Workflow neuroglancer_url does not start with configured public base",
                {
                    "neuroglancer_url": neuroglancer_url,
                    "public_base": public_base,
                },
            )
    elif neuroglancer_url:
        _record_result(
            checks,
            "warn",
            "neuroglancer.url_match",
            "Workflow has neuroglancer_url but public base is unset",
            {"neuroglancer_url": neuroglancer_url},
        )
    else:
        _record_result(
            checks,
            "warn",
            "neuroglancer.url_match",
            "Current workflow does not expose neuroglancer_url",
            {"workflow_id": workflow.get("id")},
        )

    return checks


def check_ollama(*, api_base: str, timeout: int) -> list[CheckResult]:
    checks: list[CheckResult] = []

    ollama_base = (os.environ.get("OLLAMA_BASE_URL") or "").strip()
    if not ollama_base:
        _record_result(
            checks,
            "warn",
            "ollama.base",
            "OLLAMA_BASE_URL is not set",
            {"note": "Ollama/chat checks are limited"},
        )
        return checks

    base = _normalize_base_url(ollama_base)
    required = [
        "OLLAMA_MODEL",
        "PYTC_WORKFLOW_INTENT_MODEL",
        "OLLAMA_EMBED_MODEL",
    ]
    missing_vars = [name for name in required if not os.environ.get(name)]
    if missing_vars:
        _record_result(
            checks,
            "warn",
            "ollama.env",
            "Some Ollama-related model environment variables are unset",
            {"missing": missing_vars},
        )

    try:
        status, payload, _ = _http_request_json(
            base_url=base,
            path="/api/tags",
            timeout=timeout,
            raise_for_status=False,
        )
        if status != 200 or not isinstance(payload, dict):
            _record_result(
                checks,
                "warn",
                "ollama.models",
                "Could not query Ollama /api/tags",
                {"status_code": status, "payload": payload},
            )
        else:
            models = {
                item.get("name")
                for item in (payload.get("models") or [])
                if isinstance(item, dict)
            }
            configured = [
                os.environ.get("OLLAMA_MODEL"),
                os.environ.get("PYTC_WORKFLOW_INTENT_MODEL") or os.environ.get("OLLAMA_MODEL"),
                os.environ.get("OLLAMA_EMBED_MODEL"),
            ]
            required_models = [value for value in configured if value]
            missing_models = [
                name for name in required_models if name and name not in models
            ]
            _record_result(
                checks,
                "warn" if missing_models else "pass",
                "ollama.models",
                "Some configured Ollama models are missing from /api/tags"
                if missing_models
                else "Ollama API is reachable and configured models are present",
                {
                    "ollama_base": base,
                    "configured_models": required_models,
                    "available_models": sorted(models),
                    "missing_models": missing_models,
                },
            )
    except Exception as exc:
        _record_result(
            checks,
            "warn",
            "ollama.models",
            "Could not query Ollama /api/tags",
            {"ollama_base": base, "error": str(exc)},
        )

    try:
        status, payload, _ = _http_request_json(
            base_url=api_base,
            path="/chat/status",
            timeout=timeout,
            raise_for_status=False,
        )
        if status != 200:
            _record_result(
                checks,
                "warn",
                "ollama.chat_status",
                "Could not query API /chat/status",
                {"status_code": status, "payload": payload},
            )
        elif isinstance(payload, dict) and payload.get("configured"):
            _record_result(
                checks,
                "pass",
                "ollama.chat_status",
                "API chat status reports configured",
                payload,
            )
        else:
            _record_result(
                checks,
                "warn",
                "ollama.chat_status",
                "API chat status is not configured",
                payload,
            )
    except Exception as exc:
        _record_result(
            checks,
            "warn",
            "ollama.chat_status",
            "Could not query API /chat/status",
            {"error": str(exc)},
        )

    return checks


def check_disk_and_errors(
    *,
    app_log_path: Path | None,
    workflow_bundle_dir: Path,
    error_tail_lines: int,
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    if app_log_path:
        log_rows = _tail_json_lines(app_log_path, max_lines=error_tail_lines)
        errors = [row for row in log_rows if str(row.get("level")).upper() == "ERROR"]
        counters = Counter(row.get("event") for row in errors if isinstance(row, dict))
        _record_result(
            checks,
            "warn" if errors else "pass",
            "app_error_events",
            f"Found {len(errors)} ERROR event rows in recent app log",
            {
                "error_count": len(errors),
                "top_events": counters.most_common(6),
            },
        )
        try:
            usage = _dir_size_bytes(app_log_path.parent)
            _record_result(
                checks,
                "pass",
                "app_log_disk",
                "Computed app log parent directory disk usage",
                {
                    "path": str(app_log_path.parent),
                    "bytes": usage,
                    "human": _humanize_bytes(usage),
                },
            )
        except OSError as exc:
            _record_result(
                checks,
                "warn",
                "app_log_disk",
                "Could not compute app log disk usage",
                {"path": str(app_log_path.parent), "error": str(exc)},
            )
    else:
        _record_result(
            checks,
            "warn",
            "app_error_events",
            "No app log path available from /app/log-path",
            {"reason": "log-path-unavailable"},
        )

    try:
        bundle_exists = workflow_bundle_dir.exists()
        bundle_bytes = _dir_size_bytes(workflow_bundle_dir)
        _record_result(
            checks,
            "pass" if bundle_exists else "warn",
            "workflow_bundles_disk",
            "Computed workflow bundle directory disk usage",
            {
                "path": str(workflow_bundle_dir),
                "exists": bundle_exists,
                "bytes": bundle_bytes,
                "human": _humanize_bytes(bundle_bytes),
            },
        )
    except OSError as exc:
        _record_result(
            checks,
            "warn",
            "workflow_bundles_disk",
            "Could not compute workflow bundle disk usage",
            {"path": str(workflow_bundle_dir), "error": str(exc)},
        )

    return checks


def run_diagnostics(config: argparse.Namespace) -> list[CheckResult]:
    checks: list[CheckResult] = []

    api_base = _normalize_base_url(config.api_base)
    if not api_base:
        api_base = "http://127.0.0.1:4242"

    (
        resolved_neuroglancer_port,
        resolved_neuroglancer_public_base,
        resolved_log_tail_lines,
    ) = _demo_seg_defaults(
        api_base=api_base,
        neuroglancer_port=int(config.neuroglancer_port),
        neuroglancer_public_base=config.neuroglancer_public_base,
        log_tail_lines=config.log_tail_lines,
    )

    checks.append(check_api_health(api_base=api_base, timeout=config.timeout))

    log_path_result, api_log_path = check_app_log_path(
        api_base=api_base,
        timeout=config.timeout,
    )
    checks.append(log_path_result)

    worker_url = _normalize_worker_url(config.worker_protocol, config.worker_url)
    checks.extend(
        check_runtime_events(
            app_log_path=api_log_path,
            timeout_lines=resolved_log_tail_lines,
            expected_worker_url=worker_url,
            neuroglancer_port=resolved_neuroglancer_port,
            neuroglancer_public_base=resolved_neuroglancer_public_base,
        )
    )
    checks.extend(
        check_worker_path(
            api_base=api_base,
            expected_worker_url=worker_url,
            app_log_path=api_log_path,
            timeout=config.timeout,
        )
    )

    workflow_check = check_workflow(api_base=api_base, timeout=config.timeout)
    checks.append(workflow_check)

    checks.extend(
        check_neuroglancer(
            api_base=api_base,
            workflow=(workflow_check.details or {}).get("workflow")
            if workflow_check.status == "pass"
            else None,
            neuroglancer_port=resolved_neuroglancer_port,
            neuroglancer_public_base=resolved_neuroglancer_public_base,
        )
    )

    checks.extend(check_ollama(api_base=api_base, timeout=config.timeout))

    bundle_dir = Path(config.workflow_bundle_dir).expanduser().resolve()
    checks.extend(
        check_disk_and_errors(
            app_log_path=api_log_path,
            workflow_bundle_dir=bundle_dir,
            error_tail_lines=resolved_log_tail_lines,
        )
    )

    return checks


def render_report(checks: list[CheckResult]) -> list[str]:
    symbols = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
    lines = []
    for check in checks:
        detail = f" | {json.dumps(check.details)}" if check.details else ""
        lines.append(
            f"[{symbols.get(check.status, check.status.upper())}] "
            f"{check.name}: {check.message}{detail}"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect PyTC demo-instance runtime health and misconfiguration risks."
    )
    parser.add_argument(
        "--api-base",
        default=os.environ.get("PYTC_API_BASE", "http://127.0.0.1:4342"),
        help="API base URL",
    )
    parser.add_argument(
        "--worker-protocol",
        default=os.environ.get("PYTC_WORKER_PROTOCOL", "http"),
        help="Worker protocol (default from PYTC_WORKER_PROTOCOL)",
    )
    parser.add_argument(
        "--worker-url",
        default=os.environ.get("PYTC_WORKER_URL", "localhost:4243"),
        help="Worker URL (default from PYTC_WORKER_URL)",
    )
    parser.add_argument(
        "--neuroglancer-port",
        type=int,
        default=int(os.environ.get("PYTC_NEUROGLANCER_PORT", "4244")),
        help="Expected Neuroglancer bind port",
    )
    parser.add_argument(
        "--neuroglancer-public-base",
        default=os.environ.get("PYTC_NEUROGLANCER_PUBLIC_BASE", ""),
        help="Expected Neuroglancer public base URL",
    )
    parser.add_argument(
        "--workflow-bundle-dir",
        default=os.environ.get("PYTC_WORKFLOW_BUNDLE_DIR", ".logs/workflow-bundles"),
        help="Workflow bundle directory",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--log-tail-lines",
        type=int,
        default=120,
        help="App log rows to scan for recent events",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON report output",
    )
    args = parser.parse_args()

    checks = run_diagnostics(args)

    if args.json:
        print(
            json.dumps(
                [check.__dict__ for check in checks],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for line in render_report(checks):
            print(line)

    return 1 if any(check.status == "fail" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
