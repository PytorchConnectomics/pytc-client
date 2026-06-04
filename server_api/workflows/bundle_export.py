from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm.exc import DetachedInstanceError

from .db_models import WorkflowEvent, WorkflowSession
from .service import (
    decode_json,
    agent_plan_to_dict,
    artifact_to_dict,
    correction_set_to_dict,
    evaluation_result_to_dict,
    event_to_dict,
    model_run_to_dict,
    model_version_to_dict,
    region_hotspot_to_dict,
    volume_state_to_dict,
    workflow_to_dict,
)

BUNDLE_SCHEMA_VERSION = "workflow-export-bundle/v1"
DEFAULT_COPY_MAX_BYTES = 104_857_600
DEFAULT_RAW_COPY_MAX_BYTES = 0
IMAGE_FILE_EXTENSIONS = {".tif", ".tiff", ".h5", ".hdf5", ".nii", ".nii.gz", ".n5", ".zarr"}
PROJECT_MEMORY_SUMMARY_VERSION = "pytc-project-memory-summary/v1"
COPY_POLICY_DEFAULT = {"allow_copy": True, "reason": None, "policy_code": "default"}
COPY_POLICY_EXPLICIT_REASONS = {
    "withheld_reference",
    "ground_truth_reference_outside_dataset",
    "external_reference_path",
    "metadata_restriction",
    "size_limit",
    "missing",
    "not_a_file",
    "manifest_only",
    "reference_only_policy",
}


def _safe_len_relationship(workflow: WorkflowSession, attr_name: str) -> int:
    try:
        records = getattr(workflow, attr_name)
    except DetachedInstanceError:
        return 0
    return len(records or [])
REFERENCE_ONLY_PATH_KEYS = {
    "withheld_ground_truth",
    "withheld_ground_truth_path",
    "source_ground_truth",
    "source_ground_truth_path",
}


def _parse_metadata_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        parsed = decode_json(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _policy_code_for_reason(reason: Optional[str]) -> str:
    if reason == "withheld_reference":
        return "withheld_reference"
    if reason == "ground_truth_reference_outside_dataset":
        return "ground_truth_reference_outside_dataset"
    if reason == "external_reference_path":
        return "external_reference_path"
    if reason == "missing":
        return "missing_path"
    if reason == "not_a_file":
        return "not_a_file"
    if reason == "manifest_only":
        return "manifest_only"
    if reason == "reference_only_policy":
        return "reference_only_policy"
    if reason in {"larger_than_copy_limit", "raw_larger_than_copy_limit"}:
        return "size_limit"
    return "metadata_restriction" if reason else "default"


def _merge_copy_reasons(first: Optional[str], second: Optional[str]) -> Optional[str]:
    if not first:
        return second
    if not second:
        return first
    if first == second:
        return first
    preference = [
        "withheld_reference",
        "ground_truth_reference_outside_dataset",
        "external_reference_path",
        "reference_only_policy",
        "missing",
        "not_a_file",
        "larger_than_copy_limit",
        "raw_larger_than_copy_limit",
        "metadata_restriction",
        "manifest_only",
    ]
    for reason in preference:
        if reason in {first, second}:
            return reason
    return second


def _normalize_copy_policy_reason(
    policy: Dict[str, Any],
    key: str,
    path_text: str,
    dataset_root: str | None,
) -> Optional[str]:
    base = policy.get("reason")
    if base is None:
        return None

    if policy.get("allow_copy") is False:
        should_reference_only, reference_reason = _should_mark_reference_only(
            key, path_text, dataset_root
        )
        if should_reference_only:
            return _merge_copy_reasons(str(base), reference_reason)
    return str(base)

def _is_path_key(key: str) -> bool:
    lowered = key.lower()
    if not lowered:
        return False
    if lowered in REFERENCE_ONLY_PATH_KEYS:
        return True
    if lowered.endswith("_path") or lowered == "path" or lowered.endswith("path"):
        return True
    if lowered.endswith("_ground_truth") or lowered == "ground_truth":
        return True
    if "ground_truth" in lowered and "path" in lowered:
        return True
    return False

def _should_mark_reference_only(key: str, path_text: str, dataset_root: str | None) -> tuple[bool, Optional[str]]:
    lowered = key.lower()
    if lowered in REFERENCE_ONLY_PATH_KEYS or "withheld" in lowered:
        return True, "withheld_reference"
    if "ground_truth" in lowered:
        return not _path_within_root(path_text, dataset_root), "ground_truth_reference_outside_dataset"
    return False, None


def _copy_policy_from_metadata(
    metadata: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if not isinstance(metadata, dict):
        return None
    allow_copy = metadata.get("allow_copy_in_bundle")
    if allow_copy is None:
        return None
    if allow_copy is False:
        return {
            "allow_copy": False,
            "reason": metadata.get("copy_reason") or "metadata_restriction",
        }
    if allow_copy is True:
        return {
            "allow_copy": True,
            "reason": metadata.get("copy_reason"),
        }
    return None


def _build_copy_policy(
    key: str,
    path_text: str,
    dataset_root: str | None,
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    policy = _copy_policy_from_metadata(metadata)
    if policy is not None:
        reason = _normalize_copy_policy_reason(
            policy,
            key=key,
            path_text=path_text,
            dataset_root=dataset_root,
        )
        return {
            **COPY_POLICY_DEFAULT,
            **policy,
            "policy_code": _policy_code_for_reason(
                reason if isinstance(reason, str) else None
            ),
        }
    should_reference_only, reason = _should_mark_reference_only(key, path_text, dataset_root)
    return {
        "allow_copy": not should_reference_only,
        "reason": reason,
        "policy_code": _policy_code_for_reason(reason),
    }


def _reference_scope(key: str, reason: Optional[str]) -> Dict[str, Any]:
    lowered = (key or "").lower()
    is_reference_only = (
        lowered in REFERENCE_ONLY_PATH_KEYS
        or "withheld" in lowered
        or reason == "withheld_reference"
        or reason == "ground_truth_reference_outside_dataset"
    )
    return {
        "is_reference_only": is_reference_only,
        "reference_reason": reason if is_reference_only else None,
        "reference_key": "withheld_reference" if is_reference_only else None,
    }


def _merge_copy_policies(
    current: Dict[str, Any],
    incoming: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(COPY_POLICY_DEFAULT)
    current = current or {}
    incoming = incoming or {}
    current_reason = current.get("reason") if isinstance(current.get("reason"), str) else None
    incoming_reason = incoming.get("reason") if isinstance(incoming.get("reason"), str) else None
    merged.update(current)
    merged_allow_copy = bool(current.get("allow_copy", True)) and bool(
        incoming.get("allow_copy", True)
    )
    merged_reason = _merge_copy_reasons(current_reason, incoming_reason)
    if not merged_allow_copy and not merged_reason:
        merged_reason = current_reason or incoming_reason or "metadata_restriction"
    merged.update(incoming)
    merged["allow_copy"] = merged_allow_copy
    merged["reason"] = merged_reason
    merged["policy_code"] = _policy_code_for_reason(
        merged_reason if isinstance(merged_reason, str) else None
    )
    return merged


def _coalesce_reference_scope(
    current: Optional[Dict[str, Any]],
    incoming: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    current_scope = current or {}
    incoming_scope = incoming or {}
    if not current_scope:
        return incoming_scope.copy() if incoming_scope else None
    if not incoming_scope:
        return current_scope.copy()
    return {
        "is_reference_only": bool(
            current_scope.get("is_reference_only")
            or incoming_scope.get("is_reference_only")
        ),
        "reference_reason": (
            incoming_scope.get("reference_reason")
            if incoming_scope.get("reference_reason")
            else current_scope.get("reference_reason")
        ),
        "reference_key": (
            incoming_scope.get("reference_key")
            if incoming_scope.get("reference_key")
            else current_scope.get("reference_key")
        ),
    }



def _build_skipped_artifact_record(
    *,
    path: str,
    reason: str,
    exists: bool,
    copy_policy: Optional[Dict[str, Any]] = None,
    copy_mode: Optional[str] = None,
    reference_scope: Optional[Dict[str, Any]] = None,
    size_bytes: Optional[int] = None,
    copy_limit_bytes: Optional[int] = None,
    raw_copy_max_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    policy = _merge_copy_policies({}, copy_policy or {})
    if reason:
        policy = _merge_copy_policies(
            policy,
            {
                "allow_copy": False,
                "reason": reason,
            },
        )
    record = {
        "path": path,
        "reason": reason,
        "exists": bool(exists),
        "copy_policy": policy,
        "copy_mode": copy_mode or reason,
    }
    if reference_scope is not None:
        record["reference_scope"] = reference_scope
    if size_bytes is not None:
        record["size_bytes"] = int(size_bytes)
    if copy_limit_bytes is not None:
        record["copy_limit_bytes"] = int(copy_limit_bytes)
    if raw_copy_max_bytes is not None:
        record["raw_copy_max_bytes"] = int(raw_copy_max_bytes)
    return record


def _path_within_root(path_text: str, root: str | None) -> bool:
    if not root:
        return True
    if not path_text:
        return True
    try:
        candidate = os.path.abspath(str(path_text))
        root_path = os.path.abspath(root)
        return os.path.commonpath([candidate, root_path]) == root_path
    except OSError:
        return True


def _parse_positive_int(value: Any, default: int, field_name: str) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{field_name} cannot be a boolean")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return parsed


def _looks_like_raw_image_path(path_text: str) -> bool:
    normalized = str(path_text).replace("\\", "/").lower()
    if "/raw/" in normalized or normalized.endswith("/raw"):
        return True
    if re.search(r"(^|[._-])raw([._-]|$)", normalized):
        return True
    return any(segment == "raw" for segment in normalized.strip("/").split("/") if segment)


def _is_image_like_path(path_text: str) -> bool:
    path = Path(path_text)
    return path.suffix.lower() in IMAGE_FILE_EXTENSIONS


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


def _collect_paths(
    value: Any,
    *,
    source_type: str,
    source_id: Optional[Any] = None,
    path_key: Optional[str] = None,
    parent_key: Optional[str] = None,
    dataset_root: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        for key, inner in value.items():
            item_metadata = value.get("metadata") if isinstance(value, dict) else None
            if not isinstance(key, str):
                yield from _collect_paths(
                    inner,
                    source_type=source_type,
                    source_id=source_id,
                    path_key=key,
                    parent_key=key,
                    dataset_root=dataset_root,
                    metadata=item_metadata,
                )
                continue

            if isinstance(inner, str) and _is_path_key(key):
                _, reference_reason = _should_mark_reference_only(key, inner, dataset_root)
                yield {
                    "path": inner,
                    "source_type": source_type,
                    "source_id": source_id,
                    "source_key": key,
                    "source_parent_key": parent_key,
                    "copy_policy": _build_copy_policy(key, inner, dataset_root, metadata),
                    "reference_scope": _reference_scope(key, reference_reason),
                }

            yield from _collect_paths(
                inner,
                source_type=source_type,
                source_id=source_id,
                path_key=key,
                parent_key=key,
                dataset_root=dataset_root,
                metadata=item_metadata,
            )
    elif isinstance(value, list):
        for item in value:
            yield from _collect_paths(
                item,
                source_type=source_type,
                source_id=source_id,
                path_key=path_key,
                parent_key=parent_key,
                dataset_root=dataset_root,
                metadata=metadata,
            )
    elif isinstance(value, str) and path_key and _is_path_key(path_key):
        _, reference_reason = _should_mark_reference_only(
            path_key, value, dataset_root
        )
        yield {
            "path": value,
            "source_type": source_type,
            "source_id": source_id,
            "source_key": path_key,
            "source_parent_key": parent_key,
            "copy_policy": _build_copy_policy(path_key, value, dataset_root, metadata),
            "reference_scope": _reference_scope(path_key, reference_reason),
        }


def _coalesce_path_reference(
    existing: Dict[str, Any], item: Dict[str, Any]
) -> Dict[str, Any]:
    merged = dict(existing)
    merged.setdefault("sources", [])
    source = {
        "source_type": item.get("source_type"),
        "source_id": item.get("source_id"),
        "source_key": item.get("source_key"),
        "source_parent_key": item.get("source_parent_key"),
    }
    if all(
        source != existing_source
        for existing_source in merged["sources"]
        if isinstance(existing_source, dict)
    ):
        merged["sources"].append(source)
    policy = item.get("copy_policy") or {}
    merged["copy_policy"] = _merge_copy_policies(
        merged.get("copy_policy") or {},
        policy,
    )
    merged["reference_scope"] = _coalesce_reference_scope(
        merged.get("reference_scope"),
        item.get("reference_scope"),
    )
    return merged


def _dedupe_path_refs(
    refs: Iterable[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    by_path: Dict[str, Dict[str, Any]] = {}
    for item in refs:
        path = item.get("path")
        if not path:
            continue
        path = str(path)
        if path in by_path:
            by_path[path] = _coalesce_path_reference(by_path[path], item)
            continue
        by_path[path] = {
            "path": path,
            "exists": os.path.exists(path),
            "sources": [
                {
                    "source_type": item.get("source_type"),
                    "source_id": item.get("source_id"),
                    "source_key": item.get("source_key"),
                    "source_parent_key": item.get("source_parent_key"),
                }
            ],
            "copy_policy": _merge_copy_policies({}, item.get("copy_policy") or {}),
            "reference_scope": item.get("reference_scope"),
        }
    return [
        {
            **entry,
            "copy_policy": entry.get("copy_policy") or {"allow_copy": True},
            "reference_scope": entry.get("reference_scope"),
            "sources": entry.get("sources") or [],
        }
        for entry in by_path.values()
    ]


def _build_project_memory_summary(workflow: WorkflowSession) -> Dict[str, Any]:
    metadata = _parse_metadata_json(workflow.metadata_json)
    return {
        "schema_version": PROJECT_MEMORY_SUMMARY_VERSION,
        "workflow_id": workflow.id,
        "workflow_stage": workflow.stage,
        "workflow_title": workflow.title,
        "dataset_path": workflow.dataset_path,
        "project_context": metadata.get("project_context") or {},
        "context_facts": metadata.get("context_facts") or [],
        "counts": {
            "artifact_count": _safe_len_relationship(workflow, "artifacts"),
            "model_run_count": _safe_len_relationship(workflow, "model_runs"),
            "model_version_count": _safe_len_relationship(workflow, "model_versions"),
            "correction_set_count": _safe_len_relationship(workflow, "correction_sets"),
            "evaluation_result_count": _safe_len_relationship(
                workflow,
                "evaluation_results",
            ),
            "region_hotspot_count": _safe_len_relationship(workflow, "region_hotspots"),
            "volume_state_count": _safe_len_relationship(workflow, "volume_states"),
            "agent_plan_count": _safe_len_relationship(workflow, "agent_plans"),
            "command_count": _safe_len_relationship(workflow, "commands"),
        },
    }


def build_export_bundle(
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
) -> Dict[str, Any]:
    session_snapshot = _normalize_value(workflow_to_dict(workflow))
    ordered_events = sorted(
        (_normalize_value(event_to_dict(event)) for event in events),
        key=_event_sort_key,
    )
    dataset_root = workflow.dataset_path

    discovered: List[Dict[str, Any]] = list(
        _collect_paths(
            session_snapshot,
            source_type="session_snapshot",
            dataset_root=dataset_root,
        )
    )
    for event in ordered_events:
        discovered.extend(
            _collect_paths(
                event,
                source_type="event",
                source_id=event.get("id"),
                parent_key=event.get("event_type"),
                dataset_root=dataset_root,
            )
        )
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
    volume_states = [
        _normalize_value(volume_state_to_dict(volume_state))
        for volume_state in getattr(workflow, "volume_states", [])
    ]
    agent_plans = [
        _normalize_value(agent_plan_to_dict(plan))
        for plan in getattr(workflow, "agent_plans", [])
    ]

    for artifact in typed_artifacts:
        discovered.extend(
            _collect_paths(
                artifact,
                source_type="artifact",
                source_id=artifact.get("id"),
                dataset_root=dataset_root,
            )
        )
    for run in model_runs:
        discovered.extend(
            _collect_paths(
                run,
                source_type="model_run",
                source_id=run.get("id"),
                dataset_root=dataset_root,
            )
        )
    for version in model_versions:
        discovered.extend(
            _collect_paths(
                version,
                source_type="model_version",
                source_id=version.get("id"),
                dataset_root=dataset_root,
            )
        )
    for correction_set in correction_sets:
        discovered.extend(
            _collect_paths(
                correction_set,
                source_type="correction_set",
                source_id=correction_set.get("id"),
                dataset_root=dataset_root,
            )
        )
    for result in evaluation_results:
        discovered.extend(
            _collect_paths(
                result,
                source_type="evaluation_result",
                source_id=result.get("id"),
                dataset_root=dataset_root,
            )
        )
    for volume_state in volume_states:
        discovered.extend(
            _collect_paths(
                volume_state,
                source_type="volume_state",
                source_id=volume_state.get("id"),
                dataset_root=dataset_root,
            )
        )
    for plan in agent_plans:
        discovered.extend(
            _collect_paths(
                plan,
                source_type="agent_plan",
                source_id=plan.get("id"),
                dataset_root=dataset_root,
            )
        )

    artifact_paths = sorted(
        _dedupe_path_refs(discovered), key=lambda item: item["path"]
    )

    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
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
        "volume_states": volume_states,
        "agent_plans": agent_plans,
        "artifact_paths": artifact_paths,
        "project_memory_summary": _build_project_memory_summary(workflow),
    }


def write_export_bundle_directory(
    bundle: Dict[str, Any],
    *,
    base_dir: str | None = None,
    copy_max_bytes: int | None = None,
    raw_copy_max_bytes: int | None = None,
    copy_manifest_only: bool = False,
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

    max_bytes = _parse_positive_int(
        copy_max_bytes,
        default=int(
            os.environ.get("PYTC_WORKFLOW_BUNDLE_COPY_MAX_BYTES", str(DEFAULT_COPY_MAX_BYTES))
        ),
        field_name="copy_max_bytes",
    )
    raw_image_max_bytes = _parse_positive_int(
        raw_copy_max_bytes,
        default=int(
            os.environ.get(
                "PYTC_WORKFLOW_BUNDLE_RAW_COPY_MAX_BYTES", str(DEFAULT_RAW_COPY_MAX_BYTES)
            )
        ),
        field_name="raw_copy_max_bytes",
    )
    copied_artifacts: List[Dict[str, Any]] = []
    skipped_artifacts: List[Dict[str, Any]] = []

    for artifact in bundle.get("artifact_paths") or []:
        path_text = artifact.get("path")
        if not path_text:
            continue
        copy_policy = artifact.get("copy_policy") or {}
        reference_scope = artifact.get("reference_scope")
        source = Path(path_text).expanduser()
        if not source.exists():
            skipped_artifacts.append(
                _build_skipped_artifact_record(
                    path=path_text,
                    reason="missing",
                    exists=False,
                    copy_policy=copy_policy,
                    copy_mode="missing",
                    reference_scope=reference_scope,
                )
            )
            continue
        if not source.is_file():
            skipped_artifacts.append(
                _build_skipped_artifact_record(
                    path=path_text,
                    reason="not_a_file",
                    exists=True,
                    copy_policy=copy_policy,
                    copy_mode="not_a_file",
                    reference_scope=reference_scope,
                )
            )
            continue
        if copy_manifest_only:
            skipped_artifacts.append(
                _build_skipped_artifact_record(
                    path=path_text,
                    reason="manifest_only",
                    exists=True,
                    copy_policy=copy_policy,
                    copy_mode="manifest_only",
                    reference_scope=reference_scope,
                )
            )
            continue
        if copy_policy.get("allow_copy") is False:
            skipped_artifacts.append(
                _build_skipped_artifact_record(
                    path=path_text,
                    reason="reference_only_policy",
                    exists=True,
                    copy_policy=copy_policy,
                    copy_mode="policy",
                    reference_scope=reference_scope,
                )
            )
            continue
        size_bytes = source.stat().st_size
        is_likely_raw_image = _is_image_like_path(str(source)) and _looks_like_raw_image_path(
            str(source)
        )
        effective_max_bytes = raw_image_max_bytes if is_likely_raw_image else max_bytes
        if size_bytes > effective_max_bytes:
            skip_reason = "raw_larger_than_copy_limit" if is_likely_raw_image else "larger_than_copy_limit"
            skipped_artifacts.append(
                _build_skipped_artifact_record(
                    path=path_text,
                    reason=skip_reason,
                    exists=True,
                    copy_policy=copy_policy,
                    copy_mode="size_limit",
                    reference_scope=reference_scope,
                    size_bytes=size_bytes,
                    copy_limit_bytes=effective_max_bytes,
                    raw_copy_max_bytes=raw_image_max_bytes if is_likely_raw_image else None,
                )
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
            "copy_settings": {
                "copy_max_bytes": max_bytes,
                "raw_copy_max_bytes": raw_image_max_bytes,
                "copy_manifest_only": copy_manifest_only,
            },
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
            "when they fit their configured limits.\n"
            "- Non-raw image paths use `copy_max_bytes`.\n"
            "- Raw-like image paths use `raw_copy_max_bytes`.\n"
            "- Entries marked `copy_policy.allow_copy=false` are referenced only.\n"
            "- Holdout/withheld ground-truth paths are imported as reference-only by default.\n"
            "- Set `copy_manifest_only=true` to skip all file copying.\n"
        )

    return bundle
