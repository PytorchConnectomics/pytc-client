from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
from typing import Any, Dict

from dbos import DBOS

APP_NAME = "pytc-dbos-operation-spike"
APP_VERSION = "pytc-dbos-operation-spike-v1"
QUEUE_NAME = "synthetic-operations"
PROGRESS_EVENT = "operation_progress"


def workflow_storage_key(workflow_id: str) -> str:
    return hashlib.sha256(workflow_id.encode("utf-8")).hexdigest()[:20]


def marker_directory(workspace: str, workflow_id: str) -> pathlib.Path:
    return pathlib.Path(workspace) / "markers" / workflow_storage_key(workflow_id)


def _append_json_line(path: pathlib.Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


@DBOS.step(name="pytc.synthetic_operation_step.v1")
def execute_synthetic_step(
    workspace: str,
    workflow_id: str,
    step_index: int,
    step_runtime_seconds: float,
) -> Dict[str, Any]:
    """Perform an idempotent external effect representative of a compute chunk."""

    markers = marker_directory(workspace, workflow_id)
    markers.mkdir(parents=True, exist_ok=True)
    marker = markers / f"step-{step_index:04d}.json"
    attempt = {
        "workflow_id": workflow_id,
        "step_index": step_index,
        "pid": os.getpid(),
        "attempted_at": time.time(),
    }
    try:
        with marker.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(attempt, sort_keys=True))
            stream.flush()
            os.fsync(stream.fileno())
        effect = "created"
    except FileExistsError:
        effect = "already_exists"
        _append_json_line(markers / "duplicate-attempts.jsonl", attempt)

    if step_runtime_seconds > 0:
        time.sleep(step_runtime_seconds)
    return {
        "step_index": step_index,
        "effect": effect,
        "marker": str(marker),
    }


@DBOS.workflow(name="pytc.synthetic_operation.v1")
def synthetic_operation(
    workspace: str,
    workflow_id: str,
    correlation_id: str,
    total_steps: int,
    step_runtime_seconds: float,
    inter_step_delay_seconds: float,
) -> Dict[str, Any]:
    if total_steps < 1:
        raise ValueError("total_steps must be positive")

    progress: Dict[str, Any] = {
        "status": "running",
        "workflow_id": workflow_id,
        "correlation_id": correlation_id,
        "completed_steps": 0,
        "total_steps": total_steps,
        "progress": 0.0,
    }
    DBOS.set_event(PROGRESS_EVENT, progress)

    step_results = []
    for step_index in range(total_steps):
        step_results.append(
            execute_synthetic_step(
                workspace,
                workflow_id,
                step_index,
                step_runtime_seconds,
            )
        )
        completed_steps = step_index + 1
        progress = {
            **progress,
            "completed_steps": completed_steps,
            "progress": completed_steps / total_steps,
        }
        DBOS.set_event(PROGRESS_EVENT, progress)
        if completed_steps < total_steps and inter_step_delay_seconds > 0:
            DBOS.sleep(inter_step_delay_seconds)

    result = {
        "status": "succeeded",
        "workflow_id": workflow_id,
        "correlation_id": correlation_id,
        "completed_steps": total_steps,
        "total_steps": total_steps,
        "progress": 1.0,
        "step_results": step_results,
    }
    DBOS.set_event(PROGRESS_EVENT, result)
    return result
