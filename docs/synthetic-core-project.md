# Synthetic Core Project

The local app now starts with a deterministic synthetic segmentation project by default. It formalizes one fixed development paradigm across the actual file workspace, project scanner, chunked volume reader, workflow state, progress tracker, viewer, proofreading flow, agent context, training handoff, and evaluation surfaces.

## Canonical State

The generated project lives at `.pytc/synthetic-core-project` and contains four compressed, chunked HDF5 image volumes:

| Volume | Initial state | Intended workflow role |
| --- | --- | --- |
| `train-01` | Ground truth | Training source |
| `train-02` | Ground truth | Training source |
| `review-01` | Imperfect draft | Proofreading and correction |
| `target-01` | Image only | Inference target |

The expected progress state is always **4 total / 2 ground truth / 1 needs proofreading / 1 missing segmentation**. Baseline and corrected candidate predictions are prepopulated for comparison. The data are only for interaction and systems testing; they are not scientific evidence or a model-quality benchmark.

## Run

From the repository root:

```bash
./scripts/start.sh
```

Startup creates the fixture if absent, uses `.pytc/synthetic-core.db`, seeds the current workflow, mounts the project into the file browser, builds the client, and launches Electron.

Normal startup preserves edits made inside the generated project. Restore the exact canonical files and state with:

```bash
PYTC_SYNTHETIC_PROJECT_RESET=1 ./scripts/start.sh
```

Generate or reset the fixture without starting the app:

```bash
uv run python scripts/create_synthetic_project.py --reset
```

Disable the development fixture and use the previous project/database behavior:

```bash
PYTC_SYNTHETIC_PROJECT=0 ./scripts/start.sh
```

Supplying `PYTC_INITIAL_PROJECT_ROOT` also takes precedence over synthetic mode.

## Core Test Sequence

1. Confirm the project is already mounted and the progress tracker reports `2 / 1 / 1`.
2. Open a training image and ground-truth label in the storage-backed viewer.
3. Open `review-01`, compare the baseline and candidate, and proofread the draft.
4. Ask the workflow agent for project status and the next recommended action.
5. Stage training from only the two confirmed ground-truth volumes.
6. Select `target-01` for inference and verify that the output is registered.
7. Inspect operation progress, cancellation, failure, and retry states.
8. Reset the fixture before repeating a canonical acceptance run.
