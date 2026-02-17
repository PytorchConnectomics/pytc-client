"""
Data Manager for EHTool
Handles loading and processing image datasets for error detection workflow
"""

import os
import json
from datetime import datetime, timezone
import glob
import numpy as np
import tifffile
from PIL import Image
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
from scipy import ndimage
from collections import OrderedDict

from .utils import (
    to_uint8,
    ensure_grayscale_2d,
    enhance_contrast,
    array_to_base64,
    array_to_png_bytes,
    labels_to_rgba,
    mask_to_rgba,
    glasbey_color,
    load_image_file,
    get_image_dimensions,
)


class DataManager:
    """
    Manages image and mask data for error detection workflow
    Supports both 2D images and 3D TIFF stacks
    """

    def __init__(self):
        self.image_volume: Optional[np.ndarray] = None
        self.mask_volume: Optional[np.ndarray] = None
        self.mask_path: Optional[str] = None
        self.dataset_path: Optional[str] = None
        self.is_3d: bool = False
        self.total_layers: int = 0
        self.image_shape: Optional[Tuple[int, ...]] = None
        self.instance_mode: Optional[str] = None
        self.instance_volume: Optional[np.ndarray] = None
        self.instances: Optional[List[Dict[str, Any]]] = None
        self.instance_classification: Dict[int, str] = {}
        self.progress_path: Optional[str] = None
        self._slice_cache: "OrderedDict[int, Dict[str, Any]]" = OrderedDict()
        self._active_cache: "OrderedDict[Tuple[int, int], str]" = OrderedDict()
        self._raw_cache: "OrderedDict[int, str]" = OrderedDict()
        self._slice_cache_limit = 24
        self._active_cache_limit = 128

    def load_dataset(
        self, dataset_path: str, mask_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load image dataset and optional mask dataset"""
        # Discover and load images
        image_data = self._load_volume(dataset_path)

        # Load masks if provided
        mask_data = None
        if mask_path:
            mask_data = self._load_volume(mask_path)

            # Validate mask dimensions match image
            if image_data["num_slices"] != mask_data["num_slices"]:
                raise ValueError(
                    f"Mask layer count ({mask_data['num_slices']}) does not match "
                    f"image layer count ({image_data['num_slices']})"
                )

            # Validate 2D dimensions match
            img_shape = image_data["shape"]
            mask_shape = mask_data["shape"]
            if img_shape[-2:] != mask_shape[-2:]:
                raise ValueError(
                    f"Mask dimensions {mask_shape[-2:]} do not match "
                    f"image dimensions {img_shape[-2:]}"
                )

        # Store volume data
        self.image_volume = image_data["volume"]
        self.mask_volume = mask_data["volume"] if mask_data else None
        self.mask_path = mask_path
        self.dataset_path = dataset_path
        self.is_3d = image_data["is_3d"]
        self.total_layers = image_data["num_slices"]
        self.image_shape = image_data["shape"]
        self.instance_mode = None
        self.instance_volume = None
        self.instances = None
        self.instance_classification = {}
        self._slice_cache.clear()
        self._active_cache.clear()
        self._raw_cache.clear()
        self.progress_path = self._resolve_progress_path()

        return {
            "total_layers": self.total_layers,
            "is_3d": self.is_3d,
            "image_shape": self.image_shape,
            "has_masks": mask_data is not None,
        }

    def save_mask(self, layer_index: int, mask_base64: str) -> None:
        """Update mask for a specific layer and save to disk"""
        import base64
        from io import BytesIO

        if self.mask_volume is None:
            raise ValueError("No mask volume loaded")

        if layer_index < 0 or layer_index >= self.total_layers:
            raise IndexError(f"Layer index {layer_index} out of range")

        # Decode base64 to numpy array
        if "," in mask_base64:
            mask_base64 = mask_base64.split(",")[1]

        img_data = base64.b64decode(mask_base64)
        img = Image.open(BytesIO(img_data))

        # Convert to numpy array (grayscale)
        new_mask = np.array(img.convert("L"))

        # Ensure it matches expected dimensions
        expected_shape = (
            self.image_shape[-2:] if len(self.image_shape) >= 2 else self.image_shape
        )
        if new_mask.shape != expected_shape:
            # Resize if needed (nearest neighbor to preserve classes)
            img = img.resize(expected_shape[::-1], Image.NEAREST)
            new_mask = np.array(img.convert("L"))

        # Update in-memory volume
        if self.mask_volume.ndim == 3:
            self.mask_volume[layer_index] = new_mask
        else:
            self.mask_volume = new_mask

        # Save to disk
        if self.mask_path:
            self._save_volume(self.mask_path, self.mask_volume, layer_index)

    def _save_volume(self, path: str, volume: np.ndarray, layer_index: int = -1):
        """Save volume to disk"""
        path_obj = Path(path)

        if path_obj.is_file():
            # It's a single file (likely TIFF)
            if path.lower().endswith((".tif", ".tiff")):
                # Rewrite entire TIFF
                tifffile.imwrite(path, volume, compression="zlib")
            else:
                # Single 2D image file
                if volume.ndim == 2:
                    Image.fromarray(volume).save(path)

        elif path_obj.is_dir():
            # Directory of images
            for ext in ["*.tif", "*.tiff", "*.png", "*.jpg", "*.jpeg"]:
                files = sorted(
                    glob.glob(os.path.join(path, ext))
                    + glob.glob(os.path.join(path, ext.upper()))
                )
                if files:
                    if layer_index >= 0 and layer_index < len(files):
                        target_file = files[layer_index]
                        if volume.ndim == 3:
                            slice_data = volume[layer_index]
                        else:
                            slice_data = volume
                        Image.fromarray(slice_data).save(target_file)
                        return
                    else:
                        raise IndexError(
                            f"Layer index {layer_index} out of range for file list"
                        )

    def get_layer(
        self, layer_index: int, enhance: bool = True
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Get image and mask for a specific layer"""
        if layer_index < 0 or layer_index >= self.total_layers:
            raise IndexError(
                f"Layer index {layer_index} out of range [0, {self.total_layers})"
            )

        # Get image slice
        if self.image_volume.ndim == 3:
            image = self.image_volume[layer_index]
        else:
            image = self.image_volume

        image = ensure_grayscale_2d(image)

        if enhance:
            image = enhance_contrast(image)
        else:
            image = to_uint8(image)

        # Get mask slice if exists
        mask = None
        if self.mask_volume is not None:
            if self.mask_volume.ndim == 3:
                mask = self.mask_volume[layer_index]
            else:
                mask = self.mask_volume

            mask = ensure_grayscale_2d(mask)
            mask = to_uint8(mask)

        return image, mask

    def get_layer_base64(
        self, layer_index: int, enhance: bool = True
    ) -> Tuple[str, Optional[str]]:
        """Get image and mask as base64-encoded strings"""
        image, mask = self.get_layer(layer_index, enhance=enhance)

        image_base64 = array_to_base64(image, format="PNG")
        mask_base64 = array_to_base64(mask, format="PNG") if mask is not None else None

        return image_base64, mask_base64

    def get_layer_name(self, layer_index: int) -> str:
        """Get the name for a layer"""
        if layer_index < 0 or layer_index >= self.total_layers:
            return f"Layer {layer_index}"

        if self.is_3d:
            return f"Layer {layer_index + 1}"
        else:
            return "Image"

    def ensure_instances(self) -> None:
        """Compute instance metadata if not already available."""
        if self.instances is not None:
            return

        if self.mask_volume is None:
            self.instance_mode = "none"
            self.instance_volume = None
            self.instances = []
            self.instance_classification = {}
            return

        mask = self.mask_volume
        unique_vals = np.unique(mask)
        unique_nonzero = unique_vals[unique_vals != 0]

        # Heuristic: treat binary or near-binary as semantic.
        is_integer = np.issubdtype(mask.dtype, np.integer)
        is_binary = (
            len(unique_vals) <= 2
            and np.all(np.isin(unique_vals, np.array([0, 1, 255])))
        )

        if is_integer and (is_binary or len(unique_nonzero) <= 2):
            # Semantic mask, derive instances via connected components
            binary = mask > 0
            labeled, _ = ndimage.label(binary)
            self.instance_volume = labeled.astype(np.int32)
            self.instance_mode = "semantic"
        else:
            # Instance mask with labels
            self.instance_volume = mask.astype(np.int32)
            self.instance_mode = "instance"

        if self.instance_volume is None:
            self.instances = []
            self.instance_classification = {}
            return

        labels = np.unique(self.instance_volume)
        labels = labels[labels != 0]

        if labels.size == 0:
            self.instances = []
            self.instance_classification = {}
            return

        # Counts per label
        max_label = int(labels.max())
        counts = np.bincount(self.instance_volume.ravel(), minlength=max_label + 1)

        # Center of mass per label (z, y, x). For 2D, z is 0.
        label_indices = labels.tolist()
        coms = ndimage.center_of_mass(
            self.instance_volume > 0, labels=self.instance_volume, index=label_indices
        )

        instances: List[Dict[str, Any]] = []
        for idx, label in enumerate(label_indices):
            count = int(counts[label]) if label < len(counts) else 0
            com = coms[idx]
            if self.instance_volume.ndim == 2:
                com_z = 0
                com_y = int(round(com[0]))
                com_x = int(round(com[1]))
            else:
                com_z = int(round(com[0]))
                com_y = int(round(com[1]))
                com_x = int(round(com[2]))
            instances.append(
                {
                    "id": int(label),
                    "voxel_count": count,
                    "com_z": com_z,
                    "com_y": com_y,
                    "com_x": com_x,
                }
            )

        # Sort largest-first to surface meaningful instances
        instances.sort(key=lambda item: item["voxel_count"], reverse=True)
        self.instances = instances
        self.instance_classification = {inst["id"]: "error" for inst in instances}
        self._load_progress()

    def _resolve_progress_path(self) -> Optional[str]:
        base_path = self.mask_path or self.dataset_path
        if not base_path:
            return None
        if any(char in base_path for char in ["*", "?"]):
            root = Path(base_path).parent
        else:
            base = Path(base_path)
            root = base if base.is_dir() else base.parent
        if not root.exists():
            return None
        return str(root / ".pytc_proofreading.json")

    def _load_progress(self) -> None:
        if not self.progress_path or not os.path.exists(self.progress_path):
            return
        try:
            with open(self.progress_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return

        stored = payload.get("instances", {})
        if not isinstance(stored, dict):
            return

        valid = {"correct", "incorrect", "unsure", "error"}
        for inst in self.instances or []:
            key = str(inst["id"])
            entry = stored.get(key)
            if isinstance(entry, dict):
                entry = entry.get("classification")
            if isinstance(entry, str) and entry in valid:
                self.instance_classification[inst["id"]] = entry

    def save_progress(self) -> None:
        if not self.progress_path:
            return
        try:
            payload = {
                "schema_version": 1,
                "dataset_path": self.dataset_path,
                "mask_path": self.mask_path,
                "instance_mode": self.instance_mode,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "instances": {
                    str(inst_id): {
                        "classification": classification,
                    }
                    for inst_id, classification in self.instance_classification.items()
                },
            }
            with open(self.progress_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except Exception:
            # Non-fatal: failing to persist progress should not block proofreading.
            return

    def get_instance_slice(
        self, instance_id: int, z_index: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
        """Return image, full label slice, active instance mask slice, and z index."""
        if self.instance_volume is None:
            raise ValueError("Instance volume is not available")

        if self.instance_volume.ndim == 2:
            z_index = 0
            image = ensure_grayscale_2d(self.image_volume)
            image = enhance_contrast(image)
            label_slice = self.instance_volume
        else:
            if z_index is None:
                # Fallback to middle slice if not provided
                z_index = self.total_layers // 2
            z_index = max(0, min(int(z_index), self.total_layers - 1))
            image, _ = self.get_layer(z_index, enhance=True)
            label_slice = self.instance_volume[z_index]

        active_mask = (label_slice == instance_id).astype(np.uint8)
        return image, label_slice, active_mask, z_index

    def get_instance_slice_axis(
        self, instance_id: int, axis: str, index: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
        """Return image/mask slice for a given axis (xy, zx, zy)."""
        if self.instance_volume is None:
            raise ValueError("Instance volume is not available")

        axis = axis.lower()
        if self.instance_volume.ndim == 2:
            axis = "xy"
            index = 0

        if axis not in {"xy", "zx", "zy"}:
            raise ValueError(f"Unsupported axis: {axis}")

        if axis == "xy":
            z_index = 0 if index is None else int(index)
            z_index = max(0, min(z_index, self.total_layers - 1))
            image, _ = self.get_layer(z_index, enhance=True)
            label_slice = self.instance_volume[z_index]
            active_mask = (label_slice == instance_id).astype(np.uint8)
            return image, label_slice, active_mask, z_index, self.total_layers

        # For ZX and ZY, we swap axes for a view slice
        volume = self.image_volume
        label_volume = self.instance_volume
        if axis == "zx":
            # Slice across Y dimension
            max_index = volume.shape[1] - 1
            index = max_index // 2 if index is None else int(index)
            index = max(0, min(index, max_index))
            image_slice = volume[:, index, :]
            label_slice = label_volume[:, index, :]
            total = volume.shape[1]
        else:  # zy
            max_index = volume.shape[2] - 1
            index = max_index // 2 if index is None else int(index)
            index = max(0, min(index, max_index))
            image_slice = volume[:, :, index]
            label_slice = label_volume[:, :, index]
            total = volume.shape[2]

        image_slice = ensure_grayscale_2d(image_slice)
        image_slice = enhance_contrast(image_slice)
        label_slice = ensure_grayscale_2d(label_slice)
        label_slice = to_uint8(label_slice)
        active_mask = (label_slice == instance_id).astype(np.uint8)
        return image_slice, label_slice, active_mask, index, total

    def _resize_to_max_dim(
        self, array: np.ndarray, max_dim: Optional[int], is_mask: bool = False
    ) -> np.ndarray:
        if not max_dim or max_dim <= 0:
            return array

        height, width = array.shape[:2]
        largest = max(height, width)
        if largest <= max_dim:
            return array

        scale = max_dim / float(largest)
        new_w = max(1, int(round(width * scale)))
        new_h = max(1, int(round(height * scale)))
        resample = Image.NEAREST if is_mask else Image.BILINEAR
        img = Image.fromarray(array)
        resized = img.resize((new_w, new_h), resample=resample)
        return np.array(resized)

    def _cache_get(self, cache: OrderedDict, key):
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        return None

    def _cache_set(self, cache: OrderedDict, key, value, limit: int):
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > limit:
            cache.popitem(last=False)

    def get_instance_view_data(
        self,
        instance_id: int,
        z_index: Optional[int],
        include_raw_mask: bool,
        axis: str = "xy",
    ) -> Dict[str, Any]:
        """Get cached base64 view data for an instance slice."""
        image, label_slice, active_mask, resolved_z, total = (
            self.get_instance_slice_axis(
                instance_id=instance_id, axis=axis, index=z_index
            )
        )

        cached_slice = self._cache_get(self._slice_cache, (axis, resolved_z))
        if cached_slice:
            image_base64 = cached_slice["image_base64"]
            mask_all_base64 = cached_slice["mask_all_base64"]
        else:
            image_base64 = array_to_base64(image, format="PNG")
            mask_all_rgba = labels_to_rgba(label_slice)
            mask_all_base64 = array_to_base64(mask_all_rgba, format="PNG")
            self._cache_set(
                self._slice_cache,
                (axis, resolved_z),
                {
                    "image_base64": image_base64,
                    "mask_all_base64": mask_all_base64,
                },
                self._slice_cache_limit,
            )

        active_key = (instance_id, axis, resolved_z)
        active_cached = self._cache_get(self._active_cache, active_key)
        if active_cached:
            mask_active_base64 = active_cached
        else:
            active_color = glasbey_color(instance_id)
            mask_active_rgba = mask_to_rgba(active_mask, active_color)
            mask_active_base64 = array_to_base64(mask_active_rgba, format="PNG")
            self._cache_set(
                self._active_cache,
                active_key,
                mask_active_base64,
                self._active_cache_limit,
            )

        mask_raw_base64 = None
        if include_raw_mask and self.mask_volume is not None and axis == "xy":
            cached_raw = self._cache_get(self._raw_cache, resolved_z)
            if cached_raw:
                mask_raw_base64 = cached_raw
            else:
                _, mask_raw = self.get_layer(resolved_z, enhance=False)
                if mask_raw is not None:
                    mask_raw_base64 = array_to_base64(mask_raw, format="PNG")
                    self._cache_set(
                        self._raw_cache, resolved_z, mask_raw_base64, 12
                    )

        return {
            "image_base64": image_base64,
            "mask_all_base64": mask_all_base64,
            "mask_active_base64": mask_active_base64,
            "mask_raw_base64": mask_raw_base64,
            "z_index": resolved_z,
            "total": total,
            "axis": axis,
        }

    def get_instance_image_bytes(
        self,
        instance_id: int,
        z_index: Optional[int],
        axis: str,
        kind: str,
        max_dim: Optional[int] = None,
    ) -> Tuple[bytes, int, int, str]:
        """Return PNG bytes for an instance view component."""
        image, label_slice, active_mask, resolved_index, total = (
            self.get_instance_slice_axis(
                instance_id=instance_id, axis=axis, index=z_index
            )
        )

        kind = kind.lower()
        if kind == "image":
            array = image
            array = self._resize_to_max_dim(array, max_dim, is_mask=False)
        elif kind == "mask_all":
            array = labels_to_rgba(label_slice)
            array = self._resize_to_max_dim(array, max_dim, is_mask=True)
        elif kind == "mask_active":
            active_color = glasbey_color(instance_id)
            array = mask_to_rgba(active_mask, active_color)
            array = self._resize_to_max_dim(array, max_dim, is_mask=True)
        elif kind == "mask_raw":
            if axis != "xy":
                raise ValueError("Raw mask only supported for XY view")
            _, mask_raw = self.get_layer(resolved_index, enhance=False)
            if mask_raw is None:
                array = np.zeros_like(image)
            else:
                array = ensure_grayscale_2d(mask_raw)
            array = self._resize_to_max_dim(array, max_dim, is_mask=True)
        else:
            raise ValueError(f"Unsupported image kind: {kind}")

        return array_to_png_bytes(array), resolved_index, total, axis

    def get_sparse_active_mask(
        self,
        instance_id: int,
        z_index: Optional[int],
        axis: str,
    ) -> Dict[str, Any]:
        """Return a cropped active mask with bbox metadata."""
        _, label_slice, active_mask, resolved_index, total = (
            self.get_instance_slice_axis(
                instance_id=instance_id, axis=axis, index=z_index
            )
        )

        coords = np.argwhere(active_mask > 0)
        if coords.size == 0:
            bbox = [0, 0, 0, 0]
            crop = np.zeros((1, 1), dtype=np.uint8)
        else:
            min_y, min_x = coords.min(axis=0)
            max_y, max_x = coords.max(axis=0)
            bbox = [int(min_x), int(min_y), int(max_x), int(max_y)]
            crop = active_mask[min_y : max_y + 1, min_x : max_x + 1]

        return {
            "bbox": bbox,
            "mask_crop": to_uint8(crop),
            "width": int(label_slice.shape[1]),
            "height": int(label_slice.shape[0]),
            "z_index": resolved_index,
            "total": total,
            "axis": axis,
        }

    def _load_volume(self, path: str) -> Dict[str, Any]:
        """Load volume data from a path"""
        path_obj = Path(path)

        # Single file
        if path_obj.is_file():
            if path.lower().endswith((".tif", ".tiff")):
                volume = tifffile.imread(path)
                if volume.ndim == 2:
                    return {
                        "volume": volume,
                        "shape": volume.shape,
                        "num_slices": 1,
                        "is_3d": False,
                    }
                elif volume.ndim == 3:
                    return {
                        "volume": volume,
                        "shape": volume.shape,
                        "num_slices": volume.shape[0],
                        "is_3d": True,
                    }
                else:
                    raise ValueError(f"Unsupported TIFF dimensions: {volume.ndim}")
            else:
                image = load_image_file(path)
                return {
                    "volume": image,
                    "shape": image.shape,
                    "num_slices": 1,
                    "is_3d": False,
                }

        # Directory or glob pattern
        elif path_obj.is_dir() or "*" in path or "?" in path:
            files = []
            if path_obj.is_dir():
                for ext in ["*.tif", "*.tiff", "*.png", "*.jpg", "*.jpeg"]:
                    files.extend(glob.glob(os.path.join(path, ext)))
                    files.extend(glob.glob(os.path.join(path, ext.upper())))
            else:
                files = glob.glob(path)

            if not files:
                raise ValueError(f"No image files found at: {path}")

            files = sorted(files)
            slices = []
            for file_path in files:
                img = load_image_file(file_path)
                img = ensure_grayscale_2d(img)
                slices.append(img)

            volume = np.stack(slices, axis=0)
            return {
                "volume": volume,
                "shape": volume.shape,
                "num_slices": volume.shape[0],
                "is_3d": True,
            }

        else:
            raise ValueError(f"Invalid path: {path}")
