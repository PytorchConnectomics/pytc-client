import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database as auth_database
from server_api.auth import models as auth_models
from server_api.auth.router import get_current_user
from server_api.ehtool.db_models import EHToolLayer, EHToolSession
from fastapi import FastAPI

from server_api.workflow.router import router as workflow_router


class WorkflowExportBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "workflow-export.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        auth_models.Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app = FastAPI()
        self.app.include_router(workflow_router)
        self.app.dependency_overrides[auth_database.get_db] = override_get_db

        with self.SessionLocal() as db:
            user = auth_models.User(
                username="bundle_user",
                email="bundle@example.com",
                hashed_password="hashed",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            self.user = user

        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _create_session_with_layers(self):
        dataset_path = pathlib.Path(self.temp_dir.name) / "dataset.tif"
        mask_path = pathlib.Path(self.temp_dir.name) / "mask.tif"
        image_path = pathlib.Path(self.temp_dir.name) / "layer_0.png"

        dataset_path.write_text("dataset", encoding="utf-8")
        mask_path.write_text("mask", encoding="utf-8")
        image_path.write_text("image", encoding="utf-8")

        t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(minutes=1)
        t2 = t0 + timedelta(minutes=2)

        with self.SessionLocal() as db:
            session = EHToolSession(
                user_id=self.user.id,
                project_name="Bundle Project",
                workflow_type="detection",
                dataset_path=str(dataset_path),
                mask_path=str(mask_path),
                total_layers=2,
                created_at=t0,
                updated_at=t2,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            layer0 = EHToolLayer(
                session_id=session.id,
                layer_index=0,
                layer_name="layer-0",
                classification="correct",
                image_path=str(image_path),
                mask_path=str(mask_path),
                created_at=t1,
                updated_at=t2,
            )
            layer1 = EHToolLayer(
                session_id=session.id,
                layer_index=1,
                layer_name="layer-1",
                classification="error",
                image_path=str(pathlib.Path(self.temp_dir.name) / "missing-layer.png"),
                mask_path=None,
                created_at=t2,
                updated_at=t2,
            )
            db.add_all([layer0, layer1])
            db.commit()
            return session.id, str(pathlib.Path(self.temp_dir.name) / "missing-layer.png")

    def test_export_bundle_happy_path_returns_deterministic_structure(self):
        session_id, _ = self._create_session_with_layers()

        response = self.client.post(f"/api/workflows/{session_id}/export-bundle")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertIn("exported_at", payload)

        snapshot = payload["workflow_session"]
        self.assertEqual(snapshot["id"], session_id)
        self.assertEqual(snapshot["project_name"], "Bundle Project")
        self.assertEqual(snapshot["workflow_type"], "detection")
        self.assertEqual(snapshot["total_layers"], 2)

        event_times = [event["event_time"] for event in payload["events"] if event["event_time"]]
        self.assertEqual(event_times, sorted(event_times))

        self.assertEqual(
            sorted(payload.keys()),
            ["artifacts", "events", "exported_at", "schema_version", "workflow_session"],
        )

    def test_export_bundle_marks_missing_artifact_paths_without_failing(self):
        session_id, missing_path = self._create_session_with_layers()

        response = self.client.post(f"/api/workflows/{session_id}/export-bundle")

        self.assertEqual(response.status_code, 200)
        artifacts = {artifact["path"]: artifact["exists"] for artifact in response.json()["artifacts"]}

        self.assertIn(missing_path, artifacts)
        self.assertFalse(artifacts[missing_path])


if __name__ == "__main__":
    unittest.main()
