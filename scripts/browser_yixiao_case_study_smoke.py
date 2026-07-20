#!/usr/bin/env python3
"""Browser-level regression smoke for the Yixiao TapeReader XRI case-study UI.

The script exercises the live React UI end-to-end in a browser:
- application loads
- Yixiao project appears mounted in Files
- progress summary reads 10/6/2/2
- assistant drawer opens and responds to project/training queries
- training proposal card is editable, and edited fields can be canceled
- training proposal card text is not obviously clipped at the standard viewport
- refresh/reopen keeps the app in a continuable state

If Playwright is not installed, the script fails with an explicit install gap
message so operators know the exact dependency command.
"""

from __future__ import annotations

import argparse
import json
import shlex
import re
import time
import sys
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

DEFAULT_BASE_URL = "http://127.0.0.1:3000"
DEFAULT_REPORT = "/tmp/yixiao-browser-case-study-smoke.json"
PROJECT_NAME = "Yixiao TapeReader XRI Case Study"
VIEWPORT_DEFAULT = (1280, 900)
EXPECTED_PROGRESS = {
    "Tracked volumes": 10,
    "Fully good": 6,
    "Needs proofreading": 2,
    "No segmentation": 2,
}
EXPECTED_COMPLETION_PERCENT = 60
EXPECTED_SEGMENTATION_COVERAGE_PERCENT = 80
PROJECT_ROOT_ENTRIES = [
    "data",
    "configs",
    "notes",
    "outputs",
    "snapshots",
    "project_manifest.json",
]
PLAYWRIGHT_INSTALL_HINT = """playwright is not installed.
Install with:
  {python} -m pip install playwright
  {python} -m playwright install chromium"""


def _playwright_install_hint() -> str:
    python = shlex.quote(sys.executable or "python3")
    return PLAYWRIGHT_INSTALL_HINT.format(python=python)


def _raise_playwright_error(context: str) -> RuntimeError:
    return RuntimeError(f"{_playwright_install_hint()}\nObserved issue: {context}")


def _normalize_progress_labels(raw: str) -> str:
    return (raw or "").replace("\n", " ").strip()


def _extract_progress_from_text(
    raw_text: str,
) -> Tuple[Dict[str, int], Optional[int], Optional[int]]:
    """Extract summary fields from visible page text.

    Returns:
        (label->value, completion_pct, segmentation_coverage_pct)
    """

    text = _normalize_progress_labels(raw_text)
    values: Dict[str, int] = {}
    for label, expected in EXPECTED_PROGRESS.items():
        # Keep this tolerant of layout-specific whitespace/newlines.
        match = re.search(
            rf"{re.escape(label)}\s*[^0-9]*?(\"?\d+)?,?", text, re.IGNORECASE
        )
        if not match:
            continue
        if match.group(1):
            try:
                values[label] = int(match.group(1))
            except ValueError:
                pass

    completion_match = re.search(r"Completion[^0-9%]{0,40}(\d{1,3})%", text)
    completion_pct = int(completion_match.group(1)) if completion_match else None

    segcov_match = re.search(
        r"Segmentation coverage:\s*(\d{1,3})%",
        text,
        re.IGNORECASE,
    )
    segcov_pct = int(segcov_match.group(1)) if segcov_match else None
    return values, completion_pct, segcov_pct


def _build_arg_parser() -> argparse.ArgumentParser:
    hint = _playwright_install_hint()
    parser = argparse.ArgumentParser(
        description="Browser smoke test for Yixiao TapeReader XRI case-study UI",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"If Playwright is missing or missing browsers:\n{hint}",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=(
            "Frontend URL to load."
            " Defaults to local demo frontend (127.0.0.1:3000)."
            " Pass --base-url https://demo.seg.bio for production-like checks."
        ),
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=30_000,
        help=("Timeout in ms for each high-level UI wait step. " "Defaults to 30000."),
    )
    parser.add_argument(
        "--viewport",
        default=f"{VIEWPORT_DEFAULT[0]}x{VIEWPORT_DEFAULT[1]}",
        help="Viewport as WIDTHxHEIGHT. Defaults to 1280x900.",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run Playwright with browser UI visible.",
    )
    parser.add_argument(
        "--report",
        default=DEFAULT_REPORT,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--skip-assistant",
        action="store_true",
        help="Skip assistant queries (still validates load, project mount, and progress).",
    )
    parser.add_argument(
        "--skip-reload",
        action="store_true",
        help="Skip refresh/reopen continuity checks.",
    )
    return parser


def _parse_viewport(value: str) -> Tuple[int, int]:
    if not value:
        return VIEWPORT_DEFAULT
    width_height = value.lower().split("x", 1)
    if len(width_height) != 2:
        raise argparse.ArgumentTypeError("viewport must be WIDTHxHEIGHT, e.g. 1280x900")
    width = int(width_height[0])
    height = int(width_height[1])
    if width < 320 or height < 320:
        raise argparse.ArgumentTypeError("viewport dimensions must be >= 320")
    return width, height


def _playwright_import_error() -> Optional[BaseException]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        return None
    except ModuleNotFoundError as exc:
        return exc
    except Exception as exc:  # pragma: no cover - defensive for odd envs
        return exc if isinstance(exc, ImportError) else ImportError(str(exc))


def _resolve_browser_playwright(playwright) -> None:
    browsers = [
        ("chromium", playwright.chromium),
        ("firefox", playwright.firefox),
        ("webkit", playwright.webkit),
    ]
    errors: List[str] = []
    for name, launcher in browsers:
        try:
            browser = launcher.launch(headless=True)
            browser.close()
            return
        except Exception as exc:  # pragma: no cover - engine-specific runtime behavior
            errors.append(f"{name}: {exc}")
    raise RuntimeError(
        f"No Playwright browser runtime was available. Attempts: {'; '.join(errors)}"
    )


def _open_tab(page, label: str):
    menu_item = page.locator(".pytc-top-menu .ant-menu-item").filter(
        has_text=label,
    )
    if not menu_item.count():
        raise AssertionError(f"Top-level tab '{label}' not found.")
    menu_item.first.click()
    # let animation/layout settle
    page.wait_for_timeout(250)


def _is_text_visible(page, text: str) -> bool:
    locator = page.get_by_text(re.compile(re.escape(text), re.IGNORECASE))
    return locator.count() > 0 and locator.first.is_visible()


def _wait_for_project_mount(page, timeout_ms: int) -> None:
    if _is_text_visible(page, PROJECT_NAME):
        return

    suggest_button = page.get_by_role(
        "button", name=re.compile(r"Use suggested project|Open suggested project", re.I)
    )
    if suggest_button.count() > 0 and suggest_button.first.is_enabled():
        suggest_button.first.click()
        try:
            page.get_by_text(re.compile(re.escape(PROJECT_NAME), re.I)).wait_for(
                timeout=timeout_ms,
            )
            return
        except Exception:
            pass

    if not _is_text_visible(page, PROJECT_NAME):
        raise AssertionError(
            f"Could not find mounted project '{PROJECT_NAME}' on Files page."
        )


def _assert_required_project_entries(page, timeout_ms: int) -> None:
    for entry in PROJECT_ROOT_ENTRIES:
        locator = page.get_by_text(re.compile(rf"\b{re.escape(entry)}\b", re.I))
        if locator.count() == 0:
            raise AssertionError(
                f"Required project entry '{entry}' not visible on the page"
            )
        try:
            locator.first.wait_for(timeout=timeout_ms)
        except Exception as exc:
            raise AssertionError(
                f"Required project entry '{entry}' never appeared"
            ) from exc


def _extract_progress_snapshot(page) -> Dict[str, Any]:
    script = r"""
    () => {
      const labels = {
        "Tracked volumes": "tracked",
        "Fully good": "good",
        "Needs proofreading": "proofread",
        "No segmentation": "missing",
      };
      const byLabel = {};
      const cards = Array.from(document.querySelectorAll('.ant-card'));
      const parseTextNumber = (value) => {
        if (typeof value !== 'string') return null;
        const m = value.match(/([0-9]{1,4})/);
        return m ? Number(m[1]) : null;
      };
      for (const card of cards) {
        const lines = Array.from(card.querySelectorAll('*'))
          .map((el) => (el.textContent || '').trim())
          .flatMap((text) => text.split('\n'))
          .map((text) => text.trim())
          .filter(Boolean);
        for (let i = 0; i < lines.length - 1; i += 1) {
          const line = lines[i];
          if (!labels[line]) continue;
          let j = i + 1;
          while (j < lines.length && !lines[j].match(/[0-9]/)) j += 1;
          if (j >= lines.length) continue;
          const value = parseTextNumber(lines[j]);
          if (Number.isFinite(value)) {
            byLabel[labels[line]] = value;
          }
        }
      }

      const text = document.body ? (document.body.innerText || '') : '';
      const completionMatch = text.match(/Completion[^0-9%]{0,50}(\d{1,3})%/i);
      const segMatch = text.match(/Segmentation coverage:\s*(\d{1,3})%/i);
      return {
        metrics: byLabel,
        completion_percent: completionMatch ? Number(completionMatch[1]) : null,
        segmentation_coverage_percent: segMatch ? Number(segMatch[1]) : null,
      };
    }
    """
    return page.evaluate(script)


def _assert_progress(snapshot: Dict[str, Any]) -> None:
    metrics = snapshot.get("metrics") or {}
    expected_metric_map = {
        "tracked": EXPECTED_PROGRESS["Tracked volumes"],
        "good": EXPECTED_PROGRESS["Fully good"],
        "proofread": EXPECTED_PROGRESS["Needs proofreading"],
        "missing": EXPECTED_PROGRESS["No segmentation"],
    }
    for key, expected in expected_metric_map.items():
        actual = metrics.get(key)
        if actual != expected:
            raise AssertionError(
                f"Progress metric '{key}' expected {expected}, got {actual}"
            )

    completion_pct = snapshot.get("completion_percent")
    segcov_pct = snapshot.get("segmentation_coverage_percent")
    if completion_pct != EXPECTED_COMPLETION_PERCENT:
        raise AssertionError(
            f"completion_pct expected {EXPECTED_COMPLETION_PERCENT}, got {completion_pct}"
        )
    if segcov_pct != EXPECTED_SEGMENTATION_COVERAGE_PERCENT:
        raise AssertionError(
            "segmentation_coverage_pct expected "
            f"{EXPECTED_SEGMENTATION_COVERAGE_PERCENT}, got {segcov_pct}"
        )


def _open_assistant(page) -> None:
    open_buttons = page.locator(".pytc-top-nav button.ant-btn-circle")
    if open_buttons.count() < 1:
        raise AssertionError("Could not find assistant open button on top nav")
    open_buttons.last.click()
    close_button = page.locator('button[aria-label="Close assistant"]')
    close_button.wait_for(state="visible", timeout=8000)


def _send_assistant_query(page, query: str, timeout_ms: int) -> str:
    messages = page.locator(".ant-list-item")
    before = messages.count()

    input_box = page.get_by_placeholder("Message")
    input_box.fill("")
    input_box.type(query)
    input_box.press("Enter")

    # Wait for at least one new list item (user message + assistant response may still be pending).
    page.wait_for_function(
        f"() => document.querySelectorAll('.ant-list-item').length > {before}",
        timeout=timeout_ms,
    )

    # Wait for a fresh assistant response containing non-empty text.
    def _wait_for_reply() -> str:
        for _ in range(max(1, timeout_ms // 250)):
            items = messages.all_inner_texts()
            if len(items) <= before:
                page.wait_for_timeout(250)
                continue
            candidate = items[-1]
            if candidate and candidate.strip():
                return candidate
            page.wait_for_timeout(250)
        raise AssertionError("No assistant reply text appeared in time")

    reply = _wait_for_reply()
    return reply


def _wait_for_training_proposal(page, timeout_ms: int):
    locator = page.locator("section[aria-label^='proposal-']").filter(
        has_text="Approve Training Run"
    )
    locator.first.wait_for(timeout=timeout_ms)
    return locator.first


def _check_proposal_editing(page, proposal_locator) -> Dict[str, Any]:
    edit_button = proposal_locator.locator('button:has-text("Edit details")')
    if edit_button.count() == 0:
        raise AssertionError("Training proposal did not expose an edit affordance.")
    edit_button.first.click()

    editable_fields = proposal_locator.locator('[aria-label^="Edit "]')
    if editable_fields.count() == 0:
        raise AssertionError(
            "Training proposal edit mode did not expose any editable fields."
        )

    editable_field = editable_fields.first
    field_label = editable_field.get_attribute("aria-label") or "Edit field"
    original_value = editable_field.input_value()
    test_value = f"{original_value} [smoke-edit-check]"
    editable_field.fill(test_value)
    page.wait_for_timeout(250)

    approve_button = proposal_locator.locator('button:has-text("Approve with edits")')
    if approve_button.count() == 0:
        raise AssertionError(
            "Proposal edit flow did not flag edited fields as expected."
        )

    cancel_button = proposal_locator.locator('button:has-text("Cancel edits")')
    if cancel_button.count() == 0:
        raise AssertionError("Proposal edit flow did not expose a cancel option.")
    cancel_button.first.click()
    page.wait_for_timeout(250)

    if proposal_locator.locator('[aria-label^="Edit "]').count() > 0:
        raise AssertionError("Proposal edit mode did not close after cancel.")
    return {
        "editable_fields": editable_fields.count(),
        "edited_field_label": field_label,
        "edit_flow": "passed",
    }


def _check_proposal_card_for_text_clipping(page, proposal_locator) -> Dict[str, Any]:
    details = page.evaluate(
        """
        (el) => {
          const node = typeof el === 'string' ? document.querySelector(el) : el;
          if (!node) {
            return {found: false, overflow: true, reasons: ['proposal element not found']};
          }
          const isVisible = (element) => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const offenders = [];
          const walk = (element) => {
            const children = Array.from(element.querySelectorAll('*'));
            for (const child of children) {
              if (!isVisible(child)) continue;
              const style = getComputedStyle(child);
              if (style.overflowX === 'hidden' && child.scrollWidth > child.clientWidth + 1) {
                offenders.push({
                  text: (child.textContent || '').slice(0, 140),
                  clientWidth: child.clientWidth,
                  scrollWidth: child.scrollWidth,
                  clientHeight: child.clientHeight,
                  scrollHeight: child.scrollHeight,
                  overflowX: style.overflowX,
                });
              }
              if (child.scrollWidth > child.clientWidth + 1) {
                offenders.push({
                  text: (child.textContent || '').slice(0, 140),
                  clientWidth: child.clientWidth,
                  scrollWidth: child.scrollWidth,
                  clientHeight: child.clientHeight,
                  scrollHeight: child.scrollHeight,
                  overflowX: style.overflowX,
                });
              }
            }
          };
          walk(node);
          const proposalWidth = node.getBoundingClientRect().width;
          return {
            found: true,
            overflow: offenders.length > 0,
            proposalWidth,
            count: offenders.length,
            offenders: offenders.slice(0, 5),
          };
        }
        """,
        proposal_locator,
    )
    if details.get("overflow"):
        raise AssertionError(
            f"Proposal card appears horizontally clipped: {json.dumps(details)}"
        )
    return details


def _refresh_and_reopen_checks(page, timeout_ms: int, skip_assistant: bool) -> None:
    page.reload(wait_until="networkidle")
    page.wait_for_load_state("domcontentloaded")
    _open_tab(page, "Files")
    page.wait_for_timeout(400)
    _wait_for_project_mount(page, timeout_ms)

    _open_tab(page, "Workflow")
    page.wait_for_timeout(300)
    snapshot = _extract_progress_snapshot(page)
    _assert_progress(snapshot)

    if skip_assistant:
        return

    _open_assistant(page)
    reply = _send_assistant_query(
        page,
        "what project are we looking at?",
        timeout_ms=timeout_ms,
    )
    if "yixiao" not in reply.lower():
        raise AssertionError(
            f"Assistant did not mention Yixiao after reload. Reply: {reply}"
        )


def run_smoke(
    base_url: str,
    timeout_ms: int,
    viewport: Tuple[int, int],
    headless: bool,
    skip_assistant: bool,
    skip_reload: bool,
) -> Dict[str, Any]:
    result = {
        "passed": True,
        "base_url": base_url,
        "checks": [],
    }

    viewport_config = {"width": viewport[0], "height": viewport[1]}
    playwright_error = _playwright_import_error()
    if playwright_error is not None:
        raise _raise_playwright_error(str(playwright_error))

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # Pick a working engine once to avoid launch failures at runtime.
        try:
            _resolve_browser_playwright(p)
        except RuntimeError as exc:
            raise _raise_playwright_error(str(exc))
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport=viewport_config)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            page.goto(base_url, wait_until="networkidle", timeout=timeout_ms)
            if "Yixiao" in (page.title() or ""):
                result["checks"].append("page loaded")
            else:
                result["checks"].append(f"page title: {page.title()}")

            _open_tab(page, "Files")
            page.wait_for_timeout(300)

            _wait_for_project_mount(page, timeout_ms)
            _assert_required_project_entries(page, timeout_ms)
            result["checks"].append("project mounted")

            _open_tab(page, "Workflow")
            page.wait_for_timeout(300)
            snapshot = _extract_progress_snapshot(page)
            _assert_progress(snapshot)
            result["checks"].append("progress counts verified")
            result["progress_snapshot"] = snapshot

            if not skip_assistant:
                _open_assistant(page)
                result["checks"].append("assistant opened")

                project_reply = _send_assistant_query(
                    page,
                    "what project are we looking at?",
                    timeout_ms,
                )
                if "yixiao" not in project_reply.lower():
                    raise AssertionError(
                        "Assistant did not confirm Yixiao case-study context."
                    )
                result["checks"].append("assistant project context check")

                _send_assistant_query(
                    page,
                    "train on the fully good masks to segment the image-only volumes",
                    timeout_ms,
                )
                proposal = _wait_for_training_proposal(page, timeout_ms)
                edit_report = _check_proposal_editing(page, proposal)
                overflow_report = _check_proposal_card_for_text_clipping(page, proposal)
                result["checks"].append("assistant proposal editing check")
                result["proposal_edit_report"] = edit_report
                result["checks"].append("assistant proposal card text clipping check")
                result["proposal_card_metrics"] = overflow_report

            if not skip_reload:
                _refresh_and_reopen_checks(
                    page, timeout_ms, skip_assistant=skip_assistant
                )
                result["checks"].append("refresh/reopen continuity check")

        finally:
            context.close()
            browser.close()

    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("base-url must include a scheme, e.g. http://127.0.0.1:3000")

    viewport = _parse_viewport(args.viewport)
    timeout_ms = max(5000, int(args.timeout_ms))

    report: Dict[str, Any] = {
        "generated_at_unix": time.time(),
        "script": __file__,
    }

    try:
        checks = run_smoke(
            base_url=base_url,
            timeout_ms=timeout_ms,
            viewport=viewport,
            headless=not args.no_headless,
            skip_assistant=args.skip_assistant,
            skip_reload=args.skip_reload,
        )
        report.update(checks)
        report["passed"] = True
        print("Yixiao browser smoke passed.")
    except Exception as exc:
        report.update(
            {
                "passed": False,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
        )
        print(f"Yixiao browser smoke failed: {exc}")

    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(f"Report: {args.report}")

    if not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
