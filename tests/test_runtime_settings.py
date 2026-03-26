import importlib
import os
import unittest
from unittest.mock import patch

import runtime_settings


class RuntimeSettingsTests(unittest.TestCase):
    def test_default_allowed_origins_cover_local_dev_and_packaged_electron(self):
        with patch.dict(os.environ, {}, clear=True):
            module = importlib.reload(runtime_settings)

        self.assertEqual(
            module.get_allowed_origins(),
            ["http://localhost:3000", "http://127.0.0.1:3000", "null"],
        )

    def test_allowed_origins_can_be_overridden_by_env(self):
        with patch.dict(
            os.environ,
            {"PYTC_ALLOWED_ORIGINS": "http://example.com, http://demo.local"},
            clear=True,
        ):
            module = importlib.reload(runtime_settings)
            self.assertEqual(
                module.get_allowed_origins(),
                ["http://example.com", "http://demo.local"],
            )

    def test_auth_secret_uses_env_when_present(self):
        with patch.dict(
            os.environ,
            {"PYTC_AUTH_SECRET": "test-secret"},
            clear=True,
        ):
            module = importlib.reload(runtime_settings)

        self.assertEqual(module.get_auth_secret(), "test-secret")

    def test_neuroglancer_public_base_uses_env_when_present(self):
        with patch.dict(
            os.environ,
            {"PYTC_NEUROGLANCER_PUBLIC_BASE": "https://viewer.example.com/ng/"},
            clear=True,
        ):
            module = importlib.reload(runtime_settings)
            self.assertEqual(
                module.get_neuroglancer_public_base(),
                "https://viewer.example.com/ng",
            )


if __name__ == "__main__":
    unittest.main()
