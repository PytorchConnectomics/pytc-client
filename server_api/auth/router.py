from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import models, utils, database
from jose import JWTError, jwt
from typing import Any, List, Optional
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse
import json
import shutil
import os
import uuid
import mimetypes
import re
import math
from server_api.utils.utils import resolve_existing_path

try:  # Optional preview dependency
    import cv2
except Exception:  # pragma: no cover - preview is best-effort
    cv2 = None

try:  # Optional volume inspection dependency
    import numpy as np
except Exception:  # pragma: no cover - inspection is best-effort
    np = None

try:  # Optional volume inspection dependency
    import tifffile
except Exception:  # pragma: no cover - inspection is best-effort
    tifffile = None

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
IGNORED_SYSTEM_FILENAMES = {
    ".ds_store",
    "thumbs.db",
    ".pytc_proofreading.json",
    ".pytc_instance_labels.tif",
    ".pytc_project_context.json",
}
PROJECT_PROFILE_MAX_FILES = 2500
PROJECT_PROFILE_TEXT_MAX_BYTES = 24000
PROJECT_PROFILE_MAX_CONTENT_FILES = 24
PROJECT_AUDIT_MAX_VOLUME_FILES = 16
PROJECT_AUDIT_MAX_SAMPLE_VALUES = 250_000
PROJECT_AUDIT_MAX_FINDINGS = 24
PROJECT_CONTEXT_FILENAME = ".pytc_project_context.json"

VOLUME_EXTENSIONS = {
    ".h5",
    ".hdf5",
    ".tif",
    ".tiff",
    ".ome.tif",
    ".ome.tiff",
    ".npy",
    ".npz",
    ".zarr",
    ".n5",
    ".nii",
    ".nii.gz",
    ".mrc",
    ".mrcs",
}
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml"}
CHECKPOINT_EXTENSIONS = {".pt", ".pth", ".pth.tar", ".ckpt", ".onnx"}
TEXT_SIGNAL_EXTENSIONS = CONFIG_EXTENSIONS | {".md", ".txt", ".csv", ".tsv"}


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def _is_ignored_system_file(name: Optional[str]) -> bool:
    normalized = str(name or "").strip().lower()
    return normalized in IGNORED_SYSTEM_FILENAMES or normalized.startswith(
        ".__pytc_runtime_"
    )


def _project_suggestion_candidates() -> List[dict]:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    workspace_root = os.path.abspath(os.path.join(repo_root, ".."))
    initial_project_root = os.getenv("PYTC_INITIAL_PROJECT_ROOT", "").strip()
    candidates = [
        {
            "id": "yixiao-tapereader-xri-case-study",
            "name": "yixiao_tapereader_xri_case_study",
            "directory_path": "/home/weidf/demo_data/yixiao_tapereader_xri_case_study",
            "description": "Yixiao TapeReader XRI fibre segmentation case study with GT, draft, and image-only volumes.",
            "recommended": True,
            "context_hints": {
                "imaging_modality": "X-ray / XRI volumetric microscopy",
                "target_structure": "CytoTape fibres",
                "task_family": "XRI fibre instance segmentation",
                "mask_status": "mixed: 6 ground-truth masks, 2 draft masks, 2 image-only targets",
                "image_only_strategy": "run inference on image-only volumes later",
                "training_policy": "train only on confirmed ground-truth masks",
                "task_goal": "instance segmentation, proofreading, and model retraining",
                "optimization_priority": "paper-faithful workflow coordination",
                "voxel_size_nm": [40, 16.3, 16.3],
            },
        },
        {
            "id": "mitoem2-progress-demo",
            "name": "mitoem2_progress_demo",
            "directory_path": "/home/weidf/demo_data/mitoem2_progress_demo",
            "description": "MitoEM2.0 progress demo with curated, draft, and missing segmentations.",
            "recommended": False,
            "context_hints": {
                "imaging_modality": "EM / ssSEM",
                "target_structure": "mitochondria",
                "task_goal": "segmentation",
                "optimization_priority": "accuracy",
                "voxel_size_nm": [30, 8, 8],
            },
        },
        {
            "id": "prepilot-lucchi-pp",
            "name": "prepilot_lucchi_pp",
            "directory_path": "/home/weidf/demo_data/prepilot_lucchi_pp",
            "description": "Prepilot Lucchi++ mitochondria segmentation project.",
            "recommended": False,
            "context_hints": {
                "imaging_modality": "EM",
                "target_structure": "mitochondria",
                "task_goal": "segmentation",
                "optimization_priority": "accuracy",
            },
        },
        {
            "id": "mito25-paper-loop-smoke",
            "name": "mito25-paper-loop-smoke",
            "directory_path": os.path.join(
                repo_root, "testing_projects", "mito25_paper_loop_smoke"
            ),
            "description": "Curated mito25 smoke project with image/seg, configs, checkpoint, and prediction artifacts.",
            "recommended": False,
        },
        {
            "id": "mito25-raw-data",
            "name": "mito25",
            "directory_path": os.path.join(workspace_root, "testing_data", "mito25"),
            "description": "Raw mito25 image/seg source data.",
            "recommended": False,
        },
        {
            "id": "mito25-smoke-raw-data",
            "name": "mito25-smoke",
            "directory_path": os.path.join(
                workspace_root, "testing_data", "mito25_smoke"
            ),
            "description": "Small paired mito25 HDF5 image/seg volumes for fast smoke testing.",
            "recommended": False,
        },
        {
            "id": "snemi-proofreading-data",
            "name": "snemi-proofreading",
            "directory_path": os.path.join(workspace_root, "testing_data", "snemi"),
            "description": "SNEMI-style TIFF image/label volumes for proofreading-focused testing.",
            "recommended": False,
        },
    ]
    if initial_project_root:
        candidates.insert(
            0,
            {
                "id": "initial-project",
                "name": os.path.basename(initial_project_root.rstrip(os.sep)),
                "directory_path": initial_project_root,
                "description": "Active local development project.",
                "recommended": True,
            },
        )
        for candidate in candidates[1:]:
            candidate["recommended"] = False

    unique_candidates = []
    seen_paths = set()
    for candidate in candidates:
        normalized_path = os.path.abspath(
            os.path.expanduser(candidate["directory_path"])
        )
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        unique_candidates.append(candidate)
    return unique_candidates


def _lower_path_parts(path: str) -> List[str]:
    normalized = os.path.normpath(path).lower()
    return [part for part in normalized.split(os.sep) if part]


def _project_extension(name: str) -> str:
    lower = name.lower()
    for compound in (".ome.tiff", ".ome.tif", ".nii.gz", ".pth.tar"):
        if lower.endswith(compound):
            return compound
    return os.path.splitext(lower)[1]


def _role_for_project_file(relative_path: str) -> Optional[str]:
    parts = _lower_path_parts(relative_path)
    name = parts[-1] if parts else os.path.basename(relative_path).lower()
    stem = name
    extension = _project_extension(name)
    if extension:
        stem = name[: -len(extension)]
    haystack = " ".join(parts + [stem])

    if extension in CHECKPOINT_EXTENSIONS or "checkpoint" in haystack:
        return "checkpoint"
    if extension in CONFIG_EXTENSIONS and (
        "config" in haystack or "mito" in haystack or "pytc" in haystack
    ):
        return "config"
    if extension not in VOLUME_EXTENSIONS:
        if extension in {".md", ".txt"} or "notes" in haystack:
            return "notes"
        return None

    if any(
        token in haystack
        for token in (
            "prediction",
            "predictions",
            "result",
            "inference",
            "candidate",
            "baseline",
        )
    ):
        return "prediction"
    if any(
        token in haystack
        for token in (
            "_seg",
            " seg",
            "segmentation",
            "label",
            "labels",
            "mask",
            "masks",
            "ground",
            "truth",
            "consensus",
            "gt",
        )
    ):
        return "label"
    if any(token in haystack for token in ("image", "images", "_im", "raw")):
        return "image"
    return "volume"


def _looks_like_image_label_pair(image_path: str, label_path: str) -> bool:
    image_name = os.path.basename(image_path).lower()
    label_name = os.path.basename(label_path).lower()
    normalized_image = (
        image_name.replace("_image", "")
        .replace("_images", "")
        .replace("_im", "")
        .replace("-image", "")
        .replace("image_", "")
        .replace("img_", "")
        .replace("raw_", "")
    )
    normalized_label = (
        label_name.replace("_seg", "")
        .replace("_label", "")
        .replace("_labels", "")
        .replace("_mask", "")
        .replace("_mito", "")
        .replace("_consensus", "")
        .replace("-seg", "")
        .replace("seg_", "")
        .replace("label_", "")
        .replace("labels_", "")
        .replace("mask_", "")
    )
    return normalized_image.split(".")[0] == normalized_label.split(".")[0]


def _safe_text_sample(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            raw = handle.read(PROJECT_PROFILE_TEXT_MAX_BYTES)
    except OSError:
        return ""
    return raw.decode("utf-8", errors="ignore")


def _inspect_hdf5_container(path: str, *, max_datasets: int = 16) -> Optional[dict]:
    try:
        import h5py  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        return None

    datasets = []
    root_attrs = []
    try:
        with h5py.File(path, "r") as handle:
            for key in list(handle.attrs.keys())[:8]:
                root_attrs.append(str(key))

            def visit(name, obj):
                if len(datasets) >= max_datasets:
                    return
                if isinstance(obj, h5py.Dataset):
                    datasets.append(
                        {
                            "path": name,
                            "shape": list(obj.shape),
                            "dtype": str(obj.dtype),
                        }
                    )

            handle.visititems(visit)
    except Exception as exc:
        return {"format": "hdf5", "readable": False, "error": type(exc).__name__}

    return {
        "format": "hdf5",
        "readable": True,
        "datasets": datasets,
        "root_attrs": root_attrs,
    }


def _inspect_tiff_container(path: str) -> Optional[dict]:
    if tifffile is None:
        return None
    try:
        with tifffile.TiffFile(path) as handle:
            series = handle.series[0] if handle.series else None
            return {
                "format": "tiff",
                "readable": True,
                "shape": list(series.shape) if series is not None else [],
                "dtype": str(series.dtype) if series is not None else None,
                "axes": getattr(series, "axes", None) if series is not None else None,
                "pages": len(handle.pages),
            }
    except Exception as exc:
        return {"format": "tiff", "readable": False, "error": type(exc).__name__}


def _json_safe_metadata_value(value: Any, *, max_items: int = 16) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="ignore")
    if np is not None:
        if isinstance(value, np.generic):
            value = value.item()
        elif isinstance(value, np.ndarray):
            flattened = value.reshape(-1)
            return [
                _json_safe_metadata_value(item, max_items=max_items)
                for item in flattened[:max_items]
            ]
    if isinstance(value, (list, tuple)):
        return [
            _json_safe_metadata_value(item, max_items=max_items)
            for item in list(value)[:max_items]
        ]
    if isinstance(value, dict):
        return {
            str(key): _json_safe_metadata_value(item, max_items=max_items)
            for key, item in list(value.items())[:max_items]
        }
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _attrs_to_safe_dict(attrs: Any, *, max_attrs: int = 16) -> dict:
    values = {}
    try:
        keys = list(attrs.keys())[:max_attrs]
    except Exception:
        return values
    for key in keys:
        try:
            values[str(key)] = _json_safe_metadata_value(attrs[key])
        except Exception:
            values[str(key)] = "<unreadable>"
    return values


def _numeric_values_from_metadata(value: Any) -> List[float]:
    if value is None:
        return []
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")
    if np is not None:
        if isinstance(value, np.generic):
            value = value.item()
        elif isinstance(value, np.ndarray):
            return [
                float(item)
                for item in value.reshape(-1).tolist()
                if isinstance(item, (int, float)) and math.isfinite(float(item))
            ]
    if isinstance(value, (list, tuple)):
        parsed = []
        for item in value:
            if isinstance(item, (int, float)) and math.isfinite(float(item)):
                parsed.append(float(item))
            elif isinstance(item, str):
                parsed.extend(_numeric_values_from_metadata(item))
        return parsed
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return [float(value)]
    if isinstance(value, str):
        return [
            float(match)
            for match in re.findall(r"\d+(?:\.\d+)?", value)
            if math.isfinite(float(match))
        ]
    return []


def _metadata_voxel_size_nm(attrs: dict) -> Optional[List[float]]:
    preferred_keys = (
        "voxel_size_nm_zyx",
        "voxel_size_nm",
        "resolution_nm",
        "spacing_nm",
        "pixel_size_nm",
        "voxel_size",
        "resolution",
        "spacing",
        "pixel_size",
        "scale",
    )
    normalized = {str(key).lower(): value for key, value in (attrs or {}).items()}
    ordered_keys = [
        key for preferred in preferred_keys for key in normalized if preferred in key
    ]
    for key in ordered_keys:
        values = _numeric_values_from_metadata(normalized[key])
        if len(values) < 3:
            continue
        multiplier = 1000.0 if re.search(r"(^|[_\s-])(um|micron)", key) else 1.0
        triplet = [round(value * multiplier, 6) for value in values[:3]]
        if all(value > 0 for value in triplet):
            return triplet
    return None


def _downsample_array_for_stats(
    array: Any, *, max_values: int = PROJECT_AUDIT_MAX_SAMPLE_VALUES
):
    if np is None:
        return None
    try:
        shape = tuple(int(axis) for axis in getattr(array, "shape", ()))
    except Exception:
        shape = ()
    if not shape:
        try:
            return np.asarray(array[()])
        except Exception:
            return None

    try:
        total_size = int(math.prod(shape))
    except Exception:
        total_size = 0
    if total_size <= 0:
        return None

    stride = 1
    if total_size > max_values:
        stride = max(1, int(math.ceil((total_size / max_values) ** (1 / len(shape)))))
    slices = tuple(slice(None, None, stride) for _ in shape)
    try:
        sample = np.asarray(array[slices])
    except Exception:
        try:
            sample = np.asarray(array)
        except Exception:
            return None

    if sample.size > max_values:
        stride = max(1, int(math.ceil((sample.size / max_values) ** (1 / sample.ndim))))
        sample = sample[tuple(slice(None, None, stride) for _ in range(sample.ndim))]
    return sample


def _sample_array_stats(array: Any) -> Optional[dict]:
    if np is None:
        return None
    sample = _downsample_array_for_stats(array)
    if sample is None:
        return None
    try:
        sample = np.asarray(sample)
    except Exception:
        return None
    stats = {
        "sampled_voxels": int(sample.size),
    }
    if sample.size == 0:
        stats.update({"empty": True})
        return stats

    if np.issubdtype(sample.dtype, np.number):
        numeric = sample.astype(np.float64, copy=False)
        finite_mask = np.isfinite(numeric)
        finite = numeric[finite_mask]
        stats["finite_fraction"] = float(finite.size / sample.size)
        if finite.size == 0:
            stats["empty"] = True
            return stats
        minimum = float(np.min(finite))
        maximum = float(np.max(finite))
        stats.update(
            {
                "min": minimum,
                "max": maximum,
                "mean": float(np.mean(finite)),
                "std": float(np.std(finite)),
                "dynamic_range": maximum - minimum,
                "nonzero_fraction": float(np.count_nonzero(finite) / finite.size),
            }
        )
        if np.issubdtype(sample.dtype, np.integer) or np.issubdtype(
            sample.dtype, np.bool_
        ):
            unique_values = np.unique(sample)
            stats["unique_count_sample"] = int(unique_values.size)
            stats["unique_values_preview"] = [
                _json_safe_metadata_value(item) for item in unique_values[:12]
            ]
    return stats


def _audit_findings_for_stats(
    relative_path: str, role: str, stats: Optional[dict]
) -> List[dict]:
    if not stats:
        return []
    findings = []
    nonzero_fraction = stats.get("nonzero_fraction")
    dynamic_range = stats.get("dynamic_range")
    unique_count = stats.get("unique_count_sample")
    if role == "image":
        if stats.get("sampled_voxels", 0) == 0:
            findings.append(
                {
                    "level": "warning",
                    "code": "empty_image_sample",
                    "message": "Image sample is empty.",
                    "path": relative_path,
                    "source": "volume_sample",
                }
            )
        elif nonzero_fraction == 0:
            findings.append(
                {
                    "level": "warning",
                    "code": "zero_image_sample",
                    "message": "Image sample is all zero.",
                    "path": relative_path,
                    "source": "volume_sample",
                }
            )
        elif dynamic_range is not None and dynamic_range <= 1:
            findings.append(
                {
                    "level": "warning",
                    "code": "low_dynamic_range_image",
                    "message": "Image sample has very little intensity variation.",
                    "path": relative_path,
                    "source": "volume_sample",
                }
            )
    elif role in {"label", "prediction"}:
        if nonzero_fraction == 0 or unique_count == 1:
            findings.append(
                {
                    "level": "warning",
                    "code": "empty_mask_sample",
                    "message": "Mask-like sample has no foreground labels.",
                    "path": relative_path,
                    "source": "volume_sample",
                }
            )
    return findings


def _audit_hdf5_volume(
    path: str,
    relative_path: str,
    role: str,
    *,
    collect_stats: bool = True,
) -> dict:
    try:
        import h5py  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        return {
            "path": relative_path,
            "role": role,
            "format": "hdf5",
            "readable": False,
            "error": "h5py_missing",
        }

    dataset_records = []
    findings = []
    try:
        with h5py.File(path, "r") as handle:
            root_attrs = _attrs_to_safe_dict(handle.attrs)

            def visit(name, obj):
                if len(dataset_records) >= 12:
                    return
                if isinstance(obj, h5py.Dataset):
                    dataset_attrs = _attrs_to_safe_dict(obj.attrs)
                    dataset_records.append(
                        {
                            "path": name,
                            "shape": list(obj.shape),
                            "dtype": str(obj.dtype),
                            "attrs": dataset_attrs,
                        }
                    )

            handle.visititems(visit)
            preferred_tokens = {
                "image": ("raw", "image", "img", "volume"),
                "label": ("label", "labels", "seg", "mask", "mito", "gt"),
                "prediction": ("prediction", "result", "seg", "mask"),
            }.get(role, ())
            selected_record = None
            for record in dataset_records:
                record_path = str(record.get("path", "")).lower()
                if preferred_tokens and any(
                    token in record_path for token in preferred_tokens
                ):
                    selected_record = record
                    break
            selected_record = selected_record or (
                dataset_records[0] if dataset_records else None
            )
            stats = None
            voxel_size_nm = _metadata_voxel_size_nm(root_attrs)
            if selected_record:
                dataset = handle[selected_record["path"]]
                stats = _sample_array_stats(dataset) if collect_stats else None
                voxel_size_nm = voxel_size_nm or _metadata_voxel_size_nm(
                    selected_record.get("attrs") or {}
                )
                if stats:
                    findings.extend(
                        _audit_findings_for_stats(relative_path, role, stats)
                    )
    except Exception as exc:
        return {
            "path": relative_path,
            "role": role,
            "format": "hdf5",
            "readable": False,
            "error": type(exc).__name__,
            "findings": [
                {
                    "level": "error",
                    "code": "unreadable_volume",
                    "message": f"Could not read {relative_path} as HDF5.",
                    "path": relative_path,
                    "source": "volume_metadata",
                }
            ],
        }

    result = {
        "path": relative_path,
        "role": role,
        "format": "hdf5",
        "readable": True,
        "datasets": dataset_records,
        "dataset_path": selected_record.get("path") if selected_record else None,
        "shape": selected_record.get("shape") if selected_record else None,
        "dtype": selected_record.get("dtype") if selected_record else None,
        "stats": stats,
        "findings": findings,
    }
    if voxel_size_nm:
        result["voxel_size_nm_zyx"] = voxel_size_nm
    return result


def _audit_tiff_volume(
    path: str,
    relative_path: str,
    role: str,
    *,
    collect_stats: bool = True,
) -> dict:
    metadata = _inspect_tiff_container(path)
    if not metadata:
        return {
            "path": relative_path,
            "role": role,
            "format": "tiff",
            "readable": False,
            "error": "tifffile_missing",
        }
    result = {"path": relative_path, "role": role, **metadata}
    if (
        collect_stats
        and metadata.get("readable")
        and tifffile is not None
        and np is not None
    ):
        try:
            sample = tifffile.memmap(path)
            stats = _sample_array_stats(sample)
            result["stats"] = stats
            result["findings"] = _audit_findings_for_stats(relative_path, role, stats)
        except Exception:
            result["findings"] = []
    return result


def _audit_volume_file(
    directory_path: str,
    relative_path: str,
    role: str,
    *,
    collect_stats: bool = True,
) -> dict:
    absolute_path = os.path.join(directory_path, relative_path)
    extension = _project_extension(relative_path)
    if extension in {".h5", ".hdf5"}:
        return _audit_hdf5_volume(
            absolute_path,
            relative_path,
            role,
            collect_stats=collect_stats,
        )
    if extension in {".tif", ".tiff", ".ome.tif", ".ome.tiff"}:
        return _audit_tiff_volume(
            absolute_path,
            relative_path,
            role,
            collect_stats=collect_stats,
        )
    if extension in {".zarr", ".n5"}:
        return {
            "path": relative_path,
            "role": role,
            "format": extension.lstrip("."),
            "readable": os.path.isdir(absolute_path),
            "findings": [],
        }
    return {
        "path": relative_path,
        "role": role,
        "format": extension.lstrip(".") or "unknown",
        "readable": os.path.exists(absolute_path),
        "findings": [],
    }


def _audit_context_facts(volumes: List[dict]) -> List[dict]:
    facts = []
    seen = set()
    for volume in volumes:
        voxel_size_nm = volume.get("voxel_size_nm_zyx")
        if not voxel_size_nm:
            continue
        key = ("voxel_size_nm", tuple(voxel_size_nm))
        if key in seen:
            continue
        seen.add(key)
        facts.append(
            {
                "key": "voxel_size_nm",
                "label": "Voxel size",
                "value": voxel_size_nm,
                "unit": "nm",
                "axis_order": "z,y,x",
                "source": f"volume_metadata:{volume.get('path')}",
                "confidence": "high",
            }
        )
    return facts[:8]


def _build_project_audit(
    directory_path: str,
    roles: dict,
    paired_examples: List[dict],
    *,
    include_volume_details: bool = True,
    collect_stats: bool = True,
) -> dict:
    volume_candidates = []
    seen_paths = set()

    def add_candidate(relative_path: Optional[str], role: str) -> None:
        if len(volume_candidates) >= PROJECT_AUDIT_MAX_VOLUME_FILES:
            return
        path = str(relative_path or "").strip()
        if not path or path in seen_paths:
            return
        seen_paths.add(path)
        volume_candidates.append((path, role))

    # Pair checks are only useful if both sides are inspected. Prefer declared
    # image/label pairs before filling the remaining sample budget.
    for pair in paired_examples:
        add_candidate(pair.get("image"), "image")
        add_candidate(pair.get("label"), "label")
        if len(volume_candidates) >= PROJECT_AUDIT_MAX_VOLUME_FILES:
            break

    for role in ("image", "label", "prediction", "volume"):
        for relative_path in roles.get(role) or []:
            add_candidate(relative_path, role)
            if len(volume_candidates) >= PROJECT_AUDIT_MAX_VOLUME_FILES:
                break
        if len(volume_candidates) >= PROJECT_AUDIT_MAX_VOLUME_FILES:
            break

    volumes = [
        _audit_volume_file(
            directory_path,
            relative_path,
            role,
            collect_stats=collect_stats,
        )
        for relative_path, role in volume_candidates
    ]
    volume_by_path = {volume.get("path"): volume for volume in volumes}
    pair_checks = []
    findings = []
    for volume in volumes:
        findings.extend(volume.get("findings") or [])
        if volume.get("readable") is False:
            findings.append(
                {
                    "level": "error",
                    "code": "unreadable_volume",
                    "message": f"Could not read {volume.get('path')}.",
                    "path": volume.get("path"),
                    "source": "volume_metadata",
                }
            )

    for pair in paired_examples[:PROJECT_AUDIT_MAX_VOLUME_FILES]:
        image_path = pair.get("image")
        label_path = pair.get("label")
        image_volume = volume_by_path.get(image_path)
        label_volume = volume_by_path.get(label_path)
        image_shape = image_volume.get("shape") if image_volume else None
        label_shape = label_volume.get("shape") if label_volume else None
        shape_match = bool(image_shape and label_shape and image_shape == label_shape)
        pair_check = {
            "image": image_path,
            "label": label_path,
            "image_shape": image_shape,
            "label_shape": label_shape,
            "shape_match": shape_match,
            "source": "volume_metadata",
        }
        pair_checks.append(pair_check)
        if image_shape and label_shape:
            findings.append(
                {
                    "level": "info" if shape_match else "warning",
                    "code": (
                        "pair_shape_match" if shape_match else "pair_shape_mismatch"
                    ),
                    "message": (
                        "Image and mask shapes match."
                        if shape_match
                        else "Image and mask shapes do not match."
                    ),
                    "path": image_path,
                    "related_path": label_path,
                    "source": "volume_metadata",
                }
            )

    level_counts = {"info": 0, "warning": 0, "error": 0}
    for finding in findings:
        level = finding.get("level")
        if level in level_counts:
            level_counts[level] += 1

    audit = {
        "schema_version": "pytc-project-audit/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "audited_volumes": len(volumes),
            "readable_volumes": sum(1 for volume in volumes if volume.get("readable")),
            "pair_checks": len(pair_checks),
            "shape_match_count": sum(
                1 for pair in pair_checks if pair.get("shape_match")
            ),
            "shape_mismatch_count": sum(
                1
                for pair in pair_checks
                if pair.get("image_shape")
                and pair.get("label_shape")
                and not pair.get("shape_match")
            ),
            "warnings": level_counts["warning"],
            "errors": level_counts["error"],
        },
        "pair_checks": pair_checks,
        "findings": findings[:PROJECT_AUDIT_MAX_FINDINGS],
        "context_facts": _audit_context_facts(volumes),
    }
    if include_volume_details:
        audit["volumes"] = volumes
    return audit


def _merge_audit_context_hints(context_hints: dict, audit: dict) -> dict:
    hints = dict(context_hints or {})
    for fact in audit.get("context_facts") or []:
        if fact.get("key") == "voxel_size_nm" and fact.get("value"):
            hints["voxel_size_nm"] = fact["value"]
            hints["voxel_size_source"] = fact.get("source") or "volume_metadata"
            break
    return hints


def _context_terms_for_text(text: str) -> List[str]:
    checks = {
        "EM": r"\bEM\b|electron microscopy|electron microscope|FIB-SEM|TEM|SEM",
        "XRI": r"\bXRI\b|x[\s-]?ray|xray",
        "CT": r"micro[\s-]?CT|micro.?ct|\bCT\b",
        "fluorescence": r"fluorescen|confocal|light[\s-]?sheet",
        "mitochondria": r"mitochond(?:ria|rion|rial)",
        "fibres": r"\b(?:fiber|fibers|fibre|fibres|cytotape)\b",
        "nuclei": r"\b(?:nuclei|nucleus|nuclear)\b",
        "neurites": r"\b(?:neurite|axon|dendrite|neuron[_\s-]?ids?)\b",
        "synapses": r"\b(?:synapse|synaptic|presynaptic|postsynaptic|cleft)\b",
        "segmentation": r"\bsegment(?:ation|ed|ing)?\b",
        "proofreading": r"\b(?:proofread|curat|correct)\b",
    }
    return [
        label
        for label, pattern in checks.items()
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def _collect_project_content_signals(
    directory_path: str, roles: dict, extension_counts: dict
):
    text_candidates = []
    seen_text_candidates = set()
    volume_candidates = []
    seen_volume_candidates = set()

    def add_text_candidate(relative_path: str) -> None:
        if relative_path in seen_text_candidates:
            return
        if len(text_candidates) >= PROJECT_PROFILE_MAX_CONTENT_FILES:
            return
        seen_text_candidates.add(relative_path)
        text_candidates.append(relative_path)

    for relative_path in (roles.get("config") or []) + (roles.get("notes") or []):
        add_text_candidate(relative_path)

    for current_dir, dirnames, filenames in os.walk(directory_path):
        dirnames[:] = [
            dirname
            for dirname in sorted(dirnames)
            if not _is_ignored_system_file(dirname)
        ]
        for filename in sorted(filenames):
            if _is_ignored_system_file(filename):
                continue
            relative_path = os.path.relpath(
                os.path.join(current_dir, filename), directory_path
            )
            relative_lower = relative_path.lower()
            extension = _project_extension(filename)
            if filename.lower() in {
                "project_manifest.json",
                "manifest.json",
                "readme.md",
                "README.md".lower(),
            } or (
                extension in TEXT_SIGNAL_EXTENSIONS
                and any(
                    token in relative_lower
                    for token in ("manifest", "metadata", "readme", "config", "note")
                )
            ):
                add_text_candidate(relative_path)
            if len(text_candidates) >= PROJECT_PROFILE_MAX_CONTENT_FILES:
                break
        if len(text_candidates) >= PROJECT_PROFILE_MAX_CONTENT_FILES:
            break

    for role in ("image", "label", "prediction", "volume"):
        for relative_path in roles.get(role) or []:
            if relative_path in seen_volume_candidates:
                continue
            seen_volume_candidates.add(relative_path)
            volume_candidates.append(relative_path)
            if len(volume_candidates) >= PROJECT_PROFILE_MAX_CONTENT_FILES:
                break
        if len(volume_candidates) >= PROJECT_PROFILE_MAX_CONTENT_FILES:
            break

    text_sources = []
    inference_text_parts = []
    for relative_path in text_candidates:
        absolute_path = os.path.join(directory_path, relative_path)
        text = _safe_text_sample(absolute_path)
        if not text:
            continue
        inference_text_parts.append(text)
        text_sources.append(
            {
                "path": relative_path,
                "extension": _project_extension(relative_path),
                "bytes_checked": min(
                    len(text.encode("utf-8", errors="ignore")),
                    PROJECT_PROFILE_TEXT_MAX_BYTES,
                ),
                "matched_terms": _context_terms_for_text(text),
            }
        )

    volume_metadata = []
    for relative_path in volume_candidates:
        absolute_path = os.path.join(directory_path, relative_path)
        extension = _project_extension(relative_path)
        metadata = None
        if extension in {".h5", ".hdf5"}:
            metadata = _inspect_hdf5_container(absolute_path)
        elif extension in {".tif", ".tiff", ".ome.tif", ".ome.tiff"}:
            metadata = _inspect_tiff_container(absolute_path)
        elif extension in {".zarr", ".n5"}:
            metadata = {
                "format": extension.lstrip("."),
                "readable": os.path.isdir(absolute_path),
            }
        if metadata:
            dataset_text = " ".join(
                dataset.get("path", "")
                for dataset in metadata.get("datasets", [])
                if isinstance(dataset, dict)
            )
            if dataset_text:
                inference_text_parts.append(dataset_text)
            volume_metadata.append(
                {
                    "path": relative_path,
                    "extension": extension,
                    **metadata,
                }
            )

    return {
        "extension_counts": extension_counts,
        "text_sources": text_sources,
        "volume_metadata": volume_metadata,
    }, "\n".join(inference_text_parts)


def _best_context_hint(text: str, patterns: List[tuple]) -> tuple:
    matches = []
    for value, pattern in patterns:
        count = len(re.findall(pattern, text, flags=re.IGNORECASE))
        if count:
            matches.append({"value": value, "count": count})
    matches.sort(key=lambda item: item["count"], reverse=True)
    if not matches:
        return None, []
    if len(matches) > 1 and matches[0]["count"] == matches[1]["count"]:
        return None, matches
    return matches[0]["value"], matches


def _parse_voxel_size_nm_hint(text: str) -> Optional[List[float]]:
    source = text or ""
    if not source.strip():
        return None
    three_axis_match = re.search(
        r"(?:voxel(?:\s+(?:size|spacing))?|resolution|spacing|pixel\s+size|scale)"
        r"[^\d]{0,60}"
        r"(\d+(?:\.\d+)?)\s*(?:x|by|,|;|/|-|\s)\s*"
        r"(\d+(?:\.\d+)?)\s*(?:x|by|,|;|/|-|\s)\s*"
        r"(\d+(?:\.\d+)?)(?:\s*(nm|nanometers?|um|\u00b5m|microns?))?",
        source,
        flags=re.IGNORECASE,
    )
    if three_axis_match:
        unit_text = (three_axis_match.group(4) or source).lower()
        multiplier = 1000.0 if re.search(r"\u00b5m|um|microns?", unit_text) else 1.0
        return [
            float(three_axis_match.group(index)) * multiplier for index in (1, 2, 3)
        ]

    unit_qualified_match = re.search(
        r"(?:at|@)?\s*(\d+(?:\.\d+)?)\s*(?:x|by|,|;|/|-)\s*"
        r"(\d+(?:\.\d+)?)\s*(?:x|by|,|;|/|-)\s*"
        r"(\d+(?:\.\d+)?)\s*(nm|nanometers?|um|\u00b5m|microns?)",
        source,
        flags=re.IGNORECASE,
    )
    if unit_qualified_match:
        unit_text = unit_qualified_match.group(4).lower()
        multiplier = 1000.0 if re.search(r"\u00b5m|um|microns?", unit_text) else 1.0
        return [
            float(unit_qualified_match.group(index)) * multiplier for index in (1, 2, 3)
        ]

    isotropic_match = re.search(
        r"(?:isotropic|cubic|same\s+voxel|same\s+scale)[^\d]{0,60}"
        r"(\d+(?:\.\d+)?)(?:\s*(nm|nanometers?|um|\u00b5m|microns?))?",
        source,
        flags=re.IGNORECASE,
    )
    if isotropic_match:
        unit_text = (isotropic_match.group(2) or source).lower()
        multiplier = 1000.0 if re.search(r"\u00b5m|um|microns?", unit_text) else 1.0
        value = float(isotropic_match.group(1)) * multiplier
        return [value, value, value]
    return None


def _infer_project_context_hints(content_text: str) -> dict:
    text = content_text or ""
    hints = {"source": "content_spot_check"}

    modality, modality_candidates = _best_context_hint(
        text,
        [
            ("EM", r"\bEM\b|electron microscopy|electron microscope|FIB-SEM|TEM|SEM"),
            ("X-ray / XRI volumetric microscopy", r"\bXRI\b|x[\s-]?ray|xray"),
            ("CT", r"micro[\s-]?CT|micro.?ct|\bCT\b"),
            ("fluorescence microscopy", r"fluorescen|confocal|light[\s-]?sheet"),
            ("MRI", r"\bMRI\b"),
        ],
    )
    target, target_candidates = _best_context_hint(
        text,
        [
            ("mitochondria", r"mitochond(?:ria|rion|rial)"),
            ("fibres", r"\b(?:fiber|fibers|fibre|fibres|cytotape)\b"),
            ("nuclei", r"\b(?:nuclei|nucleus|nuclear)\b"),
            ("neurites", r"\b(?:neurite|axon|dendrite|neuron[_\s-]?ids?)\b"),
            ("synapses", r"\b(?:synapse|synaptic|presynaptic|postsynaptic|cleft)\b"),
            ("membranes", r"\bmembranes?\b"),
            ("cells", r"\bcells?\b"),
        ],
    )
    task_goal, task_candidates = _best_context_hint(
        text,
        [
            ("segmentation", r"\bsegment(?:ation|ed|ing)?\b"),
            ("proofreading", r"\b(?:proofread|curat|correct)\b"),
            ("training", r"\b(?:train|retrain|fine[\s-]?tune)\b"),
            ("comparison", r"\b(?:compare|metric|evaluate|evaluation)\b"),
        ],
    )
    priority, priority_candidates = _best_context_hint(
        text,
        [
            ("accuracy", r"\b(?:accuracy|accurate|quality|careful)\b"),
            ("speed", r"\b(?:speed|fast|quick|smoke|rough)\b"),
        ],
    )

    if modality:
        hints["imaging_modality"] = modality
    if target:
        hints["target_structure"] = target
    if task_goal:
        hints["task_goal"] = task_goal
    if priority:
        hints["optimization_priority"] = priority
    if modality and target:
        lower_modality = modality.lower()
        lower_target = target.lower()
        if "xri" in lower_modality and "fibre" in lower_target:
            hints["task_family"] = "XRI fibre instance segmentation"
        elif "mitochond" in lower_target:
            hints["task_family"] = "mitochondria instance segmentation"
        elif "synap" in lower_target:
            hints["task_family"] = "synapse segmentation"
        elif "nuclei" in lower_target:
            hints["task_family"] = "nuclei instance segmentation"
    voxel_size_nm = _parse_voxel_size_nm_hint(text)
    if voxel_size_nm:
        hints["voxel_size_nm"] = voxel_size_nm
        hints["voxel_size_source"] = "content_spot_check"
    if modality_candidates:
        hints["modality_candidates"] = modality_candidates[:4]
    if target_candidates:
        hints["target_candidates"] = target_candidates[:6]
    if task_candidates:
        hints["task_goal_candidates"] = task_candidates[:4]
    if priority_candidates:
        hints["priority_candidates"] = priority_candidates[:3]
    return hints


def _project_role_directories(
    role_paths: List[str], *, max_directories: int = 6
) -> List[dict]:
    grouped = {}
    for role_path in role_paths:
        directory = os.path.dirname(role_path) or "."
        if directory not in grouped:
            grouped[directory] = {"path": directory, "count": 0, "examples": []}
        grouped[directory]["count"] += 1
        if len(grouped[directory]["examples"]) < 3:
            grouped[directory]["examples"].append(role_path)
    return sorted(
        grouped.values(),
        key=lambda item: (-item["count"], item["path"]),
    )[:max_directories]


def _project_primary_root(
    role_directories: dict, role: str, counts: dict
) -> Optional[str]:
    directories = role_directories.get(role) or []
    if not directories:
        return None
    # A single-file project is clearer as a file. Multi-volume projects should
    # default to the folder that owns the batch.
    if counts.get(role, 0) <= 1:
        return None
    return directories[0]["path"]


def _prepend_preferred_role_directory(
    role_directories: dict,
    role: str,
    preferred_root: Optional[str],
    role_paths: List[str],
    *,
    max_directories: int = 6,
) -> None:
    root = str(preferred_root or "").strip().replace("\\", "/").rstrip("/")
    if not root:
        return
    prefix = f"{root}/"
    examples = [
        path
        for path in role_paths
        if path == root or str(path).replace("\\", "/").startswith(prefix)
    ]
    if not examples:
        return
    preferred = {
        "path": root,
        "count": len(examples),
        "examples": examples[:3],
        "source": "project_manifest",
    }
    remaining = [
        item for item in (role_directories.get(role) or []) if item.get("path") != root
    ]
    role_directories[role] = [preferred, *remaining][:max_directories]


def _first_project_path(roles: dict, role: str) -> Optional[str]:
    values = roles.get(role) or []
    return values[0] if values else None


def _load_project_manifest_profile(directory_path: str) -> Optional[dict]:
    manifest_path = os.path.join(directory_path, "project_manifest.json")
    if not os.path.isfile(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return manifest if isinstance(manifest, dict) else None


def _unique_project_paths(paths: List[Optional[str]]) -> List[str]:
    seen = set()
    unique = []
    for path in paths:
        value = str(path or "").strip().replace("\\", "/")
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _manifest_volume_profile(manifest: Optional[dict]) -> dict:
    if not isinstance(manifest, dict):
        return {}
    volumes = [item for item in manifest.get("volumes") or [] if isinstance(item, dict)]
    if not volumes:
        return {}
    active_paths = manifest.get("active_paths")
    if not isinstance(active_paths, dict):
        active_paths = {}

    image_paths = _unique_project_paths([volume.get("image") for volume in volumes])
    label_paths = _unique_project_paths(
        [volume.get("segmentation") for volume in volumes if volume.get("segmentation")]
    )
    paired_examples = [
        {"image": volume.get("image"), "label": volume.get("segmentation")}
        for volume in volumes
        if volume.get("image") and volume.get("segmentation")
    ]
    image_root = active_paths.get("image_root") or (
        os.path.commonpath(image_paths) if len(image_paths) > 1 else None
    )
    label_root = active_paths.get("label_root") or (
        os.path.commonpath(label_paths) if len(label_paths) > 1 else None
    )
    volume_sets = []
    if image_paths:
        volume_sets.append(
            {
                "id": "manifest-active-set",
                "name": "manifest raw + masks",
                "image_root": image_root,
                "label_root": label_root,
                "image_count": len(image_paths),
                "label_count": len(label_paths),
                "pair_count": len(paired_examples),
                "examples": paired_examples[:3],
                "source": "project_manifest",
            }
        )

    voxel_size = manifest.get("voxel_size")
    voxel_size_nm = None
    if isinstance(voxel_size, dict):
        voxel_size_nm = voxel_size.get("zyx_nm")
    hints = {}
    if manifest.get("imaging_modality"):
        hints["imaging_modality"] = manifest.get("imaging_modality")
    if manifest.get("target_structure"):
        hints["target_structure"] = manifest.get("target_structure")
    if manifest.get("task_family"):
        hints["task_family"] = manifest.get("task_family")
    if manifest.get("task"):
        hints["task_goal"] = manifest.get("task")
    if voxel_size_nm:
        hints["voxel_size_nm"] = voxel_size_nm
        hints["voxel_size_source"] = "project_manifest.json"
    summary = manifest.get("initial_progress_summary")
    if isinstance(summary, dict):
        gt = int(summary.get("ground_truth") or 0)
        draft = int(summary.get("needs_proofreading") or 0)
        missing = int(summary.get("missing_segmentation") or 0)
        hints["mask_status"] = (
            f"mixed: {gt} ground-truth masks, {draft} draft masks, "
            f"{missing} image-only targets"
        )
    workflow_split = manifest.get("workflow_split")
    if isinstance(workflow_split, dict):
        if workflow_split.get("image_only_inference_targets"):
            hints["image_only_strategy"] = (
                "run inference on image-only volumes after training"
            )
        if workflow_split.get("ground_truth_training_volumes"):
            hints["training_policy"] = "train only on confirmed ground-truth masks"

    return {
        "active_paths": active_paths,
        "image_paths": image_paths,
        "label_paths": label_paths,
        "paired_examples": paired_examples,
        "volume_sets": volume_sets,
        "context_hints": hints,
    }


def _project_stage_status(
    *,
    ready: bool,
    missing: Optional[List[str]] = None,
    ready_label: str,
    needed_label: str,
    blocked_label: str = "Add an image volume first.",
) -> dict:
    missing = missing or []
    if ready:
        return {"status": "ready", "label": ready_label, "missing": []}
    if missing:
        return {"status": "needs_input", "label": needed_label, "missing": missing}
    return {"status": "blocked", "label": blocked_label, "missing": []}


def _build_project_workable_schema(
    roles: dict,
    counts: dict,
    paired_examples: List[dict],
    role_directories: dict,
    volume_sets: List[dict],
    *,
    truncated: bool,
) -> dict:
    primary_image = _first_project_path(roles, "image") or _first_project_path(
        roles, "volume"
    )
    primary_label = (
        paired_examples[0]["label"]
        if paired_examples
        else _first_project_path(roles, "label")
    )
    primary_prediction = _first_project_path(roles, "prediction")
    primary_config = _first_project_path(roles, "config")
    primary_checkpoint = _first_project_path(roles, "checkpoint")
    has_image = bool(primary_image)
    has_mask_like = bool(primary_label or primary_prediction)
    has_image_label = bool(primary_image and primary_label)
    # Configs are implementation details the agent can infer from presets. They
    # are tracked for provenance, but should not block a biologist from starting
    # an otherwise valid image/checkpoint or image/label workflow.
    has_inference_inputs = bool(primary_image and primary_checkpoint)
    has_training_inputs = bool(primary_image and primary_label)
    has_evaluation_inputs = bool(primary_label and counts.get("prediction", 0) >= 2)

    if not has_image:
        mode = "not_workable"
        summary = "No image volume detected yet."
    elif has_evaluation_inputs and has_training_inputs and primary_checkpoint:
        mode = "closed_loop_ready"
        summary = (
            "Ready for visualization, proofreading, training, and before/after checks."
        )
    elif has_image_label:
        mode = "image_mask_pair"
        summary = "Ready to start from an image and mask/label pair."
    else:
        mode = "image_only"
        summary = "Ready to start from an image volume; masks, configs, or checkpoints can be added later."

    inference_missing = []
    if not primary_image:
        inference_missing.append("image volume")
    if not primary_checkpoint:
        inference_missing.append("checkpoint")

    proofreading_missing = []
    if not primary_image:
        proofreading_missing.append("image volume")
    if not has_mask_like:
        proofreading_missing.append("mask, label, or prediction")

    training_missing = []
    if not primary_image:
        training_missing.append("image volume")
    if not primary_label:
        training_missing.append("label or corrected mask")

    evaluation_missing = []
    if counts.get("prediction", 0) < 2:
        evaluation_missing.append("baseline and candidate predictions")
    if not primary_label:
        evaluation_missing.append("reference label or ground truth")

    return {
        "schema_version": "pytc-project-profile/v1",
        "workable": has_image,
        "mode": mode,
        "summary": summary,
        "truncated": truncated,
        "primary_paths": {
            "image": primary_image,
            "image_root": _project_primary_root(role_directories, "image", counts)
            or _project_primary_root(role_directories, "volume", counts),
            "label": primary_label,
            "label_root": _project_primary_root(role_directories, "label", counts),
            "mask": primary_label or primary_prediction,
            "mask_root": _project_primary_root(role_directories, "label", counts),
            "prediction": primary_prediction,
            "prediction_root": _project_primary_root(
                role_directories, "prediction", counts
            ),
            "config": primary_config,
            "checkpoint": primary_checkpoint,
        },
        "role_directories": role_directories,
        "volume_sets": volume_sets,
        "stages": {
            "setup": _project_stage_status(
                ready=has_image,
                ready_label="Image volume detected.",
                needed_label="Choose an image volume.",
            ),
            "visualization": _project_stage_status(
                ready=has_image,
                ready_label="Ready to visualize.",
                needed_label="Choose an image volume.",
            ),
            "inference": _project_stage_status(
                ready=has_inference_inputs,
                ready_label="Ready to run inference.",
                needed_label="Needs inference inputs.",
                missing=inference_missing,
            ),
            "proofreading": _project_stage_status(
                ready=bool(primary_image and has_mask_like),
                ready_label="Ready to proofread masks.",
                needed_label="Needs a mask, label, or prediction.",
                missing=proofreading_missing,
            ),
            "training": _project_stage_status(
                ready=has_training_inputs,
                ready_label="Ready to train from labels/corrections.",
                needed_label="Needs training inputs.",
                missing=training_missing,
            ),
            "evaluation": _project_stage_status(
                ready=has_evaluation_inputs,
                ready_label="Ready to compare before/after predictions.",
                needed_label="Needs comparison inputs.",
                missing=evaluation_missing,
            ),
        },
    }


def _infer_project_volume_sets(roles: dict, role_directories: dict) -> List[dict]:
    image_paths = roles.get("image") or roles.get("volume") or []
    label_paths = roles.get("label") or []
    volume_sets = []

    if not image_paths:
        return volume_sets

    labels_by_directory = {}
    for label_path in label_paths:
        labels_by_directory.setdefault(os.path.dirname(label_path) or ".", []).append(
            label_path
        )

    image_directories = (
        role_directories.get("image") or role_directories.get("volume") or []
    )
    for image_directory in image_directories:
        directory = image_directory["path"]
        images_in_directory = [
            image_path
            for image_path in image_paths
            if (os.path.dirname(image_path) or ".") == directory
        ]
        best_label_directory = None
        best_pairs = []
        for label_directory in role_directories.get("label", []):
            labels_in_directory = labels_by_directory.get(label_directory["path"], [])
            pairs = []
            for image_path in images_in_directory:
                for label_path in labels_in_directory:
                    if _looks_like_image_label_pair(image_path, label_path):
                        pairs.append({"image": image_path, "label": label_path})
                        break
            if len(pairs) > len(best_pairs):
                best_pairs = pairs
                best_label_directory = label_directory

        name = os.path.basename(directory) or directory
        label_root = best_label_directory["path"] if best_label_directory else None
        if label_root and os.path.basename(label_root) == name:
            set_name = name
        elif label_root:
            set_name = f"{name} + {os.path.basename(label_root) or label_root}"
        else:
            set_name = name

        if best_pairs or image_directory["count"] > 1:
            volume_sets.append(
                {
                    "id": f"set-{len(volume_sets) + 1}",
                    "name": set_name,
                    "image_root": directory,
                    "label_root": label_root,
                    "image_count": image_directory["count"],
                    "label_count": (
                        best_label_directory["count"] if best_label_directory else 0
                    ),
                    "pair_count": len(best_pairs),
                    "examples": best_pairs[:3],
                }
            )
        if len(volume_sets) >= 6:
            break

    if not volume_sets and image_paths:
        primary_image_directory = (
            image_directories[0].get("path")
            if image_directories
            else os.path.dirname(image_paths[0]) or "."
        )
        primary_label_directory = (
            role_directories.get("label", [{}])[0].get("path")
            if role_directories.get("label")
            else None
        )
        volume_sets.append(
            {
                "id": "set-1",
                "name": os.path.basename(primary_image_directory)
                or primary_image_directory,
                "image_root": primary_image_directory,
                "label_root": primary_label_directory,
                "image_count": len(image_paths),
                "label_count": len(label_paths),
                "pair_count": 0,
                "examples": [],
            }
        )

    return volume_sets


def _record_project_role_path(
    roles: dict,
    counts: dict,
    role: Optional[str],
    relative_path: str,
) -> None:
    if role and role in roles:
        counts[role] += 1
        roles[role].append(relative_path)


def _apply_manifest_profile_to_roles(roles: dict, manifest_profile: dict) -> None:
    if not manifest_profile:
        return
    image_paths = manifest_profile.get("image_paths") or []
    label_paths = manifest_profile.get("label_paths") or []
    active_paths = manifest_profile.get("active_paths") or {}
    if image_paths:
        roles["image"] = _unique_project_paths(
            [*image_paths, *(roles.get("image") or [])]
        )
    if label_paths:
        roles["label"] = _unique_project_paths(
            [*label_paths, *(roles.get("label") or [])]
        )
    active_config = active_paths.get("config")
    if active_config:
        roles["config"] = _unique_project_paths(
            [active_config, *(roles.get("config") or [])]
        )


def _scan_project_profile(directory_path: str, *, audit_detail: str = "full") -> dict:
    roles = {
        "image": [],
        "label": [],
        "prediction": [],
        "config": [],
        "checkpoint": [],
        "volume": [],
        "notes": [],
    }
    counts = {role: 0 for role in roles}
    extension_counts = {}
    scanned_files = 0
    truncated = False

    for current_dir, dirnames, filenames in os.walk(directory_path):
        next_dirnames = []
        for dirname in sorted(dirnames):
            if _is_ignored_system_file(dirname):
                continue
            absolute_dir = os.path.join(current_dir, dirname)
            relative_dir = os.path.relpath(absolute_dir, directory_path)
            if _project_extension(dirname) in {".zarr", ".n5"}:
                extension = _project_extension(dirname)
                extension_counts[extension] = extension_counts.get(extension, 0) + 1
                _record_project_role_path(
                    roles,
                    counts,
                    _role_for_project_file(relative_dir),
                    relative_dir,
                )
                continue
            next_dirnames.append(dirname)
        dirnames[:] = next_dirnames
        for filename in sorted(filenames):
            if _is_ignored_system_file(filename):
                continue
            scanned_files += 1
            if scanned_files > PROJECT_PROFILE_MAX_FILES:
                truncated = True
                break
            absolute_path = os.path.join(current_dir, filename)
            relative_path = os.path.relpath(absolute_path, directory_path)
            extension = _project_extension(filename) or "<none>"
            extension_counts[extension] = extension_counts.get(extension, 0) + 1
            _record_project_role_path(
                roles,
                counts,
                _role_for_project_file(relative_path),
                relative_path,
            )
        if truncated:
            break

    manifest = _load_project_manifest_profile(directory_path)
    manifest_profile = _manifest_volume_profile(manifest)
    _apply_manifest_profile_to_roles(roles, manifest_profile)

    paired_examples = manifest_profile.get("paired_examples") or []
    for image_path in roles["image"]:
        if len(paired_examples) >= 4:
            break
        for label_path in roles["label"]:
            if _looks_like_image_label_pair(image_path, label_path):
                pair = {"image": image_path, "label": label_path}
                if pair not in paired_examples:
                    paired_examples.append(pair)
                break

    role_directories = {
        role: _project_role_directories(paths) for role, paths in roles.items()
    }
    manifest_active_paths = manifest_profile.get("active_paths") or {}
    _prepend_preferred_role_directory(
        role_directories,
        "image",
        manifest_active_paths.get("image_root"),
        roles.get("image") or [],
    )
    _prepend_preferred_role_directory(
        role_directories,
        "label",
        manifest_active_paths.get("label_root"),
        roles.get("label") or [],
    )
    volume_sets = manifest_profile.get("volume_sets") or _infer_project_volume_sets(
        roles, role_directories
    )
    examples = {role: paths[:8] for role, paths in roles.items()}
    schema = _build_project_workable_schema(
        examples,
        counts,
        paired_examples,
        role_directories,
        volume_sets,
        truncated=truncated,
    )
    content_signals, content_text = _collect_project_content_signals(
        directory_path,
        roles,
        extension_counts,
    )
    use_summary_audit = audit_detail == "summary"
    audit = _build_project_audit(
        directory_path,
        roles,
        paired_examples,
        include_volume_details=not use_summary_audit,
        collect_stats=not use_summary_audit,
    )
    context_hints = _merge_audit_context_hints(
        _infer_project_context_hints(content_text),
        audit,
    )
    context_hints = {
        **context_hints,
        **(manifest_profile.get("context_hints") or {}),
    }
    schema["context_hints"] = context_hints
    schema["audit"] = audit
    if manifest_profile:
        schema["manifest"] = {
            "title": manifest.get("title") if isinstance(manifest, dict) else None,
            "active_paths": manifest_profile.get("active_paths") or {},
            "initial_progress_summary": (
                manifest.get("initial_progress_summary")
                if isinstance(manifest, dict)
                else None
            ),
        }

    required_roles = {
        "image": counts["image"] > 0,
        "label": counts["label"] > 0,
        "config": counts["config"] > 0,
        "checkpoint": counts["checkpoint"] > 0,
        "prediction": counts["prediction"] >= 2,
    }
    missing_roles = [role for role, present in required_roles.items() if not present]

    return {
        "scanned_files": min(scanned_files, PROJECT_PROFILE_MAX_FILES),
        "truncated": truncated,
        "counts": counts,
        "examples": examples,
        "role_directories": role_directories,
        "volume_sets": volume_sets,
        "paired_examples": paired_examples,
        "content_signals": content_signals,
        "context_hints": context_hints,
        "audit": audit,
        "ready_for_smoke": not missing_roles,
        "missing_roles": missing_roles,
        "schema": schema,
    }


def _project_context_file_path(directory_path: str) -> str:
    source_dir = os.path.abspath(os.path.expanduser(directory_path))
    if not os.path.isdir(source_dir):
        raise HTTPException(status_code=400, detail="Directory does not exist")
    return os.path.join(source_dir, PROJECT_CONTEXT_FILENAME)


def _assert_project_context_access(
    db: Session,
    *,
    user_id: int,
    directory_path: str,
) -> None:
    source_dir = os.path.abspath(os.path.expanduser(directory_path))
    if _is_managed_upload_path(user_id, source_dir):
        return
    mounted_roots = (
        db.query(models.File)
        .filter(
            models.File.user_id == user_id,
            models.File.path == "root",
            models.File.is_folder.is_(True),
            models.File.physical_path.isnot(None),
        )
        .all()
    )
    for root in mounted_roots:
        root_path = os.path.abspath(os.path.expanduser(root.physical_path or ""))
        if source_dir == root_path or source_dir.startswith(f"{root_path}{os.sep}"):
            return
    raise HTTPException(
        status_code=403,
        detail="Project context can only be read or written for mounted projects.",
    )


def _read_project_context_profile(directory_path: str) -> Optional[dict]:
    context_path = _project_context_file_path(directory_path)
    if not os.path.isfile(context_path):
        return None
    try:
        with open(context_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500, detail="Project context file could not be read"
        ) from exc
    return data if isinstance(data, dict) else None


def _write_project_context_profile(directory_path: str, profile: dict) -> dict:
    context_path = _project_context_file_path(directory_path)
    now = datetime.now(timezone.utc).isoformat()
    existing = _read_project_context_profile(directory_path) or {}
    payload = {
        **existing,
        **(profile or {}),
        "schema_version": "pytc-project-context/v1",
        "updated_at": now,
    }
    payload.setdefault("created_at", existing.get("created_at") or now)
    temp_path = f"{context_path}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, context_path)
    except OSError as exc:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=500, detail="Project context file could not be written"
        ) from exc
    return payload


def _delete_project_context_profile(directory_path: str) -> bool:
    context_path = _project_context_file_path(directory_path)
    if not os.path.exists(context_path):
        return False
    try:
        os.remove(context_path)
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail="Project context file could not be deleted"
        ) from exc
    return True


def _ensure_unique_name(
    db: Session, user_id: int, parent_path: str, base_name: str
) -> str:
    existing_names = {
        row[0]
        for row in db.query(models.File.name).filter(
            models.File.user_id == user_id, models.File.path == parent_path
        )
    }
    if base_name not in existing_names:
        return base_name
    index = 2
    while True:
        candidate = f"{base_name} ({index})"
        if candidate not in existing_names:
            return candidate
        index += 1


def _normalize_mount_directory_input(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Project path is required")

    parsed = urlparse(value)
    if parsed.scheme == "file":
        value = unquote(parsed.path)
    elif parsed.scheme in {"http", "https"}:
        query = parse_qs(parsed.query)
        for key in ("directory_path", "project_path", "path", "project"):
            if query.get(key) and query[key][0]:
                value = query[key][0]
                break
        else:
            candidate = unquote(parsed.path or "")
            if candidate.startswith(("/home/", "/mnt/", "/data/", "/tmp/")):
                value = candidate
            elif os.getenv("PYTC_INITIAL_PROJECT_ROOT"):
                value = os.getenv("PYTC_INITIAL_PROJECT_ROOT", "")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Remote browser mounts need a server path, or a URL with "
                        "a path/directory_path query parameter."
                    ),
                )

    return os.path.abspath(os.path.expanduser(value))


def _mounted_project_response(
    source_dir: str,
    mounted_root: models.File,
    *,
    mounted_folders: int,
    mounted_files: int,
    message: str,
) -> dict:
    return {
        "message": message,
        "directory_path": source_dir,
        "mounted_root_id": mounted_root.id,
        "mount_name": mounted_root.name,
        "mounted_folders": mounted_folders,
        "mounted_files": mounted_files,
        "profile": _scan_project_profile(source_dir),
    }


def _count_indexed_mount_descendants(
    db: Session,
    *,
    user_id: int,
    mounted_root_id: int,
) -> tuple[int, int]:
    pending_parent_ids = [str(mounted_root_id)]
    mounted_folders = 0
    mounted_files = 0
    while pending_parent_ids:
        parent_id = pending_parent_ids.pop(0)
        children = (
            db.query(models.File)
            .filter(models.File.user_id == user_id, models.File.path == parent_id)
            .all()
        )
        for child in children:
            if child.is_folder:
                mounted_folders += 1
                pending_parent_ids.append(str(child.id))
            else:
                mounted_files += 1
    return mounted_folders, mounted_files


def _is_managed_upload_path(user_id: int, physical_path: Optional[str]) -> bool:
    if not physical_path:
        return False
    uploads_root = os.path.abspath(os.path.join("uploads", str(user_id)))
    target = os.path.abspath(os.path.expanduser(physical_path))
    try:
        return os.path.commonpath([uploads_root, target]) == uploads_root
    except ValueError:
        return False


def _repair_stale_mounted_entries(db: Session, user_id: int) -> None:
    candidates = (
        db.query(models.File)
        .filter(
            models.File.user_id == user_id,
            models.File.physical_path.isnot(None),
            models.File.path != "root",
        )
        .all()
    )

    changed = False
    for entry in candidates:
        if not entry.physical_path:
            continue
        if _is_managed_upload_path(user_id, entry.physical_path):
            continue
        if os.path.exists(entry.physical_path):
            continue

        repaired = resolve_existing_path(entry.physical_path)
        if repaired is None or not repaired.exists():
            continue
        if entry.is_folder and not repaired.is_dir():
            continue
        if not entry.is_folder and not repaired.is_file():
            continue

        entry.physical_path = str(repaired)
        entry.name = repaired.name
        if not entry.is_folder:
            entry.type = mimetypes.guess_type(str(repaired))[0] or entry.type
            try:
                entry.size = _format_size(repaired.stat().st_size)
            except OSError:
                pass
        changed = True

    if changed:
        db.commit()


def _prune_missing_managed_upload_entries(db: Session, user_id: int) -> None:
    candidates = (
        db.query(models.File)
        .filter(
            models.File.user_id == user_id,
            models.File.is_folder.is_(False),
            models.File.physical_path.isnot(None),
        )
        .all()
    )

    removed = False
    for entry in candidates:
        if not entry.physical_path:
            continue
        if not _is_managed_upload_path(user_id, entry.physical_path):
            continue
        if os.path.exists(entry.physical_path):
            continue
        db.delete(entry)
        removed = True

    if removed:
        db.commit()


def _delete_file_tree(
    db: Session,
    user_id: int,
    node: models.File,
    delete_disk_files: bool = True,
):
    children = (
        db.query(models.File)
        .filter(models.File.path == str(node.id), models.File.user_id == user_id)
        .all()
    )
    for child in children:
        _delete_file_tree(db, user_id, child, delete_disk_files=delete_disk_files)

    if (
        delete_disk_files
        and not node.is_folder
        and node.physical_path
        and os.path.exists(node.physical_path)
        and _is_managed_upload_path(user_id, node.physical_path)
    ):
        os.remove(node.physical_path)
    db.delete(node)


def _get_or_create_guest_user(db: Session) -> models.User:
    """Return the shared guest user, creating it if needed."""
    guest = db.query(models.User).filter(models.User.username == "guest").first()
    if guest:
        return guest
    guest = models.User(
        username="guest",
        email=None,
        hashed_password=utils.get_password_hash("guest"),
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)
):
    # If no token is provided, fall back to the shared guest account.
    if not token:
        return _get_or_create_guest_user(db)

    try:
        payload = jwt.decode(token, utils.SECRET_KEY, algorithms=[utils.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return _get_or_create_guest_user(db)
        token_data = models.TokenData(username=username)
    except JWTError:
        return _get_or_create_guest_user(db)

    user = (
        db.query(models.User)
        .filter(models.User.username == token_data.username)
        .first()
    )
    if user is None:
        return _get_or_create_guest_user(db)
    return user


@router.post("/register", response_model=models.UserResponse)
def register(user: models.UserCreate, db: Session = Depends(database.get_db)):
    db_user = (
        db.query(models.User).filter(models.User.username == user.username).first()
    )
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = utils.get_password_hash(user.password)
    new_user = models.User(
        username=user.username, email=user.email, hashed_password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/token", response_model=models.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(models.User).filter(models.User.username == form_data.username).first()
    )
    if not user or not utils.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = utils.timedelta(minutes=utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = utils.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=models.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/users/me/projects", response_model=models.UserProjectListResponse)
def list_current_user_projects(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    mounted_roots = (
        db.query(models.File)
        .filter(
            models.File.user_id == current_user.id,
            models.File.path == "root",
            models.File.is_folder.is_(True),
            models.File.physical_path.isnot(None),
        )
        .order_by(models.File.created_at.asc(), models.File.id.asc())
        .all()
    )
    mounted_projects = []
    for root in mounted_roots:
        directory_path = os.path.abspath(os.path.expanduser(root.physical_path or ""))
        if not os.path.isdir(directory_path):
            continue
        mounted_folders, mounted_files = _count_indexed_mount_descendants(
            db,
            user_id=current_user.id,
            mounted_root_id=root.id,
        )
        mounted_projects.append(
            models.MountedProjectResponse(
                mounted_root_id=root.id,
                name=root.name,
                directory_path=directory_path,
                mounted_folders=mounted_folders,
                mounted_files=mounted_files,
                profile=_scan_project_profile(directory_path, audit_detail="summary"),
                created_at=root.created_at,
            )
        )
    return models.UserProjectListResponse(
        user=current_user,
        mounted_projects=mounted_projects,
    )


# File Management Endpoints


@router.get("/files", response_model=List[models.FileResponse])
def get_files(
    parent: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    _repair_stale_mounted_entries(db, current_user.id)
    _prune_missing_managed_upload_entries(db, current_user.id)
    query = db.query(models.File).filter(models.File.user_id == current_user.id)
    if parent is not None:
        if parent != "root":
            try:
                parent_id = int(parent)
            except (TypeError, ValueError):
                parent_id = -1
            parent_folder = (
                db.query(models.File)
                .filter(
                    models.File.id == parent_id,
                    models.File.user_id == current_user.id,
                    models.File.is_folder.is_(True),
                )
                .first()
            )
            if not parent_folder:
                raise HTTPException(
                    status_code=404,
                    detail=f"Folder is no longer mounted or indexed: {parent}",
                )
        query = query.filter(models.File.path == parent)

    return [
        file
        for file in query.order_by(
            models.File.is_folder.desc(), models.File.name.asc()
        ).all()
        if not _is_ignored_system_file(file.name)
    ]


@router.get("/files/preview/{file_id}")
def file_preview(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    if cv2 is None or np is None:
        raise HTTPException(status_code=500, detail="Preview dependencies missing")

    file = (
        db.query(models.File)
        .filter(models.File.id == file_id, models.File.user_id == current_user.id)
        .first()
    )
    if not file or file.is_folder:
        raise HTTPException(status_code=404, detail="File not found")
    if not file.physical_path or not os.path.exists(file.physical_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    def to_uint8(arr):
        if arr is None:
            return None
        if arr.dtype == np.uint8:
            return arr
        arr = arr.astype(np.float32)
        min_val = np.nanmin(arr)
        max_val = np.nanmax(arr)
        if max_val <= min_val:
            return np.zeros_like(arr, dtype=np.uint8)
        scaled = (arr - min_val) / (max_val - min_val)
        return np.clip(scaled * 255.0, 0, 255).astype(np.uint8)

    def load_image(path: str) -> Optional["np.ndarray"]:
        ext = os.path.splitext(path)[1].lower()
        if ext in {".tif", ".tiff"} and tifffile is not None:
            try:
                img = tifffile.imread(path)
            except Exception:
                img = None
        else:
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None

        img = np.asarray(img)
        if img.ndim == 2:
            return to_uint8(img)
        if img.ndim == 3:
            if img.shape[2] in (3, 4):
                if img.shape[2] == 4:
                    img = img[:, :, :3]
                return to_uint8(img)
            mid = img.shape[0] // 2
            return to_uint8(img[mid])
        if img.ndim == 4:
            mid = img.shape[0] // 2
            img = img[mid]
            if img.ndim == 3 and img.shape[2] == 4:
                img = img[:, :, :3]
            return to_uint8(img)
        return None

    image = load_image(file.physical_path)
    if image is None:
        raise HTTPException(status_code=415, detail="Unsupported image format")

    max_dim = 160
    height, width = image.shape[:2]
    scale = min(1.0, max_dim / max(height, width))
    if scale < 1.0:
        new_size = (int(width * scale), int(height * scale))
        image = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)

    success, buffer = cv2.imencode(".png", image)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode preview")
    return Response(content=buffer.tobytes(), media_type="image/png")


@router.post("/files/upload", response_model=models.FileResponse)
def upload_file(
    path: str = Form(...),
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    if _is_ignored_system_file(file.filename):
        raise HTTPException(status_code=400, detail="System metadata files are ignored")

    # Create uploads directory if not exists
    upload_dir = f"uploads/{current_user.id}"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = f"{upload_dir}/{unique_filename}"

    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Calculate size (approx)
    size_bytes = os.path.getsize(file_path)
    size_str = (
        f"{size_bytes / 1024:.1f}KB"
        if size_bytes < 1024 * 1024
        else f"{size_bytes / (1024 * 1024):.1f}MB"
    )

    new_file = models.File(
        user_id=current_user.id,
        name=file.filename,
        path=path,
        is_folder=False,
        size=size_str,
        type=file.content_type or "unknown",
        physical_path=file_path,
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    return new_file


@router.post("/files/folder", response_model=models.FileResponse)
def create_folder(
    file: models.FileCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    new_folder = models.File(
        user_id=current_user.id,
        name=file.name,
        path=file.path,
        is_folder=True,
        size="0KB",
        type="folder",
    )
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return new_folder


@router.post("/files/copy", response_model=models.FileResponse)
def copy_file(
    file_copy: models.FileCopy,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    # Find source file
    source_file = (
        db.query(models.File)
        .filter(
            models.File.id == file_copy.source_id,
            models.File.user_id == current_user.id,
        )
        .first()
    )
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")

    # If it's a folder, we don't support recursive copy yet (or implement it if needed)
    # For now, let's assume file copy only or simple folder entry copy

    new_physical_path = None
    if (
        not source_file.is_folder
        and source_file.physical_path
        and os.path.exists(source_file.physical_path)
    ):
        # Generate new filename
        file_ext = os.path.splitext(source_file.physical_path)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        # Use same upload dir
        upload_dir = os.path.dirname(source_file.physical_path)
        new_physical_path = f"{upload_dir}/{unique_filename}"
        shutil.copy2(source_file.physical_path, new_physical_path)

    new_file = models.File(
        user_id=current_user.id,
        name=f"Copy of {source_file.name}",
        path=file_copy.destination_path,
        is_folder=source_file.is_folder,
        size=source_file.size,
        type=source_file.type,
        physical_path=new_physical_path,
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    return new_file


@router.post("/files/mount")
def mount_directory(
    mount_request: models.MountDirectoryRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    # This endpoint creates an app-managed file index for a project root.
    # The same contract can later be backed by cloud project files/URIs for
    # programmatic access without changing the UI workflow.
    source_dir = _normalize_mount_directory_input(mount_request.directory_path)
    if not os.path.isdir(source_dir):
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist on the server: {source_dir}",
        )

    destination_path = mount_request.destination_path or "root"
    if destination_path != "root":
        try:
            destination_id = int(destination_path)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid destination path"
            ) from exc
        destination_folder = (
            db.query(models.File)
            .filter(
                models.File.id == destination_id,
                models.File.user_id == current_user.id,
                models.File.is_folder.is_(True),
            )
            .first()
        )
        if not destination_folder:
            raise HTTPException(status_code=404, detail="Destination folder not found")

    existing_mount = (
        db.query(models.File)
        .filter(
            models.File.user_id == current_user.id,
            models.File.path == destination_path,
            models.File.is_folder.is_(True),
            models.File.physical_path == source_dir,
        )
        .first()
    )
    if existing_mount:
        child_count = (
            db.query(models.File)
            .filter(
                models.File.user_id == current_user.id,
                models.File.path == str(existing_mount.id),
            )
            .count()
        )
        return _mounted_project_response(
            source_dir,
            existing_mount,
            mounted_folders=1,
            mounted_files=child_count,
            message=f"{existing_mount.name} is already mounted.",
        )

    default_name = os.path.basename(source_dir.rstrip(os.sep)) or "mounted-project"
    requested_name = (
        mount_request.mount_name.strip()
        if mount_request.mount_name and mount_request.mount_name.strip()
        else default_name
    )
    root_name = _ensure_unique_name(
        db, current_user.id, destination_path, requested_name
    )
    mounted_root = models.File(
        user_id=current_user.id,
        name=root_name,
        path=destination_path,
        is_folder=True,
        size="0KB",
        type="folder",
        physical_path=source_dir,
    )
    db.add(mounted_root)
    db.flush()

    dir_to_id = {source_dir: str(mounted_root.id)}
    mounted_folders = 1
    mounted_files = 0

    for current_dir, dirnames, filenames in os.walk(source_dir, topdown=True):
        parent_id = dir_to_id.get(current_dir)
        if parent_id is None:
            continue
        dirnames.sort()
        filenames.sort()

        for dirname in dirnames:
            abs_subdir = os.path.join(current_dir, dirname)
            folder_name = _ensure_unique_name(db, current_user.id, parent_id, dirname)
            folder_record = models.File(
                user_id=current_user.id,
                name=folder_name,
                path=parent_id,
                is_folder=True,
                size="0KB",
                type="folder",
                physical_path=abs_subdir,
            )
            db.add(folder_record)
            db.flush()
            dir_to_id[abs_subdir] = str(folder_record.id)
            mounted_folders += 1

        for filename in filenames:
            if _is_ignored_system_file(filename):
                continue
            abs_file = os.path.join(current_dir, filename)
            if not os.path.isfile(abs_file):
                continue
            file_name = _ensure_unique_name(db, current_user.id, parent_id, filename)
            mime_type = mimetypes.guess_type(abs_file)[0] or "application/octet-stream"
            try:
                file_size = _format_size(os.path.getsize(abs_file))
            except OSError:
                file_size = "0B"
            file_record = models.File(
                user_id=current_user.id,
                name=file_name,
                path=parent_id,
                is_folder=False,
                size=file_size,
                type=mime_type,
                physical_path=abs_file,
            )
            db.add(file_record)
            mounted_files += 1

    db.commit()

    return _mounted_project_response(
        source_dir,
        mounted_root,
        mounted_folders=mounted_folders,
        mounted_files=mounted_files,
        message=f"Mounted {mounted_files} files from {source_dir}",
    )


@router.get("/files/project-suggestions")
def list_project_suggestions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    suggestions = []
    mounted_roots = (
        db.query(models.File)
        .filter(
            models.File.user_id == current_user.id,
            models.File.path == "root",
            models.File.is_folder.is_(True),
            models.File.physical_path.isnot(None),
        )
        .all()
    )
    mounted_by_path = {
        os.path.abspath(os.path.expanduser(root.physical_path)): root
        for root in mounted_roots
        if root.physical_path
    }
    for candidate in _project_suggestion_candidates():
        directory_path = os.path.abspath(
            os.path.expanduser(candidate["directory_path"])
        )
        if not os.path.isdir(directory_path):
            continue
        mounted_root = mounted_by_path.get(directory_path)
        profile = _scan_project_profile(directory_path, audit_detail="summary")
        candidate_context_hints = candidate.get("context_hints")
        if isinstance(candidate_context_hints, dict):
            scanned_context_hints = profile.get("context_hints")
            if not isinstance(scanned_context_hints, dict):
                scanned_context_hints = {}
            merged_context_hints = {
                **scanned_context_hints,
                **candidate_context_hints,
            }
            profile["context_hints"] = merged_context_hints
            schema = profile.get("schema")
            if isinstance(schema, dict):
                schema["context_hints"] = merged_context_hints
        suggestions.append(
            {
                **candidate,
                "directory_path": directory_path,
                "already_mounted": mounted_root is not None,
                "mounted_root_id": mounted_root.id if mounted_root else None,
                "profile": profile,
            }
        )
    suggested_paths = {item["directory_path"] for item in suggestions}
    for mounted_path, mounted_root in mounted_by_path.items():
        if mounted_path in suggested_paths or not os.path.isdir(mounted_path):
            continue
        suggestions.append(
            {
                "id": f"mounted-{mounted_root.id}",
                "name": mounted_root.name,
                "directory_path": mounted_path,
                "description": "Mounted project directory.",
                "recommended": False,
                "already_mounted": True,
                "mounted_root_id": mounted_root.id,
                "profile": _scan_project_profile(
                    mounted_path,
                    audit_detail="summary",
                ),
            }
        )
    return suggestions


@router.get("/files/project-context")
def read_project_context_profile(
    directory_path: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    _assert_project_context_access(
        db,
        user_id=current_user.id,
        directory_path=directory_path,
    )
    profile = _read_project_context_profile(directory_path)
    return {
        "exists": profile is not None,
        "filename": PROJECT_CONTEXT_FILENAME,
        "profile": profile,
    }


@router.put("/files/project-context")
def write_project_context_profile(
    body: models.ProjectContextProfileRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    _assert_project_context_access(
        db,
        user_id=current_user.id,
        directory_path=body.directory_path,
    )
    profile = _write_project_context_profile(body.directory_path, body.profile)
    return {
        "message": "Project context saved",
        "filename": PROJECT_CONTEXT_FILENAME,
        "profile": profile,
    }


@router.delete("/files/project-context")
def delete_project_context_profile(
    directory_path: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    _assert_project_context_access(
        db,
        user_id=current_user.id,
        directory_path=directory_path,
    )
    deleted = _delete_project_context_profile(directory_path)
    return {
        "message": (
            "Project context deleted" if deleted else "Project context not found"
        ),
        "filename": PROJECT_CONTEXT_FILENAME,
        "deleted": deleted,
    }


@router.put("/files/{file_id}", response_model=models.FileResponse)
def update_file(
    file_id: int,
    file_update: models.FileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    file = (
        db.query(models.File)
        .filter(models.File.id == file_id, models.File.user_id == current_user.id)
        .first()
    )
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Only update provided fields
    if file_update.name is not None:
        file.name = file_update.name
    if file_update.path is not None:
        file.path = file_update.path

    db.commit()
    db.refresh(file)
    return file


@router.delete("/files/unmount/{file_id}")
def unmount_project(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    folder = (
        db.query(models.File)
        .filter(
            models.File.id == file_id,
            models.File.user_id == current_user.id,
            models.File.is_folder.is_(True),
        )
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Project folder not found")

    # Mounted projects are represented by folder records that reference an external path.
    if not folder.physical_path or _is_managed_upload_path(
        current_user.id, folder.physical_path
    ):
        raise HTTPException(
            status_code=400, detail="This folder is not a mounted project"
        )

    _delete_file_tree(db, current_user.id, folder, delete_disk_files=False)
    db.commit()
    return {"message": "Project unmounted"}


@router.delete("/files/workspace")
def reset_workspace(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    root_nodes = (
        db.query(models.File)
        .filter(models.File.user_id == current_user.id, models.File.path == "root")
        .all()
    )
    total_rows = (
        db.query(models.File).filter(models.File.user_id == current_user.id).count()
    )
    mounted_root_count = 0

    for node in root_nodes:
        delete_disk_files = True
        if node.physical_path and not _is_managed_upload_path(
            current_user.id, node.physical_path
        ):
            mounted_root_count += 1
            delete_disk_files = False

        _delete_file_tree(
            db,
            current_user.id,
            node,
            delete_disk_files=delete_disk_files,
        )

    uploads_root = os.path.abspath(os.path.join("uploads", str(current_user.id)))
    if os.path.isdir(uploads_root):
        shutil.rmtree(uploads_root, ignore_errors=True)
    os.makedirs(uploads_root, exist_ok=True)

    db.commit()
    return {
        "message": "Workspace reset",
        "deleted_count": total_rows,
        "mounted_root_count": mounted_root_count,
    }


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    file = (
        db.query(models.File)
        .filter(models.File.id == file_id, models.File.user_id == current_user.id)
        .first()
    )
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete DB records recursively and only remove files from disk for app-managed uploads.
    _delete_file_tree(db, current_user.id, file, delete_disk_files=True)
    db.commit()
    return {"message": "File deleted"}
