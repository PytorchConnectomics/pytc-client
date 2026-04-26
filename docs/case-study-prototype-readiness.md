# Case-Study Prototype Readiness Protocol

This protocol defines the researcher/facilitator evidence needed before using
the prototype in paper-facing case studies. These gates are not participant UI.
The participant-facing target remains an agent-mediated, closed-loop biomedical
segmentation workflow, not a standalone PyTC GUI and not a case-study protocol
manager.

## Prototype Boundary

- Do not expose case-study design, case-study readiness gates, or case-study
  plan generation in the participant prototype.
- Keep researcher-only checks available through backend tests, backend routes,
  exported bundles, and this protocol document.
- Participant-facing controls should stay biomedical-workflow focused: load
  data, run inference, inspect hotspots, proofread, approve/reject risky agent
  actions, retrain, compare outputs, and export evidence.
- If a facilitator UI is added later, label it separately as researcher/study
  instrumentation rather than part of the biomedical user workflow.

## User Workflow Loop

1. Create or resume a workflow project.
2. Load image, label, mask, checkpoint, and configuration artifacts.
3. Run or load baseline inference.
4. Inspect results with workflow-aware agent guidance.
5. Review ranked failure hotspots.
6. Proofread selected masks and save corrections.
7. Export a `CorrectionSet`.
8. Preview correction impact and retraining readiness.
9. Review an agent-proposed next action.
10. Approve, reject, interrupt, or resume risky workflow actions.
11. Run retraining from the staged corrections.
12. Register the resulting `ModelVersion`.
13. Re-run inference with the new checkpoint.
14. Compare before/after outputs and metrics.
15. Export the evidence bundle for analysis and paper figures.

## Case Studies

| ID | Purpose | Participant Task | Required Prototype Gate |
| --- | --- | --- | --- |
| CS1 | Workflow continuity | Load data, create viewer, run or inspect inference, proofread, inspect timeline | Workflow context, data artifacts, baseline inference |
| CS2 | Agent-guided triage | Ask where to inspect, review hotspot ranking, correct a selected region | Persisted hotspots, workflow-grounded agent response |
| CS3 | Correction-to-retraining loop | Export corrections, preview impact, approve retraining, produce checkpoint | `CorrectionSet`, training `ModelRun`, `ModelVersion` |
| CS4 | Before/after evidence | Compare baseline and post-retraining inference | Two inference runs plus `EvaluationResult` |
| CS5 | Approval-gated control | Review, approve, reject, and inspect agent proposals | Proposal events, approval/rejection events |
| CS6 | Failure recovery | Recover from failed training, bad config, or interrupted run | Terminal failure events, interrupted/resumed agent plan, visible next action |
| CS7 | Study export | Export state, artifacts, metrics, events, screenshots, and task timing | Evidence bundle with typed records |

## Instrumentation Checklist

- Capture every task transition as a `WorkflowEvent`.
- Materialize image, mask, correction, checkpoint, prediction, and report paths as
  `WorkflowArtifact` records.
- Record inference and training lifecycle as `WorkflowModelRun` records.
- Register candidate checkpoints as `WorkflowModelVersion` records.
- Store before/after metrics as `WorkflowEvaluationResult` records.
- Store bounded plan previews and approval/interruption state as
  `WorkflowAgentPlan` and `WorkflowAgentStep` records for researcher-only
  protocol verification, not participant-facing app controls.
- Export event logs, typed artifacts, run/version records, correction sets,
  evaluation results, agent plans, and artifact-existence checks in the workflow
  bundle.
- Use `/api/workflows/{workflow_id}/case-study-readiness` before each session.

## UI Consistency Checklist

- Every stage page starts with the same `StageHeader` anatomy.
- The workflow rail uses the same stage names as the paper: setup,
  visualization, inference, proofreading, retraining staged, evaluation.
- Agent proposals always display title, proposal type, approval state, rationale,
  artifact references, and approve/reject controls.
- Repeated functions keep consistent labels: `Approve`, `Reject`, `Refresh
  Insights`, `Start Training`, `Start Inference`, `Open Proofreading`.
- Status colors are semantic, not decorative: amber for review/staging, green for
  completed/model-ready, red for failure/high risk, blue/teal for inspection.
- Keyboard focus and accessible names must remain consistent across repeated
  controls.
- Case-study readiness and protocol-plan previews are intentionally absent from
  the participant prototype.

## Pre-Session Exit Criteria

- The readiness endpoint has no missing P0 gates for the selected study.
- The facilitator can complete the full scripted loop on the frozen sample data.
- The evidence bundle includes typed artifacts, events, model runs, model
  versions, correction sets, evaluation records, and agent plan records.
- Screenshots for the paper can be regenerated from the scripted walkthrough.
- The paper wording matches the demonstrated prototype behavior.
