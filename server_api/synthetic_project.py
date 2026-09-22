"""Deterministic local project fixture for the core segmentation workflow."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import h5py
import numpy as np

GENERATOR_VERSION = "pytc-synthetic-core/v1"
VOLUME_SHAPE = (12, 160, 160)
VOLUME_CHUNKS = (4, 64, 64)
VOXEL_SIZE_NM = (40.0, 8.0, 8.0)


def _instance_labels(offset: tuple[int, int, int] = (0, 0, 0)) -> np.ndarray:
    z, y, x = np.indices(VOLUME_SHAPE)
    labels = np.zeros(VOLUME_SHAPE, dtype=np.uint16)
    objects = (
        (1, (4, 43, 48), (3, 18, 24)),
        (2, (7, 102, 61), (3, 24, 17)),
        (3, (5, 82, 118), (2, 16, 28)),
        (4, (8, 125, 126), (2, 18, 20)),
    )
    for label_id, center, radius in objects:
        shifted_center = tuple(center[index] + offset[index] for index in range(3))
        distance = sum(
            ((axis - shifted_center[index]) / radius[index]) ** 2
            for index, axis in enumerate((z, y, x))
        )
        labels[distance <= 1.0] = label_id
    return labels


def _image_from_labels(labels: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z, y, x = np.indices(labels.shape)
    image = (
        112.0
        + 18.0 * np.sin(x / 9.0)
        + 13.0 * np.cos(y / 13.0)
        + 7.0 * np.sin((x + y + z * 5) / 17.0)
        + rng.normal(0.0, 10.0, labels.shape)
    )
    image += np.where(labels > 0, 36.0 + (labels % 3) * 9.0, 0.0)
    boundary = np.zeros(labels.shape, dtype=bool)
    for axis in range(3):
        boundary |= labels != np.roll(labels, 1, axis=axis)
    image[boundary] -= 45.0
    return np.clip(image, 0, 255).astype(np.uint8)


def _draft_labels(labels: np.ndarray) -> np.ndarray:
    draft = labels.copy()
    draft[draft == 3] = 0
    draft[:, 92:105, 55:72][draft[:, 92:105, 55:72] == 2] = 0
    draft[3:7, 24:37, 112:130] = 9
    return draft


def _write_h5(path: Path, data: np.ndarray, *, role: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as handle:
        dataset = handle.create_dataset(
            "data",
            data=data,
            chunks=VOLUME_CHUNKS,
            compression="gzip",
            compression_opts=4,
            shuffle=True,
        )
        dataset.attrs["axes"] = "zyx"
        dataset.attrs["role"] = role
        dataset.attrs["voxel_size_nm"] = VOXEL_SIZE_NM
        handle.attrs["generator"] = GENERATOR_VERSION
        handle.attrs["synthetic"] = True


def _config_text(root: Path) -> str:
    train_image = root / "data/raw/train-01_image.h5"
    train_label = root / "data/seg/ground_truth/train-01_ground_truth.h5"
    target_image = root / "data/raw/target-01_image.h5"
    output_path = root / "runtime/training"
    inference_path = root / "runtime/inference"
    return f"""# Deterministic local workflow fixture. Not a benchmark configuration.
SYSTEM:
  NUM_GPUS: 1
  NUM_CPUS: 0
  PARALLEL: single

MODEL:
  ARCHITECTURE: unet_plus_3d
  BLOCK_TYPE: residual_se
  INPUT_SIZE: [9, 65, 65]
  OUTPUT_SIZE: [9, 65, 65]
  IN_PLANES: 1
  OUT_PLANES: 2
  NORM_MODE: gn
  FILTERS: [8, 12, 16, 24, 32]
  TARGET_OPT: ["0", "4-1-1"]
  LOSS_OPTION:
    - [WeightedBCEWithLogitsLoss, DiceLoss]
    - [WeightedBCEWithLogitsLoss, DiceLoss]
  LOSS_WEIGHT: [[1.0, 0.5], [1.0, 0.5]]
  WEIGHT_OPT: [["1", "0"], ["1", "0"]]
  OUTPUT_ACT: [["none", "sigmoid"], ["none", "sigmoid"]]

DATASET:
  INPUT_PATH: ""
  IMAGE_NAME: {train_image}
  LABEL_NAME: {train_label}
  OUTPUT_PATH: {output_path}
  PAD_SIZE: [4, 16, 16]
  PAD_MODE: reflect
  IMAGE_SCALE: [1.0, 1.0, 1.0]
  LABEL_SCALE: [1.0, 1.0, 1.0]
  DATA_SCALE: [1.0, 1.0, 1.0]
  NORMALIZE_RANGE: true
  MEAN: 0.5
  STD: 0.5
  MATCH_ACT: none
  IS_ABSOLUTE_PATH: true
  DISTRIBUTED: false
  DO_2D: false
  LOAD_2D: false
  DO_CHUNK_TITLE: 0
  DROP_CHANNEL: false
  ENSURE_MIN_SIZE: false
  LABEL_BINARY: false
  LABEL_MAG: 0
  LABEL_VAST: false
  REDUCE_LABEL: true
  VALID_RATIO: 0.25
  VALID_MASK_NAME: null
  VAL_IMAGE_NAME: null
  VAL_LABEL_NAME: null
  VAL_VALID_MASK_NAME: null
  VAL_PAD_SIZE: [0, 0, 0]
  REJECT_SAMPLING:
    SIZE_THRES: -1
    DIVERSITY: -1
    NUM_TRIAL: 10
    P: 0.95

AUGMENTOR:
  ENABLED: false

SOLVER:
  NAME: AdamW
  LR_SCHEDULER_NAME: WarmupCosineLR
  BASE_LR: 0.0003
  BETAS: [0.9, 0.999]
  WEIGHT_DECAY: 0.0001
  ITERATION_STEP: 1
  ITERATION_SAVE: 5
  ITERATION_VAL: 1000000
  ITERATION_TOTAL: 10
  SAMPLES_PER_BATCH: 1
  ITERATION_RESTART: false
  WARMUP_FACTOR: 0.001
  WARMUP_ITERS: 2
  WARMUP_METHOD: linear

MONITOR:
  ITERATION_NUM: [2, 5]
  LOG_OPT: [1, 1, 0]
  VIS_OPT: [0, 8]

INFERENCE:
  INPUT_SIZE: [9, 65, 65]
  OUTPUT_SIZE: [9, 65, 65]
  IMAGE_NAME: {target_image}
  OUTPUT_PATH: {inference_path}
  OUTPUT_NAME: target-01_prediction.h5
  OUTPUT_ACT: ["sigmoid", "sigmoid"]
  PAD_SIZE: [4, 16, 16]
  AUG_MODE: mean
  AUG_NUM: 1
  STRIDE: [8, 64, 64]
  SAMPLES_PER_BATCH: 1
  DO_EVAL: false
  UNPAD: true
"""


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generator": GENERATOR_VERSION,
        "synthetic": True,
        "title": "Synthetic Segmentation Core Loop",
        "description": "Fixed local fixture for end-to-end workflow and UI testing.",
        "imaging_modality": "Synthetic volumetric microscopy",
        "target_structure": "synthetic organelles",
        "task_family": "3D instance segmentation",
        "task": "segmentation, proofreading, retraining, and evaluation",
        "voxel_size": {"zyx_nm": list(VOXEL_SIZE_NM)},
        "active_paths": {
            "image_root": "data/raw",
            "label_root": "data/seg",
            "config": "configs/Synthetic-Core-Loop-BC.yaml",
        },
        "volumes": [
            {
                "id": "train-01",
                "split": "train",
                "image": "data/raw/train-01_image.h5",
                "segmentation": "data/seg/ground_truth/train-01_ground_truth.h5",
                "mask_state": "ground_truth",
            },
            {
                "id": "train-02",
                "split": "train",
                "image": "data/raw/train-02_image.h5",
                "segmentation": "data/seg/ground_truth/train-02_ground_truth.h5",
                "mask_state": "ground_truth",
            },
            {
                "id": "review-01",
                "split": "proofreading",
                "image": "data/raw/review-01_image.h5",
                "segmentation": "data/seg/draft/review-01_seg.h5",
                "mask_state": "needs_proofreading",
            },
            {
                "id": "target-01",
                "split": "inference",
                "image": "data/raw/target-01_image.h5",
                "segmentation": None,
                "mask_state": "missing_segmentation",
            },
        ],
        "initial_progress_summary": {
            "total": 4,
            "ground_truth": 2,
            "needs_proofreading": 1,
            "missing_segmentation": 1,
        },
        "workflow_split": {
            "ground_truth_training_volumes": ["train-01", "train-02"],
            "proofreading_volumes": ["review-01"],
            "image_only_inference_targets": ["target-01"],
        },
    }


def _is_current(root: Path) -> bool:
    try:
        manifest = json.loads((root / "project_manifest.json").read_text())
    except (OSError, json.JSONDecodeError):
        return False
    required = (
        "data/raw/train-01_image.h5",
        "data/raw/train-02_image.h5",
        "data/raw/review-01_image.h5",
        "data/raw/target-01_image.h5",
        "data/seg/ground_truth/train-01_ground_truth.h5",
        "data/seg/ground_truth/train-02_ground_truth.h5",
        "data/seg/draft/review-01_seg.h5",
        "outputs/predictions/baseline_review-01.h5",
        "outputs/predictions/candidate_review-01.h5",
        "configs/Synthetic-Core-Loop-BC.yaml",
        "notes/README.md",
    )
    return manifest.get("generator") == GENERATOR_VERSION and all(
        (root / relative_path).is_file() for relative_path in required
    )


def _has_generator_marker(root: Path) -> bool:
    try:
        manifest = json.loads((root / "project_manifest.json").read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return str(manifest.get("generator") or "").startswith("pytc-synthetic-core/")


def create_synthetic_project(output_dir: str | Path, *, reset: bool = False) -> dict:
    """Create or restore the fixed project and return its resolved contract."""
    root = Path(output_dir).expanduser().resolve()
    if root.exists() and any(root.iterdir()) and not _has_generator_marker(root):
        raise ValueError(
            f"Refusing to modify non-synthetic directory without a generator marker: {root}"
        )
    if reset and root.exists():
        shutil.rmtree(root)
    if _is_current(root):
        return {"created": False, "generator": GENERATOR_VERSION, "root": str(root)}

    root.mkdir(parents=True, exist_ok=True)
    cases = {
        "train-01": (_instance_labels(), 101),
        "train-02": (_instance_labels((0, 7, -5)), 202),
        "review-01": (_instance_labels((0, -6, 8)), 303),
        "target-01": (_instance_labels((0, 4, 5)), 404),
    }
    for name, (labels, seed) in cases.items():
        _write_h5(
            root / f"data/raw/{name}_image.h5",
            _image_from_labels(labels, seed),
            role="image",
        )

    for name in ("train-01", "train-02"):
        _write_h5(
            root / f"data/seg/ground_truth/{name}_ground_truth.h5",
            cases[name][0],
            role="ground_truth",
        )

    review_labels = cases["review-01"][0]
    draft = _draft_labels(review_labels)
    (root / "data/seg/draft/review-01_draft_seg.h5").unlink(missing_ok=True)
    _write_h5(
        root / "data/seg/draft/review-01_seg.h5",
        draft,
        role="draft_segmentation",
    )
    _write_h5(
        root / "outputs/predictions/baseline_review-01.h5",
        draft,
        role="baseline_prediction",
    )
    _write_h5(
        root / "outputs/predictions/candidate_review-01.h5",
        review_labels,
        role="candidate_prediction",
    )

    config_path = root / "configs/Synthetic-Core-Loop-BC.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_config_text(root), encoding="utf-8")
    (root / "runtime/training").mkdir(parents=True, exist_ok=True)
    (root / "runtime/inference").mkdir(parents=True, exist_ok=True)

    notes_path = root / "notes/README.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(
        """# Synthetic Segmentation Core Loop

This deterministic project tests the application workflow, not biological validity or model quality.

- `train-01` and `train-02` have confirmed ground-truth instance labels.
- `review-01` has a deliberately incomplete draft with one missing object and one false positive.
- `target-01` is image-only and should be offered as an inference target.
- Baseline and candidate predictions make comparison and evaluation views available immediately.

Expected initial progress: 4 volumes, 2 ground truth, 1 needs proofreading, and 1 missing segmentation.
The HDF5 dataset key is `data`; volumes are chunked and compressed to exercise storage-backed reads.
Use the repository reset command before a canonical test run. Generated results under `runtime/` are disposable.
""",
        encoding="utf-8",
    )
    (root / "project_manifest.json").write_text(
        json.dumps(_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"created": True, "generator": GENERATOR_VERSION, "root": str(root)}
