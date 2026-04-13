# PyTC Data Augmentation

This document describes all data augmentation options available in PyTorch Connectomics. These augmentations are specifically designed for electron microscopy (EM) and biomedical volumetric data.

All augmentations are controlled under the `AUGMENTOR` section of the YAML config. Set `AUGMENTOR.ENABLED: False` to disable all augmentation.

## Available Augmentations

### Rotation (`AUGMENTOR.ROTATE`)
Applies random 90-degree rotations.

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable rotation |
| `ROT90` | `True` | Restrict to 90° increments |
| `P` | `1.0` | Probability of applying |

### Rescale (`AUGMENTOR.RESCALE`)
Randomly rescales the volume.

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable rescaling |
| `FIX_ASPECT` | `False` | Keep aspect ratio fixed |
| `P` | `0.5` | Probability |

### Flip (`AUGMENTOR.FLIP`)
Randomly flips along axes. For isotropic data, enable z-axis flips.

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable flipping |
| `DO_ZTRANS` | `0` | Set to `1` to enable x-z and y-z flips (for isotropic cubic data) |
| `P` | `1.0` | Probability |

### Elastic Deformation (`AUGMENTOR.ELASTIC`)
Applies smooth elastic deformation to simulate tissue warping.

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable elastic deformation |
| `ALPHA` | `16.0` | Maximum pixel displacement |
| `SIGMA` | `4.0` | Gaussian filter standard deviation |
| `P` | `0.75` | Probability |

### Grayscale Augmentation (`AUGMENTOR.GRAYSCALE`)
Randomly adjusts brightness and contrast.

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable grayscale augmentation |
| `P` | `0.75` | Probability |

### Missing Parts (`AUGMENTOR.MISSINGPARTS`)
Simulates missing tissue regions (common artifact in EM data).

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable missing parts simulation |
| `ITER` | `64` | Number of missing region iterations |
| `P` | `0.9` | Probability |

### Missing Section (`AUGMENTOR.MISSINGSECTION`)
Simulates entirely missing z-slices (another common EM artifact).

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable missing section simulation |
| `NUM_SECTION` | `2` | Number of sections to remove |
| `P` | `0.5` | Probability |

### Misalignment (`AUGMENTOR.MISALIGNMENT`)
Simulates section-to-section misalignment (shift or rotation between z-slices).

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable misalignment simulation |
| `DISPLACEMENT` | `16` | Maximum pixel displacement |
| `ROTATE_RATIO` | `0.5` | Fraction of misalignments that use rotation instead of translation |
| `P` | `0.5` | Probability |

### Motion Blur (`AUGMENTOR.MOTIONBLUR`)
Simulates motion blur artifacts in EM sections.

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable motion blur |
| `SECTIONS` | `2` | Number of sections to blur |
| `KERNEL_SIZE` | `11` | Blur kernel size |
| `P` | `0.5` | Probability |

### CutBlur (`AUGMENTOR.CUTBLUR`)
Replaces a rectangular region with a downsampled-then-upsampled version, simulating resolution variation.

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable CutBlur |
| `LENGTH_RATIO` | `0.4` | Ratio of region size to volume size |
| `DOWN_RATIO_MIN` | `2.0` | Minimum downsampling factor |
| `DOWN_RATIO_MAX` | `8.0` | Maximum downsampling factor |
| `DOWNSAMPLE_Z` | `False` | Also downsample along z-axis |
| `P` | `0.5` | Probability |

### CutNoise (`AUGMENTOR.CUTNOISE`)
Adds noise to a rectangular region.

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `True` | Enable CutNoise |
| `LENGTH_RATIO` | `0.4` | Ratio of region size |
| `SCALE` | `0.3` | Noise scale |
| `P` | `0.75` | Probability |

### CopyPaste (`AUGMENTOR.COPYPASTE`)
Copy-pastes object instances for data augmentation (disabled by default).

| Key | Default | Description |
|-----|---------|-------------|
| `ENABLED` | `False` | Enable CopyPaste (disabled by default) |
| `AUG_THRES` | `0.7` | Augmentation threshold |
| `P` | `0.8` | Probability |

## Global Augmentation Options

| Key | Default | Description |
|-----|---------|-------------|
| `AUGMENTOR.ENABLED` | `True` | Master switch for all augmentations |
| `AUGMENTOR.SMOOTH` | `False` | Apply Gaussian smoothing to label masks after augmentation. WARNING: can erase thin structures. |
| `AUGMENTOR.ADDITIONAL_TARGETS_NAME` | `['label']` | Names of additional targets to augment alongside the image |
| `AUGMENTOR.ADDITIONAL_TARGETS_TYPE` | `['mask']` | Type of each additional target (`'mask'` uses nearest-neighbor interpolation) |

## Recommended Settings by Data Type

### Anisotropic EM data (e.g., SNEMI, CREMI)
- `AUGMENTOR.FLIP.DO_ZTRANS: 0` (do not flip across z)
- All other augmentations enabled by default
- Consider disabling `CUTNOISE` for clean datasets

### Isotropic EM data (e.g., Lucchi)
- `AUGMENTOR.FLIP.DO_ZTRANS: 1` (enable z-axis flips)
- `AUGMENTOR.CUTBLUR.DOWNSAMPLE_Z: True`

### 2D datasets (e.g., Cellpose)
- Disable EM-specific augmentations: `ELASTIC.ENABLED: False`, `RESCALE.ENABLED: False`, `MISSINGPARTS.ENABLED: False`
- Keep flip, rotation, and grayscale augmentations

### Sparse labels (e.g., Scutoid, NucMM)
- Enable reject sampling: `DATASET.REJECT_SAMPLING.SIZE_THRES: 1000`
- Consider disabling `CUTNOISE` to avoid corrupting sparse regions

## Per-Augmentation Skipping

Each augmentation has a `SKIP` parameter (list of sample keys to skip). This allows skipping certain augmentations for specific data channels. Default is an empty list (no skipping).
