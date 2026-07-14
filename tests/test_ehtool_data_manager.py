import numpy as np
import pytest
import tifffile

from server_api.ehtool.data_manager import DataManager
from server_api.ehtool.utils import array_to_base64, glasbey_color, labels_to_rgba

h5py = pytest.importorskip("h5py")


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

    image_slice, label_slice, active_mask, index, total = manager.get_instance_slice_axis(
        instance_id=300,
        axis="zx",
        index=2,
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
