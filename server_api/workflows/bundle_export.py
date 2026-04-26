from __future__ import annotations

import os
from datetime import datetime, timezone
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
