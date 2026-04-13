# PyTC Model Zoo

This document describes all model architectures, block types, backbones, loss functions, and target options available in PyTorch Connectomics.

## Model Architectures

Set `MODEL.ARCHITECTURE` to one of:

| Architecture | Key | Description | Best For |
|-------------|-----|-------------|----------|
| 3D U-Net | `unet_3d` | Standard 3D encoder-decoder with skip connections. Most commonly used. | General 3D segmentation |
| 2D U-Net | `unet_2d` | 2D variant for slice-by-slice processing. Requires `DATASET.DO_2D: True`. | 2D cell segmentation (e.g., Cellpose) |
| 3D U-Net++ | `unet_plus_3d` | Nested U-Net with dense skip connections. | Large-scale datasets (e.g., MitoEM) |
| 2D U-Net++ | `unet_plus_2d` | 2D variant of U-Net++. | 2D tasks with dense skip connections |
| 3D FPN | `fpn_3d` | Feature Pyramid Network. Requires a backbone (`MODEL.BACKBONE`). | Multi-scale feature extraction |
| DeepLabV3 | `deeplabv3a` / `deeplabv3b` / `deeplabv3c` | 2D DeepLab with atrous convolutions. Three variants with different dilation rates. | 2D semantic segmentation |
| UNETR | `unetr` | Vision Transformer encoder with CNN decoder. | Transformer-based 3D segmentation |
| Swin UNETR | `swinunetr` | Shifted-window Transformer encoder (MONAI-based). Supports v2. | State-of-the-art transformer segmentation |

## Block Types

Set `MODEL.BLOCK_TYPE` to one of:

| Block Type | Key | Available In | Description |
|-----------|-----|-------------|-------------|
| Residual | `residual` | unet_3d, unet_2d, fpn_3d | Standard residual block with two convolutions and a skip connection |
| Residual + SE | `residual_se` | unet_3d, unet_2d, fpn_3d | Residual block with Squeeze-and-Excitation channel attention. Most popular choice. |
| Residual PA | `residual_pa` | unet_3d | Pre-activation residual block (BN → ReLU → Conv ordering) |
| Residual PA + SE | `residual_pa_se` | unet_3d | Pre-activation block with Squeeze-and-Excitation |

## Backbones (for FPN and DeepLab)

Set `MODEL.BACKBONE` to one of:

| Backbone | Key | Description |
|----------|-----|-------------|
| ResNet | `resnet` | 3D ResNet backbone. Default for FPN. |
| RepVGG | `repvgg` | Re-parameterizable VGG. Supports deploy mode conversion at inference time. |
| BotNet | `botnet` | Bottleneck Transformer backbone. Requires `fmap_size` parameter. |
| EfficientNet | `effnet` | 3D EfficientNet with inverted residual blocks. |

## Model Configuration Options

| Key | Description | Default |
|-----|-------------|---------|
| `MODEL.FILTERS` | Number of filters at each encoder stage | `[28, 36, 48, 64, 80]` |
| `MODEL.BLOCKS` | Number of residual blocks at each stage | `[2, 2, 2, 2]` |
| `MODEL.IN_PLANES` | Number of input channels (1 for grayscale EM) | `1` |
| `MODEL.OUT_PLANES` | Number of output channels | `1` |
| `MODEL.INPUT_SIZE` | Model input patch size `[z, y, x]` | `[8, 256, 256]` |
| `MODEL.OUTPUT_SIZE` | Model output patch size `[z, y, x]` | `[8, 256, 256]` |
| `MODEL.ISOTROPY` | Per-stage isotropy flags for anisotropic data | `[False, False, False, True, True]` |
| `MODEL.ATTENTION` | Attention mechanism: `'squeeze_excitation'` or None | `'squeeze_excitation'` |
| `MODEL.PAD_MODE` | Convolution padding: `'zeros'`, `'circular'`, `'reflect'`, `'replicate'` | `'replicate'` |
| `MODEL.NORM_MODE` | Normalization: `'bn'` (BatchNorm), `'sync_bn'`, `'in'` (Instance), `'gn'` (Group), `'none'` | `'bn'` |
| `MODEL.ACT_MODE` | Activation: `'relu'`, `'elu'`, `'leaky'` (leaky_relu) | `'elu'` |
| `MODEL.POOLING_LAYER` | Use pooling for downsampling (True) or strided conv (False) | `False` |
| `MODEL.MIXED_PRECESION` | Mixed-precision training (DDP only) | `False` |
| `MODEL.EMBEDDING` | Enable embedding head | `1` |
| `MODEL.HEAD_DEPTH` | Depth of final decoder head | `1` |
| `MODEL.PRE_MODEL` | Path to pretrained model for fine-tuning | `''` |

### Swin UNETR-Specific Options

| Key | Default | Description |
|-----|---------|-------------|
| `MODEL.SWIN_UNETR_FEATURE_SIZE` | `48` | Feature dimension |
| `MODEL.DEPTHS` | `(2, 2, 2, 2)` | Layers per stage |
| `MODEL.SWIN_UNETR_NUM_HEADS` | `(3, 6, 12, 24)` | Attention heads per stage |
| `MODEL.SWIN_UNETR_DROPOUT_RATE` | `0.0` | Dropout rate |
| `MODEL.ATTN_DROP_RATE` | `0.0` | Attention dropout |
| `MODEL.USE_V2` | `False` | Use Swin UNETR v2 |
| `MODEL.SPATIAL_DIMS` | `3` | Spatial dimensions |

### UNETR-Specific Options

| Key | Default | Description |
|-----|---------|-------------|
| `MODEL.UNETR_FEATURE_SIZE` | `16` | Feature dimension |
| `MODEL.HIDDEN_SIZE` | `768` | Transformer hidden dimension |
| `MODEL.MLP_DIM` | `3072` | Feedforward dimension |
| `MODEL.UNETR_NUM_HEADS` | `12` | Number of attention heads |
| `MODEL.POS_EMBED` | `'perceptron'` | Position embedding type |
| `MODEL.UNETR_DROPOUT_RATE` | `0.0` | Dropout rate |

## Loss Functions

Set `MODEL.LOSS_OPTION` (a list of lists, one per target):

| Loss | Key | Use Case |
|------|-----|----------|
| Weighted Binary Cross-Entropy | `WeightedBCE` | Binary segmentation |
| Weighted BCE with Logits | `WeightedBCEWithLogitsLoss` | Binary segmentation (numerically stable, no activation needed) |
| Weighted BCE Focal Loss | `WeightedBCEFocalLoss` | Binary segmentation with class imbalance |
| Dice Loss | `DiceLoss` | Binary segmentation (overlap-based) |
| Weighted-Sample Dice Loss | `WSDiceLoss` | Per-sample weighted Dice |
| Weighted Cross-Entropy | `WeightedCE` | Multi-class segmentation |
| Weighted MSE | `WeightedMSE` | Regression targets (e.g., distance transforms, flow fields) |
| Weighted MAE | `WeightedMAE` | Regression targets |

Multiple losses can be combined for a single target:
```yaml
MODEL:
  LOSS_OPTION: [["WeightedBCEWithLogitsLoss", "DiceLoss"]]
  LOSS_WEIGHT: [[1.0, 1.0]]
```

## Regularization Options

Set `MODEL.REGU_OPT`:

| Regularization | Key | Description |
|---------------|-----|-------------|
| Binary | `Binary` | Encourages binary predictions |
| Foreground-Contour Consistency | `FgContour` | Enforces consistency between foreground and contour predictions |
| Contour-DT Consistency | `ContourDT` | Consistency between contour and distance transform |
| Foreground-DT Consistency | `FgDT` | Consistency between foreground and distance transform |
| Non-overlap | `Nonoverlap` | Prevents overlapping instance predictions |

## Target Options (MODEL.TARGET_OPT)

The target option string encodes what the model is predicting:

| Code | Target Type | OUT_PLANES | Description |
|------|-------------|-----------|-------------|
| `"0"` | Binary mask | 1 | Standard binary segmentation (foreground/background) |
| `"1"` | Synaptic polarity | 3 | Signed polarity prediction for synapses |
| `"2"` | Affinity map | 3 | 3-channel affinity map for instance segmentation |
| `"3"` | Small object mask | 1 | Optimized for small objects |
| `"4"` | Contour map | 1 | Boundary contour prediction |
| `"5"` | Distance transform | 1 | Quantized distance transform for watershed |
| `"7"` | Flow field | 2 | Cellpose-style gradient flow for instance segmentation |
| `"9-N"` | Multi-class | N | N-class semantic segmentation (e.g., `"9-12"` for 12 classes) |

## Weight Options (MODEL.WEIGHT_OPT)

Controls per-voxel loss weighting:

| Code | Description |
|------|-------------|
| `"0"` | No weighting (uniform) |
| `"1"` | Binary mask weighting (weight foreground vs. background) |

## Output Activations (MODEL.OUTPUT_ACT)

Applied to model output during loss computation:

| Activation | When to Use |
|-----------|-------------|
| `"none"` | When loss handles raw logits (e.g., BCEWithLogitsLoss) |
| `"sigmoid"` | Binary segmentation output |
| `"softmax"` | Multi-class segmentation output |
| `"tanh"` | Flow field / regression with [-1, 1] range |
