# PyTC Data Augmentation

This document describes all data augmentation options available in PyTorch Connectomics. These augmentations are specifically designed for electron microscopy (EM) and biomedical volumetric data.

Augmentations are controlled under the `data.augmentation` section and use a **profile-based system**. Set `data.augmentation.profile` to choose a preset, then override individual fields as needed.

## Augmentation Profiles

Choose ONE profile via `data.augmentation.profile`:

| Profile | Description | Best For |
|---------|-------------|----------|
| `aug_light` | Flip + rotate + mild intensity | Quick experiments, clean data, fine-tuning |
| `aug_standard` | Light + EM artifact simulation (misalignment, missing sections) | Most 3D EM tasks (RECOMMENDED) |
| `aug_strong` | Maximum regularization (affine, elastic, motion blur, missing parts, cut noise) | Small datasets, overfitting prevention |
| `aug_em_neuron` | DeepEM-matched augmentation with defect mutex | Neuron affinity learning on anisotropic EM (e.g., SNEMI3D) |
| `aug_instance` | Standard + copy-paste + mixup | Instance segmentation |
| `aug_superres` | CutBlur-centric for multi-scale learning | Super-resolution, denoising |

## Available Augmentations

All augmentation keys are under `data.augmentation.<augmentation_name>`:

### Flip (`data.augmentation.flip`)
Randomly flips along spatial axes.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable flipping |
| `prob` | `0.5` | Probability of applying |
| `spatial_axis` | `[1, 2]` | Axes to flip. Add `0` for z-axis (isotropic data) |

### Rotate (`data.augmentation.rotate`)
Applies random 90-degree rotations.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable rotation |
| `prob` | `0.5` | Probability |
| `spatial_axes` | `[1, 2]` | Spatial axes for rotation |

### Affine (`data.augmentation.affine`)
Random affine transforms (rotation, scaling, shearing).

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Enable affine (only in `aug_strong`) |
| `prob` | `0.3` | Probability |
| `rotate_range` | `[0.1, 0.1, 0.1]` | Rotation range per axis |
| `scale_range` | `[0.05, 0.05, 0.05]` | Scale range per axis |
| `shear_range` | `[0.05, 0.05, 0.05]` | Shear range per axis |

### Elastic Deformation (`data.augmentation.elastic`)
Smooth elastic deformation to simulate tissue warping.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | varies | Enable elastic deformation |
| `prob` | `0.3` | Probability |
| `sigma_range` | `[5.0, 8.0]` | Gaussian filter sigma range |
| `magnitude_range` | `[50.0, 150.0]` | Displacement magnitude range |

### Intensity (`data.augmentation.intensity`)
Adjusts brightness, contrast, and adds Gaussian noise.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable intensity augmentation |
| `gaussian_noise_prob` | `0.3–0.5` | Probability of Gaussian noise |
| `gaussian_noise_std` | `0.05–0.1` | Noise standard deviation |
| `shift_intensity_prob` | `0.3–0.7` | Probability of brightness shift |
| `shift_intensity_offset` | `0.1–0.2` | Brightness shift magnitude |
| `contrast_prob` | `0.3–0.7` | Probability of contrast change |
| `contrast_range` | `[0.9, 1.1]` or `[0.7, 1.4]` | Contrast scaling range |

### Misalignment (`data.augmentation.misalignment`)
Simulates section-to-section misalignment (common EM artifact).

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable misalignment |
| `prob` | `0.4–1.0` | Probability |
| `displacement` | `10–17` | Maximum pixel displacement |
| `rotate_ratio` | `0.0` | Fraction using rotation vs. translation |

### Missing Section (`data.augmentation.missing_section`)
Simulates entirely missing z-slices.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable missing section |
| `prob` | `0.3–1.0` | Probability |
| `num_sections` | `2` or `[0, 5]` | Number of sections to remove |

### Motion Blur (`data.augmentation.motion_blur`)
Simulates motion blur artifacts in EM sections.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | varies | Enable motion blur |
| `prob` | `0.3–1.0` | Probability |
| `sections` | `[1, 3]` | Number of sections to blur |
| `kernel_size` | `11` | Blur kernel size |

### Missing Parts (`data.augmentation.missing_parts`)
Simulates missing tissue regions.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | varies | Enable missing parts |
| `prob` | `0.2` | Probability |
| `hole_range` | `[0.1, 0.25]` | Hole size range relative to volume |

### Cut Noise (`data.augmentation.cut_noise`)
Adds noise to a rectangular region.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | varies | Enable cut noise |
| `prob` | `0.3` | Probability |
| `length_ratio` | `[0.1, 0.25]` | Region size ratio |
| `noise_scale` | `[0.05, 0.15]` | Noise scale range |

### Cut Blur (`data.augmentation.cut_blur`)
Replaces a region with downsampled-then-upsampled version.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | varies | Enable cut blur |
| `prob` | `0.8` | Probability |
| `length_ratio` | `[0.3, 0.5]` | Region size ratio |
| `down_ratio_range` | `[2.0, 8.0]` | Downsampling factor range |
| `downsample_z` | `false` | Also downsample along z-axis |

### Copy-Paste (`data.augmentation.copy_paste`)
Copy-pastes object instances for data augmentation.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Enable copy-paste (only in `aug_instance`) |
| `prob` | `0.6` | Probability |
| `max_obj_ratio` | `0.7` | Maximum object area ratio |

### Mixup (`data.augmentation.mixup`)
Blends two training samples together.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Enable mixup (only in `aug_instance`) |
| `prob` | `0.3` | Probability |
| `alpha_range` | `[0.7, 0.9]` | Blending alpha range |

## Special Features

### Defect Mutex (`data.augmentation.defect_mutex`)
When `true`, only one defect augmentation (misalignment, missing_section, or motion_blur) is applied per sample. Used in the `aug_em_neuron` profile to match the DeepEM augmentation strategy.

## Recommended Profile by Data Type

- **Anisotropic EM (SNEMI, CREMI)**: `aug_standard` or `aug_em_neuron`
- **Isotropic EM (Lucchi)**: `aug_standard` with `flip.spatial_axis: [0, 1, 2]`
- **Small datasets / overfitting**: `aug_strong`
- **Instance segmentation**: `aug_instance`
- **Super-resolution**: `aug_superres`
- **Quick experiments / fine-tuning**: `aug_light`
