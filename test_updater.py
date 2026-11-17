"""Proves de regressió de l'actualitzador de releases de Windows."""

import os
import tempfile
import unittest
import zipfile

from core.update_manager import (
    extract_windows_release,
    get_windows_asset,
    is_newer_release,
    make_windows_update_script,
    parse_version,
)


class ReleaseUpdaterTests(unittest.TestCase):
    def test_versions_are_compared_semantically(self):
        self.assertTrue(is_newer_release("1.1.2", "v1.1.3"))
        self.assertTrue(is_newer_release("1.1.9", "v1.1.10"))
        self.assertFalse(is_newer_release("1.1.4", "v1.1.4"))
        self.assertFalse(is_newer_release("1.1.4", "v1.1.3"))
        self.assertEqual(parse_version("v1.1.4"), (1, 1, 4))
        with self.assertRaises(ValueError):
            parse_version("a-random-commit-hash")

    def test_release_asset_is_exact_version(self):
        release = {
            "tag_name": "v1.1.4",
            "assets": [
                {"name": "source.zip", "browser_download_url": "https://github.com/example/source.zip"},
                {
                    "name": "PodcastsAmbMatxa-v1.1.4-Windows.zip",
                    "browser_download_url": (
                        "https://github.com/miquelangelfuentes/podcasts-amb-matxa/"
                        "releases/download/v1.1.4/PodcastsAmbMatxa-v1.1.4-Windows.zip"
                    ),
                },
            ],
        }
        self.assertEqual(
            get_windows_asset(release)["name"],
            "PodcastsAmbMatxa-v1.1.4-Windows.zip",
        )
        with self.assertRaises(ValueError):
            get_windows_asset({"tag_name": "v1.1.4", "assets": release["assets"][:1]})

    @staticmethod
    def make_zip(path, bad_name=None):
        with zipfile.ZipFile(path, "w") as archive:
            for name in (
                "PodcastsAmbMatxa/PodcastsAmbMatxa.exe",
                "PodcastsAmbMatxa/_internal/assets/previews/preview_styletts_2_joana.wav",
                "PodcastsAmbMatxa/_internal/assets/previews/preview_styletts_2_enric.wav",
            ):
                archive.writestr(name, b"valid-package-content")
            if bad_name:
                archive.writestr(bad_name, b"unexpected-file")

    def test_extract_validated_package(self):
        with tempfile.TemporaryDirectory() as root:
            zip_path = os.path.join(root, "build.zip")
            self.make_zip(zip_path)
            dest = os.path.join(root, "extracted")
            out = extract_windows_release(zip_path, dest)
            self.assertTrue(os.path.isfile(os.path.join(out, "PodcastsAmbMatxa.exe")))
            self.assertTrue(os.path.isfile(os.path.join(
                out, "_internal", "assets", "previews", "preview_styletts_2_joana.wav"
            )))

    def test_reject_traversal_and_missing_executable(self):
        with tempfile.TemporaryDirectory() as root:
            zip_path = os.path.join(root, "build.zip")
            self.make_zip(zip_path, "../outside.txt")
            with self.assertRaises(ValueError):
                extract_windows_release(zip_path, os.path.join(root, "extracted"))
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("PodcastsAmbMatxa/placeholder.txt", b"missing")
            with self.assertRaises(ValueError):
                extract_windows_release(zip_path, os.path.join(root, "extracted"))

    def test_process_safe_copy_and_integrity_checks(self):
        script = make_windows_update_script(
            source_dir=os.path.abspath(os.path.join("tmp", "update")),
            install_dir=os.path.abspath(os.path.join("tmp", "current")),
            exe_path=os.path.abspath(os.path.join("tmp", "current", "PodcastsAmbMatxa.exe")),
            parent_pid=12345,
            version="v1.1.4",
            staging_dir=os.path.abspath(os.path.join("tmp", "update")),
        )
        self.assertIn("Get-Process -Id $ParentPid", script)
        self.assertIn("robocopy.exe", script)
        self.assertIn("/XD models .venv", script)
        self.assertIn("if ($copyCode -ge 8)", script)
        self.assertIn("Get-FileHash", script)
        self.assertIn("Start-Process -FilePath $TargetExe", script)
        self.assertNotIn(" /XO ", script)
        self.assertNotIn("timeout /t 2", script)

    def test_powershell_quoting(self):
        script = make_windows_update_script(
            source_dir=os.path.abspath("/tmp/user's/update"),
            install_dir=os.path.abspath("/tmp/user's/app"),
            exe_path=os.path.abspath("/tmp/user's/app/PodcastsAmbMatxa.exe"),
            parent_pid=123,
            version="1.1.4",
            staging_dir=os.path.abspath("/tmp/user's/update"),
        )
        self.assertIn("user''s", script)


if __name__ == "__main__":
    unittest.main()
