# PyTC Evaluation Guide

This document explains how to evaluate segmentation results produced by PyTorch Connectomics.

## Running Inference First

Before evaluation, you must run inference to produce predictions. Use the `--inference` flag:
```
python scripts/main.py --config-file <config.yaml> --inference --checkpoint <checkpoint.pth.tar>
```

The predictions are saved to `INFERENCE.OUTPUT_PATH` (usually as HDF5 files).

## Available Evaluation Metrics

PyTC provides evaluation utilities in `connectomics.utils.evaluate`. These are used **post-inference** by loading the prediction and ground truth volumes and computing metrics in a separate Python script.

### Binary Segmentation Metrics (`get_binary_jaccard`)

For binary foreground/background segmentation (e.g., mitochondria detection):

```python
from connectomics.utils.evaluate import get_binary_jaccard
score = get_binary_jaccard(prediction, ground_truth, thres=[0.5])
```

Returns a numpy array with 4 scores per threshold:
- **Foreground IoU** (Intersection over Union for the foreground class)
- **Mean IoU** (average of foreground and background IoU)
- **Precision** (TP / (TP + FP))
- **Recall** (TP / (TP + FN))

### Instance Segmentation Metrics (`adapted_rand`)

For instance segmentation evaluation (e.g., neuron segmentation via affinity maps):

```python
from connectomics.utils.evaluate import adapted_rand
are = adapted_rand(segmentation, ground_truth)
# or with full stats:
are, precision, recall = adapted_rand(segmentation, ground_truth, all_stats=True)
```

Returns:
- **Adapted Rand Error (ARE)**: 1 minus the F-score of the Rand index. Lower is better. Used by the SNEMI3D challenge.

### Instance Matching Metrics (`instance_matching`)

For detailed instance-level evaluation (similar to COCO-style metrics):

```python
from connectomics.utils.evaluate import instance_matching
stats = instance_matching(y_true, y_pred, thresh=0.5, criterion='iou')
```

Returns a named tuple with:
- **tp, fp, fn**: True positives, false positives, false negatives
- **precision, recall, f1, accuracy**: Standard classification metrics
- **n_true, n_pred**: Number of ground truth and predicted instances
- **mean_matched_score**: Mean IoU of matched true positive pairs
- **mean_true_score**: Mean IoU normalized by total GT objects
- **panoptic_quality**: As defined in Kirillov et al. "Panoptic Segmentation" (CVPR 2019)

Matching criteria options (`criterion` parameter):
- `'iou'`: Intersection over Union (default)
- `'iot'`: Intersection over True (ground truth)
- `'iop'`: Intersection over Predicted

### Variation of Information (`voi`)

For measuring over-segmentation and under-segmentation:

```python
from connectomics.utils.evaluate import voi
split_error, merge_error = voi(segmentation, ground_truth)
```

Returns:
- **Split error** H(Y|X): measures over-segmentation
- **Merge error** H(X|Y): measures under-segmentation
- Total VI = split + merge (lower is better)

### CREMI Distance (`cremi_distance`)

For the CREMI synapse detection challenge:

```python
from connectomics.utils.evaluate import cremi_distance
fp_mean, fn_mean = cremi_distance(prediction, ground_truth, resolution=(40.0, 4.0, 4.0))
```

Computes mean distance-based false positive and false negative statistics.

## Evaluation Workflow

1. **Run inference** to produce prediction volumes.
2. **Load predictions and ground truth** using h5py or tifffile.
3. **Choose the appropriate metric** based on your task:
   - Binary segmentation → `get_binary_jaccard`
   - Instance segmentation → `adapted_rand` or `instance_matching`
   - Over/under-segmentation analysis → `voi`
   - CREMI challenge → `cremi_distance`
4. **Write a short evaluation script** that loads both volumes and calls the metric function.

## Choosing the Right Metric

| Task | Recommended Metric | Why |
|------|-------------------|-----|
| Mitochondria / binary | `get_binary_jaccard` | Standard binary IoU, precision, recall |
| Neuron instance segmentation | `adapted_rand` | SNEMI3D challenge standard |
| Cell instance segmentation | `instance_matching` | Gives TP/FP/FN counts, panoptic quality |
| Synapse detection (CREMI) | `cremi_distance` | CREMI challenge standard |
| Any instance segmentation | `voi` | Diagnose over- vs. under-segmentation |

## Notes

- PyTC does NOT automatically compute evaluation metrics after inference. You must write a separate script.
- The `--inference` flag only generates predictions; it does not compare them to ground truth.
- For large volumes, load data in chunks to avoid memory issues.
