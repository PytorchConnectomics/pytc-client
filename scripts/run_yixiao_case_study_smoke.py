#!/usr/bin/env python3
"""Smoke-test the Yixiao/TapeReader XRI case-study contract.

This is a live API harness for the demo-facing workflow. It verifies the
case-study assumptions that matter for paper/demo work: project mounting,
manifest-backed file roles, progress counts, viewer creation, project memory,
and agent action proposals.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_BASE_URL = "http://127.0.0.1:4342"
DEFAULT_PROJECT_ROOT = Path("/home/weidf/demo_data/yixiao_tapereader_xri_case_study")
DEFAULT_HOLDOUT_ROOT = Path(
    "/home/weidf/demo_data/yixiao_tapereader_xri_case_study_holdout_masks"
)
DEFAULT_REPORT_PATH = Path("/tmp/yixiao-case-study-smoke-report.json")
DEFAULT_PRE_DEMO_GATE_REPORT_PATH = Path("/tmp/yixiao-case-study-pre-demo-gate-report.json")
DEFAULT_CLOSED_LOOP_REHEARSAL_REPORT_PATH = Path(
    "/tmp/yixiao-closed-loop-rehearsal-report.json"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_TITLE = "Yixiao TapeReader XRI Case Study"
PROJECT_SLUG = "yixiao_tapereader_xri_case_study"
SUGGESTION_ID = "yixiao-tapereader-xri-case-study"
IMAGE_ONLY_TARGET_IDS = ("6_1", "6_2")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class SmokeFailure(RuntimeError):
    pass


class SmokeHarness:
    def __init__(self, *, base_url: str, verbose: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.checks: List[Dict[str, Any]] = []

    def note(self, message: str) -> None:
        if self.verbose:
            print(message)

    def check(self, name: str, passed: bool, detail: Any = None) -> None:
        self.checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise SmokeFailure(f"{name} failed: {detail}")
        self.note(f"ok - {name}")

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        url = f"{self.base_url}{path}"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise SmokeFailure(f"{method} {path} returned {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise SmokeFailure(f"{method} {path} failed: {exc}") from exc
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SmokeFailure(f"{method} {path} returned non-JSON: {raw[:300]}") from exc


def _load_manifest(project_root: Path) -> Dict[str, Any]:
    manifest_path = project_root / "project_manifest.json"
    if not manifest_path.exists():
        raise SmokeFailure(f"Missing project manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _rel_to_abs(project_root: Path, rel_path: Optional[str]) -> Optional[str]:
    if not rel_path:
        return None
    path = Path(rel_path)
    if path.is_absolute():
        return str(path)
    return str(project_root / path)


def _manifest_volumes(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    volumes = manifest.get("volumes")
    return volumes if isinstance(volumes, list) else []


def _status_counts(volumes: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for volume in volumes:
        status = str(volume.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _progress_overrides(manifest: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    overrides: Dict[str, Dict[str, str]] = {}
    for volume in _manifest_volumes(manifest):
        image = volume.get("image")
        status = volume.get("status")
        if image and status:
            overrides[str(image)] = {
                "status": str(status),
                "note": str(status),
            }
    return overrides


def _first_volume_with_label(manifest: Dict[str, Any]) -> Dict[str, Any]:
    for volume in _manifest_volumes(manifest):
        if volume.get("image") and volume.get("segmentation"):
            return volume
    raise SmokeFailure("Manifest does not contain any image/segmentation pair.")


def _first_volume_with_status(manifest: Dict[str, Any], status: str) -> Dict[str, Any]:
    for volume in _manifest_volumes(manifest):
        if volume.get("image") and volume.get("status") == status:
            return volume
    raise SmokeFailure(f"Manifest does not contain a {status!r} volume.")


def _workflow_patch_payload(project_root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    first = _first_volume_with_label(manifest)
    active_paths = manifest.get("active_paths") or {}
    voxel = (manifest.get("voxel_size") or {}).get("zyx_nm") or [40, 16.3, 16.3]
    context = {
        "task_goal": manifest.get("task")
        or "CytoTape fibre instance segmentation and workflow coordination case study",
        "imaging_modality": manifest.get("imaging_modality")
        or "X-ray / XRI volumetric microscopy",
        "target_structure": manifest.get("target_structure") or "CytoTape fibres",
        "task_family": manifest.get("task_family")
        or "fibre instance segmentation",
        "optimization_priority": "case-study workflow fidelity",
        "mask_status": "6 confirmed ground-truth volumes, 2 draft masks for proofreading, 2 image-only inference targets",
        "image_only_strategy": "run inference on 6_1 and 6_2 after training/checkpoint selection",
        "training_policy": "train only on confirmed ground-truth masks",
        "voxel_size_nm": voxel,
        "voxel_size_source": "project_manifest.json",
    }
    metadata = {
        "created_from": "yixiao_case_study_smoke",
        "project_name": PROJECT_TITLE,
        "project_context": context,
        "project_progress_overrides": _progress_overrides(manifest),
        "visualization_scales": voxel,
        "visualization_scales_source": "project_manifest.json",
    }
    return {
        "title": PROJECT_TITLE,
        "stage": "visualization",
        "dataset_path": str(project_root),
        "image_path": _rel_to_abs(project_root, first.get("image")),
        "label_path": _rel_to_abs(project_root, first.get("segmentation")),
        "mask_path": _rel_to_abs(project_root, first.get("segmentation")),
        "config_path": _rel_to_abs(project_root, active_paths.get("config")),
        "training_output_path": _rel_to_abs(project_root, "outputs/training"),
        "metadata": metadata,
    }


def _find_yixiao_suggestion(suggestions: Any) -> Optional[Dict[str, Any]]:
    items = suggestions if isinstance(suggestions, list) else suggestions.get("suggestions", [])
    for item in items:
        if item.get("id") == SUGGESTION_ID:
            return item
        text = " ".join(
            str(item.get(key) or "")
            for key in ("name", "title", "label", "directory_path")
        ).lower()
        if "yixiao" in text or "tapereader" in text or "xri" in text:
            return item
    return None


def _assert_progress_counts(
    harness: SmokeHarness,
    progress: Dict[str, Any],
    expected: Dict[str, int],
    *,
    expected_completion_pct: float = 60.0,
    expected_segmentation_coverage_pct: float = 80.0,
) -> None:
    summary = progress.get("summary") or {}
    for key, value in expected.items():
        harness.check(f"progress {key}", summary.get(key) == value, summary)
    harness.check(
        "progress completion pct",
        float(summary.get("completion_pct") or 0) == expected_completion_pct,
        summary,
    )
    harness.check(
        "progress segmentation coverage pct",
        float(summary.get("segmentation_coverage_pct") or 0)
        == expected_segmentation_coverage_pct,
        summary,
    )


def _assert_profile(harness: SmokeHarness, suggestion: Dict[str, Any]) -> None:
    profile = suggestion.get("profile") or {}
    schema = profile.get("schema") if isinstance(profile.get("schema"), dict) else {}
    primary = schema.get("primary_paths") or profile.get("primary_paths") or {}
    volume_sets = schema.get("volume_sets") or profile.get("volume_sets") or []
    audit = schema.get("audit") or profile.get("audit") or {}
    audit_summary = audit.get("summary") or {}
    harness.check("profile image root", primary.get("image_root") == "data/raw", primary)
    harness.check("profile label root", primary.get("label_root") == "data/seg", primary)
    harness.check(
        "profile config",
        primary.get("config") == "configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml",
        primary,
    )
    manifest_set = next(
        (item for item in volume_sets if item.get("id") == "manifest-active-set"),
        None,
    )
    harness.check("profile manifest volume set exists", manifest_set is not None, volume_sets)
    if manifest_set:
        harness.check("profile image count", manifest_set.get("image_count") == 10, manifest_set)
        harness.check("profile label count", manifest_set.get("label_count") == 8, manifest_set)
        harness.check("profile pair count", manifest_set.get("pair_count") == 8, manifest_set)
    harness.check("profile audit errors", audit_summary.get("errors") == 0, audit_summary)
    harness.check("profile audit warnings", audit_summary.get("warnings") == 0, audit_summary)
    harness.check(
        "profile audit pair checks",
        audit_summary.get("pair_checks") == 8,
        audit_summary,
    )
    harness.check(
        "profile audit shape matches",
        audit_summary.get("shape_match_count") == 8,
        audit_summary,
    )


def _assert_agent_project_response(harness: SmokeHarness, response: Dict[str, Any]) -> None:
    text = response.get("response") or ""
    harness.check("agent project intent", response.get("intent") == "project_context", response)
    for needle in ("Yixiao", "XRI", "CytoTape", "10 volume", "6 fully good"):
        harness.check(f"agent project mentions {needle}", needle in text, text)


def _assert_agent_training_response(
    harness: SmokeHarness,
    response: Dict[str, Any],
    *,
    expected_train_count: int = 6,
    expected_review_count: int = 2,
    expected_target_count: int = 2,
) -> None:
    harness.check("agent training intent", response.get("intent") == "start_training", response)
    actions = response.get("actions") or []
    action = next((item for item in actions if item.get("id") == "start-training"), None)
    harness.check("agent training action exists", action is not None, actions)
    if not action:
        return
    harness.check("agent training requires approval", action.get("requires_approval") is True, action)
    harness.check("agent training risk", action.get("risk_level") == "runs_job", action)
    effects = action.get("client_effects") or {}
    subset = effects.get("training_volume_subset") or {}
    harness.check(
        "training subset GT count",
        subset.get("train_volume_count") == expected_train_count,
        subset,
    )
    harness.check(
        "training subset review count",
        subset.get("review_volume_count") == expected_review_count,
        subset,
    )
    harness.check(
        "training subset target count",
        subset.get("target_volume_count") == expected_target_count,
        subset,
    )
    for key in ("set_training_image_path", "set_training_label_path", "set_training_output_path"):
        path = effects.get(key)
        harness.check(f"training effect {key}", bool(path) and Path(path).exists(), path)
    manifest_path = subset.get("manifest_path")
    harness.check(
        "training subset manifest exists",
        bool(manifest_path) and Path(manifest_path).exists(),
        manifest_path,
    )
    _assert_pytc_training_subset_resolves(
        harness,
        effects,
        expected_train_count=expected_train_count,
    )


def _assert_pytc_training_subset_resolves(
    harness: SmokeHarness,
    effects: Dict[str, Any],
    *,
    expected_train_count: int = 6,
) -> None:
    """Verify the worker-side config staging accepts the proposed subset.

    This deliberately stops before launching PyTC. It catches the common failure
    mode where the UI receives directory paths that the worker later treats as
    an unrecognizable single volume.
    """

    try:
        from server_pytc.services import model as pytc_model
    except Exception as exc:  # pragma: no cover - only depends on local env
        harness.check("PyTC worker resolver import", False, str(exc))
        return

    image_path = effects.get("set_training_image_path")
    label_path = effects.get("set_training_label_path")
    output_path = effects.get("set_training_output_path")
    config_path = effects.get("set_training_config_preset")
    images, labels, reason = pytc_model._resolve_runtime_training_inputs(
        image_path,
        label_path,
    )
    harness.check(
        "PyTC subset resolver reason",
        reason == "runtime_request_training_subset_manifest",
        reason,
    )
    harness.check(
        "PyTC subset resolver image count",
        len(images) == expected_train_count,
        images,
    )
    harness.check(
        "PyTC subset resolver label count",
        len(labels) == expected_train_count,
        labels,
    )
    config_text = Path(config_path).read_text(encoding="utf-8")
    staged_config, _changes = pytc_model._apply_runtime_path_overrides(
        config_text,
        {
            "inputImagePath": image_path,
            "inputLabelPath": label_path,
            "outputPath": output_path,
        },
        kind="training",
    )
    pytc_model._validate_runtime_launch_inputs(staged_config, kind="training")
    harness.check("PyTC staged training config validates", True, config_path)


def _normalize_smoke_args(args: argparse.Namespace) -> argparse.Namespace:
    """Normalize legacy boolean presets for one smoke invocation."""

    normalized = copy.copy(args)
    if normalized.prepare_live:
        normalized.reset_workspace = True
        normalized.mount_project = True
        normalized.reset_workflow = True
    return normalized


def _run_smoke_step(
    args: argparse.Namespace,
    *,
    step_name: str,
    report_path: Path,
) -> Dict[str, Any]:
    step_args = copy.copy(args)
    step_args = _normalize_smoke_args(step_args)
    step_args.report = str(report_path)
    start = time.time()

    entry: Dict[str, Any] = {
        "name": step_name,
        "report_path": str(report_path),
        "passed": False,
    }
    try:
        report = run(step_args)
    except Exception as exc:  # pragma: no cover - exercised in caller tests.
        entry.update(
            {
                "error": str(exc),
                "duration_seconds": time.time() - start,
            }
        )
        return entry

    entry.update(
        {
            "passed": True,
            "workflow_id": report.get("workflow_id"),
            "duration_seconds": time.time() - start,
            "report": report,
        }
    )
    return entry


def _run_readiness_check(
    harness: SmokeHarness,
    *,
    workflow_id: int,
    timeout: int = 20,
) -> Dict[str, Any]:
    start = time.time()
    try:
        payload = harness.request_json(
            "GET",
            f"/api/workflows/{workflow_id}/case-study-readiness",
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "name": "readiness_check",
            "passed": False,
            "duration_seconds": time.time() - start,
            "error": str(exc),
            "payload_missing_keys": [],
        }

    if not isinstance(payload, dict):
        return {
            "name": "readiness_check",
            "passed": False,
            "duration_seconds": time.time() - start,
            "error": "readiness response is not a JSON object",
            "payload_missing_keys": [],
        }

    required = {
        "workflow_id",
        "ready_for_case_study",
        "completed_count",
        "total_count",
        "gates",
        "next_required_items",
    }
    missing = sorted(required - set(payload.keys()))
    return {
        "name": "readiness_check",
        "passed": not missing,
        "duration_seconds": time.time() - start,
        "ready_for_case_study": bool(payload.get("ready_for_case_study")),
        "completed_count": int(payload.get("completed_count", 0)),
        "total_count": int(payload.get("total_count", 0)),
        "next_required_items": payload.get("next_required_items") or [],
        "payload_missing_keys": missing,
    }


def _run_export_bundle_check(
    harness: SmokeHarness,
    *,
    workflow_id: int,
    timeout: int = 30,
) -> Dict[str, Any]:
    start = time.time()
    try:
        payload = harness.request_json(
            "POST",
            f"/api/workflows/{workflow_id}/export-bundle",
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "name": "export_sanity",
            "passed": False,
            "duration_seconds": time.time() - start,
            "error": str(exc),
            "payload_missing_keys": [],
        }

    if not isinstance(payload, dict):
        return {
            "name": "export_sanity",
            "passed": False,
            "duration_seconds": time.time() - start,
            "error": "export response is not a JSON object",
            "payload_missing_keys": [],
        }

    required = {
        "schema_version",
        "workflow_id",
        "events",
        "artifacts",
        "model_runs",
        "model_versions",
        "correction_sets",
        "agent_plans",
        "bundle_directory",
        "bundle_manifest_path",
    }
    missing = sorted(required - set(payload.keys()))

    bundle_manifest = payload.get("bundle_manifest_path")
    bundle_directory = payload.get("bundle_directory")
    return {
        "name": "export_sanity",
        "passed": not missing,
        "duration_seconds": time.time() - start,
        "bundle_directory": bundle_directory,
        "bundle_manifest_path": bundle_manifest,
        "bundle_manifest_exists": bool(bundle_manifest and Path(bundle_manifest).exists()),
        "bundle_directory_exists": bool(bundle_directory and Path(bundle_directory).exists()),
        "artifact_counts": {
            "events": len(payload.get("events") or []),
            "artifacts": len(payload.get("artifacts") or []),
            "model_runs": len(payload.get("model_runs") or []),
            "model_versions": len(payload.get("model_versions") or []),
            "correction_sets": len(payload.get("correction_sets") or []),
            "evaluation_results": len(payload.get("evaluation_results") or []),
            "agent_plans": len(payload.get("agent_plans") or []),
            "persisted_hotspots": len(payload.get("persisted_hotspots") or []),
        },
        "payload_missing_keys": missing,
    }


def _volume_id(volume: Dict[str, Any]) -> str:
    return str(volume.get("id") or "").strip()


def _volume_by_id(manifest: Dict[str, Any], volume_id: str) -> Dict[str, Any]:
    for volume in _manifest_volumes(manifest):
        if _volume_id(volume) == volume_id:
            return volume
    raise SmokeFailure(f"Manifest does not contain volume id {volume_id!r}.")


def _path_under(path_value: Path, root_value: Path) -> bool:
    try:
        path_value.resolve().relative_to(root_value.resolve())
        return True
    except ValueError:
        return False


def _withheld_ground_truth_path(
    *,
    project_root: Path,
    holdout_root: Path,
    volume: Dict[str, Any],
) -> Path:
    volume_id = _volume_id(volume)
    configured = volume.get("withheld_ground_truth")
    if configured:
        ground_truth = Path(str(configured)).expanduser()
    else:
        ground_truth = holdout_root / f"{volume_id}-mask.tif"
    if not ground_truth.is_absolute():
        ground_truth = holdout_root / ground_truth
    ground_truth = ground_truth.resolve()
    if not ground_truth.exists():
        raise SmokeFailure(
            f"Missing withheld ground truth for {volume_id}: {ground_truth}"
        )
    if _path_under(ground_truth, project_root):
        raise SmokeFailure(
            f"Withheld ground truth for {volume_id} must live outside the mounted "
            f"project root; got {ground_truth}"
        )
    mounted_segmentation = volume.get("segmentation")
    if mounted_segmentation:
        mounted_path = Path(str(mounted_segmentation))
        if not mounted_path.is_absolute():
            mounted_path = project_root / mounted_path
        if mounted_path.resolve() == ground_truth:
            raise SmokeFailure(
                f"Withheld ground truth for {volume_id} resolves to the mounted "
                "segmentation path."
            )
    return ground_truth


def _run_closed_loop_rehearsal_target(
    *,
    output_dir: Path,
    image_path: Path,
    ground_truth_path: Path,
    crop: Optional[str],
    training_iterations: Optional[int] = None,
    inference_iterations: Optional[int] = None,
) -> Dict[str, Any]:
    from scripts.run_closed_loop_smoke import run_closed_loop_smoke

    return run_closed_loop_smoke(
        output_dir=output_dir,
        image_path=str(image_path),
        mask_path=str(ground_truth_path),
        ground_truth_path=str(ground_truth_path),
        require_explicit_ground_truth=True,
        training_iterations=training_iterations,
        inference_iterations=inference_iterations,
        crop=crop,
    )


def _build_closed_loop_rehearsal_report(args: argparse.Namespace) -> Dict[str, Any]:
    start = time.time()
    project_root = Path(args.project_root).expanduser().resolve()
    holdout_root = Path(args.holdout_root).expanduser().resolve()
    manifest = _load_manifest(project_root)
    report_path = Path(args.report).resolve()
    output_root = report_path.with_suffix("")
    output_root.mkdir(parents=True, exist_ok=True)
    target_reports: List[Dict[str, Any]] = []
    caveats = [
        "This is a local rehearsal: it validates closed-loop evidence/evaluation wiring "
        "with explicit withheld masks, but does not launch GPU training or inference.",
        "Derived baseline/candidate masks are generated from withheld truth unless real "
        "prediction paths are supplied in a future rehearsal.",
    ]

    for target_id in IMAGE_ONLY_TARGET_IDS:
        image_path = Path("")
        ground_truth_path = Path("")
        target_output_dir = output_root / target_id
        try:
            volume = _volume_by_id(manifest, target_id)
            if volume.get("status") != "missing_segmentation":
                raise SmokeFailure(
                    f"Closed-loop target {target_id} must remain image-only; "
                    f"manifest status is {volume.get('status')!r}."
                )
            if volume.get("segmentation"):
                raise SmokeFailure(
                    f"Closed-loop target {target_id} unexpectedly has a mounted segmentation."
                )
            image_path = Path(_rel_to_abs(project_root, volume.get("image")) or "")
            if not image_path.exists():
                raise SmokeFailure(f"Missing image for {target_id}: {image_path}")
            ground_truth_path = _withheld_ground_truth_path(
                project_root=project_root,
                holdout_root=holdout_root,
                volume=volume,
            )
            closed_loop = _run_closed_loop_rehearsal_target(
                output_dir=target_output_dir,
                image_path=image_path,
                ground_truth_path=ground_truth_path,
                crop=args.closed_loop_crop,
                training_iterations=args.closed_loop_training_iterations,
                inference_iterations=args.closed_loop_inference_iterations,
            )
        except Exception as exc:
            target_reports.append(
                {
                    "target_id": target_id,
                    "passed": False,
                    "error": str(exc),
                    "image_path": str(image_path),
                    "ground_truth_path": str(ground_truth_path),
                    "output_dir": str(target_output_dir),
                }
            )
            continue
        target_reports.append(
            {
                "target_id": target_id,
                "passed": bool(closed_loop.get("passed", True)),
                "image_path": str(image_path),
                "ground_truth_path": str(ground_truth_path),
                "output_dir": str(target_output_dir),
                "artifact_mode": closed_loop.get("artifact_mode"),
                "source_data": closed_loop.get("source_data"),
                "runtime_overrides": closed_loop.get("runtime_overrides"),
                "runtime_checkpoints": closed_loop.get("runtime_checkpoints"),
                "closed_loop_report": closed_loop,
            }
        )

    return {
        "passed": all(item.get("passed") for item in target_reports),
        "generated_at_unix": time.time(),
        "project_root": str(project_root),
        "holdout_root": str(holdout_root),
        "runtime_overrides": {
            "training_iterations": args.closed_loop_training_iterations,
            "inference_iterations": args.closed_loop_inference_iterations,
        },
        "target_ids": list(IMAGE_ONLY_TARGET_IDS),
        "crop": args.closed_loop_crop,
        "targets": target_reports,
        "caveats": caveats,
        "duration_seconds": time.time() - start,
    }


def _build_pre_demo_gate_report(args: argparse.Namespace) -> Dict[str, Any]:
    gate_start = time.time()
    project_root = Path(args.project_root).expanduser().resolve()
    report_dir = Path(args.report).resolve().parent
    report_dir.mkdir(parents=True, exist_ok=True)
    report_stem = Path(args.report).stem
    baseline_report_path = report_dir / f"{report_stem}.baseline-smoke.json"
    promotion_report_path = report_dir / f"{report_stem}.promotion-smoke.json"
    restore_report_path = report_dir / f"{report_stem}.restore-smoke.json"
    steps: List[Dict[str, Any]] = []

    baseline = _run_smoke_step(
        _normalize_smoke_args(
            argparse.Namespace(
                **{
                    **vars(args),
                    "prepare_live": True,
                    "exercise_promotion": False,
                    "workflow_id": None,
                    "reset_fixture": args.reset_fixture,
                }
            )
        ),
        step_name="normal_smoke",
        report_path=baseline_report_path,
    )
    steps.append(baseline)

    workflow_id = baseline.get("workflow_id")
    if workflow_id is None and baseline.get("report"):
        workflow_id = baseline.get("report", {}).get("workflow_id")

    if workflow_id is not None:
        promotion = _run_smoke_step(
            argparse.Namespace(
                **{
                    **vars(args),
                    "prepare_live": False,
                    "exercise_promotion": True,
                    "workflow_id": workflow_id,
                    "reset_workspace": False,
                    "mount_project": False,
                    "reset_workflow": False,
                    "reset_fixture": False,
                }
            ),
            step_name="promotion_roundtrip",
            report_path=promotion_report_path,
        )
        steps.append(promotion)

    restore = _run_smoke_step(
        _normalize_smoke_args(
            argparse.Namespace(
                **{
                    **vars(args),
                    "prepare_live": True,
                    "exercise_promotion": False,
                    "workflow_id": None,
                    "reset_fixture": False,
                }
            )
        ),
        step_name="restore_state",
        report_path=restore_report_path,
    )
    steps.append(restore)

    restore_workflow_id = restore.get("workflow_id")
    if restore_workflow_id is None and restore.get("report"):
        restore_workflow_id = restore.get("report", {}).get("workflow_id")

    if not args.skip_readiness_check and restore_workflow_id:
        harness = SmokeHarness(base_url=args.base_url, verbose=args.verbose)
        checks = _run_readiness_check(harness, workflow_id=restore_workflow_id)
        checks["name"] = "readiness_check"
        steps.append(checks)

    if not args.skip_export_check and restore_workflow_id:
        harness = SmokeHarness(base_url=args.base_url, verbose=args.verbose)
        checks = _run_export_bundle_check(harness, workflow_id=restore_workflow_id)
        checks["name"] = "export_sanity"
        steps.append(checks)

    passed = all(step.get("passed", False) for step in steps[:3])
    caveats: List[str] = []

    if not args.skip_readiness_check:
        if not restore_workflow_id:
            caveats.append("readiness check could not run because restore step did not return a workflow id")
            passed = False
        else:
            readiness_step = next(
                (s for s in steps if s.get("name") == "readiness_check"), None
            )
            if readiness_step is None:
                caveats.append("readiness check was requested but not executed")
                passed = False
            elif readiness_step.get("error"):
                passed = False
                caveats.append(f"readiness check failed: {readiness_step.get('error')}")
            elif readiness_step.get("payload_missing_keys"):
                passed = False
                caveats.append("readiness response missing required fields")
            elif not readiness_step.get("ready_for_case_study", False):
                caveats.append(
                    "case-study readiness is not fully met; next items: "
                    + ", ".join(readiness_step.get("next_required_items") or ["(none)"])
                )

    if not args.skip_export_check:
        if not restore_workflow_id:
            caveats.append("export sanity check could not run because restore step did not return a workflow id")
            passed = False
        else:
            export_step = next((s for s in steps if s.get("name") == "export_sanity"), None)
            if export_step is None:
                caveats.append("export sanity check was requested but not executed")
                passed = False
            elif export_step.get("error"):
                passed = False
                caveats.append(f"export sanity check failed: {export_step.get('error')}")
            elif export_step.get("payload_missing_keys"):
                passed = False
                caveats.append("export payload missing required fields")
            elif not export_step.get("bundle_manifest_exists", False):
                passed = False
                caveats.append("export bundle manifest does not exist on disk")

    return {
        "passed": passed,
        "generated_at_unix": time.time(),
        "base_url": args.base_url,
        "project_root": str(project_root),
        "report_directory": str(report_dir),
        "steps": steps,
        "caveats": caveats,
        "duration_seconds": time.time() - gate_start,
    }


def _exercise_proofreading_promotion(
    harness: SmokeHarness,
    *,
    workflow_id: int,
    manifest: Dict[str, Any],
    agent_timeout: int,
    skip_agent: bool,
) -> Dict[str, Any]:
    """Promote one draft mask and verify memory/proposal state follows it."""

    draft_volume = _first_volume_with_status(manifest, "needs_proofreading")
    volume_id = str(draft_volume.get("image") or "")
    promotion = harness.request_json(
        "POST",
        f"/api/workflows/{workflow_id}/project-progress/volume-status",
        payload={
            "volume_id": volume_id,
            "status": "ground_truth",
            "note": "Smoke-test promotion: draft mask accepted as proofread ground truth.",
        },
        timeout=90,
    )
    promoted_expected = {
        "total": 10,
        "tracked_total": 10,
        "ground_truth": 7,
        "needs_proofreading": 1,
        "missing_segmentation": 2,
        "ignored": 0,
    }
    _assert_progress_counts(
        harness,
        promotion,
        promoted_expected,
        expected_completion_pct=70.0,
        expected_segmentation_coverage_pct=80.0,
    )

    memory = harness.request_json(
        "GET",
        f"/api/workflows/{workflow_id}/memory",
        timeout=30,
    )
    items = (memory.get("volume_states") or {}).get("items") or []
    promoted = next((item for item in items if item.get("volume_id") == volume_id), None)
    harness.check("promoted volume appears in memory", promoted is not None, items)
    if promoted:
        harness.check("promoted volume legacy status", promoted.get("status") == "ground_truth", promoted)
        harness.check(
            "promoted volume canonical status",
            promoted.get("canonical_status") == "proofread_ground_truth",
            promoted,
        )

    training_answer = None
    if not skip_agent:
        training_answer = harness.request_json(
            "POST",
            f"/api/workflows/{workflow_id}/agent/query",
            payload={"query": "train on the fully good masks to segment the image-only volumes"},
            timeout=agent_timeout,
        )
        _assert_agent_training_response(
            harness,
            training_answer,
            expected_train_count=7,
            expected_review_count=1,
            expected_target_count=2,
        )

    return {
        "promoted_volume_id": volume_id,
        "progress_summary": promotion.get("summary"),
        "memory_promoted_volume": promoted,
        "agent_training_response": (training_answer or {}).get("response"),
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    manifest = _load_manifest(project_root)
    volumes = _manifest_volumes(manifest)
    counts = _status_counts(volumes)
    harness = SmokeHarness(base_url=args.base_url, verbose=args.verbose)

    expected_counts = {
        "total": 10,
        "tracked_total": 10,
        "ground_truth": 6,
        "needs_proofreading": 2,
        "missing_segmentation": 2,
        "ignored": 0,
    }

    harness.check("project root exists", project_root.is_dir(), str(project_root))
    harness.check("manifest volume count", len(volumes) == 10, len(volumes))
    harness.check("manifest GT count", counts.get("ground_truth") == 6, counts)
    harness.check("manifest draft count", counts.get("needs_proofreading") == 2, counts)
    harness.check("manifest image-only count", counts.get("missing_segmentation") == 2, counts)

    if args.reset_fixture:
        reset_script = project_root / "reset_to_initial.sh"
        harness.check("reset script exists", reset_script.exists(), str(reset_script))
        subprocess.run([str(reset_script)], check=True)

    health = harness.request_json("GET", "/health", timeout=8)
    harness.check("backend health", health.get("status") == "ok", health)

    if args.reset_workspace:
        reset = harness.request_json("DELETE", "/files/workspace", timeout=30)
        harness.check("workspace reset", reset.get("message") == "Workspace reset", reset)

    if args.mount_project:
        mount = harness.request_json(
            "POST",
            "/files/mount",
            payload={
                "directory_path": str(project_root),
                "mount_name": PROJECT_TITLE,
            },
            timeout=90,
        )
        harness.check("project mounted", bool(mount.get("mounted_root_id")), mount)

    suggestions = harness.request_json("GET", "/files/project-suggestions", timeout=90)
    suggestion = _find_yixiao_suggestion(suggestions)
    harness.check("Yixiao suggestion exists", suggestion is not None, suggestions)
    assert suggestion is not None
    harness.check("Yixiao suggestion mounted", suggestion.get("already_mounted") is True, suggestion)
    _assert_profile(harness, suggestion)

    workflow_id = args.workflow_id
    if args.reset_workflow or workflow_id is None:
        created = harness.request_json(
            "POST",
            "/api/workflows/current/reset",
            payload={
                "title": PROJECT_TITLE,
                "metadata": {"created_from": "yixiao_case_study_smoke"},
            },
            timeout=30,
        )
        workflow_id = int((created.get("workflow") or {}).get("id"))
        harness.check("workflow reset created id", workflow_id > 0, created)

    patch_payload = _workflow_patch_payload(project_root, manifest)
    workflow = harness.request_json(
        "PATCH",
        f"/api/workflows/{workflow_id}",
        payload=patch_payload,
        timeout=30,
    )
    harness.check("workflow title", workflow.get("title") == PROJECT_TITLE, workflow)
    harness.check("workflow dataset", workflow.get("dataset_path") == str(project_root), workflow)
    harness.check("workflow stage", workflow.get("stage") == "visualization", workflow)

    progress = harness.request_json(
        "GET", f"/api/workflows/{workflow_id}/project-progress", timeout=90
    )
    _assert_progress_counts(harness, progress, expected_counts)

    memory = harness.request_json("GET", f"/api/workflows/{workflow_id}/memory", timeout=30)
    facts = memory.get("project_facts") or {}
    context = facts.get("project_context") or {}
    summary = (memory.get("volume_states") or {}).get("summary") or {}
    harness.check("memory schema", memory.get("schema_version") == "pytc-project-memory/v1", memory)
    harness.check("memory task preset", (facts.get("task_family_preset") or {}).get("id") == "tapereader_xri_fiber", facts)
    harness.check("memory modality", "XRI" in str(context.get("imaging_modality")), context)
    harness.check("memory tracked volumes", summary.get("tracked_total") == 10, summary)

    first = _first_volume_with_label(manifest)
    viewer = harness.request_json(
        "POST",
        "/neuroglancer",
        payload={
            "image": _rel_to_abs(project_root, first.get("image")),
            "label": _rel_to_abs(project_root, first.get("segmentation")),
            "scales": (manifest.get("voxel_size") or {}).get("zyx_nm") or [40, 16.3, 16.3],
            "workflow_id": workflow_id,
        },
        timeout=120,
    )
    harness.check("viewer url", "/neuroglancer/v/" in str(viewer.get("url")), viewer)
    pair_discovery = viewer.get("pair_discovery") or {}
    harness.check("viewer pair count", pair_discovery.get("pair_count") == 1, pair_discovery)
    harness.check("viewer unpaired images", pair_discovery.get("unpaired_images") == [], pair_discovery)
    harness.check("viewer unpaired labels", pair_discovery.get("unpaired_labels") == [], pair_discovery)

    if not args.skip_agent:
        project_answer = harness.request_json(
            "POST",
            f"/api/workflows/{workflow_id}/agent/query",
            payload={"query": "what project are we looking at?"},
            timeout=args.agent_timeout,
        )
        _assert_agent_project_response(harness, project_answer)

        training_answer = harness.request_json(
            "POST",
            f"/api/workflows/{workflow_id}/agent/query",
            payload={"query": "train on the fully good masks to segment the image-only volumes"},
            timeout=args.agent_timeout,
        )
        _assert_agent_training_response(harness, training_answer)
    else:
        project_answer = None
        training_answer = None

    promotion_result = None
    if args.exercise_promotion:
        promotion_result = _exercise_proofreading_promotion(
            harness,
            workflow_id=workflow_id,
            manifest=manifest,
            agent_timeout=args.agent_timeout,
            skip_agent=args.skip_agent,
        )

    report = {
        "passed": True,
        "generated_at_unix": time.time(),
        "base_url": args.base_url,
        "project_root": str(project_root),
        "workflow_id": workflow_id,
        "viewer_url": viewer.get("url"),
        "progress_summary": progress.get("summary"),
        "memory_summary": summary,
        "promotion_result": promotion_result,
        "agent_project_response": (project_answer or {}).get("response"),
        "agent_training_response": (training_answer or {}).get("response"),
        "checks": harness.checks,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--project-root", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--holdout-root", default=str(DEFAULT_HOLDOUT_ROOT))
    parser.add_argument("--workflow-id", type=int, default=None)
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--agent-timeout", type=int, default=45)
    parser.add_argument(
        "--closed-loop-rehearsal",
        action="store_true",
        help=(
            "Run local closed-loop evidence/evaluation rehearsal on image-only "
            "targets using explicit withheld masks. Does not mutate the live app."
        ),
    )
    parser.add_argument(
        "--closed-loop-crop",
        default="0:8,0:128,0:128",
        help=(
            "Crop used for closed-loop rehearsal, e.g. '0:8,0:128,0:128'. "
            "Use an empty string to load full volumes."
        ),
    )
    parser.add_argument(
        "--closed-loop-training-iterations",
        type=int,
        default=2,
        help=(
            "Training iterations to use for dry-run closed-loop rehearsal evidence "
            "steps. Defaults to a small value suitable for operator checks."
        ),
    )
    parser.add_argument(
        "--closed-loop-inference-iterations",
        type=int,
        default=1,
        help=(
            "Inference iterations to use for dry-run closed-loop rehearsal evidence "
            "steps. Defaults to a small value suitable for operator checks."
        ),
    )
    parser.add_argument(
        "--pre-demo-gate",
        action="store_true",
        help="Run normal smoke + promotion roundtrip + restore, with optional readiness/export checks.",
    )
    parser.add_argument(
        "--skip-readiness-check",
        action="store_true",
        help="Skip lightweight readiness endpoint check in pre-demo gate mode.",
    )
    parser.add_argument(
        "--skip-export-check",
        action="store_true",
        help="Skip lightweight export bundle check in pre-demo gate mode.",
    )
    parser.add_argument("--reset-fixture", action="store_true")
    parser.add_argument("--reset-workspace", action="store_true")
    parser.add_argument("--mount-project", action="store_true")
    parser.add_argument("--reset-workflow", action="store_true")
    parser.add_argument(
        "--exercise-promotion",
        action="store_true",
        help="Promote one draft mask to ground truth and verify progress/memory/training update.",
    )
    parser.add_argument(
        "--prepare-live",
        action="store_true",
        help="Reset indexed workspace, mount the Yixiao project, and create a fresh workflow.",
    )
    parser.add_argument("--skip-agent", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.pre_demo_gate and args.report == str(DEFAULT_REPORT_PATH):
        args.report = str(DEFAULT_PRE_DEMO_GATE_REPORT_PATH)
    if args.closed_loop_rehearsal and args.report == str(DEFAULT_REPORT_PATH):
        args.report = str(DEFAULT_CLOSED_LOOP_REHEARSAL_REPORT_PATH)
    if args.closed_loop_crop == "":
        args.closed_loop_crop = None

    args = _normalize_smoke_args(args)

    try:
        if args.closed_loop_rehearsal:
            report = _build_closed_loop_rehearsal_report(args)
        elif args.pre_demo_gate:
            report = _build_pre_demo_gate_report(args)
        else:
        # pragma: no cover - main path used by CLI integration tests.
            report = run(args)
    except Exception as exc:
        report = {
            "passed": False,
            "error": str(exc),
            "base_url": args.base_url,
            "project_root": args.project_root,
        }
        Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Yixiao case-study smoke failed: {exc}", file=sys.stderr)
        print(f"Report: {args.report}", file=sys.stderr)
        return 1

    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.closed_loop_rehearsal:
        status = "passed" if report.get("passed") else "failed"
        print(f"Yixiao closed-loop rehearsal {status}.")
        print(f"Targets: {', '.join(report.get('target_ids') or [])}")
        for target in report.get("targets") or []:
            print(
                f" - {target.get('target_id')}: "
                f"{'pass' if target.get('passed') else 'fail'}"
            )
    elif args.pre_demo_gate:
        status = "passed" if report.get("passed") else "failed"
        print(f"Yixiao pre-demo gate {status}.")
        print(f"Steps: {len(report.get('steps') or [])}")
        for step in report.get("steps") or []:
            print(f" - {step.get('name')}: {'pass' if step.get('passed') else 'fail'}")
    else:
        print("Yixiao case-study smoke passed.")
        print(f"Workflow: {report['workflow_id']}")
        print(f"Viewer: {report['viewer_url']}")
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
