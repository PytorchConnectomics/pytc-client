import pathlib

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("tifffile")
h5py = pytest.importorskip("h5py")

import numpy as np

from scripts.run_closed_loop_smoke import run_closed_loop_smoke


def test_closed_loop_smoke_script_writes_researcher_evidence_bundle(tmp_path):
    report = run_closed_loop_smoke(pathlib.Path(tmp_path))

    assert report["ready_for_case_study"] is True
    assert report["metric_summary"]["candidate_improved_dice"] is True
    assert report["bundle_counts"]["model_runs"] >= 3
    assert report["bundle_counts"]["model_versions"] == 1
    assert report["bundle_counts"]["correction_sets"] >= 1
    assert report["bundle_counts"]["evaluation_results"] == 1
    assert report["bundle_counts"]["agent_plans"] == 1
    assert "actual PyTC training subprocess" in report["simulated_or_not_exercised"]
    assert "browser-level proofreading editor interaction" in report[
        "simulated_or_not_exercised"
    ]

    assert (tmp_path / "smoke-report.json").exists()
    assert (tmp_path / "workflow-bundle.json").exists()
    assert (tmp_path / "readiness.json").exists()
    assert (tmp_path / "evaluation-report.json").exists()


def test_closed_loop_smoke_script_accepts_real_hdf5_pair(tmp_path):
    image_path = tmp_path / "image.h5"
    mask_path = tmp_path / "mask.h5"
    image = np.arange(8 * 16 * 16, dtype=np.uint8).reshape(8, 16, 16)
    mask = np.zeros((8, 16, 16), dtype=np.uint16)
    mask[:, 4:12, 5:13] = 7
    with h5py.File(image_path, "w") as handle:
        handle.create_dataset("main", data=image)
    with h5py.File(mask_path, "w") as handle:
        handle.create_dataset("data", data=mask)

    report = run_closed_loop_smoke(
        pathlib.Path(tmp_path / "smoke"),
        image_path=str(image_path),
        mask_path=str(mask_path),
        image_dataset="main",
        mask_dataset="data",
        crop="0:4,0:12,0:12",
    )

    assert report["artifact_mode"] == "real_pair_derived_predictions"
    assert report["ready_for_case_study"] is True
    assert report["source_data"]["image_dataset"] == "main"
    assert report["source_data"]["mask_dataset"] == "data"
    assert "real biomedical/connectomics sample data" not in report[
        "simulated_or_not_exercised"
    ]
    assert any(
        item.startswith("baseline/candidate predictions derived")
        for item in report["simulated_or_not_exercised"]
    )


def test_closed_loop_smoke_script_accepts_real_hdf5_predictions(tmp_path):
    image_path = tmp_path / "image.h5"
    mask_path = tmp_path / "mask.h5"
    baseline_path = tmp_path / "baseline-prediction.h5"
    candidate_path = tmp_path / "candidate-prediction.h5"
    image = np.arange(8 * 16 * 16, dtype=np.uint8).reshape(8, 16, 16)
    mask = np.zeros((8, 16, 16), dtype=np.uint16)
    mask[:, 4:12, 5:13] = 7
    baseline = mask.copy()
    baseline[:, :, :7] = 0
    candidate = mask.copy()
    for path, dataset, array in [
        (image_path, "main", image),
        (mask_path, "data", mask),
        (baseline_path, "prediction", baseline),
        (candidate_path, "prediction", candidate),
    ]:
        with h5py.File(path, "w") as handle:
            handle.create_dataset(dataset, data=array)

    report = run_closed_loop_smoke(
        pathlib.Path(tmp_path / "smoke"),
        image_path=str(image_path),
        mask_path=str(mask_path),
        image_dataset="main",
        mask_dataset="data",
        baseline_prediction_path=str(baseline_path),
        candidate_prediction_path=str(candidate_path),
        baseline_dataset="prediction",
        candidate_dataset="prediction",
        crop="0:4,0:12,0:12",
    )

    assert report["artifact_mode"] == "real_pair_real_predictions"
    assert report["ready_for_case_study"] is True
    assert report["metric_summary"]["candidate_improved_dice"] is True
    assert report["metric_summary"]["dice_delta"] > 0
    assert report["source_data"]["baseline_dataset"] == "prediction"
    assert report["source_data"]["candidate_dataset"] == "prediction"
    assert "real prediction artifacts supplied by caller" in report[
        "real_checks_exercised"
    ]
    assert not any(
        item.startswith("baseline/candidate predictions derived")
        for item in report["simulated_or_not_exercised"]
    )


def test_closed_loop_smoke_accepts_channel_first_pytc_predictions(tmp_path):
    image_path = tmp_path / "image.h5"
    mask_path = tmp_path / "mask.h5"
    baseline_path = tmp_path / "baseline-result_xy.h5"
    candidate_path = tmp_path / "candidate-result_xy.h5"
    image = np.arange(8 * 16 * 16, dtype=np.uint8).reshape(8, 16, 16)
    mask = np.zeros((8, 16, 16), dtype=np.uint16)
    mask[:, 4:12, 5:13] = 1
    baseline = np.stack([np.zeros_like(mask), mask.copy()])
    baseline[1, :, :, :7] = 0
    candidate = np.stack([np.zeros_like(mask), mask.copy()])
    for path, dataset, array in [
        (image_path, "main", image),
        (mask_path, "data", mask),
        (baseline_path, "vol0", baseline),
        (candidate_path, "vol0", candidate),
    ]:
        with h5py.File(path, "w") as handle:
            handle.create_dataset(dataset, data=array)

    report = run_closed_loop_smoke(
        pathlib.Path(tmp_path / "smoke"),
        image_path=str(image_path),
        mask_path=str(mask_path),
        image_dataset="main",
        mask_dataset="data",
        baseline_prediction_path=str(baseline_path),
        candidate_prediction_path=str(candidate_path),
        baseline_dataset="vol0",
        candidate_dataset="vol0",
        baseline_channel=1,
        candidate_channel=1,
        crop="0:4,0:12,0:12",
    )

    assert report["artifact_mode"] == "real_pair_real_predictions"
    assert report["ready_for_case_study"] is True
    assert report["metric_summary"]["candidate_improved_dice"] is True
    assert report["source_data"]["baseline_channel"] == 1
    assert report["source_data"]["candidate_channel"] == 1


def test_closed_loop_smoke_rejects_partial_real_prediction_inputs(tmp_path):
    with pytest.raises(ValueError, match="requires both baseline_prediction_path"):
        run_closed_loop_smoke(
            pathlib.Path(tmp_path / "smoke"),
            image_path=str(tmp_path / "missing-image.h5"),
            mask_path=str(tmp_path / "missing-mask.h5"),
            baseline_prediction_path=str(tmp_path / "baseline.h5"),
        )
