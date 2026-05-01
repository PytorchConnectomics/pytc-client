# PyTorch Connectomics (PyTC) — Overview

PyTorch Connectomics (PyTC) is a deep-learning framework for automatic and semi-automatic **semantic and instance segmentation** of volumetric biomedical images, especially electron-microscopy (EM) connectomics data. It is built on PyTorch Lightning and uses Hydra for configuration management.

## What PyTC Can Do

PyTC supports the following segmentation tasks out of the box:

- **Binary semantic segmentation** — e.g., mitochondria vs. background (Lucchi dataset).
- **Instance segmentation via affinity maps** — e.g., neuron boundary detection (SNEMI, CREMI) with ABISS watershed decoding.
- **Multi-task BCD segmentation** — binary + boundary contour + distance transform prediction.
- **Nucleus segmentation** — e.g., NucMM zebrafish nuclei.
- **Synaptic cleft detection** — e.g., CREMI synapse detection.
- **Large-scale processing** — training and inference for large datasets.
- **Hyperparameter tuning** — built-in Optuna-based parameter search (e.g., watershed thresholds).

## Supported Data Formats

- **Images**: TIFF stacks (`.tif`), HDF5 (`.h5`).
- **Labels**: Same formats as images; can be binary masks, instance labels, or multi-class label volumes.
- **Data dimensionality**: Both **3D** volumetric data and **2D** image data are supported.

## Key Capabilities

- **Profile-based configuration**: Reusable presets for architectures, optimizers, augmentations, and pipelines.
- **Multi-task learning**: Train a single model with multiple loss functions and target types simultaneously.
- **Automatic distributed training**: Multi-GPU training via PyTorch Lightning with automatic mixed-precision.
- **Comprehensive data augmentation**: Profile-based augmentation system with 10+ augmentation types designed for EM data, including missing-section simulation, misalignment, and motion blur.
- **Flexible model zoo**: MONAI UNet, RSUNet, and MedNeXt architectures with configurable parameters.
- **Hydra configuration system**: All settings are controlled via YAML config files with dot-separated key overrides on the command line.
- **EMA (Exponential Moving Average)**: Built-in support for improved generalization.
- **Test-time augmentation**: Flip and rotation augmentation with configurable ensemble modes (mean, min).
- **Cache-aware inference**: Automatically detects and reuses cached predictions.
- **Sharded inference**: Distribute inference across multiple machines.

## Entry Point

All training and inference is launched through a single script:

```
python scripts/main.py --config <path/to/config.yaml> [OPTIONS] [key=value overrides]
```

Key flags:
- `--config` (required): Path to the YAML configuration file (relative to PyTC root, e.g., `tutorials/mito_lucchi++.yaml`).
- `--mode`: Mode of operation: `train` (default), `test`, `tune`, `tune-test`.
- `--checkpoint`: Path to a model checkpoint (`.ckpt`) for resuming training or running inference.
- `--fast-dev-run`: Run 1 batch for quick debugging.
- `--demo`: Quick demo using `tutorials/minimal.yaml`.
- `--debug-config`: Print fully resolved config and exit.
- `--reset-max-epochs N`: Reset max_epochs when resuming training.
- `--shard-id` / `--num-shards`: For distributed test sharding.
- `key=value` (positional): Override any config option using Hydra dot-path syntax.

Example overrides:
```
python scripts/main.py --config tutorials/mito_lucchi++.yaml \
    optimization.optimizer.lr=0.001 data.dataloader.batch_size=4
```

## What PyTC Cannot Do

PyTC is a **segmentation-only** framework. It does not support:
- Object detection (bounding boxes).
- Image classification.
- Generative models (GANs, diffusion).
- Non-image modalities (text, audio).
- Models or architectures not listed in the model zoo (monai_unet, rsunet, mednext).

If a user asks to train a model or run a task that is not one of the supported segmentation tasks listed above, the request cannot be fulfilled with PyTC.
