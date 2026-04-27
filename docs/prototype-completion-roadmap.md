# Prototype Completion Roadmap

This is the long-term project memory for moving from the current PyTC Client
toward the paper-implied prototype: an agent-mediated, human-controlled,
closed-loop biomedical segmentation workflow.

## Current Verdict

The project is not yet a paper-ready prototype of the system described by the
paper. The evidence substrate is now real enough to support structured smoke
walkthroughs: real mito25 image/seg data can enter the path, supplied PyTC
prediction files can be evaluated, completed app/PyTC inference runtimes can be
synced into workflow records, correction exports become correction-set records,
and the participant UI exposes the closed-loop pipeline, evidence artifacts,
metric controls, and bundle export. The remaining gap is still the full fresh
closed loop: app-launched baseline inference, real proofreading edit/export,
actual retraining/fine-tuning, post-training inference, and before/after
evaluation over fresh app-generated outputs.

## Prototype Boundary

- Participant UI should expose biomedical workflow state and controls, not
  case-study protocol controls.
- Case-study readiness, protocol planning, and study gates stay researcher-only
  in docs, backend routes, tests, and exported evidence bundles.
- Do not reintroduce case-study readiness bars or protocol-plan cards into the
  participant-facing app.

## Implemented Checkpoints

- Typed workflow evidence records exist for events, artifacts, model runs, model
  versions, correction sets, evaluation results, hotspots, agent plans, and
  agent steps.
- Workflow bundle export exists for researcher/paper evidence capture.
- Researcher-only readiness gates exist and are covered by backend tests.
- Synthetic closed-loop smoke exists in `scripts/run_closed_loop_smoke.py`.
- Real-pair smoke exists for mito25 HDF5 image/seg pairs, using HDF5 dataset
  keys and crop support.
- Real prediction input mode exists for supplied baseline/candidate prediction
  artifacts.
- PyTC channel-first/channel-last prediction outputs can be selected with
  explicit baseline/candidate channels in the smoke harness.
- Completed PyTC worker inference runtimes can be synchronized into workflow
  `inference.completed` events, `ModelRun` records, and prediction artifacts.
- Closed-loop evidence is visible in the participant UI: baseline prediction,
  candidate prediction, corrected mask, reference label/ground truth, latest
  evaluation report, and metric deltas.
- The participant UI can compute before/after evaluation metrics from recorded
  baseline, candidate, and reference volume paths when all required evidence is
  present.
- The participant UI exposes dataset key, crop, and channel controls for HDF5
  and PyTC-style predictions that cannot be safely auto-detected.
- The participant UI shows an explicit closed-loop pipeline map with the next
  incomplete gate.
- Evidence bundle export is available from the participant workflow evidence
  panel and logs a `workflow.bundle_exported` event for auditability.
- A workflow-agent recommendation endpoint now returns a stage-aware decision,
  readiness checklist, blockers, top hotspot, impact preview, app actions, and
  command blocks from the typed workflow evidence substrate.
- The participant UI now has a compact workflow-agent control strip across
  modules. Its primary button can navigate, start safe runtime handoffs, propose
  retraining staging from corrected masks, refresh insights, and open the
  assistant evidence/context drawer.
- Workflow chat now uses the same recommendation substrate for "what next"
  questions and keeps answers compact: `Do this`, `Why`, `Ready`, and at most
  one blocker.
- Workflow-agent chat now carries typed intent, permission-mode, risk metadata,
  and a structured loop checklist. Slash-style workflow commands are supported
  for status, inference, proofreading, training, comparison, and export.
- Assistant chat routing now distinguishes workflow intents from general chat:
  workflow-like requests go to the deterministic orchestrator, while unrelated
  or nonsensical text goes through the general assistant path instead of
  producing workflow action cards.
- The workflow-agent router now clarifies unknown requests without app action
  cards, preventing gibberish from being interpreted as a next-step command.
- Main chat now has direct guardrails for low-signal gibberish, meta questions
  about whether a job actually ran, and biologist-facing parameter delegation.
  These responses persist to chat history without invoking the docs RAG path.
- The local assistant default model is now `llama3.1:8b` instead of
  `llama3.2:1b`; current local-model evaluation notes live in
  `docs/research/on-device-llm-options-2026-04-26.md`.
- Assistant command details are collapsed behind a route disclosure so the
  visible UI stays domain-oriented rather than command-oriented.
- Agent-triggered training now stages an inferred preset, current image path,
  corrected mask path, output/log directory, and conservative default runtime
  parameters before the user approves the run.
- Proofreading mask exports materialize correction sets with edit and region
  counts derived from preceding proofreading events.
- File Management has a one-click suggested mito25 smoke-project mount.
- Suggested project mounting profiles local folders for likely image, label,
  prediction, config, checkpoint, and pair roles before the user has to browse
  manually.
- Suggested project mounting now registers detected workflow paths: dataset,
  image, label/mask, prediction, and checkpoint paths are pushed into the
  workflow session and logged as a `dataset.loaded` event.
- Suggested project mounting is now project-agnostic through
  `pytc-project-profile/v1`: folders can be `image_only`, `image_mask_pair`, or
  `closed_loop_ready`, and image-only volume folders count as valid workflow
  starts.
- Workflow preflight now exposes the current runnable state for setup,
  visualization, inference, proofreading, training, and evaluation from typed
  workflow records. It treats config/YAML as an agent-inferred implementation
  detail rather than a first-order biologist blocker.
- A stable app-shell `What next?` button now opens the assistant and asks the
  workflow agent for the next action from current preflight/evidence state,
  preserving the response and action cards in chat history.
- The app now opens directly to the main module shell. The startup
  session-intake/splash gate was removed because the user goal is always the
  same closed-loop segmentation task.
- The workflow agent now gathers biological project context at action time:
  before inference, training, or proofreading triage it asks for missing
  modality, target structure, and speed/accuracy preference, then stores that
  as `metadata.project_context`.
- Suggested project mounting no longer depends on a startup goal. SNEMI/TIFF
  and raw HDF5 smoke-data fixtures remain available as realistic alternate
  starts alongside the mito smoke project.
- A fresh workflow reset path now creates a clean `setup` workflow session
  while preserving old workflow evidence for audit/history.
- File Management now keeps the suggested project setup card on the root
  project view only, reducing repeated clutter once the user is inside a
  mounted project.
- File path inputs now open the mounted-project picker from the folder icon as
  well as the Browse button, so manual path typing is a fallback rather than
  the apparent primary flow.
- Inline field help now returns compact, field-specific guidance for common file
  selectors instead of raw local-doc excerpts.
- The proofreading editor exposes a visible `Save mask` control, tracks unsaved
  edits, and caps undo history to reduce memory churn.
- HDF5/Zarr/NumPy volume loading can select prediction channels while applying
  crops, avoiding unnecessary full channel-stack reads for PyTC outputs.
- Shared voxel loading exists for TIFF/OME-TIFF, HDF5, NumPy, Zarr/N5, common
  2D image formats, and optional NIfTI/MRC parser packages.
- Evaluation can compute before/after metrics across supported voxel formats.
- Participant-facing case-study UI has been ablated.

## Next Priority

Run the first fresh app-generated before/after loop:

- Launch baseline PyTC inference from the app on a mito25 crop and sync the
  completed runtime.
- Perform a real proofreading edit/export that creates a correction set from
  the browser/editor path.
- Run retraining or a bounded fine-tuning smoke from that correction set.
- Launch post-training inference, sync the completed runtime, and compute
  before/after metrics over the two app-generated outputs.

## Major Workstreams

1. Evidence substrate
   - Keep workflow records typed and queryable.
   - Keep artifact lineage explicit.
   - Keep evidence bundle export deterministic and paper-friendly.

2. Real data ingestion
   - Continue broad voxel-format support.
   - Add OME-Zarr/NGFF and Neuroglancer-precomputed details when the workflow
     needs lab-scale interoperability.
   - Preserve crop/key support so large volumes are testable without loading
     full datasets.

3. Real closed-loop smoke
   - Synthetic smoke is complete.
   - Real image/seg smoke with derived predictions is complete.
   - Real prediction input smoke is complete for externally supplied
     predictions.
   - Existing app-generated PyTC prediction files can be ingested as real
     prediction artifacts.
   - Fresh app-launched PyTC inference smoke is next.

4. Actual PyTC inference/training loop
   - Launch inference on real data.
   - Capture inference output as a `ModelRun`.
   - Proofread or edit a mask and persist a `CorrectionSet`.
   - Stage corrections for retraining.
   - Run retraining or fine-tuning.
   - Register the candidate checkpoint as a `ModelVersion`.
   - Run post-training inference.
   - Compare before/after outputs with real metrics.

5. Workflow UI, not case-study UI
   - Expose workflow stage, artifacts, runs, corrections, evaluation metrics,
     and agent proposals.
   - Implemented UI hardening: direct evaluation-compute controls, closed-loop
     pipeline map, evidence bundle export, and suggested smoke-project mounting
     without adding researcher case-study protocol gates.
   - Implemented agent continuity: the assistant drawer/status entry exposes
     the next recommended workflow action and a one-click evidence/context view
     without requiring a persistent canvas strip.
   - Next UI hardening: expose model versions/config lineage as secondary
     provenance, make file-role assignment editable when auto-detection guesses
     wrong, and continue reducing the generic file-browser feel.
   - Keep approval/rejection controls for risky agent actions.
   - Refine workflow rail placement and visibility.
   - Do not expose researcher protocol gates to participants.

6. Agentic bounded autonomy
   - Agent proposes actions; it does not silently execute risky steps.
   - Agent role is formalized in `docs/agent-role-spec.md`.
   - Claude Code pattern notes live in
     `docs/research/claude-code-agent-patterns.md`.
   - Implemented agent recommendation substrate: stage-aware decision, blockers,
     readiness, top hotspot, impact preview, and app-executable actions.
   - Implemented cross-module agent controls: open files, launch inference from
     current settings, open proofreading, propose retraining handoff, prime
     training labels, launch staged training, and open evidence context.
   - UI simplification pass ablated visible per-module agent nudges and the
     persistent next-step strip. The agent remains accessible through the chat
     drawer and normal module buttons where needed.
   - All chatbot agents should default to short, biologist-skimmable answers:
     next action first, three bullets or fewer, and no internal implementation
     details unless explicitly requested.
   - Approval, rejection, interruption, and resume decisions must be auditable.
   - Use LangGraph where durable state-machine behavior, checkpoints, and
     interrupt/resume semantics become real execution requirements.
   - Use LangChain only for model/tool wrappers and simple retrieval glue.
   - Next agentic-system hardening: durable job/task state, approval modes,
     workflow hooks/gates, focused biomedical subagents, and context compaction
     for long assistant sessions.
   - Implemented preflight backend/context: training and inference readiness can
     now say "ready", "missing X", or "agent can run this with inferred
     defaults" without exposing raw YAML by default.
   - Next UI integration: surface preflight only at decision points, not as
     persistent clutter.

7. Evaluation and provenance
   - Compute before/after segmentation metrics over real outputs.
   - Link metrics to exact prediction, ground-truth, checkpoint, correction, and
     config artifacts.
   - Dataset key, crop, and prediction-channel selectors are implemented in the
     workflow evidence panel.
   - Bundle export is auditable through a workflow event, but a persisted
     downloadable bundle directory/zip is still needed for paper artifact
     packaging.
   - Export paper-ready bundles with events, artifacts, runs, versions,
     corrections, metrics, and figure inputs.

8. Interop and SOTA relevance
   - Align with connectomics/bioimage formats and workflows: HDF5, OME-Zarr/NGFF,
     N5/Zarr, Neuroglancer-compatible artifacts, and eventual CAVE/Neuroglancer
     relevance.
   - Evaluate relevant model ecosystems when needed: PyTorch Connectomics,
     MONAI, nnU-Net, Cellpose/Cellpose-SAM, micro-SAM, MedSAM/SAM2 variants,
     StarDist, PlantSeg, DeepCell/Mesmer.

9. Engineering hardening
   - Replace process-global runtime state with durable job records.
   - Add a real job queue for long-running inference/training.
   - Add cancellation, retries, failure recovery, and resumable execution.
   - Link TensorBoard, MLflow, W&B, or equivalent run tracking to workflow
     records where useful.
   - Make file management and project mounting substantially more user-friendly:
     guided project setup, obvious mounted roots, automatic image/seg/config/
     checkpoint detection, duplicate/stale mount cleanup, better picker labels,
     one-click test-project mounting for smoke workflows, and editable role
     confirmation when auto-detected project roles are wrong. Current progress:
     suggested and manually mounted projects are profiled first, then routed
     through a compact role-confirmation modal before workflow registration.
     Confirmed config paths are persisted as workflow state and used as the
     preferred agent training preset. Remaining hardening is multi-dataset
     selection, batch role assignment, and browser-level blank-state rehearsal
     on non-mito data.

10. Paper alignment
   - Maintain the paper-claim-vs-implementation matrix.
   - Maintain a paper/prototype additions matrix.
   - Keep paper claims honest until the real closed loop works.
   - Refresh the claim wording after each prototype milestone.

## Paper-Claim Risk Register

| Claim Area | Current Status | Overclaim Risk | Required Evidence |
| --- | --- | --- | --- |
| Closed-loop improvement | Backend/evaluation path and external prediction input mode exist, real app-generated model loop missing | High | Real app-generated baseline inference, correction, retraining, candidate inference, before/after metrics |
| Human-controlled agent workflow | Proposal/approval substrate exists | Medium | Visible participant workflow controls and auditable approvals over real actions |
| Biomedical/connectomics relevance | Mito25 data ingestion works | Medium | Real inference/proofreading/retraining on mito/connectomics artifacts |
| Bounded autonomy | Researcher-only plan/proposal records exist | Medium | Durable interrupt/resume execution if claimed as operational |
| Reproducible evidence export | Bundle exists | Low/Medium | Bundle generated from real workflow artifacts and paper figures |
| SOTA alignment | Research notes/plans exist | Medium | Explicit comparison/baseline or clear positioning against relevant systems |

## Researcher-Only Notes

- Case-study protocol details live in `docs/case-study-prototype-readiness.md`.
- Smoke execution details live in `docs/closed-loop-smoke.md`.
- Manual bulk-test steps live in `docs/manual-bulk-test-checklist.md`.
- Evidence export details live in `docs/research/workflow-evidence-export.md`.
