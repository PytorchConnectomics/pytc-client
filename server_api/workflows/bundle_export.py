from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .db_models import WorkflowEvent, WorkflowSession
from .service import (
    agent_plan_to_dict,
    artifact_to_dict,
    correction_set_to_dict,
    evaluation_result_to_dict,
    event_to_dict,
    model_run_to_dict,
    model_version_to_dict,
    region_hotspot_to_dict,
    workflow_to_dict,
)


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "1970-01-01T00:00:00+00:00")
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _event_sort_key(event: Dict[str, Any]) -> Tuple[datetime, str]:
    timestamp = event.get("created_at")
    event_id = str(event.get("id") or "")
    return (_parse_timestamp(timestamp), event_id)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def _safe_filename(value: str, fallback: str = "artifact") -> str:
    name = os.path.basename(str(value).rstrip("/")) or fallback
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or fallback


def _collect_paths(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, inner in value.items():
            if isinstance(inner, str) and key.endswith("_path"):
                yield inner
            if key == "path" and isinstance(inner, str):
                yield inner
            yield from _collect_paths(inner)
    elif isinstance(value, list):
        for item in value:
            yield from _collect_paths(item)


def build_export_bundle(
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
) -> Dict[str, Any]:
    session_snapshot = _normalize_value(workflow_to_dict(workflow))
    ordered_events = sorted(
        (_normalize_value(event_to_dict(event)) for event in events),
        key=_event_sort_key,
    )

    discovered = set(_collect_paths(session_snapshot))
    for event in ordered_events:
        discovered.update(_collect_paths(event))
    typed_artifacts = [
        _normalize_value(artifact_to_dict(artifact))
        for artifact in getattr(workflow, "artifacts", [])
    ]
    model_runs = [
        _normalize_value(model_run_to_dict(run))
        for run in getattr(workflow, "model_runs", [])
    ]
    model_versions = [
        _normalize_value(model_version_to_dict(version))
        for version in getattr(workflow, "model_versions", [])
    ]
    correction_sets = [
        _normalize_value(correction_set_to_dict(correction_set))
        for correction_set in getattr(workflow, "correction_sets", [])
    ]
    evaluation_results = [
        _normalize_value(evaluation_result_to_dict(result))
        for result in getattr(workflow, "evaluation_results", [])
    ]
    persisted_hotspots = [
        _normalize_value(region_hotspot_to_dict(hotspot))
        for hotspot in getattr(workflow, "region_hotspots", [])
    ]
    agent_plans = [
        _normalize_value(agent_plan_to_dict(plan))
        for plan in getattr(workflow, "agent_plans", [])
    ]

    for artifact in typed_artifacts:
        discovered.update(_collect_paths(artifact))
    for run in model_runs:
        discovered.update(_collect_paths(run))
    for version in model_versions:
        discovered.update(_collect_paths(version))
    for correction_set in correction_sets:
        discovered.update(_collect_paths(correction_set))
    for result in evaluation_results:
        discovered.update(_collect_paths(result))
    for plan in agent_plans:
        discovered.update(_collect_paths(plan))

    artifact_paths = sorted(path for path in discovered if path)
    artifacts = [
        {"path": path, "exists": os.path.exists(path)} for path in artifact_paths
    ]

    return {
        "schema_version": "workflow-export-bundle/v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "workflow_id": workflow.id,
        "session_snapshot": session_snapshot,
        "events": ordered_events,
        "artifacts": typed_artifacts,
        "model_runs": model_runs,
        "model_versions": model_versions,
        "correction_sets": correction_sets,
        "evaluation_results": evaluation_results,
        "persisted_hotspots": persisted_hotspots,
        "agent_plans": agent_plans,
        "artifact_paths": artifacts,
    }


def write_export_bundle_directory(
    bundle: Dict[str, Any],
    *,
    base_dir: str | None = None,
    copy_max_bytes: int | None = None,
) -> Dict[str, Any]:
    """Persist a paper/debuggable workflow bundle without blindly copying huge data."""

    root = Path(
        base_dir
        or os.environ.get("PYTC_WORKFLOW_BUNDLE_DIR")
        or ".logs/workflow-bundles"
    )
    root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    workflow_id = bundle.get("workflow_id") or "unknown"
    export_dir = root / f"workflow-{workflow_id}-{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=False)
    files_dir = export_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = (
        copy_max_bytes
        if copy_max_bytes is not None
        else int(os.environ.get("PYTC_WORKFLOW_BUNDLE_COPY_MAX_BYTES", "104857600"))
    )
    copied_artifacts: List[Dict[str, Any]] = []
    skipped_artifacts: List[Dict[str, Any]] = []

    for artifact in bundle.get("artifact_paths") or []:
        path_text = artifact.get("path")
        if not path_text:
            continue
        source = Path(path_text).expanduser()
        if not source.exists():
            skipped_artifacts.append(
                {"path": path_text, "reason": "missing", "exists": False}
            )
            continue
        if not source.is_file():
            skipped_artifacts.append(
                {"path": path_text, "reason": "not_a_file", "exists": True}
            )
            continue
        size_bytes = source.stat().st_size
        if size_bytes > max_bytes:
            skipped_artifacts.append(
                {
                    "path": path_text,
                    "reason": "larger_than_copy_limit",
                    "exists": True,
                    "size_bytes": size_bytes,
                    "copy_limit_bytes": max_bytes,
                }
            )
            continue
        digest = hashlib.sha1(str(source.resolve()).encode("utf-8")).hexdigest()[:10]
        destination = files_dir / f"{digest}-{_safe_filename(source.name)}"
        shutil.copy2(source, destination)
        copied_artifacts.append(
            {
                "path": path_text,
                "bundle_path": str(destination),
                "relative_bundle_path": str(destination.relative_to(export_dir)),
                "size_bytes": size_bytes,
            }
        )

    bundle.update(
        {
            "bundle_directory": str(export_dir),
            "bundle_manifest_path": str(export_dir / "workflow-bundle.json"),
            "copied_artifacts": copied_artifacts,
            "skipped_artifacts": skipped_artifacts,
        }
    )

    with (export_dir / "workflow-bundle.json").open("w", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    with (export_dir / "artifact-paths.json").open("w", encoding="utf-8") as handle:
        json.dump(
            bundle.get("artifact_paths") or [],
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")
    with (export_dir / "README.md").open("w", encoding="utf-8") as handle:
        handle.write(
            "# PyTC Workflow Evidence Bundle\n\n"
            f"- Workflow ID: {workflow_id}\n"
            f"- Exported at: {bundle.get('exported_at')}\n"
            f"- Events: {len(bundle.get('events') or [])}\n"
            f"- Typed artifacts: {len(bundle.get('artifacts') or [])}\n"
            f"- Model runs: {len(bundle.get('model_runs') or [])}\n"
            f"- Model versions: {len(bundle.get('model_versions') or [])}\n"
            f"- Correction sets: {len(bundle.get('correction_sets') or [])}\n"
            f"- Evaluation results: {len(bundle.get('evaluation_results') or [])}\n"
            f"- Copied files: {len(copied_artifacts)}\n"
            f"- Skipped paths: {len(skipped_artifacts)}\n\n"
            "Large files are referenced in `artifact-paths.json` and copied only "
            "when they fit the configured bundle copy limit.\n"
        )

    return bundle
