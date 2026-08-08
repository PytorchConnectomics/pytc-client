import numpy as np
import pytest

from server_api.main import (
    _NeuroglancerSegmentationStore,
    _build_neuroglancer_local_volume_source,
    _open_neuroglancer_volume_sources,
    _resolve_neuroglancer_local_volume_policy,
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


class FakeDimensions:
    def __init__(self, scales):
        self.scales = np.asarray(scales, dtype=np.float64)


class RecordingLocalVolume:
    calls = []

    def __init__(self, data, **kwargs):
        self.data = data
        self.kwargs = kwargs
        self.__class__.calls.append((data, kwargs))


class RecordingNeuroglancer:
    LocalVolume = RecordingLocalVolume


class LegacyLocalVolume:
    calls = []

    def __init__(self, data, *, dimensions, volume_type, voxel_offset):
        self.data = data
        self.dimensions = dimensions
        self.volume_type = volume_type
        self.voxel_offset = voxel_offset
        self.__class__.calls.append(
            {
                "data": data,
                "dimensions": dimensions,
                "volume_type": volume_type,
                "voxel_offset": voxel_offset,
            }
        )


class LegacyNeuroglancer:
    LocalVolume = LegacyLocalVolume


@pytest.fixture(autouse=True)
def clear_recording_local_volume_calls():
    RecordingLocalVolume.calls.clear()
    LegacyLocalVolume.calls.clear()


def test_neuroglancer_policy_uses_2d_downsampling_for_anisotropic_data():
    policy = _resolve_neuroglancer_local_volume_policy(
        np.zeros((8, 16, 24), dtype=np.uint8),
        FakeDimensions([40, 8, 8]),
    )

    assert policy == {
        "downsampling": "2d",
        "chunk_layout": "flat",
        "max_voxels_per_chunk_log2": 18,
        "max_downsampling": 64,
        "max_downsampled_size": 128,
        "max_downsampling_scales": 8,
    }


def test_neuroglancer_policy_uses_3d_downsampling_for_isotropic_data():
    policy = _resolve_neuroglancer_local_volume_policy(
        np.zeros((8, 16, 24), dtype=np.uint8),
        FakeDimensions([8, 8, 8]),
    )

    assert policy["downsampling"] == "3d"
    assert policy["chunk_layout"] == "isotropic"


def test_neuroglancer_local_volume_policy_is_consistent_for_image_and_labels():
    dimensions = FakeDimensions([40, 8, 8])
    image = np.zeros((8, 16, 24), dtype=np.uint8)
    labels = np.zeros((8, 16, 24), dtype=np.uint64)

    _build_neuroglancer_local_volume_source(
        RecordingNeuroglancer, image, dimensions, volume_type="image"
    )
    _build_neuroglancer_local_volume_source(
        RecordingNeuroglancer, labels, dimensions, volume_type="segmentation"
    )

    image_kwargs = RecordingLocalVolume.calls[0][1]
    label_kwargs = RecordingLocalVolume.calls[1][1]
    adaptive_keys = {
        "downsampling",
        "chunk_layout",
        "max_voxels_per_chunk_log2",
        "max_downsampling",
        "max_downsampled_size",
        "max_downsampling_scales",
    }
    assert {key: image_kwargs[key] for key in adaptive_keys} == {
        key: label_kwargs[key] for key in adaptive_keys
    }
    assert image_kwargs["volume_type"] == "image"
    assert label_kwargs["volume_type"] == "segmentation"
    assert image_kwargs["max_voxels_per_chunk_log2"] == 18
    assert image_kwargs["max_downsampling"] == 64
    assert image_kwargs["max_downsampled_size"] == 128
    assert image_kwargs["max_downsampling_scales"] == 8


def test_neuroglancer_local_volume_retries_without_adaptive_options_for_legacy_api():
    data = np.zeros((8, 16, 24), dtype=np.uint8)
    dimensions = FakeDimensions([40, 8, 8])

    volume = _build_neuroglancer_local_volume_source(
        LegacyNeuroglancer,
        data,
        dimensions,
        volume_type="image",
        voxel_offset=(1, 2, 3),
    )

    assert volume.data is data
    assert LegacyLocalVolume.calls == [
        {
            "data": data,
            "dimensions": dimensions,
            "volume_type": "image",
            "voxel_offset": (1, 2, 3),
        }
    ]


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
