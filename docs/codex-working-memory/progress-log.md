# PyTC Client Progress Log

Local working log for Codex sessions on `pytc-client`.

## 2026-04-10

- Created this local-only progress log outside the repo Git root.

## 2026-04-13

- Audited the codebase against the TOCHI prototype framing for iterative biomedical image segmentation.
- Verified the frontend production build succeeds, but with ESLint warnings and a large bundle warning.
- Verified intended Python tests via `uv run python -m pytest -q tests`; 23 passed and 1 failed in `test_write_temp_config_uses_origin_parent_for_relative_bases`.
- Found that plain `uv run pytest -q` collects the vendored `pytorch_connectomics` tree and fails during local package imports.
- Found that the React package has Jest test files but no `test` npm script.
- Created implementation branch `feat/workflow-spine` for the Workflow Spine milestone.
- Added backend workflow spine models/API: `WorkflowSession`, `WorkflowEvent`, current workflow creation, patch/list/append events, pending agent proposals, approval, rejection, and deterministic workflow-agent fallback.
- Wired workflow events into Neuroglancer visualization, model inference start, model training start, and EHTool dataset load/classify/save/export paths.
- Re-enabled Mask Proofreading by restoring the EHTool surface and passing the active `workflow_id` into EHTool dataset loading.
- Added frontend `WorkflowProvider`, API helpers, compact workflow timeline, workflow-aware chat query routing, proposal approve/reject controls, and a proofreading "Stage for retraining" action.
- Added pytest config to keep normal project tests scoped to `tests/` and ignore vendored `pytorch_connectomics`.
- Fixed the temp-config placement fixture to use the existing `configs/Lucchi-Mitochondria.yaml` config path.
- Added backend tests for workflow creation/update/events, approve/reject proposal flow, and EHTool load/classify/mask-save/export event logging.
- Verification: `uv run pytest -q tests/test_workflow_routes.py` passes with 3 tests.
- Verification: `uv run pytest -q` passes with 27 tests; pytest now ignores vendored `pytorch_connectomics` through `pytest.ini`.
- Verification: `uv run python -m pytest -q tests` passes with 27 tests.
- Verification: `npm --prefix client test -- --watchAll=false` passes with 7 suites / 14 tests. The command prints a stale `baseline-browser-mapping` warning.
- Verification: `npm --prefix client run build` completes. It still reports pre-existing ESLint warnings in FilePickerModal, YamlFileUploader, EHTool/DetectionWorkflow/ProofreadingEditor, FilesManager, and Project Manager modules, plus the existing bundle-size warning.
- Manual browser smoke was not run in this pass; the EHTool workflow behavior is covered by backend API tests and frontend unit tests, but the full browser sequence with a human editing a mask remains a follow-up.
- Committed implementation in two scoped commits:
  - `2b48cf5` - `Add backend workflow spine`
  - `fa97e5e` - `Wire workflow spine into frontend`
- Push note: push to `sam4coding` was rejected by remote permissions; branch pushed successfully to `origin/feat/workflow-spine`.
- Investigated the AI assistant "Network Error" path. The running API process was configured with `OLLAMA_BASE_URL=http://cscigpu08.bc.edu:11434`, `OLLAMA_MODEL=gpt-oss:20b`, and `OLLAMA_EMBED_MODEL=qwen3-embedding:8b`; that remote Ollama endpoint timed out from this machine.
- Changed the LLM setup so chat no longer silently defaults to localhost or a hardcoded remote. `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_EMBED_MODEL` must now be exported before launch, and `OLLAMA_BASE_URL` must include an explicit service port.
- Improved chat/helper error handling so backend LLM initialization and invocation failures return a structured user-facing message telling the user to contact their system administrator with the underlying error. The frontend now displays that message instead of raw `Network Error` where possible.
- Verification: `uv run pytest -q tests/test_chatbot_config.py` passes with 3 tests.
- Verification: `uv run pytest -q` passes with 30 tests.
- Verification: `npm --prefix client test -- --watchAll=false` passes with 7 suites / 14 tests.
- Verification: `npm --prefix client run build` completes with the existing lint and bundle-size warnings.
- Committed and pushed LLM configuration/error-handling changes as `5a21f15` (`Improve LLM configuration errors`) to `origin/feat/workflow-spine`.
- Diagnosed chat failure showing `AssertionError` in UI: FAISS index embedding dimension mismatch (`assert d == self.d`) when using local `nomic-embed-text` against an existing index built with a different embedding model.
- Implemented chatbot resilience fix: if semantic retrieval fails, disable RAG for the process and transparently fall back to keyword-based documentation search instead of failing the request.
- Verification: direct `build_chain().invoke(...)` no longer crashes under local `OLLAMA_MODEL=llama3.2:1b` and `OLLAMA_EMBED_MODEL=nomic-embed-text`.
- Committed and pushed fix as `10d7766` (`Fallback to keyword docs when RAG retrieval fails`) to `origin/feat/workflow-spine`.
- Added high-visibility backend chat logging (local working tree) to diagnose stalls:
  - Request IDs for `/chat/query` and `/chat/helper/query`.
  - Start/end timing logs with query/history sizes.
  - Periodic progress heartbeat every ~5s while waiting for `chain.invoke(...)`.
  - Helper/main chain initialization reuse/latency logs.
  - Tool-level duration logs for doc search and training/inference delegation.
  - Exception logs now include type/repr + traceback in chat paths.
- Local environment setup for LLM chat:
  - Verified local Ollama daemon is reachable at `http://127.0.0.1:11434`.
  - Pulled small local chat model `llama3.2:1b` and embedding model `nomic-embed-text`.
  - Added persistent shell exports in `~/.zshrc`:
    - `OLLAMA_BASE_URL=http://127.0.0.1:11434`
    - `OLLAMA_MODEL=llama3.2:1b`
    - `OLLAMA_EMBED_MODEL=nomic-embed-text`
  - Smoke-verified backend startup with these env vars on API port `4247`.
  - Verification: `GET /health` returned `{"status":"ok"}`.
  - Verification: `GET /chat/status` returned `{"configured":true,"error":null}`.
- Rewrote manuscript Section 3/4 to foreground agentic collaboration:
  - Added explicit agentic domain goal `G6` and autonomy requirement `R9`.
  - Added draft task `T7` for bounded multi-step agent orchestration.
  - Reframed Section 4 around agentic interaction modes (`M1` on-demand guidance, `M2` approve-then-execute, `M3` draft bounded autonomy).
  - Added a new feature mapping table (`Feature x Status x Agentic Function x G/R/T`) in Section 4.
  - Marked all future autonomy features as draft/ideation, not implemented.
- Rewrote Introduction framing/contributions to position the assistant as a workflow harness rather than chat-only UI.
- Re-rendered manuscript PDF after each text-edit round via `latexmk -pdf -interaction=nonstopmode sample-manuscript.tex`.
- Manuscript styling update: removed explicit "implemented/draft/not yet implemented" status language from Sections 3/4 and feature table so the paper text reads as an integrated system design narrative.
- Internal-only status tracking retained in local notes (`progress-log.md`, `research-log.md`) for implementation reality and planning.
- Read/synthesized 9 recent TOCHI papers from local PDFs to extract writing structure patterns (contribution framing, question-driven sectioning, discussion/limitations calibration, and evidence traceability).
- Applied a TOCHI-style manuscript revision pass:
  - Added formative analysis questions (`FQ1`, `FQ2`) in Section 3.
  - Added a Goal→Requirement→Task traceability table (`tab:grt-traceability`).
  - Tightened Section 4 architecture framing with explicit workflow-state/agent-mediation/controlled-execution layers.
  - Expanded Section 5 from placeholder bullets into a rigorous evaluation protocol (`EQ1`--`EQ3`, study phases, measures, analysis plan).
- Recompiled manuscript PDF after each edit pass: `sample-manuscript.pdf` updated successfully (citations still unresolved as expected with placeholder keys).
- Added internal synthesis artifact for later paper-assistant handoff: `/Users/adamg/seg.bio/pytc-client-codex-notes/tochi-writing-synthesis.md`.
- Expanded manuscript prose substantially to better match recent TOCHI article length/style:
  - Section 3: added richer formative-method detail, workflow breakdown taxonomy (B1--B5), and stronger narrative linking observations to requirements.
  - Section 4: added architecture overview, deeper mode descriptions (M1--M3), fuller feature realization text (including F9--F11), and a closed-loop interaction walkthrough.
  - Section 5: retained structured evaluation protocol and now sits within a fuller narrative flow.
  - Added substantive draft text for `Discussion` and `Limitations/Conclusions` with explicit `\grace{TODO...}` anchors for user-fill details.
- Re-rendered manuscript after this text expansion: `sample-manuscript.pdf` now builds to 22 pages.
- Compile status remains: unresolved citation keys (expected placeholders), plus minor overfull/underfull box warnings in dense table/evaluation lines.
- Corrected overclaim issue in manuscript: removed language implying interviews were already completed.
- Reframed Section 3 as an explicit planned two-phase case study:
  - Phase I requirements interviews (derive/validate goals, requirements, tasks),
  - Phase II prototype user study (evaluate requirement coverage and agentic workflow support).
- Added clearer cross-phase analysis narrative showing how Phase I outputs constrain Phase II evaluation claims.
- Updated introduction/contribution wording to match pre-data status and avoid empirical-result claims.
- Re-rendered manuscript PDF again; current output is 23 pages with expected placeholder citation warnings.

## 2026-04-13 - Codex Draft PR Consolidation Wave

- Created clean integration worktree/branch from `origin/feat/workflow-spine`:
  - worktree: `/Users/adamg/seg.bio/pytc-client-codex-integration`
  - branch: `feat/codex-wave-integration`
- Ported codex draft outputs into existing architecture (behavior-first, no `server_api/workflow/*` path adoption):
  - Backend:
    - added hotspots + impact preview in workflow router,
    - added `GET /api/workflows/{id}/metrics`,
    - added `POST /api/workflows/{id}/export-bundle`,
    - added workflow evidence utility modules (`metrics.py`, `bundle_export.py`, `evidence_export.py`) and research doc.
  - Chat observability:
    - added request lifecycle summary logger (`server_api/chatbot/logging_utils.py`),
    - added request-id/duration/status/error summary logging in `/chat/query` and `/chat/helper/query`,
    - retained progress-heartbeat style prints for long-running chain invocation diagnostics.
  - Frontend:
    - added workflow timeline actor/event filters,
    - added richer pending-proposal cards with structured fields + approve/reject controls,
    - wired workflow insights loading (`hotspots`, `impactPreview`) through `WorkflowContext`.
- Added/updated tests:
  - backend: `test_workflow_metrics.py`, `test_workflow_export_bundle.py`, `test_workflow_evidence_export.py`, `test_workflow_spine_smoke.py`, `test_chat_logging_fields.py`, expanded `test_workflow_routes.py`,
  - frontend: `agentProposalCards.test.js`, `workflowTimelineFilters.test.js`, updated workflow timeline/context tests.
- Verification run in integration worktree:
  - `python3 -m pytest -q tests/test_workflow_routes.py tests/test_workflow_spine_smoke.py tests/test_chat_logging_fields.py tests/test_workflow_metrics.py tests/test_workflow_export_bundle.py tests/test_workflow_evidence_export.py`
    - result: `2 passed, 5 skipped` (dependency-gated skips in this shell),
  - `npm --prefix client test -- --watchAll=false --runInBand`
    - result: `9 passed`,
  - `npm --prefix client run build`
    - result: success (existing unrelated eslint warnings remain).
- Commit split on integration branch:
  - `0bfcee9` `feat(workflows): add hotspots insights, metrics, and export bundle`
  - `74c0d3e` `feat(chat): add request lifecycle observability logs`
  - `ecc2493` `feat(chat-ui): add timeline filters and proposal cards`
  - `0ace093` merge sync from `origin/main` with conflict resolution preserving required-env chatbot behavior.
- Pushed branch and opened consolidated draft PR:
  - https://github.com/PytorchConnectomics/pytc-client/pull/165
- Closed codex source draft PRs `#139`-`#164` (codex branches) with redirect comment to PR `#165` for single-threaded review.

## 2026-04-15 - Local Integration Launcher

- Added temporary local-only helper script for manually running the integration worktree:
  - `/Users/adamg/seg.bio/pytc-client-codex-integration/.local/play-integration.sh`
- Added worktree-local exclude entry so `.local/` stays out of git for this worktree.
- Purpose:
  - single-command local start/stop/status/logs while `scripts/start.sh` and Electron remain brittle on `feat/codex-wave-integration`.
- Cleanup note:
  - remove this helper before any commit from the integration worktree, or keep it strictly local-only and untracked.

## 2026-04-16 - Mainline Moved Past Codex Integration Branch

- Fetched remote state and updated branch understanding after new merge to `origin/main`.
- `origin/main` now points to:
  - `5aa4eaa` `Fix PR 166 runtime cleanup and chatbot test collection`
- Additional recent mainline commits ahead of the old codex integration base:
  - `e8ecce8` `fixed isue with incorrect arguments for triaingin`
  - `9cf43fc` `put training, inference, eval info into rag docs`
- Important consequence:
  - the codex consolidation branch `feat/codex-wave-integration` was **not** merged into `main`;
  - draft PR `#165` remains open/draft;
  - `origin/main` and `origin/feat/codex-wave-integration` now diverge substantially.
- Operational interpretation:
  - authoritative branch for new work/testing is now `origin/main` plus any fresh feature branch cut from it;
  - the integration worktree remains useful as a reference branch for selectively porting codex workflow features forward, but should not be treated as current truth.
- Local caveat:
  - the integration worktree also has local-only runtime fixes (`pyproject.toml`, `uv.lock`) that were made to get it booting on this machine and are not part of remote `feat/codex-wave-integration`.

## 2026-04-16 - Workflow Wave Forward-Port Onto Current Main

- Created fresh branch from current mainline in primary checkout:
  - branch: `feat/workflow-wave-forward-port`
  - base: `origin/main` at `5aa4eaa`
- Forward-ported the useful codex workflow-wave commits in dependency order:
  - `2b48cf5` backend workflow spine
  - `0bfcee9` workflow metrics/export/hotspots/evidence
  - `74c0d3e` chat request lifecycle logging
  - `fa97e5e` frontend workflow spine
  - `ecc2493` timeline filters + proposal cards
- Resolved drift against current mainline:
  - kept current `server_api.main` chatbot/runtime behavior while layering workflow and logging hooks,
  - kept current frontend layout (no project-manager tab resurrection),
  - fixed test path drift in `Views.test.js` and `MaskProofreading.test.js`.
- Fixed editable dependency packaging mismatch in repo proper:
  - `pyproject.toml` now references editable package name `connectomics`
  - refreshed `uv.lock`
- Verification on forward-port branch:
  - `npm --prefix client test -- --watchAll=false --runInBand`
    - result: `9 passed`
  - `npm --prefix client run build`
    - result: success with existing unrelated eslint warnings
  - `uv run pytest -q tests/test_workflow_routes.py tests/test_workflow_spine_smoke.py tests/test_chat_logging_fields.py tests/test_workflow_metrics.py tests/test_workflow_export_bundle.py tests/test_workflow_evidence_export.py`
    - result: `11 passed`
  - `uv run pytest -q tests/test_pytc_runtime_routes.py tests/test_worker_model_service.py`
    - result: `13 passed`
- Current interpretation:
  - this fresh branch is the right candidate for review instead of stale PR `#165`.

## 2026-05-03 - Workflow Context and Agent Orchestration Hardening

- Investigated the project-context ingestion path after the visualization UI kept surfacing stale `30,6,6` voxel scales.
- Removed remaining live coupling where viewer-loaded visualization scales were written back into `metadata.project_context.voxel_size_nm`; viewer scale choices now stay in `metadata.visualization_scales` with a visualization-specific source.
- Hardened workspace reset/new-workflow behavior:
  - frontend reset effects clear local training/inference/visualization inputs,
  - workflow metadata clears `project_context`, `visualization_scales`, `active_volume_pair`, and marks `needs_project_context`,
  - new workflow startup also clears local workflow form state.
- Tightened project-context sidecar access:
  - `GET/PUT/DELETE /files/project-context` now require the requested directory to be a managed upload path or mounted root/descendant for the current user,
  - tests now mount temp project roots before saving/deleting project context profiles.
- Fixed approval semantics for assistant cards:
  - risky non-training cards now create `run_client_effects` approval proposals instead of directly executing,
  - training proposals still create durable `start_training_run` commands,
  - approval cards show generic app-action proposal details.
- Connected approved durable training commands to the command runner:
  - frontend approval now runs UI prefill effects with `runtime_action` stripped,
  - backend command runner records accepted training launches as `submitted` instead of `completed`,
  - `WorkflowCommand` accepts the new `submitted` status.
- Reduced stale chat-card risk:
  - persisted workflow-agent chat messages now store `workflow_id`,
  - loading a conversation strips actions/commands/proposals from assistant messages bound to a different workflow,
  - workflow-agent queries refresh workflow state and recommendation after the backend mutates context.
- Narrowed chatbot routing so arbitrary nonempty text no longer always goes through the workflow orchestrator; greetings, slash commands, and workflow/domain language still route to the workflow agent.
- Added coverage:
  - risky non-training app cards must create approval proposals before running,
  - stale workflow-bound chat history must not render runnable cards,
  - `run_client_effects` backend approvals return client effects without creating commands,
  - durable training commands now assert `submitted`.
- Verification:
  - `.venv/bin/python -m py_compile server_api/main.py server_api/workflows/router.py server_api/workflows/service.py server_api/auth/router.py server_api/auth/models.py` passed.
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js src/contexts/WorkflowContext.test.js src/__tests__/agentProposalCards.test.js --watchAll=false` passed: 30 tests.
  - `.venv/bin/python -m pytest tests/test_pytc_runtime_routes.py tests/test_file_workspace_routes.py tests/test_workflow_routes.py -q` passed: 81 tests, 5 subtests.
  - `npm run build` passed with existing EHTool hook dependency warnings.
- Operational state:
  - restarted the local API server from this checkout on port `4242` via detached `setsid` launch so the backend changes are live.
  - follow-up repair after browser 502s: `demo.seg.bio` nginx proxies `/api/` to `127.0.0.1:4342`, so started a demo API process with `PYTC_API_PORT=4342`, `PYTC_NEUROGLANCER_PORT=4344`, and `PYTC_WORKER_URL=localhost:4243`.
  - deployed `client/build/` to `/var/www/demo.seg.bio`; public `demo.seg.bio` now serves `main.e67c5997.js`.
  - verified public routes after repair: `https://demo.seg.bio/api/api/workflows/current`, `https://demo.seg.bio/api/files?parent=root`, and `https://demo.seg.bio/api/files/project-suggestions` returned `200`.
- Remaining known gap:
  - generic non-training client actions are approval-gated, but still execute through client effects after approval; deeper durable command coverage is still needed for inference/proofreading/export/reset.

## 2026-05-03 - Project Setup Context Editing

- Updated the start-project confirmation modal so absorbed project context is editable item by item before confirmation.
- Replaced the read-only generic context chips with editable concrete assumptions:
  - imaging modality,
  - target structure,
  - voxel size in z/y/x nm,
  - freeform notes.
- Removed generic "goal", "data", "priority", and "labels" from the project brief display and generated summary because they were acting like boilerplate for every imported project.
- Stopped inventing `task_goal`, `data_unit`, and `optimization_priority` defaults from folder profiles; project suggestions now only provide concrete context defaults from content hints such as modality, target, and voxel size.
- Confirmation now stores the edited context into workflow metadata and uses edited voxel size to set `metadata.visualization_scales`.
- Verification:
  - `npm test -- --runTestsByPath src/views/FilesManager.test.js src/utils/projectSuggestions.test.js --watchAll=false` passed: 21 tests.
  - `npm run build` passed with existing EHTool hook dependency warnings.
- Operational state:
  - deployed the rebuilt frontend to `/var/www/demo.seg.bio`; public `demo.seg.bio` now serves `main.92eb5817.js`.

## 2026-05-03 - Chat Log Failure Follow-Up Routing and LLM Defaults

- Investigated the browser-side `/api/chat/query` 503s from the public demo using `.logs/app/app-events.jsonl` and `.logs/start/demo-api-server.log`.
- Root cause:
  - the UI routed workflow follow-ups like "can we take a look at it first?" and "what?" to generic docs chat instead of the workflow orchestrator,
  - generic docs chat was launched without Ollama env vars and fell back to stale defaults (`llama3.1:8b` and `nomic-embed-text:latest`), while the installed local models are `qwen3.5:9b` and `qwen3-embedding:8b`.
- Fixed frontend chat routing so short contextual follow-ups after a `workflow_orchestrator` response stay with the workflow agent, while first-message unrelated gibberish still routes to generic chat/direct guard.
- Hardened generic chat backend behavior:
  - `/chat/query` now returns a plain degraded assistant response with `source=llm_unavailable` instead of a raw 503 when the docs LLM cannot initialize or invoke,
  - `/chat/clear` no longer initializes the LLM, because clearing memory should work even when docs chat is down.
- Aligned local defaults and launch scripts with the bundled FAISS index and installed models:
  - `DEFAULT_OLLAMA_MODEL=qwen3.5:9b`,
  - `DEFAULT_OLLAMA_EMBED_MODEL=qwen3-embedding:8b`,
  - updated `scripts/start.sh`, `scripts/dev.sh`, `rag_eval.py`, and README notes.
- Verification:
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 17 tests.
  - `.venv/bin/python -m pytest -q tests/test_workflow_routes.py -k 'general_chat or clear_chat'` passed: 4 tests.
  - `.venv/bin/python -m pytest -q tests/test_chatbot_faiss_generation.py` passed: 11 tests.
  - `.venv/bin/python -m py_compile server_api/main.py server_api/chatbot/chatbot.py server_api/chatbot/update_faiss.py server_api/chatbot/rag_eval.py` passed.
  - `npm run build` passed with existing EHTool hook dependency warnings.
- Operational state:
  - deployed the rebuilt frontend to `/var/www/demo.seg.bio`; public `demo.seg.bio` now serves `main.fae73634.js`.
  - restarted the public demo API on port `4342` with `OLLAMA_BASE_URL=http://127.0.0.1:11434`, `OLLAMA_MODEL=qwen3.5:9b`, and `OLLAMA_EMBED_MODEL=qwen3-embedding:8b`.
  - verified `https://demo.seg.bio/api/chat/status` returns `{"configured":true,"error":null}`.
  - verified public generic chat returns `200` from `https://demo.seg.bio/api/chat/query` and `/chat/clear` returns `200`.

## 2026-05-03 - Comprehensive Runtime Logging and Neuroglancer HTTPS Repair

- Investigated the black Neuroglancer viewer reported from the public demo.
- Root cause from logs + browser screenshot:
  - `/api/neuroglancer` succeeded and resolved folder inputs to concrete HDF5 volumes,
  - the returned viewer URL was `http://demo.seg.bio:4344/v/...`,
  - the app was loaded from `https://demo.seg.bio`, so the browser blocked the iframe as mixed content.
- Repaired the public runtime contract:
  - restarted the public API on port `4342` with `PYTC_NEUROGLANCER_PUBLIC_BASE=https://demo.seg.bio/neuroglancer`,
  - verified `/api/neuroglancer` now returns `https://demo.seg.bio/neuroglancer/v/...`,
  - verified the HTTPS proxied Neuroglancer HTML and bundle load through nginx/Cloudflare.
- Expanded frontend runtime logging in `client/src/logging/appEventLog.js`:
  - console output is captured by default,
  - fetch and XMLHttpRequest request/response/failure events are logged,
  - DOM clicks, form/input/change/key/focus/drag/drop/paste events are logged with sanitized target metadata,
  - resource load failures and resource timing entries are logged,
  - navigation, hash/history changes, focus/blur, online/offline, visibility, and postMessage events are logged.
- Expanded visualization-specific logging:
  - viewer URL receipt,
  - mixed-content detection before iframe mount,
  - iframe mount/load/error events,
  - viewer load failures with paths, scales, workflow id, and error detail.
- Expanded backend Neuroglancer logging:
  - `neuroglancer_request_prepared` captures requested paths, scales, workflow id, content type, host/forwarded headers, and configured public base,
  - `neuroglancer_viewer_created` captures internal viewer URL, public URL, scheme, bind host/port, resolved paths, volume shapes, scales, and workflow id.
- Verification:
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js src/views/FilesManager.test.js --watchAll=false` passed: 27 tests.
  - `.venv/bin/python -m py_compile server_api/main.py` passed.
  - `.venv/bin/python -m pytest -q tests/test_neuroglancer_url_contract.py tests/test_runtime_settings.py tests/test_neuroglancer_volume_normalization.py` passed: 18 tests.
  - `npm run build` passed with existing EHTool hook dependency warnings.
  - deployed `client/build/` to `/var/www/demo.seg.bio`; public `demo.seg.bio` now serves `main.ee2e6427.js`.
  - smoke-posted `/api/app/log-event`; event appeared in `.logs/app/app-events.jsonl`.

## 2026-05-03 - Restore Workflow Action Cards for Plain Data-Viewing Requests

- Investigated why "can we view some data" produced a plain docs answer instead of the workflow agent's executable "View data" card.
- Logs showed the regression clearly:
  - client event `llm_chat_sent`,
  - `workflowId=58`,
  - query preview `can we view some data`,
  - request went to `/api/chat/query` instead of the workflow orchestrator.
- Root cause: client-side workflow routing covered `visualize`, `viewer`, and concrete object words, but missed plain action phrases like `view some data`.
- Added workflow-agent action regexes for direct app routines:
  - `view/show/open/inspect/see ... data|volume|image|label|mask|segmentation`,
  - `look at ... data|volume|image|label|mask|segmentation`,
  - `run/start/launch ... app|model|inference|training|proofread|viewer|visualization`.
- Added frontend coverage asserting `can we view some data` routes to `queryAgent`, not generic chat, and renders the `View data` action card with `Run in app`.
- Verification:
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 18 tests.
  - `npm run build` passed with existing EHTool hook dependency warnings.
- Operational state:
  - deployed rebuilt frontend to `/var/www/demo.seg.bio`; public `demo.seg.bio` now serves `main.db5029c5.js`.

## 2026-05-03 - Make Active Workflow Chat Default to Runnable Orchestrator

- Investigated the follow-up regression where `can we vis some data` still produced a generic docs response.
- Logs showed the exact failure:
  - `dom_keydown` captured the submitted text,
  - client emitted `llm_chat_sent` with `workflowId=61`,
  - the request went to `/api/chat/query` instead of the workflow orchestrator,
  - generic docs chat took ~27s and returned instructions instead of action cards.
- Changed active-workflow chat routing so readable messages default to the workflow orchestrator when a workflow is mounted; only obvious single-token gibberish still goes to generic chat/direct guard.
- Added explicit client routing support for shorthand visualization language:
  - `vis`,
  - `viz`,
  - `view/show/open/inspect/see ... data|volume|image|label|mask|segmentation`.
- Added backend workflow-agent visualization detection for `vis`/`viz` so direct API calls also produce `open-visualization` actions.
- Added coverage:
  - `can we vis some data` routes to `queryAgent`, not generic chat, and renders `View data` with `Run in app`,
  - readable active-workflow requests such as `can you help me figure this out` route to the orchestrator by default,
  - backend `/agent/query` maps `can we vis some data` to `intent=view_data` and `open-visualization`.
- Verification:
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 20 tests.
  - `.venv/bin/python -m pytest -q tests/test_workflow_routes.py -k visualize_request_populates_viewer_paths_not_status` passed: 1 test.
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed.
  - `npm run build` passed with existing EHTool hook dependency warnings.
- Operational state:
  - deployed rebuilt frontend to `/var/www/demo.seg.bio`; public `demo.seg.bio` now serves `main.b529ca4e.js`.
  - restarted the public API on port `4342` with the same Neuroglancer and Ollama env vars.
  - verified public `POST /api/api/workflows/61/agent/query` with `can we vis some data` returns `source=workflow_orchestrator`, `intent=view_data`, and an `open-visualization` action with `run_label=Run in app`.

## 2026-05-03 - Keep Agent-Launched Neuroglancer Viewers Alive

- Investigated why `Run in app` from the assistant's `View data` action card opened a black Neuroglancer iframe while the form path was healthier.
- Logs and direct curls showed the generated viewer token was already `404` at `127.0.0.1:4344` immediately after `/api/neuroglancer` returned.
- Root cause: Neuroglancer's Python server stores viewers in a weak-reference map; `server_api.main` created a local `neuroglancer.Viewer()` and returned its URL without keeping a strong server-side reference.
- Added a bounded, expiring in-memory viewer registry in `server_api/main.py`:
  - retains visualization and proofreading viewers after URL creation,
  - defaults to 12 live viewers for 2 hours,
  - evicts old viewers by TTL/capacity,
  - logs `neuroglancer_viewer_retained` with token, mode, paths, count, TTL, and evictions.
- Hardened `/neuroglancer` JSON parsing to accept `image_path`/`imagePath` aliases and return `400` for missing image/scales instead of throwing a raw `KeyError`.
- Verification:
  - `.venv/bin/python -m py_compile server_api/main.py` passed.
  - `.venv/bin/python -m pytest -q tests/test_neuroglancer_url_contract.py` passed: 5 tests.
  - restarted public API as PID `1794274` on port `4342` with `PYTC_NEUROGLANCER_PUBLIC_BASE=https://demo.seg.bio/neuroglancer`.
  - public `POST /api/neuroglancer` returned viewer `51d03712242b656c17f3985287555c380968cfe4`.
  - verified public and local viewer HTML, `main.bundle.js`, `main.bundle.css`, and `?refresh=...` iframe URLs all return `200`.

## 2026-05-03 - Repair Assistant Choose-Data Actions and Stale File Trees

- Investigated the report that the assistant's `Choose data` Run in app action only opened Files and did not provide a way to choose training/visualization volumes.
- Investigated why mounted project folders appeared empty after earlier workspace/index resets.
- Log evidence:
  - browser session kept clicking old folder ids such as `/files?parent=5`, `/files?parent=4`, and `/files?parent=3`;
  - those ids were no longer present in the server file index, but the API previously returned `200 []`, so the stale client tree looked like real empty folders.
- Backend fix:
  - `/files?parent=<id>` now validates that non-root parents still exist as folders for the current user;
  - missing/stale parents return `404 Folder is no longer mounted or indexed: <id>` instead of an empty list.
- Files UI fix:
  - root and active folder refreshes now force-fetch on initial load, focus, and visibility restore;
  - stale parent 404s log `files_parent_missing_refreshed`, remove the stale subtree, and refresh root;
  - fresh root/current-folder loads reconcile the active folder if it was removed by server truth.
- Assistant action fix:
  - workflow `Choose data` / `Choose labels` actions now include `runtime_action.kind=choose_project_data`;
  - Files consumes that runtime action by opening the project setup/data mapping confirmation, preferring mounted/recommended projects and falling back to mounted root folders;
  - the action risk is now `prefills_form`, so the card badge displays `sets form` instead of `view only`.
- Verification:
  - `npm test -- --runTestsByPath src/views/FilesManager.test.js --watchAll=false` passed: 11 tests.
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 20 tests.
  - `.venv/bin/python -m pytest -q tests/test_file_workspace_routes.py -k 'missing_parent_file_listing_returns_404 or mount_directory_skips_os_metadata_files'` passed: 2 tests.
  - `.venv/bin/python -m pytest -q tests/test_workflow_routes.py -k 'agent_train_model_names_missing_label_blocker or visualize_request_populates_viewer_paths_not_status'` passed: 2 tests.
  - `.venv/bin/python -m py_compile server_api/auth/router.py server_api/workflows/router.py` passed.
  - `npm run build` passed; remaining warnings are pre-existing EHTool hook dependency warnings.
- Operational state:
  - deployed rebuilt frontend to `/var/www/demo.seg.bio`; public `demo.seg.bio` now serves `main.45fb31fd.js`.
  - restarted public API as PID `1860978` on port `4342`.
  - verified `GET /health` returns OK.
  - verified `GET /files?parent=999999` returns `404`.
  - verified public `asset-manifest.json` references `main.45fb31fd.js`.

## 2026-05-03 - Add Read-Only Project Observation to Workflow Agent

- Addressed the core architecture gap highlighted by the chat: the workflow agent was answering mostly from workflow fields and cached context instead of probing the mounted project before responding.
- Added a read-only project observation pass to every workflow-agent query:
  - derives candidate project roots from `workflow.dataset_path`, current workflow file paths, and mounted root folders;
  - scans candidate roots with the existing `_scan_project_profile()` project profiler;
  - extracts observed volume sets with absolute image/label paths, role counts, current-set markers, roots, and context hints;
  - stores a compact `metadata.project_observation` ledger with `observed_at`, roots, volume sets, errors, and current markers;
  - logs `project_observed` app events with root and volume-set counts.
- Extended semantic workflow state with the observed project summary so future semantic routing can see discovered volume sets, not only static workflow fields.
- Added alternate data-set handling:
  - detects phrasing like `another aptly named pair`, `other set`, `different pair`, etc.;
  - forces these requests into `view_data` instead of letting `image and seg` drift into segmentation/model-launch context collection;
  - selects a non-current observed image/seg volume set when one exists;
  - bases "current set" primarily on the image root so shared label folders do not incorrectly mark every set as current.
- Result for the screenshot-style query:
  - the agent should inspect the project tree, find the alternate image/seg set, populate the visualization action with that set's paths, and avoid asking for modality/target/priority again.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed.
  - `.venv/bin/python -m pytest -q tests/test_workflow_routes.py -k 'alternate_volume_set or visualize_request_discovers_directory_pairs or visualize_request_populates_viewer_paths_not_status'` passed: 3 tests.
  - `.venv/bin/python -m pytest -q tests/test_workflow_routes.py` passed: 41 tests.
- Operational state:
  - restarted the public API as PID `1908400` on port `4342`.
  - verified local `GET /health` and public `GET /api/health` return OK.
  - did not mutate the live demo workflow for a synthetic smoke because the unauthenticated current workflow was empty after page reload.

## 2026-05-03 - Humanize Workflow Agent Responses and Add Inspectable Traces

- Addressed the regression where the workflow agent sounded like an internal planner:
  - converted rigid `Do this` / `Why` / `Current read` style strings into normal chat responses while preserving rationale and recommendation wording;
  - kept runnable app cards and command blocks intact so the agent can still propose direct `Run in app` routines;
  - added a collapsed `What I checked` trace in chat for observable context such as workflow state, project file scans, and prepared app cards.
- Persisted trace data in chat history:
  - added `chat_messages.trace_json`,
  - includes `trace` on conversation message responses and workflow-agent query responses,
  - clears trace/actions/commands/proposals from stale loaded messages that belong to another workflow.
- Added project-file overview behavior:
  - queries like `what exactly are the files in my directory?` now use the read-only project observation instead of falling into generic status or validation cards;
  - the response summarizes top-level entries, detected workflow artifacts, and observed image/seg volume sets without showing a misleading action card.
- Tightened local model selection:
  - kept `qwen3.5:9b` as the default local workflow-intent model after a quick current-source check for small-model tool calling;
  - changed the semantic intent fallback from `qwen2.5:32b` to `qwen3.5:9b`;
  - exported `PYTC_WORKFLOW_INTENT_MODEL=${OLLAMA_MODEL}` in start scripts and documented it in the README.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py server_api/auth/models.py server_api/main.py` passed.
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -q` passed: 42 tests.
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 21 tests.
  - `npm run build` passed with the existing EHTool hook dependency warnings.
- Operational state:
  - deployed rebuilt frontend to `/var/www/demo.seg.bio`; public `demo.seg.bio` now serves `main.e7661a66.js`.
  - restarted the public API as PID `1992825` on port `4342` with `PYTC_WORKFLOW_INTENT_MODEL=qwen3.5:9b`.
  - verified local `GET /health` and public `GET /api/health` return OK.
  - verified live SQLite schema has `chat_messages.trace_json`.

## 2026-05-03 - Workflow-Native Project Progress Tracker

- Revisited the main-branch Project Manager lineage after the user pointed at the main commits page:
  - main currently contains `9973906` (`Add project manager core`) and earlier PM commits;
  - used the old `ProjectManager`, `VolumeTracker`, and `ProjectManagerContext` as reference only, because the demo app now needs workflow-session-native tracking instead of the old login/RBAC PM surface.
- Added backend workflow project-progress support:
  - new `GET /api/workflows/{workflow_id}/project-progress` endpoint;
  - new `POST /api/workflows/{workflow_id}/project-progress/volume-status` endpoint for per-volume manual status overrides;
  - project observation now feeds a volume-level tracker that classifies images as `ground_truth`, `needs_proofreading`, `missing_segmentation`, or `ignored`;
  - pairing uses observed image/label roots, normalized image-vs-seg names, existing labels/predictions, correction-set evidence, and ground-truth/proofread filename markers;
  - stores a compact `metadata.project_progress_snapshot` and manual `metadata.project_progress_overrides` so both the user and agent have a shared progress reference.
- Added frontend progress module:
  - new top-level `Progress` tab in the workflow nav;
  - summary cards for tracked volumes, fully good ground truth, needs proofreading, and no segmentation;
  - completion and segmentation-coverage progress bars;
  - filterable volume table with image path, matched segmentation path, source/kind, and editable per-volume status.
- Updated agentic implementation:
  - semantic routing now recognizes progress-manager language such as "project progress", "how many volumes are done", "ground truth", "unproofread", and "missing segmentation";
  - workflow-agent responses can open the Progress tab via an `open-project-progress` app action;
  - client effects refresh the progress snapshot when the agent routes the user there;
  - normal agent query refresh now also refreshes project progress so the tracker stays aligned with file/project observation.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed.
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -q` passed: 44 tests.
  - `npm test -- --runTestsByPath src/views/ProjectProgress.test.js src/views/Views.test.js src/contexts/WorkflowContext.test.js src/components/Chatbot.test.js --watchAll=false` passed: 40 tests.
  - `npm test -- --runTestsByPath src/views/ProjectProgress.test.js --watchAll=false` passed after the hook-warning cleanup: 2 tests.
  - `npm run build` passed; remaining warnings are the pre-existing EHTool hook dependency warnings.
- Operational state:
  - deployed rebuilt frontend to `/var/www/demo.seg.bio`; public `demo.seg.bio` now serves `main.7dc1196c.js`.
  - restarted the public API as PID `2088314` on port `4342` with `PYTC_WORKFLOW_INTENT_MODEL=qwen3.5:9b`.
  - verified local `GET /health` and public `GET /api/health` return OK.

## 2026-05-03 - Switch Demo Assistant Back to 32B Model

- Switched the local assistant and workflow intent defaults from `qwen3.5:9b` back to the previously used 32B model:
  - `OLLAMA_MODEL=qwen2.5:32b`,
  - `PYTC_WORKFLOW_INTENT_MODEL=qwen2.5:32b`,
  - `OLLAMA_EMBED_MODEL=qwen3-embedding:8b` unchanged.
- Updated defaults in:
  - `README.md`,
  - `scripts/start.sh`,
  - `scripts/dev.sh`,
  - `server_api/chatbot/chatbot.py`,
  - `server_api/workflows/router.py`.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py server_api/chatbot/chatbot.py` passed.
  - Direct Ollama smoke for `qwen2.5:32b` returned `OK`.
  - restarted public API as PID `2136963` on port `4342`.
  - verified process env has `OLLAMA_MODEL=qwen2.5:32b` and `PYTC_WORKFLOW_INTENT_MODEL=qwen2.5:32b`.
  - verified local and public `GET /health` return OK.
  - verified local and public `GET /chat/status` return `{"configured":true,"error":null}`.

## 2026-05-03 - Humanize Visible Chat Language and Try Qwen3.6 27B

- Addressed visible chat tone that still sounded like backend state formatting:
  - changed the general chatbot response-style prompt to ask for normal conversational labmate-style replies;
  - removed rigid prompt-leak fallback phrases such as `Do this` / `Watch out`;
  - changed workflow-agent status, greeting, context, missing-input, and style-feedback replies away from `My read`, `Current read`, `Why this fits`, and `Tell me the job`;
  - added a `style_feedback` workflow-agent intent so feedback like "this is robotic" is acknowledged directly instead of being misrouted to a generic greeting/status reply;
  - kept app action cards and the expandable `What I checked` trace intact for structured details.
- Switched the configured local assistant model again after checking current top-small-model availability:
  - pulled `qwen3.6:27b` from Ollama successfully;
  - changed defaults to `OLLAMA_MODEL=qwen3.6:27b` and `PYTC_WORKFLOW_INTENT_MODEL=qwen3.6:27b`;
  - added `think=false` to the direct Ollama workflow-intent call and `reasoning=False` to LangChain `ChatOllama` construction so thinking-model output does not replace the visible final answer.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py server_api/chatbot/chatbot.py` passed.
  - Direct Ollama `/api/generate` with `qwen3.6:27b` and `think=false` returned `OK`.
  - Direct `ChatOllama(..., reasoning=False)` invocation with `qwen3.6:27b` returned `OK`.
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -k 'greetings_without_prompt_leakage or tone_feedback or project_file_overview' -q` passed: 3 tests.
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -q` passed: 45 tests.
- Operational state:
  - restarted public API as PID `2173819` on port `4342`.
  - verified process env has `OLLAMA_MODEL=qwen3.6:27b` and `PYTC_WORKFLOW_INTENT_MODEL=qwen3.6:27b`.
  - verified local and public `GET /health` return OK.
  - verified local and public `GET /chat/status` return `{"configured":true,"error":null}`.

## 2026-05-03 - Seed MitoEM2.0 Progress Demo Project

- Created a lightweight app-mountable MitoEM2.0 fixture at `/home/weidf/demo_data/mitoem2_progress_demo`.
- Based it on the official Hugging Face `pytc/MitoEM2.0` `Dataset006_ME2-Pyra` metadata and source filenames without downloading the full 17.1 GB benchmark payload.
- Initial active state:
  - 6 tiny HDF5 raw image volumes in `data/image`;
  - 2 active curated masks in `data/seg` that classify as `ground_truth`;
  - 2 active draft masks in `data/seg` that classify as `needs_proofreading`;
  - 2 image-only volumes with no active mask that classify as `missing_segmentation`.
- Stored withheld ground-truth masks for every volume outside the mounted project root at `/home/weidf/demo_data/mitoem2_progress_demo_holdout_masks` so they do not pollute app scanning.
- Added reset/snapshot support:
  - snapshot archive: `/home/weidf/demo_data/mitoem2_progress_demo/snapshots/initial_state.tar.gz`;
  - snapshot manifest with file hashes and expected progress counts: `/home/weidf/demo_data/mitoem2_progress_demo/snapshots/initial_state_manifest.json`;
  - reset command: `cd /home/weidf/demo_data/mitoem2_progress_demo && ./reset_to_initial.sh`.
- Verification:
  - `_scan_project_profile` sees 6 images, 4 labels, and one `image + seg` volume set.
  - Direct progress classification returns `{'ground_truth': 2, 'needs_proofreading': 2, 'missing_segmentation': 2}`.
  - Reset script removes generated top-level project artifacts, restores from the snapshot archive, and preserves the snapshot directory.

## 2026-05-03 - Make MitoEM2.0 Demo the Active Mounted Project

- Swapped the live demo instance from `/home/weidf/demo_data/prepilot_lucchi_pp` to `/home/weidf/demo_data/mitoem2_progress_demo`.
- App state changes:
  - unmounted the old `prepilot_lucchi_pp` root;
  - mounted `mitoem2_progress_demo` as the only root-level project (`mounted_root_id=1`);
  - reset the current workflow to `MitoEM2.0 Progress Demo` (`workflow_id=87`);
  - patched workflow paths to the new project root, `data/image`, `data/seg`, and `configs/MitoEM2-Pyra-Demo-BC.yaml`;
  - set workflow project context and visualization scales to `30,8,8` nm.
- Source-default changes so a restart stays on the new fixture:
  - `server_api/auth/router.py` now recommends `mitoem2_progress_demo` first and no longer marks Lucchi or mito25 as recommended;
  - `server_api/workflows/router.py` default mount path is now `/home/weidf/demo_data/mitoem2_progress_demo`;
  - `server_api/workflows/service.py` initial project defaults now use the MitoEM2 image/seg roots, config, project context, and scale metadata;
  - `client/src/views/FilesManager.js` fallback remote project path now points at the MitoEM2 fixture.
- Verification:
  - backend compile passed for `server_api/auth/router.py`, `server_api/workflows/router.py`, and `server_api/workflows/service.py`;
  - restarted API as PID `2385097` with `PYTC_INITIAL_PROJECT_ROOT=/home/weidf/demo_data/mitoem2_progress_demo` and `qwen3.6:27b`;
  - `GET /health` and `GET /chat/status` are OK;
  - `GET /files/project-suggestions` shows `mitoem2_progress_demo` as the only recommended and already-mounted suggestion;
  - `GET /api/workflows/87/project-progress` returns 6 tracked volumes: 2 ground truth, 2 needs proofreading, 2 missing segmentation.

## 2026-05-03 - Deploy Mount Project Button Default to MitoEM2.0

- Clarified that the user wanted the actual web `Mount Project` button fallback to target the MitoEM2.0 fixture the same way it previously targeted `prepilot_lucchi_pp`.
- Rebuilt the React frontend after the `DEFAULT_REMOTE_PROJECT_PATH` source change and deployed it to `/var/www/demo.seg.bio`.
- Public bundle now serves `main.a8775384.js` and contains `/home/weidf/demo_data/mitoem2_progress_demo` with no compiled `prepilot_lucchi_pp` fallback.
- Cleaned up a stale Lucchi mount that was reintroduced by the old bundle before refresh; root-level file state now contains only `MitoEM2.0 Progress Demo`.
- Verification:
  - `https://demo.seg.bio/` references `./static/js/main.a8775384.js`;
  - direct bundle check finds `/home/weidf/demo_data/mitoem2_progress_demo`;
  - `POST /files/mount` with the MitoEM2 path returns existing `mounted_root_id=1`;
  - `GET /files/project-suggestions` shows MitoEM2 as recommended/already-mounted and Lucchi as not mounted.

## 2026-05-03 - Progress-Aware Multi-Volume Training Agent

- Fixed the workflow agent intent precedence that made training requests containing phrases like “ground truth” or “no segmentation” fall into the progress-tracker response path.
- Added progress-aware training subset staging:
  - when the user asks to train from ground truth / fully good volumes / segment the rest, the agent now reads the project progress state;
  - creates a clean training subset outside the mounted project root under `/home/weidf/demo_data/.pytc_training_subsets/<project>/<run>/`;
  - links/copies only the selected training image/seg pairs into `image/` and `seg/`;
  - writes `volume_subset_manifest.json` with selected training pairs, image-only inference targets, excluded draft masks, and the source progress counts;
  - routes the training run card to the subset directories while preserving the project config and project-root training output path.
- Fixed training config selection so an explicit workflow `config_path` is used as-is. The MitoEM2 demo now proposes `/home/weidf/demo_data/mitoem2_progress_demo/configs/MitoEM2-Pyra-Demo-BC.yaml` instead of falling back to the older MitoEM case-study default.
- Updated training approval payload/cards to include `training_volume_subset`, so the UI can show why a run uses a particular subset.
- Tightened user-facing copy for this path so the assistant says plainly what it found and what it will train on instead of returning a “Do this / Why” checklist.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -k "ground_truth_progress_subset or project_progress_counts or opens_project_progress or train_model_from_current_labels or start_training_uses_data_derived_defaults or approved_training_run"` passed: 6 tests;
  - after narrowing the progress-subset trigger so generic “saved edits” retraining is not hijacked by semantic routing, `.venv/bin/python -m pytest tests/test_workflow_routes.py -k "ground_truth_progress_subset or train_model_from_current_labels or start_training_uses_data_derived_defaults"` passed: 3 tests;
  - `npm test -- --runTestsByPath src/contexts/WorkflowContext.test.js src/components/Chatbot.test.js --watchAll=false` passed: 33 tests;
  - `npm run build` passed with the existing React hook dependency warnings in `DetectionWorkflow.js` and `ProofreadingEditor.js`;
  - deployed `main.da9bd95e.js` to `/var/www/demo.seg.bio`;
  - restarted API as PID `2469115` with `OLLAMA_MODEL=qwen3.6:27b` and the MitoEM2 initial project env;
  - live local query “train a model on my ground truth to segment the rest” returns intent `start_training`, 2 GT training volumes, 2 image-only targets, 2 draft-mask exclusions, and the MitoEM2 config path.

## 2026-05-04 - Make Agent Suggestions Actionable and Training Approval Legible

- Turned the visualization “found image/seg pairs” discovery toast into an actionable notification:
  - shows the discovered pair count;
  - keeps the current first-pair auto-open behavior;
  - offers direct buttons to open the Progress view or return to Files.
- Fixed the approval path for project-local training configs:
  - backend `/pytc/config` now accepts absolute YAML paths under allowed mounted/demo project roots;
  - MitoEM2 project config `/home/weidf/demo_data/mitoem2_progress_demo/configs/MitoEM2-Pyra-Demo-BC.yaml` now loads instead of returning `404`;
  - added route coverage for external project config loading.
- Made “Review run” for training approvals populate the Train Model form immediately without starting runtime.
- Made “Approve” for agent-staged training runs start the durable workflow command and switch the Train Model runtime panel into monitor mode instead of leaving the screen idle.
- Reworked the training proposal card display so it summarizes the run in human-sized fields:
  - config;
  - image/label roots;
  - output folder;
  - number of fully good GT training volumes;
  - target and draft-mask volume counts;
  - manifest path;
  - parameter mode.
- Verification:
  - `.venv/bin/python -m py_compile server_api/main.py server_api/workflows/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_pytc_runtime_routes.py -k "config_route_allows_project_config or start_model_training_proxy_returns_504"` passed: 2 tests;
  - `npm test -- --runTestsByPath src/contexts/WorkflowContext.test.js src/components/Chatbot.test.js --watchAll=false` passed: 33 tests;
  - `npm run build` passed with only the existing React hook dependency warnings in `DetectionWorkflow.js` and `ProofreadingEditor.js`;
  - deployed frontend bundle `main.01530754.js` to `/var/www/demo.seg.bio`;
  - restarted the demo2 API as PID `3696204` on port `4342` with `qwen3.6:27b` and the MitoEM2 progress project mounted;
  - verified `GET /health`, `GET /chat/status`, and the absolute MitoEM2 `/pytc/config` lookup.

## 2026-05-04 - Populate Train Form After Approving Agent Training Runs

- Addressed the Train Model screen staying visually empty after approving an agent-proposed training run even though the durable training command was submitted.
- Client-side approval fix:
  - approval now carries the accepted training client effects into the `monitor_training` runtime action;
  - monitor actions include explicit overrides for input image, input label, output path, log path, config origin, and autopick-parameter state;
  - Train Model applies those overrides directly to the visible form before consuming the monitor action.
- Runtime-state fallback:
  - the PyTC worker now stores `inputImagePath`, `inputLabelPath`, `configOriginPath`, `workflowId`, `runId`, `commandId`, and `autoParameters` in training runtime metadata;
  - Train Model mirrors active runtime metadata back into the same four visible fields, so a refreshed or late-arriving runtime snapshot still shows what is actually running.
- Verification:
  - `.venv/bin/python -m py_compile server_pytc/services/model.py server_api/main.py` passed;
  - `npm test -- --runTestsByPath src/contexts/WorkflowContext.test.js --watchAll=false` passed: 12 tests;
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 21 tests;
  - `npm run build` passed with the existing React hook dependency warnings in `DetectionWorkflow.js` and `ProofreadingEditor.js`;
  - deployed frontend bundle `main.30d6c5f1.js` to `/var/www/demo.seg.bio`;
  - restarted the PyTC worker as PID `3784579` on port `4243` after confirming no training job was active;
  - verified worker `/hello` and API `/health` are OK.

## 2026-05-04 - Keep Assistant LLM Loaded During Training by Default

- Changed the GPU-training preflight policy so Ollama model unloading is opt-in instead of automatic.
- `server_pytc.services.model._unload_ollama_before_gpu_training()` now defaults `PYTC_UNLOAD_OLLAMA_BEFORE_TRAINING` to disabled.
- When disabled, training runtime logs a clear keep-loaded preflight event instead of calling `ollama stop`.
- `scripts/start.sh` and `scripts/dev.sh` now export `PYTC_UNLOAD_OLLAMA_BEFORE_TRAINING=0` by default.
- README runtime variables now document setting `PYTC_UNLOAD_OLLAMA_BEFORE_TRAINING=1` only for memory-constrained GPUs.
- Verification:
  - `.venv/bin/python -m py_compile server_pytc/services/model.py` passed;
  - `.venv/bin/python -m pytest tests/test_worker_model_service.py` passed: 5 tests;
  - confirmed no training job was active;
  - restarted the PyTC worker as PID `3804081` on port `4243` with `PYTC_UNLOAD_OLLAMA_BEFORE_TRAINING=0`, `OLLAMA_MODEL=qwen3.6:27b`, and `OLLAMA_EMBED_MODEL=qwen3-embedding:8b`;
  - verified worker `/hello`, API `/health`, and idle training status.

## 2026-05-04 - Repair Stale Chat Approval Cards

- Investigated the live `Approve` button regression from the app event log.
- Root cause:
  - the button did fire;
  - it posted `POST /api/workflows/112/agent-actions/334/approve`;
  - backend returned `404 Agent proposal not found` because proposal event `334` belonged to an older workflow while the page had booted fresh workflow `112`;
  - the client surfaced this only as an unhandled promise rejection, so the card looked inert.
- Frontend fix:
  - approval card clicks now handle errors explicitly;
  - if an approval event is missing/stale, the client recreates the same proposal in the current workflow and approves the fresh event;
  - stale local proposal cards are marked superseded and recreated cards are marked approved;
  - proposal cards carry `workflow_id` from the event/message context where available.
- Verification:
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 22 tests;
  - `npm test -- --runTestsByPath src/contexts/WorkflowContext.test.js --watchAll=false` passed: 12 tests;
  - `npm run build` passed with the existing EHTool hook dependency warnings;
  - deployed frontend bundle `main.998633fb.js` to `/var/www/demo.seg.bio`;
  - verified API `/health` and idle training status.

## 2026-05-04 - Fix Multi-Volume Training Subsets and Continuous Workflow Chat

- Fixed the failed agent-approved MitoEM2 training launch:
  - root cause was `DATASET.IMAGE_NAME` / `DATASET.LABEL_NAME` being rewritten to staged subset directories such as `.../workflow_113.../image`;
  - PyTC then tried to open the directory as a single volume and raised `ValueError: unrecognizable file format`;
  - runtime overrides now detect paired training directories, read `volume_subset_manifest.json` when present, and rewrite the staged subset into explicit image/label volume lists.
- Hardened launch validation:
  - training and inference image inputs now reject unexpanded plain directories;
  - list-valued image/label inputs are accepted only when every listed volume path exists.
- Simplified the main workflow assistant into one continuous session chat:
  - removed saved-chat history/sidebar/new-chat controls from the big assistant pane;
  - the pane stores its current messages and backend `conversationId` in `sessionStorage`;
  - closing and reopening the drawer in the same browser session restores the exact thread and keeps future messages on the same backend conversation.
- Verification:
  - `.venv/bin/python -m py_compile server_pytc/services/model.py` passed;
  - `.venv/bin/python -m pytest tests/test_pytc_runtime_routes.py -q` passed: 34 tests, 5 subtests;
  - `.venv/bin/python -m pytest tests/test_worker_model_service.py -q` passed: 5 tests;
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 23 tests;
  - `npm test -- --runTestsByPath src/contexts/WorkflowContext.test.js --watchAll=false` passed: 12 tests;
  - `npm run build` passed with only existing EHTool hook dependency warnings;
  - deployed frontend bundle `main.f7e1aa6b.js` to `/var/www/demo.seg.bio`;
  - restarted the PyTC worker as PID `3994027` on port `4243` with `PYTC_UNLOAD_OLLAMA_BEFORE_TRAINING=0`;
  - verified worker `/hello` and idle training status.

## 2026-05-04 - Make Training Review Cards Actually Populate the Form

- Fixed the apparent no-op after clicking an agent-proposed training run's `Review run` button.
- Root cause:
  - the chat action could create the backend approval proposal before the visible Train Model form effects ran;
  - if the continuous chat remounted against a newer workflow, old action/proposal cards were correctly stripped, but their text still said to review a run card that no longer existed.
- Frontend fix:
  - training review actions now apply the form-populating client effects first, then create the approval card;
  - if a full effect pass fails, the client still navigates to Train Model and fills image, label, output, and log paths from a fallback effect set;
  - stale reviewed-run cards now explain that their button was hidden because it belonged to an earlier workflow, instead of leaving misleading text-only instructions.
- Verification:
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 25 tests;
  - `npm test -- --runTestsByPath src/contexts/WorkflowContext.test.js --watchAll=false` passed: 12 tests;
  - `npm run build` passed with only existing EHTool hook dependency warnings;
  - deployed frontend bundle `main.3cb1a337.js` to `/var/www/demo.seg.bio`;
  - verified API `/health`, worker `/hello`, and idle worker `/training_status`.
