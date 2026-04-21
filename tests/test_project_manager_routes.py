import json
import os
import pathlib
import tempfile
import unittest

from fastapi.testclient import TestClient

import server_api.project_manager.router as pm_router_module
from server_api.main import app as server_api_app
from server_api.project_manager.template import build_default_users


class ProjectManagerRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server_api_app)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = pathlib.Path(self.temp_dir.name)
        self.original_metadata_override = pm_router_module._DATA_FILE_OVERRIDE
        self.original_data_root_override = pm_router_module._DATA_ROOT_OVERRIDE
        self.original_metadata_env = os.environ.get("PROJECT_METADATA_JSON")
        self.original_data_root_env = os.environ.get("DATA_ROOT_EM")
        pm_router_module._DATA_FILE_OVERRIDE = None
        pm_router_module._DATA_ROOT_OVERRIDE = None
        os.environ.pop("PROJECT_METADATA_JSON", None)
        os.environ.pop("DATA_ROOT_EM", None)

    def tearDown(self):
        pm_router_module._DATA_FILE_OVERRIDE = self.original_metadata_override
        pm_router_module._DATA_ROOT_OVERRIDE = self.original_data_root_override
        if self.original_metadata_env is None:
            os.environ.pop("PROJECT_METADATA_JSON", None)
        else:
            os.environ["PROJECT_METADATA_JSON"] = self.original_metadata_env
        if self.original_data_root_env is None:
            os.environ.pop("DATA_ROOT_EM", None)
        else:
            os.environ["DATA_ROOT_EM"] = self.original_data_root_env
        self.temp_dir.cleanup()

    def test_config_endpoint_updates_metadata_and_data_root(self):
        metadata_path = self.temp_path / "project_manager.json"
        data_root = self.temp_path / "h5-root"
        data_root.mkdir()

        response = self.client.post(
            "/api/pm/config",
            json={
                "metadata_path": str(metadata_path),
                "data_root": str(data_root),
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(pathlib.Path(payload["metadata_path"]), metadata_path.resolve())
        self.assertEqual(pathlib.Path(payload["data_root"]), data_root.resolve())
        self.assertTrue(payload["using_metadata_override"])
        self.assertTrue(payload["using_data_root_override"])

        data_response = self.client.get("/api/pm/data")
        self.assertEqual(data_response.status_code, 200)
        self.assertTrue(metadata_path.exists())

    def test_config_endpoint_rejects_missing_data_root(self):
        response = self.client.post(
            "/api/pm/config",
            json={"data_root": str(self.temp_path / "does-not-exist")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Data root must be an existing directory", response.text)

    def test_schema_endpoint_exposes_starter_template(self):
        response = self.client.get("/api/pm/schema")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("blank_template", payload)
        self.assertEqual(
            payload["blank_template"]["project_info"]["name"],
            "My EM Project",
        )
        self.assertIn("top_level_fields", payload)
        self.assertTrue(
            any(
                row["field"] == "volumes" and row["level"] == "required"
                for row in payload["top_level_fields"]
            )
        )
        self.assertIn(".tif", payload["supported_volume_inputs"])
        self.assertIn(".zarr", payload["supported_volume_inputs"])
        self.assertEqual(
            payload["valid_statuses"],
            ["todo", "in_progress", "done"],
        )

    def test_volume_patch_updates_status_and_assignee(self):
        metadata_path = self.temp_path / "project_manager.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "project_info": {"name": "Test Project"},
                    "users": build_default_users(),
                    "volumes": [
                        {
                            "id": "vol-1.h5",
                            "filename": "vol-1.h5",
                            "rel_path": "vol-1.h5",
                            "assignee": None,
                            "status": "todo",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        pm_router_module._DATA_FILE_OVERRIDE = str(metadata_path)

        response = self.client.patch(
            "/api/pm/volumes/vol-1.h5",
            json={"status": "in_progress", "assignee": "alex"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["volume"]["status"], "in_progress")
        self.assertEqual(payload["volume"]["assignee"], "alex")
        self.assertEqual(payload["global_progress"]["by_worker"]["alex"]["total"], 1)

        saved = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["volumes"][0]["status"], "in_progress")
        self.assertEqual(saved["volumes"][0]["assignee"], "alex")

    def test_reset_endpoint_restores_fresh_project_state(self):
        metadata_path = self.temp_path / "project_manager.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "project_info": {"name": "Loaded Project"},
                    "users": build_default_users(),
                    "volumes": [
                        {
                            "id": "vol-1.h5",
                            "filename": "vol-1.h5",
                            "rel_path": "vol-1.h5",
                            "assignee": "alex",
                            "status": "done",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        pm_router_module._DATA_FILE_OVERRIDE = str(metadata_path)

        response = self.client.post("/api/pm/data/reset")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["global_progress"]["total"], 0)
        self.assertEqual(payload["project_info"]["name"], "Project Manager")

        saved = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["volumes"], [])


if __name__ == "__main__":
    unittest.main()
