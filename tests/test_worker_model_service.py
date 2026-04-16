import pathlib
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
