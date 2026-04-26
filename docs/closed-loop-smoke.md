# Closed-Loop Workflow Smoke

Run this when you want a quick researcher/developer check that the workflow evidence substrate still works:

```bash
uv run python scripts/run_closed_loop_smoke.py --output-dir /tmp/pytc-closed-loop-smoke
```

To run against the mito25 real image/segmentation pair without loading the full volume:

```bash
uv run python scripts/run_closed_loop_smoke.py \
  --output-dir /tmp/pytc-mito25-smoke \
  --image-path /Users/adamg/seg.bio/pytc-client/testing_projects/mito25_paper_loop_smoke/data/image/mito25_smoke_13312-15360_im.h5 \
  --mask-path /Users/adamg/seg.bio/pytc-client/testing_projects/mito25_paper_loop_smoke/data/seg/mito25_smoke_13312-15360_seg.h5 \
  --image-dataset main \
  --mask-dataset data
```

If real prediction files exist, pass them directly instead of deriving
baseline/candidate masks from the segmentation:

```bash
uv run python scripts/run_closed_loop_smoke.py \
  --output-dir /tmp/pytc-real-prediction-smoke \
  --image-path /path/to/image.h5 \
  --mask-path /path/to/initial-or-ground-truth-mask.h5 \
  --image-dataset main \
  --mask-dataset data \
  --baseline-prediction-path /path/to/baseline-prediction.h5 \
  --candidate-prediction-path /path/to/candidate-prediction.h5 \
  --baseline-dataset prediction \
  --candidate-dataset prediction \
  --crop 0:16,0:256,768:1024
```

For PyTC outputs such as `result_xy.h5`, pass the HDF5 dataset and select the
prediction channel to compare:

```bash
uv run python scripts/run_closed_loop_smoke.py \
  --output-dir /tmp/pytc-app-prediction-smoke \
  --image-path /Users/adamg/seg.bio/pytc-client/testing_projects/mito25_paper_loop_smoke/data/image/mito25_smoke_13312-15360_im.h5 \
  --mask-path /Users/adamg/seg.bio/pytc-client/testing_projects/mito25_paper_loop_smoke/data/seg/mito25_smoke_13312-15360_seg.h5 \
  --image-dataset main \
  --mask-dataset data \
  --baseline-prediction-path /Users/adamg/seg.bio/pytc-client/testing_projects/mito25_paper_loop_smoke/predictions/baseline_result_xy.h5 \
  --candidate-prediction-path /Users/adamg/seg.bio/pytc-client/testing_projects/mito25_paper_loop_smoke/predictions/candidate_result_xy.h5 \
  --baseline-dataset vol0 \
  --candidate-dataset vol0 \
  --baseline-channel 0 \
  --candidate-channel 0
```

For manual UI checks, use File Management -> `Mount Test Project`. The suggested
project card should report detected image, label, prediction, config, and
checkpoint roles before mounting.

The smoke creates or stages voxel artifacts, drives the FastAPI workflow API through dataset loading, baseline inference capture, proofreading correction capture, correction staging, retraining completion capture, candidate inference capture, before/after evaluation, researcher-only readiness gates, and bundle export.

What this proves:

- Workflow events materialize typed artifacts, model runs, model versions, correction sets, evaluation results, hotspots, and bundle records.
- Correction-set records include edit and region counts derived from the
  proofreading event stream when corrections are exported.
- Evidence bundle exports are recorded as `workflow.bundle_exported` audit
  events.
- The before/after evaluation path computes real segmentation metrics over TIFF, HDF5, NumPy, Zarr/N5, and common 2D image files, with optional NIfTI/MRC support if their parser packages are installed.
- The researcher-only readiness/export path can produce an evidence bundle for planning a case-study walkthrough.
- In `real_pair_real_predictions` mode, supplied prediction artifacts are used for the metric comparison.
- PyTC channel-first/channel-last prediction outputs can be reduced to 3D voxel volumes with `--baseline-channel` and `--candidate-channel`.

What this does not prove yet:

- Real PyTC training subprocess execution.
- Real PyTC inference subprocess execution.
- Browser-level proofreading interaction inside EHTool.
- Real biomedical or connectomics sample-data performance in synthetic mode.
- Real model predictions in `real_pair_derived_predictions` mode; baseline/candidate masks are derived from the provided segmentation unless prediction paths are supplied.
- Fresh PyTC subprocess launch quality; app-generated prediction files can now be captured into workflow evidence, but launching/recovering long-running jobs still needs hardening.
- Long-running job queue behavior, retries, cancellation, or recovery.

Outputs:

- `smoke-report.json`: concise pass/fail summary and explicit simulated gaps.
- `workflow-bundle.json`: exported workflow evidence bundle.
- `readiness.json`: researcher-only readiness gate state.
- `evaluation-report.json`: before/after metric report.
- `artifacts/`: synthetic TIFFs, placeholder checkpoint, and training-output directory.
