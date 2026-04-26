import numpy as np
import pytest

h5py = pytest.importorskip("h5py")
pytest.importorskip("tifffile")

from server_api.workflows.volume_io import load_volume, parse_crop


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
