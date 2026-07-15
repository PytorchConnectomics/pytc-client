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

    def test_missing_parent_file_listing_returns_404(self):
        response = self.client.get("/files", params={"parent": "999999"})

        self.assertEqual(response.status_code, 404)
        self.assertIn("no longer mounted", response.json()["detail"])

    def test_project_context_profile_is_saved_in_hidden_project_file(self):
        project_root = pathlib.Path(self.temp_dir.name) / "profile-project"
        project_root.mkdir()
        mount_response = self.client.post(
            "/files/mount",
            json={
                "directory_path": str(project_root),
                "destination_path": "root",
            },
        )
        self.assertEqual(mount_response.status_code, 200)

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

    def test_project_context_profile_can_be_deleted(self):
        project_root = pathlib.Path(self.temp_dir.name) / "profile-project-delete"
        project_root.mkdir()
        mount_response = self.client.post(
            "/files/mount",
            json={
                "directory_path": str(project_root),
                "destination_path": "root",
            },
        )
        self.assertEqual(mount_response.status_code, 200)
        context_path = project_root / ".pytc_project_context.json"
        context_path.write_text(
            '{"schema_version":"pytc-project-context/v1"}',
            encoding="utf-8",
        )

        response = self.client.delete(
            "/files/project-context",
            params={"directory_path": str(project_root)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        self.assertFalse(context_path.exists())

    def test_project_profile_infers_voxel_size_from_notes(self):
        project_root = pathlib.Path(self.temp_dir.name) / "resolution-project"
        project_root.mkdir()
        (project_root / "README.md").write_text(
            "EM mitochondria segmentation. Voxel size: 40 x 4 x 4 nm.",
            encoding="utf-8",
        )
        (project_root / "image.h5").write_text("placeholder", encoding="utf-8")
        (project_root / "label.h5").write_text("placeholder", encoding="utf-8")

        profile = _scan_project_profile(str(project_root))

        self.assertEqual(
            profile["context_hints"]["voxel_size_nm"],
            [40.0, 4.0, 4.0],
        )
        self.assertEqual(
            profile["schema"]["context_hints"]["voxel_size_nm"],
            [40.0, 4.0, 4.0],
        )

    def test_reset_workspace_preserves_mounted_sources_and_clears_uploads(self):
        mount_root = pathlib.Path(self.temp_dir.name) / "mounted-project"
        mount_root.mkdir()
        mounted_file = mount_root / "volume.tif"
        mounted_file.write_text("data", encoding="utf-8")
        context_file = mount_root / ".pytc_project_context.json"
        context_file.write_text(
            '{"schema_version":"pytc-project-context/v1"}',
            encoding="utf-8",
        )

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
        self.assertTrue(context_file.exists())
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
        workspace_root = repo_root.parent
        smoke_project = repo_root / "testing_projects" / "mito25_paper_loop_smoke"
        smoke_project.mkdir(parents=True, exist_ok=True)
        snemi_project = workspace_root / "testing_data" / "snemi"
        snemi_project.mkdir(parents=True, exist_ok=True)

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

    def test_users_me_projects_lists_owned_mounted_projects(self):
        project_root = pathlib.Path(self.temp_dir.name) / "owned-project"
        image_dir = project_root / "data" / "image"
        label_dir = project_root / "data" / "seg"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        (image_dir / "sample_im.h5").write_bytes(b"image")
        (label_dir / "sample_seg.h5").write_bytes(b"label")

        mount_response = self.client.post(
            "/files/mount",
            json={
                "directory_path": str(project_root),
                "destination_path": "root",
                "mount_name": "Owned Demo",
            },
        )
        self.assertEqual(mount_response.status_code, 200)

        response = self.client.get("/users/me/projects")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["username"], "guest")
        self.assertEqual(len(payload["mounted_projects"]), 1)
        project = payload["mounted_projects"][0]
        self.assertEqual(project["name"], "Owned Demo")
        self.assertEqual(project["directory_path"], str(project_root))
        self.assertEqual(
            project["mounted_root_id"],
            mount_response.json()["mounted_root_id"],
        )
        self.assertGreaterEqual(project["mounted_folders"], 2)
        self.assertEqual(project["mounted_files"], 2)
        self.assertEqual(project["profile"]["counts"]["image"], 1)
        self.assertEqual(project["profile"]["counts"]["label"], 1)

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
        (project_root / "checkpoints" / "checkpoint_00001.pth.tar").write_bytes(b"ckpt")
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
        self.assertEqual(
            profile["schema"]["stages"]["visualization"]["status"], "ready"
        )
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

    def test_project_profile_prefers_manifest_volume_map(self):
        project_root = pathlib.Path(self.temp_dir.name) / "manifest-profile"
        raw_dir = project_root / "data" / "raw"
        seg_dir = project_root / "data" / "seg"
        train_dir = project_root / "data" / "pytc_train" / "1"
        config_dir = project_root / "configs"
        raw_dir.mkdir(parents=True)
        seg_dir.mkdir(parents=True)
        train_dir.mkdir(parents=True)
        config_dir.mkdir()
        for volume_id in ["1", "2", "3"]:
            (raw_dir / volume_id).mkdir()
            (raw_dir / volume_id / f"{volume_id}-xri_raw.tif").write_bytes(b"raw")
        for volume_id in ["1", "2"]:
            (seg_dir / volume_id).mkdir()
            (seg_dir / volume_id / f"{volume_id}-mask.tif").write_bytes(b"mask")
        (train_dir / "1-xri_raw-tiled_clahe.tif").write_bytes(b"train raw")
        (train_dir / "1-annotated_mask.tif").write_bytes(b"train mask")
        (config_dir / "TapeReader-Fiber-BCS-AppCompat-Sanity.yaml").write_text(
            "SYSTEM: {}\n", encoding="utf-8"
        )
        (project_root / "project_manifest.json").write_text(
            json.dumps(
                {
                    "title": "Yixiao TapeReader XRI Case Study",
                    "task": "CytoTape fibre instance segmentation",
                    "imaging_modality": "X-ray / XRI volumetric microscopy",
                    "target_structure": "CytoTape fibres",
                    "task_family": "XRI fibre instance segmentation",
                    "active_paths": {
                        "image_root": "data/raw",
                        "label_root": "data/seg",
                        "config": "configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml",
                    },
                    "initial_progress_summary": {
                        "ground_truth": 2,
                        "needs_proofreading": 0,
                        "missing_segmentation": 1,
                    },
                    "workflow_split": {
                        "ground_truth_training_volumes": ["1", "2"],
                        "image_only_inference_targets": ["3"],
                    },
                    "voxel_size": {"zyx_nm": [40, 16.3, 16.3]},
                    "volumes": [
                        {
                            "id": "1",
                            "status": "ground_truth",
                            "image": "data/raw/1/1-xri_raw.tif",
                            "segmentation": "data/seg/1/1-mask.tif",
                        },
                        {
                            "id": "2",
                            "status": "ground_truth",
                            "image": "data/raw/2/2-xri_raw.tif",
                            "segmentation": "data/seg/2/2-mask.tif",
                        },
                        {
                            "id": "3",
                            "status": "missing_segmentation",
                            "image": "data/raw/3/3-xri_raw.tif",
                            "segmentation": None,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        profile = _scan_project_profile(str(project_root))

        self.assertEqual(profile["role_directories"]["image"][0]["path"], "data/raw")
        self.assertEqual(profile["role_directories"]["label"][0]["path"], "data/seg")
        self.assertEqual(
            profile["schema"]["primary_paths"]["image"], "data/raw/1/1-xri_raw.tif"
        )
        self.assertEqual(
            profile["schema"]["primary_paths"]["label"], "data/seg/1/1-mask.tif"
        )
        self.assertEqual(
            profile["schema"]["primary_paths"]["config"],
            "configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml",
        )
        self.assertEqual(profile["schema"]["primary_paths"]["image_root"], "data/raw")
        self.assertEqual(profile["schema"]["primary_paths"]["label_root"], "data/seg")
        self.assertEqual(profile["volume_sets"][0]["source"], "project_manifest")
        self.assertEqual(profile["volume_sets"][0]["image_count"], 3)
        self.assertEqual(profile["volume_sets"][0]["label_count"], 2)
        self.assertEqual(profile["volume_sets"][0]["pair_count"], 2)
        self.assertEqual(
            profile["context_hints"]["task_family"],
            "XRI fibre instance segmentation",
        )
        self.assertEqual(profile["context_hints"]["voxel_size_nm"], [40, 16.3, 16.3])

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

    def test_project_profile_audits_hdf5_pairs_and_metadata_facts(self):
        try:
            import h5py
        except Exception:
            self.skipTest("h5py not installed")

        project_root = pathlib.Path(self.temp_dir.name) / "hdf5-audit-profile"
        image_dir = project_root / "data" / "image"
        label_dir = project_root / "data" / "seg"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        with h5py.File(image_dir / "sample_im.h5", "w") as handle:
            handle.attrs["voxel_size_nm_zyx"] = [30, 8, 8]
            handle.create_dataset(
                "volumes/raw",
                data=[
                    [[1, 2, 3], [4, 5, 6]],
                    [[7, 8, 9], [10, 11, 12]],
                ],
            )
        with h5py.File(label_dir / "sample_seg.h5", "w") as handle:
            handle.create_dataset(
                "volumes/labels/mitochondria",
                data=[
                    [[0, 1, 1], [0, 0, 2]],
                    [[0, 2, 2], [0, 0, 0]],
                ],
            )

        profile = _scan_project_profile(str(project_root))
        audit = profile["audit"]

        self.assertEqual(audit["schema_version"], "pytc-project-audit/v1")
        self.assertEqual(audit["summary"]["audited_volumes"], 2)
        self.assertEqual(audit["summary"]["readable_volumes"], 2)
        self.assertEqual(audit["summary"]["shape_match_count"], 1)
        self.assertEqual(profile["context_hints"]["voxel_size_nm"], [30, 8, 8])
        self.assertEqual(
            profile["context_hints"]["voxel_size_source"],
            "volume_metadata:data/image/sample_im.h5",
        )
        self.assertEqual(
            audit["pair_checks"][0],
            {
                "image": "data/image/sample_im.h5",
                "label": "data/seg/sample_seg.h5",
                "image_shape": [2, 2, 3],
                "label_shape": [2, 2, 3],
                "shape_match": True,
                "source": "volume_metadata",
            },
        )
        self.assertEqual(
            audit["context_facts"][0],
            {
                "key": "voxel_size_nm",
                "label": "Voxel size",
                "value": [30, 8, 8],
                "unit": "nm",
                "axis_order": "z,y,x",
                "source": "volume_metadata:data/image/sample_im.h5",
                "confidence": "high",
            },
        )
        self.assertGreater(audit["volumes"][0]["stats"]["nonzero_fraction"], 0)


if __name__ == "__main__":
    unittest.main()
