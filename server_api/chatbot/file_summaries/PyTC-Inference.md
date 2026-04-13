# PyTC Inference Guide

This document explains how to run inference (prediction) with a trained PyTorch Connectomics model.

## Inference Command

```
python scripts/main.py --config-file <config.yaml> --inference --checkpoint <checkpoint.pth.tar> [OVERRIDES]
```

Example:
```
python scripts/main.py --config-file configs/Lucchi-Mitochondria.yaml --inference --checkpoint outputs/Lucchi_UNet/checkpoint_100000.pth.tar
```

The `--inference` flag switches the trainer to test mode. A `--checkpoint` path is required to load the trained model weights.

## How Inference Works

1. The config file is loaded and inference-specific settings override the training defaults (input path, image name, output path, pad size, input/output size).
2. The model is built from the config and checkpoint weights are loaded.
3. The test volume is loaded and divided into overlapping patches based on `INFERENCE.INPUT_SIZE` and `INFERENCE.STRIDE`.
4. Each patch is fed through the model. If test-time augmentation is enabled, multiple augmented copies are predicted and aggregated.
5. Overlapping predictions are blended together (Gaussian blending by default).
6. The final prediction is saved to the output directory.

## INFERENCE Configuration Options

| Key | Description | Default |
|-----|-------------|---------|
| `INFERENCE.INPUT_SIZE` | Patch size `[z, y, x]` for inference (overrides MODEL.INPUT_SIZE) | None (uses model size) |
| `INFERENCE.OUTPUT_SIZE` | Output patch size `[z, y, x]` (overrides MODEL.OUTPUT_SIZE) | None (uses model size) |
| `INFERENCE.IMAGE_NAME` | Test image filename(s) relative to input path | None |
| `INFERENCE.INPUT_PATH` | Override DATASET.INPUT_PATH for inference | None |
| `INFERENCE.OUTPUT_PATH` | Directory where predictions are saved | `""` |
| `INFERENCE.OUTPUT_NAME` | Output filename (e.g., `result.h5`, `pred`) | `'result.h5'` |
| `INFERENCE.PAD_SIZE` | Padding `[z, y, x]` for inference volumes | None (uses dataset pad) |
| `INFERENCE.STRIDE` | Stride `[z, y, x]` between patches. Smaller stride = more overlap = smoother results but slower | `[4, 128, 128]` |
| `INFERENCE.BLENDING` | Blending mode for overlapping patches: `'gaussian'` or `'bump'` | `'gaussian'` |
| `INFERENCE.OUTPUT_ACT` | Activation function(s) for output: `'sigmoid'`, `'softmax'`, `'tanh'` | `['sigmoid']` |
| `INFERENCE.AUG_MODE` | Test-time augmentation aggregation: `'mean'` or `'min'` | `'mean'` |
| `INFERENCE.AUG_NUM` | Number of augmented copies for TTA. Set to None to disable TTA | None |
| `INFERENCE.SAMPLES_PER_BATCH` | Batch size for inference (patches per GPU) | `4` |
| `INFERENCE.DO_EVAL` | Run with `model.eval()` (affects batchnorm/dropout) | `True` |
| `INFERENCE.DO_SINGLY` | Process volumes one at a time (for multi-volume datasets) | `False` |
| `INFERENCE.DO_SINGLY_START_INDEX` | Starting index when DO_SINGLY is True | `0` |
| `INFERENCE.DO_SINGLY_STEP` | Step between volumes in DO_SINGLY mode | `1` |
| `INFERENCE.DATA_SCALE` | Override DATASET.DATA_SCALE for inference | None |
| `INFERENCE.OUTPUT_SCALE` | Rescale predictions after model output `[z, y, x]` | `[1.0, 1.0, 1.0]` |

## Inference Output

- By default, predictions are saved as HDF5 files (`.h5`) in the `INFERENCE.OUTPUT_PATH` directory.
- For chunked or DO_SINGLY inference, the output filename is a stem (e.g., `result`) and files are saved per volume.
- For multi-class segmentation (`TARGET_OPT: ["9-N"]`), the output activation is automatically set to softmax if not specified.

## Test-Time Augmentation (TTA)

TTA applies geometric augmentations (flips, rotations) to the input, runs the model on each augmented copy, and aggregates the predictions.

- `INFERENCE.AUG_NUM`: Number of augmented copies. Common values: `4`, `8`, `16`. Set to `None` to disable.
- `INFERENCE.AUG_MODE`:
  - `'mean'`: Average all predictions (recommended for most tasks).
  - `'min'`: Take the minimum prediction (useful for conservative boundary detection).

## Inference Stride and Blending

The inference stride controls how much overlap there is between adjacent patches:
- **Smaller stride** = more overlap = smoother results, but slower.
- **Larger stride** = less overlap = faster, but may show tile boundary artifacts.
- `'gaussian'` blending weights the center of each patch more heavily, producing smooth transitions.

## Large-Scale (Chunked) Inference

For datasets too large to fit in memory, use tiled inference:
```yaml
INFERENCE:
  DO_CHUNK_TITLE: 1
  DATA_CHUNK_NUM: [4, 8, 8]
```
The volume is split into chunks that are processed sequentially.

## Tips

- Use the same config file for inference that was used for training. Only override inference-specific settings.
- Increase `INFERENCE.SAMPLES_PER_BATCH` to speed up inference if GPU memory allows.
- Increase `INFERENCE.AUG_NUM` (e.g., 8 or 16) for better accuracy at the cost of speed.
- For multi-volume datasets (like CREMI with volumes A, B, C), set `INFERENCE.DO_SINGLY: True`.
- The output directory must exist or the script will create it automatically.
