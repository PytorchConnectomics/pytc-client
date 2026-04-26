from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from .db_models import WorkflowEvent, WorkflowSession
from .service import decode_json

try:  # LangGraph is optional at runtime for now, but the plan is graph-shaped.
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception as exc:  # pragma: no cover - exercised only without LangGraph.
    END = "__end__"
    START = "__start__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False
    LANGGRAPH_IMPORT_ERROR = str(exc)
else:
    LANGGRAPH_IMPORT_ERROR = None


class PlanGraphState(TypedDict, total=False):
    step_index: int
    interrupted: bool
    approval_required: bool


def _latest_exported_mask_path(events: List[WorkflowEvent]) -> Optional[str]:
    for event in reversed(events):
        if event.event_type != "proofreading.masks_exported":
            continue
        payload = decode_json(event.payload_json)
        value = (
            payload.get("corrected_mask_path")
            or payload.get("written_path")
            or payload.get("output_path")
        )
        if value:
            return str(value)
    return None


def _langgraph_runtime_summary() -> Dict[str, Any]:
    if not LANGGRAPH_AVAILABLE:
        return {
            "status": "unavailable",
            "import_error": LANGGRAPH_IMPORT_ERROR,
        }

    try:
        graph = StateGraph(PlanGraphState)

        def enter(state: PlanGraphState) -> PlanGraphState:
            return {"step_index": state.get("step_index", 0)}

        def approval_gate(state: PlanGraphState) -> PlanGraphState:
            return {"approval_required": bool(state.get("approval_required"))}

        graph.add_node("enter_plan", enter)
        graph.add_node("approval_gate", approval_gate)
        graph.add_edge(START, "enter_plan")
        graph.add_edge("enter_plan", "approval_gate")
        graph.add_edge("approval_gate", END)
        graph.compile()
    except Exception as exc:  # pragma: no cover - defensive compatibility guard.
        return {
            "status": "available_compile_failed",
            "import_error": None,
            "compile_error": str(exc),
        }

    return {
        "status": "available_not_executing",
        "state_graph": "StateGraph",
        "interrupt_strategy": "persisted human approval gates",
        "checkpointer": "sqlalchemy workflow_agent_plans/workflow_agent_steps",
    }


def _gate_lookup(gates: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(gate.get("id")): gate for gate in gates}


def _gate_complete(gates_by_id: Dict[str, Dict[str, Any]], gate_id: str) -> bool:
    return bool(gates_by_id.get(gate_id, {}).get("complete"))


def _node_status(
    *,
    action: str,
    gate_id: Optional[str],
    dependencies: List[str],
    gates_by_id: Dict[str, Dict[str, Any]],
    has_hotspots: bool,
) -> str:
    if action == "review_failure_hotspots" and has_hotspots:
        return "completed"
    if gate_id and _gate_complete(gates_by_id, gate_id):
        return "completed"
    if all(_gate_complete(gates_by_id, dependency) for dependency in dependencies):
        return "ready"
    return "blocked"


def build_case_study_plan_graph(
    *,
    workflow: WorkflowSession,
    events: List[WorkflowEvent],
    gates: List[Dict[str, Any]],
    title: Optional[str] = None,
    goal: Optional[str] = None,
) -> Dict[str, Any]:
    gates_by_id = _gate_lookup(gates)
    corrected_mask_path = workflow.corrected_mask_path or _latest_exported_mask_path(
        events
    )
    has_hotspots = bool(getattr(workflow, "region_hotspots", []) or [])
    latest_checkpoint = workflow.checkpoint_path

    step_specs: List[Dict[str, Any]] = [
        {
            "action": "verify_data_context",
            "title": "Verify data context",
            "summary": "Confirm image, label/mask, config, and workflow metadata are linked.",
            "stage": "setup",
            "gate_id": "data_loaded",
            "dependencies": ["workflow_context"],
            "requires_approval": False,
            "client_effects": {"navigate_to": "files"},
            "required_for": ["CS1", "CS7"],
        },
        {
            "action": "run_baseline_inference",
            "title": "Run baseline inference",
            "summary": "Produce or register the initial prediction artifact before proofreading.",
            "stage": "inference",
            "gate_id": "baseline_inference",
            "dependencies": ["data_loaded"],
            "requires_approval": True,
            "client_effects": {
                "navigate_to": "inference",
                "runtime_action": {"kind": "start_inference"},
            },
            "required_for": ["CS1", "CS4"],
        },
        {
            "action": "review_failure_hotspots",
            "title": "Review failure hotspots",
            "summary": "Rank likely failure regions and route the top region into proofreading.",
            "stage": "proofreading",
            "gate_id": None,
            "dependencies": ["baseline_inference"],
            "requires_approval": False,
            "client_effects": {
                "navigate_to": "mask-proofreading",
                "refresh_insights": True,
            },
            "required_for": ["CS2"],
        },
        {
            "action": "export_corrections",
            "title": "Export corrections",
            "summary": "Persist proofread masks as a correction set for retraining.",
            "stage": "proofreading",
            "gate_id": "proofreading_corrections",
            "dependencies": ["baseline_inference"],
            "requires_approval": False,
            "client_effects": {"navigate_to": "mask-proofreading"},
            "required_for": ["CS2", "CS3"],
        },
        {
            "action": "stage_retraining_from_corrections",
            "title": "Stage retraining",
            "summary": "Attach the correction set to the next training configuration.",
            "stage": "retraining_staged",
            "gate_id": "retraining_handoff",
            "dependencies": ["proofreading_corrections"],
            "requires_approval": True,
            "client_effects": {
                "navigate_to": "training",
                "set_training_label_path": corrected_mask_path or "",
            },
            "required_for": ["CS3", "CS5"],
        },
        {
            "action": "launch_retraining",
            "title": "Launch retraining",
            "summary": "Run the candidate training job from staged corrections.",
            "stage": "retraining_staged",
            "gate_id": "training_completion",
            "dependencies": ["retraining_handoff"],
            "requires_approval": True,
            "client_effects": {
                "navigate_to": "training",
                "set_training_label_path": corrected_mask_path or "",
                "runtime_action": {"kind": "start_training"},
            },
            "required_for": ["CS3", "CS6"],
        },
        {
            "action": "register_model_version",
            "title": "Register model version",
            "summary": "Link the produced checkpoint to a versioned candidate model.",
            "stage": "evaluation",
            "gate_id": "model_version",
            "dependencies": ["training_completion"],
            "requires_approval": False,
            "client_effects": {"refresh_insights": True},
            "required_for": ["CS3", "CS4"],
        },
        {
            "action": "run_post_retraining_inference",
            "title": "Run post-retraining inference",
            "summary": "Run inference with the candidate checkpoint for before/after comparison.",
            "stage": "evaluation",
            "gate_id": "post_retraining_inference",
            "dependencies": ["model_version"],
            "requires_approval": True,
            "client_effects": {
                "navigate_to": "inference",
                "set_inference_checkpoint_path": latest_checkpoint or "",
                "runtime_action": {"kind": "start_inference"},
            },
            "required_for": ["CS4"],
        },
        {
            "action": "compute_before_after_evaluation",
            "title": "Compute before/after evaluation",
            "summary": "Compare baseline and candidate predictions against held-out labels.",
            "stage": "evaluation",
            "gate_id": "evaluation_result",
            "dependencies": ["post_retraining_inference"],
            "requires_approval": False,
            "client_effects": {"refresh_insights": True},
            "required_for": ["CS4", "CS7"],
        },
        {
            "action": "audit_agent_control",
            "title": "Audit agent control",
            "summary": "Record human decisions for plan approval, interruption, resume, or rejection.",
            "stage": workflow.stage,
            "gate_id": "agent_audit",
            "dependencies": ["proofreading_corrections"],
            "requires_approval": True,
            "client_effects": {},
            "required_for": ["CS5", "CS6"],
        },
        {
            "action": "export_case_study_bundle",
            "title": "Export case-study bundle",
            "summary": "Export typed artifacts, events, metrics, plans, and evaluation evidence.",
            "stage": "evaluation",
            "gate_id": None,
            "dependencies": [
                "evaluation_result",
                "agent_audit",
                "agent_plan_preview",
            ],
            "requires_approval": False,
            "client_effects": {"refresh_insights": True},
            "required_for": ["CS7"],
        },
    ]

    nodes: List[Dict[str, Any]] = []
    for index, spec in enumerate(step_specs):
        dependencies = list(spec["dependencies"])
        status = _node_status(
            action=spec["action"],
            gate_id=spec["gate_id"],
            dependencies=dependencies,
            gates_by_id=gates_by_id,
            has_hotspots=has_hotspots,
        )
        nodes.append(
            {
                "id": f"step_{index + 1:02d}",
                "index": index,
                **spec,
                "status": status,
            }
        )

    edges: List[Dict[str, str]] = []
    action_to_node = {node["action"]: node["id"] for node in nodes}
    gate_to_node = {
        str(node["gate_id"]): node["id"] for node in nodes if node.get("gate_id")
    }
    for node in nodes:
        for dependency in node["dependencies"]:
            source = gate_to_node.get(dependency) or action_to_node.get(dependency)
            if source:
                edges.append({"source": source, "target": node["id"]})

    completed_count = len([gate for gate in gates if gate.get("complete")])
    total_count = len(gates)
    return {
        "graph_spec_version": "case-study-agent-plan/v1",
        "workflow_id": workflow.id,
        "title": title or "Closed-loop case-study plan",
        "goal": goal
        or "Drive the biomedical segmentation workflow through triage, proofreading, retraining, evaluation, and evidence export.",
        "execution_model": {
            "mode": "bounded_human_approved_plan_preview",
            "mutating_steps_require_approval": True,
            "durability": "workflow_agent_plans and workflow_agent_steps tables",
            "langgraph": _langgraph_runtime_summary(),
        },
        "readiness_snapshot": {
            "completed_count": completed_count,
            "total_count": total_count,
            "ready_for_case_study": completed_count == total_count,
        },
        "nodes": nodes,
        "edges": edges,
    }
