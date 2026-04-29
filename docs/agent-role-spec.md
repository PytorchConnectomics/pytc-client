# Agent Role Specification

This defines the intended role of the agent in the TOCHI-facing PyTC Client
prototype.

## Product Role

The agent is a workflow copilot for biomedical segmentation. It should help a
biologist understand the current state, choose the next safe action, and inspect
evidence. It is not a replacement for the human reviewer and should not silently
execute risky training, inference, overwrite, export, or retraining actions.

## Default Behavior

- Recommend the next concrete workflow action first.
- Keep answers skimmable: at most three bullets and usually under 90 words.
- Ground UI instructions in visible app controls and documented workflows.
- Show blockers clearly: missing image, label, checkpoint, prediction, export,
  correction set, model version, or metric result.
- Prefer app actions over command-line instructions for normal users.
- Ask for approval before actions that run jobs, overwrite masks, stage
  retraining, launch inference, launch training, or export evidence.

## Agent Boundaries

- The agent may navigate the user, summarize state, propose actions, explain
  settings, populate form fields, and prepare commands.
- The agent may generate a training/inference command only when explicitly
  asked for a command.
- The agent may not fabricate paths, scripts, shortcuts, results, model quality,
  or hidden app features.
- The agent may not claim autonomous closed-loop improvement until the app has
  executed baseline inference, proofreading export, retraining, candidate
  inference, and before/after evaluation using app-generated artifacts.

## UI Role

The agent should appear as a compact decision-support layer across the app, not
as a verbose chatbot. It should connect File Management, Visualization,
Inference, Proofreading, Training, Evaluation, and Evidence Export through the
workflow evidence substrate.

Implemented UI commitments:

- The assistant drawer/status entry should always answer "what should I do
  next?" from current workflow evidence without adding persistent canvas clutter.
- The first action must match the recommendation. For example, "start
  inference" should expose a start-inference action, not merely a navigation
  button.
- The agent can open the assistant evidence/context drawer from any module so
  the user can inspect artifacts, correction sets, metrics, and proposals
  without losing the active workflow.
- Retraining handoff remains approval-gated: the agent may create a pending
  proposal from corrected masks, but the human must approve staging.
- Chat responses for workflow questions should reuse the same recommendation
  state and use compact `Do this`, `Why`, `Ready`, `Watch out` structure.

## 2026-04-25 Orchestrator Pass

- The agent should speak in user goals, not implementation nouns. Use
  "Proofread this data", "Run model", "Use edits for training", and "Compare
  results" instead of "open artifact", "candidate output", or "retraining
  handoff" in biologist-facing controls.
- The primary action should mutate local app state when safe. `Proofread this
  data` now carries a `start_proofreading` runtime action with image/mask/review
  overrides so the proofreading workbench can load the current pair directly.
- Status panels should summarize readiness with domain labels: previous result,
  new result, your saved edits, and reference mask. Full paths and dataset-key
  options are still available, but should be secondary/debuggable details.
- The agent is allowed to orchestrate navigation, form prefill, proofreading
  load, inference launch, training launch, metric comparison, and report export
  through explicit client effects. Risky steps remain user-triggered and
  event-logged.

## Success Criteria

- A biologist can skim the response in under ten seconds.
- The response identifies the next useful action or the single blocking input.
- Risky actions are auditable as proposals, approvals, rejections, or workflow
  events.
- The agent improves workflow continuity without hiding provenance or control.

## 2026-04-25 Prompt-Boundary Hardening

- The active app assistant defaults to the deterministic workflow orchestrator
  for greetings, repair phrases, slash commands, and recognizable workflow
  intents. General/non-workflow text should still route to normal assistant/LLM
  handling so the chat does not turn every message into a next-step card.
- Internal system prompts, role text, routing rules, tool names, and response
  style instructions are never valid user-facing output. If the generic LLM
  leaks prompt scaffolding, the server replaces it with a compact safe fallback.
- The orchestrator now handles greetings, incomplete intents, status checks,
  module navigation, model launch, proofreading launch, retraining handoff,
  before/after metric comparison, and evidence export as explicit, auditable
  app actions.
- The agent is not just a help sidebar: it is the controller that translates
  user goals into workflow-state-aware next steps while preserving human
  approval for long-running or artifact-changing operations.

## 2026-04-26 Agent Routing and Help Cleanup

- Unknown workflow-router text must return a compact clarification and no app
  action cards. Gibberish should never produce "proofread/train/compare" cards.
- The main assistant logs whether a message went through the workflow
  orchestrator or the general assistant path.
- Inline field help should be a compact local hint, not a docs viewer. It must
  avoid raw headings such as "Relevant local docs" and keep file-selection help
  focused on visible controls such as the folder icon, Browse, and Use folder.
- File path text boxes remain editable fallback controls, but ordinary users
  should be able to open the picker from the folder icon or Browse button.

## 2026-04-26 Contextual Project Context

- Do not use a startup splash or session-goal gate. The product goal is fixed:
  move from an initial biomedical image volume to fully proofread
  segmentations.
- The agent should gather biological context only when it is needed to run or
  stage a workflow action: inference, training, proofreading triage, or
  comparison.
- Minimal project context is `imaging_modality`, `target_structure`, and
  `optimization_priority` such as speed versus accuracy. Store it under
  `metadata.project_context`, distinct from workflow progress events.
- The agent may ask one compact question before acting: modality, target
  structure, and speed/accuracy preference. The user can also say "use
  defaults" to proceed with conservative settings.
- Running progress remains append-only workflow events and artifacts:
  `dataset.loaded`, training/inference runs, correction sets, evaluation
  results, and bundle exports.

## 2026-04-27 Project Role Confirmation Contract

- The app and agent may infer image, mask/label, prediction, checkpoint, and
  config roles from a mounted directory, but workflow state is not populated
  until the user confirms or edits those roles.
- Image volume is the only required setup role. Mask/label, prediction,
  checkpoint, and config roles are optional so image-only folders remain valid
  starting points.
- Confirmed roles are recorded as a `dataset.loaded` event with the inferred
  profile mode, mounted directory, confirmed role paths, and resulting workflow
  patch.
- Config is now a first-class workflow path. It may seed agent-selected
  training defaults, but the user still approves the resulting runtime action
  before a job launches.
- The agent should treat unconfirmed project-role guesses as suggestions, not
  facts. After confirmation, it can use those paths to recommend visualization,
  inference, proofreading, training, or comparison.

## 2026-04-28 Directory and Batch Ingest Contract

- A project usually contains folders of image volumes, not one canonical file.
  Profiling must therefore surface both examples and role directories.
- `pytc-project-profile/v1` now includes `role_directories` and
  `volume_sets`. A volume set records image root, optional label root, counts,
  matched pair count, and examples.
- The confirmation UI should default to a folder when multiple images/labels
  are detected, and to a file when the project is genuinely single-volume.
- The user can add a compact natural-language project description during
  confirmation. This is agent context and audit metadata, not a startup splash
  or a blocker.
- `dataset.loaded` should include confirmed roles, detected directories,
  detected volume sets, and the user project context so downstream agent
  actions can explain what they used.
- The confirmation surface should read as a short agent check, not a technical
  manifest. Avoid readiness chips and absolute paths; show concise inferred
  structure in words, let the user correct the inference in natural language,
  and keep relative role fields editable as fallback controls.
- The project-setup correction box is an interaction loop, not passive notes:
  Enter submits the question/correction, the agent replies in place, detectable
  split changes such as "use val split" update the role fields, and the turn is
  logged as `dataset.setup_feedback` before final `dataset.loaded`.
- The correction loop must support repeated turns. Feedback submission should
  operate on the latest confirmed draft roles and should not block subsequent
  local corrections while workflow-event logging is in flight.
- Project context comes before structure correction. The confirmation surface
  has a dedicated `What is in this directory?` field for broad biological
  context, then an agent summary of detected image/label sets, then a separate
  `Correct my file mapping` loop.
- Project context is durable workflow metadata, not correction feedback. When
  supplied, it is stored under `metadata.project_context` and echoed in the
  `dataset.loaded` event as `project_description` plus inferred lightweight
  fields such as imaging modality, target structure, and speed/accuracy
  preference.
- Mapping feedback remains operational and append-only:
  `dataset.setup_feedback` records questions/corrections and role changes, but
  those turns should not be treated as the biological project description.
- The confirmation flow is now a staged subworkflow, not one combined modal:
  semantic project context comes first, file/folder mapping comes second, and
  final confirmation comes third.
- The semantic stage uses a deterministic completeness gate before advancing.
  Required context is imaging modality, target structure, task goal, data
  organization, and speed/accuracy preference. If the gate is incomplete, the
  agent asks targeted follow-up questions instead of guessing from a vague
  confidence score.
- The hidden `.pytc_project_context.json` file is the local project memory
  anchor. It stores compact semantic context, mechanistic mapping,
  workflow-memory summary, and setup turns for agent continuity across modules
  and app restarts. It is not the authoritative audit trail; workflow DB records
  and events remain authoritative.
- `.pytc_project_context.json` is hidden from the normal file-management UI and
  ignored during project mounting.
- Project setup must not infer biological context from project names alone.
  Role classification can use path/name patterns, but modality, biological
  target, and task hints should come from user description and lightweight file
  content inspection such as manifests, configs, HDF5 dataset keys, and image
  container metadata.

## 2026-04-26 Agent-Run Training Defaults

- The biologist should provide the goal, data, and approval; the agent should
  choose the nearest safe training preset and fill routine runtime paths.
- Low-level YAML, stride, blending, chunk, CPU/GPU, and iteration settings are
  advanced controls. The assistant must not lead with them unless the user asks
  to override defaults or debug a failed run.
- Agent-triggered training uses `agent_default` mode: current image path,
  corrected mask path, output/log directory, preset config, and conservative
  memory-safe defaults are staged together before the user approves the run.
- Meta questions such as "how did you run so quickly?" should state whether the
  app actually ran a job. Do not answer those with retrieved training docs.

## 2026-04-26 Project-Agnostic Setup Contract

- The agent and UI should not depend on the mito25 demo path. Any mounted folder
  can become a workable project if it contains a detectable image volume.
- Folder profiling returns `pytc-project-profile/v1` with modes:
  `not_workable`, `image_only`, `image_mask_pair`, and `closed_loop_ready`.
- The biologist-facing blocker is the missing data artifact, not YAML. Training
  configs and inference presets are agent-inferred implementation details unless
  the user asks to override them.
- Workflow preflight is exposed at `GET /api/workflows/{id}/preflight`. It
  reports whether setup, visualization, inference, proofreading, training, and
  evaluation can run from the current workflow records.
- Image-only projects are valid starts. The next step is to add/run a model or
  provide a mask/label, not to force the mito smoke fixture.

## 2026-04-27 Quick Next-Step Affordance

- The app shell can ask the workflow agent `What should I do next?` from any
  module. This is a stable entry point, not a per-module card.
- The quick action routes through the same workflow-agent chat path as typed
  requests, so the answer is persisted, action cards are preserved in history,
  and risky actions remain approval-gated.
- The agent response should be derived from workflow preflight, artifacts, runs,
  corrections, metrics, and current stage. The prompt/query is only a trigger;
  it must not become a free-form hallucinated opinion.
- Keep the answer compact: one recommended action, one reason, readiness count,
  and at most one blocker.

## 2026-04-25 Claude Code Pattern Pass

- Treat chat as a control surface over typed workflow tools. The agent should
  return app actions with risk metadata rather than long explanatory prose.
- Every action should be classifiable as `view only`, `sets form`, `opens
  editor`, `runs job`, `writes record`, or `exports`. Long-running or
  artifact-changing actions require an explicit user click and workflow-event
  logging.
- Support deterministic slash-style workflow commands for power users:
  `/status`, `/infer`, `/proofread`, `/train`, `/compare`, `/export`, and
  `/help`.
- Keep command-like route details collapsed by default. Biologist-facing UI
  should show the domain action first and reserve implementation details for
  debugging/logging.
- Maintain a structured loop checklist in the response payload so the assistant
  can answer "what is left?" without inventing state from chat history.
- Future subagents should be domain-specialized and tool-restricted:
  data-curator, model-runner, proofreading-triage, and evidence-auditor.

## 2026-04-25 Contextual Entry-Point Pass

- Keep the main drawer/chat as the full conversation and evidence inspector.
- Do not keep a persistent next-step strip on the main canvas by default; it
  competes with the biomedical task UI.
- Do not add per-module agent cards by default; they make the biomedical UI feel
  busier than the task requires.
- If a module needs agent help, expose it as a normal button near the relevant
  control, with any explanation in a hover tooltip.
- All agent-triggered buttons must still log client events and route through
  `executeAssistantItem` or `queryAgent` so they remain auditable.
- Training/inference terminal logs should be hidden by default. The main UI
  should show a plain run state such as "Running", "Completed", or "Needs
  attention" and only reveal raw logs on demand.

## 2026-04-29 Agent Action Consistency Contract

- Agent text, action cards, and command blocks must be generated from the same
  workflow decision. The assistant must not say "Proofread this data" while only
  offering generic status or setup cards.
- Intent matching must be token/phrase aware. Raw substring matches are unsafe
  because normal words such as "already" can accidentally trigger "ready" and
  route the request to status.
- If the requested action is possible, the response should include a runnable
  app card/command for that exact action. For example, a proofread request with
  an image plus mask/label should expose `start-proofreading`.
- If the requested action is blocked, the response should state the missing
  artifact plainly and offer the nearest executable setup step. For example:
  "I can proofread this, but I need a mask, label, or prediction first."
- Visualization requests are valid workflow actions. Running the card should
  move to the viewer and populate image/label paths from workflow state, not
  merely switch tabs.
- If visualization paths are directories, the agent should first discover clear
  image/segmentation pairs, offer the first concrete pair as the runnable
  action, and ask whether there are more folders or pairs to include. Directory
  paths are project context; concrete pairs are active viewing/proofreading
  targets.
- Visualization voxel scales are project context. Scale corrections like
  "reload with 1-1-1" should be parsed into z,y,x nanometer values, persisted in
  workflow metadata, logged as `visualization.scales_updated`, and exposed as a
  single reload action rather than as documentation or raw tool JSON.
- Backend agent logs should include the chosen intent, recommendation decision,
  action ids/labels, command ids/titles, and blocker list so mismatched cards
  can be debugged from `.logs/app/app-events.jsonl`.
