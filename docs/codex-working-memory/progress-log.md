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
