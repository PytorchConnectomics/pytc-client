"""
Data Manager for EHTool
Handles loading and processing image datasets for error detection workflow
"""

import os
import json
import time
import shutil
import tempfile
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
    array_to_image_bytes,
    labels_to_rgba,
    mask_to_rgba,
    glasbey_color,
    load_image_file,
    get_image_dimensions,
    base64_to_array,
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
        self.progress_payload: Optional[Dict[str, Any]] = None
        self.ui_state: Dict[str, Any] = {}
        self.project_name: Optional[str] = None
        self.progress_path: Optional[str] = None
        self._slice_cache: "OrderedDict[int, Dict[str, Any]]" = OrderedDict()
        self._active_cache: "OrderedDict[Tuple[int, int], str]" = OrderedDict()
        self._raw_cache: "OrderedDict[int, str]" = OrderedDict()
        self._resized_cache: "OrderedDict[Tuple[Any, ...], bytes]" = OrderedDict()
        self._resized_frame_cache: "OrderedDict[Tuple[Any, ...], np.ndarray]" = (
            OrderedDict()
        )
        self._filmstrip_cache: "OrderedDict[Tuple[Any, ...], bytes]" = OrderedDict()
        self._slice_cache_limit = 24
        self._active_cache_limit = 128
        self._resized_cache_limit = 128
        self._resized_frame_cache_limit = 192
        self._filmstrip_cache_limit = 64
        self._progress_schema_version = 3
        self._history_limit = 200
        self.instance_artifact_path: Optional[str] = None
        self.persistence_dirty: bool = False
        self.last_saved_at: Optional[str] = None
        self.last_export_at: Optional[str] = None
        self.last_persist_error: Optional[str] = None
        self.artifact_writable: bool = False
        self.last_export_mode: Optional[str] = None
        self.last_export_path: Optional[str] = None
        self.last_backup_path: Optional[str] = None
        self.mask_source_kind: str = "none"
        self.mask_source_files: List[str] = []

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
        self._resized_cache.clear()
        self._resized_frame_cache.clear()
        self._filmstrip_cache.clear()
        self.progress_path = self._resolve_progress_path()
        self.instance_artifact_path = self._resolve_instance_artifact_path()
        self.progress_payload = None
        self.ui_state = {}
        self.persistence_dirty = False
        self.last_saved_at = None
        self.last_export_at = None
        self.last_persist_error = None
        self.artifact_writable = self._is_path_writable(self.instance_artifact_path)
        self.last_export_mode = None
        self.last_export_path = None
        self.last_backup_path = None
        self.mask_source_kind, self.mask_source_files = self._resolve_source_layout(
            self.mask_path
        )

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

    def save_instance_mask_slice(
        self, instance_id: int, axis: str, index: int, mask_base64: str
    ) -> None:
        """Apply an edited binary mask to the active instance on a slice."""
        if self.instance_volume is None:
            raise ValueError("Instance volume is not available")
        if self.instance_mode != "instance":
            raise ValueError("Instance editing requires labeled masks")

        axis = axis.lower()
        if axis not in {"xy", "zx", "zy"}:
            raise ValueError(f"Unsupported axis: {axis}")

        if self.instance_volume.ndim == 2:
            axis = "xy"
            index = 0

        # Decode mask and binarize
        mask_arr = base64_to_array(mask_base64)
        mask_arr = ensure_grayscale_2d(mask_arr)
        binary = mask_arr > 0

        # Select target slice
        if axis == "xy":
            max_index = self.total_layers - 1
            index = max(0, min(int(index), max_index))
            slice_ref = (
                self.instance_volume
                if self.instance_volume.ndim == 2
                else self.instance_volume[index]
            )
        elif axis == "zx":
            max_index = self.instance_volume.shape[1] - 1
            index = max(0, min(int(index), max_index))
            slice_ref = self.instance_volume[:, index, :]
        else:  # zy
            max_index = self.instance_volume.shape[2] - 1
            index = max(0, min(int(index), max_index))
            slice_ref = self.instance_volume[:, :, index]

        # Resize to match slice shape if needed
        if binary.shape != slice_ref.shape:
            resized = Image.fromarray(binary.astype(np.uint8) * 255).resize(
                (slice_ref.shape[1], slice_ref.shape[0]), Image.NEAREST
            )
            binary = np.array(resized) > 0

        previous_labels = np.array(slice_ref, copy=True)
        old_active = previous_labels == instance_id
        # Keep edits safe by default: paint can grow/shrink the active instance,
        # but does not silently overwrite other labeled instances.
        writable = (previous_labels == 0) | old_active
        add_pixels = binary & writable & ~old_active
        remove_pixels = old_active & ~binary
        overwrite_blocked = binary & ~writable

        slice_ref[remove_pixels] = 0
        slice_ref[old_active | add_pixels] = instance_id

        # Keep mask_volume aligned with instance edits
        if self.mask_volume is not None:
            if axis == "xy":
                mask_slice = (
                    self.mask_volume
                    if self.mask_volume.ndim == 2
                    else self.mask_volume[index]
                )
            elif axis == "zx":
                mask_slice = self.mask_volume[:, index, :]
            else:
                mask_slice = self.mask_volume[:, :, index]
            if mask_slice.shape == binary.shape:
                previous_mask = np.array(mask_slice, copy=True)
                old_mask_active = previous_mask == instance_id
                writable_mask = (previous_mask == 0) | old_mask_active
                add_mask = binary & writable_mask & ~old_mask_active
                remove_mask = old_mask_active & ~binary
                mask_slice[remove_mask] = 0
                mask_slice[old_mask_active | add_mask] = instance_id

        # Update active instance stats without resetting classifications.
        self._update_instance_stats(instance_id)

        # Clear caches so overlays refresh
        self._slice_cache.clear()
        self._active_cache.clear()
        self._raw_cache.clear()
        self._resized_cache.clear()
        self._resized_frame_cache.clear()
        self._filmstrip_cache.clear()

        changed_pixels = int(
            np.count_nonzero(add_pixels) + np.count_nonzero(remove_pixels)
        )
        self.persistence_dirty = True
        self._persist_instance_artifact(force=True)
        blocked_pixels = int(np.count_nonzero(overwrite_blocked))
        self.save_progress(
            edit_event={
                "instance_id": int(instance_id),
                "axis": axis,
                "z_index": int(index),
                "pixels_added": int(np.count_nonzero(add_pixels)),
                "pixels_removed": int(np.count_nonzero(remove_pixels)),
                "pixels_changed": changed_pixels,
                "pixels_blocked": blocked_pixels,
            }
        )

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

    def _iso_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _is_path_writable(self, path: Optional[str]) -> bool:
        if not path:
            return False
        try:
            path_obj = Path(path)
            if path_obj.exists():
                return os.access(path_obj, os.W_OK)
            parent = path_obj.parent
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
            return os.access(parent, os.W_OK)
        except Exception:
            return False

    def _resolve_source_layout(self, path: Optional[str]) -> Tuple[str, List[str]]:
        if not path:
            return "none", []
        path_obj = Path(path)
        if path_obj.is_file():
            return "file", [str(path_obj)]
        if path_obj.is_dir():
            files: List[str] = []
            for ext in ["*.tif", "*.tiff", "*.png", "*.jpg", "*.jpeg"]:
                files.extend(glob.glob(os.path.join(path, ext)))
                files.extend(glob.glob(os.path.join(path, ext.upper())))
            files = sorted(set(files))
            return "directory", files
        if "*" in path or "?" in path:
            files = sorted(set(glob.glob(path)))
            return "glob", files
        return "none", []

    def _resolve_instance_artifact_path(self) -> Optional[str]:
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
        return str(root / ".pytc_instance_labels.tif")

    def _atomic_write_tiff(self, path: str, volume: np.ndarray) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".tmp.tif",
                dir=str(target.parent),
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)
            tifffile.imwrite(str(tmp_path), volume, compression="zlib")
            os.replace(str(tmp_path), str(target))
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def _atomic_write_image(self, path: str, array: np.ndarray) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = None
        image_array = np.asarray(array)
        if np.issubdtype(image_array.dtype, np.integer):
            max_value = int(image_array.max()) if image_array.size else 0
            if max_value <= 255:
                image_array = image_array.astype(np.uint8, copy=False)
            else:
                image_array = image_array.astype(np.uint16, copy=False)
        else:
            image_array = np.clip(image_array, 0, 255).astype(np.uint8)

        ext = target.suffix.lower()
        if ext in {".jpg", ".jpeg"}:
            image_array = np.clip(image_array, 0, 255).astype(np.uint8)
        try:
            with tempfile.NamedTemporaryFile(
                suffix=target.suffix or ".tmp",
                dir=str(target.parent),
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)
            Image.fromarray(image_array).save(str(tmp_path))
            os.replace(str(tmp_path), str(target))
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def _persist_instance_artifact(self, force: bool = False) -> None:
        if self.instance_volume is None or not self.instance_artifact_path:
            return
        if not force and not self.persistence_dirty:
            return

        try:
            self._atomic_write_tiff(
                self.instance_artifact_path, self.instance_volume.astype(np.int32)
            )
            self.last_saved_at = self._iso_now()
            self.last_persist_error = None
            self.persistence_dirty = False
        except Exception as exc:
            self.last_persist_error = str(exc)
        finally:
            self.artifact_writable = self._is_path_writable(self.instance_artifact_path)

    def _load_instance_artifact_if_available(self) -> None:
        if self.instance_volume is None or not self.instance_artifact_path:
            return
        if not os.path.exists(self.instance_artifact_path):
            return

        try:
            loaded = tifffile.imread(self.instance_artifact_path)
            if loaded.shape != self.instance_volume.shape:
                self.last_persist_error = (
                    f"Ignored artifact with mismatched shape {loaded.shape}; "
                    f"expected {self.instance_volume.shape}"
                )
                return
            self.instance_volume = loaded.astype(np.int32, copy=False)
            if self.mask_volume is not None and self.mask_volume.shape == loaded.shape:
                self.mask_volume = loaded.astype(self.mask_volume.dtype, copy=False)
            saved_at = datetime.fromtimestamp(
                os.path.getmtime(self.instance_artifact_path), tz=timezone.utc
            )
            self.last_saved_at = saved_at.isoformat()
            self.last_persist_error = None
            self.persistence_dirty = False
        except Exception as exc:
            self.last_persist_error = f"Failed to load artifact: {exc}"

    def _backup_file(self, source_path: str, timestamp: str) -> str:
        source = Path(source_path)
        backup = source.with_name(
            f"{source.stem}.backup.{timestamp}{source.suffix or '.bak'}"
        )
        shutil.copy2(str(source), str(backup))
        return str(backup)

    def _backup_file_set(self, files: List[str], timestamp: str) -> str:
        if not files:
            raise ValueError("No source files available for backup")
        first = Path(files[0])
        backup_root = first.parent / ".pytc_backups" / timestamp
        backup_root.mkdir(parents=True, exist_ok=True)
        for idx, file_path in enumerate(files):
            src = Path(file_path)
            dest = backup_root / f"{idx:05d}_{src.name}"
            shutil.copy2(str(src), str(dest))
        return str(backup_root)

    def _write_volume_to_files(self, files: List[str], volume: np.ndarray) -> None:
        if not files:
            raise ValueError("No target files available for overwrite")
        if volume.ndim == 2:
            if len(files) != 1:
                raise ValueError("2D mask overwrite expects a single target file")
            target = files[0]
            if target.lower().endswith((".tif", ".tiff")):
                self._atomic_write_tiff(target, volume)
            else:
                self._atomic_write_image(target, volume)
            return

        if len(files) != volume.shape[0]:
            raise ValueError(
                f"Slice count mismatch: source has {len(files)} files, "
                f"edited volume has {volume.shape[0]} slices"
            )

        for idx, target in enumerate(files):
            slice_data = volume[idx]
            if target.lower().endswith((".tif", ".tiff")):
                self._atomic_write_tiff(target, slice_data)
            else:
                self._atomic_write_image(target, slice_data)

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
        is_binary = len(unique_vals) <= 2 and np.all(
            np.isin(unique_vals, np.array([0, 1, 255]))
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

        # Use persisted edited labels when available and shape-compatible.
        self._load_instance_artifact_if_available()

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
        self.progress_payload = payload if isinstance(payload, dict) else None
        if isinstance(payload, dict):
            ui_state = payload.get("ui_state")
            self.ui_state = ui_state if isinstance(ui_state, dict) else {}
        else:
            self.ui_state = {}

        artifact = payload.get("artifact") if isinstance(payload, dict) else None
        if isinstance(artifact, dict):
            artifact_path = artifact.get("path")
            if (
                isinstance(artifact_path, str)
                and artifact_path
                and not self.instance_artifact_path
            ):
                self.instance_artifact_path = artifact_path
            self.persistence_dirty = bool(artifact.get("dirty", False))
            self.last_saved_at = (
                artifact.get("last_saved_at")
                if isinstance(artifact.get("last_saved_at"), str)
                else self.last_saved_at
            )
            self.last_export_at = (
                artifact.get("last_export_at")
                if isinstance(artifact.get("last_export_at"), str)
                else self.last_export_at
            )
            self.last_persist_error = (
                artifact.get("last_error")
                if isinstance(artifact.get("last_error"), str)
                else self.last_persist_error
            )
            self.last_export_mode = (
                artifact.get("last_export_mode")
                if isinstance(artifact.get("last_export_mode"), str)
                else self.last_export_mode
            )
            self.last_export_path = (
                artifact.get("last_export_path")
                if isinstance(artifact.get("last_export_path"), str)
                else self.last_export_path
            )
            self.last_backup_path = (
                artifact.get("last_backup_path")
                if isinstance(artifact.get("last_backup_path"), str)
                else self.last_backup_path
            )
        self.artifact_writable = self._is_path_writable(self.instance_artifact_path)

        stored = payload.get("instances", {}) if isinstance(payload, dict) else {}
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

    def _build_review_stats(self) -> Dict[str, Any]:
        counts = {"correct": 0, "incorrect": 0, "unsure": 0, "error": 0}
        for value in self.instance_classification.values():
            if value in counts:
                counts[value] += 1
            else:
                counts["error"] += 1
        total = len(self.instance_classification)
        reviewed = max(0, total - counts["error"])
        progress = (reviewed / total) if total > 0 else 0.0
        return {
            "total_instances": total,
            "reviewed_instances": reviewed,
            "progress": round(progress, 6),
            "counts": counts,
        }

    def get_persistence_status(self) -> Dict[str, Any]:
        artifact_exists = bool(
            self.instance_artifact_path and os.path.exists(self.instance_artifact_path)
        )
        writable = self._is_path_writable(self.instance_artifact_path)
        self.artifact_writable = writable
        return {
            "enabled": bool(self.instance_artifact_path),
            "artifact_path": self.instance_artifact_path,
            "artifact_exists": artifact_exists,
            "dirty": bool(self.persistence_dirty),
            "writable": bool(writable),
            "last_saved_at": self.last_saved_at,
            "last_error": self.last_persist_error,
            "last_export_at": self.last_export_at,
            "last_export_mode": self.last_export_mode,
            "last_export_path": self.last_export_path,
            "last_backup_path": self.last_backup_path,
        }

    def _append_history(self, entry: Dict[str, Any], item: Dict[str, Any]) -> None:
        history = entry.get("history")
        if not isinstance(history, list):
            history = []
        history.append(item)
        if len(history) > self._history_limit:
            history = history[-self._history_limit :]
        entry["history"] = history

    def _update_instance_stats(self, instance_id: int) -> None:
        if self.instance_volume is None or not self.instances:
            return
        target = None
        for inst in self.instances:
            if int(inst.get("id", -1)) == int(instance_id):
                target = inst
                break
        if target is None:
            return
        coords = np.argwhere(self.instance_volume == int(instance_id))
        target["voxel_count"] = int(coords.shape[0])
        if coords.shape[0] == 0:
            target["com_z"] = 0
            target["com_y"] = 0
            target["com_x"] = 0
            return
        if self.instance_volume.ndim == 2:
            target["com_z"] = 0
            target["com_y"] = int(np.rint(np.mean(coords[:, 0])))
            target["com_x"] = int(np.rint(np.mean(coords[:, 1])))
        else:
            target["com_z"] = int(np.rint(np.mean(coords[:, 0])))
            target["com_y"] = int(np.rint(np.mean(coords[:, 1])))
            target["com_x"] = int(np.rint(np.mean(coords[:, 2])))

    def save_progress(
        self,
        ui_state: Optional[Dict[str, Any]] = None,
        edit_event: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.progress_path:
            return
        try:
            payload = (
                self.progress_payload if isinstance(self.progress_payload, dict) else {}
            )
            payload["schema_version"] = self._progress_schema_version
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()

            project = payload.get("project")
            if not isinstance(project, dict):
                project = {}
            project["name"] = (
                self.project_name or project.get("name") or "Untitled Project"
            )
            project["dataset_path"] = self.dataset_path
            project["mask_path"] = self.mask_path
            project["instance_mode"] = self.instance_mode
            payload["project"] = project

            payload["review"] = self._build_review_stats()

            if isinstance(ui_state, dict):
                stored_ui = payload.get("ui_state")
                if not isinstance(stored_ui, dict):
                    stored_ui = {}
                stored_ui.update(ui_state)
                payload["ui_state"] = stored_ui
                self.ui_state = stored_ui

            instances_payload = payload.get("instances")
            if not isinstance(instances_payload, dict):
                instances_payload = {}

            for inst_id, classification in self.instance_classification.items():
                key = str(inst_id)
                entry = instances_payload.get(key)
                if not isinstance(entry, dict):
                    entry = {}
                previous_classification = entry.get("classification", "error")
                entry["classification"] = classification
                now_iso = datetime.now(timezone.utc).isoformat()
                if previous_classification != classification:
                    entry["reviewed_at"] = now_iso
                    self._append_history(
                        entry,
                        {
                            "at": now_iso,
                            "by": "local",
                            "type": "classification",
                            "action": classification,
                        },
                    )
                else:
                    entry["reviewed_at"] = entry.get("reviewed_at")
                entry.setdefault("notes", "")

                metadata = entry.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                matching_instance = None
                if self.instances:
                    matching_instance = next(
                        (
                            inst
                            for inst in self.instances
                            if int(inst.get("id", -1)) == int(inst_id)
                        ),
                        None,
                    )
                if matching_instance:
                    metadata["voxel_count"] = int(
                        matching_instance.get("voxel_count", 0)
                    )
                    metadata["com_z"] = int(matching_instance.get("com_z", 0))
                    metadata["com_y"] = int(matching_instance.get("com_y", 0))
                    metadata["com_x"] = int(matching_instance.get("com_x", 0))
                entry["metadata"] = metadata
                instances_payload[key] = entry

            if isinstance(edit_event, dict):
                inst_id = edit_event.get("instance_id")
                if inst_id is not None:
                    key = str(int(inst_id))
                    entry = instances_payload.get(key)
                    if not isinstance(entry, dict):
                        entry = {"classification": "error", "notes": ""}
                    edits = entry.get("edits")
                    if not isinstance(edits, dict):
                        edits = {}
                    edits["last_edit_at"] = datetime.now(timezone.utc).isoformat()
                    edits["count"] = int(edits.get("count", 0)) + 1
                    edits["pixels_added"] = int(edits.get("pixels_added", 0)) + int(
                        edit_event.get("pixels_added", 0)
                    )
                    edits["pixels_removed"] = int(edits.get("pixels_removed", 0)) + int(
                        edit_event.get("pixels_removed", 0)
                    )
                    edits["pixels_changed"] = int(edits.get("pixels_changed", 0)) + int(
                        edit_event.get("pixels_changed", 0)
                    )
                    edits["pixels_blocked"] = int(edits.get("pixels_blocked", 0)) + int(
                        edit_event.get("pixels_blocked", 0)
                    )
                    by_axis = edits.get("by_axis")
                    if not isinstance(by_axis, dict):
                        by_axis = {}
                    axis_key = str(edit_event.get("axis") or "xy").lower()
                    by_axis[axis_key] = int(by_axis.get(axis_key, 0)) + int(
                        edit_event.get("pixels_changed", 0)
                    )
                    edits["by_axis"] = by_axis
                    entry["edits"] = edits
                    self._append_history(
                        entry,
                        {
                            "at": edits["last_edit_at"],
                            "by": "local",
                            "type": "mask_edit",
                            "axis": axis_key,
                            "z_index": int(edit_event.get("z_index", 0)),
                            "pixels_added": int(edit_event.get("pixels_added", 0)),
                            "pixels_removed": int(edit_event.get("pixels_removed", 0)),
                            "pixels_changed": int(edit_event.get("pixels_changed", 0)),
                            "pixels_blocked": int(edit_event.get("pixels_blocked", 0)),
                        },
                    )
                    instances_payload[key] = entry

            payload["instances"] = instances_payload
            payload.setdefault("extensions", {})
            payload["artifact"] = self.get_persistence_status()

            with open(self.progress_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            self.progress_payload = payload
        except Exception:
            # Non-fatal: failing to persist progress should not block proofreading.
            return

    def export_masks(
        self,
        mode: str,
        output_path: Optional[str] = None,
        create_backup: bool = True,
    ) -> Dict[str, Any]:
        if self.instance_volume is None:
            raise ValueError("No instance volume available for export")

        mode_value = (mode or "").strip().lower()
        if mode_value not in {"new_file", "overwrite_source"}:
            raise ValueError("mode must be 'new_file' or 'overwrite_source'")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = None
        written_path = None

        if mode_value == "new_file":
            if not output_path:
                raise ValueError("output_path is required for mode='new_file'")
            target = Path(output_path).expanduser()
            if target.exists() and target.is_dir():
                target = target / "edited_instance_labels.tif"
            if target.suffix.lower() not in {".tif", ".tiff"}:
                target = target.with_suffix(".tif")
            if target.exists() and create_backup:
                backup_path = self._backup_file(str(target), timestamp)
            self._atomic_write_tiff(str(target), self.instance_volume.astype(np.int32))
            written_path = str(target)
        else:
            if not self.mask_path:
                raise ValueError("No source mask path available for overwrite")

            # Overwrite is always protected by backup in v1.
            create_backup = True
            source_kind, source_files = self._resolve_source_layout(self.mask_path)
            if source_kind == "none" or not source_files:
                raise ValueError("Unable to resolve source mask files for overwrite")

            if source_kind == "file":
                source_file = source_files[0]
                if create_backup:
                    backup_path = self._backup_file(source_file, timestamp)
                if source_file.lower().endswith((".tif", ".tiff")):
                    self._atomic_write_tiff(
                        source_file, self.instance_volume.astype(np.int32)
                    )
                else:
                    if self.instance_volume.ndim == 3:
                        if self.instance_volume.shape[0] != 1:
                            raise ValueError(
                                "Cannot overwrite multi-slice volume into a single 2D source image"
                            )
                        slice_data = self.instance_volume[0]
                    else:
                        slice_data = self.instance_volume
                    self._atomic_write_image(source_file, slice_data)
                written_path = source_file
            else:
                if create_backup:
                    backup_path = self._backup_file_set(source_files, timestamp)
                self._write_volume_to_files(source_files, self.instance_volume)
                written_path = self.mask_path

        self.last_export_at = self._iso_now()
        self.last_export_mode = mode_value
        self.last_export_path = written_path
        self.last_backup_path = backup_path
        self.last_persist_error = None
        self.save_progress()

        return {
            "message": "Masks exported successfully",
            "written_path": written_path,
            "backup_path": backup_path,
            "timestamp": self.last_export_at,
        }

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

    def _normalize_output_format(self, kind: str, format: str) -> Tuple[str, str]:
        requested = (format or "png").lower()
        if requested not in {"png", "webp"}:
            raise ValueError(f"Unsupported format: {format}")

        if kind != "image":
            requested = "png"

        media_type = "image/webp" if requested == "webp" else "image/png"
        return requested, media_type

    def get_instance_view_data(
        self,
        instance_id: int,
        z_index: Optional[int],
        include_raw_mask: bool,
        axis: str = "xy",
    ) -> Dict[str, Any]:
        """Get cached base64 view data for an instance slice."""
        (
            image,
            label_slice,
            active_mask,
            resolved_z,
            total,
        ) = self.get_instance_slice_axis(
            instance_id=instance_id, axis=axis, index=z_index
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
                    self._cache_set(self._raw_cache, resolved_z, mask_raw_base64, 12)

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
        quality: str = "full",
        format: str = "png",
    ) -> Tuple[bytes, int, int, str, str, Dict[str, Any]]:
        """Return encoded image bytes for an instance view component."""
        quality = (quality or "full").lower()
        if quality not in {"full", "preview"}:
            raise ValueError(f"Unsupported quality: {quality}")
        (
            image,
            label_slice,
            active_mask,
            resolved_index,
            total,
        ) = self.get_instance_slice_axis(
            instance_id=instance_id, axis=axis, index=z_index
        )

        kind = kind.lower()
        output_format, media_type = self._normalize_output_format(kind, format)
        resize_ms = 0.0
        max_dim_value = int(max_dim) if max_dim is not None else None
        if quality == "preview" and (not max_dim_value or max_dim_value <= 0):
            max_dim_value = 384
        if max_dim_value and max_dim_value > 0:
            cache_key = (
                instance_id,
                axis,
                resolved_index,
                kind,
                max_dim_value,
                quality,
                output_format,
            )
            cached = self._cache_get(self._resized_cache, cache_key)
            if cached:
                return (
                    cached,
                    resolved_index,
                    total,
                    axis,
                    media_type,
                    {"cache_hit": True, "decode_ms": 0.0, "resize_ms": 0.0},
                )
        resize_started = time.perf_counter()
        if kind == "image":
            array = image
            array = self._resize_to_max_dim(array, max_dim_value, is_mask=False)
        elif kind == "mask_all":
            array = labels_to_rgba(label_slice)
            array = self._resize_to_max_dim(array, max_dim_value, is_mask=True)
        elif kind == "mask_active":
            active_color = glasbey_color(instance_id)
            array = mask_to_rgba(active_mask, active_color)
            array = self._resize_to_max_dim(array, max_dim_value, is_mask=True)
        elif kind == "mask_active_binary":
            array = to_uint8(active_mask * 255)
            array = self._resize_to_max_dim(array, max_dim_value, is_mask=True)
        elif kind == "mask_raw":
            if axis != "xy":
                raise ValueError("Raw mask only supported for XY view")
            _, mask_raw = self.get_layer(resolved_index, enhance=False)
            if mask_raw is None:
                array = np.zeros_like(image)
            else:
                array = ensure_grayscale_2d(mask_raw)
            array = self._resize_to_max_dim(array, max_dim_value, is_mask=True)
        else:
            raise ValueError(f"Unsupported image kind: {kind}")
        if max_dim_value and max_dim_value > 0:
            resize_ms = (time.perf_counter() - resize_started) * 1000.0

        encoded_bytes = array_to_image_bytes(array, format=output_format)
        if max_dim_value and max_dim_value > 0:
            self._cache_set(
                self._resized_cache,
                (
                    instance_id,
                    axis,
                    resolved_index,
                    kind,
                    max_dim_value,
                    quality,
                    output_format,
                ),
                encoded_bytes,
                self._resized_cache_limit,
            )
        return (
            encoded_bytes,
            resolved_index,
            total,
            axis,
            media_type,
            {"cache_hit": False, "decode_ms": 0.0, "resize_ms": resize_ms},
        )

    def get_instance_filmstrip_bytes(
        self,
        instance_id: int,
        axis: str,
        z_start: int,
        z_count: int,
        kind: str,
        max_dim: Optional[int] = None,
        quality: str = "preview",
        format: str = "png",
    ) -> Tuple[bytes, int, int, int, str, int, str, Dict[str, Any]]:
        """Return stacked filmstrip bytes for a contiguous z-range."""
        if self.instance_volume is None:
            raise ValueError("Instance volume is not available")

        axis = axis.lower()
        if axis not in {"xy", "zx", "zy"}:
            raise ValueError(f"Unsupported axis: {axis}")

        kind = kind.lower()
        output_format, media_type = self._normalize_output_format(kind, format)
        quality = (quality or "preview").lower()
        if quality not in {"full", "preview"}:
            raise ValueError(f"Unsupported quality: {quality}")

        if self.instance_volume.ndim == 2:
            total = 1
            axis = "xy"
        elif axis == "xy":
            total = self.total_layers
        elif axis == "zx":
            total = int(self.image_volume.shape[1])
        else:
            total = int(self.image_volume.shape[2])

        if z_count is None:
            z_count = 1
        z_count = max(1, int(z_count))
        z_start = max(0, min(int(z_start), max(total - 1, 0)))
        z_count = min(z_count, total - z_start)
        if z_count <= 0:
            raise ValueError("No slices available for requested filmstrip range")

        max_dim_value = int(max_dim) if max_dim is not None else None
        if quality == "preview" and (not max_dim_value or max_dim_value <= 0):
            max_dim_value = 384
        cache_key = (
            instance_id,
            axis,
            z_start,
            z_count,
            kind,
            max_dim_value,
            quality,
            output_format,
        )
        cached = self._cache_get(self._filmstrip_cache, cache_key)
        if cached:
            if isinstance(cached, tuple):
                cached_bytes, cached_height = cached
            else:
                cached_bytes, cached_height = cached, int(max_dim_value or 0)
            return (
                cached_bytes,
                z_start,
                z_count,
                total,
                axis,
                cached_height,
                media_type,
                {"cache_hit": True, "decode_ms": 0.0, "resize_ms": 0.0},
            )

        resize_started = time.perf_counter()
        slices: List[np.ndarray] = []
        for offset in range(z_count):
            z_index = z_start + offset
            frame_cache_key = (
                instance_id,
                axis,
                z_index,
                kind,
                max_dim_value or 0,
                quality,
            )
            frame = (
                self._cache_get(self._resized_frame_cache, frame_cache_key)
                if max_dim_value and max_dim_value > 0
                else None
            )
            if frame is None:
                image, label_slice, active_mask, _, _ = self.get_instance_slice_axis(
                    instance_id=instance_id, axis=axis, index=z_index
                )

                if kind == "image":
                    frame = image
                    frame = self._resize_to_max_dim(frame, max_dim_value, is_mask=False)
                elif kind == "mask_all":
                    frame = labels_to_rgba(label_slice)
                    frame = self._resize_to_max_dim(frame, max_dim_value, is_mask=True)
                elif kind == "mask_active":
                    active_color = glasbey_color(instance_id)
                    frame = mask_to_rgba(active_mask, active_color)
                    frame = self._resize_to_max_dim(frame, max_dim_value, is_mask=True)
                elif kind == "mask_active_binary":
                    frame = to_uint8(active_mask * 255)
                    frame = self._resize_to_max_dim(frame, max_dim_value, is_mask=True)
                elif kind == "mask_raw":
                    if axis != "xy":
                        raise ValueError("Raw mask only supported for XY view")
                    _, raw_mask = self.get_layer(z_index, enhance=False)
                    frame = (
                        np.zeros_like(image)
                        if raw_mask is None
                        else ensure_grayscale_2d(raw_mask)
                    )
                    frame = self._resize_to_max_dim(frame, max_dim_value, is_mask=True)
                else:
                    raise ValueError(f"Unsupported image kind: {kind}")

                if max_dim_value and max_dim_value > 0:
                    self._cache_set(
                        self._resized_frame_cache,
                        frame_cache_key,
                        frame,
                        self._resized_frame_cache_limit,
                    )

            slices.append(frame)

        if not slices:
            raise ValueError("No slices generated for filmstrip")
        resize_ms = (time.perf_counter() - resize_started) * 1000.0

        frame_height = int(slices[0].shape[0]) if slices else 0
        filmstrip = np.concatenate(slices, axis=0)
        encoded_bytes = array_to_image_bytes(filmstrip, format=output_format)
        self._cache_set(
            self._filmstrip_cache,
            cache_key,
            (encoded_bytes, frame_height),
            self._filmstrip_cache_limit,
        )
        return (
            encoded_bytes,
            z_start,
            z_count,
            total,
            axis,
            frame_height,
            media_type,
            {"cache_hit": False, "decode_ms": 0.0, "resize_ms": resize_ms},
        )

    def get_sparse_active_mask(
        self,
        instance_id: int,
        z_index: Optional[int],
        axis: str,
    ) -> Dict[str, Any]:
        """Return a cropped active mask with bbox metadata."""
        (
            _,
            label_slice,
            active_mask,
            resolved_index,
            total,
        ) = self.get_instance_slice_axis(
            instance_id=instance_id, axis=axis, index=z_index
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
