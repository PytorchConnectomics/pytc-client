from __future__ import annotations

import json

from scripts import browser_synthetic_core_smoke as smoke


def test_parser_defaults_target_local_synthetic_app() -> None:
    args = smoke._build_arg_parser().parse_args([])

    assert args.base_url == smoke.DEFAULT_BASE_URL
    assert args.report == smoke.DEFAULT_REPORT
    assert args.viewport == "1280x900"
    assert not args.skip_reload


def test_main_records_a_successful_smoke(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        smoke,
        "run_smoke",
        lambda **kwargs: {
            "passed": True,
            "base_url": kwargs["base_url"],
            "checks": ["bounded file picker navigated"],
        },
    )
    report_path = tmp_path / "report.json"

    result = smoke.main(["--skip-reload", "--report", str(report_path)])

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["checks"] == ["bounded file picker navigated"]


def test_main_records_browser_failures(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        smoke,
        "run_smoke",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("picker failed")),
    )
    report_path = tmp_path / "failed.json"

    result = smoke.main(["--report", str(report_path)])

    assert result == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["error"] == "picker failed"
