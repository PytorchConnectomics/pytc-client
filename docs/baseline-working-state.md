# Baseline working state — September 15, 2026

Active checkout: `pytc-agent-prototype`, branch `feat/project-manager-agents`.
This repairs the May 5 baseline before adding manager/task-agent integration.

## Repairs

- The launcher starts the UI, API and compute worker together. Browser API calls use
  a same-origin development proxy; this resolved the first-request network failures
  reproduced in the in-app browser. Action failures no longer escape the chat click
  handler and crash the screen.
- Files preview uses the real TIFF thumbnail endpoint instead of a placeholder URL.
  Navigation fits the window, with overflow tabs accessible through the menu.
- Saved project paths populate visualization, training and inference. Launched
  configurations persist in project metadata for reload. Opening a proofreading
  volume preserves the project directory; opening a viewer preserves established
  source-image and reference-label assignments.
- `POST /api/workflows/{id}/stage-corrections` checks session ownership and requires
  a saved, clean artifact. It commits staging and its evidence together and returns
  both training inputs. Repeating it for the same save reuses the evidence event.
  Published source labels are no longer a fallback for “saved corrections.”
- Erasing now actually removes pixels from the persisted mask. Save failures are
  reported instead of recording successful saves. Neighbor labels and source TIFFs
  remain intact.
- CPU requests run with CUDA disabled and one logical device in the legacy backend,
  avoiding a zero inference batch size. The original zero-GPU request remains in
  the stored configuration; runtime corrections are logged.
- Jobs are recorded as started after the worker accepts them. Runtime panels can
  resume polling an active job after reload and disregard another project's logs.
  Successful jobs are no longer marked failed because a warning mentions memory.
  TensorBoard connection failures stay inline, and hidden Monitor tabs stop polling.
- Inference has a **View prediction** handoff to the existing volume viewer.

## Verification

Computer use in the in-app browser verified project reload, first-request chat,
proposal approval, real TIFF preview, unsaved-correction rejection, erase/save,
staging into populated training inputs, training, checkpoint handoff, inference,
and inspection of the resulting prediction as a label overlay.

The isolated `NucMM engineering check` project (ID 2) used copies under
`uploads/NucMM-engineering`. A browser edit changed 159 voxels. The original and
copied reference labels still match exactly. Two CPU training iterations produced
`runs/train/checkpoint_00002.pth.tar` (6,429,621 bytes); inference produced finite
`runs/inference/result_xy.h5` data of shape `[2, 64, 96, 96]` (CZYX). Both processes
exited successfully. This checks execution, not segmentation accuracy.

- Backend: 107 tests passed, plus 5 subtests, covering runtime routes, workflow
  routes, mask persistence, worker service and file workspace routes.
- Frontend: 58 tests passed across workflow context, chat, runtime status, views,
  inference and files. Existing React/deprecation warnings remain.
- Final viewer checks: 16 additional tests passed for Neuroglancer URL contracts
  and volume normalization; seed and API modules also passed Python compilation.
- Machine-readable evidence: `.logs/agent-prototype/baseline-validation.json`.

The original `NucMM dummy project` (ID 1) is restored as current. Its labels have
not been scientifically reviewed or changed by this check. It has a two-step CPU
preset ready; no completed engineering run is attributed to that project.

## Run locally

From this checkout, with Python and Node dependencies installed:

```sh
git submodule update --init pytorch_connectomics
python scripts/seed_agent_demo.py  # only creates a project if none exists
bash scripts/start_agent_prototype.sh
```

The local machine currently reuses existing `.venv` and `client/node_modules`
installations. `PYTC_AGENT_PYTHON` and `PYTC_AGENT_NODE` override runtime binaries.
App: `http://127.0.0.1:3001/`; API: 4242; worker: 4243.
Logs: `.logs/agent-prototype/{api,client,worker}.log`.
The pinned compute checkout is `04c2a35e78a1a7ca1138f83a98fc3ef27097abd4`.

## Boundaries

The CPU preset is an engineering smoke configuration, not a useful trained nuclei
model. Two-channel predictions belong in the viewer's **Label** input, which builds
its existing preview segmentation. Raw multichannel predictions are not directly
editable instance-label TIFFs; exporting a chosen postprocessing result remains a
separate step. The viewer does not certify model quality or human proofreading.

This pass does not implement or validate LLM specialist delegation, the retired DSL,
a public deployment, or scientific before/after improvement. These remain separate
from the working local baseline. The earlier audit's network errors and failed runs
remain in history as evidence; they are not current successful results.
