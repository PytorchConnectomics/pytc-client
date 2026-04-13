from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from .db_models import WorkflowEvent, WorkflowSession
from .service import decode_json

EVIDENCE_EXPORT_VERSION = "1.0"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


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


def _timeline_snippet(events: List[WorkflowEvent], max_events: int = 20) -> List[Dict[str, Any]]:
    snippet: List[Dict[str, Any]] = []
    for event in events[:max_events]:
        payload = decode_json(event.payload_json)
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


def build_workflow_evidence_export(
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
) -> Dict[str, Any]:
    stage_progression = _stage_progression(events)
    proposal_summary = _proposal_approval_summary(events)
    timeline = _timeline_snippet(events)

    return {
        "version": EVIDENCE_EXPORT_VERSION,
        "workflow_id": workflow.id,
        "workflow_stage": workflow.stage,
        "stage_progression_summary": stage_progression,
        "agent_proposal_approval_summary": proposal_summary,
        "key_event_timeline_snippet": timeline,
    }
