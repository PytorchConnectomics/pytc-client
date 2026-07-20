# PyTC Client Progress Log

Local working log for Codex sessions on `pytc-client`.

## 2026-06-04

- Hardened agent proposal UX in chat for safer approval workflows:
  - made proposal fields editable before approval via a visible `Edit details` action and clickable field values;
  - ensured approved/rejected proposal cards remain locked (approve/reject disabled, no active edit mode).
  - reduced long label clipping risk with wrapping-safe proposal header, type tag, field, and agent badge styles.
  - propagated specialist agent metadata from proposal payload/action_card so non-PM badges render in chat cards.
  - extended/updated focused React tests for edit-before-approve, disabled after decision, long-label/wrapping, and specialist badge behavior.
  - verified with:
    - `npm --prefix client test -- --watchAll=false --runInBand --runTestsByPath src/components/chat/AgentProposalCard.test.js src/__tests__/agentProposalCards.test.js src/components/Chatbot.test.js`.

- Audited and stabilized the Yixiao browser smoke script at
  `scripts/browser_yixiao_case_study_smoke.py`:
  - fixed parser/help string syntax;
  - fixed Playwright runtime validation flow (now uses an active Playwright context correctly);
  - added an explicit install remediation message (`python3 -m pip install playwright` + `python3 -m playwright install chromium`).
- Added focused unit coverage for smoke parser helpers in
  `tests/test_browser_yixiao_case_study_smoke.py`:
  - viewport parsing behavior,
  - progress-text extraction (`10/6/2/2`, `60%`, `80%`),
  - default arg parsing.
- Documented browser smoke usage and operator-facing dependency gap in
  `docs/manual-yixiao-case-study-demo.md`.

- Refined Yixiao readiness taxonomy into explicit go/no-go gates for a one-hour case-study launch:
  - baseline project state, agent context, approval-gated training proposal, proofread promotion, closed-loop rehearsal, real artifact production, export bundle health, and live demo health.
- Added explicit claim boundary in paper-readiness plan: what can be claimed from the current prototype versus after real train/infer/eval closure.
- Updated the Yixiao demo manual with a launch acceptance checklist and revised claim-tier language for facilitators.
- Added one API gate-coverage regression test in `tests/test_workflow_case_study_acceptance.py` to assert readiness endpoint has all required gate IDs.
- Added workflow evidence/export hardening:
  - exported paths now retain provenance (`source_type`, `source_key`, `sources`) and copy-policy metadata;
  - proposal/approval links and user status-change history are surfaced in evidence summaries;
  - held-out/withheld ground-truth paths are treated as reference-only by default during bundle copy, while still being fully represented in `artifact_paths`;
  - added focused bundle/artifact regression coverage for Yixiao-style `withheld_ground_truth` references.

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

## 2026-05-05 - Add Mechanical Project Context Audits

- Added a bounded project scan audit that samples readable volume files instead of relying only on file names or user prose.
- Backend project profiles now include `audit` / `schema.audit` with:
  - sampled HDF5/TIFF volume metadata and simple statistics;
  - image/mask pair shape checks;
  - warnings for unreadable, empty, all-zero, or low-dynamic-range sampled data;
  - source-tagged `context_facts`, currently including voxel size pulled from volume metadata attributes.
- Project context defaults now prefer high-confidence audit facts over stale text/default hints, so metadata can correct bad scales before the workflow starts.
- Project setup UI now shows a "What I checked automatically" panel with audited volume counts, pair checks, source-tagged facts, and warnings/errors.
- Persisted `.pytc_project_context.json` now carries `project_audit` and `context_facts` so the workflow assistant can reference mechanically verified project facts later.
- Verification:
  - `.venv/bin/python -m pytest tests/test_file_workspace_routes.py -q` passed: 15 tests;
  - `npm test -- --runTestsByPath src/utils/projectSuggestions.test.js src/views/FilesManager.test.js --watchAll=false` passed: 23 tests, with existing React `act(...)` warnings from file-loading effects;
  - `npm run build` passed with the existing EHTool hook dependency warnings;
  - deployed frontend bundle `main.5c07d5d9.js` to `/var/www/demo.seg.bio`;
  - restarted the public demo API as PID `2188115` on port `4342` with `PYTC_ALLOWED_ORIGINS=https://demo.seg.bio,...`;
  - remounted `mitoem2_progress_demo` as root item `1`;
  - verified public `/api/health`, root files, worker `/hello`, and project suggestions with audit summary `{audited_volumes: 10, pair_checks: 4, warnings: 0, errors: 0}`.

## 2026-05-05 - Replace Blank Project Setup Prompt With Guided Context

- Removed the stranded blank first step for mounted projects when the app already has enough detected context.
- Project setup now:
  - jumps directly to the mapping/start confirmation when modality, target, voxel size, and image data are already inferred;
  - otherwise shows a guided "Project basics" checklist for modality, target, and voxel size;
  - keeps free-text as an optional note instead of the primary required input.
- Backend project suggestions now use a lightweight audit summary:
  - still checks metadata, image/mask pair shapes, findings, and context facts;
  - avoids full sample statistics and bulky per-volume payloads while rendering the project list.
- Project scanning now ignores transient runtime config files like `.__pytc_runtime_training_*.yaml`.
- Verification:
  - `.venv/bin/python -m pytest tests/test_file_workspace_routes.py -q` passed: 15 tests;
  - `npm test -- --runTestsByPath src/utils/projectSuggestions.test.js src/views/FilesManager.test.js --watchAll=false` passed: 24 tests, with existing React `act(...)` warnings from file-loading effects;
  - `npm run build` passed with the existing EHTool hook dependency warnings;
  - deployed frontend bundle `main.32c3c460.js` to `/var/www/demo.seg.bio`;
  - restarted the public demo API as PID `2335698` on port `4342`;
  - verified public `/api/health`, root files, worker `/hello`, and project suggestions returning in roughly `0.27s` with MitoEM2 audit summary `{audited_volumes: 10, pair_checks: 4, warnings: 0, errors: 0}`.

## 2026-05-23 - Sunset Monitor Tab

- Removed the Monitor module from the top navigation and stopped mounting the standalone Monitoring view.
- Retargeted legacy `navigate_to: monitoring` client effects to Train Model so older agent cards or saved actions do not strand users on a removed screen.
- Updated workflow-agent monitor/log/TensorBoard actions to open Train Model runtime details instead of proposing an "Open Monitor" card.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed;
  - `npm test -- --runTestsByPath src/views/Views.test.js --watchAll=false` passed: 6 tests;
  - `npm run build` passed with the existing EHTool hook dependency warnings;
  - deployed frontend bundle `main.a299bdfd.js` to `/var/www/demo.seg.bio`;
  - restarted the public demo API as PID `1118358` on port `4342`;
  - verified public `/api/health`.

## 2026-05-23 - Soften Workflow Agent Chat Tone

- Replaced the most robotic canned workflow-agent responses:
  - removed "The next useful move looks like..." from greeting/status-style paths;
  - changed greeting replies from status-template language to conversational guidance;
  - softened "workflow checks are ready" and style-feedback acknowledgements.
- Kept mechanical details in the expandable evidence/status surfaces rather than front-loading them in the chat response.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -q` passed: 46 tests;
  - restarted `pytc-demo@pytc-client-demo2.service` and `pytc-worker-demo2.service`;
  - verified public `/api/health`;
  - verified local demo workflow-agent greeting returns: "Hey. We are still in proofreading. I would probably keep proofreading likely mistakes. I can open the right screen, walk through what I am seeing, or help decide the next step."

## 2026-05-23 - Technical Incongruity Pass

- Fixed a sunset-monitoring inconsistency:
  - the top-level Monitor tab was already gone, but chatbot/RAG help still described a standalone TensorBoard/Monitoring page;
  - updated `Monitoring.md`, `GettingStarted.md`, `rag_eval.py`, and the manual checklist so user-facing help now points to Train Model runtime details instead.
- Fixed the Train Model completion card's TensorBoard button:
  - it had become a no-op that navigated back to Train Model;
  - it now starts TensorBoard for the resolved training output path, stores the returned URL in app context, and opens it in a new tab when available.
- Verification:
  - `npm test -- --runInBand src/contexts/WorkflowContext.test.js src/components/Chatbot.test.js src/views/Views.test.js src/views/FilesManager.test.js src/utils/projectSuggestions.test.js` passed: 67 tests, with existing FilesManager `act(...)` warnings;
  - `CI=true npm test -- --runInBand src/views/ModelTraining.js src/views/Views.test.js src/components/Chatbot.test.js` passed the matching test suites: 31 tests;
  - `CI=true npm run build` passed with existing EHTool hook dependency warnings;
  - `.venv/bin/python -m py_compile server_api/workflows/router.py server_api/auth/router.py server_api/main.py` passed;
  - direct backend `pytest` without the venv used system Python 2 and failed at collection; venv-targeted workflow tests were attempted but timed out while executing the selected agent-query test.

## 2026-05-24 - Deep Technical Audit Report

- Created `docs/research/internal-technical-audit-2026-05-24.md` as a broad internal audit of the current agentic PyTC client.
- Covered frontend workflow surfaces, backend workflow orchestration, project ingestion/context, training/runtime launch, proofread/EHTool persistence, logging/observability, and UI streamlining.
- Key risks called out:
  - workflow semantic intent prompt/schema drift rejects valid LLM intents;
  - app boot still clears mounted file/workflow state in places that conflict with continuous workflow memory;
  - workflow-agent routing captures nearly every chat message once a workflow exists, starving general help/RAG;
  - training subset staging points PyTC at directories, which can reproduce the previous "unrecognizable file format" failure;
  - chat/action execution remains split across multiple command/action paths;
  - project context and proofread artifacts are still sidecar-heavy rather than a first-class project memory model.
- UI and agent expansion notes include guided context intake, richer progress row actions, explicit agent readouts, traceable tool probes, continuous chat hydration, and a unified action proposal model.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py server_api/auth/router.py server_api/main.py server_pytc/services/model.py server_api/ehtool/router.py server_api/ehtool/data_manager.py runtime_settings.py app_event_logger.py` passed;
  - `CI=true npm test -- --runInBand src/views/Views.test.js src/components/Chatbot.test.js src/views/FilesManager.test.js src/utils/projectSuggestions.test.js` passed: 55 tests, with existing FilesManager `act(...)` warnings;
  - `CI=true npm run build` passed with existing EHTool hook dependency warnings and bundle-size warnings;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py tests/test_file_workspace_routes.py -q` passed: 61 tests, with existing framework deprecation warnings.

## 2026-05-24 - Deep Research Synthesis And Semantic Intent Hardening

- Synthesized the user-provided deep research report into `docs/research/deep-research-engineering-synthesis-2026-05-24.md`.
- Updated `docs/codex-working-memory/backlog.md` with research-driven engineering priorities:
  - structured project memory as the core state model;
  - one approval-gated action execution envelope;
  - server-backed continuous workflow chat and project hydration;
  - first-class per-volume state and multi-volume training artifacts;
  - conversational visible agent responses with mechanics in expandable traces;
  - task-family presets and eventual `valid_mask`/region-level support.
- Fixed the semantic workflow router prompt/validator mismatch:
  - introduced `SEMANTIC_WORKFLOW_INTENT_ORDER` as the prompt source of truth;
  - derived `SEMANTIC_WORKFLOW_INTENTS` from it;
  - included `style_feedback`, `project_files`, and `project_progress` so LLM classifications for those prompt-listed intents are no longer discarded.
- Added a regression test asserting the semantic prompt intent list and validation set stay aligned.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py tests/test_workflow_routes.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -k "semantic_workflow_intents or project_file_overview or opens_project_progress or style_feedback" -q` passed: 3 tests, with existing framework deprecation warnings;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -q` passed: 47 tests, with existing framework deprecation warnings.

## 2026-05-24 - Code Sweep Bug Fix Pass

- Fixed app boot wiping useful state:
  - removed the frontend `CacheBootstrapper` that reset file state before rendering;
  - restored localforage-backed hydration/persistence for global app state, while leaving the live Neuroglancer viewer object non-persisted;
  - changed workflow boot from "start a fresh workflow on every reload" to resuming the current workflow session.
- Kept explicit resets explicit:
  - `startNewWorkflow` and agent `start_new_workflow` effects still reset the file workspace and local workflow inputs before creating a new workflow;
  - the workspace reset route now preserves mounted-source `.pytc_project_context.json` sidecars instead of deleting project context during cleanup.
- Fixed workflow chat continuity:
  - added `GET /api/workflows/{workflow_id}/agent/conversation`;
  - hydrated the big workflow chat from the latest server-side workflow-agent conversation when reopening the panel in the same workflow session.
- Fixed over-eager workflow-agent routing:
  - general conceptual questions now stay on the regular chatbot/RAG path;
  - project/file/data/workflow questions and workflow follow-ups still route to the workflow agent.
- Reduced debug noise:
  - gated verbose training/inference client API logs behind `REACT_APP_DEBUG_API_LOGS`;
  - removed EHTool module-load prints and replaced a layer-preview failure print with structured event logging.
- Confirmed the existing training-subset path expansion test passes, covering the earlier "unrecognizable file format for .../image" failure mode.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py server_api/auth/router.py server_api/ehtool/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py tests/test_file_workspace_routes.py -q` passed: 63 tests, with existing framework deprecation warnings;
  - `CI=true npm test -- --runInBand src/contexts/WorkflowContext.test.js src/components/Chatbot.test.js` passed: 38 tests, with one existing intentional network-error warning;
  - `CI=true npm run build` passed with existing browser-data, EHTool hook dependency, and bundle-size warnings;
  - `CI=true npm test -- --runInBand src/views/Views.test.js src/views/FilesManager.test.js src/utils/projectSuggestions.test.js` passed: 30 tests, with existing FilesManager `act(...)` warnings;
  - `.venv/bin/python -m pytest tests/test_pytc_runtime_routes.py -k training_subset -q` passed: 1 test, with existing framework deprecation warnings.

## 2026-05-24 - Paper Readiness Production Plan

- Created `docs/codex-working-memory/paper-readiness-production-plan.md` as the detailed bridge from the current prototype to the paper-implied final product.
- The plan defines:
  - the core product contract for a production-shaped human-agent segmentation workflow;
  - the paper claim contract mapping claims to required system evidence;
  - P0/P1 readiness gates;
  - three case-study placeholders for guided intake, proofreading/data curation, and closed-loop training/inference/evaluation;
  - twelve implementation workstreams with concrete action items, verification gates, and paper evidence outputs;
  - milestone ordering from state foundation through paper freeze;
  - a final readiness checklist for claim-to-evidence alignment.

## 2026-05-24 - Backend Volume State And Project Management Hardening

- Added durable workflow-level volume state:
  - introduced `workflow_volume_states` with one row per workflow volume;
  - stores status, provenance/source, confidence, image/label/prediction/corrected-mask paths, training eligibility, inference eligibility, notes, metadata, and event linkage;
  - exposes volume state in workflow export bundles so paper/evidence snapshots include the actual project status map.
- Hardened the project progress loop:
  - project-progress refresh now syncs derived volume rows into durable volume state;
  - manual progress/status edits are preserved as manual volume-state overrides instead of being overwritten by rescans;
  - progress rows now include durable volume-state ids plus training/inference eligibility flags.
- Added backend APIs for the workflow loop:
  - `GET /api/workflows/{workflow_id}/volumes` refreshes and returns canonical workflow volume state with summary counts;
  - `PATCH /api/workflows/{workflow_id}/volumes` updates one volume's status, paths, eligibility, note, and metadata while appending a workflow event.
- Added a user-scoped mounted-project inventory:
  - `GET /users/me/projects` returns the current user plus mounted project roots owned by that user, indexed file/folder counts, and a summary project profile.
- Updated the production plan so its backend endpoint checklist matches the implemented workflow-scoped API surface.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/db_models.py server_api/workflows/service.py server_api/workflows/bundle_export.py server_api/workflows/router.py server_api/auth/models.py server_api/auth/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -k "project_progress_counts or workflow_volume_state_api" -q` passed: 2 tests, with existing framework deprecation warnings;
  - `.venv/bin/python -m pytest tests/test_file_workspace_routes.py -k "users_me_projects" -q` passed: 1 test, with existing framework deprecation warnings;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py tests/test_file_workspace_routes.py tests/test_workflow_export_bundle.py -q` passed: 66 tests, with existing framework deprecation warnings.

## 2026-05-24 - Canonical Workflow Overview Surface

- Formalized workflow progress display around one backend overview object:
  - added `GET /api/workflows/{workflow_id}/overview`;
  - overview includes current phase, phase reason, volume summary, full project progress snapshot, workflow stages, blockers, recommended next actions, active runs, and recent events;
  - derives from the same workflow/project-progress/model-run/event state that the agent and progress tables use.
- Updated frontend workflow state:
  - `WorkflowContext` now refreshes and stores `workflowOverview`;
  - overview refresh also hydrates the existing `projectProgress` cache when returned;
  - project progress status changes refresh the overview so manual volume edits are reflected in the shared state map.
- Reworked the visible workflow UI:
  - top navigation now has an always-visible workflow overview strip showing project name, phase, GT/draft/missing counts, blocker/run state, and the top next action;
  - renamed the old `Progress` tab to `Workflow`;
  - the page title is now `Workflow Overview` and includes phase/stage tiles, blockers, recommended next moves, completion summary, and the volume table;
  - chat drawer's old `Status` toggle is now `Evidence`, keeping traces/details separate from canonical workflow state.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -k "workflow_overview or project_progress_counts or workflow_volume_state_api" -q` passed: 3 tests, with existing framework deprecation warnings;
  - `CI=true npm test -- --runInBand src/views/Views.test.js src/views/ProjectProgress.test.js src/contexts/WorkflowContext.test.js src/components/Chatbot.test.js` from `client/` passed: 46 tests, with the existing intentional workflow-event network warning;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py tests/test_file_workspace_routes.py tests/test_workflow_export_bundle.py -q` passed: 67 tests, with existing framework deprecation warnings;
  - `CI=true npm run build` from `client/` passed with existing browser-data, EHTool hook dependency, and bundle-size warnings.

## 2026-05-24 - Deploy Workflow Overview To demo.seg.bio

- Deployed the current React build to `/var/www/demo.seg.bio`.
- Restarted `pytc-demo@pytc-client-demo2.service` so the new workflow overview API is live.
- Verification:
  - `https://demo.seg.bio/` serves `static/js/main.1166f4b3.js`;
  - `https://demo.seg.bio/api/health` returns `{"status":"ok"}`;
  - `https://demo.seg.bio/api/api/workflows/current` returns the active workflow;
  - `https://demo.seg.bio/api/api/workflows/167/overview` returns the new overview payload with phase `proofread`, volume summary, project progress, blockers/actions, and recent events.

## 2026-05-24 - Remove Assistant Evidence Drawer

- Removed the assistant drawer's local `Evidence`/timeline panel so the chat surface stays focused on plain conversation, action cards, proposals, and expandable per-message traces.
- Redirected legacy `show_workflow_context` client effects to the main `Workflow` page instead of opening a hidden drawer-specific context panel.
- Kept workflow state and provenance anchored in the app-level workflow surfaces rather than duplicating them in the chat header.
- Verification:
  - `CI=true npm test -- --runInBand src/components/Chatbot.test.js src/views/Views.test.js` from `client/` passed: 32 tests;
  - `CI=true npm run build` from `client/` passed with existing browser-data, EHTool hook dependency, and bundle-size warnings;
  - deployed the new React bundle to `/var/www/demo.seg.bio`;
  - `https://demo.seg.bio/` serves `static/js/main.d076d1c1.js`;
  - `https://demo.seg.bio/api/health` returns `{"status":"ok"}`;
  - verified the served bundle no longer contains `Hide Evidence`, `Show timeline`, `Hide timeline`, `forceShowWorkflowInspector`, or `onWorkflowInspectorConsumed`.

## 2026-05-24 - Yixiao TapeReader XRI Case Study Fixture

- Located the XRI data backing the older `view.seg.bio` visualization demo at `/home/weidf/Downloads/PT37_round2`.
- Cloned `https://github.com/LinghuLab/TapeReader` into `/home/weidf/reference_repos/TapeReader` and inspected the pipeline/PyTC configs.
- Assembled a current-app case-study project at `/home/weidf/demo_data/yixiao_tapereader_xri_case_study`:
  - 10 PT37 round-2 XRI raw TIFF volumes;
  - 6 ground-truth volumes matching the TapeReader training split (`1`, `2`, `3`, `4_1`, `4_2`, `4_3`);
  - 2 draft-mask volumes for proofreading (`5_1`, `5_2`);
  - 2 image-only inference targets (`6_1`, `6_2`) with masks withheld outside the project root at `/home/weidf/demo_data/yixiao_tapereader_xri_case_study_holdout_masks`.
- Added project-facing artifacts:
  - `project_manifest.json` with TapeReader/paper provenance, volume state, source paths, label counts, and voxel size `40 x 16.3 x 16.3 nm`;
  - `configs/TapeReader-Fiber-BCS-Original-Barcode.yaml`, preserving the paper pipeline's PyTC target list `["0", "4-0-1", "a-0-40-16-16"]`;
  - `configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`, using a current PyTC-compatible fallback target list `["0", "4-0-1", "5-2d-1-0-1.0-0"]`;
  - `configs/tapereader_pipeline_config.yaml`, `README.md`, case-study notes, copied TapeReader source/config references, a reset script, and an initial-state metadata snapshot.
- Added the Yixiao project to backend project suggestions so it can be mounted from the app.

### 2026-05-24 - Yixiao TapeReader XRI Case Study Verification

- Hardened `/home/weidf/demo_data/yixiao_tapereader_xri_case_study/reset_to_initial.sh` to use the demo app venv when regenerating CLAHE training inputs, so reset does not depend on ambient `python` packages.
- Verified fixture counts after reset: 10 raw volumes, 8 visible segmentation masks, 12 PyTC training files, and 10 withheld masks in `/home/weidf/demo_data/yixiao_tapereader_xri_case_study_holdout_masks`.
- Verified manifest split remains 6 ground-truth volumes, 2 draft/needs-proofreading volumes, and 2 image-only/missing-segmentation volumes.
- Verified both TapeReader YAML configs parse and load through the local PyTC config loader. The app-compatible sanity target builds local PyTC training targets on a crop; the original barcode-branch target intentionally fails under bundled current PyTC with `Target option a is not valid`, preserving the known compatibility boundary.
- Restarted the live `pytc-demo@pytc-client-demo2.service` process via systemd auto-restart and confirmed `https://demo.seg.bio/api/files/project-suggestions` now includes `yixiao-tapereader-xri-case-study`.

## 2026-05-24 - Guided Project Context Intake Pass

- Reworked mounted-project setup toward inspect-first guided confirmation:
  - added a detected-data summary showing image, mask, prediction, config, and checkpoint counts;
  - added quick confirmation chips for task family, mask readiness, image-only volume behavior, and training policy;
  - persisted those confirmations into project context/profile memory so they can be reused by the workflow agent and future setup passes.
- Improved XRI/TapeReader context handling:
  - frontend context inference now recognizes XRI / X-ray microscopy and fibres/CytoTape;
  - Yixiao project suggestions now carry task-family, mask-state, image-only strategy, and training-policy hints;
  - fixed suggestion hint merging so hand-authored case-study hints override noisy scanned text rather than being overwritten by it.
- Softened required agent context collection:
  - the workflow agent no longer requires generic speed-vs-accuracy as a hard prerequisite;
  - it asks for concrete project facts like imaging modality and target structure, with XRI/fibre examples.
- Verification:
  - `CI=true npm test -- --runInBand src/views/FilesManager.test.js src/utils/projectSuggestions.test.js --watchAll=false` passed: 25 tests, with existing FilesManager React `act(...)` warnings;
  - `.venv/bin/python -m py_compile server_api/auth/router.py server_api/workflows/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -k "project_context or train_short_phrases or stores_context" -q` passed: 3 tests, with existing framework deprecation warnings;
  - `CI=true npm run build` passed with existing EHTool hook dependency and bundle-size warnings;
  - deployed frontend bundle `main.46186d5c.js` to `/var/www/demo.seg.bio`;
  - restarted the public demo API as PID `4107560` and verified `https://demo.seg.bio/api/health`;
  - verified public Yixiao project suggestion context now reports XRI fibre instance segmentation, 40 x 16.3 x 16.3 nm, mixed masks/image-only volumes, and GT-only training policy.

## 2026-05-24 - Canonical Project Memory Endpoint

- Added a backend project-memory read model for the workflow agent and UI to share:
  - `project_facts` with mounted path, project context, audit facts, and task-family preset;
  - `artifact_index` with canonical paths and registered workflow artifacts;
  - `volume_states` with summary, items, and progress snapshot;
  - `run_history` and `evidence_events` for provenance-aware answers and action proposals.
- Added task-family presets for TapeReader/XRI fibre, MitoEM-style mitochondria instance segmentation, and generic volumetric segmentation so the agent does not treat every project as the same generic task.
- Exposed `GET /api/workflows/{workflow_id}/memory` and records a `workflow_project_memory/project_memory_refreshed` event when refreshed.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py server_api/auth/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -q` passed: 51 tests, with existing framework deprecation warnings;
  - `CI=true npm test -- --runInBand src/views/FilesManager.test.js src/utils/projectSuggestions.test.js --watchAll=false` passed: 25 tests, with existing FilesManager React `act(...)` warnings;
  - restarted the public demo API and verified `https://demo.seg.bio/api/health`;
  - verified `https://demo.seg.bio/api/api/workflows/168/memory` returns `pytc-project-memory/v1` with canonical paths, task-family preset, volume states, and evidence events.

## 2026-05-24 - Agent Context And Tone Integration

- Fed richer canonical context into semantic intent routing:
  - task family, mask status, image-only strategy, training policy, and project-progress summary now appear in the workflow state sent to intent classification;
  - server-side casual context extraction now recognizes XRI/X-ray, CytoTape fibres, mixed masks/image-only projects, and GT-only training policy.
- Softened front-facing workflow-agent responses:
  - project-context answers now read as a short human summary of the current project, paths, tracker counts, and likely next move;
  - generic follow-up answers no longer end with the stiff "I will not launch..." template;
  - capabilities copy now emphasizes natural requests plus reviewable app-action cards.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py server_api/auth/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py -q` passed: 51 tests, with existing framework deprecation warnings;
  - restarted the public demo API as PID `4164882` and verified `https://demo.seg.bio/api/health`;
  - verified live workflow-agent response for `what project are we looking at?` returns a concise project summary and tracker counts rather than the old status-template response.

## 2026-05-27 - Yixiao Case Study Live Prep And Smoke Test

- Mounted `/home/weidf/demo_data/yixiao_tapereader_xri_case_study` as the active demo2 project and reset the live workflow to `170` with Yixiao/TapeReader context:
  - active raw root `data/raw`;
  - active segmentation root `data/seg`;
  - active config `configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`;
  - voxel spacing `40 x 16.3 x 16.3 nm`;
  - project split: 10 tracked volumes, 6 confirmed ground truth, 2 draft masks needing proofreading, 2 image-only inference targets.
- Hardened mounted-project ingestion for manifest-backed case studies:
  - the scanner now uses `project_manifest.json` to seed canonical image/label/config roots before noisy derivative folders like `data/pytc_train`;
  - manifest-declared image/label pairs are included in project audits before the sample budget is filled;
  - nested XRI raw/mask folders now pair by matching per-volume folder IDs, so `data/raw/5_1/...` maps to `data/seg/5_1/...`.
- Hardened Neuroglancer volume-pair diagnostics:
  - single image/single label fallback pairs no longer report the same selected image as unpaired;
  - added a regression test for that fallback path.
- Smoke-tested the live demo2 stack:
  - systemd services `pytc-demo@pytc-client-demo2.service` and `pytc-worker-demo2.service` are active;
  - `http://127.0.0.1:4342/health` and `https://demo.seg.bio/api/health` return `{"status":"ok"}`;
  - public project suggestions include `yixiao-tapereader-xri-case-study` and report it as already mounted;
  - public progress endpoint reports 10 tracked volumes, 6 ground truth, 2 needs-proofreading, 2 missing segmentation, 60% completion, and 80% segmentation coverage;
  - workflow agent answers `what project are we looking at?` with XRI/CytoTape context and the 6/2/2 tracker readout;
  - workflow agent stages a review-gated training action from the 6 fully good masks and preserves the 2 draft masks plus 2 image-only targets in the generated subset manifest;
  - Neuroglancer route opens the first Yixiao image/mask pair at `40,16.3,16.3` nm and returns a live `/neuroglancer/v/...` URL.
- Verification:
  - `.venv/bin/python -m py_compile server_api/auth/router.py server_api/workflows/router.py server_api/workflows/volume_pairs.py` passed during the pass;
  - targeted file-workspace manifest/profile tests passed;
  - targeted project-progress nested XRI pairing test passed;
  - `tests/test_neuroglancer_volume_normalization.py` passed: 12 tests.
- Caveat:
  - FastAPI `TestClient` endpoint smoke tests still hang in this environment even for `/health`, so live local/public HTTP smoke checks were used for route-level verification.

## 2026-05-27 - Agentic Workflow Deep Research Brief

- Added `docs/research/deep-research-agentic-workflow-formalization-2026-05-27.md`.
- The brief asks a follow-on Codex/deep-research agent to investigate how to formalize the app's agentic implementation into a workflow-aware, approval-gated project operator for biomedical image segmentation.
- It includes:
  - local repo/data context for demo2;
  - MitoEM/MitoEM2, Yixiao/TapeReader XRI, and third-case-study placeholders;
  - code areas to inspect;
  - literature areas to review;
  - required deliverable structure for project memory schema, action cards, state machine, context elicitation, evaluation plan, and engineering roadmap.

## 2026-05-27 - Yixiao Repeatable Demo Harness

- Added `scripts/run_yixiao_case_study_smoke.py`, a live API harness for the Yixiao/TapeReader XRI case study.
- The harness can prepare live demo state with `--prepare-live`:
  - reset indexed workspace state;
  - mount `/home/weidf/demo_data/yixiao_tapereader_xri_case_study`;
  - create and patch a fresh Yixiao workflow;
  - verify project profile, progress, project memory, Neuroglancer, and agent training proposal behavior.
- The harness now also validates the worker-side PyTC training-subset path without launching training:
  - generated subset image/seg directories resolve through `volume_subset_manifest.json`;
  - six concrete training image/label files are found;
  - the staged training config passes runtime path validation.
- Fixed a staging bug exposed by the harness:
  - agent-proposed multi-volume training now creates the output/log directory during subset proposal staging, so the Train Model UI receives an existing output path.
- Added `docs/manual-yixiao-case-study-demo.md` with the facilitator walkthrough, expected UI states, agent prompts, reset/smoke commands, and known caveats.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py scripts/run_yixiao_case_study_smoke.py` passed;
  - `scripts/run_yixiao_case_study_smoke.py --prepare-live --verbose` passed against local demo2 API;
  - live workflow created by the latest smoke run: `174`;
  - live viewer URL returned: `https://demo.seg.bio/neuroglancer/v/2c26be144fec3d205344aca6f59b9c519ae0c9dc/`.

## 2026-05-27 - Preliminary Agentic Report Triage

- Reviewed `docs/research/agentic-workflow-formalization-report.md`, the fast preliminary research/architecture report.
- Reviewed the ChatGPT Deep Research prompt files already present:
  - `docs/research/deep-research-agentic-workflow-formalization-chatgpt-prompt-2026-05-27.md`;
  - `docs/research/deep-research-agentic-workflow-lit-review-chatgpt-prompt-2026-05-27.md`.
- Added `docs/research/preliminary-agentic-report-triage-2026-05-27.md` to separate:
  - recommendations solid enough to implement now;
  - claims needing deeper literature validation;
  - Yixiao-focused engineering work to continue while the full deep research pass runs.
- Current triage recommendation: work next on the Yixiao proofreading roundtrip so a draft mask can be promoted to ground truth and the agent's future training proposal updates from 6 GT volumes to 7 GT volumes.

## 2026-05-27 - Project Memory And Yixiao Roundtrip Hardening

- Enriched workflow project memory with paper-facing canonical volume states while preserving legacy app statuses:
  - `ground_truth` -> `proofread_ground_truth`;
  - `needs_proofreading` -> `draft_needs_proofreading`;
  - `missing_segmentation` -> `image_only`;
  - `ignored` -> `ignored`.
- Added memory freshness metadata so downstream agent logic and evidence bundles can see when project progress, volume states, and assistant context were generated.
- Embedded the project-memory snapshot into workflow evidence bundles and fixed datetime serialization so bundle export remains JSON-safe.
- Extended `scripts/run_yixiao_case_study_smoke.py` with `--exercise-promotion`:
  - promotes one draft Yixiao mask to `ground_truth`;
  - verifies progress updates from 6/2/2 to 7/1/2;
  - verifies project memory records canonical `proofread_ground_truth`;
  - verifies the next agent training proposal uses 7 training pairs, 1 review pair, and 2 image-only inference targets.
- Updated `docs/manual-yixiao-case-study-demo.md` with the promotion smoke flow and reset guidance.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py scripts/run_yixiao_case_study_smoke.py tests/test_workflow_routes.py tests/test_workflow_export_bundle.py` passed;
  - `timeout 60 .venv/bin/python -m pytest tests/test_workflow_export_bundle.py -q` passed;
  - `timeout 60 .venv/bin/python -m pytest tests/test_workflow_routes.py::WorkflowRouteTests::test_project_memory_endpoint_returns_canonical_context -q` passed;
  - `scripts/run_yixiao_case_study_smoke.py --prepare-live --exercise-promotion --report /tmp/yixiao-case-study-smoke-promotion-report.json --verbose` passed against local demo2 API;
  - live bundle export for workflow `175` returned `workflow-export-bundle/v1` with embedded `pytc-project-memory/v1` and 7 ground-truth volumes after promotion;
  - reran `scripts/run_yixiao_case_study_smoke.py --prepare-live --report /tmp/yixiao-case-study-smoke-report.json --verbose` to restore the public demo to the initial 6/2/2 state as workflow `176`;
  - live bundle export for workflow `176` returned embedded project memory with 6 ground-truth volumes and 2 image-only volumes.

## 2026-05-27 - Subagent Architecture Sprint Started

- Spawned six focused subagents for the next prototype-hardening pass:
  - Backend State: composite volume state and memory backend;
  - App Agent Capability: assistant intent/action behavior;
  - Action Policy: action-card schema and approval tiers;
  - Trace/Evidence: structured trace and provenance export;
  - UI Workflow: coherent manual-agent handoff surfaces;
  - Yixiao Case Study: first case-study demo readiness.
- Reliability/QA was deferred because the agent thread limit was reached; queue it after one current subagent completes.
- Added `docs/research/subagent-orchestration-integration-2026-05-27.md` to keep subagent outputs tied to one implementation path and acceptance criteria.

## 2026-05-27 - Subagent Sprint Implementation Pass

- Integrated the subagent recommendations into the backend workflow substrate:
  - added composite volume-state columns to `WorkflowVolumeState`;
  - retained legacy progress statuses while adding `annotation_state`, `role_state`, `execution_state`, `region_scope`, and `workflow-volume-state/v2`;
  - projected manual progress edits through the same composite-state helper so the Progress page, project memory, and agent training eligibility do not drift;
  - rejected contradictory legacy/composite volume-state updates.
- Expanded agent action cards without breaking existing frontend `client_effects`:
  - every `AgentChatAction` now carries `workflow.action_card/v2`;
  - action cards include action type, target, risk tier, approval reason, summary fields, input/output artifacts, expected effects, and bounded executor metadata;
  - runtime training cards are now explicitly `R4_runtime_job`, while navigation/status cards remain `R0_view`.
- Expanded assistant traces into a structured `agent_trace/v1` shape:
  - trace rows now include `category`, `data`, and `evidence_refs`;
  - persisted assistant messages retain those structured traces for later inspection;
  - workflow evidence bundles now include `agent_messages`, `action_card_index`, and `trace_index`.
- Added `docs/research/subagent-reliability-qa-2026-05-27.md` via the QA subagent and updated `docs/research/subagent-orchestration-integration-2026-05-27.md` with the full subagent synthesis.
- Verification:
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py tests/test_workflow_export_bundle.py -q` passed: 53 tests;
  - relaunched the demo2 backend manually on `127.0.0.1:4342` after systemd restart required interactive auth;
  - `scripts/run_yixiao_case_study_smoke.py --prepare-live --report /tmp/yixiao-case-study-smoke-report.json --verbose` passed as workflow `178`;
  - live viewer returned `https://demo.seg.bio/neuroglancer/v/baff3168abe7f9a2ea7e10e96770100ec0b13b54/`;
  - live bundle export for workflow `178` returned `workflow-export-bundle/v1`, embedded `pytc-project-memory/v1`, 4 agent messages, 6 trace entries, and 2 action-card entries.

## 2026-05-27 - App Agent Organization: Orchestrator And Specialist Agents

- Reorganized the app-facing assistant model around a main Project Manager orchestrator plus typed specialist subagents:
  - Project Manager / Orchestrator;
  - Data Scout;
  - Visualization Agent;
  - Proofreading Agent;
  - Training Agent;
  - Inference Agent;
  - Evaluation Agent;
  - Evidence Agent.
- Backend agent responses now include:
  - `orchestrator_agent`;
  - `subagents`;
  - per-action `specialist_agent`, `agent_type`, `agent_label`, and `agent_color`;
  - per-trace `agent_type`, `agent_label`, and `agent_color`;
  - `workflow.action_card/v2` cards with both orchestrator and specialist agent metadata.
- Chat UI now presents the drawer as `Project Manager`, describes it as an orchestrator, and uses colored badges/borders to distinguish specialist agents on action cards, approval cards, and trace rows.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed;
  - targeted route tests for project-progress and training agent cards passed;
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 26 tests;
  - relaunched the manual demo2 backend on `127.0.0.1:4342`;
  - `scripts/run_yixiao_case_study_smoke.py --prepare-live --report /tmp/yixiao-case-study-smoke-report.json --verbose` passed as workflow `179`;
  - live agent query returned Project Manager as orchestrator, the full specialist-agent catalog, Training Agent for the training action, and Data Scout for file-inspection trace rows.

## 2026-05-27 - Chat-Visible Agent Operation Trace

- Moved the assistant trace above the final natural-language answer in the workflow chat, so the chat now reads more like an agent run:
  - expandable operation trace first;
  - final response second;
  - action/proposal cards after that.
- Relabeled the trace affordance to `Agent trace · What I checked`.
- Trace rows now show the responsible specialist-agent badge and the operation category (`Checked`, `Inferred`, `Proposed`, `Blocked`).
- This deliberately exposes structured operation summaries rather than raw hidden chain-of-thought.
- Verification:
  - `npm test -- --runTestsByPath src/components/Chatbot.test.js --watchAll=false` passed: 26 tests;
  - relaunched the manual demo2 backend on `127.0.0.1:4342`.

## 2026-05-27 - demo.seg.bio Frontend Deployment

- Rebuilt the React production bundle for the demo2 checkout with `npm run build`.
- Synced the resulting `client/build/` output into the nginx web root at `/var/www/demo.seg.bio/`.
- Verified `https://demo.seg.bio` now serves `static/js/main.2441c22e.js` instead of the stale May 24 bundle.
- Verified the served bundle contains the new workflow-agent UI strings:
  - `Project Manager`;
  - `Orchestrates specialist workflow agents`;
  - `Agent trace`.
- Verified the live demo backend is reachable through nginx at `https://demo.seg.bio/api/api/workflows/current` and reports the mounted Yixiao TapeReader XRI workflow `179`.
- Verified live agent query for workflow `179` returns:
  - Project Manager orchestrator metadata;
  - specialist subagent catalog;
  - structured trace rows.
- Ran `scripts/run_yixiao_case_study_smoke.py --prepare-live --report /tmp/yixiao-case-study-smoke-report.json --verbose` after deployment; it passed as workflow `180` with viewer `https://demo.seg.bio/neuroglancer/v/d1a4256dc058d12b516f5f168c84bd61b7d79fdd/`.
- Note: the demo backend is still running via the manual `server_api.main` process on `127.0.0.1:4342`; systemd user unit lookup/restart was not available in this shell.

## 2026-05-28 - Proofreading Route Hardening

- Audited the proofreading view stack across `DatasetLoader`, `DetectionWorkflow`, `ProofreadingEditor`, `server_api/ehtool`, and workflow event handling.
- Fixed proofreading source selection by centralizing path priority in `client/src/views/ehtool/proofreadingPaths.js`:
  - source image now comes from `image_path` or `dataset_path`, not prediction output;
  - editable mask priority is corrected mask, then inference prediction, then original mask, then label.
- Mirrored the same path priority in backend agent proofreading action effects so chat-proposed `start_proofreading` launches cannot reintroduce stale source/mask selection.
- Fixed retraining staging from proofreading so `Use edits for training` no longer silently stages an original mask/label or a non-existent planned persistence path.
- Added focused frontend coverage for proofreading path priority and edited-mask staging eligibility.
- Added backend coverage for agent proofreading launch priority across corrected masks and prediction masks.
- Verification:
  - `npm test -- --runTestsByPath src/views/ehtool/proofreadingPaths.test.js src/views/ehtool/DatasetLoader.test.js src/views/MaskProofreading.test.js --watchAll=false` passed: 3 suites, 9 tests;
  - `.venv/bin/python -m pytest tests/test_ehtool_data_manager.py tests/test_ehtool_mesh_preview.py tests/test_workflow_routes.py::WorkflowRouteTests::test_ehtool_load_classify_save_and_export_append_workflow_events tests/test_workflow_routes.py::WorkflowRouteTests::test_agent_can_start_proofreading_from_current_image_mask_pair tests/test_workflow_routes.py::WorkflowRouteTests::test_agent_proofreading_launch_prefers_corrected_or_prediction_masks tests/test_workflow_routes.py::WorkflowRouteTests::test_agent_proofread_request_names_blocker_when_inputs_missing -q` passed: 9 tests.

## 2026-05-28 - Editable Agent Approval Cards

- Added an edit-before-approval path for agent proposal cards:
  - pending training, retraining, inference, visualization, and proofreading cards can expose editable auto-filled fields;
  - users can click `Adjust`, change the proposed paths/parameters, and approve the same card as `Approve with edits`;
  - unchanged approvals keep the existing one-click behavior.
- Threaded field overrides through the frontend approval path:
  - `AgentProposalCard` emits only changed fields;
  - `Chatbot`, `WorkflowTimeline`, `WorkflowContext`, and `api.js` pass overrides to the approval endpoint only when present.
- Hardened backend approval handling:
  - added an allowlisted `overrides` request body for approval;
  - merged approved edits into nested `client_effects` before training commands are queued;
  - recorded applied `user_edits` in approval/staging workflow events.
- Added focused coverage:
  - `AgentProposalCard.test.js` verifies editable training and client-effect fields;
  - `test_approved_training_run_applies_user_field_overrides` verifies edited training paths reach the queued command.
- Verification:
  - `npm test -- --runTestsByPath src/components/chat/AgentProposalCard.test.js src/components/WorkflowTimeline.test.js src/components/Chatbot.test.js --watchAll=false` passed: 3 suites, 32 tests;
  - `npm test -- --runTestsByPath src/contexts/WorkflowContext.test.js --watchAll=false` passed: 1 suite, 12 tests;
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py::WorkflowRouteTests::test_approved_training_run_proposal_returns_runtime_launch_effects tests/test_workflow_routes.py::WorkflowRouteTests::test_approved_training_run_applies_user_field_overrides -q` passed: 2 tests.

## 2026-05-28 - demo.seg.bio Deploy Editable Approval Cards

- Built the current React production bundle and synced it to `/var/www/demo.seg.bio/`.
- Public frontend now serves `static/js/main.721ed937.js`.
- Verified the served bundle contains the editable approval UI string `Approve with edits`.
- Restarted the demo2 backend from `/home/weidf/deploy/pytc-client-demo2` as PID `83317` on port `4342` with:
  - `PYTC_ALLOWED_ORIGINS=https://demo.seg.bio,http://localhost:3000,http://127.0.0.1:3000,null`;
  - `PYTC_NEUROGLANCER_PUBLIC_BASE=https://demo.seg.bio/neuroglancer`;
  - `PYTC_WORKER_URL=localhost:4343`.
- Verification:
  - `https://demo.seg.bio/api/health` returned `{"status":"ok"}`;
  - `https://demo.seg.bio/api/api/workflows/current` returned active workflow `180`;
  - live OpenAPI exposes `AgentActionApprovalRequest` / `overrides`.

## 2026-05-28 - More Disparate Workflow Agent Palette

- Replaced the agent/subagent palette with more visually separated hues:
  - Project Manager: charcoal `#111827`;
  - Data Scout: green `#00843D`;
  - Visualization Agent: royal blue `#0057B8`;
  - Proofreading Agent: hot magenta `#E0007A`;
  - Training Agent: violet `#7B2CBF`;
  - Inference Agent: burnt orange `#D55E00`;
  - Evaluation Agent: ochre `#B58900`;
  - Evidence Agent: cyan `#00A6A6`.
- Updated frontend fallback/orchestrator colors to match the backend palette.
- Deployed the rebuilt frontend to `/var/www/demo.seg.bio`; public bundle is now `static/js/main.99644842.js`.
- Restarted the demo2 backend from this checkout; live API process is PID `120119` on port `4342`.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed;
  - `npm test -- --runTestsByPath src/components/chat/AgentProposalCard.test.js src/components/Chatbot.test.js --watchAll=false` passed: 2 suites, 28 tests;
  - `https://demo.seg.bio/api/health` returned `{"status":"ok"}`;
  - served bundle contains the new palette values.

## 2026-05-28 - Agent Icon and Border Encodings

- Added non-color visual encodings for the project manager and workflow specialist agents:
  - Project Manager uses the workflow/project icon with a solid rail;
  - Data Scout uses the Files/folder icon with a dotted rail;
  - Visualization Agent uses the Visualize/eye icon with a double rail;
  - Proofreading Agent uses the Proofread/bug icon with a dashed rail;
  - Training Agent uses the Train Model/experiment icon with a heavier rail;
  - Inference Agent uses the Run Model/thunderbolt icon with a dash/top accent;
  - Evaluation Agent uses a bar-chart icon with a top accent;
  - Evidence Agent uses a file-done icon with an inset rail.
- Extended backend agent metadata with `icon_key` and `border_style`, and mirrored those fields onto chat actions and trace items.
- Added shared frontend agent visual helpers so action cards, approval cards, and trace rows use the same badge and rail encoding.
- Deployed the rebuilt frontend to `/var/www/demo.seg.bio`; public bundle is now `static/js/main.45e34a89.js`.
- Restarted the demo2 backend from this checkout as a detached `setsid` process; live API process is PID `158563` on port `4342`.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py` passed;
  - `npm test -- --watchAll=false --runTestsByPath src/__tests__/assistantActionCard.test.js src/__tests__/agentProposalCards.test.js` passed: 2 suites, 4 tests;
  - `.venv/bin/python -m pytest tests/test_workflow_routes.py::WorkflowRouteTests::test_agent_train_model_uses_ground_truth_progress_subset -q` passed;
  - `npm run build` passed with existing hook dependency warnings in proofreading/detection views;
  - `https://demo.seg.bio/api/health` returned `{"status":"ok"}`.

## 2026-05-28 - Visible Consulted-Agent Strip

- Follow-up after staged-demo feedback that the chat still looked like everything came only from Project Manager.
- Added a visible `Agents` strip at the top of workflow-assistant replies, derived from trace/action/proposal metadata.
- Switched agent badges to compact, non-clipping labels:
  - `PM`, `Data`, `Vis`, `Proof`, `Train`, `Infer`, `Eval`, `Evidence`;
  - each chip keeps the full agent name in its hover title and preserves the icon/color encoding.
- Deployed the rebuilt frontend to `/var/www/demo.seg.bio`; public bundle is now `static/js/main.b4d6fb58.js`.
- Verification:
  - `npm test -- --watchAll=false --runTestsByPath src/__tests__/assistantActionCard.test.js src/__tests__/agentProposalCards.test.js src/components/Chatbot.test.js` passed: 3 suites, 30 tests;
  - `npm run build` passed with the existing hook dependency warnings in proofreading/detection views;
  - `https://demo.seg.bio/api/health` returned `{"status":"ok"}`;
  - backend remained healthy as PID `158563` on port `4342`.

## 2026-05-28 - PyTC Worker Proxy Logging and Demo Service Repair

- Investigated a staged training approval failure:
  - browser/API error was `503: Failed to connect to PyTC worker`;
  - live API had been manually launched with `PYTC_WORKER_URL=localhost:4343`;
  - the actual PyTC worker was on `localhost:4243`.
- Added structured API-to-worker proxy events in `server_api/main.py`:
  - `api_runtime_configured` logs API/worker/neuroglancer runtime settings on startup;
  - `worker_proxy_request_started` logs each proxied worker call;
  - `worker_proxy_request_completed` logs latency and status;
  - `worker_proxy_request_failed` logs connection failures, timeouts, and upstream request errors.
- Added focused test coverage for connection-refused logging on `/training_status`.
- Repaired the live demo process topology:
  - killed the stale detached May 4 worker that was occupying `4243`;
  - killed the manually detached API process;
  - restarted `pytc-worker-demo2.service` and `pytc-demo@pytc-client-demo2.service` under systemd;
  - confirmed the deployed env file uses `PYTC_WORKER_URL=localhost:4243`.
- Verification:
  - `pytc-worker-demo2.service` active on port `4243`;
  - `pytc-demo@pytc-client-demo2.service` active on port `4342`;
  - `http://localhost:4243/hello` returned `["hello"]`;
  - `https://demo.seg.bio/api/health` returned `{"status":"ok"}`;
  - `https://demo.seg.bio/api/training_status` returned idle worker state through the API proxy;
  - app event log now records the full API proxy request path and worker latency.

## 2026-06-03 - Yixiao Case-Study Finish-Line Reorientation

- Re-read the current Yixiao case-study runbook, prototype readiness protocol,
  backlog, and progress log after returning to the project.
- Re-ran the live Yixiao smoke harness against the demo backend:
  - command: `.venv/bin/python scripts/run_yixiao_case_study_smoke.py --report /tmp/yixiao-case-study-smoke-report-latest.json --verbose`;
  - first sandboxed attempt was blocked from localhost HTTP;
  - reran with approved local API access.
- Smoke result: passed.
- Current verified workflow: `181`.
- Current verified viewer:
  `https://demo.seg.bio/neuroglancer/v/33755065f156f05d7d4ba86918a641c02d8d90de/`.
- Verified gates:
  - Yixiao project root and manifest exist;
  - manifest has 10 volumes: 6 ground truth, 2 needs proofreading, 2 missing segmentation;
  - backend health passes;
  - Yixiao project suggestion is mounted;
  - profile resolves `data/raw`, `data/seg`, and `configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`;
  - progress summary reports 60% complete and 80% segmentation coverage;
  - project memory schema and `tapereader_xri_fiber` preset are present;
  - Neuroglancer viewer generation succeeds for the first image/mask pair;
  - agent correctly identifies Yixiao/XRI/CytoTape project context;
  - agent stages an approval-gated training action using 6 GT volumes, leaving 2 draft masks and 2 image-only targets out;
  - PyTC subset resolver maps staged training directories to 6 concrete image/label files;
  - staged training config validates without launching a full GPU job.

## 2026-06-04 - Evidence Bundle Hygiene For Yixiao Case Study

- Hardened workflow evidence export to avoid repeated raw-volume copies by default:
  - added raw-image path detection (`.../raw/...` and `*_raw*` patterns),
  - added separate `raw_copy_max_bytes` policy (default `0`),
  - retained general `copy_max_bytes` cap for non-raw artifacts,
  - added manifest-only mode via `copy_manifest_only=true`.
- Exposed export copy controls on `POST /api/workflows/{workflow_id}/export-bundle`:
  - `copy_max_bytes`
  - `raw_copy_max_bytes`
  - `copy_manifest_only`
- Included `copy_settings` in bundle metadata and `workflow.bundle_exported` audit
  event payload.
- Added focused regression coverage in `tests/test_workflow_export_bundle.py` to verify
  raw-like paths are skipped by default and manifest-only export skips binary copies.
- Updated `docs/manual-yixiao-case-study-demo.md` and
  `docs/research/workflow-evidence-export.md` with operator guidance for large-volume
  case-study exports.
- Verification:
  - `.venv/bin/python -m pytest tests/test_workflow_export_bundle.py -q` passed.

## 2026-06-04 - Yixiao Pre-Demo Gate Fastening

- Extended `scripts/run_yixiao_case_study_smoke.py` with a deterministic pre-demo mode:
  - added `--pre-demo-gate` orchestration that runs baseline smoke, promotion smoke, and final restore smoke,
  - optionally performs lightweight readiness and export checks (`/case-study-readiness`, `/export-bundle`) and records residual caveats in the JSON output,
  - writes per-step reports at deterministic sibling paths and a composite report at `--report`.
- Added focused unit tests in `tests/test_yixiao_pre_demo_smoke.py` with mocked `run` and `SmokeHarness.request_json`:
  - verifies step ordering and pass/fail aggregation,
  - verifies residual readiness caveat behavior,
  - verifies export payload failure is surfaced as a gate failure.
- Updated `docs/manual-yixiao-case-study-demo.md` with the new fast pre-demo command and defaults,
  including readiness/export skip options.
- Updated `docs/research/subagent-reliability-qa-2026-05-27.md` to document the new pre-demo gate in the Yixiao QA flow.
- Verification:
  - `.venv/bin/python -m py_compile scripts/run_yixiao_case_study_smoke.py` passed;
  - `uv run pytest tests/test_yixiao_pre_demo_smoke.py -q` passed.
  - pre-demo gate error handling is covered for readiness/export endpoint failures and reports them as residual caveats.

## 2026-06-04 - Deployment Runtime Diagnostics Helper

- Added `scripts/inspect_demo_instance.py` as a fast operator-only diagnostics script for
  case-study readiness triage.
- Checks implemented:
  - API health and `/app/log-path` connectivity;
  - API runtime config log reconciliation (`api_runtime_configured`);
  - worker direct `GET /hello` and API `GET /training_status`;
  - worker URL mismatch detection from runtime log/proxy observations;
  - current workflow read for active-state visibility (`/api/workflows/current`);
  - Neuroglancer reachability and public-base/url alignment checks;
  - Ollama model/chat reachability checks with env-variable diagnostics;
  - workflow bundle disk usage and recent app-log ERROR count from log tail.
- Updated `docs/manual-yixiao-case-study-demo.md` with an operator section including
  pre-demo command (`inspect_demo_instance.py`) and failure interpretation.
- Added focused unit coverage in `tests/test_inspect_demo_instance.py` covering:
  - API health/workflow auth-state checks,
  - runtime-config worker mismatch check,
  - worker mismatch detection via proxy log target,
  - Neuroglancer connectivity checks with mocked socket failure,
  - disk/error tail behavior.
- Verification:
  - `.venv/bin/python -m py_compile scripts/inspect_demo_instance.py tests/test_inspect_demo_instance.py` passed;
  - `.venv/bin/pytest -q tests/test_inspect_demo_instance.py` passed.

## 2026-06-04 - Demo2 API Runtime Manager

- Added `scripts/manage_demo_instance.py` for safe, scoped control of demo2 API:
  - supports `start|stop|restart|status` with `nohup` + `setsid`;
  - discovers matching processes by repo checkout path and `server_api.main` command, and
    requires `PYTC_API_PORT` match (defaults to `4342`) to avoid touching demo3/user-seg-bio;
  - verifies persistence with `/health` and prints recent startup log output when a fresh start does not become ready;
  - uses graceful SIGTERM then SIGKILL fallback on stop.
- Added `tests/test_manage_demo_instance.py` with unit coverage for:
  - process discovery filtering by root/port,
  - command composition including required `nohup setsid`,
  - env override parsing,
  - stop path behavior and status when no process exists.
- Updated `docs/manual-yixiao-case-study-demo.md` with an operator restart command for demo2.
- Verification:
  - `uv run pytest tests/test_manage_demo_instance.py -q` passed.

## 2026-06-04 - Agent Bounded-Action Audit for TapeReader Workflow

- Audited `server_api/workflows/router.py` for TapeReader/TapeReader-XRI routing gaps and enforced bounded routines:
  - explicit workflow pair selection is used for visualization when concrete image/label paths are set;
  - proofreading keeps preferring draft/corrected masks first;
  - TapeReader training now requires trusted label sources (confirmed labels or saved proofreading edits) before launch, and does not accept raw predictions as training labels;
  - inference still requires a checkpoint before launch;
  - evaluation requires previous result, new result, and reference mask before comparison.
- Added focused backend coverage in `tests/test_workflow_routes.py` for:
  - explicit visualization pair selection;
  - TapeReader training trust-boundary blocker and recovery with corrected edits;
  - checkpoint requirement for image-only inference requests;
  - evaluation blocker when reference mask is missing.
- Updated `docs/agent-role-spec.md` with a TapeReader bounded-action contract section.
- Verification:
  - `.venv/bin/python -m py_compile server_api/workflows/router.py`
  - `.venv/bin/pytest tests/test_workflow_routes.py -k 'agent_visualize_request_uses_explicit_selected_pair or agent_train_on_trusted_masks_only_for_tapereader_context or agent_infer_on_image_only_projects_only_with_checkpoint or agent_evaluation_blocks_when_reference_mask_missing' -q`

## 2026-06-04 - Workflow Session Continuity and Training Proposal Hardening

- Hardened workflow chat/proposal continuity for browser refresh and reopen:
  - workflow session hydration now merges server-side proposal status into persisted local chat entries so approved/reviewed runs keep correct card state after reload,
  - proposal cards now render approval state and action visibility from proposal status,
  - proposal payload now carries action-card/agent context through card rendering.
- Added durable runtime resume support for training monitoring:
  - `approveAgentAction` stores a `monitor_training` pending action after durable training approval,
  - `WorkflowContext` restores monitor actions from sessionStorage with workflow-scoped TTL,
  - stale/invalid persisted actions are cleared, preventing cross-workflow bleed-through.
- Reduced action-card clipping/clarity risks:
  - wrapped proposal field and rationale text in `AgentProposalCard` and `App.css`.
- Added focused React verification:
  - `client/src/contexts/WorkflowContext.test.js` covers restore/persist pending runtime actions.
  - `client/src/components/Chatbot.test.js` covers proposal-status reconciliation across reopen plus routing guard for non-workflow conceptual questions.
  - `client/src/components/chat/AgentProposalCard.test.js` covers disabled action state after approval.
- Verification:
  - `npm --prefix client test -- --watchAll=false --runInBand --runTestsByPath src/contexts/WorkflowContext.test.js src/components/Chatbot.test.js src/components/chat/AgentProposalCard.test.js`

## 2026-06-04 - Yixiao Closed-Loop Evaluation Rehearsal Guard

- Added a Yixiao-specific closed-loop rehearsal mode to
  `scripts/run_yixiao_case_study_smoke.py`:
  - `--closed-loop-rehearsal` runs the existing local closed-loop evidence harness
    for image-only targets `6_1` and `6_2`;
  - the mode requires explicit external withheld masks and refuses mounted-project
    truth for the image-only targets;
  - rehearsal now enforces explicit holdout usage for real-artifact evaluation
    (`require_explicit_ground_truth`) and records per-target source checkpoints,
    model versions, and runtime sync summaries;
  - the default crop is `0:8,0:128,0:128` so it is fast enough for operator checks;
  - defaults now include dry-run iteration overrides
    (`--closed-loop-training-iterations`, `--closed-loop-inference-iterations`);
  - reports are written under `/tmp/yixiao-closed-loop-rehearsal-report.json` by default.
- Updated `docs/manual-yixiao-case-study-demo.md` with the command and clear
  scope boundaries: this validates closed-loop training/inference/evaluation
  wiring, checkpoint/model-version capture, and explicit holdout constraints.
- Added focused test coverage in `tests/test_yixiao_pre_demo_smoke.py` verifying
  that the rehearsal passes external withheld masks for `6_1` and `6_2`, and that
  rehearsal fails when holdout paths are not outside the mounted project.
- Added focused test coverage in `tests/test_closed_loop_smoke_script.py` for
  runtime sync/report shape and explicit ground-truth requirements in real-artifact mode.

## 2026-06-04 - Parallel Finish-Line Integration Pass

- Re-ran the finish-line heuristic for the Yixiao case-study prototype and split the remaining work across six focused subagents:
  - closed-loop rehearsal/execution evidence,
  - browser-facing QA harness,
  - approval-card editing UX,
  - workflow memory/provenance export,
  - demo deployment survivability,
  - paper/case-study readiness gates.
- Integrated the subagent results into the main demo2 checkout and verified the combined system:
  - `.venv/bin/python -m py_compile ...` passed for touched smoke scripts and workflow backend modules;
  - focused backend suite passed: `102 passed`;
  - focused React suite passed: `50 passed`;
  - `npm --prefix client run build` completed with only pre-existing React hook warnings in `DetectionWorkflow.js` and `ProofreadingEditor.js`;
  - closed-loop rehearsal passed for Yixiao image-only targets `6_1` and `6_2`;
  - post-deploy Yixiao pre-demo gate passed all 5 steps: normal smoke, promotion roundtrip, restore state, readiness check, export sanity;
  - demo2 API was restarted with `scripts/manage_demo_instance.py` and came back healthy as PID `976573`;
  - final `inspect_demo_instance.py` passed API, worker proxy, current workflow, Neuroglancer, app-error, and disk checks against configured Neuroglancer port `4244`.
- Remaining known gaps:
  - browser smoke is implemented but requires installing Playwright before it can run end-to-end in this checkout;
  - real GPU train/infer/eval remains outside the automated paper-strength gate and should be run manually before any performance claims;
  - evidence export still has deeper schema polish remaining around strict response models and durable proposal-to-approval foreign-key edges.

## 2026-06-04 - Literature-Informed Third Finish-Line Pass

- Ran a new HCI/VIS-oriented scan and captured the resulting task taxonomy in
  `docs/codex-working-memory/third-finish-line-lit-and-task-taxonomy.md`.
  Source anchors included common-ground workflow schemas, agentic visualization
  patterns, multimodal visual-analytics agents, feedback-barrier work, and a
  recent human-AI collaboration review.
- Split implementation across six focused workers:
  - common-ground project facts in Files setup,
  - visible operational traces in chat/proposal/timeline UI,
  - backend action policy/freshness regressions,
  - evidence/export contract strengthening,
  - browser certification and proposal-edit smoke coverage,
  - runtime/deploy observability.
- Integrated the worker outputs:
  - setup now shows a compact "Shared project facts" surface for modality,
    target, voxel size, volume split, task family, and training policy;
  - proposal cards and timeline entries now expose concise operational traces
    with inspected facts, policy decision, approval/execution status, affected
    artifacts, and project-memory updates;
  - evidence export now includes stronger copy-policy/provenance metadata and a
    proposal -> approval -> command/run/progress graph;
  - browser smoke now checks editable proposal behavior and reports exact
    Playwright installation commands when the dependency is missing;
  - inspector now reports a unified runtime-config check and treats transient
    training-status timeouts as warnings rather than hard failures;
  - backend route tests now cover existing policy/freshness payloads around
    missing/stale project context and approval-required actions.
- Integration fixes:
  - updated `_build_proofreading_action` to pass through `policy_decision`,
    `blocking_reasons`, and `freshness` to action cards;
  - removed fresh frontend lint warnings from the operational-trace changes.
- Verification before deploy:
  - `git diff --check` passed;
  - py_compile passed for changed scripts and workflow backend modules;
  - backend integration slice passed: `97 passed`;
  - React integration slice passed: `69 passed`;
  - focused proposal/timeline tests passed: `42 passed`;
  - production build passed with only pre-existing hook warnings in
    `DetectionWorkflow.js` and `ProofreadingEditor.js`.
- Remaining known gaps:
  - Playwright is still not installed in this checkout, so browser smoke is
    ready but not executed end-to-end here;
  - real GPU train/infer/eval remains required before claiming model-performance
    improvement;
  - evidence payloads are more structured but still not fully typed with
    strict Pydantic nested models.
