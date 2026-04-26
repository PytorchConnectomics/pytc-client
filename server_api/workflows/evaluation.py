from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .volume_io import load_volume


def _read_volume(
    path: str,
    *,
    dataset_key: Optional[str] = None,
    crop: Optional[str] = None,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> np.ndarray:
    return np.asarray(
        load_volume(
            path,
            dataset_key=dataset_key,
            crop=crop,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )
    )


def _read_eval_volume(
    path: str,
    *,
    dataset_key: Optional[str] = None,
    crop: Optional[str] = None,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str,
) -> np.ndarray:
    return _read_volume(
        path,
        dataset_key=dataset_key,
        crop=crop,
        channel=channel,
        reference_ndim=reference_ndim,
        label=label,
    )


def _validate_same_shape(*arrays: np.ndarray) -> None:
    shapes = {array.shape for array in arrays}
    if len(shapes) != 1:
        raise ValueError(f"Evaluation arrays must have identical shape; got {shapes}")


def _safe_ratio(numerator: float, denominator: float, empty_value: float = 1.0) -> float:
    if denominator == 0:
        return empty_value
    return float(numerator / denominator)


def _segmentation_metrics(prediction: np.ndarray, ground_truth: np.ndarray) -> Dict[str, Any]:
    prediction_binary = prediction > 0
    truth_binary = ground_truth > 0
    intersection = np.logical_and(prediction_binary, truth_binary).sum()
    prediction_sum = prediction_binary.sum()
    truth_sum = truth_binary.sum()
    union = np.logical_or(prediction_binary, truth_binary).sum()

    metrics: Dict[str, Any] = {
        "dice": round(_safe_ratio(2 * intersection, prediction_sum + truth_sum), 6),
        "iou": round(_safe_ratio(intersection, union), 6),
        "voxel_accuracy": round(float(np.mean(prediction == ground_truth)), 6),
        "foreground_voxels": int(prediction_sum),
        "truth_foreground_voxels": int(truth_sum),
    }

    try:
        from skimage.metrics import adapted_rand_error, variation_of_information

        are, precision, recall = adapted_rand_error(ground_truth, prediction)
        split_vi, merge_vi = variation_of_information(ground_truth, prediction)
        metrics.update(
            {
                "adapted_rand_error": round(float(are), 6),
                "adapted_rand_precision": round(float(precision), 6),
                "adapted_rand_recall": round(float(recall), 6),
                "vi_split": round(float(split_vi), 6),
                "vi_merge": round(float(merge_vi), 6),
                "vi_total": round(float(split_vi + merge_vi), 6),
            }
        )
    except Exception:
        metrics["advanced_metrics_unavailable"] = True

    return metrics


def compute_before_after_evaluation(
    *,
    baseline_prediction_path: str,
    candidate_prediction_path: str,
    ground_truth_path: str,
    baseline_dataset: Optional[str] = None,
    candidate_dataset: Optional[str] = None,
    ground_truth_dataset: Optional[str] = None,
    crop: Optional[str] = None,
    baseline_channel: Optional[int] = None,
    candidate_channel: Optional[int] = None,
    ground_truth_channel: Optional[int] = None,
) -> Dict[str, Any]:
    ground_truth = _read_eval_volume(
        ground_truth_path,
        dataset_key=ground_truth_dataset,
        crop=crop,
        channel=ground_truth_channel,
        label="ground truth",
    )
    baseline = _read_eval_volume(
        baseline_prediction_path,
        dataset_key=baseline_dataset,
        crop=crop,
        channel=baseline_channel,
        reference_ndim=ground_truth.ndim,
        label="baseline prediction",
    )
    candidate = _read_eval_volume(
        candidate_prediction_path,
        dataset_key=candidate_dataset,
        crop=crop,
        channel=candidate_channel,
        reference_ndim=ground_truth.ndim,
        label="candidate prediction",
    )
    _validate_same_shape(baseline, candidate, ground_truth)

    baseline_metrics = _segmentation_metrics(baseline, ground_truth)
    candidate_metrics = _segmentation_metrics(candidate, ground_truth)
    deltas: Dict[str, float] = {}
    for key, candidate_value in candidate_metrics.items():
        baseline_value = baseline_metrics.get(key)
        if isinstance(candidate_value, (int, float)) and isinstance(
            baseline_value, (int, float)
        ):
            deltas[key] = round(float(candidate_value - baseline_value), 6)

    return {
        "baseline": baseline_metrics,
        "candidate": candidate_metrics,
        "delta": deltas,
        "summary": {
            "dice_delta": deltas.get("dice"),
            "iou_delta": deltas.get("iou"),
            "voxel_accuracy_delta": deltas.get("voxel_accuracy"),
            "candidate_improved_dice": bool(
                candidate_metrics.get("dice", 0) >= baseline_metrics.get("dice", 0)
            ),
        },
    }


def write_evaluation_report(path: str, payload: Dict[str, Any]) -> str:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(target)
