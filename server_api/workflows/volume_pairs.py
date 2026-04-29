from __future__ import annotations

import pathlib
import re
from typing import Any, Dict, List, Optional, Tuple


NEUROGLANCER_VOLUME_FILE_SUFFIXES = (
    ".h5",
    ".hdf5",
    ".hdf",
    ".tif",
    ".tiff",
    ".ome.tif",
    ".ome.tiff",
    ".npy",
    ".npz",
    ".nii",
    ".nii.gz",
    ".mrc",
    ".map",
    ".rec",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
)
NEUROGLANCER_VOLUME_DIR_SUFFIXES = (".zarr", ".n5")


def _path_has_suffix(path: pathlib.Path, suffixes: tuple[str, ...]) -> bool:
    lower = path.name.lower()
    return any(lower.endswith(suffix) for suffix in suffixes)


def _is_neuroglancer_volume_file(path: pathlib.Path) -> bool:
    return path.is_file() and _path_has_suffix(path, NEUROGLANCER_VOLUME_FILE_SUFFIXES)


def _is_chunked_volume_directory(path: pathlib.Path) -> bool:
    return path.is_dir() and _path_has_suffix(path, NEUROGLANCER_VOLUME_DIR_SUFFIXES)


def _volume_pair_key(path: pathlib.Path) -> str:
    name = path.name.lower()
    for suffix in sorted(
        NEUROGLANCER_VOLUME_FILE_SUFFIXES + NEUROGLANCER_VOLUME_DIR_SUFFIXES,
        key=len,
        reverse=True,
    ):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    replacements = (
        ("image_", ""),
        ("images_", ""),
        ("img_", ""),
        ("raw_", ""),
        ("volume_", ""),
        ("vol_", ""),
        ("seg_", ""),
        ("label_", ""),
        ("labels_", ""),
        ("mask_", ""),
        ("masks_", ""),
        ("gt_", ""),
        ("ground_truth_", ""),
        ("_image", ""),
        ("_images", ""),
        ("_img", ""),
        ("_im", ""),
        ("_raw", ""),
        ("_volume", ""),
        ("_vol", ""),
        ("_seg", ""),
        ("_label", ""),
        ("_labels", ""),
        ("_mask", ""),
        ("_masks", ""),
        ("_gt", ""),
        ("_ground_truth", ""),
        ("-image", ""),
        ("-images", ""),
        ("-img", ""),
        ("-raw", ""),
        ("-volume", ""),
        ("-seg", ""),
        ("-label", ""),
        ("-labels", ""),
        ("-mask", ""),
    )
    for old, new in replacements:
        name = name.replace(old, new)
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def _volume_file_candidates(
    directory: pathlib.Path, *, max_candidates: int = 2000
) -> List[pathlib.Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    direct = [
        child
        for child in sorted(directory.iterdir(), key=lambda item: item.name.lower())
        if _is_neuroglancer_volume_file(child) or _is_chunked_volume_directory(child)
    ]
    if direct:
        return direct[:max_candidates]

    candidates: List[pathlib.Path] = []
    for child in sorted(directory.rglob("*"), key=lambda item: str(item).lower()):
        if _is_neuroglancer_volume_file(child) or _is_chunked_volume_directory(child):
            candidates.append(child)
            if len(candidates) >= max_candidates:
                break
    return candidates


def _as_volume_candidates(path: Optional[pathlib.Path]) -> List[pathlib.Path]:
    if path is None:
        return []
    if _is_chunked_volume_directory(path) or _is_neuroglancer_volume_file(path):
        return [path]
    if path.is_dir():
        return _volume_file_candidates(path)
    return []


def discover_neuroglancer_volume_pairs(
    image_path: pathlib.Path,
    label_path: Optional[pathlib.Path] = None,
    *,
    max_pairs: int = 50,
) -> Dict[str, Any]:
    image_candidates = _as_volume_candidates(image_path)
    label_candidates = _as_volume_candidates(label_path)
    label_by_key: Dict[str, List[pathlib.Path]] = {}
    for candidate in label_candidates:
        label_by_key.setdefault(_volume_pair_key(candidate), []).append(candidate)

    pairs: List[Dict[str, Any]] = []
    unpaired_images: List[str] = []
    used_labels: set[str] = set()
    for image_candidate in image_candidates:
        key = _volume_pair_key(image_candidate)
        label_candidate = None
        if key in label_by_key and label_by_key[key]:
            label_candidate = label_by_key[key].pop(0)
            used_labels.add(str(label_candidate))
        if label_candidate:
            pairs.append(
                {
                    "key": key,
                    "image_path": str(image_candidate),
                    "label_path": str(label_candidate),
                    "image_name": image_candidate.name,
                    "label_name": label_candidate.name,
                }
            )
        else:
            unpaired_images.append(str(image_candidate))
        if len(pairs) >= max_pairs:
            break

    if not pairs and len(image_candidates) == 1 and len(label_candidates) == 1:
        image_candidate = image_candidates[0]
        label_candidate = label_candidates[0]
        pairs.append(
            {
                "key": _volume_pair_key(image_candidate),
                "image_path": str(image_candidate),
                "label_path": str(label_candidate),
                "image_name": image_candidate.name,
                "label_name": label_candidate.name,
                "match_basis": "single-image-single-label",
            }
        )
        used_labels.add(str(label_candidate))

    unpaired_labels = [
        str(candidate)
        for candidate in label_candidates
        if str(candidate) not in used_labels
    ]
    return {
        "requested_image_path": str(image_path),
        "requested_label_path": str(label_path) if label_path else None,
        "image_is_directory": image_path.is_dir()
        and not _is_chunked_volume_directory(image_path),
        "label_is_directory": bool(label_path)
        and label_path.is_dir()
        and not _is_chunked_volume_directory(label_path),
        "image_candidate_count": len(image_candidates),
        "label_candidate_count": len(label_candidates),
        "pair_count": len(pairs),
        "pairs": pairs,
        "unpaired_images": unpaired_images[:10],
        "unpaired_labels": unpaired_labels[:10],
        "truncated": len(pairs) >= max_pairs,
    }


def _resolve_neuroglancer_image_path(
    image_path: pathlib.Path,
    label_path: Optional[pathlib.Path] = None,
) -> Tuple[pathlib.Path, Optional[str]]:
    if _is_chunked_volume_directory(image_path) or image_path.is_file():
        return image_path, None
    if not image_path.is_dir():
        return image_path, None

    discovery = discover_neuroglancer_volume_pairs(image_path, label_path)
    if discovery["pairs"]:
        selected = pathlib.Path(discovery["pairs"][0]["image_path"])
        return (
            selected,
            f"Selected matching image volume {selected.name} from folder {image_path}.",
        )

    image_candidates = _volume_file_candidates(image_path)
    if not image_candidates:
        raise ValueError(f"No readable image volume files found in {image_path}")

    return (
        image_candidates[0],
        f"Selected first readable image volume {image_candidates[0].name} from folder {image_path}.",
    )


def _resolve_neuroglancer_label_path(
    label_path: Optional[pathlib.Path],
    resolved_image_path: pathlib.Path,
) -> Tuple[Optional[pathlib.Path], Optional[str]]:
    if label_path is None:
        return None, None
    if _is_chunked_volume_directory(label_path) or label_path.is_file():
        return label_path, None
    if not label_path.is_dir():
        return label_path, None

    discovery = discover_neuroglancer_volume_pairs(resolved_image_path, label_path)
    if discovery["pairs"]:
        selected = pathlib.Path(discovery["pairs"][0]["label_path"])
        return (
            selected,
            f"Selected matching label volume {selected.name} from folder {label_path}.",
        )

    label_candidates = _volume_file_candidates(label_path)
    if not label_candidates:
        raise ValueError(f"No readable label volume files found in {label_path}")

    return (
        label_candidates[0],
        f"Selected first readable label volume {label_candidates[0].name} from folder {label_path}.",
    )
