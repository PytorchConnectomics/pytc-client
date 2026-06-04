# Internal Technical Audit - Agentic PyTC Client

Date: 2026-05-24

Repo: `/home/weidf/deploy/pytc-client-demo2`

Branch: `checkpoint/tochi-agentic-prototype`

This report is an internal engineering pass over the current app state after the MitoEM2 progress demo, project progress tracker, guided project context flow, continuous workflow chat, Monitor-tab sunset, and agent action-card work. It focuses on bugs, technical incongruities, UI streamlining, and ways to expand the agent into a more useful workflow collaborator.

## What I Inspected

Primary files and systems:

- Frontend shell and state: `client/src/App.js`, `client/src/contexts/GlobalContext.js`, `client/src/contexts/WorkflowContext.js`, `client/src/api.js`
- Main workflow UI: `client/src/views/Views.js`, `FilesManager.js`, `Visualization.js`, `ModelTraining.js`, `ModelInference.js`, `ProjectProgress.js`, `MaskProofreading.js`
- Chat UI: `client/src/components/Chatbot.js`, `AssistantTrace`, action/proposal card handling
- Runtime config/client launch: `client/src/runtime/modelLaunch.js`, `client/src/configSchema.js`
- Backend app: `server_api/main.py`, `runtime_settings.py`, `app_event_logger.py`
- Workflow agent/backend orchestration: `server_api/workflows/router.py`, `service.py`, `db_models.py`, `agent_plan.py`, `volume_io.py`
- File/project mounting and context scan: `server_api/auth/router.py`
- Worker runtime: `server_pytc/services/model.py`
- Proofreading backend/frontend: `server_api/ehtool/router.py`, `server_api/ehtool/data_manager.py`, `client/src/views/ehtool/DetectionWorkflow.js`, `ProofreadingEditor.js`
- Tests and docs touched by recent work: `tests/test_workflow_routes.py`, `tests/test_file_workspace_routes.py`, `client/src/components/Chatbot.test.js`, `client/src/views/FilesManager.test.js`, `docs/codex-working-memory/progress-log.md`

Validation run during this audit:

- `.venv/bin/python -m py_compile server_api/workflows/router.py server_api/auth/router.py server_api/main.py server_pytc/services/model.py server_api/ehtool/router.py server_api/ehtool/data_manager.py runtime_settings.py app_event_logger.py`
- `CI=true npm test -- --runInBand src/views/Views.test.js src/components/Chatbot.test.js src/views/FilesManager.test.js src/utils/projectSuggestions.test.js`
  - Passed: 55 tests
  - Existing warning: FilesManager async state updates are not wrapped in `act(...)` in tests
- `CI=true npm run build`
  - Passed with existing EHTool hook dependency warnings and large bundle warning
- `.venv/bin/python -m pytest tests/test_workflow_routes.py tests/test_file_workspace_routes.py -q`
  - Passed: 61 tests, 12 dependency/deprecation warnings

## Executive Readout

The prototype now has many of the right ingredients: mounted-project scanning, volume-pair discovery, project context memory, progress snapshots, proofread artifacts, durable workflow commands, action cards, runtime logs, and a broad app-event log. The main issue is that these parts are still stitched together by ad hoc metadata, UI side effects, and heuristic routing rather than a single canonical workflow state model.

The two most urgent product-level gaps are:

1. The agent does not yet have a reliable observe-orient-act loop over project state. It observes files and progress, but this is embedded in `server_api/workflows/router.py` and stored in mutable JSON blobs rather than exposed as a small set of typed tools and state records.
2. User-facing agent actions are too fragile. An action can be a chat item, a proposal, a durable command, a runtime action, a client effect, or some combination. This creates regressions like "Approve does nothing", hidden form prefill failures, stale cards, and confusing training state.

The most concrete bug found in this pass is in the semantic workflow router: the prompt asks the LLM to emit intents that the validation set rejects. That means the LLM can make the right semantic decision and the app will discard it.

## Highest Priority Bugs And Risks

### 1. Semantic Router Rejects Its Own Prompted Intents

Evidence:

- `server_api/workflows/router.py` `SEMANTIC_WORKFLOW_INTENTS` omits `style_feedback`, `project_files`, and `project_progress`.
- `_semantic_intent_payload()` prompt lists all three as valid intents.
- If the LLM returns one of these prompt-listed intents, the backend rejects it with:
  - `if intent not in SEMANTIC_WORKFLOW_INTENTS: return {}`

Why it matters:

- This directly undermines the recent work to make the agent understand less explicit user requests.
- It explains some "robotic" or irrelevant fallback responses even when the semantic model was likely correct.
- It makes app behavior dependent on whether the regex fallback happens to catch the same wording.

Recommendation:

- Add the missing intents to `SEMANTIC_WORKFLOW_INTENTS`.
- Add a unit test that asserts every intent listed in the semantic prompt is present in the validation set.
- Consider defining intents once as structured data and generating both prompt text and validation from it.

### 2. App Boot Still Resets Workflow And File State

Evidence:

- `client/src/App.js` `CacheBootstrapper` calls `resetFileState()` before rendering the workflow provider.
- `client/src/contexts/WorkflowContext.js` `bootFreshSession()` calls:
  - `resetFileWorkspace()`
  - `clearLocalWorkflowInputs()`
  - `startNewWorkflowApi({ metadata: { created_from: "page_reload" } })`

Why it matters:

- This conflicts with the desired "one continuous big chat/workflow in the same session" model.
- It can erase mounted file indexes, selected paths, workflow context, and active runtime-facing state on reload.
- It makes debugging confusing because reloads create fresh workflow records and reset local state even if the user is still in the same browser session.

Recommendation:

- Replace fresh boot with resume-first boot:
  - call `getCurrentWorkflow()`;
  - hydrate file/project state from workflow metadata;
  - only reset when the user explicitly clicks New project or Reset workspace.
- Keep an explicit `session_generation` or `workflow_generation` field to invalidate stale cards without nuking the workspace.

### 3. "Persisted" App State Is Not Persisted

Evidence:

- `client/src/contexts/GlobalContext.js` imports `localforage`, but `usePersistedState(_key, defaultValue)` is a thin `useState` wrapper.
- `resetFileState()` removes localforage keys that are not actually written by `usePersistedState`.

Why it matters:

- The code reads as if local state persists, but it does not.
- This makes chat/workflow state behavior harder to reason about and increases hidden reliance on backend workflow records.

Recommendation:

- Either restore real persisted state for selected fields or rename this helper to make it honest.
- Prefer workflow-backed hydration for scientific project state, not browser-only caches.

### 4. Main Chat Routing Sends Nearly Every Message To The Workflow Agent

Evidence:

- `client/src/components/Chatbot.js` `shouldUseWorkflowAgent()` returns true for any non-empty query when a workflow exists:
  - `isWorkflowAgentQuery(...) || isWorkflowFollowUpQuery(...) || query.trim().length > 0`

Why it matters:

- The general RAG chat path is effectively dead in normal workflow sessions.
- The workflow agent has to answer everything, including ordinary conceptual questions and UI tone feedback.
- If the workflow agent is over-constrained, every response inherits the same robotic workflow template.

Recommendation:

- Route by intent class:
  - workflow agent for workflow state, app actions, mounted project state, and run orchestration;
  - docs/RAG for conceptual PyTC questions;
  - conversational model path for open-ended explanation or tone feedback.
- Keep a single visible chat, but allow multiple internal responders behind it.

### 5. Continuous Chat Is Split Between Browser SessionStorage And Server DB

Evidence:

- `Chatbot.js` stores visible messages in `sessionStorage` under `pytc.workflowAssistant.continuousChat.v1`.
- `server_api/workflows/router.py` persists workflow-agent exchanges to `chat_messages` through `_persist_workflow_agent_chat_exchange()`.
- The frontend does not hydrate visible chat from the workflow-agent conversation on boot.
- Legacy `/chat/conversations` endpoints still exist in `server_api/main.py`.

Why it matters:

- Closing and reopening the drawer in the same session works, but reloads and cross-device sessions are fragile.
- The backend has a richer durable history than the frontend uses.
- Stale card sanitization exists because old frontend-only cards can outlive their workflow.

Recommendation:

- Make server workflow chat the source of truth.
- Keep `sessionStorage` only as an optimistic display cache.
- Hydrate visible chat from `GET /workflow/{id}/agent/conversation` or equivalent.
- Store card/action state by workflow/action id, not just by serialized frontend messages.

### 6. Agent Action Execution Has Too Many Overlapping Concepts

Current concepts:

- Chat `actions`
- Chat `commands`
- Workflow `proposals`
- Durable `WorkflowCommand`
- `client_effects`
- `runtime_action`
- `pendingRuntimeAction`
- `lastClientEffects`

Why it matters:

- User-facing regressions have repeatedly appeared around "Approve" and "Run in app".
- `approveAgentAction()` applies client effects without runtime, runs a durable command, then sets `pendingRuntimeAction` to `monitor_training`, not `start_training`.
- Some actions execute immediately, some require approval, some create commands, and some only prefill UI.
- Failure states are not consistently appended to the chat as human-readable messages.

Recommendation:

- Introduce a typed `ActionExecution` state machine:
  - `proposed`
  - `approved`
  - `prefilling`
  - `ready_to_run`
  - `starting`
  - `running`
  - `completed`
  - `failed`
  - `rejected`
- Use one action envelope for all agent-to-app work:
  - `kind`
  - `risk`
  - `required_inputs`
  - `client_prefill`
  - `server_command`
  - `runtime_watch`
  - `expected_visible_result`
- Render that envelope consistently in chat, forms, and runtime panels.

### 7. Training Subset Plan Is Still Fragile

Evidence:

- `server_api/workflows/router.py` `_build_progress_training_subset_plan()` symlinks selected images and labels into:
  - `/home/weidf/demo_data/.pytc_training_subsets/<project>/<run>/image`
  - `/home/weidf/demo_data/.pytc_training_subsets/<project>/<run>/seg`
- `server_pytc/services/model.py` later converts directory inputs into file lists using a subset manifest or direct directory scan.
- The user already saw `ValueError: unrecognizable file format for .../workflow_.../image`, indicating at least one path reached PyTC as a directory instead of a concrete file/list-compatible input.

Why it matters:

- This is the heart of progress-based training. If it fails, "train on fully good volumes" cannot be trusted.
- PyTC configs may expect a single H5, a list field, a directory pattern, or a dataset-specific loader. A generic directory of symlinks is not a universal contract.

Recommendation:

- Make "multi-volume training set" a first-class runtime input:
  - either write a PyTC-compatible manifest that the dataset loader explicitly understands;
  - or create a combined H5/Zarr stack with matching image/label arrays;
  - or add a config schema path that is explicitly a list of volume files.
- Before launching, validate the final staged config by instantiating the dataset or running a dry-run loader check.
- Show the exact training volumes in the approval card with counts, status filters, and excluded volumes.

### 8. Config Mutation Is Duplicated Across Client And Worker

Evidence:

- `client/src/runtime/modelLaunch.js` mutates YAML for launch defaults and output/input paths.
- `server_pytc/services/model.py` also applies path overrides, sanitizes numeric values, resolves missing direct volume paths, coerces inference aug count, and applies "agent safe training defaults".

Why it matters:

- Client and worker can drift.
- Debugging staged configs is harder because multiple layers mutate YAML.
- The agent approval card may describe one config while the worker launches another.

Recommendation:

- Move all runtime config staging into the backend/worker.
- Let frontend only display proposed structured fields and call a `stage_config`/`preview_config` endpoint.
- Store a config diff artifact in workflow evidence for every launch.

### 9. Project Context Memory Is Written Into Mounted Source Directories

Evidence:

- `server_api/auth/router.py` writes `.pytc_project_context.json` into the mounted project directory.
- `reset_workspace()` deletes that hidden file from mounted roots.
- EHTool also writes `.pytc_proofreading.json` and `.pytc_instance_labels.tif` alongside source mask/data directories.

Why it matters:

- For real biology projects, writing hidden metadata into source data directories can surprise users.
- Resetting app workspace should not silently delete project memory unless the user explicitly asks.
- Multiple app-side hidden files create mixed ownership between source data and app state.

Recommendation:

- Store app-managed project memory in an app workspace keyed by project root hash.
- If writing sidecars into the project is useful, ask explicitly and show where they live.
- Split "unmount/reset app index" from "delete project context sidecars".

### 10. File Manager And Workflow Router Are Too Monolithic

Evidence:

- `client/src/views/FilesManager.js` is over 4,000 lines.
- `server_api/workflows/router.py` is around 7,900 lines.
- `server_api/main.py` and `server_api/auth/router.py` are also multi-thousand-line modules.

Why it matters:

- Cross-feature changes have high regression risk.
- The codebase lacks obvious ownership boundaries for:
  - project scanning;
  - project memory;
  - agent intent routing;
  - action proposal/execution;
  - progress tracking;
  - runtime launch;
  - file tree sync.

Recommendation:

- Split by domain:
  - `project_observation.py`
  - `project_progress.py`
  - `agent_intents.py`
  - `agent_actions.py`
  - `runtime_commands.py`
  - `project_memory.py`
  - frontend hooks/components for file tree, setup wizard, context audit, and role mapping.

## Agent And Orchestration Findings

### The Agent Needs A Canonical Observe-Orient-Act Loop

The current agent can inspect state, but the inspection is embedded inside `query_workflow_agent()`. A stronger architecture would define explicit tools:

- `list_project_tree(root, depth, filters)`
- `inspect_volume(path)`
- `sample_volume_slices(path, count, axes)`
- `discover_image_label_pairs(root)`
- `read_project_manifest(root)`
- `read_progress_tracker(workflow_id)`
- `update_project_memory(fact, source, confidence)`
- `stage_visualization(image, label, scales)`
- `stage_training_run(training_set, config, output)`
- `inspect_runtime_failure(run_id)`

The agent should call these tools as part of a bounded loop and return:

- a normal human response;
- an expandable trace of what it checked;
- one or more typed action proposals.

### Project Memory Should Be Structured, Versioned, And Source-Aware

The app already stores:

- `project_context`
- `project_observation`
- `project_progress_snapshot`
- `active_volume_pair`
- `volume_pair_discovery`
- `.pytc_project_context.json`
- `.pytc_proofreading.json`

But these are not yet one cohesive system. The project memory model should distinguish:

- User-provided facts: "we care about mitochondria", "prioritize accuracy"
- Mechanically verified facts: H5 shape, dtype, voxel size from metadata, pair shape match
- Agent inferences: likely image/seg pairing, likely dataset purpose
- Workflow decisions: selected active pair, selected training subset
- Runtime outcomes: checkpoint path, prediction path, proofread artifact path

Each memory item should carry:

- `key`
- `value`
- `source`
- `confidence`
- `observed_at`
- `valid_for_path`
- `supersedes`
- `needs_user_confirmation`

### The Agent Should Be Allowed To Be Human-Facing Without Losing Rigor

The recent `AssistantTrace` pattern is the right direction. The chat should speak normally:

- "I found two clean ground-truth volumes. I can train on those and leave the two draft masks out."

The expandable trace should carry rigor:

- files checked;
- status counts;
- exact paths;
- assumptions;
- reasons for excluding volumes.

Do not put all mechanical detail in the top-level chat message unless the user asks for it.

### The Agent Currently Offers Too Few Simultaneous Useful Actions

Evidence:

- `_one_app_suggestion()` intentionally reduces actions to a single primary action.

Why it matters:

- For a scientific workflow, the agent often should offer a small set of adjacent actions:
  - "View first pair"
  - "Open progress"
  - "Train on good masks"
  - "Proofread draft masks"
- Reducing to one action makes the agent feel less capable and forces additional chat turns.

Recommendation:

- Allow up to 2 or 3 action cards when they are distinct and safe.
- Group related cards under "I can do these next".
- Keep destructive or expensive actions approval-gated.

## UI Streamlining Opportunities

### Guided Project Intake Should Replace Blank Free Text

The current guided project setup is an improvement, but the product direction should be:

- Start with "I checked your folder" summary.
- Ask 3 to 5 concrete questions with selectable choices:
  - What are we segmenting?
  - What imaging modality is this?
  - Which masks are ground truth versus draft?
  - What should count as done?
  - Is speed or accuracy more important?
- Offer "I do not know" and "Use detected default" for each.
- Allow optional voice/free-text note after structured choices.

Biologists should not have to know what project context is useful to the agent.

### Progress Page Needs Direct Workflow Actions

Current state:

- The Progress page gives counts and manual status dropdowns.

Missing:

- Per-row actions:
  - View image/mask
  - Open proofreader
  - Mark as ground truth with note
  - Run inference on this volume
  - Exclude from training
- Multi-select actions:
  - Train on selected ground truth
  - Proofread selected draft masks
  - Segment selected missing masks
- Notes/reasons:
  - "marked ground truth by Adam"
  - "excluded because shape mismatch"

### Training Approval Card Needs A Compact Summary

The raw path-heavy card is hard to parse. A better training proposal card:

- Title: "Train on 2 ground-truth volumes"
- Summary chips:
  - Training set: 2 proofread GT
  - Targets after training: 2 missing masks
  - Excluded: 2 draft masks
  - Config: MitoEM2 Pyra demo
  - Output: `outputs/training/<run>`
- Expandable details:
  - exact paths;
  - config diff;
  - manifest path;
  - runtime defaults.
- Buttons:
  - Review in Train Model
  - Approve and start
  - Edit selection

### Runtime Pages Need Stronger "What Is Happening" State

Train/Run pages should visually separate:

- Proposed but not approved
- Prefilled and ready
- Submitted to worker
- Running
- Finished
- Failed

On failure, the page should offer:

- "Ask agent to inspect failure"
- "Open log"
- "Copy diagnostic bundle"
- "Retry with fixed config"

### File Manager Should Be Less Central To Everything

FilesManager now owns too many workflows:

- mounting;
- project setup;
- context editing;
- audit display;
- role mapping;
- file operations;
- preview;
- project suggestions;
- reset/unmount.

Recommended UI split:

- Files page: browsing, preview, mount/unmount
- Project Setup drawer/page: context, audit, role mapping
- Progress page: volume status and workflow actions
- Assistant panel: propose/reroute actions

## Runtime And Data Findings

### Neuroglancer Is Better, But Needs Metadata Spot-Checks

Good:

- Viewer URLs are retained server-side.
- Mixed-content handling and public base URL are handled.
- Scales are now required and pulled from workflow/project context.
- Folder-level inputs can resolve to concrete volume pairs.

Risk:

- Axis/order assumptions are still implicit. Volumes are treated as z,y,x after loading.
- The weird-looking MitoEM2 dummy data may be a real data-crop choice, an axis rendering issue, or a contrast/shape issue. The app has no first-class "volume sanity check" panel to explain this.

Recommendation:

- Add a volume inspector panel:
  - shape;
  - dtype;
  - min/max/percentiles;
  - voxel size;
  - selected dataset key inside H5;
  - thumbnail slices along z/y/x;
  - warnings for very small z depth, low dynamic range, wrong-looking axis ratio.

### EHTool Proofreading State Is Useful But Too Hidden

Good:

- `DataManager` persists instance edits to `.pytc_instance_labels.tif`.
- It persists review state to `.pytc_proofreading.json`.
- It records workflow events for classification and mask save.

Risks:

- `_data_managers` is an in-memory dict keyed by session id. Process restart reloads from DB paths, but cache behavior and multi-user/process behavior are not robust.
- Sidecar artifacts live next to source data.
- Project Progress does not yet directly consume proofreading completion in a first-class way.

Recommendation:

- Register proofread artifacts as workflow artifacts.
- Link proofread artifacts back to progress volumes.
- Use proofread completion to update `ground_truth` status automatically only after explicit "Use edits for training" or "Mark good" confirmation.

### Runtime Logging Is Broad But Needs Correlation

Good:

- Client event logging captures console/network/DOM/resource events.
- Server middleware logs requests and response codes.
- Worker logs runtime command, config snapshots, subprocess output, TensorBoard status, and artifacts.

Gaps:

- Client logs and server request logs are not consistently tied by a propagated `x-request-id`.
- Chat query -> proposal -> approval -> command -> worker process -> artifact is not one explicit trace id.
- Logging is very high volume and may leak paths/config text into app logs.

Recommendation:

- Add `workflow_trace_id` to every action card and propagate it through:
  - chat query;
  - proposal event;
  - command row;
  - API request;
  - worker runtime state;
  - app event log;
  - generated artifacts.
- Add redaction controls for paths and full config text when needed.

## File And Project Context Findings

### Project Mounting Can Be Expensive And Noisy

Evidence:

- Mounting recursively indexes source dirs into DB.
- Project scans skip some ignored names, but mounted tree can still include dot/cache directories.
- `get_files(parent)` repairs stale mounted entries and prunes uploads on requests.

Risks:

- Large biology projects can have huge folders.
- Folder refreshes can produce UI stalls or apparent empty folders if backend scans lag or fail.

Recommendation:

- Use lazy tree indexing by folder.
- Store scan status per folder:
  - unscanned;
  - scanning;
  - scanned;
  - failed;
  - stale.
- Surface scan errors and partial states in the UI.

### File Preview And Properties Are Partial

Evidence:

- File preview supports some image/TIFF paths but not HDF5 previews generally.
- Properties modal uses placeholder timestamps rather than backend metadata.

Recommendation:

- Use the volume inspector for HDF5/Zarr/N5.
- Do not show fake created/modified metadata.
- Add "copy absolute path" and "inspect datasets" for H5.

### Progress Pairing Is Heuristic

Evidence:

- `server_api/workflows/router.py` derives pair keys from file names and token matching.
- It uses markers like `gt`, `curated`, and `consensus` to infer ground truth.
- Manual overrides exist, but notes/reasons are not exposed in the UI.

Risks:

- Datasets with nonstandard naming can be mispaired.
- Draft segmentations can be treated as ground truth or vice versa if names are misleading.

Recommendation:

- Store explicit volume records:
  - `image_path`
  - `segmentation_path`
  - `segmentation_status`
  - `status_source`
  - `status_note`
  - `validated_shape_match`
  - `last_viewed_at`
  - `proofread_artifact_path`
- Let project setup confirm pair mapping once, then stop relying on repeated filename inference.

## Frontend Technical Findings

### API Base Pathing Is Confusing

Evidence:

- `apiClient` baseURL is `${origin}/api` in production.
- Workflow API methods call paths like `/api/workflows/current`, producing public paths like `/api/api/workflows/current`.
- Some endpoints use raw `axios` and `BASE_URL`; others use `apiClient`.

Why it matters:

- The app works because deployment routes have been adapted around this, but it is easy to break.
- Docs already mention both `/api/workflows` and `/api/api/workflows`.

Recommendation:

- Normalize frontend API paths:
  - baseURL should be origin only, and all paths include `/api`;
  - or baseURL should be `/api`, and paths must not start with `/api`.
- Add tests for deployed URL construction.

### Debug Logs Are Still In Production-Built Code

Evidence:

- `client/src/api.js`, `InputSelector.js`, `ModelTraining.js`, `ModelInference.js`, and EHTool router have debug `console.log`/diagnostic prints.
- `server_api/ehtool/router.py` prints "EHTOOL ROUTER MODULE LOADED - VERSION: DEBUG v2" at import time.

Recommendation:

- Gate debug logs behind a logging helper or env flag.
- Keep app-event logs structured and avoid duplicate raw console spam.

### Build Warnings Should Be Addressed

Current build warnings:

- EHTool hook dependency warnings in `DetectionWorkflow.js`
- EHTool hook dependency warnings in `ProofreadingEditor.js`
- Bundle size warning: main JS around 694 kB gzip

Recommendation:

- Fix hook dependencies deliberately. For canvas-heavy components, move imperative drawing functions into refs/callbacks to avoid stale closures.
- Code-split EHTool/proofreading and Neuroglancer-heavy paths so the first load is smaller.

## Backend Technical Findings

### Workflow Metadata JSON Is Carrying Too Much Contract

Examples:

- `project_context`
- `project_observation`
- `project_progress_snapshot`
- `project_progress_overrides`
- `active_volume_pair`
- `volume_pair_discovery`
- `neuroglancer_proofreading`
- runtime-ish fields

Risk:

- Important state has weak validation, weak migrations, and no typed ownership.

Recommendation:

- Keep metadata as an extension field, but move core concepts into typed tables or Pydantic schemas:
  - project memories;
  - volume records;
  - action executions;
  - runtime runs;
  - proofread artifacts.

### Legacy Generic Chat Has Process-Global State

Evidence:

- `server_api/main.py` has module-level `_active_convo_id` and `_chat_history` for generic chat.

Risk:

- Multi-user or multi-session chat can leak context or behave unpredictably.
- This is especially risky if one visible chat remains but routes between workflow and generic chat.

Recommendation:

- Remove process-global chat state.
- Persist all chat history by conversation id and workflow id.

### Durable Commands Only Support Training

Evidence:

- `/api/workflows/{workflow_id}/commands/{command_id}/run` rejects command types other than `start_training`.

Recommendation:

- Generalize durable commands for:
  - start training;
  - start inference;
  - run evaluation;
  - export evidence;
  - run data prep.
- Make command status the source of truth for action-card progress.

## Suggested Agent Role Expansion

### Near-Term Agent Capabilities

Add the following as typed, tested workflow tools:

- Read project summary
- List folders/files with filters
- Inspect H5/Zarr/TIFF volume metadata
- Discover and confirm image/label pairs
- Read and update project memory
- Read project progress
- Mark volume status with note
- Stage visualization for a selected pair
- Stage training from selected progress statuses
- Stage inference for selected missing volumes
- Inspect last runtime failure

### Medium-Term Agent Behavior

The agent should behave like:

1. Observe
   - Refresh project observation and progress.
   - Inspect relevant files or volume metadata.
2. Orient
   - Identify what is known, unknown, and risky.
   - Update project memory with sourced facts.
3. Propose
   - Provide a normal chat response.
   - Show trace in expandable UI.
   - Offer 1 to 3 action cards.
4. Act
   - Execute only approved or low-risk actions.
   - Keep visible status synced to command/runtime state.
5. Learn
   - Store what worked, what failed, and what the user corrected.

### Long-Term Agent Features

- Voice-guided project intake for biologists.
- Project "interview" mode that asks one concrete question at a time.
- Auto-generated project map:
  - folders;
  - image volumes;
  - masks;
  - checkpoints;
  - configs;
  - outputs.
- Agent-generated run notebook:
  - what was trained on;
  - what was excluded;
  - why;
  - model config diff;
  - results and next step.
- Failure triage:
  - parse runtime logs;
  - identify config/data mismatch;
  - propose specific fix;
  - generate retry card.

## Suggested Engineering Roadmap

### Immediate Stabilization

1. Fix semantic intent set mismatch.
2. Stop resetting workflow/file state on ordinary app boot.
3. Make visible chat hydrate from server workflow conversation.
4. Normalize API path handling.
5. Add unknown `navigate_to` validation so bad agent effects cannot blank the UI.
6. Make proposal approval append a visible chat status message and show action execution state.
7. Fix training subset launch contract with a dry-run dataset validation.

### Project Memory And Progress

1. Create a `project_memory` backend module with typed schemas.
2. Create explicit volume records from confirmed mappings.
3. Move progress tracker from repeated heuristics to stored volume state plus refreshable observations.
4. Connect proofread artifacts to progress volume statuses.
5. Add volume notes and row actions.

### Runtime And Agent Execution

1. Introduce `ActionExecution` as a single envelope for all app actions.
2. Generalize durable commands beyond training.
3. Centralize config staging and diff generation in backend/worker.
4. Propagate `workflow_trace_id` across chat, commands, worker logs, and artifacts.
5. Add "Inspect failure" action for failed runs.

### UI Polish

1. Replace blank/free-text project setup with a guided checklist and optional notes.
2. Add a persistent project status summary visible outside the Progress tab.
3. Add compact training/inference proposal cards with expandable technical details.
4. Add a volume inspector for H5/Zarr/TIFF shape, dtype, metadata, and thumbnails.
5. Code-split heavy proofread/3D modules.

## Specific Follow-Up Bugs To File

- `SEMANTIC_WORKFLOW_INTENTS` missing prompt-listed intents.
- `CacheBootstrapper` and `WorkflowProvider` boot reset conflict with continuous workflow sessions.
- `usePersistedState` name is misleading and unused `localforage` import should be reconciled.
- `shouldUseWorkflowAgent()` routes every non-empty workflow-session message to workflow agent.
- Training subset staging can pass directories where PyTC expects concrete volume files or list-compatible config.
- `approveAgentAction()` durable command branch switches to `monitor_training` after command submission, which hides whether the launch actually happened unless the runtime page watches correctly.
- `buildRuntimeOverridesFromEffects()` uses `inferenceConfigOriginPath` while most runtime paths expect `configOriginPath`.
- Project context/proofread sidecars are written into mounted source data directories.
- `reset_workspace()` deletes `.pytc_project_context.json` from mounted source roots.
- `server_api/ehtool/router.py` import-time diagnostic print should be removed or gated.
- `client/src/views/Monitoring.js` remains as dead code after Monitor tab sunset.
- Production build still contains several debug `console.log` calls.
- EHTool hook dependency warnings remain.
- Generic chat has process-global `_chat_history` / `_active_convo_id`.

## Closing Assessment

The app is close to a useful agentic workflow prototype, but the next jump is architectural rather than cosmetic. The right direction is not "more prompt engineering"; it is to give the agent a canonical project memory, typed observation tools, typed action execution, and a progress model that is not reconstructed from path heuristics every time.

Once those exist, the chat can become much more natural because the technical rigor can move into traces, cards, and project state rather than being jammed into every assistant message.
