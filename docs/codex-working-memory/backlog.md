# PyTC Client Backlog

Local backlog for ideas, follow-ups, and possible improvements discovered while working on `pytc-client`.

## Candidate Items

- Keep this list lightweight: add items here when they are useful but not part of the current task.

## Codebase Audit Backlog - 2026-04-13

### Highest Priority

- Extend the Workflow Spine from "stage retraining" to an actual retraining run artifact: launch, checkpoint produced, model version created, and evaluation-ready output.
- Add an evaluation stage that can compare pre/post-retraining masks or metrics and close the iteration loop.
- Expand agent proposal allowlist beyond `stage_retraining_from_corrections`, while keeping explicit approval for every mutating action.

### Product/Research Prototype

- Explore CAVE integration for connectomics workflows: https://pmc.ncbi.nlm.nih.gov/articles/PMC10402030/
- Add a "model failure regions" surface that can rank or surface uncertain/high-error regions for expert review.
- Add explicit model/version/result management so training and inference runs become inspectable artifacts rather than transient process logs.
- Make Project Manager data real enough for study use: replace static seed/mock values with imported datasets/tasks, durable storage, and role-aware server authorization.
- Extend project setup beyond one active role set: backend profiling now detects role directories and volume sets, and the UI can confirm folder-level image/label roles. Remaining work is an active-set selector, batch actions across multiple confirmed sets, and agent-safe provenance for multi-set runs.
- Improve project-context extraction after setup: the confirmation modal now captures freeform biological context before mapping correction and stores lightweight inferred metadata. Name/path regexes no longer infer biological context; backend content spot checks now provide conservative `context_hints`. Remaining work is a stronger parser/LLM extraction pass for uncommon modalities/structures and a clear way to inspect/edit saved project memory later.
- Surface hidden project-memory persistence failures better: `.pytc_project_context.json` is now written best-effort, but read-only project directories should produce a clear nonblocking warning and maybe a fallback app-managed memory location.
- Decide whether durable evidence bundles should copy large image/mask/checkpoint files or keep the safer default of path manifests plus small copied artifacts.
- Add study/export support for interaction logs and workflow efficiency metrics.
- Add region-level workflow state: selected slice/range, bounding box, active instance, and proofreader attention targets.
- Add an action-log export format for paper evaluation: CSV/JSON with actor, stage, event type, payload, approval status, and timestamps.

### Cleanup/Fixes

- Remove or gate verbose `console.log`/`print` debug logging in API, training, inference, visualization, and EHTool paths.
- Replace hardcoded Project Manager demo credentials and frontend-displayed passwords with a proper local auth flow or clearly labeled demo mode.
- Replace the File Manager preview modal placeholders with the existing `/files/preview/{id}` endpoint and useful text preview support.
- Address React build warnings: hook dependencies, unused imports/state, unsafe loop closures, and accessibility issues.
- Add route/API contract tests for Project Manager and EHTool endpoints.
- Move tracked runtime logs out of Git or stop mutating tracked `.logs/start/*.log` files.
- Normalize JSON formatting/newline handling for `server_api/data_store/project_manager_data.json` to reduce noisy diffs.
- Add package/test config for local modules instead of relying on command-specific import behavior.
- Replace ad hoc SQLite schema patching with Alembic or an explicit local migration path before any multi-user deployment.
- Reduce direct component knowledge of workflow side effects; over time, workflow events should be emitted from narrow service/API helpers rather than scattered UI code.
- Add a controlled `start_visualization` runtime action so an approved agent
  command can open Neuroglancer directly after setting image/label paths. Current
  behavior only populates the viewer inputs and navigates to Visualize.
- Consider replacing hand-rolled agent intent rules with a small typed intent
  parser once more workflow actions accumulate. The current rule set is tested,
  but every new biomedical phrasing increases maintenance burden.
- Resolve folder-level active role paths before launching visualization or
  proofreading. Current project setup can correctly register directories such as
  `Image/train` and `Label/train`, but Neuroglancer and EHTool need a selected
  volume file or a supported folder reader. The agent should ask which volume
  pair to open, or auto-pick a small representative pair with approval.
