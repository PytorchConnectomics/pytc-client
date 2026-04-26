#!/usr/bin/env python3
"""Run a local closed-loop workflow smoke against the FastAPI workflow API.

This harness is deliberately honest about scope: it exercises workflow
materialization, metrics, bundle export, and researcher-readiness gates with
synthetic TIFF artifacts. It does not run PyTC training, PyTC inference, or the
browser proofreading editor.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import tifffile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server_api.workflows.volume_io import (  # noqa: E402
    SUPPORTED_VOLUME_FORMATS,
    load_volume,
    parse_crop,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _request_json(response, label: str) -> Dict[str, Any]:
    if response.status_code >= 400:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text}")
    return response.json()


def _post_event(
    client,
    *,
    workflow_id: int,
    event_type: str,
    stage: str,
    summary: str,
    payload: Optional[Dict[str, Any]] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    return _request_json(
        client.post(
            f"/api/workflows/{workflow_id}/events",
            json={
                "actor": actor,
                "event_type": event_type,
                "stage": stage,
                "summary": summary,
                "payload": payload or {},
            },
        ),
        f"post {event_type}",
    )


def generate_smoke_artifacts(output_dir: Path) -> Dict[str, str]:
    artifact_dir = output_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    volume_shape = (4, 32, 32)
    z, y, x = np.indices(volume_shape)
    image = ((x * 5 + y * 3 + z * 17) % 255).astype(np.uint8)

    ground_truth = np.zeros(volume_shape, dtype=np.uint8)
    ground_truth[:, 8:22, 9:23] = 1
    ground_truth[1:3, 18:27, 4:13] = 2

    baseline = np.zeros_like(ground_truth)
    baseline[:, 10:20, 11:21] = 1
    baseline[1:3, 20:25, 6:11] = 2

    corrected = ground_truth.copy()
    candidate = ground_truth.copy()

    paths = {
        "image": artifact_dir / "image.tif",
        "initial_mask": artifact_dir / "initial-mask.tif",
        "corrected_mask": artifact_dir / "corrected-mask.tif",
        "ground_truth": artifact_dir / "ground-truth.tif",
        "baseline_prediction": artifact_dir / "baseline-prediction.tif",
        "candidate_prediction": artifact_dir / "candidate-prediction.tif",
        "training_output": artifact_dir / "training-output",
        "checkpoint": artifact_dir / "checkpoint-smoke.pth",
        "evaluation_report": output_dir / "evaluation-report.json",
    }

    tifffile.imwrite(str(paths["image"]), image, photometric="minisblack")
    tifffile.imwrite(str(paths["initial_mask"]), baseline, photometric="minisblack")
    tifffile.imwrite(str(paths["corrected_mask"]), corrected, photometric="minisblack")
    tifffile.imwrite(str(paths["ground_truth"]), ground_truth, photometric="minisblack")
    tifffile.imwrite(
        str(paths["baseline_prediction"]), baseline, photometric="minisblack"
    )
    tifffile.imwrite(
        str(paths["candidate_prediction"]), candidate, photometric="minisblack"
    )
    paths["training_output"].mkdir(parents=True, exist_ok=True)
    paths["checkpoint"].write_text("synthetic checkpoint placeholder\n", encoding="utf-8")

    return {key: str(value) for key, value in paths.items()}


def _write_tiff(path: Path, volume: np.ndarray) -> str:
    tifffile.imwrite(str(path), np.asarray(volume), photometric="minisblack")
    return str(path)


def _apply_crop_to_array(array: np.ndarray, crop: Optional[str]) -> np.ndarray:
    crop_slices = parse_crop(crop)
    if crop_slices is None:
        return np.asarray(array)
    if len(crop_slices) > array.ndim:
        raise ValueError(
            f"Crop has {len(crop_slices)} dimensions but prediction array has "
            f"{array.ndim}"
        )
    key = tuple(list(crop_slices) + [slice(None)] * (array.ndim - len(crop_slices)))
    return np.asarray(array[key])


def _select_prediction_channel(
    array: np.ndarray,
    *,
    channel: Optional[int],
    reference_ndim: int,
    label: str,
) -> np.ndarray:
    volume = np.asarray(array)
    if volume.ndim == reference_ndim:
        if channel is not None:
            raise ValueError(
                f"{label} prediction is already {reference_ndim}D; "
                "do not pass a channel selector for this artifact."
            )
        return volume
    if volume.ndim != reference_ndim + 1:
        return volume

    if channel is not None and channel < 0:
        raise ValueError(f"{label} channel must be non-negative")

    if channel is None:
        if volume.shape[0] <= 16:
            axis = 0
        elif volume.shape[-1] <= 16:
            axis = -1
        else:
            raise ValueError(
                f"{label} prediction has shape {volume.shape}; pass an explicit "
                "channel because no small channel axis could be inferred."
            )
        channel = 0
    elif volume.shape[0] > channel and volume.shape[0] <= 16:
        axis = 0
    elif volume.shape[-1] > channel and volume.shape[-1] <= 16:
        axis = -1
    elif volume.shape[0] > channel:
        axis = 0
    elif volume.shape[-1] > channel:
        axis = -1
    else:
        raise ValueError(
            f"{label} channel {channel} is out of bounds for prediction shape "
            f"{volume.shape}"
        )

    return np.take(volume, channel, axis=axis)


def _load_prediction_volume(
    path: str,
    *,
    dataset_key: Optional[str],
    crop: Optional[str],
    channel: Optional[int],
    reference_ndim: int,
    label: str,
) -> np.ndarray:
    raw = load_volume(str(path), dataset_key=dataset_key)
    selected = _select_prediction_channel(
        raw,
        channel=channel,
        reference_ndim=reference_ndim,
        label=label,
    )
    return _apply_crop_to_array(selected, crop)


def _derived_baseline_from_mask(mask: np.ndarray) -> np.ndarray:
    baseline = np.asarray(mask).copy()
    if baseline.size == 0:
        return baseline
    last_axis = baseline.ndim - 1
    cutoff = max(1, baseline.shape[last_axis] // 4)
    index = [slice(None)] * baseline.ndim
    index[last_axis] = slice(0, cutoff)
    baseline[tuple(index)] = 0
    return baseline


def generate_real_pair_artifacts(
    output_dir: Path,
    *,
    image_path: str,
    mask_path: str,
    image_dataset: Optional[str] = None,
    mask_dataset: Optional[str] = None,
    baseline_prediction_path: Optional[str] = None,
    candidate_prediction_path: Optional[str] = None,
    baseline_dataset: Optional[str] = None,
    candidate_dataset: Optional[str] = None,
    baseline_channel: Optional[int] = None,
    candidate_channel: Optional[int] = None,
    ground_truth_path: Optional[str] = None,
    ground_truth_dataset: Optional[str] = None,
    crop: Optional[str] = None,
) -> Dict[str, str]:
    artifact_dir = output_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    image = load_volume(image_path, dataset_key=image_dataset, crop=crop)
    ground_truth_source = ground_truth_path or mask_path
    ground_truth_key = ground_truth_dataset or mask_dataset
    ground_truth = load_volume(
        ground_truth_source,
        dataset_key=ground_truth_key,
        crop=crop,
    )
    if image.shape != ground_truth.shape:
        raise ValueError(
            "Real image/ground-truth pair must resolve to the same shape after crop; "
            f"got image {image.shape} and ground truth {ground_truth.shape}"
        )

    using_real_predictions = bool(baseline_prediction_path or candidate_prediction_path)
    if using_real_predictions and not (
        baseline_prediction_path and candidate_prediction_path
    ):
        raise ValueError(
            "Real-prediction mode requires both baseline_prediction_path and "
            "candidate_prediction_path"
        )

    if using_real_predictions:
        baseline = _load_prediction_volume(
            str(baseline_prediction_path),
            dataset_key=baseline_dataset,
            crop=crop,
            channel=baseline_channel,
            reference_ndim=ground_truth.ndim,
            label="baseline",
        )
        candidate = _load_prediction_volume(
            str(candidate_prediction_path),
            dataset_key=candidate_dataset,
            crop=crop,
            channel=candidate_channel,
            reference_ndim=ground_truth.ndim,
            label="candidate",
        )
        shapes = {
            "ground_truth": ground_truth.shape,
            "baseline_prediction": baseline.shape,
            "candidate_prediction": candidate.shape,
        }
        if len(set(shapes.values())) != 1:
            raise ValueError(
                "Real prediction volumes must match ground truth shape after crop; "
                f"got {shapes}"
            )
    else:
        baseline = _derived_baseline_from_mask(ground_truth)
        candidate = np.asarray(ground_truth).copy()

    paths = {
        "source_image": str(Path(image_path).expanduser()),
        "source_mask": str(Path(mask_path).expanduser()),
        "source_ground_truth": str(Path(ground_truth_source).expanduser()),
        "image": _write_tiff(artifact_dir / "image-crop.tif", image),
        "initial_mask": _write_tiff(artifact_dir / "initial-mask-derived.tif", baseline),
        "corrected_mask": _write_tiff(
            artifact_dir / "corrected-mask-crop.tif", ground_truth
        ),
        "ground_truth": _write_tiff(
            artifact_dir / "ground-truth-crop.tif", ground_truth
        ),
        "baseline_prediction": _write_tiff(
            artifact_dir
            / (
                "baseline-prediction-real.tif"
                if using_real_predictions
                else "baseline-prediction-derived.tif"
            ),
            baseline,
        ),
        "candidate_prediction": _write_tiff(
            artifact_dir
            / (
                "candidate-prediction-real.tif"
                if using_real_predictions
                else "candidate-prediction-derived.tif"
            ),
            candidate,
        ),
        "training_output": str(artifact_dir / "training-output"),
        "checkpoint": str(artifact_dir / "checkpoint-smoke.pth"),
        "evaluation_report": str(output_dir / "evaluation-report.json"),
    }
    if baseline_prediction_path:
        paths["source_baseline_prediction"] = str(
            Path(baseline_prediction_path).expanduser()
        )
        if baseline_channel is not None:
            paths["source_baseline_channel"] = str(baseline_channel)
    if candidate_prediction_path:
        paths["source_candidate_prediction"] = str(
            Path(candidate_prediction_path).expanduser()
        )
        if candidate_channel is not None:
            paths["source_candidate_channel"] = str(candidate_channel)

    Path(paths["training_output"]).mkdir(parents=True, exist_ok=True)
    Path(paths["checkpoint"]).write_text(
        "real-pair smoke checkpoint placeholder\n", encoding="utf-8"
    )
    return paths


def run_closed_loop_smoke(
    output_dir: Path,
    *,
    include_research_plan: bool = True,
    image_path: Optional[str] = None,
    mask_path: Optional[str] = None,
    image_dataset: Optional[str] = None,
    mask_dataset: Optional[str] = None,
    baseline_prediction_path: Optional[str] = None,
    candidate_prediction_path: Optional[str] = None,
    baseline_dataset: Optional[str] = None,
    candidate_dataset: Optional[str] = None,
    baseline_channel: Optional[int] = None,
    candidate_channel: Optional[int] = None,
    ground_truth_path: Optional[str] = None,
    ground_truth_dataset: Optional[str] = None,
    crop: Optional[str] = None,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if image_path or mask_path:
        if not image_path or not mask_path:
            raise ValueError("Real-artifact mode requires both image_path and mask_path")
        has_prediction_inputs = bool(baseline_prediction_path or candidate_prediction_path)
        if has_prediction_inputs and not (
            baseline_prediction_path and candidate_prediction_path
        ):
            raise ValueError(
                "Real-prediction mode requires both baseline_prediction_path and "
                "candidate_prediction_path"
            )
        artifact_mode = (
            "real_pair_real_predictions"
            if has_prediction_inputs
            else "real_pair_derived_predictions"
        )
        artifacts = generate_real_pair_artifacts(
            output_dir,
            image_path=image_path,
            mask_path=mask_path,
            image_dataset=image_dataset,
            mask_dataset=mask_dataset,
            baseline_prediction_path=baseline_prediction_path,
            candidate_prediction_path=candidate_prediction_path,
            baseline_dataset=baseline_dataset,
            candidate_dataset=candidate_dataset,
            baseline_channel=baseline_channel,
            candidate_channel=candidate_channel,
            ground_truth_path=ground_truth_path,
            ground_truth_dataset=ground_truth_dataset,
            crop=crop,
        )
        source_data = {
            "image_path": image_path,
            "mask_path": mask_path,
            "image_dataset": image_dataset,
            "mask_dataset": mask_dataset,
            "ground_truth_path": ground_truth_path or mask_path,
            "ground_truth_dataset": ground_truth_dataset or mask_dataset,
            "baseline_prediction_path": baseline_prediction_path,
            "candidate_prediction_path": candidate_prediction_path,
            "baseline_dataset": baseline_dataset,
            "candidate_dataset": candidate_dataset,
            "baseline_channel": baseline_channel,
            "candidate_channel": candidate_channel,
            "crop": crop,
        }
    else:
        artifact_mode = "synthetic"
        artifacts = generate_smoke_artifacts(output_dir)
        source_data = {"synthetic": True}

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from server_api.auth import database as auth_database
    from server_api.auth import models

    with contextlib.redirect_stdout(sys.stderr):
        from server_api.main import app as server_api_app

    db_path = output_dir / "workflow-smoke.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    previous_override = server_api_app.dependency_overrides.get(auth_database.get_db)
    server_api_app.dependency_overrides[auth_database.get_db] = override_get_db
    prediction_runtime = (
        "external_artifact"
        if artifact_mode == "real_pair_real_predictions"
        else "simulated"
    )
    baseline_summary = (
        "Recorded external baseline prediction artifact."
        if artifact_mode == "real_pair_real_predictions"
        else "Recorded synthetic baseline inference output."
    )
    candidate_summary = (
        "Recorded external candidate prediction artifact."
        if artifact_mode == "real_pair_real_predictions"
        else "Recorded synthetic candidate inference output."
    )

    try:
        client = TestClient(server_api_app)
        current = _request_json(client.get("/api/workflows/current"), "get workflow")
        workflow_id = current["workflow"]["id"]

        _post_event(
            client,
            workflow_id=workflow_id,
            actor="user",
            event_type="dataset.loaded",
            stage="visualization",
            summary="Loaded synthetic smoke-test image and initial mask.",
            payload={
                "image_path": artifacts.get("source_image") or artifacts["image"],
                "mask_path": artifacts["initial_mask"],
                "source_mask_path": artifacts.get("source_mask"),
                "source_ground_truth_path": artifacts.get("source_ground_truth"),
                "image_dataset": image_dataset,
                "mask_dataset": mask_dataset,
                "ground_truth_dataset": ground_truth_dataset,
                "crop": crop,
                "artifact_mode": artifact_mode,
            },
        )
        _post_event(
            client,
            workflow_id=workflow_id,
            event_type="inference.completed",
            stage="inference",
            summary=baseline_summary,
            payload={
                "outputPath": artifacts["baseline_prediction"],
                "runtime": prediction_runtime,
                "artifact_mode": artifact_mode,
                "source_prediction_path": artifacts.get("source_baseline_prediction"),
                "prediction_dataset": baseline_dataset,
                "prediction_channel": baseline_channel,
            },
        )
        _post_event(
            client,
            workflow_id=workflow_id,
            actor="user",
            event_type="proofreading.instance_classified",
            stage="proofreading",
            summary="Marked the smoke hotspot as incorrect.",
            payload={"region_id": "z:1", "classification": "incorrect"},
        )
        _post_event(
            client,
            workflow_id=workflow_id,
            actor="user",
            event_type="proofreading.mask_saved",
            stage="proofreading",
            summary="Saved a synthetic corrected mask for the hotspot.",
            payload={"region_id": "z:1", "instance_id": 42},
        )
        _post_event(
            client,
            workflow_id=workflow_id,
            event_type="proofreading.masks_exported",
            stage="proofreading",
            summary="Exported synthetic corrected masks.",
            payload={
                "written_path": artifacts["corrected_mask"],
                "region_id": "z:1",
                "runtime": "simulated",
                "artifact_mode": artifact_mode,
            },
        )

        hotspots = _request_json(
            client.get(f"/api/workflows/{workflow_id}/hotspots"),
            "compute hotspots",
        )
        proposal = _request_json(
            client.post(
                f"/api/workflows/{workflow_id}/agent-actions",
                json={
                    "action": "stage_retraining_from_corrections",
                    "summary": "Stage smoke corrections for retraining.",
                    "payload": {"corrected_mask_path": artifacts["corrected_mask"]},
                },
            ),
            "create agent proposal",
        )
        _request_json(
            client.post(
                f"/api/workflows/{workflow_id}/agent-actions/{proposal['id']}/approve"
            ),
            "approve agent proposal",
        )
        _post_event(
            client,
            workflow_id=workflow_id,
            event_type="training.completed",
            stage="evaluation",
            summary="Recorded synthetic retraining completion.",
            payload={
                "outputPath": artifacts["training_output"],
                "checkpointPath": artifacts["checkpoint"],
                "checkpointName": "checkpoint-smoke.pth",
                "runtime": "simulated",
                "artifact_mode": artifact_mode,
            },
        )
        _post_event(
            client,
            workflow_id=workflow_id,
            event_type="inference.completed",
            stage="evaluation",
            summary=candidate_summary,
            payload={
                "outputPath": artifacts["candidate_prediction"],
                "checkpointPath": artifacts["checkpoint"],
                "runtime": prediction_runtime,
                "artifact_mode": artifact_mode,
                "source_prediction_path": artifacts.get("source_candidate_prediction"),
                "prediction_dataset": candidate_dataset,
                "prediction_channel": candidate_channel,
            },
        )

        research_plan: Optional[Dict[str, Any]] = None
        if include_research_plan:
            research_plan = _request_json(
                client.post(
                    f"/api/workflows/{workflow_id}/agent-plans",
                    json={
                        "title": "Researcher-only smoke readiness plan",
                        "metadata": {"researcher_only": True, "synthetic": True},
                    },
                ),
                "create researcher-only agent plan",
            )
            _request_json(
                client.post(
                    f"/api/workflows/{workflow_id}/agent-plans/{research_plan['id']}/approve"
                ),
                "approve researcher-only agent plan",
            )

        evaluation = _request_json(
            client.post(
                f"/api/workflows/{workflow_id}/evaluation-results/compute",
                json={
                    "name": "synthetic-closed-loop-smoke",
                    "ground_truth_path": artifacts["ground_truth"],
                    "baseline_prediction_path": artifacts["baseline_prediction"],
                    "candidate_prediction_path": artifacts["candidate_prediction"],
                    "report_path": artifacts["evaluation_report"],
                    "metadata": {
                        "artifact_mode": artifact_mode,
                        "source_data": source_data,
                    },
                },
            ),
            "compute evaluation",
        )
        readiness = _request_json(
            client.get(f"/api/workflows/{workflow_id}/case-study-readiness"),
            "get researcher readiness",
        )
        bundle = _request_json(
            client.post(f"/api/workflows/{workflow_id}/export-bundle"),
            "export bundle",
        )

        _write_json(output_dir / "workflow-bundle.json", bundle)
        _write_json(output_dir / "readiness.json", readiness)

        report = {
            "workflow_id": workflow_id,
            "artifact_mode": artifact_mode,
            "source_data": source_data,
            "output_dir": str(output_dir),
            "db_path": str(db_path),
            "ready_for_case_study": readiness["ready_for_case_study"],
            "readiness": {
                "completed_count": readiness["completed_count"],
                "total_count": readiness["total_count"],
                "next_required_items": readiness["next_required_items"],
            },
            "metric_summary": evaluation["metrics"]["summary"],
            "bundle_counts": {
                "events": len(bundle.get("events", [])),
                "artifacts": len(bundle.get("artifacts", [])),
                "model_runs": len(bundle.get("model_runs", [])),
                "model_versions": len(bundle.get("model_versions", [])),
                "correction_sets": len(bundle.get("correction_sets", [])),
                "evaluation_results": len(bundle.get("evaluation_results", [])),
                "persisted_hotspots": len(bundle.get("persisted_hotspots", [])),
                "agent_plans": len(bundle.get("agent_plans", [])),
            },
            "top_hotspot": hotspots.get("hotspots", [{}])[0],
            "real_checks_exercised": [
                "FastAPI workflow routes",
                "SQLite workflow persistence with typed records",
                "artifact materialization from workflow events",
                "correction-set materialization",
                "model-run and model-version materialization",
                "hotspot ranking from workflow event evidence",
                "TIFF before/after segmentation metrics",
                *(
                    ["real prediction artifacts supplied by caller"]
                    if artifact_mode == "real_pair_real_predictions"
                    else []
                ),
                "workflow evidence bundle export",
            ],
            "simulated_or_not_exercised": [
                "actual PyTC training subprocess",
                "actual PyTC inference subprocess",
                "browser-level proofreading editor interaction",
                *(
                    []
                    if artifact_mode.startswith("real_pair_")
                    else ["real biomedical/connectomics sample data"]
                ),
                *(
                    [
                        "baseline/candidate predictions derived from real segmentation labels, not model outputs"
                    ]
                    if artifact_mode == "real_pair_derived_predictions"
                    else []
                ),
                "long-running job queue, cancellation, retry, and failure recovery",
            ],
            "supported_volume_formats": list(SUPPORTED_VOLUME_FORMATS),
            "researcher_only_checks": [
                "case-study readiness gate",
                "bounded agent plan preview and approval audit",
            ]
            if include_research_plan
            else ["case-study readiness gate without plan approval"],
            "artifacts": artifacts,
        }
        _write_json(output_dir / "smoke-report.json", report)
        return report
    finally:
        if previous_override is None:
            server_api_app.dependency_overrides.pop(auth_database.get_db, None)
        else:
            server_api_app.dependency_overrides[
                auth_database.get_db
            ] = previous_override
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a synthetic closed-loop workflow smoke for PyTC workflow evidence."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for generated smoke artifacts. Defaults to a temp directory.",
    )
    parser.add_argument(
        "--no-research-plan",
        action="store_true",
        help="Skip the researcher-only agent-plan readiness gate.",
    )
    parser.add_argument(
        "--image-path",
        type=str,
        default=None,
        help="Optional real raw image volume path. Enables real-artifact mode.",
    )
    parser.add_argument(
        "--mask-path",
        type=str,
        default=None,
        help="Optional real label/segmentation volume path. Enables real-artifact mode.",
    )
    parser.add_argument(
        "--image-dataset",
        type=str,
        default=None,
        help="Dataset key for HDF5/Zarr/NPZ image volumes, e.g. main.",
    )
    parser.add_argument(
        "--mask-dataset",
        type=str,
        default=None,
        help="Dataset key for HDF5/Zarr/NPZ mask volumes, e.g. data.",
    )
    parser.add_argument(
        "--ground-truth-path",
        type=str,
        default=None,
        help="Optional ground-truth path for evaluation. Defaults to --mask-path.",
    )
    parser.add_argument(
        "--ground-truth-dataset",
        type=str,
        default=None,
        help="Dataset key for the ground-truth volume. Defaults to --mask-dataset.",
    )
    parser.add_argument(
        "--baseline-prediction-path",
        type=str,
        default=None,
        help="Optional real baseline prediction path.",
    )
    parser.add_argument(
        "--candidate-prediction-path",
        type=str,
        default=None,
        help="Optional real candidate prediction path.",
    )
    parser.add_argument(
        "--baseline-dataset",
        type=str,
        default=None,
        help="Dataset key for the baseline prediction volume.",
    )
    parser.add_argument(
        "--candidate-dataset",
        type=str,
        default=None,
        help="Dataset key for the candidate prediction volume.",
    )
    parser.add_argument(
        "--baseline-channel",
        type=int,
        default=None,
        help=(
            "Optional channel index for channel-first/channel-last baseline "
            "prediction volumes such as PyTC result_xy.h5."
        ),
    )
    parser.add_argument(
        "--candidate-channel",
        type=int,
        default=None,
        help=(
            "Optional channel index for channel-first/channel-last candidate "
            "prediction volumes such as PyTC result_xy.h5."
        ),
    )
    parser.add_argument(
        "--crop",
        type=str,
        default=None,
        help="Optional crop like '0:8,0:256,0:256'. Use this for large volumes.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or Path(
        tempfile.mkdtemp(prefix="pytc-closed-loop-smoke-")
    )
    report = run_closed_loop_smoke(
        output_dir=output_dir,
        include_research_plan=not args.no_research_plan,
        image_path=args.image_path,
        mask_path=args.mask_path,
        image_dataset=args.image_dataset,
        mask_dataset=args.mask_dataset,
        baseline_prediction_path=args.baseline_prediction_path,
        candidate_prediction_path=args.candidate_prediction_path,
        baseline_dataset=args.baseline_dataset,
        candidate_dataset=args.candidate_dataset,
        baseline_channel=args.baseline_channel,
        candidate_channel=args.candidate_channel,
        ground_truth_path=args.ground_truth_path,
        ground_truth_dataset=args.ground_truth_dataset,
        crop=args.crop,
    )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
