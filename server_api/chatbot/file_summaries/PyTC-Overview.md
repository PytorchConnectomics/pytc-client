# PyTorch Connectomics (PyTC) — Overview

PyTorch Connectomics (PyTC) is a deep-learning framework for automatic and semi-automatic **semantic and instance segmentation** of volumetric biomedical images, especially electron-microscopy (EM) connectomics data. It is built on PyTorch and maintained by the Visual Computing Group (VCG) at Harvard University.

## What PyTC Can Do

PyTC supports the following segmentation tasks out of the box:

- **Binary semantic segmentation** — e.g., mitochondria vs. background (Lucchi dataset).
- **Instance segmentation via affinity maps** — e.g., neuron boundary detection (SNEMI, CREMI).
- **Multi-class semantic segmentation** — e.g., labeling 12+ organelle types in a single volume.
- **Nucleus segmentation** — e.g., NucMM mouse and zebrafish nuclei.
- **Cell segmentation with flow fields** — e.g., Cellpose-style gradient prediction.
- **Distance-transform prediction** — boundary distance maps for watershed-based instance segmentation.
- **Synaptic cleft detection** — e.g., CREMI synapse detection.
- **Large-scale tile-based processing** — chunked training and inference for datasets that do not fit in memory (MitoEM, Scutoid).

## Supported Data Formats

- **Images**: TIFF stacks (`.tif`), HDF5 (`.h5`), JSON tile manifests (`.json`).
- **Labels**: Same formats as images; can be binary masks, instance labels, or multi-class label volumes.
- **Data dimensionality**: Both **3D** volumetric data and **2D** image data are supported. Set `DATASET.DO_2D: True` for 2D mode.

## Key Capabilities

- **Multi-task learning**: Train a single model with multiple loss functions and target types simultaneously.
- **Distributed training**: Multi-GPU training via DataParallel (DP) or DistributedDataParallel (DDP) with optional mixed-precision.
- **Comprehensive data augmentation**: 11 augmentation types designed specifically for EM data, including missing-section simulation, misalignment, and motion blur.
- **Flexible model zoo**: Multiple encoder-decoder architectures (UNet 3D/2D, UNet++, FPN, UNETR, Swin UNETR, DeepLabV3) with configurable block types and backbones.
- **YACS configuration system**: All settings are controlled via YAML config files. Any default can be overridden on the command line.
- **Stochastic Weight Averaging (SWA)**: Built-in support for improved generalization.
- **Inference augmentation**: Test-time augmentation with configurable modes (mean, min) and number of augmented copies.

## Entry Point

All training and inference is launched through a single script:

```
python scripts/main.py --config-file <path/to/config.yaml> [OPTIONS] [OVERRIDES]
```

Key flags:
- `--config-file` (required): Path to the YAML configuration file.
- `--config-base`: Optional base config that the main config extends.
- `--inference`: Run inference instead of training.
- `--checkpoint`: Path to a model checkpoint for resuming training or running inference.
- `--distributed`: Enable distributed multi-GPU training (DDP).
- `SECTION.KEY=value` (positional): Override any config option on the command line.

## What PyTC Cannot Do

PyTC is a **segmentation-only** framework. It does not support:
- Object detection (bounding boxes).
- Image classification.
- Generative models (GANs, diffusion).
- Non-image modalities (text, audio).
- Models or architectures not listed in the model zoo (unet_3d, unet_2d, fpn_3d, unet_plus_3d, unet_plus_2d, deeplabv3a/b/c, unetr, swinunetr).

If a user asks to train a model or run a task that is not one of the supported segmentation tasks listed above, the request cannot be fulfilled with PyTC.
