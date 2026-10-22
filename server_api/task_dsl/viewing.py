"""Prepare fetched volumes for the app's Neuroglancer endpoint.

The viewer's segmentation layer needs a 3D volume of integer labels. Model
predictions are multi-channel probability maps, so they are converted here:
foreground channel, thresholded, then split into connected objects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


MIN_OBJECT_VOXELS = 20


def _first_dataset(handle):
    return handle[list(handle.keys())[0]]


def voxel_size(path: str) -> list[float]:
    """Voxel size (z, y, x) stored with the volume, or 1s when the file has none."""
    if not path.endswith((".h5", ".hdf5")):
        return [1.0, 1.0, 1.0]
    import h5py

    with h5py.File(path, "r") as handle:
        size = _first_dataset(handle).attrs.get("voxel_size_nm")
    return [float(v) for v in size] if size is not None and len(size) == 3 else [1.0, 1.0, 1.0]


def labels_for_viewer(path: str, threshold: float = 0.5) -> tuple[str, str]:
    """Return a path the viewer can show as segmentation, and a note if it was converted."""
    if not path.endswith((".h5", ".hdf5")):
        return path, ""
    import h5py
    from scipy import ndimage

    with h5py.File(path, "r") as handle:
        data = _first_dataset(handle)
        if data.ndim == 3 and (np.issubdtype(data.dtype, np.integer) or data.dtype == bool):
            return path, ""  # already a label volume
        volume = np.asarray(data)
    note_parts: list[str] = []
    if volume.ndim == 4:
        note_parts.append(f"The prediction has {volume.shape[0]} channels; showing channel 1 (foreground)")
        volume = volume[0]
    elif volume.ndim != 3:
        raise ValueError(f"Cannot show a volume with shape {volume.shape} as segmentation.")
    probability = volume.astype(np.float32)
    if probability.max() > 1.0:
        probability /= 255.0
    labels, count = ndimage.label(probability >= threshold)
    sizes = np.bincount(labels.ravel())
    specks = np.flatnonzero(sizes < MIN_OBJECT_VOXELS)
    specks = specks[specks > 0]
    if specks.size:  # undertrained models leave thousands of specks; hide them, and say so
        labels[np.isin(labels, specks)] = 0
        labels, count = ndimage.label(labels > 0)
    note_parts.append(f"voxels above {threshold:g} are split into {count} connected objects")
    if specks.size:
        note_parts.append(f"{specks.size} specks under {MIN_OBJECT_VOXELS} voxels are hidden")
    out = Path(path).with_name(Path(path).stem + "_labels.h5")
    with h5py.File(out, "w") as handle:
        handle.create_dataset("main", data=labels.astype(np.uint32), compression="gzip")
    note = ", ".join(note_parts) + "."
    return str(out), note[0].upper() + note[1:]


def prepare(local_paths: list[str]) -> dict[str, Any]:
    image = local_paths[0]
    result: dict[str, Any] = {"local_paths": [image], "scales": voxel_size(image), "view_note": ""}
    if len(local_paths) > 1:
        label, note = labels_for_viewer(local_paths[1])
        result["local_paths"].append(label)
        result["view_note"] = note
    return result
