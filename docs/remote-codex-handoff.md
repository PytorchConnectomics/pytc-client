# Remote Codex Handoff: PyTC Client Agentic Prototype

Use this file to port the current local Codex context to a remote Codex session.
The remote goal is practical: keep the case-study demo moving, fix obvious
workflow breaks quickly, and preserve the prototype direction.

## Current Branch

- Repo: `https://github.com/PytorchConnectomics/pytc-client.git`
- Branch: `checkpoint/tochi-agentic-prototype`
- Latest pushed commit: `ac940e4 fix(agent): recognize training requests`

On the remote machine:

```bash
git fetch origin
git checkout checkpoint/tochi-agentic-prototype
git pull --ff-only origin checkpoint/tochi-agentic-prototype
```

If the remote is intentionally on another branch, cherry-pick the latest fix:

```bash
git fetch origin
git cherry-pick ac940e4
```

## Prototype Goal

This is not just a PyTC GUI. The target prototype is an agent-orchestrated,
human-controlled biomedical segmentation loop:

1. User mounts a project folder.
2. App inspects contents and asks for semantic project context.
3. User confirms image/label/prediction/checkpoint/config roles.
4. Agent can route the user through visualization, model running, proofreading,
   training, comparison, and evidence export.
5. Every agent action should be explicit, logged, approval-gated if risky, and
   phrased for a biologist rather than as a terminal/config explanation.

The core user goal is always: go from initial image volumes to proofread
segmentations, with model runs and retraining as needed.

## Most Important Recent Work

### Project-Agnostic Setup

- File setup moved away from the hardcoded mito-only path.
- Suggested/mounted project folders now go through a confirmation flow.
- The app attempts to infer:
  - image data
  - mask/label data
  - existing predictions
  - checkpoints
  - config presets
- The user can correct mappings before the workflow state is written.
- Project context is intended to persist as hidden project memory, not as noisy
  UI text.

Relevant files:

- `client/src/views/FilesManager.js`
- `client/src/utils/projectSuggestions.js`
- `server_api/auth/router.py`
- `tests/test_file_workspace_routes.py`
- `client/src/views/FilesManager.test.js`

### Workflow Agent

- The agent is meant to be an orchestrator, not a documentation chatbot.
- It should answer with short “do this / why / blocker” language.
- It should return app action cards for runnable tasks.
- It should name blockers when it cannot act.
- It should not leak JSON tool calls or internal prompts.

Recent critical fix:

- `train`, `train a model`, `train on saved edits`, and similar phrases now hit
  the workflow-agent training path instead of “did not understand”.

Relevant files:

- `server_api/workflows/router.py`
- `client/src/components/Chatbot.js`
- `client/src/contexts/WorkflowContext.js`
- `tests/test_workflow_routes.py`
- `client/src/components/Chatbot.test.js`

### Visualization and Volume Pair Handling

- Directory-level image/label roles are valid project context.
- Neuroglancer cannot directly load a directory as a volume, so the backend now
  tries to find clear image-to-seg file pairs inside directories.
- The agent should ask if there are more pairs/folders instead of pretending one
  file is the whole project.
- Visualization scale changes are now workflow context:
  - “reload with 1-1-1” should store z,y,x scale as `visualization_scales`
  - it should also update `project_context.voxel_size_nm`
  - the agent should offer `Reload viewer`

Relevant files:

- `server_api/workflows/volume_pairs.py`
- `server_api/main.py`
- `server_api/workflows/router.py`
- `client/src/views/Visualization.js`
- `tests/test_neuroglancer_volume_normalization.py`

### Proofreading Context

- Proofreading should use current workflow image/mask paths.
- It should not show global project suggestions from unrelated projects.
- Assistant-triggered proofreading load has a one-shot guard to avoid duplicate
  loads from React effect re-entry.

Relevant files:

- `client/src/views/ehtool/DatasetLoader.js`
- `client/src/views/ehtool/DatasetLoader.test.js`
- `client/src/views/ehtool/DetectionWorkflow.js`

## Current Remote Screenshot Diagnosis

The screenshot showing repeated:

> I did not understand that as a workflow job...

for training requests means the remote is missing `ac940e4` or equivalent. Pull
the branch or cherry-pick that commit. After it lands:

- `train` should ask for missing project context if needed.
- `can we train a model for this?` should either return `Train model` or name
  missing image/label inputs.
- `train on saved edits` should name missing labels/saved edits instead of
  falling to unknown.

## Case-Study Demo Path

For a prepilot, use a small real dataset project, not a synthetic-only smoke
path. Current likely remote target from screenshot:

- Mounted folder: `prepilot_lucchi_pp`
- Expected purpose: mitochondria / EM segmentation stress test
- Demo target: show whether the app can ingest a practitioner-style folder,
  infer image/label roles, visualize a pair, and let the agent route to
  proofreading/training without user config spelunking.

Suggested short script:

1. Start from Files with one mounted project.
2. Open or mount `prepilot_lucchi_pp`.
3. Confirm project context in plain language:
   `EM mitochondria dataset; segment mitochondria; prioritize accuracy.`
4. Confirm image/label roles.
5. Ask agent:
   `what should I do next?`
6. Ask:
   `can we visualize my existing segs?`
7. Run the `View data` / `Reload viewer` action.
8. If visualization works, ask:
   `proofread this data`
9. If labels or edits exist, ask:
   `can we train a model for this?`
10. If blocked, confirm the agent names exactly what is missing.

## Remote Debug Runbook

If no server logs are accessible, use endpoint probes and browser behavior.

### Check Current Workflow

```bash
curl -s https://demo.seg.bio/api/api/workflows/current | python -m json.tool | head -80
```

If the frontend is configured differently, also try:

```bash
curl -s https://demo.seg.bio/api/workflows/current | python -m json.tool | head -80
```

### Query Workflow Agent Directly

Replace `1` with the workflow id from the current-workflow response:

```bash
curl -s -X POST https://demo.seg.bio/api/api/workflows/1/agent/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"can we train a model for this?"}' | python -m json.tool
```

Expected after `ac940e4`:

- `intent` is `collect_project_context` or `start_training`
- response does not say `did not understand`
- actions either contain `start-training` or a setup blocker action

### Check Visualization Pair Handling

```bash
curl -s -X POST https://demo.seg.bio/api/api/workflows/1/agent/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"can we visualize my existing segs?"}' | python -m json.tool
```

Expected:

- `intent` is `view_data`
- action id is usually `open-visualization`
- if directories contain matched files, response mentions clear image/seg pairs

### Check Scale Correction

```bash
curl -s -X POST https://demo.seg.bio/api/api/workflows/1/agent/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"the scales are off; reload with 1-1-1"}' | python -m json.tool
```

Expected:

- `intent` is `set_visualization_scales`
- action id is `reload-visualization-scales`
- workflow metadata stores `visualization_scales: [1.0, 1.0, 1.0]`

## Tests To Run Remotely When Possible

Fast targeted backend:

```bash
/opt/homebrew/bin/uv run pytest tests/test_workflow_routes.py -q
```

If `uv` path differs:

```bash
uv run pytest tests/test_workflow_routes.py -q
```

Frontend targeted:

```bash
cd client
CI=true npm test -- --runInBand src/components/Chatbot.test.js
```

Production build:

```bash
cd client
npm run build
```

Known build warnings exist in older files. Do not block case-study progress on
non-new ESLint warnings unless they are directly related to the bug at hand.

## Known Wonkiness To Preserve In Context

- The UI is still too busy in places. Do not add more persistent explanatory
  panels unless absolutely necessary.
- Agent replies should be short. Avoid long documentation-style answers.
- Biologists should not have to manually tune config details unless they ask.
  The agent should infer safe defaults and expose an approval-gated app action.
- The project can contain many volumes, not one volume. Do not force a single
  image path as the full mental model.
- Directory names may be semantically weak. Infer roles from extensions,
  structure, manifests/configs, and lightweight file inspection, not only names.
- If an agent action cannot run, say the blocker plainly and provide the nearest
  useful action.
- Remote `demo.seg.bio` may have path prefix quirks. Recent remote note says the
  frontend should call `https://demo.seg.bio/api/files` and
  `https://demo.seg.bio/api/api/workflows/current` depending on deployed base
  config. Verify with curl before assuming.

## Implementation Principles For Remote Codex

- Prefer narrow fixes over large redesigns during case-study prep.
- Keep app actions typed through `client_effects`.
- Risky actions still require a user click:
  - model run
  - training
  - proofreading editor load
  - evidence export
  - metric computation
- Record every meaningful agent/workflow action in backend events when possible.
- If touching chat behavior, update both:
  - `server_api/workflows/router.py`
  - `client/src/components/Chatbot.test.js` or `tests/test_workflow_routes.py`
- If touching project ingest, update:
  - `client/src/views/FilesManager.test.js`
  - `client/src/utils/projectSuggestions.test.js`
  - `tests/test_file_workspace_routes.py`

## Memory Docs Worth Reading

- `docs/codex-working-memory/README.md`
- `docs/codex-working-memory/research-log.md`
- `docs/codex-working-memory/backlog.md`
- `docs/codex-working-memory/progress-log.md`
- `docs/prototype-completion-roadmap.md`
- `docs/agent-role-spec.md`
- `docs/case-study-prototype-readiness.md`
- `docs/manual-bulk-test-checklist.md`
- `docs/research/pytc-prepilot-dataset-stress-test.md`

The `docs/codex-working-memory/` files are vendored from the local Mac's
external Codex notes so remote Codex can operate with the same progress log and
backlog context.

## Current High-Level Priority

For the remote case-study sprint, the priority is not architectural perfection.
It is:

1. Make project ingest feel sane for a real folder.
2. Make the agent answer and act on obvious workflow requests.
3. Make visualization/proofreading/training blockers explicit.
4. Avoid UI clutter and long agent prose.
5. Capture enough evidence to know where the prototype still breaks.
