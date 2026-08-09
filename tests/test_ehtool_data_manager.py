import numpy as np
import pytest
import tifffile

import server_api.ehtool.data_manager as data_manager_module
from server_api.ehtool.data_manager import DataManager
from server_api.ehtool.utils import array_to_base64, glasbey_color, labels_to_rgba

h5py = pytest.importorskip("h5py")
zarr = pytest.importorskip("zarr")


def _write_proofreading_pyramid(path, *, coarse_translation=(0.0, 0.0, 0.0)):
    fine = np.arange(8 * 12 * 16, dtype=np.uint16).reshape(8, 12, 16)
    coarse = fine[::2, ::2, ::2]
    root = zarr.open_group(str(path), mode="w")
    create_array = getattr(root, "create_array", root.create_dataset)
    create_array("0", data=fine, chunks=(2, 4, 4))
    create_array("1", data=coarse, chunks=(1, 3, 4))
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
                        {"type": "scale", "scale": [1.0, 1.0, 1.0]},
                        {"type": "translation", "translation": [0.0, 0.0, 0.0]},
                    ],
                },
                {
                    "path": "1",
                    "coordinateTransformations": [
                        {"type": "scale", "scale": [2.0, 2.0, 2.0]},
                        {
                            "type": "translation",
                            "translation": list(coarse_translation),
                        },
                    ],
                },
            ],
        }
    ]
    return fine, coarse


class _RecordingStore:
    def __init__(self, store, level):
        self._store = store
        self.level = level
        self.reads = []
        self.close_calls = 0

    @property
    def metadata(self):
        return self._store.metadata

    @property
    def shape(self):
        return self._store.shape

    @property
    def ndim(self):
        return self._store.ndim

    def read(self, crop=None, **kwargs):
        self.reads.append(crop)
        return self._store.read(crop, **kwargs)

    def close(self):
        self.close_calls += 1
        self._store.close()


def _record_pyramid_reads(monkeypatch):
    real_open = data_manager_module.open_volume_store
    opened = []

    def recording_open(path, *, level=None, **kwargs):
        store = _RecordingStore(
            real_open(path, level=level, **kwargs), 0 if level is None else level
        )
        opened.append(store)
        return store

    monkeypatch.setattr(data_manager_module, "open_volume_store", recording_open)
    return opened


def test_semantic_mask_edits_persist_instance_artifact_and_binary_mask(tmp_path):
    image_path = tmp_path / "image.tif"
    mask_path = tmp_path / "mask.tif"

    image = np.zeros((2, 8, 8), dtype=np.uint8)
    mask = np.zeros((2, 8, 8), dtype=np.uint8)
    mask[0, 1:3, 1:3] = 255
    mask[0, 5:7, 5:7] = 255
    tifffile.imwrite(str(image_path), image)
    tifffile.imwrite(str(mask_path), mask)

    manager = DataManager()
    manager.load_dataset(str(image_path), str(mask_path))
    manager.ensure_instances()

    assert manager.instance_mode == "semantic"
    instance_id = manager.instances[0]["id"]

    edited_active_mask = np.zeros((8, 8), dtype=np.uint8)
    edited_active_mask[0:4, 0:4] = 255
    result = manager.save_instance_mask_slice(
        instance_id=instance_id,
        axis="xy",
        index=0,
        mask_base64=array_to_base64(edited_active_mask, format="PNG"),
    )

    assert result["pixels_changed"] > 0
    assert manager.mask_volume[0, 0, 0] == 255
    assert manager.mask_volume[0, 4, 4] == 0
    assert manager.instance_artifact_path
    assert (tmp_path / ".pytc_instance_labels.tif").exists()
    assert (tmp_path / ".pytc_proofreading.json").exists()

    reloaded = DataManager()
    reloaded.load_dataset(str(image_path), str(mask_path))
    reloaded.ensure_instances()

    assert reloaded.instance_mode == "semantic"
    assert reloaded.mask_volume[0, 0, 0] == 255
    assert reloaded.instance_volume[0, 0, 0] == instance_id


def test_side_axis_active_mask_uses_original_instance_labels(tmp_path):
    image_path = tmp_path / "image.tif"
    mask_path = tmp_path / "mask.tif"

    image = np.zeros((3, 5, 5), dtype=np.uint8)
    mask = np.zeros((3, 5, 5), dtype=np.uint16)
    mask[:, 2, 1:4] = 300
    mask[0, 0, 0] = 301
    mask[2, 4, 4] = 302
    tifffile.imwrite(str(image_path), image)
    tifffile.imwrite(str(mask_path), mask)

    manager = DataManager()
    manager.load_dataset(str(image_path), str(mask_path))
    manager.ensure_instances()

    image_slice, label_slice, active_mask, index, total = (
        manager.get_instance_slice_axis(
            instance_id=300,
            axis="zx",
            index=2,
        )
    )

    assert index == 2
    assert total == 5
    assert image_slice.shape == label_slice.shape == active_mask.shape
    assert np.count_nonzero(active_mask) == 9


def test_labels_to_rgba_vectorized_overlay_preserves_large_label_colors():
    labels = np.zeros((4, 5), dtype=np.uint16)
    labels[0, 0] = 1
    labels[1, 2] = 300
    labels[3, 4] = 1025

    rgba = labels_to_rgba(labels)

    assert rgba.shape == (4, 5, 4)
    assert tuple(rgba[0, 0, :3]) == glasbey_color(1)
    assert tuple(rgba[1, 2, :3]) == glasbey_color(300)
    assert tuple(rgba[3, 4, :3]) == glasbey_color(1025)
    assert rgba[0, 1, 3] == 0
    assert rgba[1, 2, 3] == 255


def test_hdf5_project_load_accepts_main_and_data_dataset_names(tmp_path):
    image_path = tmp_path / "image-main.h5"
    mask_path = tmp_path / "mask-data.h5"

    image = np.zeros((3, 8, 8), dtype=np.uint8)
    mask = np.zeros((3, 8, 8), dtype=np.uint16)
    mask[:, 2:4, 2:4] = 7
    with h5py.File(image_path, "w") as handle:
        handle.create_dataset("main", data=image)
    with h5py.File(mask_path, "w") as handle:
        handle.create_dataset("data", data=mask)

    manager = DataManager()
    result = manager.load_dataset(str(image_path), str(mask_path))

    assert result["total_layers"] == 3
    assert result["is_3d"] is True
    assert manager.image_volume.shape == (3, 8, 8)
    assert manager.mask_volume.shape == (3, 8, 8)
    assert manager.mask_volume.dtype == np.uint16


def test_preview_reads_native_mip_before_io_and_overlays_read_no_image(
    tmp_path, monkeypatch
):
    image_path = tmp_path / "image.zarr"
    mask_path = tmp_path / "mask.tif"
    _write_proofreading_pyramid(image_path)
    mask = np.zeros((8, 12, 16), dtype=np.uint8)
    mask[6, 2:6, 3:8] = 255
    tifffile.imwrite(mask_path, mask)
    opened = _record_pyramid_reads(monkeypatch)

    manager = DataManager()
    manager.load_dataset(str(image_path), str(mask_path))
    manager.ensure_instances()
    instance_id = manager.instances[0]["id"]
    assert opened[0].reads == []

    preview = manager.get_instance_image_bytes(
        instance_id=instance_id,
        z_index=6,
        axis="xy",
        kind="image",
        max_dim=6,
        quality="preview",
    )

    level_one = next(store for store in opened if store.level == 1)
    assert opened[0].reads == []
    assert level_one.reads == [(slice(3, 4), slice(None), slice(None))]
    assert preview[1:4] == (6, 8, "xy")
    assert preview[-1]["pyramid_level"] == 1
    assert preview[-1]["pyramid_scale"] == [2.0, 2.0, 2.0]
    assert preview[-1]["pyramid_authoritative_level"] == 0
    assert preview[-1]["pyramid_revision"]

    read_count = sum(len(store.reads) for store in opened)
    manager.get_instance_image_bytes(
        instance_id=instance_id,
        z_index=6,
        axis="xy",
        kind="mask_active",
        max_dim=6,
        quality="preview",
    )
    manager.get_instance_filmstrip_bytes(
        instance_id=instance_id,
        axis="xy",
        z_start=5,
        z_count=2,
        kind="mask_all",
        max_dim=6,
        quality="preview",
    )
    assert sum(len(store.reads) for store in opened) == read_count

    full = manager.get_instance_image_bytes(
        instance_id=instance_id,
        z_index=6,
        axis="xy",
        kind="image",
        max_dim=None,
        quality="full",
    )
    assert opened[0].reads == [(slice(6, 7), slice(None), slice(None))]
    assert full[-1]["pyramid_level"] == 0


def test_coarse_preview_then_edit_persists_authoritative_voxels(tmp_path):
    image_path = tmp_path / "image.zarr"
    mask_path = tmp_path / "mask.tif"
    _write_proofreading_pyramid(image_path)
    mask = np.zeros((8, 12, 16), dtype=np.uint8)
    mask[6, 2:6, 3:8] = 255
    tifffile.imwrite(mask_path, mask)

    manager = DataManager()
    manager.load_dataset(str(image_path), str(mask_path))
    manager.ensure_instances()
    instance_id = manager.instances[0]["id"]
    preview = manager.get_instance_image_bytes(
        instance_id=instance_id,
        z_index=6,
        axis="xy",
        kind="image",
        max_dim=6,
        quality="preview",
    )
    assert preview[-1]["pyramid_level"] == 1

    edited = np.zeros((12, 16), dtype=np.uint8)
    edited[1:5, 1:5] = 255
    result = manager.save_instance_mask_slice(
        instance_id=instance_id,
        axis="xy",
        index=6,
        mask_base64=array_to_base64(edited, format="PNG"),
    )

    assert result["z_index"] == 6
    assert manager.mask_volume[6, 1, 1] == 255
    assert manager.mask_volume[3, 1, 1] == 0
    manager.close()

    reloaded = DataManager()
    reloaded.load_dataset(str(image_path), str(mask_path))
    reloaded.ensure_instances()
    assert reloaded.mask_volume[6, 1, 1] == 255
    assert reloaded.mask_volume[3, 1, 1] == 0


def test_translated_mip_is_not_used_for_level_zero_overlay(tmp_path):
    image_path = tmp_path / "translated.zarr"
    mask_path = tmp_path / "mask.tif"
    _write_proofreading_pyramid(image_path, coarse_translation=(0.0, 1.0, 0.0))
    mask = np.zeros((8, 12, 16), dtype=np.uint8)
    mask[:, 2:4, 2:4] = 7
    tifffile.imwrite(mask_path, mask)

    manager = DataManager()
    manager.load_dataset(str(image_path), str(mask_path))
    manager.ensure_instances()
    response = manager.get_instance_image_bytes(
        instance_id=7,
        z_index=2,
        axis="xy",
        kind="image",
        max_dim=6,
        quality="preview",
    )

    assert response[-1]["pyramid_level"] == 0


def test_reload_and_close_release_each_pyramid_store_once(tmp_path, monkeypatch):
    image_path = tmp_path / "image.zarr"
    mask_path = tmp_path / "mask.tif"
    _write_proofreading_pyramid(image_path)
    mask = np.zeros((8, 12, 16), dtype=np.uint8)
    mask[:, 2:4, 2:4] = 1
    tifffile.imwrite(mask_path, mask)
    opened = _record_pyramid_reads(monkeypatch)

    manager = DataManager()
    manager.load_dataset(str(image_path), str(mask_path))
    manager.ensure_instances()
    manager.get_instance_image_bytes(
        instance_id=1,
        z_index=2,
        axis="xy",
        kind="image",
        max_dim=6,
        quality="preview",
    )
    original_stores = list(opened)

    manager.load_dataset(str(image_path), str(mask_path))
    assert [store.close_calls for store in original_stores] == [1, 1]
    replacement = opened[-1]
    manager.close()
    manager.close()
    assert replacement.close_calls == 1
    assert manager._image_store is None
    assert manager._image_level_stores == {}


def test_proofreading_rejects_non_zyx_ngff_axes(tmp_path):
    image_path = tmp_path / "permuted.zarr"
    root = zarr.open_group(str(image_path), mode="w")
    create_array = getattr(root, "create_array", root.create_dataset)
    create_array("0", data=np.zeros((16, 12, 8), dtype=np.uint8))
    root.attrs["multiscales"] = [
        {
            "axes": ["x", "y", "z"],
            "datasets": [{"path": "0"}],
        }
    ]

    manager = DataManager()
    with pytest.raises(ValueError, match="must be ZYX"):
        manager.load_dataset(str(image_path))
