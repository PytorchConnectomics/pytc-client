# PyTC Bundled Configuration Files

This document describes every YAML configuration file bundled with PyTorch Connectomics. Users should start from the closest matching config and modify it rather than writing one from scratch.

## Lucchi (Mitochondria Segmentation)

**Dataset**: Lucchi — isotropic EM volume of mitochondria in hippocampus.
**Task**: Binary semantic segmentation (mitochondria vs. background).

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/Lucchi-Mitochondria.yaml` | `unet_3d` / `residual_se` | Input: `[112,112,112]`, LR: `0.04`, Loss: BCE+Dice, Isotropic data, 100K iterations |

## SNEMI (Neuron Segmentation)

**Dataset**: SNEMI3D — anisotropic EM serial section images of mouse cortex neurons.
**Task**: Instance segmentation via affinity maps.

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/SNEMI/SNEMI-Base.yaml` | `unet_3d` / `residual` | Affinity target (`"2"`), 3-channel output, GroupNorm, 150K iters |
| `configs/SNEMI/SNEMI-Affinity-UNet.yaml` | `unet_3d` / `residual_se` | Extends SNEMI-Base with SE attention blocks |
| `configs/SNEMI/SNEMI-Affinity-UNet-2x.yaml` | `unet_3d` | Larger model variant |
| `configs/SNEMI/SNEMI-Affinity-UNet-LR.yaml` | `unet_3d` | Learning rate experiment variant |
| `configs/SNEMI/SNEMI-Affinity-UNet-MER.yaml` | `unet_3d` | Model ensemble with regularization |
| `configs/SNEMI/SNEMI-Affinity-Contour-UNet-2x.yaml` | `unet_3d` | Multi-task: affinity + contour prediction |
| `configs/SNEMI/SNEMI-Affinity-ResNet.yaml` | `fpn_3d` / ResNet backbone | FPN architecture with ResNet backbone |
| `configs/SNEMI/SNEMI-Affinity-EffNet.yaml` | `fpn_3d` / EfficientNet backbone | FPN with EfficientNet backbone |
| `configs/SNEMI/SNEMI-Affinity-SwinUNETR.yaml` | `swinunetr` | Swin Transformer-based segmentation |
| `configs/SNEMI/SNEMI-Affinity-UNETR.yaml` | `unetr` | Vision Transformer-based segmentation |
| `configs/SNEMI/SNEMI-Base_multiGPU.yaml` | `unet_3d` | Multi-GPU (4 GPUs) distributed training variant |

## CREMI (Synapse Detection)

**Dataset**: CREMI — anisotropic EM volumes (A, B, C) with synaptic cleft annotations.
**Task**: Synapse detection / binary segmentation with reject sampling for sparse labels.

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/CREMI/CREMI-Base.yaml` | `unet_3d` / `residual` | SyncBN, Reject sampling (threshold 1000), 150K iters |
| `configs/CREMI/CREMI-Base_multiGPU.yaml` | `unet_3d` | Multi-GPU distributed variant |
| `configs/CREMI/CREMI-Foreground-UNet.yaml` | `unet_3d` | Foreground prediction with UNet |
| `configs/CREMI/CREMI-Foreground-DT-UNet.yaml` | `unet_3d` | Multi-task: foreground + distance transform |
| `configs/CREMI/CREMI-Foreground-DT-Regu-UNet.yaml` | `unet_3d` | Foreground + DT with regularization |
| `configs/CREMI/CREMI-Foreground-FPN-ResNet.yaml` | `fpn_3d` / ResNet | FPN with ResNet for foreground detection |
| `configs/CREMI/CREMI-Foreground-FPN-RepVGG.yaml` | `fpn_3d` / RepVGG | FPN with RepVGG backbone |

## MitoEM (Large-Scale Mitochondria)

**Dataset**: MitoEM — large-scale EM dataset for mitochondria instance segmentation.
**Task**: Binary/instance segmentation with tile-based training for large volumes.

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/MitoEM/MitoEM-R-Base.yaml` | `unet_plus_3d` / `residual_se` | Chunked training (4×8×8), 4 GPUs, SyncBN, 150K iters |
| `configs/MitoEM/MitoEM-R-A.yaml` | variant | Architecture A experiment |
| `configs/MitoEM/MitoEM-R-AC.yaml` | variant | Architecture AC experiment |
| `configs/MitoEM/MitoEM-R-BC.yaml` | variant | Boundary + Contour multi-task |
| `configs/MitoEM/MitoEM-R-BCD.yaml` | variant | Boundary + Contour + Distance Transform multi-task |

## NucMM (Nucleus Segmentation)

**Dataset**: NucMM — 3D nuclei segmentation in mouse brain and zebrafish.
**Task**: Instance segmentation of cell nuclei.

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/NucMM/NucMM-Mouse-Base.yaml` | `unet_3d` / `residual_se` | 4 GPUs, GroupNorm, Reject sampling, 100K iters |
| `configs/NucMM/NucMM-Mouse-UNet-BC.yaml` | `unet_3d` | Boundary + Contour multi-task |
| `configs/NucMM/NucMM-Mouse-UNet-BCD.yaml` | `unet_3d` | Boundary + Contour + Distance Transform |
| `configs/NucMM/NucMM-Zebrafish-Base.yaml` | `unet_3d` / `residual_se` | Zebrafish data, similar setup |
| `configs/NucMM/NucMM-Zebrafish-UNet-BC.yaml` | `unet_3d` | Zebrafish BC variant |
| `configs/NucMM/NucMM-Zebrafish-UNet-BCD.yaml` | `unet_3d` | Zebrafish BCD variant |

## JWR15 (Neuron and Synapse Segmentation)

**Dataset**: JWR15 — EM dataset with both neuron and synapse annotations.

### Neuron configs
| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/JWR15/neuron/JWR15-Neuron-Base.yaml` | `unet_3d` | Neuron segmentation baseline |
| `configs/JWR15/neuron/JWR15-Neuron-Affinity-UNet-MER.yaml` | `unet_3d` | Affinity-based with model ensemble |

### Synapse configs
| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/JWR15/synapse/JWR15-Synapse-Base.yaml` | `unet_3d` | Synapse detection baseline |
| `configs/JWR15/synapse/JWR15-Synapse-BCE.yaml` | `unet_3d` | BCE loss variant |
| `configs/JWR15/synapse/JWR15-Synapse-BCE-DICE.yaml` | `unet_3d` | BCE + Dice loss |
| `configs/JWR15/synapse/JWR15-Synapse-BCE-DICE-Regu.yaml` | `unet_3d` | BCE + Dice + Regularization |
| `configs/JWR15/synapse/JWR15-Synapse-Semantic-CE.yaml` | `unet_3d` | Multi-class semantic variant |

## Cellpose (2D Cell Segmentation)

**Dataset**: Cellpose — 2D microscopy images of cells.
**Task**: Instance segmentation using flow-field prediction.

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/Cellpose/Cellpose-Base.yaml` | `unet_2d` / `residual_se` | 2D mode, Multi-task (mask + flow), LeakyReLU, Batch=32, 50K iters, Elastic/Rescale/MissingParts disabled |

## Scutoid (Epithelial Cell Segmentation)

**Dataset**: Scutoid — 3D EM volumes of epithelial cells.
**Task**: Instance segmentation with scaled data.

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/Scutoid/Scutoid-Base.yaml` | `unet_3d` / `residual_se` | 4 GPUs, Data scale `[1.0, 0.5, 0.5]`, Reject sampling, CutNoise disabled |
| `configs/Scutoid/Scutoid-UNet-BCD.yaml` | `unet_3d` | Boundary + Contour + Distance Transform |

## Zebrafinch (Neuron Segmentation)

**Dataset**: Zebrafinch — anisotropic EM of songbird brain neurons.
**Task**: Instance segmentation via affinity maps.

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `configs/Zebrafinch/Zebrafinch-Base.yaml` | `unet_3d` | Neuron segmentation baseline |
| `configs/Zebrafinch/Zebrafinch-Affinity-UNet.yaml` | `unet_3d` / `residual_se` | Affinity-based with SE blocks |
| `configs/Zebrafinch/Zebrafinch-Affinity-UNet-MER.yaml` | `unet_3d` | Affinity with model ensemble regularization |

## Generic / Template Configs

| Config | Task | Description |
|--------|------|-------------|
| `configs/Multiclass-Semantic-Seg.yaml` | Multi-class segmentation | Template for N-class semantic segmentation. Uses `TARGET_OPT: ["9-12"]` and `WeightedCE` loss. 12 output channels. |
| `configs/Distance-Transform-Quantized.yaml` | Distance transform | Template for quantized distance transform prediction. Uses `TARGET_OPT: ["5"]` and `WeightedCE` loss. |

## How to Choose a Config

1. **Identify your task**: binary segmentation, instance segmentation, multi-class, or cell segmentation.
2. **Find the closest dataset**: Pick the bundled config whose dataset most resembles yours (isotropic vs. anisotropic, resolution, structure type).
3. **Start from Base**: Use the `-Base.yaml` config as your starting point.
4. **Override paths**: Change `DATASET.INPUT_PATH`, `DATASET.IMAGE_NAME`, `DATASET.LABEL_NAME`, and `DATASET.OUTPUT_PATH` to point to your data.
5. **Adjust as needed**: Modify learning rate, batch size, iteration count, and model architecture based on your GPU resources and dataset size.
