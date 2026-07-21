import numpy as np
import pytest

from server_api.main import (
    _NeuroglancerSegmentationStore,
    _build_neuroglancer_local_volume_source,
    _open_neuroglancer_volume_sources,
)
from server_api.workflows.volume_io import ArrayVolumeStore


class RecordingLabelArray:
    shape = (8, 16, 24)
    dtype = np.dtype(np.int32)
    chunks = (2, 4, 6)

    def __init__(self, fill_value=7):
        self.fill_value = fill_value
        self.requested_keys = []

    def __array__(self, *_args, **_kwargs):
        raise AssertionError("full label volume was materialized")

    def __getitem__(self, key):
        self.requested_keys.append(key)
        return np.full((2, 4, 6), self.fill_value, dtype=self.dtype)


def test_segmentation_source_validates_and_converts_only_requested_chunk(tmp_path):
    backing = RecordingLabelArray()
    store = ArrayVolumeStore(
        backing,
        path=tmp_path / "labels.zarr",
        format="zarr",
    )
    source = _NeuroglancerSegmentationStore(store)

    chunk = source[1:3, 4:8, 6:12]

    assert source.shape == backing.shape
    assert source.dtype == np.dtype(np.uint64)
    assert chunk.dtype == np.uint64
    assert backing.requested_keys == [(slice(1, 3), slice(4, 8), slice(6, 12))]


def test_segmentation_source_rejects_negative_labels_per_chunk(tmp_path):
    store = ArrayVolumeStore(
        RecordingLabelArray(fill_value=-1),
        path=tmp_path / "negative-labels.zarr",
        format="zarr",
    )
    source = _NeuroglancerSegmentationStore(store)

    with pytest.raises(ValueError, match="non-negative"):
        source[0:2, 0:4, 0:6]


def test_segmentation_source_requires_preprocessed_3d_labels(tmp_path):
    store = ArrayVolumeStore(
        np.zeros((2, 8, 16, 24), dtype=np.float32),
        path=tmp_path / "prediction.zarr",
        format="zarr",
    )

    with pytest.raises(ValueError, match="requires a 3D label volume"):
        _NeuroglancerSegmentationStore(store)


def test_neuroglancer_local_volume_reads_hdf5_subvolumes_on_demand(tmp_path):
    h5py = pytest.importorskip("h5py")
    neuroglancer = pytest.importorskip("neuroglancer")
    image_path = tmp_path / "image.h5"
    label_path = tmp_path / "labels.h5"
    with h5py.File(image_path, "w") as handle:
        handle.create_dataset(
            "data",
            data=np.arange(8 * 16 * 24, dtype=np.uint8).reshape(8, 16, 24),
            chunks=(2, 4, 6),
        )
    with h5py.File(label_path, "w") as handle:
        handle.create_dataset(
            "data",
            data=np.ones((8, 16, 24), dtype=np.int32),
            chunks=(2, 4, 6),
        )

    image, labels, resources = _open_neuroglancer_volume_sources(image_path, label_path)
    try:
        dimensions = neuroglancer.CoordinateSpace(
            names=["z", "y", "x"], units=["nm", "nm", "nm"], scales=[1, 1, 1]
        )
        image_volume = _build_neuroglancer_local_volume_source(
            neuroglancer, image, dimensions, volume_type="image"
        )
        label_volume = _build_neuroglancer_local_volume_source(
            neuroglancer, labels, dimensions, volume_type="segmentation"
        )
        start = np.array([1, 2, 3], dtype=np.int64)
        end = np.array([3, 6, 9], dtype=np.int64)

        image_payload, image_content_type = image_volume.get_encoded_subvolume(
            "raw", start, end, "1,1,1"
        )
        label_payload, label_content_type = label_volume.get_encoded_subvolume(
            "raw", start, end, "1,1,1"
        )

        assert image_payload
        assert label_payload
        assert image_content_type == "application/octet-stream"
        assert label_content_type == "application/octet-stream"
    finally:
        for resource in resources:
            resource.close()
