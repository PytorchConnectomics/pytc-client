import pathlib
import shutil
import tempfile
import unittest
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database as auth_database
from server_api.auth import models
from server_api.auth.router import _scan_project_profile
from server_api.main import app as server_api_app


class FileWorkspaceRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "auth-test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        models.Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        server_api_app.dependency_overrides[auth_database.get_db] = override_get_db
        self.client = TestClient(server_api_app)

        with self.SessionLocal() as db:
            guest = models.User(
                username="guest",
                email=None,
                hashed_password="guest",
            )
            db.add(guest)
            db.commit()
            db.refresh(guest)
            self.user_id = guest.id

        self.uploads_root = pathlib.Path("uploads") / str(self.user_id)
        if self.uploads_root.exists():
            shutil.rmtree(self.uploads_root)
        self.uploads_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        server_api_app.dependency_overrides.clear()
        if self.uploads_root.exists():
            shutil.rmtree(self.uploads_root, ignore_errors=True)
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _create_file(
        self,
        *,
        name,
        path="root",
        is_folder=False,
        physical_path=None,
        size="1B",
        file_type="text/plain",
    ):
        with self.SessionLocal() as db:
            node = models.File(
                user_id=self.user_id,
                name=name,
                path=path,
                is_folder=is_folder,
                physical_path=physical_path,
                size=size,
                type=file_type,
            )
            db.add(node)
            db.commit()
            db.refresh(node)
            return node.id

    def test_mount_directory_skips_os_metadata_files(self):
        mount_root = pathlib.Path(self.temp_dir.name) / "project"
        mount_root.mkdir()
        (mount_root / ".DS_Store").write_text("junk", encoding="utf-8")
        (mount_root / ".pytc_project_context.json").write_text(
            '{"schema_version":"pytc-project-context/v1"}',
            encoding="utf-8",
        )
        (mount_root / "volume.tif").write_text("data", encoding="utf-8")

        response = self.client.post(
            "/files/mount",
            json={
                "directory_path": str(mount_root),
                "destination_path": "root",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mounted_files"], 1)
        mounted_root_id = response.json()["mounted_root_id"]

        files_response = self.client.get("/files")
        self.assertEqual(files_response.status_code, 200)
        names = {item["name"] for item in files_response.json()}
        self.assertIn("project", names)
        self.assertIn("volume.tif", names)
        self.assertNotIn(".DS_Store", names)
        self.assertNotIn(".pytc_project_context.json", names)

        root_response = self.client.get("/files", params={"parent": "root"})
        self.assertEqual(root_response.status_code, 200)
        root_names = [item["name"] for item in root_response.json()]
        self.assertEqual(root_names, ["project"])

        child_response = self.client.get(
            "/files",
            params={"parent": str(mounted_root_id)},
        )
        self.assertEqual(child_response.status_code, 200)
        child_names = [item["name"] for item in child_response.json()]
        self.assertEqual(child_names, ["volume.tif"])

    def test_project_context_profile_is_saved_in_hidden_project_file(self):
        project_root = pathlib.Path(self.temp_dir.name) / "profile-project"
        project_root.mkdir()

        write_response = self.client.put(
            "/files/project-context",
            json={
                "directory_path": str(project_root),
                "profile": {
                    "project_name": "profile-project",
                    "semantic_context": {
                        "imaging_modality": "EM",
                        "target_structure": "mitochondria",
                    },
                    "mechanistic_mapping": {"image": "data/image"},
                },
            },
        )
        self.assertEqual(write_response.status_code, 200)
        context_path = project_root / ".pytc_project_context.json"
        self.assertTrue(context_path.exists())

        read_response = self.client.get(
            "/files/project-context",
            params={"directory_path": str(project_root)},
        )
        self.assertEqual(read_response.status_code, 200)
        payload = read_response.json()
        self.assertTrue(payload["exists"])
        self.assertEqual(
            payload["profile"]["schema_version"],
            "pytc-project-context/v1",
        )
        self.assertEqual(
            payload["profile"]["semantic_context"]["target_structure"],
            "mitochondria",
        )

    def test_reset_workspace_preserves_mounted_sources_and_clears_uploads(self):
        mount_root = pathlib.Path(self.temp_dir.name) / "mounted-project"
        mount_root.mkdir()
        mounted_file = mount_root / "volume.tif"
        mounted_file.write_text("data", encoding="utf-8")

        mount_response = self.client.post(
            "/files/mount",
            json={
                "directory_path": str(mount_root),
                "destination_path": "root",
            },
        )
        self.assertEqual(mount_response.status_code, 200)

        upload_file = self.uploads_root / "uploaded.tif"
        upload_file.write_text("upload", encoding="utf-8")
        self._create_file(
            name="uploaded.tif",
            physical_path=str(upload_file),
            size="6B",
        )

        response = self.client.delete("/files/workspace")

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["deleted_count"], 3)
        self.assertEqual(response.json()["mounted_root_count"], 1)
        self.assertTrue(mount_root.exists())
        self.assertTrue(mounted_file.exists())
        self.assertFalse(upload_file.exists())
        self.assertTrue(self.uploads_root.exists())

        files_response = self.client.get("/files")
        self.assertEqual(files_response.status_code, 200)
        self.assertEqual(files_response.json(), [])

    def test_get_files_repairs_renamed_mounted_file_entries(self):
        mount_root = pathlib.Path(self.temp_dir.name) / "project"
        mount_root.mkdir()
        original_file = mount_root / "volume.h5"
        original_file.write_bytes(b"data")

        mount_response = self.client.post(
            "/files/mount",
            json={
                "directory_path": str(mount_root),
                "destination_path": "root",
            },
        )
        self.assertEqual(mount_response.status_code, 200)
        mounted_root_id = mount_response.json()["mounted_root_id"]

        renamed_file = mount_root / "volume_im.h5"
        original_file.rename(renamed_file)

        child_response = self.client.get(
            "/files",
            params={"parent": str(mounted_root_id)},
        )
        self.assertEqual(child_response.status_code, 200)

        child_entries = child_response.json()
        self.assertEqual([item["name"] for item in child_entries], ["volume_im.h5"])
        self.assertEqual(child_entries[0]["physical_path"], str(renamed_file))

    def test_get_files_prunes_missing_managed_upload_entries(self):
        missing_upload = self.uploads_root / "ghost.h5"
        self._create_file(
            name="ghost.h5",
            physical_path=str(missing_upload),
            size="10B",
            file_type="application/x-hdf5",
        )

        response = self.client.get("/files")
        self.assertEqual(response.status_code, 200)
        returned_names = [item["name"] for item in response.json()]
        self.assertNotIn("ghost.h5", returned_names)

        with self.SessionLocal() as db:
            ghost = db.query(models.File).filter(models.File.name == "ghost.h5").first()
            self.assertIsNone(ghost)

    def test_project_suggestions_marks_existing_smoke_project_mount(self):
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        smoke_project = repo_root / "testing_projects" / "mito25_paper_loop_smoke"
        smoke_project.mkdir(parents=True, exist_ok=True)

        response = self.client.get("/files/project-suggestions")
        self.assertEqual(response.status_code, 200)
        suggestions = response.json()
        smoke_suggestion = next(
            item for item in suggestions if item["id"] == "mito25-paper-loop-smoke"
        )
        self.assertTrue(
            any(item["id"] == "snemi-proofreading-data" for item in suggestions)
        )
        self.assertFalse(smoke_suggestion["already_mounted"])

        mount_response = self.client.post(
            "/files/mount",
            json={
                "directory_path": str(smoke_project),
                "destination_path": "root",
                "mount_name": "mito25-paper-loop-smoke",
            },
        )
        self.assertEqual(mount_response.status_code, 200)

        mounted_response = self.client.get("/files/project-suggestions")
        self.assertEqual(mounted_response.status_code, 200)
        mounted_smoke = next(
            item
            for item in mounted_response.json()
            if item["id"] == "mito25-paper-loop-smoke"
        )
        self.assertTrue(mounted_smoke["already_mounted"])
        self.assertEqual(
            mounted_smoke["mounted_root_id"],
            mount_response.json()["mounted_root_id"],
        )
        self.assertIn("profile", mounted_smoke)

    def test_project_profile_detects_smoke_project_roles(self):
        project_root = pathlib.Path(self.temp_dir.name) / "project-profile"
        (project_root / "data" / "image").mkdir(parents=True)
        (project_root / "data" / "seg").mkdir(parents=True)
        (project_root / "configs").mkdir()
        (project_root / "checkpoints").mkdir()
        (project_root / "predictions").mkdir()
        (project_root / "data" / "image" / "mito25_smoke_im.h5").write_bytes(b"im")
        (project_root / "data" / "seg" / "mito25_smoke_seg.h5").write_bytes(b"seg")
        (project_root / "configs" / "Mito25-Local-Smoke.yaml").write_text(
            "SYSTEM: {}\n", encoding="utf-8"
        )
        (project_root / "checkpoints" / "checkpoint_00001.pth.tar").write_bytes(
            b"ckpt"
        )
        (project_root / "predictions" / "baseline_result_xy.h5").write_bytes(
            b"baseline"
        )
        (project_root / "predictions" / "candidate_result_xy.h5").write_bytes(
            b"candidate"
        )

        profile = _scan_project_profile(str(project_root))

        self.assertTrue(profile["ready_for_smoke"])
        self.assertEqual(profile["counts"]["image"], 1)
        self.assertEqual(profile["counts"]["label"], 1)
        self.assertEqual(profile["counts"]["prediction"], 2)
        self.assertEqual(profile["counts"]["config"], 1)
        self.assertEqual(profile["counts"]["checkpoint"], 1)
        self.assertEqual(profile["schema"]["schema_version"], "pytc-project-profile/v1")
        self.assertTrue(profile["schema"]["workable"])
        self.assertEqual(profile["schema"]["mode"], "closed_loop_ready")
        self.assertEqual(profile["schema"]["stages"]["inference"]["status"], "ready")
        self.assertEqual(
            profile["paired_examples"],
            [
                {
                    "image": "data/image/mito25_smoke_im.h5",
                    "label": "data/seg/mito25_smoke_seg.h5",
                }
            ],
        )

    def test_project_profile_treats_image_only_volume_as_workable_start(self):
        project_root = pathlib.Path(self.temp_dir.name) / "image-only-project"
        (project_root / "raw").mkdir(parents=True)
        (project_root / "raw" / "sample_volume.ome.tif").write_bytes(b"image")

        profile = _scan_project_profile(str(project_root))

        self.assertFalse(profile["ready_for_smoke"])
        self.assertEqual(profile["counts"]["image"], 1)
        self.assertTrue(profile["schema"]["workable"])
        self.assertEqual(profile["schema"]["mode"], "image_only")
        self.assertEqual(
            profile["schema"]["primary_paths"]["image"],
            "raw/sample_volume.ome.tif",
        )
        self.assertEqual(profile["schema"]["stages"]["visualization"]["status"], "ready")
        self.assertEqual(
            profile["schema"]["stages"]["inference"]["status"],
            "needs_input",
        )
        self.assertEqual(
            profile["schema"]["stages"]["inference"]["missing"],
            ["checkpoint"],
        )

    def test_project_profile_groups_multi_volume_batches_by_directory(self):
        project_root = pathlib.Path(self.temp_dir.name) / "batch-profile"
        image_dir = project_root / "data" / "source" / "Image" / "train"
        label_dir = project_root / "data" / "source" / "Label" / "train"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        (project_root / "configs").mkdir()
        (project_root / "checkpoints").mkdir()
        for index in range(4):
            (image_dir / f"crop_{index:03d}_im.h5").write_bytes(b"im")
            (label_dir / f"crop_{index:03d}_seg.h5").write_bytes(b"seg")
        (project_root / "configs" / "batch.yaml").write_text(
            "SYSTEM: {}\n", encoding="utf-8"
        )
        (project_root / "checkpoints" / "model.pth.tar").write_bytes(b"ckpt")

        profile = _scan_project_profile(str(project_root))

        self.assertEqual(profile["counts"]["image"], 4)
        self.assertEqual(profile["counts"]["label"], 4)
        self.assertEqual(
            profile["role_directories"]["image"][0],
            {
                "path": "data/source/Image/train",
                "count": 4,
                "examples": [
                    "data/source/Image/train/crop_000_im.h5",
                    "data/source/Image/train/crop_001_im.h5",
                    "data/source/Image/train/crop_002_im.h5",
                ],
            },
        )
        self.assertEqual(
            profile["schema"]["primary_paths"]["image_root"],
            "data/source/Image/train",
        )
        self.assertEqual(
            profile["schema"]["primary_paths"]["label_root"],
            "data/source/Label/train",
        )
        self.assertEqual(profile["volume_sets"][0]["image_count"], 4)
        self.assertEqual(profile["volume_sets"][0]["label_count"], 4)
        self.assertEqual(profile["volume_sets"][0]["pair_count"], 4)

    def test_project_profile_uses_content_for_context_hints(self):
        project_root = pathlib.Path(self.temp_dir.name) / "content-profile"
        (project_root / "volumes").mkdir(parents=True)
        (project_root / "volumes" / "raw_image.h5").write_bytes(b"not-real-hdf5")
        (project_root / "project_manifest.json").write_text(
            json.dumps(
                {
                    "task": "Mitochondria semantic segmentation benchmark",
                    "notes": [
                        "Electron microscopy volume with expert masks.",
                        "Prioritize segmentation accuracy.",
                    ],
                }
            ),
            encoding="utf-8",
        )

        profile = _scan_project_profile(str(project_root))

        self.assertEqual(profile["content_signals"]["extension_counts"][".h5"], 1)
        self.assertEqual(profile["content_signals"]["extension_counts"][".json"], 1)
        self.assertEqual(
            profile["content_signals"]["text_sources"][0]["path"],
            "project_manifest.json",
        )
        self.assertEqual(profile["context_hints"]["imaging_modality"], "EM")
        self.assertEqual(profile["context_hints"]["target_structure"], "mitochondria")
        self.assertEqual(profile["context_hints"]["task_goal"], "segmentation")
        self.assertEqual(profile["context_hints"]["optimization_priority"], "accuracy")

    def test_project_profile_spot_checks_hdf5_dataset_keys(self):
        try:
            import h5py
        except Exception:
            self.skipTest("h5py not installed")

        project_root = pathlib.Path(self.temp_dir.name) / "hdf5-profile"
        project_root.mkdir()
        h5_path = project_root / "sample_volume.h5"
        with h5py.File(h5_path, "w") as handle:
            handle.create_dataset("volumes/raw", data=[[[1, 2], [3, 4]]])
            handle.create_dataset("volumes/labels/neuron_ids", data=[[[1, 1], [2, 2]]])

        profile = _scan_project_profile(str(project_root))
        metadata = profile["content_signals"]["volume_metadata"][0]

        self.assertTrue(metadata["readable"])
        self.assertEqual(metadata["format"], "hdf5")
        self.assertEqual(
            [dataset["path"] for dataset in metadata["datasets"]],
            ["volumes/labels/neuron_ids", "volumes/raw"],
        )
        self.assertEqual(profile["context_hints"]["target_structure"], "neurites")


if __name__ == "__main__":
    unittest.main()
