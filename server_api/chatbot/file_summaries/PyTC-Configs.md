# PyTC Bundled Configuration Files

This document describes the YAML configuration files bundled with PyTorch Connectomics. All configs are in the `tutorials/` directory and use Hydra/OmegaConf format with a profile-based system. Users should start from the closest matching config and modify it rather than writing one from scratch.

## Config Architecture

Configs use a profile-based inheritance system. Each tutorial config references base profiles from `tutorials/bases/`:
- `arch_profiles.yaml` — Model architecture presets
- `optimizer_profiles.yaml` — Optimizer and scheduler presets
- `augmentation_profiles.yaml` — Data augmentation presets
- `pipeline_profiles.yaml` — End-to-end pipeline presets (loss, labels, decoding)
- `dataloader_profiles.yaml` — Dataloader presets
- `system_profiles.yaml` — GPU/CPU resource presets

## Mitochondria Segmentation

### Lucchi++ (Isotropic EM)

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `tutorials/mito_lucchi++.yaml` | `monai_unet` | Input: `[112,112,112]`, binary pipeline, WarmupCosineLR, batch_size=8, 100 epochs, isotropic data |

### MitoEM (Large-Scale)

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `tutorials/mito_mitoEM_common.yaml` | shared base | Common settings for MitoEM configs |
| `tutorials/mito_mitoEM_H.yaml` | variant | MitoEM-H dataset variant |
| `tutorials/mito_mitoEM_R.yaml` | variant | MitoEM-R dataset variant |
| `tutorials/mito_mitoEM_HR.yaml` | variant | Combined H+R dataset variant |

### BetaSeg (Mitochondria)

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `tutorials/mito_betaseg.yaml` | varies | BetaSeg mitochondria segmentation |

### MitoLab

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `tutorials/mito_mitolab.yaml` | varies | MitoLab mitochondria segmentation |

## Neuron Segmentation

### SNEMI3D (Anisotropic EM)

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `tutorials/neuron_snemi.yaml` | `rsunet` | 12-channel affinity maps, anisotropic, WarmupCosineLR, 100 epochs, ABISS decoding with parameter tuning |

### NISB (Neuron Instance Segmentation Benchmark)

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `tutorials/neuron_nisb_common.yaml` | shared base | Common NISB settings |
| `tutorials/neuron_nisb_40nm_common.yaml` | shared base | 40nm resolution common settings |
| `tutorials/neuron_nisb_40nm_base.yaml` | varies | 40nm baseline |
| `tutorials/neuron_nisb_40nm_liconn.yaml` | varies | 40nm LiConn variant |
| `tutorials/neuron_nisb_9nm_common.yaml` | shared base | 9nm resolution common settings |
| `tutorials/neuron_nisb_9nm_base.yaml` | varies | 9nm baseline |
| `tutorials/neuron_nisb_9nm_liconn.yaml` | varies | 9nm LiConn variant |

## Synapse Detection

### CREMI (Synaptic Cleft)

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `tutorials/syn_cremi.yaml` | `rsunet` | Binary synapse cleft detection, BCE+Dice loss, reject sampling, 150K steps, CREMI evaluation metrics |

## Nucleus Segmentation

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `tutorials/nuc_nucmm-z.yaml` | varies | NucMM zebrafish nucleus segmentation |

## Other Datasets

| Config | Architecture | Key Settings |
|--------|-------------|-------------|
| `tutorials/vesicle_xm.yaml` | varies | Vesicle segmentation |
| `tutorials/fiber_linghu26.yaml` | varies | Fiber segmentation |
| `tutorials/minimal.yaml` | varies | Minimal config for demo/testing |

### Misc Configs

| Config | Description |
|--------|-------------|
| `tutorials/misc/mito_2dsem_seg.yaml` | 2D SEM mitochondria segmentation |
| `tutorials/misc/tsai_axon.yaml` | Axon segmentation |
| `tutorials/misc/worm2d.yaml` | 2D worm segmentation |
| `tutorials/misc/zebrafish_neurons.yaml` | Zebrafish neuron segmentation |
| `tutorials/misc/hydra-lv.yaml` | Hydra large-volume config |
| `tutorials/misc/hydra-lv-finetune.yaml` | Hydra large-volume fine-tuning |

## How to Choose a Config

1. **Identify your task**: binary segmentation (mitochondria, synapse), instance segmentation (neurons, nuclei), or other.
2. **Find the closest dataset**: Pick the tutorial config whose dataset most resembles yours (isotropic vs. anisotropic, resolution, structure type).
3. **Override data paths**: Set `data.train.image`, `data.train.label`, and `test.data.test.image` to point to your data.
4. **Choose profiles**: Select appropriate `model.arch.profile`, `optimization.profile`, and `data.augmentation.profile`.
5. **Adjust as needed**: Override learning rate, batch size, epochs, etc. using Hydra command-line overrides.
