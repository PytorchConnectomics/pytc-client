from argparse import Namespace

import pytest

from scripts import run_yixiao_case_study_smoke as smoke


def _fake_pre_demo_args(tmp_path, *, skip_readiness_check=False, skip_export_check=False):
    return Namespace(
        base_url="http://127.0.0.1:4342",
        project_root=str(tmp_path),
        holdout_root=str(tmp_path / "holdout"),
        workflow_id=None,
        report=str(tmp_path / "pre-demo-gate.json"),
        agent_timeout=10,
        closed_loop_rehearsal=False,
        closed_loop_crop="0:8,0:128,0:128",
        closed_loop_training_iterations=2,
        closed_loop_inference_iterations=1,
        pre_demo_gate=True,
        skip_readiness_check=skip_readiness_check,
        skip_export_check=skip_export_check,
        reset_fixture=False,
        reset_workspace=True,
        mount_project=True,
        reset_workflow=True,
        exercise_promotion=False,
        prepare_live=True,
        skip_agent=True,
        verbose=False,
    )


def _setup_fake_run(monkeypatch):
    calls = []

    def fake_run(args):
        calls.append(args.report)
        if "baseline" in args.report:
            return {
                "workflow_id": 100,
                "viewer_url": "https://demo.seg.bio/neuroglancer/v/base/",
                "passed": True,
            }
        if "promotion" in args.report:
            return {
                "workflow_id": 100,
                "viewer_url": "https://demo.seg.bio/neuroglancer/v/promo/",
                "passed": True,
            }
        return {
            "workflow_id": 101,
            "viewer_url": "https://demo.seg.bio/neuroglancer/v/restore/",
            "passed": True,
        }

    monkeypatch.setattr(smoke, "run", fake_run)
    return calls


def test_pre_demo_gate_reports_residual_readiness_caveat(monkeypatch, tmp_path):
    _setup_fake_run(monkeypatch)

    manifest_path = tmp_path / "bundle-manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")

    def fake_request_json(self, method, path, payload=None, timeout=30):
        if path.endswith("/case-study-readiness"):
            return {
                "workflow_id": 101,
                "ready_for_case_study": False,
                "completed_count": 1,
                "total_count": 3,
                "gates": [],
                "next_required_items": ["before/after evaluation"],
            }
        if path.endswith("/export-bundle"):
            return {
                "schema_version": "workflow-export-bundle/v1",
                "workflow_id": 101,
                "events": [],
                "artifacts": [],
                "model_runs": [],
                "model_versions": [],
                "correction_sets": [],
                "agent_plans": [],
                "bundle_directory": str(tmp_path),
                "bundle_manifest_path": str(manifest_path),
            }
        pytest.fail(f"unexpected path: {path}")

    monkeypatch.setattr(smoke.SmokeHarness, "request_json", fake_request_json)
    args = _fake_pre_demo_args(tmp_path)

    report = smoke._build_pre_demo_gate_report(args)

    assert report["passed"]
    names = [step.get("name") for step in report["steps"]]
    assert names == [
        "normal_smoke",
        "promotion_roundtrip",
        "restore_state",
        "readiness_check",
        "export_sanity",
    ]
    assert len(report["caveats"]) == 1
    assert report["caveats"][0].startswith("case-study readiness is not fully met")


def test_pre_demo_gate_fails_when_export_payload_is_incomplete(monkeypatch, tmp_path):
    _setup_fake_run(monkeypatch)

    def fake_request_json(self, method, path, payload=None, timeout=30):
        if path.endswith("/case-study-readiness"):
            return {
                "workflow_id": 101,
                "ready_for_case_study": True,
                "completed_count": 3,
                "total_count": 3,
                "gates": [],
                "next_required_items": [],
            }
        if path.endswith("/export-bundle"):
            return {
                "schema_version": "workflow-export-bundle/v1",
                "workflow_id": 101,
            }
        pytest.fail(f"unexpected path: {path}")

    monkeypatch.setattr(smoke.SmokeHarness, "request_json", fake_request_json)
    args = _fake_pre_demo_args(tmp_path)

    report = smoke._build_pre_demo_gate_report(args)

    assert not report["passed"]
    export_step = next(step for step in report["steps"] if step["name"] == "export_sanity")
    assert not export_step["passed"]
    assert "export payload missing required fields" in report["caveats"]


def test_pre_demo_gate_records_readiness_and_export_check_failures_as_caveats(monkeypatch, tmp_path):
    _setup_fake_run(monkeypatch)

    def fake_request_json(self, method, path, payload=None, timeout=30):
        raise smoke.SmokeFailure(f"API unavailable for {path}")

    monkeypatch.setattr(smoke.SmokeHarness, "request_json", fake_request_json)
    args = _fake_pre_demo_args(tmp_path)

    report = smoke._build_pre_demo_gate_report(args)

    assert not report["passed"]
    readiness_step = next(step for step in report["steps"] if step["name"] == "readiness_check")
    export_step = next(step for step in report["steps"] if step["name"] == "export_sanity")
    assert not readiness_step["passed"]
    assert not export_step["passed"]
    assert any("readiness check failed" in caveat for caveat in report["caveats"])
    assert any("export sanity check failed" in caveat for caveat in report["caveats"])


def test_closed_loop_rehearsal_uses_explicit_external_holdout_masks(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    holdout_root = tmp_path / "holdout"
    project_root.mkdir()
    holdout_root.mkdir()
    for target_id, raw_name in {
        "6_1": "6_1-xri_raw.tif",
        "6_2": "6_2-xri-raw.tif",
    }.items():
        raw_dir = project_root / "data" / "raw" / target_id
        raw_dir.mkdir(parents=True)
        (raw_dir / raw_name).write_text("raw", encoding="utf-8")
        (holdout_root / f"{target_id}-mask.tif").write_text("mask", encoding="utf-8")

    manifest = {
        "volumes": [
            {
                "id": "6_1",
                "status": "missing_segmentation",
                "image": "data/raw/6_1/6_1-xri_raw.tif",
                "segmentation": None,
                "withheld_ground_truth": str(holdout_root / "6_1-mask.tif"),
            },
            {
                "id": "6_2",
                "status": "missing_segmentation",
                "image": "data/raw/6_2/6_2-xri-raw.tif",
                "segmentation": None,
                "withheld_ground_truth": str(holdout_root / "6_2-mask.tif"),
            },
        ]
    }
    (project_root / "project_manifest.json").write_text(
        smoke.json.dumps(manifest), encoding="utf-8"
    )

    calls = []

    def fake_rehearsal_target(
        *, output_dir, image_path, ground_truth_path, crop, **kwargs
    ):
        calls.append(
            {
                "output_dir": str(output_dir),
                "image_path": str(image_path),
                "ground_truth_path": str(ground_truth_path),
                "crop": crop,
            }
        )
        return {
            "passed": True,
            "artifact_mode": "real_pair_derived_predictions",
            "runtime_overrides": {
                "training_iterations": kwargs.get("training_iterations"),
                "inference_iterations": kwargs.get("inference_iterations"),
            },
            "runtime_checkpoints": {
                "checkpoint": "simulated-checkpoint.pth",
                "training_run_checkpoint": "sim-checkpoint.pth",
                "inference_run_checkpoint": "sim-inference-checkpoint.pth",
                "model_version_checkpoint": "sim-model-version.pth",
            },
            "source_data": {
                "image_path": str(image_path),
                "mask_path": str(ground_truth_path),
                "ground_truth_path": str(ground_truth_path),
            },
        }

    monkeypatch.setattr(
        smoke, "_run_closed_loop_rehearsal_target", fake_rehearsal_target
    )
    args = Namespace(
        project_root=str(project_root),
        holdout_root=str(holdout_root),
        report=str(tmp_path / "closed-loop.json"),
        closed_loop_crop="0:2,0:16,0:16",
        closed_loop_training_iterations=7,
        closed_loop_inference_iterations=5,
    )

    report = smoke._build_closed_loop_rehearsal_report(args)

    assert report["passed"]
    assert report["runtime_overrides"] == {
        "training_iterations": 7,
        "inference_iterations": 5,
    }
    assert [target["target_id"] for target in report["targets"]] == ["6_1", "6_2"]
    assert len(calls) == 2
    assert calls[0]["ground_truth_path"] == str(holdout_root / "6_1-mask.tif")
    assert calls[1]["ground_truth_path"] == str(holdout_root / "6_2-mask.tif")
    assert all("project/data/seg" not in call["ground_truth_path"] for call in calls)
    assert report["targets"][0]["runtime_overrides"]["training_iterations"] == 7
    assert report["targets"][0]["runtime_overrides"]["inference_iterations"] == 5


def test_withheld_ground_truth_must_live_outside_project(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    holdout_root = tmp_path / "holdout"
    project_root.mkdir()
    holdout_root.mkdir()
    raw_dir = project_root / "data" / "raw" / "6_1"
    raw_dir.mkdir(parents=True)
    (raw_dir / "6_1-xri_raw.tif").write_text("raw", encoding="utf-8")

    seg_path = project_root / "data" / "seg" / "6_1-mask.tif"
    seg_path.parent.mkdir(parents=True)
    seg_path.write_text("seg", encoding="utf-8")

    manifest = {
        "volumes": [
            {
                "id": "6_1",
                "status": "missing_segmentation",
                "image": "data/raw/6_1/6_1-xri_raw.tif",
                "segmentation": None,
                "withheld_ground_truth": str(seg_path),
            },
            {
                "id": "6_2",
                "status": "missing_segmentation",
                "image": "data/raw/6_1/6_1-xri_raw.tif",
                "segmentation": None,
                "withheld_ground_truth": str(holdout_root / "6_2-mask.tif"),
            },
        ]
    }
    (project_root / "project_manifest.json").write_text(
        smoke.json.dumps(manifest), encoding="utf-8"
    )
    (holdout_root / "6_2-mask.tif").write_text("mask", encoding="utf-8")

    def fake_rehearsal_target(*args, **kwargs):
        return {}

    monkeypatch.setattr(smoke, "_run_closed_loop_rehearsal_target", fake_rehearsal_target)

    report = smoke._build_closed_loop_rehearsal_report(
        Namespace(
            project_root=str(project_root),
            holdout_root=str(holdout_root),
            report=str(tmp_path / "closed-loop.json"),
            closed_loop_crop=None,
            closed_loop_training_iterations=2,
            closed_loop_inference_iterations=1,
        )
    )

    assert not report["passed"]
    assert report["targets"][0]["passed"] is False
    assert "must live outside the mounted project root" in report["targets"][0]["error"]
