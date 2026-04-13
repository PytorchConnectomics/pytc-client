# PyTC Training Guide

This document explains how to configure and run training jobs with PyTorch Connectomics.

## Training Command

```
python scripts/main.py --config-file <config.yaml> [OVERRIDES]
```

Example:
```
python scripts/main.py --config-file configs/Lucchi-Mitochondria.yaml SOLVER.BASE_LR=0.001 SOLVER.SAMPLES_PER_BATCH=4
```

Overrides use dotted YAML key paths: `SECTION.KEY=value`. Multiple overrides can be appended.

## Required Configuration Sections

Every training config must specify at minimum: a model architecture, dataset paths, and solver settings. The YAML files in the `configs/` directory provide complete working examples; users should start from the closest matching config and modify it rather than writing one from scratch.

### DATASET Section

| Key | Description | Default |
|-----|-------------|---------|
| `DATASET.INPUT_PATH` | Root directory containing images and labels | `'path/to/input'` |
| `DATASET.IMAGE_NAME` | Image filename(s) relative to INPUT_PATH. Multiple files separated by `@` | None |
| `DATASET.LABEL_NAME` | Label filename(s) relative to INPUT_PATH. Multiple files separated by `@` | None |
| `DATASET.OUTPUT_PATH` | Directory where checkpoints and logs are saved | `'path/to/output'` |
| `DATASET.PAD_SIZE` | Padding `[z, y, x]` to avoid border sampling issues | `[2, 64, 64]` |
| `DATASET.IS_ISOTROPIC` | Whether the voxels are cubic (isotropic) | `False` |
| `DATASET.DO_2D` | Enable 2D training mode | `False` |
| `DATASET.LOAD_2D` | Load data as 2D slices | `False` |
| `DATASET.DATA_SCALE` | Scale ratio `[z, y, x]` for resampling input | `[1.0, 1.0, 1.0]` |
| `DATASET.MEAN` | Normalization mean | `0.5` |
| `DATASET.STD` | Normalization std | `0.5` |
| `DATASET.LABEL_BINARY` | Binarize the label volume | `False` |
| `DATASET.LABEL_EROSION` | Erode label masks by N pixels | None |
| `DATASET.DO_CHUNK_TITLE` | Enable tile-based (chunked) training for large datasets | `0` |
| `DATASET.DATA_CHUNK_NUM` | Number of chunks `[z, y, x]` for tiled data | `[1, 1, 1]` |
| `DATASET.DATA_CHUNK_ITER` | Iterations per chunk | `1000` |
| `DATASET.REJECT_SAMPLING.SIZE_THRES` | Reject patches with foreground below this threshold (-1 = disabled) | `-1` |
| `DATASET.REJECT_SAMPLING.P` | Probability of applying reject sampling | `0.95` |

### SOLVER Section (Training Hyperparameters)

| Key | Description | Default |
|-----|-------------|---------|
| `SOLVER.NAME` | Optimizer name: `"SGD"`, `"Adam"`, `"AdamW"` | `"SGD"` |
| `SOLVER.BASE_LR` | Base learning rate | `0.001` |
| `SOLVER.MOMENTUM` | SGD momentum | `0.9` |
| `SOLVER.BETAS` | Adam/AdamW beta parameters | `(0.9, 0.999)` |
| `SOLVER.WEIGHT_DECAY` | Weight decay | `0.0001` |
| `SOLVER.LR_SCHEDULER_NAME` | LR scheduler: `"MultiStepLR"`, `"WarmupMultiStepLR"`, `"WarmupCosineLR"`, `"ReduceLROnPlateau"`, `"OneCycle"` | `"MultiStepLR"` |
| `SOLVER.STEPS` | Milestones for MultiStepLR | `(30000, 35000)` |
| `SOLVER.GAMMA` | LR decay factor at each step | `0.1` |
| `SOLVER.WARMUP_ITERS` | Number of warmup iterations | `1000` |
| `SOLVER.WARMUP_FACTOR` | Initial LR multiplier during warmup | `1/1000` |
| `SOLVER.SAMPLES_PER_BATCH` | Number of samples per GPU per batch | `2` |
| `SOLVER.ITERATION_TOTAL` | Total training iterations | `40000` |
| `SOLVER.ITERATION_SAVE` | Save a checkpoint every N iterations | `5000` |
| `SOLVER.ITERATION_VAL` | Run validation every N iterations | `5000` |
| `SOLVER.ITERATION_RESTART` | Restart iteration counter from 0 when loading a pretrained model | `False` |
| `SOLVER.CLIP_GRADIENTS.ENABLED` | Enable gradient clipping | `False` |
| `SOLVER.CLIP_GRADIENTS.CLIP_TYPE` | Clipping type: `"value"` or `"norm"` | `"value"` |
| `SOLVER.CLIP_GRADIENTS.CLIP_VALUE` | Clipping threshold | `1.0` |
| `SOLVER.SWA.ENABLED` | Enable Stochastic Weight Averaging | `False` |
| `SOLVER.SWA.START_ITER` | Iteration to begin SWA | `90000` |
| `SOLVER.SWA.LR_FACTOR` | SWA learning rate = BASE_LR × LR_FACTOR | `0.05` |

### MONITOR Section

| Key | Description | Default |
|-----|-------------|---------|
| `MONITOR.LOG_OPT` | Logging options `[loss, lr, gpu_usage]` (1=on, 0=off) | `[1, 1, 0]` |
| `MONITOR.VIS_OPT` | Visualization options `[image, feature_map]` | `[0, 16]` |
| `MONITOR.ITERATION_NUM` | Log every N[0] iters; visualize every N[1] iters | `[20, 200]` |

### SYSTEM Section

| Key | Description | Default |
|-----|-------------|---------|
| `SYSTEM.NUM_GPUS` | Number of GPUs | `4` |
| `SYSTEM.NUM_CPUS` | Number of CPU workers for data loading | `4` |
| `SYSTEM.DISTRIBUTED` | Use DistributedDataParallel | `False` |
| `SYSTEM.PARALLEL` | Parallelism mode: `'DP'` (DataParallel) or `'DDP'` | `'DP'` |

## Distributed Training

To run multi-GPU training with DDP:
```
python -m torch.distributed.launch --nproc_per_node=<NUM_GPUS> scripts/main.py --distributed --config-file <config.yaml>
```

Mixed-precision training (`MODEL.MIXED_PRECESION: True`) only works with DDP.

## Resuming Training

To resume from a checkpoint:
```
python scripts/main.py --config-file <config.yaml> --checkpoint <path/to/checkpoint.pth.tar>
```

Training resumes from the saved iteration unless `SOLVER.ITERATION_RESTART: True` is set.

## Transfer Learning / Fine-tuning

Set `MODEL.PRE_MODEL` to the path of a pretrained checkpoint. The model will load those weights before training begins. Use `MODEL.FINETUNE` to add a suffix to saved checkpoint names so they do not overwrite the original.

## Tips

- Start from the closest bundled config in `configs/` and override only what you need.
- For anisotropic EM data, use odd input sizes (e.g., `[17, 257, 257]`) when not using pooling layers to avoid feature mismatching.
- For isotropic data, set `DATASET.IS_ISOTROPIC: True` and `AUGMENTOR.FLIP.DO_ZTRANS: 1` to enable z-axis augmentation.
- Use `DATASET.REJECT_SAMPLING.SIZE_THRES` to avoid sampling empty patches in sparse datasets.
- The output directory receives checkpoints (`checkpoint_NNNNN.pth.tar`) and a `config.yaml` snapshot.
