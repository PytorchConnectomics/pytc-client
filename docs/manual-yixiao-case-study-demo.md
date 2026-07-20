# Yixiao TapeReader XRI Case Study Demo

## Purpose

This walkthrough locks the current demo around the Yixiao / TapeReader XRI fibre segmentation case study. It is meant for a facilitator or developer preparing `https://demo.seg.bio`, not as a participant-facing protocol.

The case study should demonstrate a workflow-aware agent that understands mounted project state, summarizes volume progress, opens data, proposes bounded training actions, and keeps proofread/training/inference roles separate.

## One-Hour Case-Study Acceptance Gates

Use this for launch decision:

- **Baseline fixture state**: baseline mount must show `10` volumes and `6/2/2` status split.
- **Agent context**: assistant context must mention `Yixiao TapeReader XRI Case Study`, `40 × 16.3 × 16.3`, and the `6/2/2` split.
- **Approval-gated training proposal**: “train on the fully good masks” must create a reviewable proposal.
- **Proofread promotion**: `5_1` or `5_2` can be promoted through the progress API and that change is visible.
- **Closed-loop rehearsal**: `6_1` and `6_2` can be paired with external holdout masks without leakage.
- **Real training/inference/evaluation artifacts**: before final claim, confirm terminal training, checkpoint/version, inference, and evaluation entries exist in workflow records.
- **Export bundle**: export returns `workflow-bundle.json` plus copy summary and required fields.
- **Live health**: `inspect_demo_instance.py --json` key checks are healthy or expected warnings are documented.

### Claim Boundary (important for facilitator)

- `GO` claim for this setup today:
  - workflow grounding and coordination, bounded approvals, projection of proofread and image-only roles.
- `NO` claim today:
  - TapeReader-level reproduction/accuracy claims without app-backed train/infer/eval evidence.
  - browser-level edit-quality claims beyond what the current editor actually returns.

## Known Project State

Project root:

```text
/home/weidf/demo_data/yixiao_tapereader_xri_case_study
```

Reference pipeline and paper:

- TapeReader: `https://github.com/LinghuLab/TapeReader`
- Paper: `https://www.biorxiv.org/content/10.1101/2025.05.10.653182v1`

Expected app state:

| Item                    | Expected Value                                       |
| ----------------------- | ---------------------------------------------------- |
| Project title           | `Yixiao TapeReader XRI Case Study`                   |
| Imaging modality        | X-ray / XRI volumetric microscopy                    |
| Target                  | CytoTape fibres                                      |
| Voxel size              | `40,16.3,16.3` nm in z,y,x                           |
| Active image root       | `data/raw`                                           |
| Active label root       | `data/seg`                                           |
| Active config           | `configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml` |
| Total volumes           | `10`                                                 |
| Fully good ground truth | `6`                                                  |
| Needs proofreading      | `2`                                                  |
| No segmentation yet     | `2`                                                  |

Volume split:

- Ground truth: `1`, `2`, `3`, `4_1`, `4_2`, `4_3`
- Draft masks needing proofreading: `5_1`, `5_2`
- Image-only inference targets: `6_1`, `6_2`

The withheld masks for image-only targets live outside the mounted project at:

```text
/home/weidf/demo_data/yixiao_tapereader_xri_case_study_holdout_masks
```

Do not use withheld masks during demo training/inference setup.

## Reset And Smoke Test

Before a demo, run the live smoke harness:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --prepare-live \
  --report /tmp/yixiao-case-study-smoke-report.json
```

What `--prepare-live` does:

- resets the indexed app workspace;
- mounts the Yixiao project;
- creates a fresh workflow;
- patches that workflow with Yixiao context;
- verifies project profile, progress counts, memory, Neuroglancer, and agent proposals.

What it does not do:

- it does not regenerate fixture data;
- it does not launch a GPU training job;
- it does not run inference.

Only regenerate the fixture data when you intentionally want to reset the case-study files:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --reset-fixture \
  --prepare-live \
  --report /tmp/yixiao-case-study-smoke-report.json
```

The fixture reset can take longer because it rebuilds CLAHE PyTC training inputs.

## Operator Diagnostics (Recommended Pre-Case-Study)

Before final checks, run the operator diagnostics script for a fast live sanity readout:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/inspect_demo_instance.py \
  --api-base https://demo.seg.bio \
  --json
```

For a single-command go/no-go gate before launch (exit non-zero on hard-fail only):

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/inspect_demo_instance.py \
  --api-base https://demo.seg.bio \
  --worker-url localhost:4243 \
  --neuroglancer-port 4244 \
  --json \
  | python3 - <<'PY'
import json
import sys

report = json.load(sys.stdin)
hard_fail = [row["name"] for row in report if row["status"] == "fail"]
if hard_fail:
    print("DEMO HEALTH HARD-FAIL:", hard_fail, file=sys.stderr)
    raise SystemExit(1)
print("DEMO HEALTH: GO")
PY
```

Useful defaults are also inferred from env:

- `PYTC_API_BASE`
- `PYTC_WORKER_PROTOCOL`
- `PYTC_WORKER_URL`
- `PYTC_NEUROGLANCER_PORT`
- `PYTC_NEUROGLANCER_PUBLIC_BASE`
- `PYTC_WORKFLOW_BUNDLE_DIR`

Key failures to scan for:

- `api.health` fails (`FAIL`) means the API endpoint is not healthy.
- `api.runtime_config` (`PASS`/`WARN`) shows matched/mismatched operator expectations for worker URL, configured Neuroglancer port, and Neuroglancer public base.
- `worker.hello` `WARN` means the configured worker address is not reachable directly.
- `worker.url_mismatch` `FAIL` means API requests are reaching a different worker URL than the configured `PYTC_WORKER_URL` (this was a known case-study outage class).
- `api.proxy_log` `WARN` means no matching proxy events were found in the recent app-log tail.
- `neuroglancer.port` `WARN` means the configured Neuroglancer bind port is not reachable from the operator node.
- `neuroglancer.public_base` `WARN` means `PYTC_NEUROGLANCER_PUBLIC_BASE` is absent or not an absolute URL.
- `neuroglancer.url_match` `WARN` means workflow’s stored Neuroglancer URL does not match the configured base.
- `app_error_events` `WARN` indicates recent ERROR rows in the app log; check the same log via `.logs/app/app-events.jsonl`.
- `workflow_bundles_disk` `WARN` indicates the workflow bundle directory is unavailable or unreadable.

This script is read-only and does not alter API/workflow state.

## Browser-Level UX Smoke (Optional)

After the API-side checks pass, you can run the browser-level smoke directly against the frontend:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python3 scripts/browser_yixiao_case_study_smoke.py \
  --base-url http://127.0.0.1:3000 \
  --report /tmp/yixiao-browser-smoke-report.json
```

For the production host:

```bash
.venv/bin/python3 scripts/browser_yixiao_case_study_smoke.py \
  --base-url https://demo.seg.bio \
  --report /tmp/yixiao-browser-smoke-report.json
```

Recommended flags for pre-demo smoke:

- add `--no-headless` when visually monitoring checks.
- add `--skip-assistant` if the assistant backend is intentionally unavailable.
- add `--skip-reload` to avoid a continuity round-trip check.

If Playwright is not installed, the script exits with a clear remediation message and does not attempt a partial run. Install exactly with:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python3 -m pip install playwright
.venv/bin/python3 -m playwright install chromium
```

The script prints the full remediation block with the interpreter it is running
under, so this install command is deterministic even when multiple Python
environments are present.

The smoke verifies:

- app boots at the target URL,
- Files shows the Yixiao project and required top-level entries,
- Workflow progress snapshot is `10/6/2/2` with `60%` completion and `80%` segmentation coverage,
- assistant panel can open and answer a project-context query (unless skipped),
- training proposal card generation plus editable proposal fields,
- training proposal card is not obviously clipped at the default viewport,
- reload/reopen continuity for the same active UI state.

## Demo2 API Runtime Control

Use this helper instead of manual `nohup`/`setsid` invocations:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/manage_demo_instance.py restart \
  --api-port 4342 \
  --force \
  --health-timeout 90 \
  --log-file .logs/start/demo2-api-server.log
```

What this command does:

- finds and stops only demo2 API processes running from this checkout (`server_api.main`) on port `4342`,
- starts the API with `nohup` + `setsid` so it persists after shell exit,
- writes startup output to `.logs/start/demo2-api-server.log`,
- verifies persistence via `/health`,
- prints the last log lines plus shutdown hints on failure.

Behavior safeguards:

- it matches `server_api.main` processes by repo path and `PYTC_API_PORT`,
- it does not stop sibling demo services (`demo3` / `user-seg-bio`) because they use different checkout roots and/or ports,
- restart and stop are idempotent when no matching process exists.

To exercise the closed-loop promotion path without launching GPU training:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --prepare-live \
  --exercise-promotion \
  --report /tmp/yixiao-case-study-smoke-promotion-report.json
```

This promotes one draft mask from `Needs proofreading` to `Fully good`, verifies project memory records the canonical `proofread_ground_truth` status, and verifies the next training proposal updates from `6` to `7` training volumes. Rerun the normal `--prepare-live` smoke afterward to restore the public demo to the initial 6/2/2 state.

## Manual Demo Flow

### 1. Open The Demo

Open:

```text
https://demo.seg.bio
```

Expected:

- the app loads without health/toast errors;
- the `Files` tab shows `Yixiao TapeReader XRI Case Study` mounted;
- the folder tree includes `data`, `configs`, `notes`, `outputs`, `snapshots`, and `project_manifest.json`.

### 2. Check Files / Project Inspection

Stay on `Files`.

Expected:

- opening the project triggers a compact project-context confirmation card showing:
  - modality, target, voxel size, task family, training policy, and volume split;
  - the card should show `6/2/2` as `(6 ground-truth, 2 draft masks, 2 image-only)` text (or equivalent);
- if any fact is wrong, use the controls in the same modal to correct it before starting.
- the suggested project button opens the Yixiao project if it is not already mounted;
- file roles should be driven by `project_manifest.json`;
- raw image root should be `data/raw`, not `data/pytc_train`;
- label root should be `data/seg`;
- active config should be `TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`.

If the file tree is stale or wrong, rerun:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/run_yixiao_case_study_smoke.py --prepare-live
```

### 3. Open Progress

Go to `Progress`.

Expected summary:

- `10` tracked volumes;
- `6` fully good;
- `2` needs proofreading;
- `2` no segmentation;
- completion is `60%`;
- segmentation coverage is `80%`.

Expected interpretation:

- fully good volumes are training-ready;
- needs-proofreading volumes should be reviewed before promotion;
- no-segmentation volumes are inference targets after a model/checkpoint exists.

### 4. Ask The Agent What This Project Is

Open the assistant and ask:

```text
what project are we looking at?
```

Expected response should mention:

- `Yixiao TapeReader XRI Case Study`;
- XRI / X-ray volumetric microscopy;
- CytoTape fibres;
- `40 x 16.3 x 16.3 nm`;
- `10` tracked volumes;
- `6` fully good, `2` needing proofreading, `2` without segmentation.

The agent should not describe this as mitochondria or Lucchi/MitoEM.

### 5. Visualize The First Pair

Ask the agent:

```text
can we look at some data?
```

Or go to `Visualize` directly.

Expected:

- image path: `data/raw/1/1-xri_raw.tif`;
- label path: `data/seg/1/1-mask.tif`;
- scales: `40,16.3,16.3`;
- Neuroglancer opens through an HTTPS `/neuroglancer/v/...` URL;
- the viewer should show XRI fibre-like structures and mask overlay.

Known visual caveat:

- These XRI volumes can look banded/wavy compared with EM. That is expected for this fixture and should not be presented as mitochondria-like EM.

### 6. Propose Training From Ground Truth

Ask:

```text
train on the fully good masks to segment the image-only volumes
```

Expected:

- the agent should stage a `Train model` action;
- the card should say it found `6` fully good ground-truth volumes;
- it should leave `2` draft masks out of training;
- it should identify `2` image-only volumes as later inference targets;
- the action should be review/approval gated, not silently launched.

Expected staged training details:

- training image path is a generated subset directory under:

```text
/home/weidf/demo_data/.pytc_training_subsets/yixiao_tapereader_xri_case_study/
```

- training label path is the sibling `seg` subset directory;
- output/log path is under:

```text
/home/weidf/demo_data/yixiao_tapereader_xri_case_study/outputs/training/
```

- subset manifest exists and lists:
  - `6` train pairs;
  - `2` review pairs;
  - `2` target images.

### 7. Review Training Form

Click the training card's review/run affordance.

Expected:

- app navigates to `Train Model`;
- Input Image is populated with the generated subset `image` directory;
- Input Label is populated with the generated subset `seg` directory;
- Output Path is populated;
- Log Path is populated;
- config preset points to `TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`.

Do not start a long training job during a timed walkthrough unless the facilitator intends to show runtime behavior.

The smoke harness verifies that the worker-side PyTC path resolver can turn the subset directories into six concrete image/label files and validate a staged config. That is not the same as a full GPU training success.

### 8. Proofreading Story

Go to `Proofread`.

Use this narrative:

- `5_1` and `5_2` are draft masks that should be proofread before becoming training ground truth;
- after edits are saved and a volume is promoted, Progress should move it from `Needs proofreading` to `Fully good`;
- once promoted, the agent should include it in future training proposals.

Current caveat:

- If the browser proofreading editor does not yet provide a fully realistic edit/save/promote loop for this fixture, present this as the next closed-loop hardening task rather than claiming it is complete.

### 9. Inference Story

Use this narrative:

- `6_1` and `6_2` are image-only targets;
- the agent should not infer until a checkpoint exists;
- after training creates or registers a checkpoint, Run Model should target `6_1` and `6_2`;
- prediction artifacts should be written back into project memory and change Progress coverage.

Current caveat:

- There is no paper-faithful TapeReader checkpoint wired into the fixture yet. The app-compatible config is for workflow validation and sanity runs; the original barcode target is preserved separately because it requires TapeReader-specific branch semantics.

## Developer Smoke Contract

The automated harness currently checks:

- backend health;
- manifest has 10 volumes and the 6/2/2 split;
- project can be mounted;
- project suggestion/profile uses manifest roots;
- audit sees 8 image/mask pairs with matching shapes;
- workflow is patched to Yixiao context;
- project progress reports 10/6/2/2;
- canonical project memory uses `tapereader_xri_fiber`;
- Neuroglancer route returns a viewer URL and no false unpaired entries;
- agent can summarize project context;
- agent stages a review-gated training card;
- PyTC worker-side subset resolver accepts the staged training subset.

### Export Bundle Hygiene (Case-Study Runs)

Evidence exports can be large if raw image paths are copied. For repeated case-study
demonstrations, prefer manifest-only mode:

```bash
cd /home/weidf/deploy/pytc-client-demo2
python - <<'PY'
import requests

workflow_id = <WORKFLOW_ID>
requests.post(f"https://demo.seg.bio/api/workflows/{workflow_id}/export-bundle",
              params={"copy_manifest_only": True})
PY
```

The endpoint also supports:

- `copy_max_bytes` for general artifact copy cap;
- `raw_copy_max_bytes` for raw-like image paths (default `0`);
- `copy_manifest_only=true` to disable all artifact file copies while still emitting
  `artifact-paths.json`, `workflow-bundle.json`, and a copy summary.

With `--exercise-promotion`, it also checks:

- a draft volume can be promoted through the progress API;
- project memory exposes both legacy app status and canonical paper-facing status;
- progress changes to `7` fully good, `1` needs proofreading, `2` missing segmentation;
- the agent's next training proposal uses seven ground-truth training pairs.

For a fast pre-demo gate, run once:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --pre-demo-gate \
  --report /tmp/yixiao-case-study-pre-demo-gate-report.json
```

This runs:

- normal smoke (`--prepare-live`) with all baseline assertions,
- one promotion dry-run (`--exercise-promotion`),
- one final restore smoke to return the public workflow to the baseline `6/2/2` state.

By default it also runs lightweight endpoint checks on the restored workflow:

- `GET /api/workflows/{workflow_id}/case-study-readiness`,
- `POST /api/workflows/{workflow_id}/export-bundle`.

Disable those checks with:

```bash
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --pre-demo-gate \
  --skip-readiness-check \
  --skip-export-check
```

The command writes a single composite JSON report including step pass/fail and residual caveats (for example, readiness not yet met when no training/evaluation loop has been run).

If you only want a single smoke run, keep the legacy pattern:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/run_yixiao_case_study_smoke.py --prepare-live --verbose
```

### Closed-Loop Rehearsal With Withheld Masks

To verify the evidence/evaluation wiring for the two image-only targets without
launching GPU jobs, run:

```bash
cd /home/weidf/deploy/pytc-client-demo2
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --closed-loop-rehearsal \
  --closed-loop-training-iterations 2 \
  --closed-loop-inference-iterations 1 \
  --report /tmp/yixiao-closed-loop-rehearsal-report.json
```

This uses:

- image targets `6_1` and `6_2` from the mounted manifest;
- explicit withheld masks from `/home/weidf/demo_data/yixiao_tapereader_xri_case_study_holdout_masks`;
- a small crop by default: `0:8,0:128,0:128`;
- the existing `run_closed_loop_smoke.py` evidence harness, which now verifies:
  - training using explicit withheld target masks,
  - captured training checkpoints and inferred runtime model-version linkage,
  - inference runtime synchronization for each target inference pass,
  - metric evaluation against explicit withheld ground truth.

It deliberately refuses to use mounted project labels as truth for `6_1` or `6_2`.
Those volumes must remain image-only in the app-facing project. The withheld masks
are for operator-only evaluation/rehearsal after predictions exist. Rehearsal
fails if an explicit path is inside the mounted project root or resolves to the
mounted segmentation path.

Use a different crop for a bigger rehearsal:

```bash
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --closed-loop-rehearsal \
  --closed-loop-training-iterations 12 \
  --closed-loop-inference-iterations 8 \
  --closed-loop-crop "0:16,0:256,0:256"
```

Use full volumes only when you actually need it:

```bash
.venv/bin/python scripts/run_yixiao_case_study_smoke.py \
  --closed-loop-rehearsal \
  --closed-loop-crop ""
```

This rehearsal proves:

- the image-only targets have external ground-truth masks available for later evaluation;
- evaluation evidence can be produced with explicit withheld truth paths and explicit
  iteration overrides;
- target-level reports include `runtime_overrides`, `runtime_checkpoints`, and
  `runtime_sync` fields;
- export/readiness plumbing can represent before/after comparisons.

It does not prove:

- real TapeReader/PyTC training convergence;
- real inference quality on `6_1` or `6_2`;
- paper-faithful barcode-target reproduction.

## Known Gaps To Avoid Overclaiming

- The harness does not prove full GPU training convergence.
- The harness does not prove inference produces scientifically meaningful predictions.
- The harness does not prove browser-level proofreading edit quality.
- The app-compatible config is not identical to the original TapeReader barcode-target config.
- The case study currently proves workflow coordination, not segmentation accuracy.

## Good Paper Claim From This Demo

This case study can support a claim like:

> The system maintains a grounded project state for an XRI fibre segmentation workflow, distinguishes ground truth, draft masks, and image-only volumes, and turns a natural-language training request into an approval-gated, reproducible multi-volume training proposal.

For publication-level model claims, the claim boundary is:

- **Can claim now:** coordination behavior, grounded context, approval-gating.
- **Can claim after run evidence:** closed-loop training, post-training inference on `6_1` and `6_2`, and holdout-based evaluation.

Avoid claiming that the system has already reproduced TapeReader's model performance unless a separate evaluation run proves it.
