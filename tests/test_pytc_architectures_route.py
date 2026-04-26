import unittest

from fastapi.testclient import TestClient

from server_api.main import app as server_api_app


class PytcArchitectureRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server_api_app)

    def test_pytc_architectures_returns_known_models(self):
        response = self.client.get("/pytc/architectures")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("architectures", payload)
        self.assertIn("unet_3d", payload["architectures"])
        self.assertIn("unet_plus_3d", payload["architectures"])
        self.assertIn("swinunetr", payload["architectures"])


if __name__ == "__main__":
    unittest.main()
