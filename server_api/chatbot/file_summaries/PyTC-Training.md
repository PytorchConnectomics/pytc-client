# PyTC Training Guide

This document explains how to configure and run training jobs with PyTorch Connectomics.

## Training Command

```
python scripts/main.py --config <config.yaml> [key=value overrides]
```

Example:
```
python scripts/main.py --config tutorials/mito_lucchi++.yaml optimization.optimizer.lr=0.001 data.dataloader.batch_size=4
```

Overrides use Hydra/OmegaConf dot-separated key paths: `section.subsection.key=value`. Multiple overrides can be appended.

## Required Configuration Sections

Every training config must specify at minimum: a model architecture, dataset paths, and optimization settings. The YAML files in the `tutorials/` directory provide complete working examples; users should start from the closest matching config and modify it rather than writing one from scratch. Configs use a profile-based system where base profiles (in `tutorials/bases/`) define reusable presets for architectures, optimizers, augmentations, etc.

### Data Section

| Key | Description | Example |
|-----|-------------|---------|
| `data.train.image` | Path(s) to training image file(s) | `datasets/lucchi++/train_im.h5` |
| `data.train.label` | Path(s) to training label file(s) | `datasets/lucchi++/train_mito.h5` |
| `data.train.resolution` | Voxel resolution `[z, y, x]` in nm | `[5, 5, 5]` |
| `data.dataloader.batch_size` | Number of samples per batch | `8` |
| `data.dataloader.patch_size` | Training patch size `[z, y, x]` | `[112, 112, 112]` |
| `data.dataloader.profile` | Dataloader profile: `cached` or `lazy` | `cached` |
| `data.data_transform.pad_size` | Padding `[z, y, x]` for context | `[8, 128, 128]` |
| `data.augmentation.profile` | Augmentation profile (see PyTC-Augmentation) | `aug_standard` |
| `data.image_transform.clip_percentile_low` | Low percentile for intensity clipping | `0.0` |
| `data.image_transform.clip_percentile_high` | High percentile for intensity clipping | `1.0` |

### Optimization Section (Training Hyperparameters)

| Key | Description | Default |
|-----|-------------|---------|
| `optimization.optimizer.name` | Optimizer: `"AdamW"`, `"Adam"`, `"SGD"` | `"AdamW"` |
| `optimization.optimizer.lr` | Learning rate | `0.0003` |
| `optimization.optimizer.weight_decay` | Weight decay | `0.01` |
| `optimization.optimizer.betas` | Adam/AdamW beta parameters | `[0.9, 0.999]` |
| `optimization.optimizer.eps` | Epsilon for numerical stability | `1.0e-08` |
| `optimization.max_steps` | Total training steps (alternative to max_epochs) | varies |
| `optimization.max_epochs` | Total training epochs | `100` |
| `optimization.n_steps_per_epoch` | Steps per epoch | `1000` |
| `optimization.gradient_clip_val` | Gradient clipping value | `1.0` |
| `optimization.accumulate_grad_batches` | Gradient accumulation steps | `1` |
| `optimization.precision` | Training precision: `bf16-mixed`, `16-mixed`, `32` | `bf16-mixed` |
| `optimization.profile` | Optimizer profile preset (see below) | `warmup_cosine_lr` |

### Optimizer Profiles

Instead of configuring each optimizer/scheduler field individually, you can use a predefined profile:

| Profile | Optimizer | Scheduler | Description |
|---------|-----------|-----------|-------------|
| `warmup_cosine_lr` | AdamW (lr=0.0003) | WarmupCosineLR | Warmup then cosine decay (recommended) |
| `cosine_annealing_lr` | AdamW (lr=0.0003) | CosineAnnealingLR | Standard cosine annealing |
| `reduce_on_plateau` | AdamW (lr=0.0003) | ReduceLROnPlateau | Reduce LR when loss plateaus |
| `step_lr` | AdamW (lr=0.0003) | StepLR | Step decay every N epochs |
| `multistep_lr` | AdamW (lr=0.0003) | MultiStepLR | Decay at specific epoch milestones |

### Scheduler Section

| Key | Description | Default |
|-----|-------------|---------|
| `optimization.scheduler.name` | LR scheduler name | `WarmupCosineLR` |
| `optimization.scheduler.interval` | Update interval: `epoch` or `step` | `epoch` |
| `optimization.scheduler.warmup_epochs` | Number of warmup epochs | `3` |
| `optimization.scheduler.warmup_start_lr` | LR at start of warmup | `1.0e-05` |
| `optimization.scheduler.min_lr` | Minimum LR | `1.0e-06` |

### EMA (Exponential Moving Average)

| Key | Description | Default |
|-----|-------------|---------|
| `optimization.ema.enabled` | Enable EMA | `true` (in some configs) |
| `optimization.ema.decay` | EMA decay rate | `0.999` |
| `optimization.ema.warmup_steps` | Steps before EMA starts | `500` |
| `optimization.ema.validate_with_ema` | Use EMA weights for validation | `true` |

### Monitor Section

| Key | Description | Default |
|-----|-------------|---------|
| `monitor.logging.scalar.loss_every_n_steps` | Log loss every N steps | `50` |
| `monitor.logging.images.log_every_n_epochs` | Log images every N epochs | `10` |
| `monitor.logging.images.max_images` | Max images to log | `8` |
| `monitor.logging.images.num_slices` | Number of slices to visualize | `2` |
| `monitor.checkpoint.save_top_k` | Keep the top K checkpoints | `3` |
| `monitor.checkpoint.monitor` | Metric to monitor for checkpointing | `train_loss_total_epoch` |
| `monitor.checkpoint.save_every_n_epochs` | Save checkpoint every N epochs | `10` |
| `monitor.checkpoint.dirpath` | Directory for saving checkpoints | `outputs/<experiment>/checkpoints/` |
| `monitor.early_stopping.enabled` | Enable early stopping | `false` |

### System Section

| Key | Description | Default |
|-----|-------------|---------|
| `system.num_gpus` | Number of GPUs (-1 = all available) | `-1` |
| `system.num_workers` | Number of CPU workers (-1 = all available) | `-1` |
| `system.seed` | Random seed for reproducibility | `42` |
| `system.profile` | System profile: `all-gpu-cpu` or `single-gpu-cpu` | `all-gpu-cpu` |

## Resuming Training

To resume from a checkpoint:
```
python scripts/main.py --config <config.yaml> --checkpoint <path/to/checkpoint.ckpt>
```

To reset max_epochs when resuming:
```
python scripts/main.py --config <config.yaml> --checkpoint <path/to/checkpoint.ckpt> --reset-max-epochs 500
```

## Quick Debug Run

```
python scripts/main.py --config tutorials/mito_lucchi++.yaml --fast-dev-run
```

This runs a single training batch for quick validation. Use `--fast-dev-run 2` for 2 batches.

## Demo Mode

```
python scripts/main.py --demo
```

Uses `tutorials/minimal.yaml` with `--fast-dev-run` for a quick sanity check.

## Tips

- Start from the closest bundled config in `tutorials/` and override only what you need.
- Use optimizer profiles (e.g., `optimization.profile=warmup_cosine_lr`) instead of configuring each field manually.
- Use augmentation profiles (e.g., `data.augmentation.profile=aug_standard`) for recommended augmentation settings.
- For sparse datasets, enable reject sampling in the config: `data.dataloader.reject_sampling.size_thres=1000`.
- The output directory receives checkpoints (`.ckpt` files) and a saved config snapshot.
