# PyTC Model Zoo

This document describes all model architectures, loss functions, label transforms, and pipeline profiles available in PyTorch Connectomics.

## Model Architectures

Set `model.arch.profile` to use a predefined architecture, or set `model.arch.type` directly:

| Architecture | Profile / Type | Description | Best For |
|-------------|----------------|-------------|----------|
| MONAI UNet | `monai_unet` | MONAI-based 3D UNet with configurable filters and dropout | General 3D segmentation (recommended for beginners) |
| Residual Symmetric UNet | `rsunet` | Custom RSUNet with group norm, ELU activation, anisotropic downsampling | Anisotropic EM data (SNEMI, CREMI) |
| MedNeXt Small | `mednext_s` | MedNeXt architecture, size S | Efficient segmentation |
| MedNeXt Base | `mednext_b` | MedNeXt architecture, size B | Balanced performance |
| MedNeXt Medium | `mednext_m` | MedNeXt architecture, size M | Higher capacity |
| MedNeXt Large | `mednext_l` | MedNeXt architecture, size L | Maximum capacity |

### Architecture Profile Details

**MONAI UNet (`monai_unet`)**:
```yaml
model:
  arch:
    profile: monai_unet
  monai:
    filters: [32, 64, 128, 256]
    dropout: 0.1
```

**RSUNet (`rsunet`)**:
```yaml
model:
  arch:
    profile: rsunet
  rsunet:
    width: [18, 36, 48, 64, 80]
    norm: group
    activation: elu
    num_groups: 4
    down_factors: [[1, 2, 2], [1, 2, 2], [1, 2, 2], [1, 2, 2]]
    depth_2d: 1
    kernel_2d: [1, 3, 3]
```

## Model Configuration Options

| Key | Description | Example |
|-----|-------------|---------|
| `model.arch.profile` | Architecture profile name | `monai_unet`, `rsunet`, `mednext_s` |
| `model.arch.type` | Architecture type (set by profile) | `monai_unet`, `rsunet`, `mednext` |
| `model.out_channels` | Number of output channels | `1` (binary), `3` (BCD), `12` (affinity) |
| `model.input_size` | Model input patch size `[z, y, x]` | `[112, 112, 112]` |
| `model.output_size` | Model output patch size `[z, y, x]` | `[112, 112, 112]` |
| `model.monai.filters` | Filter sizes per stage (MONAI UNet) | `[32, 64, 128, 256]` |
| `model.monai.dropout` | Dropout rate (MONAI UNet) | `0.1` |
| `model.rsunet.width` | Channel widths per stage (RSUNet) | `[18, 36, 48, 64, 80]` |
| `model.rsunet.norm` | Normalization type (RSUNet): `batch`, `group` | `group` |
| `model.rsunet.activation` | Activation function (RSUNet): `elu`, `relu` | `elu` |
| `model.rsunet.num_groups` | Number of groups for group norm | `4` |
| `model.rsunet.down_factors` | Downsampling factors per stage | `[[1,2,2], [1,2,2], ...]` |

## Loss Functions

Losses are configured under `model.loss` using either a profile or explicit list:

### Loss Profiles

| Profile | Losses | Use Case |
|---------|--------|----------|
| `loss_binary` | WeightedBCEWithLogitsLoss + DiceLoss | Binary segmentation (mitochondria, synapse) |
| `loss_bcd` | BCE+Dice (foreground) + BCE+Dice (boundary) + WeightedMSE (distance) | Multi-task BCD segmentation |
| `loss_per_channel` | PerChannelBCEWithLogitsLoss (auto pos_weight) | Per-channel affinity prediction |
| `loss_bd` | BCE+Dice (all but last channel) + WeightedMSE (last channel) | Boundary + distance multi-task |

### Direct Loss Configuration

```yaml
model:
  loss:
    losses:
      - function: WeightedBCEWithLogitsLoss
        weight: 1.0
        kwargs: {reduction: mean}
      - function: DiceLoss
        weight: 1.0
        kwargs: {sigmoid: true, smooth_nr: 1e-5, smooth_dr: 1e-5}
```

Available loss functions:
- `WeightedBCEWithLogitsLoss` — Binary cross-entropy with logits
- `DiceLoss` — Overlap-based Dice loss
- `WeightedMSELoss` — Mean squared error (for distance/regression targets)
- `PerChannelBCEWithLogitsLoss` — Per-channel BCE with automatic positive weight balancing

Loss entries support `pred_slice` and `target_slice` to apply different losses to different output channels (e.g., `"0:1"` for first channel only).

## Pipeline Profiles

Pipeline profiles bundle model output channels, loss, label transforms, and decoding into a single preset. Set via `default.pipeline_profile`:

| Profile | Out Channels | Description |
|---------|-------------|-------------|
| `binary` | 1 | Binary segmentation (foreground/background) with BCE+Dice loss |
| `bcd` | 3 | Multi-task: binary + boundary + distance transform |
| `affinity-12` | 12 | 12-channel affinity prediction with per-channel BCE and ABISS decoding |

## Label Transforms

Label transforms convert raw instance labels into training targets. Configured via `data.label_transform.profile`:

| Profile | Targets | Description |
|---------|---------|-------------|
| `label_bcd` | binary + instance_boundary + instance_edt | Multi-task BCD labels |
| `label_affinity_12` | affinity (12 offsets) | Short and long-range affinity maps with DeepEM crop |

## Activation Profiles

Channel activations applied during TTA and inference. Referenced by pipeline profiles:

| Profile | Description |
|---------|-------------|
| `act_binary` | Sigmoid activation for binary channels |
| `act_bcd` | Per-channel activations for BCD outputs |

## Decoding Profiles

Post-inference decoding to convert raw predictions into segmentation. Referenced by pipeline profiles:

| Profile | Description |
|---------|-------------|
| `decoding_abiss` | ABISS watershed for affinity-to-instance conversion |
| `decoding_bcd` | BCD-based instance segmentation decoding |
