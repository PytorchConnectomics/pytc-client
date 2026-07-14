import os
import pathlib
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from server_pytc.services import model as model_service


class WorkerModelServiceTests(unittest.TestCase):
    def tearDown(self):
        model_service.cleanup_temp_files()

    def test_matches_pytc_mode_process_supports_legacy_cli(self):
        script_path = str(model_service._pytc_script_path())
        cmdline = [
            "/usr/bin/python",
            script_path,
            "--config",
            "/tmp/runtime.yaml",
            "--mode",
            "train",
        ]

        self.assertTrue(model_service._matches_pytc_mode_process(cmdline, "train"))
        self.assertFalse(model_service._matches_pytc_mode_process(cmdline, "test"))

    def test_matches_pytc_mode_process_supports_current_cli(self):
        script_path = str(model_service._pytc_script_path())
        train_cmdline = [
            "/usr/bin/python",
            script_path,
            "--config-file",
            "/tmp/runtime.yaml",
        ]
        inference_cmdline = [
            "/usr/bin/python",
            script_path,
            "--config-file",
            "/tmp/runtime.yaml",
            "--inference",
        ]

        self.assertTrue(model_service._matches_pytc_mode_process(train_cmdline, "train"))
        self.assertFalse(model_service._matches_pytc_mode_process(train_cmdline, "test"))
        self.assertTrue(
            model_service._matches_pytc_mode_process(inference_cmdline, "test")
        )
        self.assertFalse(
            model_service._matches_pytc_mode_process(inference_cmdline, "train")
        )

    def test_cleanup_temp_files_is_scoped_by_kind(self):
        training_file = tempfile.NamedTemporaryFile(delete=False)
        inference_file = tempfile.NamedTemporaryFile(delete=False)
        training_file.close()
        inference_file.close()

        model_service._temp_files["training"].append(training_file.name)
        model_service._temp_files["inference"].append(inference_file.name)

        model_service.cleanup_temp_files("training")

        self.assertFalse(pathlib.Path(training_file.name).exists())
        self.assertTrue(pathlib.Path(inference_file.name).exists())

        model_service.cleanup_temp_files("inference")

        self.assertFalse(pathlib.Path(inference_file.name).exists())

    def test_ollama_unload_is_disabled_by_default(self):
        with patch.dict(
            os.environ,
            {
                "OLLAMA_MODEL": "qwen3.6:27b",
                "PYTC_HELPER_OLLAMA_MODEL": "",
                "OLLAMA_HELPER_MODEL": "",
            },
            clear=False,
        ):
            os.environ.pop("PYTC_UNLOAD_OLLAMA_BEFORE_TRAINING", None)
            with patch("server_pytc.services.model.subprocess.run") as run_mock:
                unloaded = model_service._unload_ollama_before_gpu_training()

        self.assertEqual(unloaded, [])
        run_mock.assert_not_called()

    def test_ollama_unload_can_be_enabled_explicitly(self):
        run_result = MagicMock(returncode=0, stdout="")
        with patch.dict(
            os.environ,
            {
                "PYTC_UNLOAD_OLLAMA_BEFORE_TRAINING": "1",
                "OLLAMA_MODEL": "qwen3.6:27b",
                "PYTC_HELPER_OLLAMA_MODEL": "",
                "OLLAMA_HELPER_MODEL": "",
            },
            clear=False,
        ):
            with patch(
                "server_pytc.services.model.subprocess.run",
                return_value=run_result,
            ) as run_mock:
                unloaded = model_service._unload_ollama_before_gpu_training()

        self.assertEqual(unloaded, ["qwen3.6:27b"])
        run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
