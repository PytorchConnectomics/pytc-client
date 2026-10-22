"""HTTP endpoints for task scripts: draft, check, run, and follow jobs."""

from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import drafter, viewing
from .compiler import PRESETS, compile_script
from .language import MANAGED_KEYS, SCHEMA, TARGETS, check, output_parents
from .targets import STATE_DIR, TargetError, get_target

router = APIRouter()
_JOBS_FILE = STATE_DIR / "jobs.json"
_LOCK = threading.Lock()


def _load_jobs() -> list[dict[str, Any]]:
    try:
        return json.loads(_JOBS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_jobs(jobs: list[dict[str, Any]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _JOBS_FILE.write_text(json.dumps(jobs, indent=2))


def _update_job(job_id: str, **changes: Any) -> Optional[dict[str, Any]]:
    with _LOCK:
        jobs = _load_jobs()
        for job in jobs:
            if job["id"] == job_id:
                job.update(changes)
                _save_jobs(jobs)
                return job
    return None


def _output_root(target_name: str) -> str:
    target = get_target(target_name)
    if target_name == "cluster" and getattr(target, "root", ""):
        return f"{target.root}/runs"
    return str(STATE_DIR / "runs")


def _check(script_text: str, check_paths: bool):
    def path_checker(target_name: str, paths: list[str]) -> dict[str, bool]:
        target = get_target(target_name)
        parents = [p.rstrip("/").rsplit("/", 1)[0] or "/" for p in paths]
        return target.exists(paths + parents)

    script, diags = check(script_text, PRESETS, path_checker if check_paths else None)
    errors = [d for d in diags if d.severity == "error"]
    plan = None
    if script is not None and not errors:
        plan = compile_script(script)
    return script, diags, errors, plan


class DraftRequest(BaseModel):
    request: str
    target: str = "cluster"


class ScriptRequest(BaseModel):
    script: str
    check_paths: bool = True
    request: str = ""


@router.get("/schema")
def schema() -> dict[str, Any]:
    cluster = get_target("cluster")
    return {
        "tasks": {verb: [{"name": s.name, "kind": s.kind, "required": s.required, "help": s.help, "default": s.default}
                         for s in specs] for verb, specs in SCHEMA.items()},
        "presets": list(PRESETS),
        "targets": list(TARGETS),
        "cluster": {"configured": cluster.configured, "host": cluster.host, "root": cluster.root,
                    "partition": cluster.partition},
        "draft_model": drafter.DRAFT_MODEL,
        "managed_keys": {verb: list(keys) for verb, keys in MANAGED_KEYS.items()},
    }


@router.post("/draft")
def draft(body: DraftRequest) -> dict[str, Any]:
    if body.target not in TARGETS:
        raise HTTPException(400, f"Unknown target {body.target}.")
    target = get_target(body.target)
    return drafter.draft(body.request, target, _load_jobs(), _output_root(body.target))


class ConverseRequest(BaseModel):
    request: str = ""
    script: str
    message: str
    thread: list[dict[str, str]] = []
    draft_note: str = ""


@router.post("/converse")
def converse(body: ConverseRequest) -> dict[str, Any]:
    """Answer a question about the script, or propose a revised script from feedback."""
    script, _ = check(body.script, PRESETS)
    task = script.as_dict() if script else None
    target = get_target((task or {}).get("target") or "cluster")
    result = drafter.converse(body.request, body.script, body.message, body.thread, task, target,
                              _load_jobs(), body.draft_note)
    if result.get("script"):
        _, diags, errors, _ = _check(result["script"], True)
        result["problems"] = [d.as_dict() for d in errors]
    return result


@router.post("/check")
def check_script(body: ScriptRequest) -> dict[str, Any]:
    script, diags, errors, plan = _check(body.script, body.check_paths)
    return {
        "ok": not errors,
        "diagnostics": [d.as_dict() for d in diags],
        "task": script.as_dict() if script else None,
        "plan": plan.as_dict() if plan else None,
    }


@router.post("/run")
def run_script(body: ScriptRequest) -> dict[str, Any]:
    script, diags, errors, plan = _check(body.script, True)
    if errors or plan is None:
        raise HTTPException(422, {"message": "Fix the errors before running.", "diagnostics": [d.as_dict() for d in diags]})
    target = get_target(plan.target)
    job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    job: dict[str, Any] = {
        "id": job_id,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "request": body.request,
        "script": body.script,
        "verb": plan.verb,
        "target": plan.target,
        "summary": plan.summary,
        "changes": plan.changes,
        "outputs": plan.outputs,
        "state": "submitting",
    }
    try:
        if plan.verb == "view":
            paths = [plan.outputs["image"]] + ([plan.outputs["label"]] if "label" in plan.outputs else [])
            local = target.fetch(paths)
            job.update(state="done", local_paths=local)
        else:
            job["handle"] = target.submit(plan, job_id)
            job["state"] = "queued"
    except TargetError as exc:
        job.update(state="failed", error=str(exc))
    with _LOCK:
        jobs = _load_jobs()
        jobs.append(job)
        _save_jobs(jobs)
    return job


@router.get("/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return list(reversed(_load_jobs()))[:30]


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = next((j for j in _load_jobs() if j["id"] == job_id), None)
    if job is None:
        raise HTTPException(404, "No such job.")
    if job.get("handle") and job["state"] in ("queued", "running", "submitting", "unknown"):
        try:
            status = get_target(job["target"]).status(job["handle"])
        except TargetError as exc:
            return dict(job, log=f"(could not reach the {job['target']}: {exc})")
        changes: dict[str, Any] = {"state": status["state"]}
        if status["metrics"]:
            try:
                changes["metrics"] = json.loads(status["metrics"])
            except json.JSONDecodeError:
                pass
        job = _update_job(job_id, **changes) or job
        return dict(job, log=status["log"])
    if job.get("handle"):
        try:
            status = get_target(job["target"]).status(job["handle"])
            return dict(job, log=status["log"])
        except TargetError:
            pass
    return job


@router.post("/jobs/{job_id}/viewer")
def prepare_viewer(job_id: str) -> dict[str, Any]:
    """Make a finished view task's files viewable: label volumes must be 3D integer labels."""
    job = next((j for j in _load_jobs() if j["id"] == job_id), None)
    if job is None or job.get("verb") != "view" or not job.get("local_paths"):
        raise HTTPException(404, "No viewable files for this run.")
    try:
        return viewing.prepare(job["local_paths"])
    except (ValueError, OSError) as exc:
        raise HTTPException(422, f"Could not prepare the files for viewing: {exc}") from exc


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    job = next((j for j in _load_jobs() if j["id"] == job_id), None)
    if job is None or not job.get("handle"):
        raise HTTPException(404, "No such running job.")
    try:
        get_target(job["target"]).cancel(job["handle"])
    except TargetError as exc:
        raise HTTPException(502, str(exc)) from exc
    return _update_job(job_id, state="cancelled") or job
