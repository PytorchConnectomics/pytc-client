# PyTC Client Research Log

Paper-facing implementation notes for the TOCHI prototype. This file is local-only and outside the Git-tracked repo.

## 2026-04-28 - PyTC Dataset Prepilot Stress Test Plan

### Design Decision

Drafted a solo prepilot plan that uses real PyTorch Connectomics dataset/config families before recruiting case-study participants. The ladder starts with local Mito25, then uses public MitoEM toy crops, Lucchi/Lucchi++, CREMI, SNEMI3D, and NucMM to progressively stress project setup, data role inference, config selection, runtime orchestration, proofreading, correction export, metrics, and evidence bundles.

### Research Rationale

The prototype should fail in private on realistic PyTC data before it is shown in case studies. The selected datasets cover the main PyTC workflow families: mitochondria semantic segmentation, mitochondria instance segmentation, synaptic cleft detection, dense neuron affinity segmentation, and nuclei instance segmentation. This intentionally tests whether the app is project-agnostic or still implicitly shaped around the mito25 demo path.

### User-Control Implication

The prepilot emphasizes explicit confirmation of project roles and approval-gated agent actions. It also checks whether the agent gives workflow-specific next actions rather than exposing PyTC docs or raw config mechanics to a biologist.

### Evidence Captured In Docs

- Added `docs/research/pytc-prepilot-dataset-stress-test.md`.
- The doc includes source grounding, public data links, matching local config paths, a dataset ladder, solo test script, expected failure modes, and a minimum completion bar before external case studies.
- Added and ran `scripts/ingest_prepilot_datasets.py`.
- Staged local prepilot projects under `/Users/adamg/seg.bio/testing_projects`: `prepilot_mito25_smoke`, `prepilot_mitoem_toy`, `prepilot_lucchi_pp`, `prepilot_snemi3d_local`, `prepilot_cremi_official`, and `prepilot_nucmm_mouse`.
- Each staged project has `project_manifest.json`, `notes/README.md`, and `notes/prepilot-log.md`; public sources were downloaded from Hugging Face and CREMI where needed, while existing local data was symlinked.

### Open Paper Question

Decide which two non-mito25 datasets should become paper-demo fixtures. MitoEM toy crop plus Lucchi/CREMI is the most practical pair because they stress project agnosticism without requiring the full MitoEM2.0 or NucMM scale.

## 2026-04-13 - Workflow Spine Milestone

### Design Decision

The prototype now has an explicit workflow spine: `WorkflowSession` stores the current loop state, and `WorkflowEvent` stores chronological evidence of user, agent, and system actions. The first loop target is load data, visualize/infer, proofread, export corrected masks, stage corrected masks for retraining, and preserve the evidence trail.

### Research Rationale

The paper framing argues that biomedical segmentation is not a one-shot inference task. The workflow state model makes the iterative cycle concrete in the system: each step can be inspected, replayed in a timeline, and used by the agent when recommending next actions.

### User-Control Implication

Agent actions are proposal-first. The workflow-aware agent can create a pending proposal, but mutation happens only when the user approves the allowlisted action. The first action is intentionally narrow: `stage_retraining_from_corrections`.

### Evidence Captured In Code/Logs

- `workflow.created` records session creation.
- `viewer.created` records Neuroglancer viewer creation and URL.
- `inference.started`, `inference.completed`, and `inference.failed` record inference transitions.
- `dataset.loaded` and `proofreading.session_loaded` link EHTool sessions to workflow state.
- `proofreading.instance_classified`, `proofreading.mask_saved`, and `proofreading.masks_exported` record proofreading work.
- `agent.proposal_created`, `agent.proposal_approved`, and `agent.proposal_rejected` record mixed-initiative control decisions.
- `retraining.staged` records the corrected mask artifact selected for retraining.

### Open Paper Question

The current milestone stages retraining but does not prove that retraining improves the model. For the paper, this supports the workflow-orchestration claim, but a stronger evaluation needs model-version artifacts and before/after evidence.

## 2026-04-13 - Workflow Timeline And Chat Integration

### Design Decision

The chat drawer now includes a compact workflow timeline. Workflow-related user queries route to `POST /api/workflows/{id}/agent/query`; unrelated chat still uses the existing chatbot path.

### Research Rationale

This keeps the agent grounded in current system state without pretending that every general chat message is an executable workflow instruction.

### User-Control Implication

Pending proposals appear with explicit Approve and Reject controls. Approval returns client effects such as navigation to Model Training and prefilled training label path, but only after the user clicks Approve.

### Evidence Captured In Code/Logs

Frontend tests cover timeline rendering and approve/reject controls. Backend tests cover approval/rejection state transitions and event creation.

### Open Paper Question

The current agent response is deterministic fallback logic. If an LLM-backed planner is added later, the paper should distinguish between agent UX/design contribution and LLM reasoning capability.

## 2026-04-13 - Verification Notes

### Design Decision

Automated verification currently emphasizes API contracts and UI-state wiring rather than a browser-level human proofreading session.

### Research Rationale

The tests prove that evidence is generated for the intended loop transitions, which is directly relevant for later paper claims about inspectable workflow history. They do not yet prove usability or interaction efficiency.

### User-Control Implication

Approval/rejection is covered at both backend and frontend levels. This supports the claim that the prototype uses user-approved agent execution rather than hidden automation.

### Evidence Captured In Code/Logs

- Backend tests pass for workflow current/create/update/events and agent approve/reject.
- Backend EHTool test passes for dataset load, instance classify, mask save, and mask export event logging.
- Frontend tests pass for EHTool re-enable, workflow timeline, approve/reject controls, and approval client effects.
- Production build succeeds with warnings that are mostly existing technical debt.

### Open Paper Question

Before evaluation, add a realistic walkthrough dataset and run a browser-level smoke or study-pilot task that records time/order of actions, agent proposal usefulness, and points of user override.

## 2026-04-13 - LLM Configuration Failure UX

### Design Decision

The AI assistant no longer relies on implicit local or hardcoded remote Ollama defaults. Operators must export `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_EMBED_MODEL` before starting the app. Backend failures are logged and returned as structured LLM-unavailable errors; the frontend prioritizes the user-facing administrative message.

### Research Rationale

For a research prototype, failed agent infrastructure should be explicit rather than mistaken for a failed user action. Making the LLM endpoint an operator-controlled environment variable separates system deployment configuration from the interaction design being evaluated.

### User-Control Implication

Users see that the assistant is unavailable because of system configuration or connectivity, not because their request was invalid. The error text directs them to an administrator while preserving the underlying message needed for diagnosis.

### Evidence Captured In Code/Logs

- Missing `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, or `OLLAMA_EMBED_MODEL` raises a configuration error before chat execution.
- `OLLAMA_BASE_URL` must be a full URL with an explicit port.
- Chat and helper-chat initialization/invocation failures are logged with `[CHATBOT]` prefixes and returned as structured `llm_unavailable` responses.
- Frontend API handling surfaces `detail.user_message` without prefixing it with an HTTP status.

### Open Paper Question

For study deployments, decide whether LLM availability should be preflighted in the UI before sessions begin, so participants do not encounter infrastructure failures during timed workflow tasks.

## 2026-04-13 - Agentic Framing Rewrite For Manuscript Sections 3/4

### Design Decision

Reframed manuscript Sections 3 and 4 so the assistant is modeled as an agentic workflow harness with explicit autonomy modes, rather than as an add-on chat interface.

### Research Rationale

Paper title and contribution claims require an explicit mapping from expert workflow pain points to agent-mediated capabilities. The revised structure now makes that mapping inspectable:
- Section 3 now includes `G6` (agent leverage under human control), `R9` (configurable autonomy envelope), and `T7` (draft bounded multi-step delegation).
- Section 4 now describes implemented and draft agent modes (`M1`/`M2`/`M3`) and ties concrete features to `G/R/T`.

### User-Control Implication

The rewritten framing keeps control boundaries explicit: implemented behavior is approve-then-execute, while project-level autonomy is clearly labeled draft/planned with guardrails and interruption rights.

### Evidence Captured In Code/Logs

- Added a Section 4 feature matrix table (`Feature`, `Status`, `Agentic Function`, `G/R/T` mapping).
- Added explicit draft labeling in manuscript text for non-implemented autonomy features.
- Recompiled manuscript PDF after each text-edit iteration.

### Open Paper Question

Decide whether the final paper should present bounded autonomy as a design implication only, or include an implemented minimal version (`T7`) before submission to support stronger empirical claims.

## 2026-04-13 - Manuscript Status-Language Policy

### Design Decision

Removed explicit implementation-status markers (e.g., "implemented", "draft", "not yet implemented") from manuscript Sections 3 and 4, including the feature mapping table.

### Research Rationale

For paper readability and narrative coherence, the public manuscript now presents a unified system-design view centered on human--agent collaboration patterns, while implementation maturity distinctions are maintained separately in internal project logs.

### User-Control Implication

Control-boundary claims remain explicit in manuscript text (approval gates, bounded autonomy guardrails), but maturity-level tracking moved to internal documentation.

### Evidence Captured In Code/Logs

- Section 4 table schema changed from `Feature | Status | Agentic Function | Mapping` to `Feature | Agentic Function | Mapping`.
- Section 3/4 wording updated to remove direct status qualifiers.
- Internal logs now carry the implementation-vs-ideation distinction.

### Open Paper Question

Before submission freeze, decide whether to reintroduce concise scoping language in a limitations paragraph to avoid over-claim risk while preserving the cleaner narrative flow.

## 2026-04-13 - TOCHI Writing Pattern Synthesis and Manuscript Refactor

### Design Decision

Used a targeted corpus pass over nine recent TOCHI papers to refactor manuscript Sections 3--5 toward a question-driven, traceable, and claims-calibrated narrative structure.

### Research Rationale

The strongest recurring pattern was explicit traceability: empirical observations are translated into goals/requirements/tasks, then mapped to design features and evaluated against explicit questions. We mirrored that pattern by adding:
- formative questions (`FQ1`, `FQ2`) in Section 3,
- a `G -> R -> T` traceability table,
- a structured evaluation protocol (`EQ1`--`EQ3`, measures, analysis plan).

### User-Control Implication

The revised writing keeps control boundaries explicit while avoiding status labels in paper text:
- human approval remains central for mutating agent actions,
- agent orchestration remains bounded by guardrails,
- provenance is treated as a first-class evaluation target.

### Evidence Captured In Code/Logs

- Manuscript edits in `sample-manuscript.tex` covering Sections 3, 4, and 5.
- PDF re-rendered after edits (`sample-manuscript.pdf`).
- Internal synthesis notes recorded in `tochi-writing-synthesis.md`.

### Internal Implementation Distinction (Not In Manuscript Text)

Implemented evidence-backed features:
- workflow session/event model and APIs,
- event-linked inference/proofreading flows,
- approval/rejection action gating,
- workflow-aware chat timeline,
- LLM configuration hardening and backend diagnostics.

Ideation/planned feature set:
- failure hotspot prioritization,
- correction impact preview,
- bounded project-level autonomous run manager,
- versioned experiment bundles,
- CAVE-compatible integration,
- autonomous plan simulation/edit-before-run.

### Open Paper Question

In final drafting, decide whether to keep Section 5 as protocol-forward (pre-summative-study) or split into "Evaluation Plan" and "Preliminary Instrumentation Results" if pilot data is available by submission lock.

## 2026-04-13 - Long-Form TOCHI-Style Expansion Pass

### Design Decision

Performed a high-volume prose expansion across Sections 3--6 to align narrative density with recent TOCHI papers while preserving technical traceability and agentic framing.

### Research Rationale

Recent TOCHI articles in the reviewed corpus consistently combine: (1) explicit framing questions, (2) richer methodological prose, (3) stronger bridge text between findings and design, and (4) substantial discussion/limitations narratives. To better match that shape, the manuscript was expanded from concise scaffolding to fuller paragraph-based argumentation.

### User-Control Implication

The expanded text continues to center user authority:
- agent guidance is grounded in workflow evidence,
- mutating actions remain approval-gated,
- bounded autonomy is framed around checkpoints and interruption rights.

### Evidence Captured In Code/Logs

- `sample-manuscript.tex` expanded in:
  - Section 3 (`Formative Participants`, `Observed Workflow Pattern`, new `Workflow Breakdowns and Agent Opportunities`, expanded goal/requirement/task bridge),
  - Section 4 (new `Architecture Overview`, richer interaction-model interpretation, added F9--F11 prose, closed-loop walkthrough),
  - Section 6 (`Discussion`) and `Limitations/Conclusions` (now draft prose, not placeholders).
- Added additional `\grace{TODO...}` anchors for user-fill specifics (protocol details, figures, deployment constraints, final takeaway line).
- Recompiled PDF successfully (`sample-manuscript.pdf`, 22 pages).

### Internal Implementation Distinction (Not In Manuscript Text)

The manuscript text remains status-neutral. Implementation-vs-ideation distinctions continue to be tracked only in internal logs and synthesis notes.

### Open Paper Question

Decide whether to keep F9--F11 and extension narrative at current length in the final camera-ready draft, or reduce forward-looking feature text if reviewer emphasis shifts toward strictly demonstrated capabilities.

## 2026-04-13 - Case-Study Framing Correction (Pre-Interview Status)

### Design Decision

Removed manuscript wording that implied interviews had already been completed; restructured Section 3 to present a planned two-phase case study.

### Research Rationale

Claim calibration is critical for TOCHI review. Since interviews and user studies are not yet run, the paper should present:
- a rigorous study design and requirement framework,
- a concrete implemented prototype,
- clearly planned empirical phases.

### User-Control Implication

The revised text still centers human-control boundaries, but now frames them as design hypotheses and evaluation targets to be tested in Phase II rather than as concluded findings.

### Evidence Captured In Code/Logs

- Intro and contribution bullets updated to protocol-first wording.
- Section 3 retitled and reorganized around:
  - two-phase structure,
  - Phase I interview plan,
  - provisional workflow/breakdown model,
  - provisional G/R/T traceability,
  - explicit Phase II linkage.
- Discussion/limitations language adjusted to avoid post-hoc empirical claims.
- PDF re-rendered (`sample-manuscript.pdf`, 23 pages).

### Open Paper Question

When Phase I starts, decide whether to preserve all provisional framing text as “study design” context or replace portions with empirical findings immediately to reduce redundancy.

## 2026-04-13 - Consolidated Codex Wave (Implemented vs Deferred)

### Design Decision

Consolidated all codex-generated draft PR outputs into one architecture-aligned integration branch and one draft PR, instead of merging each draft branch directly.

### Research Rationale

The codex draft branches were generated against mixed assumptions (notably `server_api/workflow/*` vs repo-standard `server_api/workflows/*`). A direct-merge strategy would obscure evaluation evidence and create fragile behavior. Behavior-first porting preserves traceability and keeps implementation consistent with the workflow-spine milestone framing.

### User-Control Implication

User control remains explicit:
- mutating workflow operations still require approve/reject decisions,
- proposal cards increase transparency of agent intent and parameters,
- timeline filters make auditability easier during debugging and study instrumentation.

### Evidence Captured In Code/Logs

- Consolidated branch/PR:
  - branch: `feat/codex-wave-integration`
  - draft PR: `#165` (to `main`)
- Implemented in this wave:
  - workflow hotspots + impact preview,
  - workflow metrics endpoint,
  - workflow export-bundle endpoint,
  - workflow evidence utility module and research export doc,
  - chat lifecycle observability summary logging,
  - timeline actor/event filters,
  - richer pending proposal cards with approve/reject.
- Deferred intentionally:
  - CAVE integration spike scaffolds/docs remain deferred backlog work (not merged as product behavior).
- Consolidation hygiene:
  - codex source draft PRs `#139`-`#164` closed with redirect to `#165`.

### Open Paper Question

Decide whether to expose workflow metrics/export-bundle endpoints in the paper as “evaluation instrumentation implemented” or keep them described as internal research support infrastructure, depending on how much of their output is used in the final user-study analysis.

## 2026-04-27 - Editable Project Role Confirmation Checkpoint

### Design Decision

Project mounting now separates indexing from workflow registration. The app
infers likely project roles from the mounted directory, then asks the user to
confirm or edit image, mask/label, prediction, checkpoint, and optional config
paths before writing workflow state.

### Research Rationale

This makes the prototype more project-agnostic and aligns with the paper's
human-controlled agent framing. Auto-detection is useful, but silently treating
detected files as workflow facts makes the system brittle and hard to explain
in a study. Confirmation creates an auditable handoff from file management to
the segmentation loop.

### User-Control Implication

Image volume is the only required role. Biologists can start with image-only
data, add masks later, or override incorrect auto-detected files without typing
full paths. The agent should treat unconfirmed role guesses as suggestions and
confirmed roles as workflow context.

### Evidence Captured In Code/Logs

- Added confirmed-role workflow patch generation utilities.
- Updated File Management so suggested and manually mounted directories open a
  role-confirmation modal before `dataset.loaded`.
- `dataset.loaded` now records confirmed roles, profile mode, mounted root, and
  workflow patch source metadata.
- Added frontend tests for suggested project confirmation, edited/cleared roles,
  image-only setup, and canceling manual mount confirmation.

### Open Paper Question

Decide how much of this setup handoff appears in the paper figures: it may be
important evidence for bounded autonomy, but it should not distract from the
main segmentation-loop contribution.

## 2026-04-27 - Config Lineage and Durable Evidence Bundle Pass

### Design Decision

Confirmed project configs are now persisted as first-class workflow state, and
workflow evidence export writes a durable local bundle directory in addition to
returning JSON through the API.

### Research Rationale

The paper-ready prototype needs artifact lineage that survives beyond the live
UI session. A config path is part of the model/run decision, not just a UI
detail. Likewise, a bundle response that only exists in memory is insufficient
for case-study audit, figure preparation, or claim calibration.

### User-Control Implication

The agent can prefer the confirmed config when staging training defaults, but
runtime launch remains approval-gated. Evidence export now creates a local
directory with `workflow-bundle.json`, `artifact-paths.json`, `README.md`, and
small copied artifacts while referencing large files by path.

### Evidence Captured In Code/Logs

- Added `WorkflowSession.config_path`, update/response serialization, SQLite
  compatibility column creation, and frontend role-confirmation propagation.
- Agent training defaults now prefer the confirmed workflow config path before
  falling back to data-derived bundled presets.
- `export-bundle` now records `bundle_directory`, `bundle_manifest_path`, copied
  artifact count, skipped artifact count, and missing path count in the audit
  event.

### Open Paper Question

Decide whether final study exports should copy large image/mask/checkpoint
files into a removable bundle or keep the current safer manifest-plus-small-
artifact approach for local case-study machines.

## 2026-04-28 - Directory-Aware Project Ingest Pass

### Design Decision

Project setup now treats a mounted project as a directory structure first, not
as one image/mask/config tuple. Backend profiling reports role directories and
detected image/label volume sets. The frontend defaults to folder-level roles
when multiple image/label volumes are detected, while preserving single-file
defaults for small smoke projects.

### Research Rationale

Practitioner project folders often contain batches, train/test splits, or
multiple crops. A one-file confirmation modal misrepresents that workflow and
weakens the paper claim that the agent can help with realistic iterative
segmentation. Directory-aware confirmation makes the human-agent handoff more
honest: the agent infers likely structure, then the user quickly corrects it.

### User-Control Implication

The user can now type a short biological/project-context note during setup and
confirm folders or files for image, label, prediction, checkpoint, and config
roles. Workflow state still changes only after `Start project`; the
`dataset.loaded` event records confirmed roles, detected directories, detected
volume sets, and project context.

### Evidence Captured In Code/Logs

- Added backend role-directory summaries, generic `.zarr`/`.n5` directory
  recognition, and `volume_sets` inference.
- Updated project setup defaults to prefer folders only for multi-volume
  projects.
- Updated File Management confirmation UI to capture concise natural-language
  project context and show detected batch structure.
- Refined the confirmation UI to remove stage/readiness chips, avoid full
  absolute paths in role fields, and present the detected project structure as
  a compact agent-style sentence asking the user to confirm or correct it.
- Added an in-modal setup feedback loop: pressing Enter submits the user's
  question/correction, returns a compact local agent response, applies simple
  detected split corrections such as "use val split", records a client app log
  event, and appends a `dataset.setup_feedback` workflow event when a workflow
  is active.
- Fixed the feedback loop to support repeated correction turns. The submit path
  now reads the latest draft setup state through a ref and does not block local
  correction updates while workflow-event logging is still in flight.
- Added backend and frontend tests for multi-volume folder defaults and event
  payloads.

## 2026-04-28 - Project Context First Confirmation Pass

### Design Decision

The confirmation flow now asks for broad biological/project context before it
shows detected structure and before it accepts mapping corrections. The earlier
single text box conflated "what is this dataset?" with "fix my file mapping,"
which made the agent context ambiguous and made the UI feel like a technical
manifest rather than a project handoff.

### User-Control Implication

The user can describe the directory in their own words first. The app then
shows what it inferred, lets the user correct image/label/prediction/checkpoint
roles separately, and only writes workflow state after `Start project`.
Mapping correction turns are no longer folded into project context.

### Evidence Captured In Code/Logs

- Added a dedicated `projectDescription` field before detected structure.
- Added a separate `mappingFeedback` field for the Enter-to-ask/apply loop.
- Project descriptions are stored in `metadata.project_context` when supplied,
  with lightweight inferred fields for modality, target structure, and
  speed/accuracy preference.
- `dataset.loaded` now carries both `project_description` and structured
  `project_context`; `dataset.setup_feedback` remains the audit trail for file
  mapping correction turns.
- Focused frontend tests passed:
  `CI=true npm test -- --runInBand src/views/FilesManager.test.js src/utils/projectSuggestions.test.js`
  with 13 tests passing.

### Open Risk

The context parser is intentionally lightweight. It is good enough for common
terms such as EM, micro-CT, mitochondria, nuclei, and speed/accuracy, but the
agent still needs a richer context extraction pass or explicit follow-up
questions for uncommon modalities, structures, and lab-specific naming.

## 2026-04-28 - Staged Project Initialization and Hidden Agent Memory

### Design Decision

Project initialization is now a partitioned subworkflow. The app asks for
semantic project context first, requires a deterministic completeness check,
then moves to mechanistic file/folder mapping, and only then allows final
workflow registration. This keeps biological intent and directory-role mapping
separate while still making both available to the agent.

### Perturbations From The Proposed Plan

- The hidden project file is not the source of truth for audit. It is a compact
  agent memory/profile layer; workflow DB records and events remain the
  authoritative evidence trail.
- The context threshold is deterministic rather than LLM-confidence-based:
  modality, target structure, task goal, data organization, and speed/accuracy
  preference are required unless the user explicitly chooses conservative
  defaults.
- A `Use defaults` escape hatch exists for smoke tests and ambiguous folders.
  It is recorded in project context as `use_defaults: true` so the agent knows
  it should be cautious later.

### Evidence Captured In Code/Logs

- Added backend read/write routes for `.pytc_project_context.json`.
- Hid `.pytc_project_context.json` from project mounting and file listings.
- Added staged modal states: `Describe project`, `Confirm file mapping`, and
  `Start project`.
- Added deterministic project-context parsing/completeness helpers.
- On confirmation, the app writes workflow metadata, `dataset.loaded`, and the
  hidden project memory file containing semantic context, mechanistic mapping,
  workflow-memory summary, and setup turns.
- Empty root file-management state now shows a project-initialization card
  instead of a generic empty-folder state.
- Focused frontend tests passed with 14 tests; backend file-workspace route
  tests passed with 9 tests.

### Open Risk

The hidden memory file is written best-effort from the client through the API.
Read-only mounted directories should surface a clearer user-facing warning if
profile persistence fails; for now the workflow still starts and logs the
failure.

### Related Multi-Set Risk

The app still chooses one active image/label root per workflow. True multi-set
operation needs an active-set selector, batch actions, and agent actions that
can iterate over several confirmed sets without hiding artifact provenance.

## 2026-04-28 - Project Context Modal UI Trim

### Decision

The project-description step should collect semantic context without exposing
the internal completeness rubric as visible UI. The modal now keeps only the
plain-language prompt and text area. The deterministic parser, setup-turn
recording, hidden `.pytc_project_context.json` profile, and workflow metadata
are unchanged.

### Rationale

The visible "I still need..." diagnostic and the gray "Required..." footer made
the setup feel like an implementation checklist rather than a normal project
intake. The rubric remains useful for agent memory, but it should not be
presented as primary biologist-facing UI.

### Follow-Up Fix

After hiding the rubric, `Continue` appeared broken whenever the description did
not satisfy every deterministic context field because the modal stayed on the
same step with no visible explanation. The setup flow now advances after any
non-empty project description and records incomplete/missing context internally
for the agent to resolve later. Empty descriptions still require either text or
the explicit defaults path.

### Correction To Match Intended Loop

The intended interaction is not "any text advances"; it is: user gives a first
description, the agent asks one follow-up question if context is incomplete, the
user adds more detail, and the loop repeats until enough context exists. The UI
now shows only the next natural-language follow-up question, never the internal
missing-field checklist. `Use defaults` remains the explicit escape hatch.

### Loop State Fix

Runtime logs showed project-context review events with no frontend exception.
The issue was local state: the text box was acting as both the current answer
and the accumulated project description. Short follow-up answers such as `EM!`
could therefore erase earlier context and make the loop appear stalled. The
modal now keeps accumulated context separately, clears the answer box after each
follow-up prompt, and appends each answer into hidden project memory. The parser
also recognizes punctuated modality answers such as `EM!`.

### Project Brief Upgrade

The confirmation step now renders a derived project brief instead of a raw
transcript/chip dump. The brief summarizes biological intent, extracted context
fields, how the agent will use the confirmed paths/config, and the first
uncertainty to watch. The same `project_brief` object is saved into the hidden
project context profile and the `dataset.loaded` workflow event so this display
also becomes agent-usable state.

### Context Loop Stalling Fix

Runtime `project_context_reviewed` events showed the modal was receiving
`Continue` clicks, but missing fields were not shrinking on some projects. The
loop was too dependent on what the user typed and ignored information already
available from the profiled directory. A temporary implementation used
name/path-derived defaults; that was later corrected below because it overfit
semantically lucky demo names. App event logs still include the inferred context
and next question so future stalls are diagnosable.

### Content-Based Context Correction

Name/path-based biological defaults were too brittle and too demo-specific.
The profiler now separates mechanistic role classification from semantic
project context. File and folder names may still classify roles such as image,
label, prediction, config, and checkpoint, but modality/target/task hints come
from lightweight content spot checks: manifest/config/readme snippets, HDF5
dataset keys/shapes, TIFF headers, and extension counts. The frontend now
consumes only explicit backend `context_hints` for biological defaults.

The large File Management project-setup banner was removed. Suggested projects
remain available through the normal `Open suggested project` button, keeping
the file screen less visually noisy.

## 2026-04-29 - Agent Action Card Robustness Fix

### Diagnosis

The screenshot query was routed as `status` because the status intent matched
the term `ready` inside the word `already`. The agent then produced a next-step
recommendation that said "Proofread this data" while the returned cards were
generic status/setup actions. The app could render Run-in-app cards, but the
backend selected the wrong card set.

### Changes

- Replaced raw substring status matching with token/phrase-aware `_query_has`.
- Added explicit visualization intent handling for requests like "can you
  visualize these volumes?".
- Added visualization client effects so agent-run `View data` populates the
  image/label fields before switching to the viewer.
- Made setup-stage recommendations prefer `Proofread this data` when the
  workflow already has a source volume plus mask/label/prediction.
- Added proofreading blockers. If image or mask-like data are missing, the agent
  now says exactly what is missing and offers `Choose data` rather than a fake
  proofreading command.
- Expanded workflow-agent backend logs with action ids, labels, command ids,
  recommendation decision, next stage, and proofreading blockers.

### Test Evidence

- `/opt/homebrew/bin/uv run pytest tests/test_workflow_routes.py -q`: 26 passed.
- `CI=true npm test -- --runInBand src/contexts/WorkflowContext.test.js src/components/Chatbot.test.js`: 16 passed.
- `npm run build`: compiled successfully with existing warnings.

### Remaining Risk

The visualization card currently fills paths and opens the tab; it does not
auto-click the Neuroglancer `Visualize` button. That is safer for now, but a
future controlled `start_visualization` runtime action could make it fully
hands-free.

## 2026-04-29 - Proofreading Context Leak Diagnosis

Runtime logs showed two separate failures after the agent was asked to visualize
an image/segmentation pair. First, the visualization action populated the
current `prepilot_nucmm_mouse` image and label directories, then Neuroglancer
returned 400 because it was handed a directory path instead of a directly
readable volume file. Second, the subsequent proofreading page showed
`mito25-paper-loop-smoke` because `DatasetLoader` queried global
`/files/project-suggestions` whenever no EHTool session was loaded.

The latter was a real context leak: proofreading was advertising an unrelated
suggested project independent of mounted/current workflow state. The loader now
uses only the current workflow's confirmed image/mask paths, or falls back to
the manual loader with no global suggestion card.

The same log window showed duplicate `/eh/detection/load` attempts from one
assistant proofreading action. A small one-shot guard was added around
assistant-triggered proofreading runtime actions so React effect re-entry cannot
submit the same load twice.

## 2026-04-29 - Raw Tool Call Leak Fix

The chat screenshot showed the general LLM path returning raw JSON:
`{"name":"visualize_volume_pair", ...}`. Logs confirmed the request went through
`/chat/query` rather than the workflow-agent endpoint, so the app displayed the
local LLM's pseudo tool call as normal assistant text.

Fixes: visualization/volume-pair requests now route to the workflow agent, which
can return app actions/cards, and both frontend and backend chat sanitizers
replace raw JSON tool-call-shaped responses with a plain-language recovery
message. This protects current rendering and persisted chat history.

## 2026-04-29 - Train/Run Model Label Pass

Renamed the user-facing top navigation and major stage copy from `Train`/`Infer`
and `Model Training`/`Model Inference` to `Train Model` and `Run Model`.
Internal route keys, workflow stages, PyTC command flags, and persisted event
types remain `training`/`inference` for compatibility.

## 2026-04-29 - Visualization Folder-Pair Resolver

A visualization run failed because the workflow stored folder-level roles
(`Image/train` and `Label/train`) and `/neuroglancer` tried to read the image
folder as a volume file. The backend now resolves folder-level visualization
inputs to a concrete readable image/label pair before loading Neuroglancer. For
folders with matching names like `img_000_604_576.h5` and `seg_000_604_576.h5`,
it selects the matched pair, updates workflow paths to the concrete files, and
logs the resolution as `neuroglancer_volume_path_resolved`.

Also removed the duplicate workflow-agent command block for visualization
requests. The assistant should now show one primary `View data` app action
instead of both `View data` and `View data in app` for the same operation.

## 2026-04-29 - Directory Pair Discovery for Visualization Agent

Refined the visualization fix so directory roles are treated as candidate
image/segmentation pair sets instead of just a folder to silently coerce into
one file. Added shared volume-pair discovery logic that normalizes common
image/label prefixes (`img_`, `seg_`, `label_`, `mask_`, etc.) and returns all
clear matches. The workflow agent now detects these pairs before offering a
`View data` action, points the action at the first concrete matched pair, and
asks the user whether more folders or pairs should be included.

The `/neuroglancer` endpoint now logs `neuroglancer_volume_pairs_detected`,
returns the selected pair plus the detected pair set, and records
`active_volume_pair` / `volume_pair_discovery` in workflow metadata when a
directory-level request reaches the endpoint. The Visualization UI accepts this
richer response shape, updates its local fields to the resolved concrete pair,
and surfaces the "more pairs?" prompt as a lightweight message. The workflow
agent also falls back to the stored discovery metadata after an active concrete
pair has replaced folder-level fields, so it can keep continuity across later
queries.

Test evidence:
- `python -m py_compile server_api/main.py server_api/workflows/router.py server_api/workflows/volume_pairs.py`
- `/opt/homebrew/bin/uv run pytest tests/test_neuroglancer_volume_normalization.py -q`: 11 passed.
- `/opt/homebrew/bin/uv run pytest tests/test_workflow_routes.py -q`: 27 passed.
- `CI=true npm test -- --runInBand src/components/Chatbot.test.js`: 9 passed.
- `npm run build`: passed with existing ESLint warnings.

## 2026-04-29 - Visualization Scale Context and Agent Reload

The scale-correction screenshot exposed another agent routing gap: "reload with
1-1-1" was not a first-class workflow action, so the generic chat path could
return tool-call-shaped JSON instead of a useful app action. The fix treats
voxel scale updates as workflow state, not explanatory chat.

Implemented a `set_visualization_scales` workflow-agent intent. It parses
z,y,x values from natural language, stores them as `visualization_scales` and
`project_context.voxel_size_nm`, appends a `visualization.scales_updated`
workflow event, and offers one `Reload viewer` action that routes the UI to
Visualization with `runtime_action: load_visualization`. The Visualization
screen now reads persisted scale context and agent-triggered reloads use the
current image/label fields when workflow paths are not enough.

Also hardened chat rendering against embedded JSON tool-call leaks such as
"Here is the revised function call..." followed by a JSON object.

Test evidence:
- `python -m py_compile server_api/main.py server_api/workflows/router.py server_api/workflows/volume_pairs.py`
- `/opt/homebrew/bin/uv run pytest tests/test_workflow_routes.py -q`: 29 passed.
- `CI=true npm test -- --runInBand src/components/Chatbot.test.js src/contexts/WorkflowContext.test.js`: 20 passed.
- `npm run build`: passed with existing nonblocking lint warnings outside this scale-change path.
