from __future__ import annotations

import json
import argparse
import pytest

from scripts import browser_yixiao_case_study_smoke as smoke


def test_parse_viewport_defaults_when_empty() -> None:
    assert smoke._parse_viewport("") == smoke.VIEWPORT_DEFAULT


def test_parse_viewport_rejects_small_values() -> None:
    for value in ["319x800", "800x319", "100x100"]:
        try:
            smoke._parse_viewport(value)
            raise AssertionError(f"expected ValueError for {value}")
        except argparse.ArgumentTypeError:
            pass


def test_parse_viewport_parses_valid_dimensions() -> None:
    assert smoke._parse_viewport("1920x1080") == (1920, 1080)


def test_extract_progress_from_text_parses_metrics_and_rates() -> None:
    raw = """
        Tracked volumes
        10
        Fully good
        6
        Needs proofreading
        2
        No segmentation
        2
        Completion
        60%
        Segmentation coverage: 80%
    """

    values, completion_pct, segmentation_pct = smoke._extract_progress_from_text(raw)

    assert values == {
        "Tracked volumes": 10,
        "Fully good": 6,
        "Needs proofreading": 2,
        "No segmentation": 2,
    }
    assert completion_pct == 60
    assert segmentation_pct == 80


def test_arg_parser_defaults_are_browser_ready() -> None:
    args = smoke._build_arg_parser().parse_args([])

    assert args.base_url == smoke.DEFAULT_BASE_URL
    assert args.report == smoke.DEFAULT_REPORT
    assert args.viewport == f"{smoke.VIEWPORT_DEFAULT[0]}x{smoke.VIEWPORT_DEFAULT[1]}"
    assert args.timeout_ms == 30_000
    assert not args.no_headless
    assert not args.skip_assistant
    assert not args.skip_reload


def test_run_smoke_raises_install_guidance_when_playwright_missing(monkeypatch) -> None:
    monkeypatch.setattr(smoke, "_playwright_import_error", lambda: ModuleNotFoundError("no module named playwright"))

    with pytest.raises(RuntimeError) as exc:
        smoke.run_smoke(
            base_url=smoke.DEFAULT_BASE_URL,
            timeout_ms=10_000,
            viewport=smoke.VIEWPORT_DEFAULT,
            headless=True,
            skip_assistant=False,
            skip_reload=False,
        )

    message = str(exc.value)
    assert "Observed issue:" in message
    assert "no module named playwright" in message
    assert smoke._playwright_install_hint() in message


def test_main_applies_timeout_minimum_and_writes_success_report(
    monkeypatch,
    tmp_path,
) -> None:
    captured = {}

    def fake_run_smoke(
        base_url,
        timeout_ms,
        viewport,
        headless,
        skip_assistant,
        skip_reload,
    ):
        captured.update(
            {
                "base_url": base_url,
                "timeout_ms": timeout_ms,
                "viewport": viewport,
                "headless": headless,
                "skip_assistant": skip_assistant,
                "skip_reload": skip_reload,
            },
        )
        return {
            "checks": ["page loaded"],
            "base_url": base_url,
            "progress_snapshot": {
                "metrics": {
                    "tracked": 10,
                    "good": 6,
                    "proofread": 2,
                    "missing": 2,
                },
                "completion_percent": 60,
                "segmentation_coverage_percent": 80,
            },
        }

    monkeypatch.setattr(smoke, "run_smoke", fake_run_smoke)
    report_path = tmp_path / "browser-report.json"

    result = smoke.main(
        [
            "--base-url",
            "https://demo.seg.bio",
            "--timeout-ms",
            "1000",
            "--viewport",
            "1280x900",
            "--skip-assistant",
            "--skip-reload",
            "--report",
            str(report_path),
        ],
    )

    assert result == 0
    assert report_path.exists()
    assert captured["timeout_ms"] == 5000
    assert captured["headless"] is True
    assert captured["skip_assistant"] is True
    assert captured["skip_reload"] is True
    assert captured["viewport"] == smoke.VIEWPORT_DEFAULT

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["base_url"] == "https://demo.seg.bio"
    assert report["checks"] == ["page loaded"]
    assert report["progress_snapshot"]["completion_percent"] == 60
    assert report["progress_snapshot"]["segmentation_coverage_percent"] == 80


def test_main_writes_error_shape_on_failure(monkeypatch, tmp_path) -> None:
    def fake_run_smoke(*_args, **_kwargs):
        raise RuntimeError("playwright is not ready")

    monkeypatch.setattr(smoke, "run_smoke", fake_run_smoke)
    report_path = tmp_path / "browser-failed.json"

    result = smoke.main(
        [
            "--report",
            str(report_path),
        ]
    )

    assert result == 1
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["error"] == "playwright is not ready"
    assert report["error_type"] == "RuntimeError"
