import os
import pathlib
import unittest

from fastapi.testclient import TestClient

from server_api.main import app as server_api_app


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SNEMI_ROOT = pathlib.Path(
    os.getenv(
        "PYTC_TEST_SNEMI_ROOT",
        REPO_ROOT.parent / "testing_data" / "snemi",
    )
)
TEST_INPUT_PATH = SNEMI_ROOT / "image" / "test-input.tif"
TRAIN_LABELS_PATH = SNEMI_ROOT / "seg" / "train-labels.tif"


@unittest.skipUnless(TEST_INPUT_PATH.exists(), "SNEMI fixture is not available")
class CheckFilesRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server_api_app)

    def test_check_files_marks_snemi_image_as_not_label(self):
        response = self.client.post(
            "/check_files",
            json={
                "filePath": str(TEST_INPUT_PATH),
                "folderPath": str(TEST_INPUT_PATH.parent),
                "name": TEST_INPUT_PATH.name,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"label": False})

    def test_check_files_marks_snemi_labels_as_label(self):
        response = self.client.post(
            "/check_files",
            json={
                "filePath": str(TRAIN_LABELS_PATH),
                "folderPath": str(TRAIN_LABELS_PATH.parent),
                "name": TRAIN_LABELS_PATH.name,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"label": True})

    def test_check_files_returns_error_payload_for_missing_path(self):
        missing_path = SNEMI_ROOT / "image" / "does-not-exist.tif"
        response = self.client.post(
            "/check_files",
            json={
                "filePath": str(missing_path),
                "folderPath": str(missing_path.parent),
                "name": missing_path.name,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.json())


if __name__ == "__main__":
    unittest.main()
