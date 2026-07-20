# Reliability / QA Plan For Agentic Prototype

Date: 2026-05-27

Scope: verify the agentic PyTC prototype is stable enough for the Yixiao TapeReader XRI demo without overclaiming full GPU training, inference quality, or proofreading-at-scale. This plan is a release gate, not a research-evaluation protocol.

## 1. Regression Suite

Run from repo root:

```bash
cd /home/weidf/deploy/pytc-client-demo2
uv run pytest
cd client && npm test -- --watchAll=false
cd client && npm run build
```

Minimum passing expectation:

- `uv run pytest` passes all backend/workflow tests, especially workflow routes, evidence export, volume I/O, Neuroglancer URL contract, runtime settings, file workspace routes, and closed-loop smoke script tests.
- React/Jest passes workflow context, proposal cards, assistant action/command cards, timeline filters, file manager, project progress, model training/inference, proofreading, and input-selector tests.
- `npm run build` completes without compile errors.

Fast targeted rerun after workflow/agent edits:

```bash
uv run pytest \
  tests/test_workflow_routes.py \
  tests/test_workflow_artifact_records.py \
  tests/test_workflow_export_bundle.py \
  tests/test_workflow_case_study_acceptance.py \
  tests/test_closed_loop_smoke_script.py

cd client && npm test -- --watchAll=false \
  src/contexts/WorkflowContext.test.js \
  src/__tests__/agentProposalCards.test.js \
  src/components/Chatbot.test.js \
  src/views/ProjectProgress.test.js \
  src/views/FilesManager.test.js
```

## 2. Live Service Smoke

Start local services:

```bash
cd /home/weidf/deploy/pytc-client-demo2
scripts/start.sh
```

Health checks:

```bash
curl -fsS http://localhost:8000/
curl -fsS http://localhost:4242/health
curl -fsS http://localhost:4243/hello
curl -fsS http://localhost:3000/
```

Closed-loop workflow smoke:

```bash
uv run python scripts/run_closed_loop_smoke.py \
  --output-dir /tmp/pytc-closed-loop-smoke
cat /tmp/pytc-closed-loop-smoke/smoke-report.json
```

Expected: smoke report passes and creates `workflow-bundle.json`, `readiness.json`, `evaluation-report.json`, and artifacts. Known exclusions are acceptable only if the report calls them out: real PyTC training, real PyTC inference, browser proofreading interaction, retries/cancellation/recovery.

## 3. Yixiao Live Smoke

Reset and prepare the public demo state:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --prepare-live \
  --report /tmp/yixiao-case-study-smoke-report.json \
  --verbose
cat /tmp/yixiao-case-study-smoke-report.json
```

Promotion-path check:

```bash
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --prepare-live \
  --exercise-promotion \
  --report /tmp/yixiao-case-study-smoke-promotion-report.json
cat /tmp/yixiao-case-study-smoke-promotion-report.json

.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --prepare-live \
  --report /tmp/yixiao-case-study-smoke-report.json
```

Fast pre-demo gate (recommended for final readiness checks):

```bash
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --pre-demo-gate \
  --report /tmp/yixiao-case-study-pre-demo-gate-report.json
```

When run successfully, this command performs normal smoke + promotion roundtrip + restore, then writes a composite report including readiness/export sanity checks. Readiness may still be incomplete in this fixture context unless closed-loop evidence has been intentionally executed.

Expected:

- Normal run verifies manifest-backed mount, project profile, 10 volumes, 6 fully good, 2 needs proofreading, 2 no segmentation, 60% completion, 80% segmentation coverage, project memory, Neuroglancer URL, agent summary, review-gated training proposal, and PyTC subset resolver.
- Promotion run verifies a draft mask can become canonical `proofread_ground_truth`, progress changes to 7/1/2, and the next training proposal uses seven training pairs.
- Final normal run restores the public demo to 6/2/2.

## 4. Stale State Checks

Before any timed demo, remove ambiguity from old runtime state:

```bash
cd /home/weidf/deploy/pytc-client-demo2
lsof -tiTCP:8000 -sTCP:LISTEN
lsof -tiTCP:4242 -sTCP:LISTEN
lsof -tiTCP:4243 -sTCP:LISTEN
lsof -tiTCP:3000 -sTCP:LISTEN
```

If the wrong process owns a port, stop it intentionally, then restart with `scripts/start.sh`.

State assertions:

- Files tab mounts `/home/weidf/demo_data/yixiao_tapereader_xri_case_study`.
- File tree includes `data`, `configs`, `notes`, `outputs`, `snapshots`, and `project_manifest.json`.
- Active roots are `data/raw` and `data/seg`; active config is `configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`.
- The assistant does not describe the project as mitochondria, Lucchi, MitoEM, or mito25 after Yixiao is mounted.
- No old workflow card silently launches training or inference; all agent-generated training actions remain review/approval gated.

Useful log inspection:

```bash
tail -n 120 .logs/start/api-server.log
tail -n 120 .logs/start/pytc-server.log
tail -n 120 .logs/start/react-dev.log
```

## 5. Browser Refresh / Session Continuity

Manual browser checks against `http://localhost:3000` or `https://demo.seg.bio`:

1. Mount the Yixiao project, open `Files`, refresh the browser, and confirm the same project remains mounted.
2. Open `Progress`, refresh, and confirm counts stay 10/6/2/2 with 60% completion and 80% segmentation coverage.
3. Ask `what project are we looking at?`, refresh, reopen the assistant, and confirm project context is still Yixiao/TapeReader/XRI.
4. Ask `train on the fully good masks to segment the image-only volumes`, refresh before approval, and confirm the proposal remains review-gated rather than auto-running.
5. Navigate to `Visualize`, open the first image/mask pair, refresh, and confirm the viewer can be reopened through an HTTPS `/neuroglancer/v/...` URL.
6. Close and reopen the browser session; repeat `Files`, `Progress`, and assistant context checks.

Fail the gate if refresh drops the mounted project, changes volume counts, loses proposal gating, or resurrects stale non-Yixiao context.

## 6. Failed Run Checks

Simulate and inspect common failures without editing code:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --prepare-live \
  --project-root /tmp/not-a-yixiao-project \
  --report /tmp/yixiao-negative-smoke-report.json || true
cat /tmp/yixiao-negative-smoke-report.json 2>/dev/null || true
```

Expected failed-run behavior:

- Failure is explicit and actionable, not a false pass.
- UI surfaces health or validation errors instead of hanging indefinitely.
- Failed training/inference attempts do not create completed workflow evidence.
- A failed or canceled run leaves later agent proposals review-gated.
- After rerunning `--prepare-live`, the demo state returns to the known 6/2/2 baseline.

When a real PyTC run is intentionally started, record:

- exact config path;
- input image/label paths;
- output/log paths;
- checkpoint path if created;
- terminal status: completed, failed, canceled, or unknown;
- whether workflow evidence accurately matches that status.

## 7. Yixiao Demo-Readiness Gates

Go/no-go requires all of the following:

- Regression suite passes or any skipped/failing tests are documented as unrelated to the demo path.
- `scripts/start.sh` brings all four local services up cleanly.
- `--pre-demo-gate` command passes and writes a composite report at
  `/tmp/yixiao-case-study-pre-demo-gate-report.json`.
- (For manual verification) normal Yixiao smoke passes and report is archived at `/tmp/yixiao-case-study-smoke-report.json`.
- (For manual verification) promotion smoke passes once, then normal smoke is rerun to restore 6/2/2.
- Browser refresh/session checks pass on the target demo URL.
- Assistant correctly states: Yixiao TapeReader XRI Case Study, XRI/X-ray volumetric microscopy, CytoTape fibres, 40 x 16.3 x 16.3 nm, 10 total volumes, 6 fully good, 2 needs proofreading, 2 without segmentation.
- Training proposal uses only the 6 fully good masks, excludes 5_1 and 5_2 draft masks, targets 6_1 and 6_2 for later inference, and requires approval.
- Visualize opens `data/raw/1/1-xri_raw.tif` with `data/seg/1/1-mask.tif` and correct scales.
- Proofreading and inference are presented with the known caveats from `docs/manual-yixiao-case-study-demo.md`.
- No claim is made that the prototype has reproduced TapeReader model performance unless a separate completed evaluation run proves it.

Demo is blocked if any of these are true:

- services are unhealthy or using unknown stale processes;
- Yixiao smoke fails;
- project state is not 6/2/2 before the public walkthrough;
- assistant uses stale mitochondria/mito25 context;
- refresh loses mounted project or staged proposals;
- training/inference can launch silently without review;
- failed runs appear as successful workflow evidence.
