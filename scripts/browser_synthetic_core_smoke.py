#!/usr/bin/env python3
"""Browser smoke for the deterministic synthetic core project."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.browser_yixiao_case_study_smoke import (
    DEFAULT_BASE_URL,
    VIEWPORT_DEFAULT,
    _extract_progress_snapshot,
    _open_tab,
    _parse_viewport,
    _playwright_import_error,
    _raise_playwright_error,
    _resolve_browser_playwright,
)

PROJECT_TITLE = "Synthetic Segmentation Core Loop"
PROJECT_MOUNT_LABEL = PROJECT_TITLE
EXPECTED_PROGRESS = {
    "tracked": 4,
    "good": 2,
    "proofread": 1,
    "missing": 1,
}
DEFAULT_REPORT = "/tmp/synthetic-core-browser-smoke.json"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument(
        "--viewport",
        default=f"{VIEWPORT_DEFAULT[0]}x{VIEWPORT_DEFAULT[1]}",
    )
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--skip-reload", action="store_true")
    parser.add_argument("--report", default=DEFAULT_REPORT)
    return parser


def _assert_progress(page) -> Dict[str, Any]:
    snapshot = _extract_progress_snapshot(page)
    for key, expected in EXPECTED_PROGRESS.items():
        actual = (snapshot.get("metrics") or {}).get(key)
        if actual != expected:
            raise AssertionError(
                f"Synthetic progress metric {key!r} expected {expected}, got {actual}"
            )
    return snapshot


def _open_file_picker(page, timeout_ms: int) -> None:
    _open_tab(page, "Visualize")
    page.get_by_role("button", name="Browse", exact=True).first.click()
    dialog = page.get_by_role("dialog", name="Select File")
    dialog.wait_for(state="visible", timeout=timeout_ms)
    if dialog.get_by_text("Files unavailable").count():
        raise AssertionError("Browse modal reported that files were unavailable")

    project_row = dialog.locator(".file-picker-item").filter(
        has_text=PROJECT_MOUNT_LABEL
    )
    project_row.first.wait_for(state="visible", timeout=timeout_ms)
    project_row.first.click()
    data_row = dialog.locator(".file-picker-item").filter(has_text="data")
    data_row.first.wait_for(state="visible", timeout=timeout_ms)
    data_row.first.click()
    raw_row = dialog.locator(".file-picker-item").filter(has_text="raw")
    raw_row.first.wait_for(state="visible", timeout=timeout_ms)
    raw_row.first.click()
    preview = dialog.get_by_role("img", name="train-01_image.h5")
    preview.wait_for(state="attached", timeout=timeout_ms)
    page.wait_for_function(
        "image => image.complete && image.naturalWidth > 0",
        arg=preview.element_handle(),
        timeout=timeout_ms,
    )
    if dialog.get_by_text("Files unavailable").count():
        raise AssertionError("Browse modal failed after opening the project folder")
    dialog.get_by_role("button", name="Close").click()


def _exercise_core_ui(page, timeout_ms: int) -> Dict[str, Any]:
    page.get_by_text(PROJECT_TITLE, exact=True).first.wait_for(
        state="visible", timeout=timeout_ms
    )
    _open_tab(page, "Files")
    page.get_by_text(PROJECT_MOUNT_LABEL, exact=True).first.wait_for(
        state="visible", timeout=timeout_ms
    )
    _open_file_picker(page, timeout_ms)
    _open_tab(page, "Workflow")
    page.wait_for_timeout(300)
    return _assert_progress(page)


def run_smoke(
    *,
    base_url: str,
    timeout_ms: int,
    viewport: Tuple[int, int],
    headless: bool,
    skip_reload: bool,
) -> Dict[str, Any]:
    playwright_error = _playwright_import_error()
    if playwright_error is not None:
        raise _raise_playwright_error(str(playwright_error))

    from playwright.sync_api import sync_playwright

    result: Dict[str, Any] = {"passed": True, "base_url": base_url, "checks": []}
    with sync_playwright() as playwright:
        try:
            browser = _resolve_browser_playwright(playwright, headless=headless)
        except RuntimeError as exc:
            raise _raise_playwright_error(str(exc)) from exc
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]}
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page_errors: List[str] = []
        api_failures: List[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "response",
            lambda response: (
                api_failures.append(
                    f"{response.status} {response.request.method} {response.url}"
                )
                if response.status >= 500 and "/api" in response.url
                else None
            ),
        )
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
            snapshot = _exercise_core_ui(page, timeout_ms)
            result["checks"].extend(
                [
                    "synthetic project loaded",
                    "bounded file picker navigated",
                    "bounded volume preview decoded",
                    "progress counts verified",
                ]
            )
            result["progress_snapshot"] = snapshot

            if not skip_reload:
                page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
                _exercise_core_ui(page, timeout_ms)
                result["checks"].append("reload continuity verified")

            if page_errors:
                raise AssertionError(f"Browser page errors: {page_errors}")
            if api_failures:
                raise AssertionError(f"API 5xx responses: {api_failures}")
        finally:
            context.close()
            browser.close()
    return result


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    base_url = args.base_url.rstrip("/")
    if urlparse(base_url).scheme not in {"http", "https"}:
        raise ValueError("base-url must include an http or https scheme")

    report: Dict[str, Any] = {
        "generated_at_unix": time.time(),
        "script": str(Path(__file__).resolve()),
    }
    try:
        report.update(
            run_smoke(
                base_url=base_url,
                timeout_ms=max(5_000, args.timeout_ms),
                viewport=_parse_viewport(args.viewport),
                headless=not args.no_headless,
                skip_reload=args.skip_reload,
            )
        )
    except Exception as exc:
        report.update(
            passed=False,
            error=str(exc),
            error_type=exc.__class__.__name__,
        )

    Path(args.report).write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        "Synthetic browser smoke passed."
        if report.get("passed")
        else f"Synthetic browser smoke failed: {report.get('error')}"
    )
    print(f"Report: {args.report}")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
