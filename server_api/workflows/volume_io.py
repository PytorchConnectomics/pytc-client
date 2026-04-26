from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple, Union

import numpy as np

CropSpec = Union[str, Sequence[slice], None]

COMMON_DATASET_NAMES = (
    "data",
    "main",
    "volume",
    "vol",
    "raw",
    "image",
    "images",
    "label",
    "labels",
    "seg",
    "segmentation",
    "prediction",
    "predictions",
)

SUPPORTED_VOLUME_FORMATS = (
    "TIFF/OME-TIFF: .tif, .tiff, .ome.tif, .ome.tiff",
    "HDF5: .h5, .hdf5, .hdf",
    "NumPy: .npy, .npz",
    "Zarr/N5: .zarr, .n5",
    "Common 2D images: .png, .jpg, .jpeg, .bmp",
    "Optional NIfTI if nibabel is installed: .nii, .nii.gz",
    "Optional MRC if mrcfile is installed: .mrc, .map, .rec",
)


def split_dataset_ref(path: str) -> Tuple[str, Optional[str]]:
    if "::" not in path:
        return path, None
    file_path, dataset_key = path.split("::", 1)
    return file_path, dataset_key or None


def parse_crop(crop: CropSpec) -> Optional[Tuple[slice, ...]]:
    if crop is None:
        return None
    if isinstance(crop, (list, tuple)) and all(isinstance(item, slice) for item in crop):
        return tuple(crop)
    if not isinstance(crop, str):
        raise ValueError("crop must be a string like '0:16,0:256,0:256'")

    normalized = crop.strip().lower()
    if normalized in {"", "none", "full", ":"}:
        return None

    slices: List[slice] = []
    for part in normalized.split(","):
        token = part.strip()
        if not token:
            raise ValueError(f"Invalid empty crop token in {crop!r}")
        if ":" not in token:
            index = int(token)
            slices.append(slice(index, index + 1))
            continue
        pieces = token.split(":")
        if len(pieces) > 3:
            raise ValueError(f"Invalid crop token {token!r}")
        values = [int(piece) if piece else None for piece in pieces]
        while len(values) < 3:
            values.append(None)
        slices.append(slice(values[0], values[1], values[2]))
    return tuple(slices)


def _normalize_crop_for_shape(
    crop: Optional[Tuple[slice, ...]], shape: Sequence[int]
) -> Union[slice, Tuple[slice, ...]]:
    if crop is None:
        return slice(None)
    if len(crop) > len(shape):
        raise ValueError(f"Crop has {len(crop)} dimensions but array has {len(shape)}")
    return tuple(list(crop) + [slice(None)] * (len(shape) - len(crop)))


def _infer_channel_axis(
    shape: Sequence[int],
    *,
    channel: Optional[int],
    reference_ndim: Optional[int],
    label: str,
) -> Optional[int]:
    if channel is None:
        return None
    if channel < 0:
        raise ValueError(f"{label} channel must be non-negative")

    reference_ndim = reference_ndim or max(1, len(shape) - 1)
    if len(shape) == reference_ndim:
        raise ValueError(
            f"{label} volume is already {reference_ndim}D; "
            "do not pass a channel selector for this artifact."
        )
    if len(shape) != reference_ndim + 1:
        raise ValueError(
            f"{label} volume has shape {tuple(shape)}; expected "
            f"{reference_ndim}D or {reference_ndim + 1}D for channel selection."
        )

    if shape[0] > channel and shape[0] <= 16:
        return 0
    if shape[-1] > channel and shape[-1] <= 16:
        return len(shape) - 1
    if shape[0] > channel:
        return 0
    if shape[-1] > channel:
        return len(shape) - 1
    raise ValueError(
        f"{label} channel {channel} is out of bounds for volume shape {tuple(shape)}"
    )


def _normalize_crop_for_output(
    crop: Optional[Tuple[slice, ...]], output_ndim: int
) -> List[slice]:
    if crop is None:
        return [slice(None)] * output_ndim
    if len(crop) > output_ndim:
        raise ValueError(f"Crop has {len(crop)} dimensions but array has {output_ndim}")
    return list(crop) + [slice(None)] * (output_ndim - len(crop))


def _array_index(
    data: Any,
    crop: Optional[Tuple[slice, ...]] = None,
    *,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> Union[int, slice, Tuple[Any, ...]]:
    shape = getattr(data, "shape", ())
    if channel is None:
        return _normalize_crop_for_shape(crop, shape)

    channel_axis = _infer_channel_axis(
        shape,
        channel=channel,
        reference_ndim=reference_ndim,
        label=label,
    )
    output_ndim = len(shape) - 1
    crop_key = _normalize_crop_for_output(crop, output_ndim)
    key: List[Any] = []
    crop_index = 0
    for axis_index in range(len(shape)):
        if axis_index == channel_axis:
            key.append(channel)
            continue
        key.append(crop_key[crop_index])
        crop_index += 1
    return tuple(key)


def _as_array(
    data: Any,
    crop: Optional[Tuple[slice, ...]] = None,
    *,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> np.ndarray:
    if crop is None and channel is None:
        return np.asarray(data)
    key = _array_index(
        data,
        crop,
        channel=channel,
        reference_ndim=reference_ndim,
        label=label,
    )
    return np.asarray(data[key])


def _collect_h5_datasets(handle: Any) -> List[str]:
    import h5py

    datasets: List[str] = []

    def visitor(name: str, obj: Any) -> None:
        if isinstance(obj, h5py.Dataset):
            datasets.append(name)

    handle.visititems(visitor)
    return datasets


def _select_h5_dataset(handle: Any, dataset_key: Optional[str]) -> Any:
    import h5py

    if dataset_key:
        if dataset_key not in handle:
            raise ValueError(f"HDF5 dataset {dataset_key!r} not found")
        target = handle[dataset_key]
        if not isinstance(target, h5py.Dataset):
            raise ValueError(f"HDF5 path {dataset_key!r} is not a dataset")
        return target

    for name in COMMON_DATASET_NAMES:
        if name in handle and isinstance(handle[name], h5py.Dataset):
            return handle[name]

    datasets = _collect_h5_datasets(handle)
    if not datasets:
        raise ValueError("HDF5 file does not contain any datasets")
    return handle[datasets[0]]


def _read_hdf5(
    path: Path,
    dataset_key: Optional[str],
    crop: Optional[Tuple[slice, ...]],
    *,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> np.ndarray:
    import h5py

    with h5py.File(path, "r") as handle:
        dataset = _select_h5_dataset(handle, dataset_key)
        return _as_array(
            dataset,
            crop,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )


def _is_zarr_array(value: Any) -> bool:
    return hasattr(value, "shape") and hasattr(value, "dtype") and hasattr(value, "__getitem__")


def _collect_zarr_arrays(group: Any, prefix: str = "") -> List[str]:
    arrays: List[str] = []
    try:
        keys = list(group.keys())
    except Exception:
        return arrays
    for key in keys:
        child = group[key]
        child_path = f"{prefix}/{key}" if prefix else str(key)
        if _is_zarr_array(child):
            arrays.append(child_path)
        else:
            arrays.extend(_collect_zarr_arrays(child, child_path))
    return arrays


def _select_zarr_array(store: Any, dataset_key: Optional[str]) -> Any:
    if _is_zarr_array(store):
        if dataset_key:
            raise ValueError("Dataset key was provided, but Zarr path is already an array")
        return store

    if dataset_key:
        return store[dataset_key]

    for name in COMMON_DATASET_NAMES:
        try:
            child = store[name]
        except Exception:
            continue
        if _is_zarr_array(child):
            return child

    arrays = _collect_zarr_arrays(store)
    if not arrays:
        raise ValueError("Zarr/N5 store does not contain any arrays")
    return store[arrays[0]]


def _read_zarr(
    path: Path,
    dataset_key: Optional[str],
    crop: Optional[Tuple[slice, ...]],
    *,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> np.ndarray:
    import zarr

    store = zarr.open(str(path), mode="r")
    array = _select_zarr_array(store, dataset_key)
    return _as_array(
        array,
        crop,
        channel=channel,
        reference_ndim=reference_ndim,
        label=label,
    )


def _read_npz(
    path: Path,
    dataset_key: Optional[str],
    crop: Optional[Tuple[slice, ...]],
    *,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> np.ndarray:
    with np.load(path) as loaded:
        key = dataset_key
        if not key:
            for candidate in COMMON_DATASET_NAMES:
                if candidate in loaded:
                    key = candidate
                    break
        if not key:
            keys = list(loaded.keys())
            if not keys:
                raise ValueError("NPZ file does not contain any arrays")
            key = keys[0]
        return _as_array(
            loaded[key],
            crop,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )


def _read_nifti(
    path: Path,
    crop: Optional[Tuple[slice, ...]],
    *,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> np.ndarray:
    try:
        import nibabel as nib
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("nibabel is required to read NIfTI volumes") from exc

    image = nib.load(str(path))
    data = image.dataobj
    return _as_array(
        data,
        crop,
        channel=channel,
        reference_ndim=reference_ndim,
        label=label,
    )


def _read_mrc(
    path: Path,
    crop: Optional[Tuple[slice, ...]],
    *,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> np.ndarray:
    try:
        import mrcfile
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("mrcfile is required to read MRC/MAP volumes") from exc

    with mrcfile.open(str(path), permissive=True) as handle:
        return _as_array(
            handle.data,
            crop,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )


def load_volume(
    path: str,
    *,
    dataset_key: Optional[str] = None,
    crop: CropSpec = None,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> np.ndarray:
    file_path, inline_dataset_key = split_dataset_ref(str(path))
    dataset_key = dataset_key or inline_dataset_key
    target = Path(file_path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"Volume artifact does not exist: {target}")

    crop_slices = parse_crop(crop)
    lower_name = target.name.lower()
    lower_path = str(target).lower()

    if lower_name.endswith((".h5", ".hdf5", ".hdf")):
        return _read_hdf5(
            target,
            dataset_key,
            crop_slices,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )
    if lower_name.endswith((".tif", ".tiff", ".ome.tif", ".ome.tiff")):
        import tifffile

        return _as_array(
            tifffile.imread(str(target)),
            crop_slices,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )
    if lower_name.endswith(".npy"):
        return _as_array(
            np.load(target, mmap_mode="r"),
            crop_slices,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )
    if lower_name.endswith(".npz"):
        return _read_npz(
            target,
            dataset_key,
            crop_slices,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )
    if target.is_dir() or lower_name.endswith((".zarr", ".n5")):
        return _read_zarr(
            target,
            dataset_key,
            crop_slices,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )
    if lower_path.endswith((".nii", ".nii.gz")):
        return _read_nifti(
            target,
            crop_slices,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )
    if lower_name.endswith((".mrc", ".map", ".rec")):
        return _read_mrc(
            target,
            crop_slices,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )
    if lower_name.endswith((".png", ".jpg", ".jpeg", ".bmp")):
        import imageio.v3 as iio

        return _as_array(
            iio.imread(target),
            crop_slices,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )

    raise ValueError(
        f"Unsupported volume format for {target}. Supported formats: "
        + "; ".join(SUPPORTED_VOLUME_FORMATS)
    )
