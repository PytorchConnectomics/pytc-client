# PyTC Inference Guide

This document explains how to run inference (prediction) with a trained PyTorch Connectomics model.

## Inference Command

```
python scripts/main.py --config <config.yaml> --mode test --checkpoint <checkpoint.ckpt> [key=value overrides]
```

Example:
```
python scripts/main.py --config tutorials/mito_lucchi++.yaml --mode test --checkpoint outputs/mito_lucchi++/20241124_203930/checkpoints/last.ckpt
```

The `--mode test` flag switches the trainer to test/inference mode. A `--checkpoint` path is required to load the trained model weights.

## How Inference Works

1. The config file is loaded and test-stage settings override the training defaults (test data paths, output paths).
2. The model is built from the config and checkpoint weights are loaded.
3. The test volume is loaded and divided into overlapping patches via sliding window inference.
4. Each patch is fed through the model. If test-time augmentation is enabled, multiple augmented copies are predicted and aggregated.
5. Overlapping predictions are blended together (Gaussian blending by default).
6. Postprocessing and decoding are applied if configured.
7. The final prediction is saved to the output directory.

## Inference Configuration Options

### Sliding Window Settings

| Key | Description | Default |
|-----|-------------|---------|
| `inference.batch_size` | Batch size for inference | `1` |
| `inference.sliding_window.window_size` | Patch size `[z, y, x]` for sliding window inference | matches model input_size |
| `inference.sliding_window.sw_batch_size` | Number of patches per sliding window batch | `4` |
| `inference.sliding_window.overlap` | Overlap ratio between adjacent patches (0.0–1.0) | `0.5` |
| `inference.sliding_window.blending` | Blending mode: `'gaussian'` or `'constant'` | `'gaussian'` |
| `inference.sliding_window.sigma_scale` | Sigma scale for Gaussian blending | `0.25` |
| `inference.sliding_window.padding_mode` | Padding mode: `'reflect'`, `'constant'`, etc. | `'reflect'` |

### Test-Time Augmentation (TTA)

| Key | Description | Default |
|-----|-------------|---------|
| `inference.test_time_augmentation.enabled` | Enable TTA | `true` or `false` (config-dependent) |
| `inference.test_time_augmentation.flip_axes` | Flip axes for TTA: `'all'` or list of axis combinations | `'all'` |
| `inference.test_time_augmentation.rotation90_axes` | Rotation axes for TTA: `'all'` or list | None |
| `inference.test_time_augmentation.ensemble_mode` | Aggregation mode: `'mean'` or `'min'` | `'mean'` |
| `inference.test_time_augmentation.channel_activations` | Per-channel activation functions | varies |
| `inference.test_time_augmentation.distributed_sharding` | Distribute TTA across GPUs | `false` |

### Postprocessing and Decoding

| Key | Description | Default |
|-----|-------------|---------|
| `inference.postprocessing.enabled` | Enable postprocessing | `false` |
| `inference.postprocessing.crop_pad` | Crop padding from predictions | None |
| `inference.decoding` | List of decoding profiles (e.g., ABISS watershed) | None |

### Save Prediction

| Key | Description | Default |
|-----|-------------|---------|
| `inference.save_prediction.enabled` | Save prediction to disk | `true` |
| `inference.save_prediction.intensity_scale` | Scale intensity values (-1 = disabled) | `-1` |
| `inference.save_prediction.intensity_dtype` | Output data type | `float32` |
| `inference.save_prediction.output_formats` | Output file format(s) | `[h5]` |

### Evaluation

| Key | Description | Default |
|-----|-------------|---------|
| `inference.evaluation.enabled` | Run evaluation metrics after inference | `true` or `false` |
| `inference.evaluation.metrics` | List of metrics: `jaccard`, `adapted_rand`, `cremi_distance`, etc. | varies |

### Test Data

| Key | Description | Example |
|-----|-------------|---------|
| `test.data.test.image` | Test image file path(s) | `datasets/lucchi++/test_im.h5` |
| `test.data.test.label` | Test label file path(s) (for evaluation) | `datasets/lucchi++/test_mito.h5` |
| `test.data.test.resolution` | Test data voxel resolution | `[5, 5, 5]` |
| `test.output_path` | Directory where predictions are saved | `outputs/<experiment>/results/` |

## Test-Time Augmentation (TTA)

TTA applies geometric augmentations (flips, 90° rotations) to the input, runs the model on each augmented copy, and aggregates predictions.

- **`flip_axes: all`**: All combinations of axis flips (2^D variants for D spatial dimensions).
- **`ensemble_mode: mean`**: Average all predictions (recommended for most tasks).
- **`ensemble_mode: min`**: Take the minimum prediction (useful for conservative boundary detection in affinity maps).

## Sliding Window and Blending

The sliding window controls how the volume is split into overlapping patches:
- **Higher overlap** (e.g., `0.5`) = smoother results, but slower.
- **Lower overlap** (e.g., `0.25`) = faster, but may show tile boundary artifacts.
- `'gaussian'` blending weights the center of each patch more heavily, producing smooth transitions.

## Multi-Volume and Sharded Inference

For multi-volume datasets, test data paths can be lists. For distributed inference across multiple machines:
```
python scripts/main.py --config <config.yaml> --mode test --checkpoint <ckpt> --shard-id 0 --num-shards 4
python scripts/main.py --config <config.yaml> --mode test --checkpoint <ckpt> --shard-id 1 --num-shards 4
```

## Cache-Aware Inference

PyTC automatically detects cached prediction files and skips redundant inference. This is useful when re-running postprocessing or evaluation without re-computing predictions.

## Tips

- Use the same config file for inference that was used for training. Only override test-specific settings.
- Increase `inference.sliding_window.sw_batch_size` to speed up inference if GPU memory allows.
- Enable TTA (`inference.test_time_augmentation.enabled=true`) for better accuracy at the cost of speed.
- Checkpoint files use `.ckpt` extension (PyTorch Lightning format).
- The output directory is automatically created based on the checkpoint path.
