#!/usr/bin/env python3
"""Lightweight public health checks for demo.seg.bio deployment."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests


DEFAULT_DEMO_BASE = "https://demo.seg.bio"
DEFAULT_TIMEOUT = 5.0


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str
    critical: bool = True


def _build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _to_json(response: requests.Response) -> Any | None:
    try:
        return response.json()
    except ValueError:
        return None


def _require_status(
    response: requests.Response, *, expected: int, check_name: str, detail: str
) -> CheckResult:
    if response.status_code != expected:
        return CheckResult(check_name, False, f"{detail}: HTTP {response.status_code}")
    return CheckResult(check_name, True, f"{detail} (status {response.status_code})")


def _check_root(base_url: str, timeout: float) -> CheckResult:
    response = requests.get(_build_url(base_url, "/"), timeout=timeout)
    return _require_status(
        response,
        expected=200,
        check_name="root.app",
        detail="Root app path returned",
    )


def _check_json_dict(
    response: requests.Response,
    *,
    check_name: str,
    path: str,
    required_fields: list[str] | None = None,
) -> tuple[CheckResult, Any | None]:
    status_check = _require_status(
        response,
        expected=200,
        check_name=check_name,
        detail=f"{path} returned",
    )
    if not status_check.ok:
        return status_check, None

    payload = _to_json(response)
    if not isinstance(payload, dict):
        return (
            CheckResult(check_name, False, f"{path} returned non-JSON payload"),
            None,
        )

    if required_fields:
        missing = [field for field in required_fields if field not in payload]
        if missing:
            return (
                CheckResult(
                    check_name,
                    False,
                    f"{path} missing required fields: {', '.join(missing)}",
                ),
                payload,
            )

    return CheckResult(check_name, True, f"{path} returned valid JSON"), payload


def _check_workflow_routes(
    base_url: str, timeout: float
) -> tuple[list[CheckResult], dict[str, Any] | None]:
    results: list[CheckResult] = []

    canonical_path = "/api/workflows/current"
    compat_path = "/api/api/workflows/current"

    canonical_response = requests.get(_build_url(base_url, canonical_path), timeout=timeout)
    canonical_result, canonical_payload = _check_json_dict(
        canonical_response,
        check_name="workflow.current",
        path=canonical_path,
        required_fields=["workflow", "events"],
    )
    results.append(canonical_result)

    compat_response = requests.get(_build_url(base_url, compat_path), timeout=timeout)
    compat_result, compat_payload = _check_json_dict(
        compat_response,
        check_name="workflow.compat",
        path=compat_path,
        required_fields=["workflow", "events"],
    )

    if compat_result.ok and isinstance(compat_payload, dict):
        workflow = compat_payload.get("workflow")
        if isinstance(workflow, dict):
            compat_workflow_id = workflow.get("id")
            compat_result = CheckResult(
                "workflow.compat",
                True,
                f"{compat_path} returned workflow {compat_workflow_id}",
            )
    results.append(compat_result)

    workflow_payload: dict[str, Any] | None = None
    if canonical_result.ok and isinstance(canonical_payload, dict):
        workflow_payload = canonical_payload
    elif compat_result.ok and isinstance(compat_payload, dict):
        workflow_payload = compat_payload

    return results, workflow_payload


def _check_files_root(base_url: str, timeout: float) -> CheckResult:
    response = requests.get(
        _build_url(base_url, "/api/files"),
        params={"parent": "root"},
        timeout=timeout,
    )
    status_result = _require_status(
        response,
        expected=200,
        check_name="files.root",
        detail="Files root check",
    )
    if not status_result.ok:
        return status_result

    payload = _to_json(response)
    if not isinstance(payload, list):
        return CheckResult(
            "files.root",
            False,
            "Files root returned non-list JSON",
        )

    return CheckResult("files.root", True, f"Files root returned {len(payload)} entries")


def _check_project_suggestions(base_url: str, timeout: float) -> CheckResult:
    response = requests.get(_build_url(base_url, "/api/files/project-suggestions"), timeout=timeout)
    status_result = _require_status(
        response,
        expected=200,
        check_name="files.project_suggestions",
        detail="Project suggestions",
    )
    if not status_result.ok:
        return status_result

    payload = _to_json(response)
    if not isinstance(payload, list):
        return CheckResult(
            "files.project_suggestions",
            False,
            "Project suggestions returned non-list JSON",
        )

    return CheckResult(
        "files.project_suggestions",
        True,
        f"Project suggestions returned {len(payload)} entries",
    )


def _check_app_log_event(base_url: str, timeout: float) -> CheckResult:
    response = requests.post(
        _build_url(base_url, "/api/app/log-event"),
        json={
            "event": "demo.health_check",
            "level": "INFO",
            "message": "demo health check",
            "source": "check_demo_health.py",
            "data": {
                "check": "public_demo_health",
            },
        },
        timeout=timeout,
        headers={"Content-Type": "application/json"},
    )
    status_result = _require_status(
        response,
        expected=200,
        check_name="app.log_event",
        detail="App log event endpoint",
    )
    if not status_result.ok:
        return status_result

    payload = _to_json(response)
    if not isinstance(payload, dict):
        return CheckResult("app.log_event", False, "App log event returned non-JSON payload")

    status_value = str(payload.get("status", "")).lower()
    if status_value not in {"ok", "success"}:
        return CheckResult(
            "app.log_event",
            False,
            f"App log event returned unexpected status payload: {payload!r}",
        )

    return CheckResult("app.log_event", True, "App log event accepted")


def _check_viewer_health(
    base_url: str,
    timeout: float,
    *,
    workflow_payload: dict[str, Any] | None,
    configured_url: str | None,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    candidate = (configured_url or "").strip()

    if not candidate and workflow_payload:
        workflow = workflow_payload.get("workflow")
        if isinstance(workflow, dict):
            candidate = str(workflow.get("neuroglancer_url", "")).strip()

    if not candidate:
        return [
            CheckResult(
                "viewer.health",
                False,
                "No viewer URL available; skipped",
                critical=False,
            )
        ]

    if candidate.startswith("/"):
        candidate = urljoin(base_url.rstrip("/") + "/", candidate.lstrip("/"))

    response = requests.get(candidate, timeout=timeout)
    status_result = _require_status(
        response,
        expected=200,
        check_name="viewer.health",
        detail="Neuroglancer viewer",
    )
    if not status_result.ok:
        return [status_result]

    return [
        CheckResult(
            "viewer.health",
            True,
            f"Neuroglancer viewer check passed for {candidate}",
        )
    ]


def _format_result(result: CheckResult) -> str:
    label = "PASS" if result.ok else "FAIL"
    if not result.ok and not result.critical:
        label = "SKIP"
    return f"[{label}] {result.name}: {result.message}"


def run(base_url: str, timeout: float, neuroglancer_url: str | None = None) -> int:
    checks: list[CheckResult] = []

    checks.append(_check_root(base_url, timeout))

    workflow_results, workflow_payload = _check_workflow_routes(base_url, timeout)
    checks.extend(workflow_results)

    checks.append(_check_files_root(base_url, timeout))
    checks.append(_check_project_suggestions(base_url, timeout))
    checks.append(_check_app_log_event(base_url, timeout))
    checks.extend(
        _check_viewer_health(
            base_url,
            timeout,
            workflow_payload=workflow_payload,
            configured_url=neuroglancer_url,
        )
    )

    for result in checks:
        print(_format_result(result))

    failed = [result for result in checks if result.critical and not result.ok]
    if failed:
        print(f"\nHealth check failed ({len(failed)} failing checks)")
        for check in failed:
            print(f" - {check.name}: {check.message}")
        return 1

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run demo.seg.bio health checks")
    parser.add_argument(
        "--base",
        default=os.environ.get("DEMO_BASE_URL", DEFAULT_DEMO_BASE),
        help=f"Demo base URL (default: {DEFAULT_DEMO_BASE})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--neuroglancer-url",
        default=os.environ.get("DEMO_NEUROGLANCER_URL", ""),
        help="Override Neuroglancer URL to probe for viewer health",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sys.exit(
        run(
            base_url=args.base,
            timeout=args.timeout,
            neuroglancer_url=args.neuroglancer_url,
        )
    )


if __name__ == "__main__":
    main()
