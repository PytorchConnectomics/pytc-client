# Deep Research Engineering Synthesis

Date: 2026-05-24

Source: user-provided deep research report, "Designing Human-Agent Collaboration for Iterative Biomedical Image Segmentation."

This note translates the research output into engineering and product choices for the current PyTC Client / seg.bio prototype. It is intentionally implementation-facing: what to build, what to simplify, and what claims the app should support.

## Core Interpretation

The strongest product direction is not "chatbot next to PyTC." It is a workflow-aware coordination layer for iterative biomedical segmentation. The assistant should help users move through inspection, visualization, proofreading, training, inference, and evaluation while keeping project state and artifact provenance legible.

The research strongly reinforces several issues already found in the local technical audit:

- project context needs to be structured and continuously refreshed;
- agent actions need one approval-gated execution model;
- visible chat should be natural and short, with details behind "What I checked";
- project onboarding should start with mechanical inspection and guided questions, not a blank prompt;
- volume state should be a core object, not inferred repeatedly from filenames;
- task-family presets matter because semantic masks, instance labels, affinities, proofreading, and evaluation metrics differ across PyTC workflows.

## Product Decisions To Adopt

### 1. Treat Project Memory As The Center

The canonical system object should be a structured project memory, not the chat transcript and not the current form fields.

Minimum schema:

- `project_facts`: modality, target structure, voxel size, task family, dataset family, optimization preference.
- `artifact_index`: raw images, labels, predictions, configs, checkpoints, logs, metrics, screenshots, evidence bundles.
- `volumes`: one row per volume or subvolume with image path, segmentation path, prediction path, status, status source, and provenance.
- `runs`: training, inference, evaluation, proofreading sessions, and their output artifacts.
- `evidence_events`: facts observed, user confirmations, agent suggestions, approvals, failures, and artifact mutations.

Design consequence: the assistant should answer from this memory plus fresh targeted probes, not from stale summaries or unstructured chat history.

### 2. Keep Chat Human, Keep Mechanics Expandable

User-facing assistant responses should read like a normal collaborator:

- short summary first;
- one concrete next move;
- no "Current read / Why this fits / Blocker" boilerplate in normal speech;
- no dumped JSON, config fragments, or internal decision fields in the visible answer.

Mechanical details belong in expandable traces:

- files checked;
- volume counts;
- manifest/config matched;
- exact reason a volume entered a training set;
- runtime/log status;
- warnings and uncertainty.

Design consequence: the agent response object should separate `message`, `trace`, `proposal`, and `state_update`. The renderer should never have to infer which parts are human-facing.

### 3. Use Action Cards As The Only Consequential Execution Path

Every consequential action should use the same lifecycle:

1. observe current project state;
2. propose a bounded app routine;
3. show scope, inputs, outputs, expected cost, and why now;
4. wait for explicit approval when the action mutates artifacts or starts compute;
5. execute through a typed app routine;
6. write events/artifacts back to project memory;
7. update the visible chat with success/failure.

This should replace the current split between ad hoc actions, commands, durable proposals, runtime actions, and client effects.

### 4. Make Per-Volume State First-Class

The progress table should become the canonical user's-eye state of the project:

- `ground_truth`: curated and training-ready;
- `needs_proofreading`: segmentation exists but should not be used as ground truth yet;
- `image_only`: raw image exists, no segmentation/prediction yet;
- `predicted`: model output exists and needs review;
- `ignored`: intentionally out of scope.

Each status needs provenance:

- detected from file naming;
- imported from manifest;
- marked by user;
- produced by inference;
- promoted from proofreading;
- overridden by agent/user.

Design consequence: training/inference/proofreading actions should select volumes from this state table, not re-derive their own private volume sets.

### 5. Guided Onboarding Should Be Inspect-First

The first project flow should be:

1. mount directory;
2. inspect files/configs/checkpoints/metadata;
3. show what was detected;
4. ask two or three concrete questions only when needed;
5. let the user correct individual facts;
6. save context as project memory.

Avoid asking a biologist to start with a blank "describe project" box. Optional notes can remain, but they should not be the main gate.

### 6. Task Families Need Presets

The app should not treat all segmentation as the same. At minimum:

- mitochondria semantic segmentation, e.g. Lucchi++;
- mitochondria instance segmentation, e.g. MitoEM / MitoEM2;
- neuron affinity segmentation, e.g. SNEMI3D;
- synaptic cleft segmentation, e.g. CREMI;
- nuclei instance segmentation, e.g. NucMM.

Each preset should define expected inputs, output heads, proofreading expectations, evaluation metrics, and safe default run settings.

## Near-Term Engineering Backlog

### P0: Fix Agent Intent And Action Reliability

- Keep semantic intent prompt and validation from one source of truth.
- Add tests for prompt-listed intents.
- Replace fragmented action/proposal execution with one `ActionExecution` envelope.
- Ensure approval always produces a visible status update and either a form prefill, started job, or actionable failure.

### P0: Resume, Do Not Reset, Workflow State

- Hydrate the continuous big chat and mounted project state from server workflow records.
- Stop page reloads from creating fresh workflows unless the user explicitly starts a new project.
- Keep browser storage as cache only.

### P1: Build Structured Project Memory

- Promote current `project_context`, `project_observation`, `project_progress_snapshot`, and sidecar artifacts into a normalized project-memory shape.
- Add invalidation rules: re-scan only affected folders/artifacts when files, statuses, or run outputs change.
- Add a "Project memory" inspection panel for debugging and study evidence.

### P1: Make Training Sets Real Artifacts

- Replace directory-of-symlinks training subsets with a PyTC-compatible manifest, combined volume, or explicit supported file list.
- Dry-run the staged config by constructing the dataset before launching expensive training.
- Show selected training volumes and excluded volumes on the approval card and Train Model form.

### P1: Strengthen Proofreading-To-Training Provenance

- Treat proofread masks as versioned artifacts.
- Store which instances/regions were edited.
- Support promotion from prediction/draft to ground truth only through explicit user action.
- Plan for `valid_mask` support so partially annotated regions can become training-ready without pretending the whole volume is complete.

### P2: Evaluation And Evidence Export

- Add evaluation as a real stage: baseline prediction, proofread correction, retraining run, candidate prediction, metrics, evidence bundle.
- Export logs/events/configs/metrics/status transitions as a case-study evidence package.

## UI Streamlining Implications

- Files should focus on mounted project inspection and detected roles, not just a file-browser clone.
- Progress should become the project control surface: row actions for view, proofread, mark ground truth, ignore, train on selected, infer missing.
- Train Model should show training set membership, not just one image path and one label path.
- Run Model should show target volumes and output registration into project progress.
- Proofread should expose "use edits for training" as a status transition with artifact provenance.
- The assistant panel should render one primary proposal card at a time, with an obvious execution state.

## Paper Positioning Notes

The strongest manuscript claim is:

> Iterative biomedical image segmentation is bottlenecked by workflow coordination across inspection, inference, proofreading, retraining, and evaluation. This prototype contributes a workflow-aware, approval-gated human-agent interface that keeps project context visible and helps users move through that loop.

Safe claims:

- integrates fragmented workflow stages;
- keeps per-volume workflow state visible;
- uses approval-gated actions;
- supports closed-loop correction and retraining as an interaction design;
- reduces manual translation between software-specific steps.

Avoid until backed by study data:

- improves segmentation accuracy;
- reduces effort for all bioimage domains;
- safely automates scientific workflows;
- generalizes across all biomedical imaging tasks.

## Immediate Code Change From This Synthesis

The semantic intent prompt/validator mismatch was fixed in the same pass that created this synthesis. This is a small but important example of the larger principle: agent semantics need typed contracts, not duplicated prompt prose and code allowlists.
