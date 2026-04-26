# Mito25 Paper Loop Smoke Project

Use this mounted project to test the current prototype checkpoint without
digging through unrelated folders.

## What To Test

- Open File Management and confirm `mito25-paper-loop-smoke` is mounted.
- In `data/image`, use `mito25_smoke_13312-15360_im.h5` with dataset key `main`.
- In `data/seg`, use `mito25_smoke_13312-15360_seg.h5` with dataset key `data`.
- In `configs`, use `Mito25-Local-Smoke-BC.yaml` for smoke inference/training checks.
- In `checkpoints`, use `checkpoint_00001.pth.tar`.
- In `predictions`, use `baseline_result_xy.h5` and `candidate_result_xy.h5`, dataset `vol0`, channel `0`, for before/after smoke evaluation.

## Known Boundary

This mount contains existing smoke artifacts. It is for validating file picking,
workflow capture, helper stability, and prediction-ingestion paths. A fresh
app-launched inference/retraining loop is still the next prototype checkpoint.
