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


def _write_ngff_pyramid(path):
    zarr = pytest.importorskip("zarr")
    fine = np.arange(8 * 12 * 16, dtype=np.uint16).reshape(8, 12, 16)
    coarse = (10000 + np.arange(4 * 6 * 8, dtype=np.uint16)).reshape(4, 6, 8)
    root = zarr.open_group(str(path), mode="w")
    create_array = getattr(root, "create_array", root.create_dataset)
    create_array("fine", data=fine, chunks=(2, 4, 4))
    create_array("coarse", data=coarse, chunks=(1, 3, 4))
    root.attrs["multiscales"] = [
        {
            "version": "0.4",
            "name": "synthetic-image",
            "axes": [
                {"name": "z", "type": "space", "unit": "nanometer"},
                {"name": "y", "type": "space", "unit": "nanometer"},
                {"name": "x", "type": "space", "unit": "nanometer"},
            ],
            "datasets": [
                {
                    "path": "fine",
                    "coordinateTransformations": [
                        {"type": "scale", "scale": [40.0, 8.0, 8.0]},
                        {
                            "type": "translation",
                            "translation": [20.0, 4.0, 4.0],
                        },
                    ],
                },
                {
                    "path": "coarse",
                    "coordinateTransformations": [
                        {"type": "scale", "scale": [80.0, 16.0, 16.0]},
                        {
                            "type": "translation",
                            "translation": [40.0, 8.0, 8.0],
                        },
                    ],
                },
            ],
        }
    ]
    return fine, coarse


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


def test_open_volume_store_reads_ngff_axes_transforms_and_levels(tmp_path):
    path = tmp_path / "pyramid.zarr"
    fine, _coarse = _write_ngff_pyramid(path)

    with open_volume_store(str(path)) as store:
        metadata = store.metadata

        assert metadata.multiscale_version == "0.4"
        assert metadata.selected_level == 0
        assert metadata.dataset_key == "fine"
        assert metadata.shape == fine.shape
        assert metadata.chunks == (2, 4, 4)
        assert tuple(axis.name for axis in metadata.axes) == ("z", "y", "x")
        assert tuple(axis.type for axis in metadata.axes) == (
            "space",
            "space",
            "space",
        )
        assert tuple(axis.unit for axis in metadata.axes) == (
            "nanometer",
            "nanometer",
            "nanometer",
        )
        assert len(metadata.levels) == 2
        assert metadata.levels[0].index == 0
        assert metadata.levels[0].dataset_key == "fine"
        assert metadata.levels[0].scale == (40.0, 8.0, 8.0)
        assert metadata.levels[0].translation == (20.0, 4.0, 4.0)
        assert metadata.levels[1].index == 1
        assert metadata.levels[1].dataset_key == "coarse"
        assert metadata.levels[1].shape == (4, 6, 8)
        assert metadata.levels[1].chunks == (1, 3, 4)
        assert metadata.levels[1].scale == (80.0, 16.0, 16.0)
        assert metadata.levels[1].translation == (40.0, 8.0, 8.0)


def test_open_volume_store_selects_explicit_ngff_level_and_reads_bounded_region(
    tmp_path,
):
    path = tmp_path / "pyramid.zarr"
    _fine, coarse = _write_ngff_pyramid(path)

    with open_volume_store(str(path), level=1) as store:
        loaded = store.read("1:3,2:5,3:7")

        assert store.metadata.selected_level == 1
        assert store.metadata.dataset_key == "coarse"
        assert store.metadata.shape == coarse.shape

    np.testing.assert_array_equal(loaded, coarse[1:3, 2:5, 3:7])


def test_load_volume_selects_explicit_ngff_level(tmp_path):
    path = tmp_path / "pyramid.zarr"
    _fine, coarse = _write_ngff_pyramid(path)

    loaded = load_volume(str(path), level=1, crop="0:2,1:4,2:6")

    np.testing.assert_array_equal(loaded, coarse[0:2, 1:4, 2:6])


@pytest.mark.parametrize("level", [-1, 2])
def test_open_volume_store_rejects_invalid_ngff_level(tmp_path, level):
    path = tmp_path / "pyramid.zarr"
    _write_ngff_pyramid(path)

    with pytest.raises(ValueError, match="level"):
        open_volume_store(str(path), level=level)


def test_open_volume_store_rejects_malformed_ngff_transform_dimensions(tmp_path):
    zarr = pytest.importorskip("zarr")
    path = tmp_path / "malformed.zarr"
    root = zarr.open_group(str(path), mode="w")
    create_array = getattr(root, "create_array", root.create_dataset)
    create_array("0", shape=(4, 6, 8), chunks=(2, 3, 4), dtype=np.uint8)
    root.attrs["multiscales"] = [
        {
            "version": "0.4",
            "axes": [
                {"name": "z", "type": "space"},
                {"name": "y", "type": "space"},
                {"name": "x", "type": "space"},
            ],
            "datasets": [
                {
                    "path": "0",
                    "coordinateTransformations": [
                        {"type": "scale", "scale": [2.0, 2.0]}
                    ],
                }
            ],
        }
    ]

    with pytest.raises(ValueError, match="scale"):
        open_volume_store(str(path))


def test_open_volume_store_rejects_ngff_dataset_that_does_not_exist(tmp_path):
    zarr = pytest.importorskip("zarr")
    path = tmp_path / "missing-level.zarr"
    root = zarr.open_group(str(path), mode="w")
    root.attrs["multiscales"] = [
        {
            "version": "0.4",
            "axes": [
                {"name": "z", "type": "space"},
                {"name": "y", "type": "space"},
                {"name": "x", "type": "space"},
            ],
            "datasets": [{"path": "does-not-exist"}],
        }
    ]

    with pytest.raises(ValueError, match="does-not-exist"):
        open_volume_store(str(path))


def test_bare_zarr_remains_a_single_level_volume(tmp_path):
    zarr = pytest.importorskip("zarr")
    path = tmp_path / "bare.zarr"
    volume = np.arange(4 * 6 * 8, dtype=np.uint16).reshape(4, 6, 8)
    root = zarr.open_group(str(path), mode="w")
    create_array = getattr(root, "create_array", root.create_dataset)
    create_array("raw", data=volume, chunks=(2, 3, 4))

    with open_volume_store(str(path)) as store:
        loaded = store.read("1:3,2:5,3:7")
        assert store.metadata.dataset_key == "raw"
        assert store.metadata.selected_level == 0
        assert store.metadata.axes == ()
        assert len(store.metadata.levels) == 1
        assert store.metadata.levels[0].dataset_key == "raw"

    np.testing.assert_array_equal(loaded, volume[1:3, 2:5, 3:7])

    with pytest.raises(ValueError, match="level"):
        open_volume_store(str(path), level=1)


def test_open_volume_store_reads_nested_ngff_05_ome_metadata(tmp_path):
    zarr = pytest.importorskip("zarr")
    path = tmp_path / "ngff-05.zarr"
    fine = np.arange(6 * 10 * 14, dtype=np.uint16).reshape(6, 10, 14)
    coarse = fine[::2, ::2, ::2]
    root = zarr.open_group(str(path), mode="w")
    create_array = getattr(root, "create_array", root.create_dataset)
    create_array("scale0", data=fine, chunks=(2, 5, 7))
    create_array("scale1", data=coarse, chunks=(1, 5, 7))
    root.attrs["ome"] = {
        "version": "0.5",
        "multiscales": [
            {
                "name": "nested-metadata",
                "axes": [
                    {"name": "z", "type": "space", "unit": "micrometer"},
                    {"name": "y", "type": "space", "unit": "micrometer"},
                    {"name": "x", "type": "space", "unit": "micrometer"},
                ],
                "datasets": [
                    {
                        "path": "scale0",
                        "coordinateTransformations": [
                            {"type": "scale", "scale": [1.0, 0.5, 0.5]}
                        ],
                    },
                    {
                        "path": "scale1",
                        "coordinateTransformations": [
                            {"type": "scale", "scale": [2.0, 1.0, 1.0]}
                        ],
                    },
                ],
            }
        ],
    }

    with open_volume_store(str(path), level=1) as store:
        assert store.metadata.multiscale_version == "0.5"
        assert store.metadata.selected_level == 1
        assert store.metadata.dataset_key == "scale1"
        assert store.metadata.shape == coarse.shape
        assert tuple(axis.name for axis in store.metadata.axes) == ("z", "y", "x")
        assert tuple(axis.unit for axis in store.metadata.axes) == (
            "micrometer",
            "micrometer",
            "micrometer",
        )
        assert store.metadata.levels[1].scale == (2.0, 1.0, 1.0)
        loaded = store.read("1:3,1:4,2:6")

    np.testing.assert_array_equal(loaded, coarse[1:3, 1:4, 2:6])


def test_ngff_composes_dataset_then_multiscale_transforms(tmp_path):
    zarr = pytest.importorskip("zarr")
    path = tmp_path / "composed-transforms.zarr"
    root = zarr.open_group(str(path), mode="w")
    create_array = getattr(root, "create_array", root.create_dataset)
    create_array("0", shape=(4, 6, 8), chunks=(2, 3, 4), dtype=np.uint8)
    root.attrs["multiscales"] = [
        {
            "version": "0.4",
            "axes": ["z", "y", "x"],
            "coordinateTransformations": [
                {"type": "scale", "scale": [10.0, 20.0, 30.0]},
                {"type": "translation", "translation": [5.0, 6.0, 7.0]},
            ],
            "datasets": [
                {
                    "path": "0",
                    "coordinateTransformations": [
                        {"type": "scale", "scale": [2.0, 3.0, 4.0]},
                        {"type": "translation", "translation": [1.0, 2.0, 3.0]},
                    ],
                }
            ],
        }
    ]

    with open_volume_store(str(path)) as store:
        level = store.metadata.levels[0]

    # Dataset coordinates are transformed first, then mapped through the
    # multiscale coordinate system: parent_scale * child_translation + parent_t.
    assert level.scale == (20.0, 60.0, 120.0)
    assert level.translation == (15.0, 46.0, 97.0)


def test_open_volume_store_rejects_unsupported_ngff_dataset_transform(tmp_path):
    zarr = pytest.importorskip("zarr")
    path = tmp_path / "unsupported-transform.zarr"
    root = zarr.open_group(str(path), mode="w")
    create_array = getattr(root, "create_array", root.create_dataset)
    create_array("0", shape=(4, 6, 8), chunks=(2, 3, 4), dtype=np.uint8)
    root.attrs["multiscales"] = [
        {
            "version": "0.4",
            "axes": ["z", "y", "x"],
            "datasets": [
                {
                    "path": "0",
                    "coordinateTransformations": [{"type": "rotation", "angle": 45.0}],
                }
            ],
        }
    ]

    with pytest.raises(ValueError, match="[Uu]nsupported.*transform"):
        open_volume_store(str(path))


def test_open_volume_store_selects_ome_tiff_subifd_level(tmp_path):
    tifffile = pytest.importorskip("tifffile")
    path = tmp_path / "pyramid.ome.tif"
    fine = np.arange(32 * 48, dtype=np.uint16).reshape(32, 48)
    coarse = fine[::2, ::2]
    with tifffile.TiffWriter(path, bigtiff=True) as handle:
        handle.write(
            fine,
            subifds=1,
            metadata={"axes": "YX"},
            photometric="minisblack",
        )
        handle.write(
            coarse,
            subfiletype=1,
            metadata={"axes": "YX"},
            photometric="minisblack",
        )

    with open_volume_store(str(path)) as base_store:
        assert base_store.metadata.selected_level == 0
        assert base_store.metadata.shape == fine.shape
        assert tuple(axis.name for axis in base_store.metadata.axes) == ("y", "x")
        assert len(base_store.metadata.levels) == 2
        np.testing.assert_array_equal(base_store.read("3:8,4:11"), fine[3:8, 4:11])

    with open_volume_store(str(path), level=1) as coarse_store:
        assert coarse_store.metadata.selected_level == 1
        assert coarse_store.metadata.shape == coarse.shape
        assert coarse_store.metadata.levels[1].scale == (2.0, 2.0)
        loaded = coarse_store.read("2:6,3:9")

    np.testing.assert_array_equal(loaded, coarse[2:6, 3:9])
