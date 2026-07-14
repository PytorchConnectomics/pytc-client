import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database as auth_database
from server_api.auth import models
from server_api.main import app as server_api_app
from server_api.main import _normalize_api_compat_path


class ApiCompatibilityRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/api-compatibility-test.db"
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

    def tearDown(self):
        server_api_app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_compat_workflow_current_matches_canonical_route(self):
        canonical = self.client.get("/api/workflows/current")
        legacy = self.client.get("/api/api/workflows/current")

        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(
            canonical.json()["workflow"]["id"],
            legacy.json()["workflow"]["id"],
        )
        self.assertEqual(canonical.json()["events"], legacy.json()["events"])

    def test_compat_files_root_and_project_suggestions_match_canonical(self):
        canonical_root = self.client.get("/files", params={"parent": "root"})
        legacy_root = self.client.get("/api/files", params={"parent": "root"})

        self.assertEqual(canonical_root.status_code, 200)
        self.assertEqual(legacy_root.status_code, 200)
        self.assertEqual(canonical_root.json(), legacy_root.json())

        canonical_suggestions = self.client.get("/files/project-suggestions")
        legacy_suggestions = self.client.get("/api/files/project-suggestions")

        self.assertEqual(canonical_suggestions.status_code, 200)
        self.assertEqual(legacy_suggestions.status_code, 200)
        canonical_payload = canonical_suggestions.json()
        legacy_payload = legacy_suggestions.json()
        self.assertEqual(len(canonical_payload), len(legacy_payload))

        canonical_lookup = {item["id"]: item for item in canonical_payload}
        for item in legacy_payload:
            canonical_item = canonical_lookup[item["id"]]
            self.assertEqual(canonical_item["name"], item["name"])
            self.assertEqual(canonical_item["directory_path"], item["directory_path"])
            self.assertEqual(canonical_item["description"], item["description"])
            self.assertEqual(canonical_item["recommended"], item["recommended"])
            self.assertEqual(canonical_item["already_mounted"], item["already_mounted"])
            self.assertEqual(canonical_item["mounted_root_id"], item["mounted_root_id"])

    def test_compat_log_event_matches_canonical(self):
        payload = {
            "event": "frontend-compat-test",
            "level": "INFO",
            "message": "api compatibility check",
            "source": "compat-test",
            "sessionId": "api-compat-session",
            "url": "http://localhost/tests",
            "data": {"status": "ok"},
        }
        canonical = self.client.post("/app/log-event", json=payload)
        legacy = self.client.post("/api/app/log-event", json=payload)

        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(canonical.json(), {"status": "ok"})
        self.assertEqual(legacy.json(), {"status": "ok"})

    def test_compat_neuroglancer_routes_match_canonical_validation(self):
        canonical = self.client.post("/neuroglancer", json={})
        legacy = self.client.post("/api/neuroglancer", json={})

        self.assertEqual(canonical.status_code, legacy.status_code)
        self.assertGreaterEqual(canonical.status_code, 400)
        self.assertLess(canonical.status_code, 500)

        canonical_proofread = self.client.post("/neuroglancer/proofread", json={})
        legacy_proofread = self.client.post("/api/neuroglancer/proofread", json={})

        self.assertEqual(canonical_proofread.status_code, legacy_proofread.status_code)
        self.assertGreaterEqual(canonical_proofread.status_code, 400)
        self.assertLess(canonical_proofread.status_code, 500)

    def test_unrelated_paths_are_not_remapped(self):
        response = self.client.get("/api/filesystem")
        self.assertEqual(response.status_code, 404)
        response = self.client.get("/api/apply")
        self.assertEqual(response.status_code, 404)


class ApiCompatibilityPathNormalizationTests(unittest.TestCase):
    def test_runtime_paths_under_api_prefix_map_to_canonical_routes(self):
        self.assertEqual(
            _normalize_api_compat_path("/api/start_model_training"),
            "/start_model_training",
        )
        self.assertEqual(
            _normalize_api_compat_path("/api/start_model_inference"),
            "/start_model_inference",
        )
        self.assertEqual(
            _normalize_api_compat_path("/api/stop_model_training"),
            "/stop_model_training",
        )
        self.assertEqual(
            _normalize_api_compat_path("/api/training_status"),
            "/training_status",
        )
        self.assertEqual(
            _normalize_api_compat_path("/api/get_tensorboard_status"),
            "/get_tensorboard_status",
        )

    def test_unrelated_api_prefixes_are_not_rewritten(self):
        self.assertIsNone(_normalize_api_compat_path("/api/filesystem"))
        self.assertIsNone(_normalize_api_compat_path("/api/apply"))
