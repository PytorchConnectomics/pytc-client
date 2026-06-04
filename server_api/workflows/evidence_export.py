from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm.exc import DetachedInstanceError

from .bundle_export import _build_project_memory_summary
from .db_models import WorkflowCommand, WorkflowEvent, WorkflowModelRun, WorkflowSession
from .service import decode_json

EVIDENCE_EXPORT_VERSION = "1.0"

PROGRESS_EVENT_TYPES = {
    "training.started",
    "training.completed",
    "training.failed",
    "inference.started",
    "inference.completed",
    "inference.failed",
    "evaluation.completed",
    "evaluation.failed",
}
ACTION_EVENT_TYPES = {
    "training.run_approved",
    "agent.client_effects_approved",
    "retraining.staged",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _event_payload(event: WorkflowEvent) -> Dict[str, Any]:
    return decode_json(event.payload_json)


def _parse_event_time(value: Any) -> datetime:
    if value is None:
        return datetime.min
    if isinstance(value, datetime):
        return value
    if hasattr(value, "isoformat"):
        parsed = value
        if isinstance(parsed, str):
            text = parsed
            if text.endswith("Z"):
                text = text.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                return datetime.min
    return datetime.min


def _event_run_id(payload: Dict[str, Any]) -> Optional[str]:
    for key in (
        "run_id",
        "runId",
        "job_id",
        "jobId",
        "execution_id",
        "executionId",
    ):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return None


def _event_run_type(event_type: Optional[str]) -> Optional[str]:
    if not event_type or "." not in event_type:
        return None
    return event_type.split(".", 1)[0]


def _command_run_type(command_type: Optional[str]) -> Optional[str]:
    if not command_type:
        return None
    if command_type == "start_training":
        return "training"
    if command_type == "start_inference":
        return "inference"
    if command_type == "start_evaluation":
        return "evaluation"
    return None


def _stage_progression(events: List[WorkflowEvent]) -> Dict[str, Any]:
    observed: List[str] = []
    entered_at: Dict[str, str] = {}
    transition_count = 0
    previous_stage: str | None = None

    for event in events:
        stage = event.stage
        if not stage:
            continue
        if stage not in observed:
            observed.append(stage)
            if stage not in entered_at:
                entered_at[stage] = _iso(event.created_at) or ""
        if previous_stage and previous_stage != stage:
            transition_count += 1
        previous_stage = stage

    return {
        "observed_stages": observed,
        "entered_at": entered_at,
        "transition_count": transition_count,
    }


def _proposal_approval_summary(events: List[WorkflowEvent]) -> Dict[str, Any]:
    proposals_by_actor: Counter[str] = Counter()
    decisions_by_actor: Counter[str] = Counter()
    approved = 0
    rejected = 0

    for event in events:
        if event.event_type == "agent.proposal_created":
            proposals_by_actor[event.actor or "unknown"] += 1
        elif event.event_type == "agent.proposal_approved":
            decisions_by_actor[event.actor or "unknown"] += 1
            approved += 1
        elif event.event_type == "agent.proposal_rejected":
            decisions_by_actor[event.actor or "unknown"] += 1
            rejected += 1

    return {
        "proposal_count": int(sum(proposals_by_actor.values())),
        "approved_count": approved,
        "rejected_count": rejected,
        "proposals_by_actor": dict(proposals_by_actor),
        "decisions_by_actor": dict(decisions_by_actor),
    }


def _proposal_approval_links(events: List[WorkflowEvent]) -> List[Dict[str, Any]]:
    created: Dict[int, Dict[str, Any]] = {}
    links: List[Dict[str, Any]] = []

    for event in events:
        event_payload = _event_payload(event)
        if event.event_type == "agent.proposal_created":
            created[int(event.id)] = {
                "proposal_id": int(event.id),
                "proposal_summary": event.summary,
                "proposal_stage": event.stage,
                "proposal_actor": event.actor,
                "proposal_action": event_payload.get("action"),
                "proposal_params": event_payload.get("params"),
                "created_at": _iso(event.created_at),
            }
            continue

        if event.event_type in {"agent.proposal_approved", "agent.proposal_rejected"}:
            proposal_event_id = event_payload.get("proposal_event_id")
            if isinstance(proposal_event_id, int) and proposal_event_id in created:
                links.append(
                    {
                        "proposal_event_id": proposal_event_id,
                        "proposal_summary": created[proposal_event_id].get(
                            "proposal_summary"
                        ),
                        "action": created[proposal_event_id].get("proposal_action"),
                        "params": created[proposal_event_id].get("proposal_params"),
                        "approval_event_id": event.id,
                        "approval_status": event.event_type.split("_")[-1],
                        "approval_stage": event.stage,
                        "approval_actor": event.actor,
                        "approval_at": _iso(event.created_at),
                        "proposal_stage": created[proposal_event_id].get(
                            "proposal_stage"
                        ),
                        "proposal_actor": created[proposal_event_id].get(
                            "proposal_actor"
                        ),
                    }
                )
            else:
                links.append(
                    {
                        "proposal_event_id": proposal_event_id,
                        "approval_event_id": event.id,
                        "approval_status": event.event_type.split("_")[-1],
                        "approval_stage": event.stage,
                        "approval_actor": event.actor,
                        "approval_at": _iso(event.created_at),
                    }
                )

    return links


def _user_status_changes(events: List[WorkflowEvent]) -> List[Dict[str, Any]]:
    status_changes: List[Dict[str, Any]] = []
    last_stage: str | None = None
    for event in events:
        stage = event.stage
        if not stage or event.actor != "user":
            continue
        if stage == last_stage:
            continue
        status_changes.append(
            {
                "at": _iso(event.created_at),
                "event_id": event.id,
                "event_type": event.event_type,
                "stage": stage,
                "source_event_id": event.id,
                "summary": event.summary,
            }
        )
        last_stage = stage
    return status_changes


def _safe_related_records(workflow: WorkflowSession, relationship_name: str) -> List[Any]:
    try:
        records = getattr(workflow, relationship_name)
    except DetachedInstanceError:
        return []
    return list(records or [])


def _timeline_snippet(events: List[WorkflowEvent], max_events: int = 20) -> List[Dict[str, Any]]:
    snippet: List[Dict[str, Any]] = []
    for event in events[:max_events]:
        payload = _event_payload(event)
        snippet.append(
            {
                "timestamp": _iso(event.created_at),
                "event_type": event.event_type,
                "stage": event.stage,
                "actor": event.actor,
                "summary": event.summary,
                "payload_keys": sorted(payload.keys()),
            }
        )
    return snippet


def _safe_len_relationship(workflow: WorkflowSession, attr_name: str) -> int:
    try:
        related = getattr(workflow, attr_name)
    except DetachedInstanceError:
        return 0
    return len(related or [])


def _run_for_event(
    event: WorkflowEvent,
    runs: List[WorkflowModelRun],
) -> Optional[WorkflowModelRun]:
    payload = _event_payload(event)
    run_id = _event_run_id(payload)
    if run_id is not None:
        for row in runs:
            if str(row.run_id) == str(run_id):
                return row

    event_run_type = _event_run_type(event.event_type)
    if event.id is not None:
        for row in runs:
            if row.source_event_id == event.id:
                return row

    if event_run_type is not None:
        if event.created_at:
            candidates = [
                row
                for row in runs
                if row.run_type == event_run_type
                and row.created_at
                and row.created_at <= _parse_event_time(event.created_at)
            ]
            if candidates:
                return max(candidates, key=lambda row: (row.created_at or datetime.min, row.id))

        candidates = [
            row
            for row in runs
            if row.run_type == event_run_type
            and row.id is not None
        ]
        if candidates:
            return max(candidates, key=lambda row: row.id)

    return None


def _run_for_command(
    command: WorkflowCommand,
    runs: List[WorkflowModelRun],
) -> Optional[WorkflowModelRun]:
    run_type = _command_run_type(command.command_type)
    if not run_type:
        return None

    created_at = _parse_event_time(command.created_at)
    candidates = [
        row
        for row in runs
        if row.run_type == run_type
        and row.created_at
        and _parse_event_time(row.created_at) >= created_at
    ]
    if candidates:
        return min(candidates, key=lambda row: (row.created_at or datetime.min, row.id))

    candidates = [row for row in runs if row.run_type == run_type and row.id is not None]
    return min(candidates, key=lambda row: row.id) if candidates else None


def _progress_event_belongs_to_run(
    event: WorkflowEvent,
    run: WorkflowModelRun,
) -> bool:
    payload = _event_payload(event)
    event_run_type = _event_run_type(event.event_type)
    if event_run_type != run.run_type:
        return False
    if run.run_id is not None:
        run_id = _event_run_id(payload)
        if run_id is not None and str(run_id) == str(run.run_id):
            return True
    if event.id is not None and run.source_event_id == event.id:
        return True

    event_time = _parse_event_time(event.created_at)
    run_started = _parse_event_time(run.started_at)
    run_completed = _parse_event_time(run.completed_at)
    if run.started_at and run.completed_at:
        if run_started <= event_time <= run_completed:
            return True
    elif run.started_at and event_time >= run_started:
        return True
    return False


def _build_progress_event_summary(event: WorkflowEvent, run_id: str | None = None) -> Dict[str, Any]:
    payload = _event_payload(event)
    event_run_id = _event_run_id(payload)
    return {
        "event_id": event.id,
        "event_type": event.event_type,
        "status": event.event_type.split(".")[-1],
        "run_type": _event_run_type(event.event_type),
        "run_id": event_run_id if event_run_id is not None else run_id,
        "stage": event.stage,
        "actor": event.actor,
        "created_at": _iso(event.created_at),
        "summary": event.summary,
        "payload_keys": sorted(payload.keys()),
    }


def _build_run_summary(
    run: WorkflowModelRun,
    progress_events: List[WorkflowEvent],
) -> Dict[str, Any]:
    run_progress = [
        _build_progress_event_summary(event, run_id=str(run.run_id))
        for event in progress_events
        if _progress_event_belongs_to_run(event, run)
    ]
    return {
        "run_record_id": run.id,
        "run_id": run.run_id,
        "run_type": run.run_type,
        "status": run.status,
        "name": run.name,
        "config_path": run.config_path,
        "checkpoint_path": run.checkpoint_path,
        "log_path": run.log_path,
        "output_path": run.output_path,
        "source_event_id": run.source_event_id,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "progress_events": run_progress,
    }


def _build_command_summary(command: WorkflowCommand) -> Dict[str, Any]:
    return {
        "command_id": command.id,
        "command_type": command.command_type,
        "status": command.status,
        "idempotency_key": command.idempotency_key,
        "actor": command.actor,
        "source_event_id": command.source_event_id,
        "approval_event_id": command.approval_event_id,
        "attempt_count": command.attempt_count,
        "created_at": _iso(command.created_at),
        "updated_at": _iso(command.updated_at),
        "started_at": _iso(command.started_at),
        "completed_at": _iso(command.completed_at),
    }


def _build_proposal_approval_graph(
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
) -> List[Dict[str, Any]]:
    runs = _safe_related_records(workflow, "model_runs")
    commands = _safe_related_records(workflow, "commands")
    proposal_events = [event for event in events if event.event_type == "agent.proposal_created"]
    if not proposal_events:
        return []

    approvals = [
        event for event in events if event.event_type in {"agent.proposal_approved", "agent.proposal_rejected"}
    ]
    approval_index: Dict[int, List[WorkflowEvent]] = defaultdict(list)
    for approval in approvals:
        approval_payload = _event_payload(approval)
        proposal_id = approval_payload.get("proposal_event_id")
        if isinstance(proposal_id, int):
            approval_index[proposal_id].append(approval)

    actions = [
        event
        for event in events
        if event.event_type in ACTION_EVENT_TYPES
    ]

    progress_events = [
        event for event in events if event.event_type in PROGRESS_EVENT_TYPES
    ]

    graph: List[Dict[str, Any]] = []
    for proposal in proposal_events:
        proposal_payload = _event_payload(proposal)
        proposal_id = proposal.id
        approvals_for_proposal = approval_index.get(int(proposal_id), []) if proposal_id else []
        approval = approvals_for_proposal[0] if approvals_for_proposal else None

        action_events = [
            event
            for event in actions
            if _event_payload(event).get("proposal_event_id") == proposal_id
        ]

        proposal_commands = [
            command
            for command in commands
            if command.source_event_id == proposal_id
            or (approval and command.approval_event_id == approval.id)
        ]

        linked_runs: Dict[int, WorkflowModelRun] = {}
        for action_event in action_events:
            run = _run_for_event(action_event, runs)
            if run is not None and run.id is not None:
                linked_runs[run.id] = run

        for command in proposal_commands:
            run = _run_for_command(command, runs)
            if run is not None and run.id is not None:
                linked_runs[run.id] = run

        run_refs = [_build_run_summary(run, progress_events) for run in sorted(linked_runs.values(), key=lambda row: row.id)]

        graph.append(
            {
                "proposal": {
                    "event_id": proposal.id,
                    "summary": proposal.summary,
                    "stage": proposal.stage,
                    "actor": proposal.actor,
                    "action": proposal_payload.get("action"),
                    "params": proposal_payload.get("params") if isinstance(proposal_payload.get("params"), dict) else {},
                    "created_at": _iso(proposal.created_at),
                },
                "approval": None
                if approval is None
                else {
                    "event_id": approval.id,
                    "status": approval.event_type.split("_")[-1],
                    "stage": approval.stage,
                    "actor": approval.actor,
                    "approved_at": _iso(approval.created_at),
                    "approval_payload": _event_payload(approval),
                },
                "action_events": [
                    {
                        "event_id": event.id,
                        "event_type": event.event_type,
                        "stage": event.stage,
                        "actor": event.actor,
                        "created_at": _iso(event.created_at),
                        "summary": event.summary,
                        "payload": _event_payload(event),
                    }
                    for event in action_events
                ],
                "commands": [_build_command_summary(command) for command in proposal_commands],
                "runs": run_refs,
            }
        )

    return graph


def build_workflow_evidence_export(
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
) -> Dict[str, Any]:
    stage_progression = _stage_progression(events)
    proposal_summary = _proposal_approval_summary(events)
    timeline = _timeline_snippet(events)
    proposal_links = _proposal_approval_links(events)
    status_changes = _user_status_changes(events)
    proposal_graph = _build_proposal_approval_graph(workflow, events)

    return {
        "version": EVIDENCE_EXPORT_VERSION,
        "workflow_id": workflow.id,
        "workflow_stage": workflow.stage,
        "stage_progression_summary": stage_progression,
        "agent_proposal_approval_summary": proposal_summary,
        "agent_proposal_approval_links": proposal_links,
        "agent_proposal_approval_graph": proposal_graph,
        "user_status_changes": status_changes,
        "model_context": {
            "model_run_count": _safe_len_relationship(workflow, "model_runs"),
            "model_version_count": _safe_len_relationship(workflow, "model_versions"),
            "evaluation_result_count": _safe_len_relationship(
                workflow, "evaluation_results"
            ),
        },
        "project_memory_summary": _build_project_memory_summary(workflow),
        "key_event_timeline_snippet": timeline,
    }
