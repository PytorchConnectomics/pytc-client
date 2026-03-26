import pathlib
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database as auth_database
from server_api.auth import models
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


if __name__ == "__main__":
    unittest.main()
