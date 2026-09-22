import numpy as np
import pytest

h5py = pytest.importorskip("h5py")
pytest.importorskip("tifffile")

from server_api.workflows.volume_io import (
    ArrayVolumeStore,
    load_volume,
    open_volume_store,
    parse_crop,
)


def test_parse_crop_accepts_voxel_slice_strings():
    assert parse_crop("0:4,10:20,30:40") == (
        slice(0, 4, None),
        slice(10, 20, None),
        slice(30, 40, None),
    )
    assert parse_crop("full") is None


def test_load_volume_reads_hdf5_dataset_with_crop(tmp_path):
    path = tmp_path / "volume.h5"
    volume = np.arange(4 * 5 * 6, dtype=np.uint16).reshape(4, 5, 6)
    with h5py.File(path, "w") as handle:
        handle.create_dataset("data", data=volume)

    loaded = load_volume(str(path), dataset_key="data", crop="1:3,2:5,1:4")

    np.testing.assert_array_equal(loaded, volume[1:3, 2:5, 1:4])


def test_open_volume_store_exposes_metadata_without_reading_data(tmp_path):
    path = tmp_path / "volume.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset(
            "data",
            shape=(64, 128, 256),
            chunks=(8, 32, 32),
            dtype=np.uint16,
        )

    with open_volume_store(str(path), dataset_key="data") as store:
        assert store.metadata.shape == (64, 128, 256)
        assert store.metadata.chunks == (8, 32, 32)
        assert store.metadata.dtype == np.dtype(np.uint16)
        assert store.metadata.dataset_key == "data"
        assert store.metadata.format == "hdf5"


def test_volume_store_indexes_region_before_numpy_materialization(tmp_path):
    class RecordingArray:
        shape = (100, 200, 300)
        dtype = np.dtype(np.uint16)
        chunks = (10, 20, 30)

        def __init__(self):
            self.requested_keys = []

        def __array__(self, *_args, **_kwargs):
            raise AssertionError("full backing array was materialized")

        def __getitem__(self, key):
            self.requested_keys.append(key)
            return np.zeros((2, 3, 4), dtype=self.dtype)

    backing = RecordingArray()
    store = ArrayVolumeStore(
        backing,
        path=tmp_path / "recording.zarr",
        format="zarr",
    )

    result = store.read("1:3,10:13,20:24")

    assert result.shape == (2, 3, 4)
    assert backing.requested_keys == [(slice(1, 3), slice(10, 13), slice(20, 24))]


def test_volume_store_supports_storage_backed_array_protocol(tmp_path):
    class RecordingArray:
        shape = (100, 200, 300)
        dtype = np.dtype(np.uint16)
        chunks = (10, 20, 30)

        def __init__(self):
            self.requested_keys = []

        def __array__(self, *_args, **_kwargs):
            raise AssertionError("full backing array was materialized")

        def __getitem__(self, key):
            self.requested_keys.append(key)
            return np.ones((2, 3, 4), dtype=self.dtype)

    backing = RecordingArray()
    store = ArrayVolumeStore(
        backing,
        path=tmp_path / "viewer.zarr",
        format="zarr",
    )

    region = store[1:3, 10:13, 20:24]

    assert store.shape == (100, 200, 300)
    assert store.ndim == 3
    assert store.dtype == np.dtype(np.uint16)
    assert region.shape == (2, 3, 4)
    assert backing.requested_keys == [(slice(1, 3), slice(10, 13), slice(20, 24))]


def test_volume_store_context_closes_backing_resource(tmp_path):
    closed = []
    store = ArrayVolumeStore(
        np.zeros((2, 3, 4), dtype=np.uint8),
        path=tmp_path / "volume.npy",
        format="npy",
        close=lambda: closed.append(True),
    )

    with store:
        assert store.read("0:1").shape == (1, 3, 4)

    assert closed == [True]
    with pytest.raises(RuntimeError, match="closed"):
        store.read("0:1")


def test_load_volume_reads_inline_hdf5_dataset_reference(tmp_path):
    path = tmp_path / "volume.h5"
    volume = np.arange(2 * 3 * 4, dtype=np.uint8).reshape(2, 3, 4)
    with h5py.File(path, "w") as handle:
        handle.create_dataset("main", data=volume)

    loaded = load_volume(f"{path}::main")

    np.testing.assert_array_equal(loaded, volume)


def test_load_volume_selects_channel_before_crop_for_hdf5(tmp_path):
    path = tmp_path / "prediction.h5"
    volume = np.arange(2 * 4 * 5 * 6, dtype=np.float32).reshape(2, 4, 5, 6)
    with h5py.File(path, "w") as handle:
        handle.create_dataset("vol0", data=volume)

    loaded = load_volume(
        str(path),
        dataset_key="vol0",
        crop="1:3,2:5,1:4",
        channel=1,
        reference_ndim=3,
        label="prediction",
    )

    np.testing.assert_array_equal(loaded, volume[1, 1:3, 2:5, 1:4])


def test_load_volume_rejects_channel_for_already_3d_volume(tmp_path):
    path = tmp_path / "mask.h5"
    volume = np.arange(4 * 5 * 6, dtype=np.uint16).reshape(4, 5, 6)
    with h5py.File(path, "w") as handle:
        handle.create_dataset("data", data=volume)

    with pytest.raises(ValueError, match="already 3D"):
        load_volume(
            str(path),
            dataset_key="data",
            channel=0,
            reference_ndim=3,
            label="mask",
        )


def test_load_volume_reads_compressed_tiff_crop(tmp_path):
    tifffile = pytest.importorskip("tifffile")
    path = tmp_path / "volume.tif"
    volume = np.arange(8 * 16 * 24, dtype=np.uint16).reshape(8, 16, 24)
    tifffile.imwrite(
        path,
        volume,
        compression="zlib",
        metadata={"axes": "ZYX"},
    )

    loaded = load_volume(str(path), crop="2:5,4:9,6:12")

    np.testing.assert_array_equal(loaded, volume[2:5, 4:9, 6:12])


def test_open_volume_store_reads_zarr_region(tmp_path):
    zarr = pytest.importorskip("zarr")
    path = tmp_path / "volume.zarr"
    volume = np.arange(6 * 12 * 18, dtype=np.uint16).reshape(6, 12, 18)
    root = zarr.open(str(path), mode="w")
    create_array = getattr(root, "create_array", root.create_dataset)
    create_array("raw", data=volume, chunks=(2, 4, 6))

    with open_volume_store(f"{path}::raw") as store:
        loaded = store.read("1:4,3:8,5:11")
        assert store.metadata.shape == volume.shape
        assert store.metadata.chunks == (2, 4, 6)

    np.testing.assert_array_equal(loaded, volume[1:4, 3:8, 5:11])
