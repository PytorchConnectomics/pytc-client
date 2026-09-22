from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

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


@dataclass(frozen=True)
class VolumeAxis:
    """A named array axis in canonical multiscale order."""

    name: str
    type: Optional[str] = None
    unit: Optional[str] = None


@dataclass(frozen=True)
class VolumeLevel:
    """Storage and coordinate metadata for one pyramid level."""

    index: int
    dataset_key: Optional[str]
    shape: Tuple[int, ...]
    dtype: np.dtype
    chunks: Optional[Tuple[int, ...]] = None
    scale: Tuple[float, ...] = ()
    translation: Tuple[float, ...] = ()


@dataclass(frozen=True)
class VolumeMetadata:
    """Storage-level metadata available without materializing voxel data."""

    path: str
    format: str
    shape: Tuple[int, ...]
    dtype: np.dtype
    dataset_key: Optional[str] = None
    chunks: Optional[Tuple[int, ...]] = None
    axes: Tuple[VolumeAxis, ...] = ()
    levels: Tuple[VolumeLevel, ...] = ()
    selected_level: int = 0
    multiscale_version: Optional[str] = None

    @property
    def ndim(self) -> int:
        return len(self.shape)


class VolumeStore(ABC):
    """A bounded region-reader for a single array inside a volume artifact."""

    @property
    @abstractmethod
    def metadata(self) -> VolumeMetadata:
        raise NotImplementedError

    @property
    def shape(self) -> Tuple[int, ...]:
        return self.metadata.shape

    @property
    def dtype(self) -> np.dtype:
        return self.metadata.dtype

    @property
    def ndim(self) -> int:
        return self.metadata.ndim

    @abstractmethod
    def read(
        self,
        crop: CropSpec = None,
        *,
        channel: Optional[int] = None,
        reference_ndim: Optional[int] = None,
        label: str = "volume",
    ) -> np.ndarray:
        raise NotImplementedError

    def close(self) -> None:
        """Release resources held by the backing artifact."""

    def __enter__(self) -> "VolumeStore":
        return self

    def __exit__(self, *_exc_info: Any) -> None:
        self.close()


class ArrayVolumeStore(VolumeStore):
    """VolumeStore adapter for array-like objects supporting basic indexing."""

    def __init__(
        self,
        data: Any,
        *,
        path: Path,
        format: str,
        dataset_key: Optional[str] = None,
        close: Optional[Callable[[], None]] = None,
        axes: Sequence[VolumeAxis] = (),
        levels: Sequence[VolumeLevel] = (),
        selected_level: int = 0,
        multiscale_version: Optional[str] = None,
    ) -> None:
        self._data = data
        self._close = close
        self._closed = False
        chunks = getattr(data, "chunks", None)
        shape = tuple(int(value) for value in data.shape)
        dtype = np.dtype(data.dtype)
        normalized_chunks = (
            tuple(int(value) for value in chunks)
            if chunks is not None and all(value is not None for value in chunks)
            else None
        )
        normalized_levels = tuple(levels) or (
            VolumeLevel(
                index=0,
                dataset_key=dataset_key,
                shape=shape,
                dtype=dtype,
                chunks=normalized_chunks,
                scale=tuple(1.0 for _ in shape),
                translation=tuple(0.0 for _ in shape),
            ),
        )
        self._metadata = VolumeMetadata(
            path=str(path),
            format=format,
            shape=shape,
            dtype=dtype,
            dataset_key=dataset_key,
            chunks=normalized_chunks,
            axes=tuple(axes),
            levels=normalized_levels,
            selected_level=selected_level,
            multiscale_version=multiscale_version,
        )

    @property
    def metadata(self) -> VolumeMetadata:
        return self._metadata

    def read(
        self,
        crop: CropSpec = None,
        *,
        channel: Optional[int] = None,
        reference_ndim: Optional[int] = None,
        label: str = "volume",
    ) -> np.ndarray:
        if self._closed:
            raise RuntimeError("Volume store is closed")
        return _as_array(
            self._data,
            parse_crop(crop),
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )

    def __getitem__(self, key: Any) -> Any:
        """Expose storage-backed slicing to consumers such as Neuroglancer."""
        if self._closed:
            raise RuntimeError("Volume store is closed")
        return self._data[key]

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._close is not None:
            self._close()


def split_dataset_ref(path: str) -> Tuple[str, Optional[str]]:
    if "::" not in path:
        return path, None
    file_path, dataset_key = path.split("::", 1)
    return file_path, dataset_key or None


def parse_crop(crop: CropSpec) -> Optional[Tuple[slice, ...]]:
    if crop is None:
        return None
    if isinstance(crop, (list, tuple)) and all(
        isinstance(item, slice) for item in crop
    ):
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


def _is_zarr_array(value: Any) -> bool:
    return (
        hasattr(value, "shape")
        and hasattr(value, "dtype")
        and hasattr(value, "__getitem__")
    )


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
            raise ValueError(
                "Dataset key was provided, but Zarr path is already an array"
            )
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


def _normalized_chunks(data: Any) -> Optional[Tuple[int, ...]]:
    chunks = getattr(data, "chunks", None)
    if chunks is None or not all(value is not None for value in chunks):
        return None
    return tuple(int(value) for value in chunks)


def _zarr_attrs(value: Any) -> dict:
    attrs = getattr(value, "attrs", None)
    if attrs is None:
        return {}
    try:
        return dict(attrs)
    except Exception:
        asdict = getattr(attrs, "asdict", None)
        return dict(asdict()) if callable(asdict) else {}


def _ngff_multiscales(group: Any) -> Tuple[Optional[List[Any]], Optional[str]]:
    """Return NGFF multiscales for both 0.4 and 0.5 metadata layouts."""

    attrs = _zarr_attrs(group)
    multiscales = attrs.get("multiscales")
    version: Optional[str] = None
    if multiscales is None:
        ome = attrs.get("ome")
        if isinstance(ome, dict):
            multiscales = ome.get("multiscales")
            if ome.get("version") is not None:
                version = str(ome["version"])
    if multiscales is None:
        return None, version
    if not isinstance(multiscales, list) or not multiscales:
        raise ValueError("NGFF multiscales metadata must be a non-empty list")
    return multiscales, version


def _parse_ngff_axes(raw_axes: Any) -> Tuple[VolumeAxis, ...]:
    if raw_axes is None:
        return ()
    if not isinstance(raw_axes, list):
        raise ValueError("NGFF axes metadata must be a list")
    axes: List[VolumeAxis] = []
    for axis in raw_axes:
        if isinstance(axis, str):
            axes.append(VolumeAxis(name=axis))
            continue
        if not isinstance(axis, dict) or not axis.get("name"):
            raise ValueError("Each NGFF axis must be a name or an object with a name")
        axes.append(
            VolumeAxis(
                name=str(axis["name"]),
                type=str(axis["type"]) if axis.get("type") is not None else None,
                unit=str(axis["unit"]) if axis.get("unit") is not None else None,
            )
        )
    return tuple(axes)


def _parse_ngff_transform(
    transforms: Any, ndim: int, *, dataset_path: str
) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    scale = [1.0] * ndim
    translation = [0.0] * ndim
    if transforms is None:
        transforms = []
    if not isinstance(transforms, list):
        raise ValueError(
            f"NGFF coordinateTransformations for {dataset_path!r} must be a list"
        )
    for transform in transforms:
        if not isinstance(transform, dict):
            raise ValueError(f"Invalid NGFF transform for {dataset_path!r}")
        transform_type = transform.get("type")
        if transform_type not in {"scale", "translation"}:
            raise ValueError(
                f"Unsupported NGFF transform {transform_type!r} for {dataset_path!r}"
            )
        values = transform.get(transform_type)
        if not isinstance(values, (list, tuple)) or len(values) != ndim:
            raise ValueError(
                f"NGFF {transform_type} for {dataset_path!r} must have {ndim} values"
            )
        vector = [float(value) for value in values]
        if transform_type == "scale":
            scale = [current * value for current, value in zip(scale, vector)]
            translation = [
                current * value for current, value in zip(translation, vector)
            ]
        else:
            translation = [
                current + value for current, value in zip(translation, vector)
            ]
    return tuple(scale), tuple(translation)


def _open_ngff_level(
    group: Any, *, level: Optional[int]
) -> Optional[
    Tuple[Any, Tuple[VolumeAxis, ...], Tuple[VolumeLevel, ...], int, Optional[str]]
]:
    multiscales, container_version = _ngff_multiscales(group)
    if multiscales is None:
        return None

    multiscale = multiscales[0]
    if not isinstance(multiscale, dict):
        raise ValueError("NGFF multiscales entries must be objects")
    datasets = multiscale.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("NGFF multiscale datasets must be a non-empty list")
    axes = _parse_ngff_axes(multiscale.get("axes"))
    selected_level = 0 if level is None else level
    if isinstance(selected_level, bool) or not isinstance(selected_level, int):
        raise ValueError("Pyramid level must be an integer")
    if selected_level < 0 or selected_level >= len(datasets):
        raise ValueError(
            f"Pyramid level {selected_level} is out of range; "
            f"available levels are 0..{len(datasets) - 1}"
        )

    parsed_levels: List[VolumeLevel] = []
    arrays: List[Any] = []
    for index, dataset in enumerate(datasets):
        if not isinstance(dataset, dict) or not dataset.get("path"):
            raise ValueError("Each NGFF dataset must provide a non-empty path")
        dataset_path = str(dataset["path"])
        try:
            data = group[dataset_path]
        except Exception as exc:
            raise ValueError(f"NGFF dataset {dataset_path!r} was not found") from exc
        if not _is_zarr_array(data):
            raise ValueError(f"NGFF dataset {dataset_path!r} is not an array")
        shape = tuple(int(value) for value in data.shape)
        if axes and len(axes) != len(shape):
            raise ValueError(
                f"NGFF axes has {len(axes)} entries but {dataset_path!r} is {len(shape)}D"
            )
        dataset_transforms = dataset.get("coordinateTransformations") or []
        multiscale_transforms = multiscale.get("coordinateTransformations") or []
        if not isinstance(dataset_transforms, list) or not isinstance(
            multiscale_transforms, list
        ):
            raise ValueError("NGFF coordinateTransformations must be lists")
        scale, translation = _parse_ngff_transform(
            dataset_transforms + multiscale_transforms,
            len(shape),
            dataset_path=dataset_path,
        )
        arrays.append(data)
        parsed_levels.append(
            VolumeLevel(
                index=index,
                dataset_key=getattr(data, "path", None) or dataset_path,
                shape=shape,
                dtype=np.dtype(data.dtype),
                chunks=_normalized_chunks(data),
                scale=scale,
                translation=translation,
            )
        )
    version = multiscale.get("version") or container_version
    return (
        arrays[selected_level],
        axes,
        tuple(parsed_levels),
        selected_level,
        str(version) if version is not None else None,
    )


def _validate_single_level(level: Optional[int]) -> None:
    if level not in (None, 0):
        raise ValueError("This artifact has only pyramid level 0")


def _close_all(*resources: Any) -> Callable[[], None]:
    def close() -> None:
        first_error: Optional[Exception] = None
        for resource in resources:
            close_resource = getattr(resource, "close", None)
            if not callable(close_resource):
                continue
            try:
                close_resource()
            except Exception as exc:  # pragma: no cover - defensive cleanup
                first_error = first_error or exc
        if first_error is not None:
            raise first_error

    return close


def _select_npz_array(loaded: Any, dataset_key: Optional[str]) -> Tuple[str, Any]:
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
    if key not in loaded:
        raise ValueError(f"NPZ array {key!r} not found")
    return key, loaded[key]


def open_volume_store(
    path: str,
    *,
    dataset_key: Optional[str] = None,
    level: Optional[int] = None,
) -> VolumeStore:
    """Open a volume for metadata inspection and bounded region reads.

    Callers should use this as a context manager. HDF5, NPY, Zarr/N5, NIfTI,
    MRC, and TIFF expose their backing array directly; indexing therefore occurs
    before NumPy materialization. Formats without random-access support retain an
    eager compatibility fallback.
    """

    file_path, inline_dataset_key = split_dataset_ref(str(path))
    dataset_key = dataset_key or inline_dataset_key
    target = Path(file_path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"Volume artifact does not exist: {target}")

    lower_name = target.name.lower()
    lower_path = str(target).lower()

    if lower_name.endswith((".h5", ".hdf5", ".hdf")):
        _validate_single_level(level)
        import h5py

        handle = h5py.File(target, "r")
        try:
            data = _select_h5_dataset(handle, dataset_key)
            selected_key = data.name.lstrip("/")
            return ArrayVolumeStore(
                data,
                path=target,
                format="hdf5",
                dataset_key=selected_key,
                close=handle.close,
            )
        except Exception:
            handle.close()
            raise

    if lower_name.endswith((".tif", ".tiff", ".ome.tif", ".ome.tiff")):
        import tifffile
        import zarr

        handle = tifffile.TiffFile(str(target))
        try:
            series = handle.series[0]
            pyramid = tuple(getattr(series, "levels", ()) or (series,))
            selected_level = 0 if level is None else level
            if (
                isinstance(selected_level, bool)
                or not isinstance(selected_level, int)
                or selected_level < 0
                or selected_level >= len(pyramid)
            ):
                raise ValueError(
                    f"Pyramid level {selected_level} is out of range; "
                    f"available levels are 0..{len(pyramid) - 1}"
                )
            selected_series = pyramid[selected_level]
            try:
                # Opening through the base series with an explicit level avoids
                # receiving a multiscale Zarr group for level 0.
                tiff_store = series.aszarr(level=selected_level)
            except TypeError:  # pragma: no cover - older tifffile compatibility
                tiff_store = selected_series.aszarr()
            data = zarr.open(tiff_store, mode="r")
            if not _is_zarr_array(data):
                try:
                    data = data[str(selected_level)]
                except Exception:
                    data = _select_zarr_array(data, None)
            base_shape = tuple(int(value) for value in pyramid[0].shape)
            levels: List[VolumeLevel] = []
            for index, pyramid_series in enumerate(pyramid):
                shape = tuple(int(value) for value in pyramid_series.shape)
                scale = tuple(
                    float(base) / float(current)
                    for base, current in zip(base_shape, shape)
                )
                levels.append(
                    VolumeLevel(
                        index=index,
                        dataset_key=None if index == 0 else f"level/{index}",
                        shape=shape,
                        dtype=np.dtype(pyramid_series.dtype),
                        chunks=(
                            _normalized_chunks(data)
                            if index == selected_level
                            else None
                        ),
                        scale=scale,
                        translation=tuple(0.0 for _ in shape),
                    )
                )
            axis_names = str(getattr(series, "axes", ""))
            axes = tuple(VolumeAxis(name=name.lower()) for name in axis_names)
            return ArrayVolumeStore(
                data,
                path=target,
                format="ome-tiff" if ".ome.tif" in lower_name else "tiff",
                dataset_key=(
                    None if selected_level == 0 else f"level/{selected_level}"
                ),
                close=_close_all(tiff_store, handle),
                axes=axes,
                levels=levels,
                selected_level=selected_level,
            )
        except ValueError:
            handle.close()
            raise
        except Exception:
            handle.close()
            _validate_single_level(level)
            return ArrayVolumeStore(
                tifffile.imread(str(target)),
                path=target,
                format="ome-tiff" if ".ome.tif" in lower_name else "tiff",
            )

    if lower_name.endswith(".npy"):
        _validate_single_level(level)
        data = np.load(target, mmap_mode="r")
        mmap = getattr(data, "_mmap", None)
        return ArrayVolumeStore(
            data,
            path=target,
            format="npy",
            close=getattr(mmap, "close", None),
        )

    if lower_name.endswith(".npz"):
        _validate_single_level(level)
        loaded = np.load(target)
        try:
            selected_key, data = _select_npz_array(loaded, dataset_key)
            return ArrayVolumeStore(
                data,
                path=target,
                format="npz",
                dataset_key=selected_key,
                close=loaded.close,
            )
        except Exception:
            loaded.close()
            raise

    if target.is_dir() or lower_name.endswith((".zarr", ".n5")):
        import zarr

        root = zarr.open(str(target), mode="r")
        candidate = root
        if dataset_key and not _is_zarr_array(root):
            try:
                candidate = root[dataset_key]
            except Exception as exc:
                raise ValueError(f"Zarr/N5 path {dataset_key!r} not found") from exc

        ngff = (
            None
            if _is_zarr_array(candidate)
            else _open_ngff_level(candidate, level=level)
        )
        if ngff is not None:
            data, axes, levels, selected_level, version = ngff
            selected_key = (
                getattr(data, "path", None) or levels[selected_level].dataset_key
            )
            return ArrayVolumeStore(
                data,
                path=target,
                format="n5" if lower_name.endswith(".n5") else "zarr",
                dataset_key=selected_key,
                axes=axes,
                levels=levels,
                selected_level=selected_level,
                multiscale_version=version,
            )

        _validate_single_level(level)
        data = (
            candidate
            if _is_zarr_array(candidate)
            else _select_zarr_array(candidate, None)
        )
        selected_key = dataset_key or getattr(data, "path", None) or None
        return ArrayVolumeStore(
            data,
            path=target,
            format="n5" if lower_name.endswith(".n5") else "zarr",
            dataset_key=selected_key,
        )

    if lower_path.endswith((".nii", ".nii.gz")):
        _validate_single_level(level)
        try:
            import nibabel as nib
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("nibabel is required to read NIfTI volumes") from exc
        image = nib.load(str(target))
        return ArrayVolumeStore(
            image.dataobj,
            path=target,
            format="nifti",
            close=getattr(image, "uncache", None),
        )

    if lower_name.endswith((".mrc", ".map", ".rec")):
        _validate_single_level(level)
        try:
            import mrcfile
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("mrcfile is required to read MRC/MAP volumes") from exc
        handle = mrcfile.open(str(target), permissive=True)
        return ArrayVolumeStore(
            handle.data,
            path=target,
            format="mrc",
            close=handle.close,
        )

    if lower_name.endswith((".png", ".jpg", ".jpeg", ".bmp")):
        _validate_single_level(level)
        import imageio.v3 as iio

        return ArrayVolumeStore(
            iio.imread(target),
            path=target,
            format=target.suffix.lower().lstrip("."),
        )

    raise ValueError(
        f"Unsupported volume format for {target}. Supported formats: "
        + "; ".join(SUPPORTED_VOLUME_FORMATS)
    )


def load_volume(
    path: str,
    *,
    dataset_key: Optional[str] = None,
    level: Optional[int] = None,
    crop: CropSpec = None,
    channel: Optional[int] = None,
    reference_ndim: Optional[int] = None,
    label: str = "volume",
) -> np.ndarray:
    with open_volume_store(path, dataset_key=dataset_key, level=level) as store:
        return store.read(
            crop,
            channel=channel,
            reference_ndim=reference_ndim,
            label=label,
        )
