import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database as auth_database
from server_api.auth import models
from server_api.auth.router import (
    _project_suggestion_candidates,
    _scan_project_profile,
)
from server_api.main import app as server_api_app
from server_api.synthetic_project import (
    GENERATOR_VERSION,
    VOLUME_CHUNKS,
    VOLUME_SHAPE,
    create_synthetic_project,
)
from server_api.workflows import service as workflow_service


class SyntheticProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = pathlib.Path(self.temp_dir.name) / "synthetic-core-project"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_generator_is_deterministic_idempotent_and_resettable(self):
        first = create_synthetic_project(self.project_root)
        self.assertTrue(first["created"])
        self.assertEqual(first["generator"], GENERATOR_VERSION)

        with h5py.File(self.project_root / "data/raw/train-01_image.h5") as handle:
            first_image = handle["data"][:]
            self.assertEqual(handle["data"].shape, VOLUME_SHAPE)
            self.assertEqual(handle["data"].chunks, VOLUME_CHUNKS)
            self.assertEqual(handle["data"].compression, "gzip")
            self.assertTrue(handle.attrs["synthetic"])

        notes_path = self.project_root / "notes/README.md"
        notes_path.write_text("local testing note\n", encoding="utf-8")
        second = create_synthetic_project(self.project_root)
        self.assertFalse(second["created"])
        self.assertEqual(notes_path.read_text(encoding="utf-8"), "local testing note\n")

        restored = create_synthetic_project(self.project_root, reset=True)
        self.assertTrue(restored["created"])
        self.assertIn(
            "Expected initial progress", notes_path.read_text(encoding="utf-8")
        )
        with h5py.File(self.project_root / "data/raw/train-01_image.h5") as handle:
            np.testing.assert_array_equal(handle["data"][:], first_image)

    def test_fixture_encodes_expected_project_and_prediction_states(self):
        create_synthetic_project(self.project_root)
        manifest = json.loads(
            (self.project_root / "project_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["initial_progress_summary"],
            {
                "total": 4,
                "ground_truth": 2,
                "needs_proofreading": 1,
                "missing_segmentation": 1,
            },
        )

        with (
            h5py.File(
                self.project_root / "outputs/predictions/baseline_review-01.h5"
            ) as baseline_handle,
            h5py.File(
                self.project_root / "outputs/predictions/candidate_review-01.h5"
            ) as candidate_handle,
        ):
            baseline = baseline_handle["data"][:]
            candidate = candidate_handle["data"][:]
        self.assertGreater(np.count_nonzero(baseline != candidate), 0)
        self.assertIn(9, np.unique(baseline))
        self.assertNotIn(9, np.unique(candidate))

        profile = _scan_project_profile(str(self.project_root), audit_detail="summary")
        self.assertEqual(profile["volume_sets"][0]["image_count"], 4)
        self.assertEqual(profile["volume_sets"][0]["label_count"], 3)
        self.assertEqual(profile["volume_sets"][0]["pair_count"], 3)
        self.assertEqual(
            profile["context_hints"]["imaging_modality"],
            "Synthetic volumetric microscopy",
        )
        self.assertEqual(profile["context_hints"]["voxel_size_nm"], [40.0, 8.0, 8.0])

    def test_generator_refuses_to_overwrite_an_unmarked_directory(self):
        self.project_root.mkdir()
        (self.project_root / "important.txt").write_text("keep", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "non-synthetic directory"):
            create_synthetic_project(self.project_root, reset=True)

        self.assertEqual(
            (self.project_root / "important.txt").read_text(encoding="utf-8"),
            "keep",
        )

    def test_initial_project_candidate_and_workflow_defaults_use_fixture(self):
        create_synthetic_project(self.project_root)
        with (
            patch.dict(
                "os.environ",
                {
                    "PYTC_INITIAL_PROJECT_ROOT": str(self.project_root),
                    "PYTC_INITIAL_PROJECT_KIND": "synthetic",
                },
                clear=False,
            ),
            patch.object(
                workflow_service,
                "INITIAL_PROJECT_ROOT",
                str(self.project_root),
            ),
        ):
            candidates = _project_suggestion_candidates()
            defaults = workflow_service._initial_project_defaults()

        self.assertEqual(candidates[0]["id"], "initial-project")
        self.assertTrue(candidates[0]["recommended"])
        self.assertFalse(any(item["recommended"] for item in candidates[1:]))
        self.assertEqual(defaults["title"], "Synthetic Segmentation Core Loop")
        self.assertEqual(defaults["image_path"], str(self.project_root / "data/raw"))
        self.assertTrue(defaults["metadata"]["synthetic"])
        self.assertEqual(
            defaults["metadata"]["project_context"]["training_policy"],
            "train only on confirmed ground-truth masks",
        )


class SyntheticProjectProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = pathlib.Path(self.temp_dir.name) / "synthetic-core-project"
        create_synthetic_project(self.project_root)

        self.engine = create_engine(
            f"sqlite:///{pathlib.Path(self.temp_dir.name) / 'test.db'}",
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        models.Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            with self.SessionLocal() as db:
                yield db

        server_api_app.dependency_overrides[auth_database.get_db] = override_get_db
        self.client = TestClient(server_api_app)

    def tearDown(self):
        server_api_app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_real_progress_endpoint_reports_fixture_contract(self):
        current_response = self.client.get("/api/workflows/current")
        self.assertEqual(current_response.status_code, 200)
        workflow_id = current_response.json()["workflow"]["id"]
        patch_response = self.client.patch(
            f"/api/workflows/{workflow_id}",
            json={
                "title": "Synthetic Segmentation Core Loop",
                "dataset_path": str(self.project_root),
                "image_path": str(self.project_root / "data/raw"),
                "label_path": str(self.project_root / "data/seg"),
                "config_path": str(
                    self.project_root / "configs/Synthetic-Core-Loop-BC.yaml"
                ),
            },
        )
        self.assertEqual(patch_response.status_code, 200)

        progress_response = self.client.get(
            f"/api/workflows/{workflow_id}/project-progress"
        )
        self.assertEqual(progress_response.status_code, 200)
        payload = progress_response.json()
        self.assertEqual(payload["summary"]["total"], 4)
        self.assertEqual(payload["summary"]["ground_truth"], 2)
        self.assertEqual(payload["summary"]["needs_proofreading"], 1)
        self.assertEqual(payload["summary"]["missing_segmentation"], 1)
        states = {row["name"]: row["status"] for row in payload["volumes"]}
        self.assertEqual(states["review-01_image.h5"], "needs_proofreading")
        self.assertEqual(states["target-01_image.h5"], "missing_segmentation")
