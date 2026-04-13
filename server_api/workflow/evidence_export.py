from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from .data_access import WorkflowDataError, load_workflow_payload

EVIDENCE_EXPORT_VERSION = "1.0"


def _stage_progression(payload: Dict[str, Any]) -> Dict[str, Any]:
    stages = payload.get("stages") if isinstance(payload.get("stages"), list) else []
    events = payload["events"]

    observed: List[str] = []
    entered_at: Dict[str, str] = {}
    transition_count = 0

    for event in events:
        event_type = event.get("type")
        stage = event.get("stage")
        if event_type in {"stage_entered", "stage_changed"} and isinstance(stage, str):
            transition_count += 1
            if stage not in observed:
                observed.append(stage)
            if stage not in entered_at and isinstance(event.get("timestamp"), str):
                entered_at[stage] = event["timestamp"]

    completed = [stage for stage in stages if stage in observed]
    pending = [stage for stage in stages if stage not in observed]

    return {
        "declared_stages": stages,
        "observed_stages": observed,
        "completed_stages": completed,
        "pending_stages": pending,
        "entered_at": entered_at,
        "transition_count": transition_count,
    }


def _proposal_approval_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    proposals_by_agent: Counter[str] = Counter()
    approvals_by_agent: Counter[str] = Counter()
    decisions_by_proposal: Dict[str, Dict[str, Any]] = defaultdict(dict)

    for event in events:
        event_type = event.get("type")
        proposal_id = str(event.get("proposal_id")) if event.get("proposal_id") is not None else None
        agent = event.get("agent") if isinstance(event.get("agent"), str) else "unknown"

        if event_type == "proposal_submitted":
            proposals_by_agent[agent] += 1
            if proposal_id:
                decisions_by_proposal[proposal_id]["submitted_by"] = agent
                decisions_by_proposal[proposal_id]["submitted_at"] = event.get("timestamp")
        elif event_type in {"proposal_approved", "proposal_rejected"}:
            approvals_by_agent[agent] += 1
            if proposal_id:
                decisions_by_proposal[proposal_id]["decision"] = (
                    "approved" if event_type == "proposal_approved" else "rejected"
                )
                decisions_by_proposal[proposal_id]["decided_by"] = agent
                decisions_by_proposal[proposal_id]["decided_at"] = event.get("timestamp")

    approved_count = sum(
        1 for details in decisions_by_proposal.values() if details.get("decision") == "approved"
    )
    rejected_count = sum(
        1 for details in decisions_by_proposal.values() if details.get("decision") == "rejected"
    )

    return {
        "proposal_count": int(sum(proposals_by_agent.values())),
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "proposals_by_agent": dict(proposals_by_agent),
        "decisions_by_agent": dict(approvals_by_agent),
        "proposals": dict(decisions_by_proposal),
    }


def _timeline_snippet(events: List[Dict[str, Any]], max_events: int = 20) -> List[Dict[str, Any]]:
    timeline: List[Dict[str, Any]] = []
    for event in events[:max_events]:
        timeline.append(
            {
                "timestamp": event.get("timestamp"),
                "event_type": event.get("type"),
                "stage": event.get("stage"),
                "agent": event.get("agent"),
                "proposal_id": event.get("proposal_id"),
                "status": event.get("status"),
            }
        )
    return timeline


def build_workflow_evidence_export(payload: Dict[str, Any]) -> Dict[str, Any]:
    events = payload.get("events", [])
    return {
        "version": EVIDENCE_EXPORT_VERSION,
        "workflow_id": payload.get("workflow_id"),
        "stage_progression_summary": _stage_progression(payload),
        "agent_proposal_approval_summary": _proposal_approval_summary(events),
        "key_event_timeline_snippet": _timeline_snippet(events),
    }


def export_workflow_evidence(workflow_path: str | Path, output_path: str | Path) -> Path:
    payload = load_workflow_payload(workflow_path)
    export_payload = build_workflow_evidence_export(payload)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(export_payload, indent=2), encoding="utf-8")
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export workflow evidence summaries for paper-writing notes."
    )
    parser.add_argument("--workflow-json", required=True, help="Path to workflow JSON input")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write export JSON (for example docs/research/exports/workflow-evidence.json)",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        output = export_workflow_evidence(args.workflow_json, args.output)
    except WorkflowDataError as exc:
        print(f"workflow evidence export failed: {exc}")
        return 2

    print(f"workflow evidence export written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
