"""Project-manager scaffold: persisted delegation to bounded, read-only workers.

The local-model executor plans tasks and selects bounded tools; deterministic checks remain available when no model is configured.
Specialist boundaries and task/result contracts are explicit so model-backed workers
can be substituted without giving them unrestricted workflow or filesystem writes.
"""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
import tifffile
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Session, sessionmaker

from server_api.auth.database import Base, get_db
from server_api.auth.router import get_current_user
from .service import append_workflow_event, decode_json, get_user_workflow_or_404
from . import team_llm

router = APIRouter()
ROLES = {
    "data": ("Data specialist", "Inspect the registered image and label geometry.", ["inspect_tiff"]),
    "annotation": ("Annotation specialist", "Check saved corrections and review boundaries.", ["stat_artifact"]),
    "model": ("Model specialist", "Check configured model inputs and existing artifacts.", ["stat_artifact"]),
}
PATHS = ("image_path", "label_path", "mask_path", "corrected_mask_path", "checkpoint_path", "config_path", "inference_output_path")


class AgentTeamRun(Base):
    __tablename__ = "workflow_team_runs"
    __table_args__ = (UniqueConstraint("workflow_id", "request_key"),)
    id = Column(String, primary_key=True)
    workflow_id = Column(Integer, ForeignKey("workflow_sessions.id"), nullable=False, index=True)
    request_key = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    payload_json = Column(Text, nullable=False)
    created_at = Column(String, nullable=False, default=lambda: datetime.now(timezone.utc).isoformat())


class TeamRequest(BaseModel):
    scope: Literal["project", "data", "annotation", "model"] = "project"
    goal: str = Field(default="Review the project and identify a supported next step.", max_length=2000)
    request_key: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=100)


def now():
    return datetime.now(timezone.utc).isoformat()


def file_ref(value):
    if not value:
        return {"path": None, "exists": False}
    path = Path(value).expanduser()
    try:
        stat = path.stat()
        return {"path": str(path), "exists": True, "is_file": path.is_file(), "bytes": stat.st_size, "modified_ns": stat.st_mtime_ns}
    except OSError:
        return {"path": str(path), "exists": False}


def snapshot(workflow):
    metadata = decode_json(workflow.metadata_json)
    return {"workflow_id": workflow.id, "project": workflow.title, "stage": workflow.stage,
            "objective": metadata.get("project_context", {}),
            "artifacts": {key: file_ref(getattr(workflow, key)) for key in PATHS}}


def fingerprint(context):
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()


def task_context(context, role):
    keys = {"data": ("image_path", "label_path"),
            "annotation": ("mask_path", "label_path", "corrected_mask_path"),
            "model": ("image_path", "label_path", "corrected_mask_path", "config_path", "checkpoint_path", "inference_output_path")}[role]
    return {"workflow_id": context["workflow_id"], "objective": context["objective"],
            "artifacts": {key: context["artifacts"][key] for key in keys}}


def inspect_tiff(ref, labels=False):
    if not ref["exists"] or not ref.get("is_file"):
        raise ValueError("A concrete TIFF file is required; select a volume pair first.")
    path = Path(ref["path"])
    if path.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("This inspection worker currently supports TIFF volumes only.")
    with tifffile.TiffFile(path) as handle:
        series = handle.series[0]
        info = {"path": str(path), "shape": list(series.shape), "dtype": str(series.dtype)}
        if labels:
            decoded_bytes = int(np.prod(series.shape, dtype=object)) * series.dtype.itemsize
            if decoded_bytes > 64 * 1024 * 1024:
                info["label_count_note"] = "Counting skipped: decoded label volume exceeds 64 MiB inspection budget."
            elif series.dtype.kind not in "uib":
                info["label_count_note"] = "Not an integer label volume; instance counting skipped."
            else:
                ids = np.unique(series.asarray())
                info["nonzero_label_ids"] = int(np.count_nonzero(ids))
        return info


def run_specialist(role, context):
    """Role-specific tools receive only the selected, immutable project snapshot."""
    artifacts = {key: file_ref(ref["path"]) for key, ref in context["artifacts"].items()}
    observations, blockers, actions = [], [], []
    facts = {}
    if role == "data":
        for key, label in (("image_path", False), ("label_path", True)):
            try:
                facts[key] = inspect_tiff(artifacts[key], labels=label)
            except (ValueError, OSError, tifffile.TiffFileError) as error:
                blockers.append(f"{key.replace('_path', '').capitalize()}: {error}")
        image, labels = facts.get("image_path"), facts.get("label_path")
        if image:
            observations.append(f"Image: {' × '.join(map(str, image['shape']))} voxels, {image['dtype']}.")
        if labels:
            count = labels.get("nonzero_label_ids")
            observations.append(f"Labels: {count} nonzero IDs." if count is not None else labels.get("label_count_note", "Label metadata inspected."))
        if image and labels:
            if image["shape"] != labels["shape"]:
                blockers.append("Image and label shapes differ; check the selected pair.")
            else:
                observations.append("Image and label shapes match.")
                actions.append({"label": "Open proofreading", "kind": "proofread", "query": "Start proofreading"})
        if image:
            actions.append({"label": "View data", "kind": "visualize", "query": "Show this data in the viewer"})
    elif role == "annotation":
        corrected = artifacts["corrected_mask_path"]
        saved = corrected["exists"] and corrected.get("is_file")
        facts["saved_correction_artifact"] = corrected
        observations.append("A saved correction artifact is registered." if saved else "No saved correction artifact is registered.")
        if saved:
            actions.append({"label": "Prepare training", "kind": "prepare_training", "query": "Train on saved edits"})
        elif any(artifacts[key]["exists"] for key in ("mask_path", "label_path")):
            actions.append({"label": "Open proofreading", "kind": "proofread", "query": "Start proofreading"})
        else:
            blockers.append("No label or mask is available for proofreading.")
    elif role == "model":
        facts = artifacts
        for key, name in (("config_path", "Training preset"), ("checkpoint_path", "Checkpoint"), ("inference_output_path", "Prediction")):
            ref = artifacts[key]
            observations.append(f"{name}: {'registered file exists' if ref['exists'] and ref.get('is_file') else 'no registered file available'}.")
        if artifacts["checkpoint_path"]["exists"]:
            actions.append({"label": "Prepare model run", "kind": "prepare_inference", "query": "Run model"})
        if not artifacts["image_path"]["exists"]:
            blockers.append("Training and inference need an accessible image.")
    return {"observations": observations, "facts": facts, "blockers": blockers, "actions": actions}


def store(db, row, payload):
    row.payload_json = json.dumps(payload)
    db.add(row)
    db.commit()


def execute_run(bind, run_id):
    with sessionmaker(bind=bind)() as lookup:
        record = lookup.get(AgentTeamRun, run_id)
        if json.loads(record.payload_json).get("executor") == "local_llm":
            return execute_model_run(bind, run_id)
    with sessionmaker(bind=bind)() as db:
        row = db.get(AgentTeamRun, run_id)
        payload = json.loads(row.payload_json)
        row.status = "running"
        store(db, row, payload)
        for task in payload["tasks"]:
            task.update(status="running", started_at=now())
            store(db, row, payload)
            try:
                task["result"] = run_specialist(task["role"], task["context"])
                task["status"] = "blocked" if task["result"]["blockers"] else "completed"
            except Exception as error:
                task.update(status="failed", error=f"{type(error).__name__}: {error}")
            task["finished_at"] = now()
            store(db, row, payload)
        needs_attention = any(task["status"] != "completed" for task in payload["tasks"])
        row.status = "needs_attention" if needs_attention else "completed"
        payload["finished_at"] = now()
        results = {task["role"]: task.get("result", {}) for task in payload["tasks"]}
        annotation = results.get("annotation", {}).get("facts", {}).get("saved_correction_artifact", {})
        if needs_attention:
            payload["summary"] = "The specialists found issues that need attention. Review the flagged tasks before continuing."
        elif "annotation" in results:
            payload["summary"] = (
                "Saved corrections are available. Review them, then prepare training when ready."
                if annotation.get("exists") and annotation.get("is_file") else
                "No saved corrections are registered. Start with proofreading, then prepare training from the saved edits."
            )
        else:
            payload["summary"] = "The requested specialist check is complete. Findings and proposed next steps are below."

        # The manager integrates proposals; specialists never execute app mutations.
        payload["actions"] = []
        seen = set()
        data_failed = any(t["role"] == "data" and t["status"] != "completed" for t in payload["tasks"])
        for task in sorted(payload["tasks"], key=lambda task: {"annotation": 0, "data": 1, "model": 2}[task["role"]]):
            if task["status"] != "completed" or data_failed:
                continue
            for action in task.get("result", {}).get("actions", []):
                if action["query"] not in seen:
                    seen.add(action["query"])
                    payload["actions"].append({**action, "source_task_id": task["id"]})
        append_workflow_event(db, workflow_id=row.workflow_id, actor="agent",
                              event_type="agent_team.completed", summary=payload["summary"],
                              payload={"run_id": row.id, "status": row.status, "executor": payload["executor"],
                                       "tasks": [{"id": t["id"], "role": t["role"], "status": t["status"]} for t in payload["tasks"]]}, commit=False)
        store(db, row, payload)


def serialize(row, workflow):
    payload = json.loads(row.payload_json)
    return {**payload, "id": row.id, "workflow_id": row.workflow_id, "status": row.status,
            "stale": payload["context_fingerprint"] != fingerprint(snapshot(workflow))}


@router.get("/{workflow_id}/team-runs")
def list_runs(workflow_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    rows = db.query(AgentTeamRun).filter_by(workflow_id=workflow_id).order_by(AgentTeamRun.created_at.desc()).limit(20).all()
    return sorted([serialize(row, workflow) for row in rows], key=lambda item: item["created_at"], reverse=True)


@router.post("/{workflow_id}/team-runs", status_code=202)
def start_run(workflow_id: int, body: TeamRequest, background: BackgroundTasks,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    existing = db.query(AgentTeamRun).filter_by(workflow_id=workflow_id, request_key=body.request_key).first()
    if existing:
        return serialize(existing, workflow)
    if db.query(AgentTeamRun).filter(AgentTeamRun.workflow_id == workflow_id, AgentTeamRun.status.in_(["queued", "running"])).first():
        raise HTTPException(409, "A project check is already running.")
    context = snapshot(workflow)
    model_config = team_llm.settings()
    roles = [] if model_config["model"] else (list(ROLES) if body.scope == "project" else [body.scope])
    run_id = str(uuid.uuid4())
    payload = {"created_at": now(), "manager": "Project manager", "executor": "local_llm" if model_config["model"] else "tool_backed_scaffold",
               "model_config": model_config, "phase": "queued", "model_calls": [],
               "goal": body.goal, "scope": body.scope,
               "context_fingerprint": fingerprint(context), "context": context,
               "summary": "The project manager is preparing the task plan." if model_config["model"] else "The project manager is collecting bounded specialist checks.",
               "tasks": [{"id": f"{run_id}:{role}", "role": role, "name": ROLES[role][0],
                          "goal": ROLES[role][1], "tools": ROLES[role][2], "status": "queued",
                          "context": task_context(context, role)} for role in roles]}
    row = AgentTeamRun(id=run_id, workflow_id=workflow_id, request_key=body.request_key, payload_json=json.dumps(payload))
    db.add(row)
    append_workflow_event(db, workflow_id=workflow_id, actor="agent", event_type="agent_team.delegated",
                          summary="Project manager delegated bounded specialist checks.",
                          payload={"run_id": run_id, "roles": roles, "executor": payload["executor"]}, commit=False)
    db.commit()
    background.add_task(execute_run, db.get_bind(), run_id)
    return serialize(row, workflow)


def recover_interrupted_runs(bind):
    """A server restart cannot truthfully leave in-process work marked running."""
    with sessionmaker(bind=bind)() as db:
        for row in db.query(AgentTeamRun).filter(AgentTeamRun.status.in_(["queued", "running"])):
            payload = json.loads(row.payload_json)
            row.status = "interrupted"
            payload["summary"] = "The server restarted before the checks finished. Run a fresh project check."
            for task in payload["tasks"]:
                if task["status"] in {"queued", "running"}:
                    task["status"] = "interrupted"
            store(db, row, payload)


def delegation_scope(query):
    """Recognize explicit delegation/check requests; do not intercept job commands."""
    text = query.lower().strip()
    if re.search(r"\b(?:don't|do not|never)\s+(?:ask|delegate|check|inspect|review)\b", text):
        return None
    if not re.search(r"\b(ask|delegate|inspect|check|review|assess)\b", text):
        return None
    if re.search(r"\b(data|image|volume)\s+(specialist|agent|worker)\b", text):
        return "data"
    if re.search(r"\b(annotation|proofreading)\s+(specialist|agent|worker)\b", text):
        return "annotation"
    if re.search(r"\b(model|training|inference)\s+(specialist|agent|worker)\b", text):
        return "model"
    if re.search(r"\b(team|specialists|whole project|project readiness)\b", text):
        return "project"
    return None


@router.post("/{workflow_id}/team-runs/{run_id}/actions/{index}")
def resolve_action(workflow_id: int, run_id: str, index: int,
                   user=Depends(get_current_user), db: Session = Depends(get_db)):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    row = db.get(AgentTeamRun, run_id)
    if not row or row.workflow_id != workflow_id:
        raise HTTPException(404, "Project check not found.")
    run = serialize(row, workflow)
    if run["stale"]:
        raise HTTPException(409, "Project inputs changed. Run a fresh check before using this result.")
    actions = run.get("actions", [])
    if row.status not in {"completed", "needs_attention"} or index < 0 or index >= len(actions):
        raise HTTPException(404, "Available task action not found.")
    action = actions[index]
    # Compatibility for checks saved before typed handoffs were introduced.
    kind = action.get("kind") or {"Start proofreading": "proofread", "Show this data in the viewer": "visualize",
        "Train on saved edits": "prepare_training", "Run model": "prepare_inference"}.get(action.get("query"))
    image = workflow.image_path
    label = workflow.corrected_mask_path or workflow.mask_path or workflow.label_path
    metadata = decode_json(workflow.metadata_json)
    if kind == "visualize":
        effects = {"navigate_to": "visualization", "set_visualization_image_path": image,
                   "set_visualization_label_path": workflow.label_path,
                   "set_visualization_scales": metadata.get("visualization_scales") or metadata.get("project_context", {}).get("voxel_size_nm") or [1, 1, 1],
                   "runtime_action": {"kind": "load_visualization"}}
    elif kind == "proofread":
        effects = {"navigate_to": "mask-proofreading", "set_proofreading_dataset_path": image,
                   "set_proofreading_mask_path": label, "set_proofreading_project_name": workflow.title,
                   "runtime_action": {"kind": "start_proofreading"}}
    elif kind == "prepare_training":
        effects = {"navigate_to": "training", "set_training_image_path": image,
                   "set_training_label_path": workflow.corrected_mask_path,
                   "set_training_config_preset": workflow.config_path,
                   "set_training_output_path": workflow.training_output_path}
    elif kind == "prepare_inference":
        effects = {"navigate_to": "inference", "set_inference_image_path": image,
                   "set_inference_checkpoint_path": workflow.checkpoint_path,
                   "set_inference_config_preset": workflow.config_path}
    else:
        raise HTTPException(422, "This task action is not supported.")
    append_workflow_event(db, workflow_id=workflow_id, actor="user", event_type="agent_team.action_requested",
                          summary=action["label"], payload={"run_id": run_id, "task_id": action.get("source_task_id"), "kind": kind})
    return {"id": f"team:{run_id}:{index}", "label": action["label"], "workflow_id": workflow_id,
            "requires_approval": kind == "proofread", "risk_level": "loads_editor" if kind == "proofread" else "view_only",
            "client_effects": effects}


def specialist_tools(role, context):
    """All tool inputs are server-selected references; model supplies no paths/code."""
    tools = {ROLES[role][2][0]: lambda: run_specialist(role, context)}
    if role == "model":
        def inspect_config():
            import yaml
            ref = file_ref(context["artifacts"]["config_path"]["path"])
            if not ref["exists"] or not ref.get("is_file"):
                return {"facts": {}, "observations": [], "blockers": ["No registered configuration file exists."], "actions": []}
            if ref["bytes"] > 128 * 1024:
                raise ValueError("Configuration exceeds the 128 KiB inspection budget.")
            config = yaml.safe_load(Path(ref["path"]).read_text())
            if not isinstance(config, dict):
                raise ValueError("Configuration must contain a YAML mapping.")
            facts = {key: config.get(key) for key in ("SYSTEM", "MODEL", "SOLVER")}
            observations = ["Registered training configuration was read; settings do not establish model quality."]
            model = facts.get("MODEL") or {}
            system = facts.get("SYSTEM") or {}
            solver = facts.get("SOLVER") or {}
            if system.get("NUM_GPUS") == 0:
                observations.append("Configured for CPU execution (NUM_GPUS=0).")
            if model.get("INPUT_SIZE"):
                observations.append(f"Input patch: {model['INPUT_SIZE']} voxels; patch dimensions do not describe voxel resolution.")
            if solver.get("ITERATION_TOTAL") is not None:
                observations.append(f"Configured training budget: {solver['ITERATION_TOTAL']} iterations; a smoke-test budget does not establish scientific performance.")
            return {"facts": facts, "observations": observations, "blockers": [], "actions": []}
        tools["inspect_config"] = inspect_config
    return tools


def execute_model_run(bind, run_id):
    from server_api.auth.models import ChatMessage
    from .db_models import WorkflowSession
    with sessionmaker(bind=bind)() as db:
        row = db.get(AgentTeamRun, run_id)
        payload = json.loads(row.payload_json)
        def persist():
            store(db, row, payload)
        def checkpoint():
            db.refresh(row)
            if row.status == "cancelled":
                raise team_llm.Cancelled("Task cancelled by user.")
            workflow = db.get(WorkflowSession, row.workflow_id)
            if workflow is not None:
                db.refresh(workflow)
            if not workflow or fingerprint(snapshot(workflow)) != payload["context_fingerprint"]:
                raise team_llm.ModelFailure("Project inputs changed during the run. Start a fresh task.")
        def record(entry, replace=False):
            # Preserve cancellation state if it arrived while the model was responding.
            db.refresh(row)
            if replace:
                payload["model_calls"][-1] = dict(entry)
            else:
                payload["model_calls"].append(dict(entry))
            persist()
        session = team_llm.ModelSession(payload["model_config"], checkpoint, record)
        try:
            checkpoint()
            row.status = "running"
            payload["phase"] = "planning"
            persist()
            plan = team_llm.plan_run(session, payload["context"], payload["goal"], payload["scope"], payload.get("memory", []))
            payload["plan"] = plan.model_dump()
            payload["summary"] = f"The manager assigned {len(plan.tasks)} specialist task(s). Findings will appear as they finish."
            payload["tasks"] = [{"id": f"{run_id}:{item.role}", "role": item.role, "name": ROLES[item.role][0],
                "goal": item.goal, "tools": list(specialist_tools(item.role, task_context(payload["context"], item.role))),
                "context": task_context(payload["context"], item.role), "status": "queued"} for item in plan.tasks]
            payload["phase"] = "specialists"
            persist()
            for task in payload["tasks"]:
                checkpoint()
                task.update(status="running", started_at=now())
                persist()
                try:
                    task["result"] = team_llm.specialist_run(session, task, specialist_tools(task["role"], task["context"]), persist)
                    task["status"] = "blocked" if task["result"]["blockers"] else "completed"
                except team_llm.Cancelled:
                    raise
                except Exception as error:
                    task.update(status="failed", error=str(error)[:700])
                task["finished_at"] = now()
                persist()
            candidates = []
            data_failed = any(t["role"] == "data" and t["status"] != "completed" for t in payload["tasks"])
            if not data_failed:
                for task in payload["tasks"]:
                    if task["status"] == "completed":
                        for action in task["result"]["actions"]:
                            candidates.append({**action, "source_task_id": task["id"], "id": f"a{len(candidates)}"})
            checkpoint()
            if payload["tasks"]:
                payload["phase"] = "synthesis"
                persist()
                answer = team_llm.synthesize(session, payload["goal"], payload["tasks"], candidates)
                payload["summary"] = answer.summary
                payload["cited_task_ids"] = answer.task_ids
                chosen = set(answer.action_ids)
                seen = set()
                payload["actions"] = []
                for candidate in candidates:
                    if candidate["id"] in chosen and candidate["kind"] not in seen:
                        payload["actions"].append(candidate)
                        seen.add(candidate["kind"])
            else:
                payload["summary"] = plan.message
                payload["actions"] = []
            failed = any(t["status"] != "completed" for t in payload["tasks"])
            row.status = "needs_attention" if failed else "completed"
            if failed:
                payload["summary"] = "Some specialist checks need attention. " + payload["summary"]
        except team_llm.Cancelled:
            row.status = "cancelled"
            payload["summary"] = "Cancelled. No further model calls or app actions will run."
            payload["actions"] = []
        except Exception as error:
            row.status = "failed"
            payload["summary"] = "The model-driven task could not finish. Review the error and retry."
            payload["error"] = str(error)[:1000]
            payload["actions"] = []
        finally:
            payload["phase"] = row.status
            payload["finished_at"] = now()
            for task in payload["tasks"]:
                if task["status"] in {"running", "queued"}:
                    task.update(status="cancelled" if row.status == "cancelled" else "interrupted", finished_at=now())
            persist()
            append_workflow_event(db, workflow_id=row.workflow_id, actor="agent", event_type="agent_team.finished",
                summary=payload["summary"], payload={"run_id": run_id, "executor": "local_llm", "status": row.status,
                "model": payload["model_config"]["model"], "model_calls": len(payload["model_calls"])})
            # Update the manager's persisted reply, not an unrelated conversation.
            if payload.get("conversation_id"):
                for message in db.query(ChatMessage).filter(ChatMessage.conversation_id == payload["conversation_id"],
                        ChatMessage.workflow_id == row.workflow_id, ChatMessage.role == "assistant", ChatMessage.trace_json.contains(run_id)):
                    message.content = payload["summary"]
                db.commit()


@router.get("/team-runtime")
def team_runtime(user=Depends(get_current_user)):
    config = team_llm.settings()
    return {"enabled": bool(config["model"]), "provider": config["provider"], "model": config["model"]}


@router.post("/{workflow_id}/team-runs/{run_id}/cancel")
def cancel_run(workflow_id: int, run_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    workflow = get_user_workflow_or_404(db, workflow_id=workflow_id, user_id=user.id)
    row = db.get(AgentTeamRun, run_id)
    if not row or row.workflow_id != workflow_id:
        raise HTTPException(404, "Project check not found.")
    if row.status in {"queued", "running"}:
        row.status = "cancelled"
        payload = json.loads(row.payload_json)
        payload["summary"] = "Cancellation requested; an in-flight model call may take up to 60 seconds to return."
        payload["actions"] = []
        store(db, row, payload)
    return serialize(row, workflow)
