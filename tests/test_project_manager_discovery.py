import pathlib
import tempfile
import unittest

from server_api.project_manager.discovery import (
    discover_project_manager_volumes,
    summarize_discovered_formats,
)


class ProjectManagerDiscoveryTests(unittest.TestCase):
    def test_discovery_finds_supported_files_and_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "vol_a.h5").touch()
            (root / "vol_b.tif").touch()
            (root / "vol_c.nii.gz").touch()

            zarr_dir = root / "dataset_a.zarr"
            zarr_dir.mkdir()
            (zarr_dir / ".zattrs").touch()

            n5_dir = root / "dataset_b.n5"
            n5_dir.mkdir()
            (n5_dir / "attributes.json").touch()

            image_stack = root / "retina_stack"
            image_stack.mkdir()
            (image_stack / "slice_001.png").touch()
            (image_stack / "slice_002.png").touch()

            (root / ".ignored_root.h5").touch()
            hidden_dir = root / ".hidden"
            hidden_dir.mkdir()
            (hidden_dir / "ignored.h5").touch()

            entries = discover_project_manager_volumes(root)
            rel_paths = {entry["rel_path"] for entry in entries}
            formats = {entry["rel_path"]: entry["format"] for entry in entries}
            format_counts = summarize_discovered_formats(entries)

            self.assertEqual(
                rel_paths,
                {
                    "vol_a.h5",
                    "vol_b.tif",
                    "vol_c.nii.gz",
                    "dataset_a.zarr",
                    "dataset_b.n5",
                    "retina_stack",
                },
            )
            self.assertEqual(formats["vol_a.h5"], ".h5")
            self.assertEqual(formats["vol_b.tif"], ".tif")
            self.assertEqual(formats["vol_c.nii.gz"], ".nii.gz")
            self.assertEqual(formats["dataset_a.zarr"], ".zarr")
            self.assertEqual(formats["dataset_b.n5"], ".n5")
            self.assertEqual(formats["retina_stack"], "image_stack")
            self.assertEqual(format_counts[".h5"], 1)
            self.assertEqual(format_counts[".tif"], 1)
            self.assertEqual(format_counts[".nii.gz"], 1)
            self.assertEqual(format_counts[".zarr"], 1)
            self.assertEqual(format_counts[".n5"], 1)
            self.assertEqual(format_counts["image_stack"], 1)


if __name__ == "__main__":
    unittest.main()
