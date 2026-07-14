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
from urllib.parse import urlsplit


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
DEFAULT_POST_DEPLOY_REPORT_ROOT = Path("docs/case-studies")
REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_TITLE = "Yixiao TapeReader XRI Case Study"
PROJECT_SLUG = "yixiao_tapereader_xri_case_study"
SUGGESTION_ID = "yixiao-tapereader-xri-case-study"
IMAGE_ONLY_TARGET_IDS = ("6_1", "6_2")
POST_DEPLOY_WORKFLOW_ID = 199
POST_DEPLOY_PROJECT_ROOT = "/home/weidf/demo_data/yixiao_tapereader_xri_case_study"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class SmokeFailure(RuntimeError):
    pass


class SmokeHarness:
    def __init__(self, *, base_url: str, verbose: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.checks: List[Dict[str, Any]] = []
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; pytc-yixiao-smoke)",
        }

    def note(self, message: str) -> None:
        if self.verbose:
            print(message)

    def check(self, name: str, passed: bool, detail: Any = None) -> None:
        self.checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise SmokeFailure(f"{name} failed: {detail}")
        self.note(f"ok - {name}")

    def request_json_with_status(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        expect_json: bool = True,
    ) -> Any:
        data = None
        headers = dict(self.headers)
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        url = f"{self.base_url}{path}"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.status
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            raise SmokeFailure(f"{method} {path} failed: {exc}") from exc
        if not raw:
            return status, {}
        if not expect_json:
            return status, raw
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError as exc:
            if status >= 400:
                raise SmokeFailure(f"{method} {path} returned {status}: {raw[:300]}") from exc
            raise SmokeFailure(f"{method} {path} returned non-JSON: {raw[:300]}") from exc

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Any:
        status, parsed = self.request_json_with_status(
            method,
            path,
            payload=payload,
            timeout=timeout,
            expect_json=True,
        )
        if status >= 400:
            raise SmokeFailure(f"{method} {path} returned {status}: {parsed}")
        return parsed


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


def _default_post_deploy_report_paths() -> Dict[str, Path]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    markdown_path = (
        DEFAULT_POST_DEPLOY_REPORT_ROOT
        / f"yixiao-postdeploy-smoke-report-{stamp}.md"
    )
    return {
        "markdown_path": markdown_path,
        "json_path": markdown_path.with_suffix(".json"),
    }


def _normalize_post_deploy_api_base(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/api"):
        return base
    return f"{base}/api"


def _probe_endpoint(
    harness: SmokeHarness,
    *,
    name: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
    expect_json: bool = True,
) -> Dict[str, Any]:
    start = time.time()
    try:
        status, payload_data = harness.request_json_with_status(
            method,
            path,
            payload=payload,
            timeout=timeout,
            expect_json=expect_json,
        )
        return {
            "name": name,
            "method": method,
            "path": path,
            "passed": status == 200,
            "status_code": status,
            "duration_seconds": time.time() - start,
            "payload": payload_data if expect_json else None,
            "raw_body": payload_data if not expect_json else None,
        }
    except Exception as exc:  # pragma: no cover - exercised in integration path
        return {
            "name": name,
            "method": method,
            "path": path,
            "passed": False,
            "status_code": None,
            "duration_seconds": time.time() - start,
            "error": str(exc),
            "payload": None,
            "raw_body": None,
        }


def _query_agent_action(
    harness: SmokeHarness,
    *,
    workflow_id: int,
    query: str,
    timeout: int = 45,
) -> Dict[str, Any]:
    step = _probe_endpoint(
        harness,
        name=f"agent_query:{query}",
        method="POST",
        path=f"/api/workflows/{workflow_id}/agent/query",
        payload={"query": query},
        timeout=timeout,
    )
    if not step["passed"]:
        return step
    payload = step.get("payload") or {}
    actions = payload.get("actions") or []
    return {
        "name": step["name"],
        "passed": bool(actions),
        "method": "POST",
        "path": f"/api/workflows/{workflow_id}/agent/query",
        "status_code": step["status_code"],
        "duration_seconds": step["duration_seconds"],
        "query": query,
        "intent": payload.get("intent"),
        "response": payload.get("response"),
        "actions": [
            {
                "id": action.get("id"),
                "requires_approval": action.get("requires_approval"),
                "label": action.get("label"),
            }
            for action in actions
            if isinstance(action, dict)
        ],
        "action_count": len(actions),
    }


def _expected_progress_summary() -> Dict[str, Any]:
    return {
        "total": 10,
        "tracked_total": 10,
        "ground_truth": 6,
        "needs_proofreading": 2,
        "missing_segmentation": 2,
        "ignored": 0,
        "completion_pct": 60.0,
        "segmentation_coverage_pct": 80.0,
    }


def _compare_progress(
    observed: Optional[Dict[str, Any]],
    *,
    expected: Dict[str, Any],
) -> List[str]:
    issues: List[str] = []
    if not isinstance(observed, dict):
        return ["progress summary missing"]
    for key, value in expected.items():
        if observed.get(key) != value:
            issues.append(f"summary[{key}] expected {value!r}, got {observed.get(key)!r}")
    return issues


def _build_post_deploy_report(args: argparse.Namespace) -> Dict[str, Any]:
    start = time.time()
    api_base = _normalize_post_deploy_api_base(args.base_url)
    public_root = args.base_url.rstrip("/")
    harness = SmokeHarness(base_url=api_base, verbose=args.verbose)
    checks: List[Dict[str, Any]] = []
    caveats: List[str] = []
    report: Dict[str, Any] = {
        "generated_at_unix": time.time(),
        "base_url": api_base,
        "public_root_url": public_root,
        "report_type": "post_deploy_readonly",
        "checks": checks,
        "caveats": caveats,
        "agent_queries": [],
        "public_endpoints": [],
        "duration_seconds": 0.0,
    }

    endpoint_checks: List[Dict[str, Any]] = []
    report["public_endpoints"] = endpoint_checks

    current = _probe_endpoint(harness, name="workflow_current", method="GET", path="/api/workflows/current")
    endpoint_checks.append(current)
    workflow_payload = current.get("payload") or {}
    current_workflow = workflow_payload.get("workflow") if isinstance(workflow_payload, dict) else None
    if not isinstance(current_workflow, dict):
        checks.append(
            {
                "name": "workflow_current_payload_shape",
                "passed": False,
                "error": "GET /api/workflows/current did not return workflow object",
            }
        )
        return {
            **report,
            "passed": False,
            "checks": checks,
            "duration_seconds": time.time() - start,
        }

    workflow_id = current_workflow.get("id")
    if args.workflow_id is not None:
        workflow_id = args.workflow_id
    if workflow_id is None:
        checks.append({"name": "workflow_id_resolved", "passed": False, "error": "workflow_id unavailable"})
        report["passed"] = False
        return {**report, "checks": checks, "duration_seconds": time.time() - start}
    workflow_id = int(workflow_id)

    if workflow_id != POST_DEPLOY_WORKFLOW_ID:
        caveats.append(
            f"Expected workflow id {POST_DEPLOY_WORKFLOW_ID} for the post-deploy fixture, "
            f"but active workflow is {workflow_id}"
        )

    checks.append({"name": "workflow_id", "passed": True, "workflow_id": workflow_id})
    report["workflow_id"] = workflow_id
    report["workflow_title"] = current_workflow.get("title")
    report["project_root_detected"] = current_workflow.get("dataset_path")
    report["expected_project_root"] = POST_DEPLOY_PROJECT_ROOT

    if report["project_root_detected"] != POST_DEPLOY_PROJECT_ROOT:
        caveats.append(
            "Detected workflow dataset_path differs from expected mounted Yixiao fixture path."
        )

    project_progress = _probe_endpoint(
        harness,
        name="project_progress",
        method="GET",
        path=f"/api/workflows/{workflow_id}/project-progress",
    )
    endpoint_checks.append(project_progress)
    summary = None
    if project_progress["passed"]:
        summary = project_progress.get("payload", {}).get("summary")
        issue_lines = _compare_progress(summary, expected=_expected_progress_summary())
        if issue_lines:
            checks.append({"name": "progress_counts", "passed": False, "issues": issue_lines})
            caveats.append("Progress counts are not the expected 6/2/2 split.")
        else:
            checks.append({"name": "progress_counts", "passed": True, "summary": summary})
    else:
        checks.append({"name": "progress_counts", "passed": False, "error": project_progress.get("error")})

    memory = _probe_endpoint(
        harness,
        name="workflow_memory",
        method="GET",
        path=f"/api/workflows/{workflow_id}/memory",
    )
    endpoint_checks.append(memory)
    if memory["passed"] and isinstance(memory.get("payload"), dict):
        checks.append(
            {
                "name": "memory_schema_version",
                "passed": memory["payload"].get("schema_version")
                == "pytc-project-memory/v1",
                "schema_version": memory["payload"].get("schema_version"),
            }
        )
    else:
        checks.append({"name": "memory_schema_version", "passed": False, "error": memory.get("error")})

    overview = _probe_endpoint(
        harness,
        name="workflow_overview",
        method="GET",
        path=f"/api/workflows/{workflow_id}/overview",
    )
    endpoint_checks.append(overview)

    readiness = _run_readiness_check(harness, workflow_id=workflow_id)
    checks.append(readiness)
    report["readiness"] = readiness
    if readiness.get("passed"):
        checks.append(
            {
                "name": "case_study_readiness_gate",
                "passed": bool(readiness.get("ready_for_case_study")),
                "ready_for_case_study": readiness.get("ready_for_case_study"),
                "next_required_items": readiness.get("next_required_items"),
            }
        )
        if not readiness.get("ready_for_case_study"):
            caveats.append("Case-study readiness gate is not yet met.")

    export_sanity = _run_export_bundle_check(harness, workflow_id=workflow_id)
    checks.append(export_sanity)
    report["export_bundle"] = export_sanity

    suggestions = _probe_endpoint(
        harness,
        name="project_suggestions",
        method="GET",
        path="/files/project-suggestions",
    )
    endpoint_checks.append(suggestions)
    suggestion_error: Optional[str] = None
    suggestion = None
    if suggestions["passed"] and isinstance(suggestions.get("payload"), list):
        suggestion = _find_yixiao_suggestion(suggestions["payload"])
        if suggestion:
            checks.append(
                {
                    "name": "yixiao_suggestion",
                    "passed": bool(suggestion),
                    "mounted": suggestion.get("already_mounted"),
                    "directory_path": suggestion.get("directory_path"),
                }
            )
            if suggestion.get("already_mounted") is not True:
                caveats.append("Yixiao suggestion exists but is not currently mounted.")
        else:
            suggestion_error = "Yixiao suggestion not found in files/project-suggestions"
    else:
        suggestion_error = suggestion_error or "Could not load project-suggestions"
    if suggestion_error:
        checks.append({"name": "yixiao_suggestion", "passed": False, "error": suggestion_error})

    visualization_payload = None
    if summary and summary.get("total") == 10:
        visualization_payload = {
            "workflow_id": workflow_id,
            "image": f"{POST_DEPLOY_PROJECT_ROOT}/data/raw/1/1-xri_raw.tif",
            "label": f"{POST_DEPLOY_PROJECT_ROOT}/data/seg/1/1-mask.tif",
            "scales": [40, 16.3, 16.3],
        }
    visualization_steps: List[Dict[str, Any]] = []
    create_viewer = _probe_endpoint(
        harness,
        name="neuroglancer_create",
        method="POST",
        path="/neuroglancer",
        payload=visualization_payload or {},
        timeout=30,
    )
    visualization_steps.append(create_viewer)
    public_viewer_url = ""
    if create_viewer.get("passed") and isinstance(create_viewer.get("payload"), dict):
        public_viewer_url = str(
            create_viewer["payload"].get("url")
            or create_viewer["payload"].get("neuroglancer_url")
            or ""
        ).strip()
    if public_viewer_url:
        public_path = urlsplit(public_viewer_url).path or "/neuroglancer/"
        public_viewer = _probe_endpoint(
            SmokeHarness(base_url=public_root, verbose=args.verbose),
            name="neuroglancer_public_viewer",
            method="GET",
            path=public_path,
            timeout=20,
            expect_json=False,
        )
        public_viewer["url"] = public_viewer_url
        visualization_steps.append(public_viewer)
    report["visualization"] = visualization_steps
    for candidate in visualization_steps:
        if candidate.get("name") == "neuroglancer_public_viewer" and candidate.get("status_code") == 200:
            break
    else:
        caveats.append(
            "Public visualization viewer did not return a successful response; "
            "check demo.seg.bio/neuroglancer runtime health and viewer retention."
        )

    agent_queries = [
        "what project are we looking at?",
        "train on the fully good masks to segment the image-only volumes",
        "what should I proofread next?",
        "Can we run inference on image-only targets next?",
    ]
    agent_checks: List[Dict[str, Any]] = []
    for query in agent_queries:
        agent_checks.append(
            _query_agent_action(harness, workflow_id=workflow_id, query=query, timeout=args.agent_timeout)
        )
    report["agent_queries"] = agent_checks
    training_query = next((row for row in agent_checks if row.get("query") == agent_queries[1]), {})
    if training_query.get("passed") and any(action.get("id") == "start-training" for action in training_query.get("actions", [])):
        checks.append({"name": "training_action_proposal", "passed": True, "action_ids": [a.get("id") for a in training_query.get("actions", [])]})
    else:
        checks.append({"name": "training_action_proposal", "passed": False, "error": "start-training action not returned for training prompt"})
        caveats.append("Training action proposal is not currently returning expected `start-training` behavior.")
    proofread_query = next((row for row in agent_checks if row.get("query") == agent_queries[2]), {})
    if proofread_query.get("passed") and any(
        action.get("id") == "start-proofreading" for action in proofread_query.get("actions", [])
    ):
        checks.append({"name": "proofread_action_proposal", "passed": True, "action_ids": [a.get("id") for a in proofread_query.get("actions", [])]})
    else:
        checks.append({"name": "proofread_action_proposal", "passed": False, "error": "start-proofreading action not returned"})
        caveats.append("Proofread action proposal is weak or not returning expected identifier.")
    inference_query = next((row for row in agent_checks if row.get("query") == agent_queries[3]), {})
    if inference_query.get("passed") and (
        any(action.get("id") == "open-inference" for action in inference_query.get("actions", []))
        or any(action.get("id") == "start-inference" for action in inference_query.get("actions", []))
    ):
        checks.append(
            {
                "name": "inference_action_proposal",
                "passed": True,
                "action_ids": [a.get("id") for a in inference_query.get("actions", [])],
            }
        )
    else:
        checks.append(
            {
                "name": "inference_action_proposal",
                "passed": False,
                "error": "Inference proposal action not returned",
            }
        )
        caveats.append("Inference proposal may need checkpoint/agent sequencing before action can be launched.")

    report["checks"] = checks
    report["caveats"] = caveats
    participant_start_ready = all(
        bool(check.get("passed"))
        for check in checks
        if check.get("name")
        not in {
            "case_study_readiness_gate",
        }
    ) and any(
        row.get("name") == "neuroglancer_public_viewer" and row.get("passed")
        for row in visualization_steps
    )
    report["participant_start_ready"] = participant_start_ready
    report["passed"] = participant_start_ready
    report["duration_seconds"] = time.time() - start
    return report


def _write_post_deploy_report_markdown(report: Dict[str, Any], path: Path) -> None:
    public_endpoints = report.get("public_endpoints") or []
    checks = report.get("checks") or []
    readiness = report.get("readiness") or {}
    viz = report.get("visualization") or []
    agent_queries = report.get("agent_queries") or []
    progress = None
    for check in checks:
        if check.get("name") == "progress_counts":
            progress = check.get("summary") or check.get("issues")
            break

    lines = [
        "# Yixiao Post-Deploy Smoke Report",
        "",
        f"- Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(report.get('generated_at_unix', 0)))}",
        f"- Report type: {report.get('report_type')}",
        f"- Public root: `{report.get('public_root_url')}`",
        f"- Workflow endpoint API base: `{report.get('base_url')}`",
        f"- Workflow id (active): `{report.get('workflow_id')}`",
        f"- Workflow title: `{report.get('workflow_title')}`",
        f"- Workflow dataset path: `{report.get('project_root_detected')}`",
        f"- Expected dataset path: `{report.get('expected_project_root')}`",
        "",
        f"- Participant starting fixture: {'READY' if report.get('participant_start_ready') else 'NOT READY'}",
        f"- Full case-study completion gate: {'PASS' if readiness.get('ready_for_case_study') else 'NOT YET'}",
    ]

    if readiness:
        lines.extend(
            [
                "",
                "## Case-Study Readiness",
                f"- Ready flag: `{readiness.get('ready_for_case_study')}`",
                f"- Completed count: `{readiness.get('completed_count')}`",
                f"- Total count: `{readiness.get('total_count')}`",
                f"- Next required items: {', '.join(readiness.get('next_required_items') or ['(none)'])}",
            ]
        )

    lines.extend(
        [
            "",
            "## Progress Summary",
            f"- {progress if progress is not None else 'Not available'}",
        ]
    )

    lines.extend(["", "## Public Endpoint Status", ""])
    for row in public_endpoints:
        status = row.get("status_code")
        lines.append(
            f"- `{row.get('name')}` `{row.get('method')}` `{row.get('path')}` -> {status} ({'PASS' if row.get('passed') else 'FAIL'})"
        )

    lines.extend(["", "## Visualization Probe", ""])
    for row in viz:
        target = row.get("url") or row.get("path")
        lines.append(
            f"- `{row.get('name')}` `{target}` -> {row.get('status_code')} ({'PASS' if row.get('passed') else 'FAIL'})"
        )
    lines.append("")
    lines.extend(["", "## Agent Proposal Probes", ""])
    for row in agent_queries:
        lines.append(
            f"- Q: `{row.get('query')}` -> `{row.get('intent')}` / "
            f"actions={row.get('action_count')} status={row.get('status_code')}"
        )
        if row.get("actions"):
            lines.append(
                "  - " + ", ".join(
                    [f"{action.get('id')} (approval={action.get('requires_approval')})" for action in row.get("actions") if isinstance(action, dict)]
                )
            )
        if row.get("error"):
            lines.append(f"  - error: `{row.get('error')}`")

    if report.get("caveats"):
        lines.extend(["", "## Known Risks", ""])
        for caveat in report["caveats"]:
            lines.append(f"- {caveat}")

    path.write_text("\n".join(lines), encoding="utf-8")


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
        "--post-deploy",
        action="store_true",
        help=(
            "Run a read-only public post-deploy validation sweep for workflow "
            "state, endpoint health, and dry-run proposal probes."
        ),
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
    if args.post_deploy and args.report == str(DEFAULT_REPORT_PATH):
        default_paths = _default_post_deploy_report_paths()
        args.report = str(default_paths["json_path"])
    if args.closed_loop_rehearsal and args.report == str(DEFAULT_REPORT_PATH):
        args.report = str(DEFAULT_CLOSED_LOOP_REHEARSAL_REPORT_PATH)
    if args.closed_loop_crop == "":
        args.closed_loop_crop = None

    args = _normalize_smoke_args(args)
    post_deploy_json_path: Path | None = None
    post_deploy_markdown_path: Path | None = None
    if args.post_deploy:
        post_deploy_json_path = Path(args.report)
        post_deploy_markdown_path = post_deploy_json_path.with_suffix(".md")

    try:
        if args.closed_loop_rehearsal:
            report = _build_closed_loop_rehearsal_report(args)
        elif args.post_deploy:
            report = _build_post_deploy_report(args)
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
    if args.post_deploy and post_deploy_markdown_path:
        _write_post_deploy_report_markdown(report, post_deploy_markdown_path)
    if args.closed_loop_rehearsal:
        status = "passed" if report.get("passed") else "failed"
        print(f"Yixiao closed-loop rehearsal {status}.")
        print(f"Targets: {', '.join(report.get('target_ids') or [])}")
        for target in report.get("targets") or []:
            print(
                f" - {target.get('target_id')}: "
                f"{'pass' if target.get('passed') else 'fail'}"
            )
    elif args.post_deploy:
        status = "passed" if report.get("passed") else "failed"
        print(f"Yixiao post-deploy smoke {status}.")
        print(f"Workflow: {report.get('workflow_id')}")
        readiness = report.get("readiness") or {}
        print(
            f"Readiness: {readiness.get('ready_for_case_study')}, "
            f"{len(readiness.get('next_required_items') or [])} pending item(s)"
        )
        print(f"Markdown report: {post_deploy_markdown_path}")
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
