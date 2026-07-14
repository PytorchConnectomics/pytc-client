# seg.bio Prototype Implementation Report - 2026-06-04

## Summary

This report records the major implementation work completed on the `checkpoint/tochi-agentic-prototype` branch for the seg.bio / PyTC Client prototype. The work moved the app from a mostly tab-and-chat prototype toward a workflow-aware, approval-gated project operator for biomedical volume segmentation case studies.

The main throughline was:

1. Make mounted projects inspectable and understandable to the app.
2. Make project progress visible as workflow state, not hidden chat context.
3. Let the agent propose bounded workflow actions with editable fields and approval gates.
4. Keep chat human-readable while exposing operational traces separately.
5. Build a Yixiao TapeReader/XRI case-study fixture and smoke-test path.
6. Add enough runtime logging and operator diagnostics to support demo deployment.
7. Preserve paper-facing research, provenance, and implementation context in markdown.

The current deployed branch head is:

```text
a047f34 docs(research): capture paper prototype roadmap
```

Remote branch:

```text
origin/checkpoint/tochi-agentic-prototype
```

## Recent Commit Split

The latest pushed split was:

```text
d706244 feat(workflows): harden project memory and provenance
302a373 feat(auth): add project user management foundations
e24c205 feat(ui): surface workflow agents and editable action cards
e364ffb test(demo): add Yixiao case study gates
a047f34 docs(research): capture paper prototype roadmap
```

These were pushed after earlier commits on the same branch:

```text
eb5cce6 feat(projects): confirm mounted project context
1b80965 feat(workflows): add progress-aware agent commands
c1f3d7a feat(assistant): keep workflow chat continuous
143d127 feat(viewer): harden visualization and proofreading
4ea4bb1 fix(runtime): launch multi-volume training subsets
3292ff7 chore(logging): capture detailed app events
c151bf9 docs: record agent prototype progress
```

## Project Context And Onboarding

The mounted-project flow was changed from a blank text box into a guided, inspection-led intake.

What changed:

- Added mounted project context confirmation and project observation logic.
- Added a compact shared project facts panel in the setup modal.
- Propagated project facts such as modality, target structure, task family, voxel size, training policy, volume split, and image-only strategy into workflow metadata.
- Removed brittle assumptions like hard-coded default image scales where possible and moved toward project-derived voxel sizes.
- Added project suggestion handling so the demo can mount the intended Yixiao case-study project instead of a stale/default project.

Why it matters:

- Biologists should not need to know what facts the agent needs up front.
- The app should inspect first, then ask concrete follow-up questions.
- The agent needs canonical project context instead of relying on chat memory.

Key files:

- `client/src/views/FilesManager.js`
- `client/src/utils/projectSuggestions.js`
- `server_api/workflows/router.py`
- `server_api/workflows/service.py`

## Project Progress And Workflow State

The progress surface was rebuilt into a workflow reference point for both users and the agent.

What changed:

- Added per-volume progress states:
  - `ground_truth`
  - `needs_proofreading`
  - `missing_segmentation`
  - `ignored`
- Added canonical-ish derived state fields such as annotation state, role state, and execution state in progress snapshots.
- Added progress summaries for total tracked volumes, fully good/reference volumes, proofreading targets, missing segmentation targets, completion percentage, and segmentation coverage.
- Added volume-level status update routes and UI controls.
- Made the agent read and use project progress when proposing training, proofreading, and inference actions.

Why it matters:

- The progress tab is not just a dashboard; it is shared memory for the workflow.
- Training eligibility now depends on trusted volume status instead of mask file existence alone.
- The user and the agent can refer to the same volume-level state.

Key files:

- `client/src/views/ProjectProgress.js`
- `server_api/workflows/router.py`
- `server_api/workflows/db_models.py`
- `tests/test_workflow_routes.py`
- `tests/test_workflow_case_study_acceptance.py`

## Agentic Workflow Implementation

The agent was reshaped away from generic chat and toward a workflow operator that can propose bounded routines.

What changed:

- Added agent action proposal cards.
- Added approval/reject flow for costly or mutating actions.
- Added editable action fields before approval, so users can correct auto-filled paths and parameters.
- Added specialist-agent visual encoding with icons and color accents.
- Added operational traces to cards and timeline entries.
- Added continuous main workflow chat instead of fragmented chat history.
- Added APIs for fetching workflow agent conversation.
- Added route behavior for project, visualization, proofreading, training, and progress intents.
- Improved natural-language handling for casual requests like "train on my good data" or "what are we looking at?"

Why it matters:

- The agent can propose real app routines without silently executing risky work.
- The user can correct fields before launch rather than having only Approve/Reject.
- The chat can sound normal while the mechanics remain inspectable in a trace.

Key files:

- `client/src/components/Chatbot.js`
- `client/src/components/chat/AgentProposalCard.js`
- `client/src/components/chat/AssistantActionCard.js`
- `client/src/components/chat/AssistantTrace.js`
- `client/src/components/chat/AgentVisuals.js`
- `client/src/contexts/WorkflowContext.js`
- `client/src/contexts/workflow/proposalCardConfig.js`
- `server_api/workflows/router.py`

## Operational Traces

The app now exposes workflow traces without dumping robotic reasoning into the main answer.

Trace sections include:

- Inspected facts.
- Policy decision.
- Approval or execution status.
- Affected artifacts.
- Project-memory updates.

Trace data can be parsed from:

- `trace`
- `params.trace`
- `payload.trace`
- `action_card.trace`
- `payload_json`

Why it matters:

- This supports the paper framing around progressive disclosure.
- It makes agent behavior auditable without showing raw hidden reasoning.
- It makes the system feel more like a workflow harness than a plain chatbot.

## Multi-Volume Training

Training flow was changed to support clean multi-volume subsets.

What changed:

- The agent can stage a training run from all currently trusted ground-truth volumes.
- Draft masks and image-only volumes are excluded by policy.
- The system writes staged subset directories/manifests for training.
- Training action cards show selected config, images, labels, output path, training set count, left-out volumes, and parameters.
- Approval can populate the Train Model UI with staged paths.
- Runtime config sanitization handles staged PyTC configs.

Why it matters:

- Case-study training should use all eligible reference volumes, not one currently selected image.
- The paper needs the agent to coordinate stateful training selection from progress/memory.

Key files:

- `server_api/workflows/router.py`
- `server_api/workflows/service.py`
- `client/src/views/ModelTraining.js`
- `tests/test_workflow_routes.py`
- `tests/test_pytc_runtime_routes.py`

## Visualization And Neuroglancer

Visualization was hardened for agent-populated actions and demo deployment.

What changed:

- Fixed mixed-content and public Neuroglancer URL handling for `demo.seg.bio`.
- Added runtime config for Neuroglancer bind port and public base.
- Improved viewer URL generation so public URLs use `https://demo.seg.bio/neuroglancer/...`.
- Added volume pair discovery and viewer metadata into workflow state.
- Added smoke tests that verify viewer URL generation and pair discovery.
- Added operator diagnostics to verify Neuroglancer port reachability and URL prefix.

Why it matters:

- The agent-triggered "Run in app" viewer path had been failing differently from manual usage.
- Demo deployment needs public URLs, not local/insecure iframe URLs.

Key files:

- `server_api/main.py`
- `server_api/workflows/volume_pairs.py`
- `scripts/inspect_demo_instance.py`
- `scripts/run_yixiao_case_study_smoke.py`

## Proofreading

The proofreading view and path handling were audited and hardened.

What changed:

- Added helper utilities for proofreading image/mask paths.
- Added tests around proofreading path behavior.
- Kept proofreading as a workflow stage that can be proposed by the agent.
- Added progress integration so draft masks can be treated as proofreading targets rather than trusted ground truth.
- Added UI and docs around using proofread edits for training.

Why it matters:

- The case-study story depends on moving from draft segmentations to accepted training references.
- Draft masks must not silently enter the training set.

Key files:

- `client/src/views/ehtool/proofreadingPaths.js`
- `client/src/views/ehtool/DatasetLoader.js`
- `client/src/views/ehtool/DetectionWorkflow.js`
- `server_api/workflows/router.py`

## Runtime Logging And Demo Operations

Logging and operator diagnostics were expanded substantially.

What changed:

- Added detailed app event logging.
- Added runtime startup config event with API host/port, worker URL, Neuroglancer port, and public Neuroglancer base.
- Added worker proxy logging for PyTC worker requests.
- Added `scripts/manage_demo_instance.py` to start/stop/restart/status the demo API process.
- Added `scripts/inspect_demo_instance.py` to inspect:
  - API health.
  - app log path.
  - runtime config.
  - worker reachability.
  - `/training_status`.
  - worker proxy target.
  - current workflow.
  - Neuroglancer port and public URL.
  - recent app error events.
  - app log and workflow bundle disk usage.
- Fixed a false runtime-config warning by making the inspector scan enough app log history.
- Added the missing `neuroglancer_public_base` field to startup runtime logging.

Why it matters:

- When the demo fails, we need to see whether it is the API, PyTC worker, Neuroglancer, Ollama, or workflow state.
- The operator scripts make the deployed instance auditable by future agents.

Key files:

- `scripts/manage_demo_instance.py`
- `scripts/inspect_demo_instance.py`
- `server_api/main.py`
- `tests/test_manage_demo_instance.py`
- `tests/test_inspect_demo_instance.py`

## Evidence And Provenance Export

Evidence export was expanded into a more paper-appropriate provenance layer.

What changed:

- Added richer workflow bundle export metadata.
- Added artifact path metadata and copy-policy handling.
- Added structured evidence export sections:
  - project memory summary.
  - model context.
  - agent proposal to approval links.
  - proposal/approval/action/run/progress graph.
  - user status changes.
  - command and run lineage.
  - withheld reference handling.
- Added documentation for evidence export structure.

Why it matters:

- The strongest TOCHI-style systems contribution is not just "the agent answered"; it is that every meaningful workflow action leaves a reproducible trail.
- Paper figures and case studies need exportable evidence of what was used and what changed.

Key files:

- `server_api/workflows/bundle_export.py`
- `server_api/workflows/evidence_export.py`
- `docs/research/workflow-evidence-export.md`
- `tests/test_workflow_export_bundle.py`
- `tests/test_workflow_evidence_export.py`

## User Management Foundations

A foundation for user/project management was added.

What changed:

- Expanded backend auth models and routes.
- Added more substantial user/session/project-management surfaces in the backend.

Why it matters:

- Production use will need ownership, project mounting state, permissions, and audit attribution.
- The evidence ledger needs actor identity over time.

Key files:

- `server_api/auth/models.py`
- `server_api/auth/router.py`

## Yixiao TapeReader/XRI Case Study

A case-study fixture was assembled around the Yixiao TapeReader/XRI dataset.

What changed:

- Located and prepared the XRI project currently relevant to the demo.
- Added project context for the TapeReader / CytoTape workflow.
- Added manifest-driven status split:
  - 10 tracked volumes.
  - 6 confirmed ground-truth volumes.
  - 2 draft masks needing proofreading.
  - 2 image-only inference targets.
- Added app-compatible PyTC config path:
  - `configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`
- Added smoke tests that mount the project, inspect context, stage workflow state, verify progress, open viewer metadata, query the agent, stage training, validate training subsets, and test export sanity.
- Added manual demo guide.

Why it matters:

- This is the first concrete case study path for the paper prototype.
- It exercises the actual mixed workflow: inspect, visualize, understand progress, stage training, avoid untrusted labels, and prepare downstream inference/proofreading.

Key files:

- `scripts/run_yixiao_case_study_smoke.py`
- `tests/test_yixiao_pre_demo_smoke.py`
- `docs/manual-yixiao-case-study-demo.md`

## Browser And Smoke Testing

The smoke testing system was expanded beyond unit tests.

What changed:

- Added deterministic Yixiao case-study gate.
- Added browser smoke harness with Playwright detection.
- Added tests for the browser smoke script itself.
- Added checks for proposal card editability.
- Added pre-demo gate modes:
  - normal smoke.
  - promotion roundtrip.
  - restore state.
  - readiness check.
  - export sanity.

Why it matters:

- The app is now complex enough that endpoint tests alone are not sufficient.
- Case-study readiness depends on complete flows, not isolated functions.

Key files:

- `scripts/browser_yixiao_case_study_smoke.py`
- `scripts/run_yixiao_case_study_smoke.py`
- `tests/test_browser_yixiao_case_study_smoke.py`
- `tests/test_yixiao_pre_demo_smoke.py`

## Research And Paper Planning

Several internal research and planning reports were added.

Important docs include:

- `docs/codex-working-memory/paper-readiness-production-plan.md`
- `docs/codex-working-memory/third-finish-line-lit-and-task-taxonomy.md`
- `docs/codex-working-memory/yixiao-finish-line-task-taxonomy.md`
- `docs/research/agentic-workflow-formalization-report.md`
- `docs/research/internal-technical-audit-2026-05-24.md`
- `docs/research/deep-research-engineering-synthesis-2026-05-24.md`
- `docs/research/deep-research-agentic-workflow-formalization-2026-05-27.md`
- `docs/research/deep-research-agentic-bioimage-segmentation.md`

Core paper-facing framing:

- This should be presented as a mixed-initiative workflow agent for iterative biomedical volume segmentation.
- The central contribution is workflow coordination, not a new segmentation model.
- The strongest system abstractions are:
  - canonical project memory.
  - composite volume state.
  - typed action proposals.
  - risk-graded approval.
  - bounded execution.
  - evidence/provenance ledger.
  - progressive disclosure of operational traces.

## Literature-Informed Design Direction

The latest heuristic pass incorporated recent HCI/VIS/agent work around common ground, agentic visualization, feedback, and collaboration limits.

The resulting design takeaways were:

- Build explicit common ground between user and agent.
- Do not make chat history the source of truth.
- Make the current workflow state visible and queryable.
- Use action cards for consequential actions.
- Keep user-facing language conversational and short.
- Put mechanical details in expandable traces.
- Treat user corrections as durable project-memory events.
- Make provenance export part of the workflow, not an afterthought.

## Verification Completed

The following verification was run after the third finish-line implementation pass:

```text
.venv/bin/python -m py_compile scripts/browser_yixiao_case_study_smoke.py scripts/manage_demo_instance.py scripts/inspect_demo_instance.py server_api/workflows/bundle_export.py server_api/workflows/evidence_export.py server_api/workflows/router.py server_api/workflows/service.py
```

Backend/test slices:

```text
.venv/bin/python -m pytest -q tests/test_browser_yixiao_case_study_smoke.py tests/test_manage_demo_instance.py tests/test_inspect_demo_instance.py tests/test_workflow_export_bundle.py tests/test_workflow_evidence_export.py tests/test_workflow_routes.py tests/test_yixiao_pre_demo_smoke.py tests/test_workflow_case_study_acceptance.py
```

Result:

```text
97 passed, 12 warnings
```

Frontend test slice:

```text
CI=true npm --prefix client test -- --runInBand --watchAll=false --runTestsByPath src/views/FilesManager.test.js src/components/Chatbot.test.js src/components/WorkflowTimeline.test.js src/components/chat/AgentProposalCard.test.js src/__tests__/agentProposalCards.test.js src/contexts/WorkflowContext.test.js
```

Result:

```text
69 passed
```

Build:

```text
npm --prefix client run build
```

Result:

```text
passed
```

Known remaining frontend build warnings are pre-existing warnings in older EHTool files:

- `src/views/ehtool/DetectionWorkflow.js`
- `src/views/ehtool/ProofreadingEditor.js`

Whitespace check:

```text
git diff --check
```

Result:

```text
passed
```

## Demo Deployment State

The demo API was restarted and verified on port `4342`.

Runtime config:

```text
api_port=4342
worker_url=localhost:4243
neuroglancer_port=4244
neuroglancer_public_base=https://demo.seg.bio/neuroglancer
```

Final live checks passed:

- API `/health`.
- Runtime config log comparison.
- Worker `hello`.
- API `/training_status`.
- Worker proxy URL alignment.
- Current workflow endpoint.
- Neuroglancer port reachability.
- Public Neuroglancer URL prefix.
- Recent app error scan.

Final warmed workflow:

```text
workflow_id=195
title=Yixiao TapeReader XRI Case Study
stage=visualization
```

Final Yixiao viewer URL prefix:

```text
https://demo.seg.bio/neuroglancer/
```

The Yixiao smoke pass reported:

```text
Yixiao case-study smoke passed.
Workflow: 195
```

The Yixiao pre-demo gate passed:

```text
normal_smoke: pass
promotion_roundtrip: pass
restore_state: pass
readiness_check: pass
export_sanity: pass
```

## Remaining Known Gaps

The prototype is much stronger, but not production-complete.

Known gaps:

- Playwright is not installed in the current environment, so the browser smoke script is present and tested structurally, but full browser automation was not run locally.
- Real GPU training/inference/evaluation still needs end-to-end live validation for paper performance claims.
- The evidence/provenance payload is much richer, but the schema is not yet fully typed or migration-backed as a stable public contract.
- User management exists as a foundation, not a polished multi-user product.
- The current Yixiao case-study config is app-compatible and sanity-oriented; paper-faithful TapeReader parity still needs explicit confirmation against the original pipeline.
- The proofreading UI is useful for the prototype but not yet a full production-grade annotation/proofreading system.
- The app still has older EHTool build warnings that should be cleaned before a polished release.
- There is an untracked local file, `demo-proofread-3d.png`, which was not committed because it is not referenced by the app.

## Recommended Next Steps

1. Run the Yixiao case study manually from the demo link and record where the user feels friction.
2. Validate one real training run from the staged ground-truth subset.
3. Validate one inference run on the image-only targets.
4. Decide whether draft masks `5_1` and `5_2` should be real proofreading targets or treated as simulated placeholders.
5. Tighten the evidence export into a formal schema for the paper.
6. Make the agent response style less mechanical in a few remaining fallback cases.
7. Install Playwright and run the browser smoke harness against the deployed demo.
8. Clean the remaining EHTool warnings.
9. Decide the third case study fixture and implement its task-family preset.
10. Write the paper methods section around the actual system architecture:
    - project inspector.
    - workflow memory.
    - progress/volume state.
    - action proposal cards.
    - approval-gated execution.
    - evidence ledger.

## Current Git State At Report Time

Branch:

```text
checkpoint/tochi-agentic-prototype
```

Remote:

```text
origin/checkpoint/tochi-agentic-prototype
```

Current head:

```text
a047f34 docs(research): capture paper prototype roadmap
```

Untracked local artifact:

```text
demo-proofread-3d.png
```

This file was intentionally not included in the pushed commits because no repository file references it.
