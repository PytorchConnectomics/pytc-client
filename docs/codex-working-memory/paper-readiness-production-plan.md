# Paper Readiness And Production System Plan

Last updated: 2026-06-04

This document turns the current product direction into a concrete execution
plan for a paper-ready, production-shaped human-agent system for iterative
biomedical image segmentation.

The goal is not to build a generic biology chatbot. The goal is to build a
workflow-aware system that can coordinate the actual segmentation loop:

`mount project -> inspect context -> confirm volume state -> visualize -> run inference -> proofread -> promote corrections -> train/retrain -> run inference again -> evaluate -> export evidence`

The paper should be ready only when the implemented system can perform that
loop on real data, with durable project state, explicit user control, and
exportable evidence that supports the manuscript claims.

## Core Product Contract

The final system implied by the paper should satisfy this contract:

1. A biologist can mount a project without knowing the app's internal schema.
2. The app inspects the project and presents concrete findings instead of a
   blank prompt.
3. The user can correct or confirm project facts through guided UI controls.
4. Every volume has an explicit workflow state that both the user and agent can
   reference.
5. The assistant can answer from current project state, fresh file probes,
   previous actions, and run evidence.
6. The assistant proposes bounded app routines, not arbitrary hidden actions.
7. Training, inference, proofreading, and evaluation are durable workflow
   records with inputs, outputs, logs, and provenance.
8. Consequential actions are approval-gated.
9. The system can export enough evidence to reproduce the paper's walkthroughs,
   figures, and claims.
10. User-facing language is normal and helpful; mechanical details are available
    through expandable evidence traces.

## Paper Claim Contract

The paper can safely claim the following only if the corresponding gates pass.

| Claim | Required System Evidence | Paper Risk If Missing |
| --- | --- | --- |
| The system maintains project-level workflow context. | Canonical project memory, rescan/update behavior, per-volume state, evidence log. | The assistant looks like a chat panel with stale guesses. |
| The system coordinates fragmented segmentation stages. | End-to-end loop across visualization, inference, proofreading, training, evaluation. | The paper overclaims beyond a prototype GUI. |
| The assistant supports mixed-initiative handoffs. | Action cards with inspect/propose/approve/execute/update lifecycle. | The agent looks passive or unsafe. |
| Users remain in control of expensive or mutating actions. | Approval gates, rejection, interruption, audit trail. | The system is not defensible for scientific workflows. |
| The interface reduces setup ambiguity for biologists. | Guided onboarding with detected facts and concrete questions. | The first-run UX contradicts the HCI argument. |
| The workflow creates reusable evidence. | Bundle export with events, artifacts, configs, metrics, screenshots/links. | Case-study results become anecdotal and hard to verify. |
| The loop supports iterative model improvement. | Before/after inference and metrics from real app-generated artifacts. | The paper must avoid accuracy or improvement claims. |

## Case-Study Readiness Taxonomy

For the Yixiao workflow, the paper-ready surface is split by artifact maturity.

| Claim Surface | Required Artifact Set | Pass Condition |
| --- | --- | --- |
| Workflow coordination claim | project context snapshot, volume-state counts, and bounded proposal/action traces | Proposal + training drill demonstrates context-aware gating with `6/2/2` baseline |
| Review-control claim | explicit proposal approvals and audit trails (`agent.proposal_*` and `agent.plan_*`) | No mutating action appears without recorded approval step |
| Closed-loop claim | training completion record, checkpoint/version, inference record, evaluation result, export bundle | At least one run is reproducible from `WorkflowExport` metadata with model/evaluation links |
| Paper evidence claim | export bundle with manifest-only policy and copied artifact summary | `export-bundle` call returns schema, paths, and copy policy metadata |

This mapping is intentionally strict:

- If only the coordination claim is backed by evidence, frame the case study as a
  coordination demo.
- If training/inference/eval are backed, the manuscript can include improvement
  statements with caveats around target and dataset specificity.

## One-hour Yixiao Acceptance Checklist

These are the practical go/no-go items for a timed demo:

- Baseline project state (`10` volumes, `6/2/2`, context roots, target IDs).
- Agent context stays on the mounted fixture (no MitoEM/Lucchi regressions).
- Training proposal is approval-gated and excludes draft/image-only masks from training.
- Draft mask promotion can move `5_1`/`5_2` to a training-ready state.
- Closed-loop rehearsal can reference held-out ground truth without mounting it as training data.
- Real training/inference/evaluation artifacts exist before claiming model improvement.
- Export bundle call succeeds with manifest/skip policy and required core fields.
- Live health checks (`inspect_demo_instance.py --json`) are healthy enough to launch.

## Definition Of Paper-Ready

The prototype is paper-ready when all P0 gates pass and at least one full case
study can be run without manual developer intervention.

### P0 Gates

- A fresh mounted project can be inspected, confirmed, and represented in
  canonical project memory.
- The Progress page accurately represents every volume state.
- The assistant can explain the current project, current blockers, and next
  useful action from project memory.
- The assistant can propose visualization, inference, proofreading, training,
  and evaluation actions using the same action-card contract.
- Training on multiple selected ground-truth volumes works through app-created
  artifacts, not fragile directory guessing.
- Inference over image-only or draft volumes works and registers predictions.
- Proofreading saves durable corrected masks and updates volume status.
- Evaluation computes at least one relevant before/after metric for the main
  case study.
- Every run, artifact, status transition, and approval is exportable.
- A reset script can return the demo dataset to its initial study state.

### P1 Gates

- Region-level proofreading state and `valid_mask` style partial supervision.
- Multiple task-family presets beyond the primary case study.
- More robust data backends such as OME-Zarr, OMERO, or Neuroglancer
  precomputed.
- Scheduler-aware long-running training and inference jobs.
- Stronger multi-user authorization and deployment hardening.

## Case Study Placeholders

The paper should use three case studies that build the argument in layers.

### Case Study 1: Guided Project Intake And Inspection

Purpose:

- Demonstrate that a biologist can mount a project and get a useful,
  inspect-first onboarding flow without knowing what metadata the agent needs.

Dataset placeholder:

- `CASE_STUDY_1_DATASET`: likely Lucchi++ or a small MitoEM/MitoEM2 subset.

Participant/task placeholder:

- `CASE_STUDY_1_TASK`: mount the project, confirm detected images/masks,
  correct voxel size or target structure, visualize one pair, and inspect the
  project progress state.

Required product capabilities:

- Guided onboarding wizard.
- Project profiler and file role detector.
- Editable project facts.
- Per-volume status creation.
- Progress page with accurate counts.
- Conversational assistant answer to "what am I looking at?"

Evidence to export:

- Initial project scan.
- User corrections.
- Confirmed project memory snapshot.
- Volume table.
- Visualization action event.
- Chat response plus "What I checked" trace.

Success criteria:

- User does not need to type a free-form project description to get started.
- The system identifies at least one valid image/mask pair or explains exactly
  what is missing.
- The final project memory matches the ground-truth setup for the fixture.

Paper contribution supported:

- Guided intent elicitation for domain experts who know their data but not the
  software schema.

### Case Study 2: Agent-Guided Proofreading And Data Curation

Purpose:

- Demonstrate that the system can coordinate the human correction loop and
  maintain training readiness state.

Dataset placeholder:

- `CASE_STUDY_2_DATASET`: MitoEM2 progress demo with a mix of ground-truth,
  draft segmentation, and image-only volumes.

Participant/task placeholder:

- `CASE_STUDY_2_TASK`: inspect draft segmentations, proofread selected masks,
  promote corrected masks to ground truth, and decide which volumes are ready
  for training.

Required product capabilities:

- Progress statuses: `ground_truth`, `needs_proofreading`, `image_only`,
  `ignored`.
- Row-level actions: view, proofread, mark as ground truth, mark as draft,
  ignore.
- Proofreading editor persistence.
- Correction artifact registration.
- Assistant awareness of which volumes are training-ready.

Evidence to export:

- Pre-proofreading volume status table.
- Proofreading session events.
- Correction artifacts.
- Status transitions.
- Assistant recommendation before and after corrections.
- Screenshots or reproducible viewer links.

Success criteria:

- Corrected masks are saved as real files.
- The corresponding volume status changes are durable.
- The agent correctly excludes draft/unproofread masks from training unless the
  user explicitly overrides.

Paper contribution supported:

- Workflow-aware coordination between human correction and model retraining.

### Case Study 3: Closed-Loop Training, Inference, And Evaluation

Purpose:

- Demonstrate the complete iterative loop from curated ground truth to model
  run to new predictions to evaluation.

Dataset placeholder:

- `CASE_STUDY_3_DATASET`: primary MitoEM or MitoEM2 subset with at least:
  - two ground-truth volumes;
  - two draft segmentation volumes;
  - two image-only target volumes;
  - a reset script and frozen initial snapshot.

Participant/task placeholder:

- `CASE_STUDY_3_TASK`: train on approved ground-truth volumes, run inference on
  image-only volumes, proofread or inspect predictions, then compare outputs.

Required product capabilities:

- Multi-volume training subset creation.
- PyTC-compatible staged training manifest/config.
- Training run launch, log capture, TensorBoard link, checkpoint registration.
- Inference run launch from selected checkpoint.
- Prediction registration as draft segmentation.
- Evaluation metrics against held-out or revealed labels.
- Evidence bundle export.

Evidence to export:

- Training action card and approval.
- Staged dataset manifest.
- Runtime config.
- Training logs.
- Checkpoint/model version record.
- Inference action card and approval.
- Prediction artifacts.
- Evaluation results.
- Before/after project state snapshot.

Success criteria:

- The run can be reproduced from exported config, artifacts, and project memory.
- The agent can explain what was trained on, what was left out, and why.
- Evaluation results are attached to the relevant volumes and model runs.

Paper contribution supported:

- Approval-gated human-agent orchestration of a full closed-loop biomedical
  segmentation workflow.

## Workstream 1: Canonical Project Memory

### Objective

Replace scattered inference, browser state, and sidecar assumptions with one
canonical project memory model that all UI surfaces and agent routines use.

### Concrete Action Items

- Define `ProjectMemory` schema:
  - `project_id`
  - `root_path`
  - `dataset_name`
  - `task_family`
  - `modality`
  - `target_structure`
  - `voxel_size_zyx_nm`
  - `confidence_by_field`
  - `source_evidence_by_field`
  - `volume_ids`
  - `artifact_ids`
  - `run_ids`
  - `created_at`
  - `updated_at`
- Define `VolumeState` schema:
  - `volume_id`
  - `display_name`
  - `image_path`
  - `label_path`
  - `prediction_path`
  - `status`
  - `status_source`
  - `status_confidence`
  - `last_reviewed_at`
  - `eligible_for_training`
  - `eligible_for_inference`
  - `notes`
- Define allowed volume statuses:
  - `image_only`
  - `draft_segmentation`
  - `needs_proofreading`
  - `ground_truth`
  - `ignored`
  - `invalid`
- Define `Artifact` schema:
  - raw image
  - label
  - prediction
  - corrected mask
  - config
  - checkpoint
  - metric report
  - screenshot or viewer state
  - evidence bundle
- Define `ProjectEvent` schema:
  - actor
  - event type
  - timestamp
  - affected volumes
  - affected artifacts
  - previous state
  - next state
  - evidence payload
- Implement server APIs:
  - `GET /users/me/projects` for user-scoped mounted project inventory.
  - `GET /api/workflows/{workflow_id}/volumes` for canonical workflow volume
    state, refreshed from the mounted project when requested.
  - `PATCH /api/workflows/{workflow_id}/volumes` for manual volume-state
    corrections, training/inference eligibility, and path updates.
  - `GET /api/workflows/{workflow_id}/export-bundle` for evidence, events,
    artifacts, and volume state.
  - Future project-memory endpoints can still be layered over this as
    `/api/projects/{id}/memory`, `/api/projects/{id}/rescan`, and
    `/api/projects/{id}/events` once project identity is separated from the
    current workflow session model.
- Move Progress page to read from project memory, not ad hoc derived values.
- Move assistant context builder to project memory plus recent events.
- Add migration/import path from existing `.pytc_project_context.json` and
  `project_manifest.json` into the canonical schema.

### Verification Gates

- Unit tests validate status transitions.
- API tests create, update, rescan, and export project memory.
- Reloading the app preserves project memory exactly.
- Rescanning a project adds newly discovered files without overwriting
  user-confirmed facts.
- Deleting or moving a file marks affected artifacts stale instead of silently
  pretending they still work.

### Paper Readiness Evidence

- Exported project memory snapshot before and after each case-study session.
- Event log showing detected facts, user corrections, and volume state changes.
- Figure-ready Progress page state generated from canonical memory.

## Workstream 2: Guided Onboarding And Context Elicitation

### Objective

Replace the blank context box with an inspect-first onboarding flow that guides
biologists through concrete confirmations.

### Concrete Action Items

- Run project scan immediately after mount.
- Present a wizard with detected facts:
  - likely image files;
  - likely mask/segmentation files;
  - likely configs;
  - likely checkpoints;
  - likely voxel size;
  - likely task family;
  - ambiguous or missing fields.
- Add editable fields:
  - target structure;
  - imaging modality;
  - voxel size;
  - label semantics: ground truth, draft prediction, unknown;
  - priority: speed, accuracy, balanced;
  - task family preset.
- Replace free-form prompt as primary input with:
  - confirmation chips;
  - dropdowns;
  - "not sure" choices;
  - small examples;
  - optional note field.
- Ask one concrete follow-up question at a time when a required field is
  missing.
- Add "Use detected defaults" only when defaults are visible and editable.
- Add "Show evidence" for each inferred fact.
- Save every user confirmation or correction as a project event.

### Verification Gates

- A user can mount a known fixture and complete onboarding without typing a
  paragraph.
- The wizard identifies known fixture image/mask pairs correctly.
- Unknown fields remain marked as unknown rather than fabricated.
- User corrections are reflected in project memory and future agent responses.
- Onboarding can be reopened to edit context later.

### Paper Readiness Evidence

- Screenshot sequence of guided onboarding.
- Exported evidence showing auto-detected facts and user corrections.
- Case-study notes showing reduced blank-prompt burden.

## Workstream 3: Progress Page As Shared Source Of Truth

### Objective

Make Progress the user and agent's common map of the project.

### Concrete Action Items

- Rebuild Progress from `VolumeState`.
- Show summary cards:
  - total volumes;
  - ground truth;
  - needs proofreading;
  - draft segmentation;
  - image-only;
  - ignored;
  - stale/broken artifacts.
- Add per-row actions:
  - view image;
  - view image plus label;
  - proofread;
  - mark ground truth;
  - mark draft;
  - run inference;
  - include in training;
  - exclude/ignore;
  - inspect provenance.
- Add bulk actions:
  - train on selected ground-truth volumes;
  - run inference on selected image-only volumes;
  - mark selected as ignored;
  - export selected manifest.
- Add "Why this status?" provenance popover.
- Add filters by status, split, source folder, task family, and stale state.
- Add validation warnings for duplicate rows, missing labels, duplicate masks,
  and impossible statuses.

### Verification Gates

- Progress counts match project memory after mount, reload, proofread save,
  inference completion, and training completion.
- Duplicate volumes are detected and surfaced.
- Agent recommendations cite the same volume counts shown in Progress.
- Bulk training selection excludes non-ground-truth volumes by default.

### Paper Readiness Evidence

- Progress screenshots before and after each case-study action.
- Exported volume-state CSV/JSON.
- Event log of status transitions.

## Workstream 4: Unified Action Cards And Execution Envelope

### Objective

Make every agent-proposed action understandable, reviewable, executable, and
auditable through one contract.

### Concrete Action Items

- Define `ActionProposal` schema:
  - `proposal_id`
  - `routine`
  - `title`
  - `plain_language_summary`
  - `why_now`
  - `inputs`
  - `affected_volumes`
  - `expected_outputs`
  - `estimated_cost`
  - `risk_level`
  - `requires_approval`
  - `approval_state`
  - `created_from_evidence`
  - `created_at`
- Define allowed routines:
  - `open_progress`
  - `view_volume`
  - `proofread_volume`
  - `mark_volume_status`
  - `stage_training_set`
  - `start_training`
  - `run_inference`
  - `compute_evaluation`
  - `export_evidence`
  - `rescan_project`
- Replace fragmented client effects, commands, and proposal payloads with this
  envelope.
- Render all cards with the same visual anatomy:
  - title;
  - short summary;
  - affected volumes;
  - expected output;
  - approve/reject or run/open button;
  - expandable details.
- Store proposal, approval, execution start, execution completion, execution
  failure, and artifact registration as events.
- Add retry, cancel, and failure explanation states.

### Verification Gates

- All mutating or expensive routines require explicit approval.
- Approving a card updates the corresponding app UI and creates durable events.
- Rejecting a card leaves project state unchanged and records rejection.
- Refresh/reload does not lose pending cards.
- Tests cover each routine's happy path and failure path.

### Paper Readiness Evidence

- Action-card screenshots.
- Approval/rejection event log.
- Exported routine inputs and outputs for each case study.

## Workstream 5: Workflow Agent Behavior

### Objective

Make the assistant useful as a workflow partner while keeping the visible chat
human and concise.

### Concrete Action Items

- Separate internal trace from visible response:
  - visible response: short, conversational, next-step oriented;
  - trace: files checked, volume states read, configs inspected, blockers.
- Add project tools:
  - inspect project memory;
  - inspect files;
  - inspect HDF5/TIFF/Zarr metadata;
  - inspect run history;
  - inspect progress statuses;
  - inspect checkpoints/configs;
  - inspect logs and metrics.
- Make the default response shape:
  - direct answer;
  - one suggested next move;
  - optional action card if there is a concrete app routine.
- Add clarification behavior:
  - ask concrete questions only when required facts are missing;
  - avoid asking the user to restate facts already in project memory.
- Add conversational tone tests for canned/fallback paths.
- Add regression tests for common user intents:
  - "what am I looking at?"
  - "train on the good ones"
  - "segment the rest"
  - "show me what changed"
  - "why is this volume not training-ready?"
  - "what failed?"

### Verification Gates

- General conceptual questions do not get hijacked by workflow routing.
- Workflow questions cite current project memory accurately.
- Agent does not hallucinate missing files or ground-truth state.
- Agent proposes action cards only when a bounded routine exists.
- User-facing text does not expose raw JSON, internal planner language, or
  chain-of-thought style narration.

### Paper Readiness Evidence

- Chat transcripts with expandable evidence traces.
- Intent-routing test results.
- Case-study examples showing agent handoff support.

## Workstream 6: Multi-Volume Training

### Objective

Make training a real multi-volume project operation driven by volume statuses.

### Concrete Action Items

- Add Training Set artifact:
  - `training_set_id`
  - included volumes;
  - excluded volumes;
  - exclusion reasons;
  - staged image paths;
  - staged label paths;
  - generated manifest;
  - source project memory version.
- Default included volumes to `ground_truth`.
- Default excluded volumes:
  - `image_only`;
  - `draft_segmentation`;
  - `needs_proofreading`;
  - `ignored`;
  - stale or invalid artifacts.
- Add UI to review training set before launch.
- Generate PyTC-compatible config/manifest for multiple volumes.
- Run a dry-run loader validation before training starts.
- Populate Train Model UI fields from the approved proposal.
- Register training run:
  - config origin;
  - staged config path;
  - training set artifact;
  - output path;
  - log path;
  - TensorBoard URL;
  - process ID;
  - terminal status;
  - checkpoint path.
- Avoid unloading the LLM unless resource policy says it is necessary.

### Verification Gates

- Training cannot start with an image directory path that PyTC treats as an
  unrecognized file.
- Training set dry-run catches missing labels, bad HDF5 keys, incompatible
  shapes, and unreadable files.
- Approving a training card visibly populates Train Model fields.
- Completed training registers a model version/checkpoint.
- Failed training surfaces the actual error and suggested repair.

### Paper Readiness Evidence

- Training action card.
- Training set manifest.
- Runtime config.
- Training logs.
- Model version/checkpoint record.

## Workstream 7: Inference And Prediction Registration

### Objective

Make inference produce project-aware draft segmentations that feed Progress and
Proofread.

### Concrete Action Items

- Add Inference Run artifact:
  - checkpoint/model version;
  - target volumes;
  - config;
  - output paths;
  - run status;
  - logs;
  - metrics if available.
- Let agent propose inference on:
  - `image_only` volumes;
  - selected held-out volumes;
  - volumes with stale predictions;
  - post-training comparison targets.
- Require checkpoint selection before launch.
- Register predictions as `draft_segmentation`.
- Attach prediction path to each affected volume.
- Provide "Open prediction" and "Proofread next" actions after completion.
- Handle inference failures per volume where possible.

### Verification Gates

- Inference on multiple target volumes creates one registered prediction per
  volume.
- Progress counts update automatically after inference.
- Viewer and proofreader can open app-generated predictions.
- Failed inference does not mark volumes as predicted.

### Paper Readiness Evidence

- Inference proposal, approval, run logs, prediction artifacts, and status
  updates.

## Workstream 8: Proofreading And Correction Promotion

### Objective

Make human edits durable, inspectable, and reusable for training.

### Concrete Action Items

- Load proofreader from selected volume state.
- Support draft segmentation and ground-truth mask inspection.
- Save corrected masks as artifacts.
- Create Correction Set records:
  - corrected mask path;
  - source image;
  - source prediction/mask;
  - edit summary;
  - actor;
  - timestamp;
  - eligible for training flag.
- Add "Use edits for training" state transition.
- Add "Still needs review" state transition.
- Record edit provenance and status changes.
- Add optional region-level status design for future `valid_mask` support.

### Verification Gates

- Saved edits survive reload and remount.
- Promoting corrections changes the corresponding volume status.
- Training selection sees promoted corrections as eligible ground truth.
- The system can explain which masks are original labels vs proofread edits.

### Paper Readiness Evidence

- Before/after correction artifacts.
- Proofreading session event log.
- Correction Set export.

## Workstream 9: Evaluation And Comparison

### Objective

Provide enough quantitative evidence to support closed-loop workflow claims
without overclaiming algorithmic novelty.

### Concrete Action Items

- Define evaluation tasks by task family:
  - semantic masks: Dice, IoU, precision, recall;
  - instance masks: adapted Rand, variation of information, object counts;
  - affinity workflows: decoder-specific metrics where supported.
- Add Evaluation Result artifact:
  - prediction path;
  - reference path;
  - metric names;
  - metric values;
  - config;
  - run status.
- Add compare UI:
  - baseline prediction;
  - candidate prediction;
  - reference label;
  - metric delta.
- Let agent propose evaluation when required artifacts exist.
- Make missing-reference cases explicit.

### Verification Gates

- Evaluation refuses incompatible shapes or missing references with a clear
  error.
- Evaluation outputs are attached to model runs and volumes.
- Before/after comparison can be regenerated from exported evidence.

### Paper Readiness Evidence

- Metrics table.
- Before/after figure.
- Exported evaluation JSON.

## Workstream 10: Evidence Export And Reproducibility

### Objective

Make every paper claim traceable to exported system evidence.

### Concrete Action Items

- Expand evidence bundle to include:
  - project memory snapshots;
  - volume state table;
  - action proposals;
  - approvals/rejections;
  - run configs;
  - logs;
  - model versions;
  - prediction artifacts;
  - correction sets;
  - evaluation results;
  - app version/commit;
  - environment metadata;
  - viewer states or screenshots where possible.
- Add one-click export from a researcher-visible location.
- Add script to validate an exported bundle.
- Add script to regenerate paper figures/tables from bundle data.
- Add reset script for every case-study fixture.

### Verification Gates

- Bundle validator passes for all three case studies.
- A fresh checkout can inspect the bundle without database access.
- Paper figures and tables can be regenerated from bundle content.
- Reset script restores fixture to initial snapshot exactly.

### Paper Readiness Evidence

- Bundle file path and validation report for every case-study run.

## Workstream 11: Production Hardening

### Objective

Remove prototype fragility that would undermine the case studies or demo.

### Concrete Action Items

- Add health checks for:
  - API;
  - frontend bundle;
  - PyTC worker;
  - Ollama/model server;
  - Neuroglancer assets;
  - TensorBoard;
  - filesystem access;
  - GPU availability if required.
- Add structured logs for:
  - route calls;
  - agent decisions;
  - file scans;
  - status transitions;
  - run lifecycle;
  - frontend action execution.
- Add user-visible failure messages for:
  - missing files;
  - unsupported volume formats;
  - bad HDF5 keys;
  - bad YAML config;
  - missing checkpoint;
  - shape mismatch;
  - training process failure;
  - mixed-content or asset loading failure.
- Add end-to-end smoke tests for the golden path.
- Add deployment checklist for `demo.seg.bio`.
- Add rollback/reset steps.
- Add database migration strategy before multi-user use.

### Verification Gates

- Golden-path smoke passes on demo fixture.
- Error-path tests produce useful user-facing messages.
- Demo can be reset and rerun without manual cleanup.
- Logs are sufficient to diagnose every known failure mode from previous
  sessions.

### Paper Readiness Evidence

- Smoke-test logs.
- Demo reset logs.
- Known-failure recovery examples.

## Workstream 12: Manuscript Alignment

### Objective

Keep the manuscript synchronized with what the artifact can actually do.

### Concrete Action Items

- Maintain a claim-to-evidence table.
- Remove future-tense language for implemented features.
- Mark unimplemented ideas as future work.
- Frame contribution around:
  - workflow coordination;
  - project memory;
  - guided intent elicitation;
  - approval-gated action proposals;
  - evidence-bearing closed-loop segmentation.
- Avoid unsupported claims:
  - broad bioimage generalization;
  - autonomous science;
  - guaranteed accuracy improvements;
  - safety beyond bounded routines.
- Prepare paper figures:
  - system architecture;
  - project memory model;
  - onboarding flow;
  - Progress page;
  - action card lifecycle;
  - closed-loop case-study timeline;
  - before/after evaluation.
- Prepare methods appendix:
  - datasets;
  - system implementation;
  - agent routines;
  - logging/evidence export;
  - case-study protocol;
  - limitations.

### Verification Gates

- Every central claim has an exported artifact, screenshot, event log, or study
  observation attached.
- Every paper figure can be regenerated or traced to a specific fixture and
  app version.
- Limitations explicitly cover missing P1 features.
- The manuscript does not imply the agent can do filesystem or workflow actions
  that are not implemented.

## Suggested Milestone Order

### Milestone A: State Foundation

Exit criteria:

- Canonical project memory exists.
- Guided onboarding writes to it.
- Progress reads from it.
- Agent reads from it.

Paper value:

- Supports the core claim that the system maintains workflow context.

### Milestone B: Action Foundation

Exit criteria:

- Unified action cards exist.
- Proposal/approval/execution events are durable.
- Visualization, progress, and status changes use the same action envelope.

Paper value:

- Supports the mixed-initiative and approval-gated control argument.

### Milestone C: Curation Loop

Exit criteria:

- Draft segmentation can be proofread.
- Corrected masks are saved.
- Status promotion affects training eligibility.

Paper value:

- Supports human correction as part of the model workflow, not an isolated UI.

### Milestone D: Model Loop

Exit criteria:

- Multi-volume training works from selected ground-truth volumes.
- Inference runs on image-only volumes.
- Predictions become draft segmentations.

Paper value:

- Supports the closed-loop segmentation workflow claim.

### Milestone E: Evaluation And Evidence

Exit criteria:

- Before/after evaluation works.
- Evidence bundle validates.
- Three case-study fixtures can be reset and replayed.

Paper value:

- Supports empirical case-study reporting and reproducibility.

### Milestone F: Paper Freeze

Exit criteria:

- All screenshots and figures are regenerated from the frozen app.
- Claim-to-evidence table is complete.
- Case-study placeholders are replaced with real data and observations.
- Unsupported claims are removed or moved to future work.

Paper value:

- Moves from prototype narrative to defensible systems/HCI paper.

## Claim-To-Workstream Matrix

| Paper Claim | Workstreams Required |
| --- | --- |
| The system maintains project context over time. | 1, 2, 3, 5, 10 |
| The system supports biologist-friendly onboarding. | 2, 5, 12 |
| The system enables visible volume-level workflow tracking. | 1, 3, 8, 10 |
| The agent proposes bounded, approval-gated workflow actions. | 4, 5, 11 |
| The system supports closed-loop segmentation. | 6, 7, 8, 9 |
| The system produces reproducible evidence for case studies. | 10, 11, 12 |
| The design is suitable for iterative biomedical segmentation workflows. | All workstreams plus case-study evidence |

## Final Readiness Checklist

Use this before claiming the system is paper-ready.

- [ ] A non-developer can mount each case-study fixture.
- [ ] The app detects useful project facts before asking the user to type.
- [ ] The user can correct every important detected fact.
- [ ] Every volume has a correct state.
- [ ] The agent can explain current project state accurately.
- [ ] The agent can propose the next useful action.
- [ ] Action cards are understandable and auditable.
- [ ] Training works on multiple approved ground-truth volumes.
- [ ] Inference works on selected target volumes.
- [ ] Proofreading saves durable corrections.
- [ ] Corrected masks can become training-ready.
- [ ] Evaluation works where references exist.
- [ ] Evidence bundle export validates.
- [ ] Demo reset restores initial state.
- [ ] Case Study 1 is runnable and documented.
- [ ] Case Study 2 is runnable and documented.
- [ ] Case Study 3 is runnable and documented.
- [ ] Paper figures are regenerated from frozen evidence.
- [ ] Paper claims are mapped to evidence.
- [ ] Unsupported claims are removed or clearly labeled future work.
