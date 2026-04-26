import numpy as np

from server_api.main import (
    _normalize_segmentation_volume_for_neuroglancer,
)


def test_normalize_segmentation_converts_non_negative_int64_to_unsigned():
    volume = np.array([[0, 1], [2, 255]], dtype=np.int64)

    normalized = _normalize_segmentation_volume_for_neuroglancer(volume)

    assert normalized.dtype == np.uint8
    assert np.array_equal(normalized, volume)


def test_normalize_segmentation_uses_uint64_for_large_labels():
    volume = np.array([[0, 2**40]], dtype=np.int64)

    normalized = _normalize_segmentation_volume_for_neuroglancer(volume)

    assert normalized.dtype == np.uint64
    assert np.array_equal(normalized, volume.astype(np.uint64))


def test_normalize_segmentation_rejects_negative_labels():
    volume = np.array([[0, -1]], dtype=np.int64)

    try:
        _normalize_segmentation_volume_for_neuroglancer(volume)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("expected negative labels to be rejected")


def test_normalize_segmentation_accepts_integral_float_labels():
    volume = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)

    normalized = _normalize_segmentation_volume_for_neuroglancer(volume)

    assert normalized.dtype == np.uint8
    assert np.array_equal(normalized, volume.astype(np.uint8))


def test_normalize_segmentation_rejects_fractional_float_labels():
    volume = np.array([[0.5, 1.0]], dtype=np.float32)

    try:
        _normalize_segmentation_volume_for_neuroglancer(volume)
    except ValueError as exc:
        assert "integer-valued" in str(exc)
    else:
        raise AssertionError("expected fractional labels to be rejected")


def test_normalize_segmentation_squeezes_singleton_channel_volumes():
    volume = np.array([[[[0, 1], [2, 3]]]], dtype=np.uint8)

    normalized = _normalize_segmentation_volume_for_neuroglancer(volume)

    assert normalized.shape == (1, 2, 2)
    assert normalized.dtype == np.uint8
    assert np.array_equal(normalized, volume[0])


def test_normalize_segmentation_builds_preview_from_two_channel_prediction():
    semantic = np.zeros((8, 8, 8), dtype=np.uint8)
    boundary = np.zeros_like(semantic)
    semantic[1:7, 1:7, 1:7] = 255
    volume = np.stack([semantic, boundary], axis=0)

    normalized = _normalize_segmentation_volume_for_neuroglancer(volume)

    assert normalized.ndim == 3
    assert normalized.shape == semantic.shape
    assert normalized.dtype == np.uint8
    assert int(normalized.max()) > 0


def test_normalize_segmentation_uses_argmax_for_multiclass_prediction():
    volume = np.zeros((3, 2, 2, 2), dtype=np.uint8)
    volume[2, 1, 1, 1] = 255

    normalized = _normalize_segmentation_volume_for_neuroglancer(volume)

    assert normalized.shape == (2, 2, 2)
    assert normalized.dtype == np.uint8
    assert int(normalized[1, 1, 1]) == 2
