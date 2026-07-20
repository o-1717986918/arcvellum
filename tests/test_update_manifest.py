from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "packaging" / "build_update_manifest.py"
SPEC = importlib.util.spec_from_file_location("arcvellum_build_update_manifest", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
build_manifest = MODULE.build_manifest


class UpdateManifestTests(unittest.TestCase):
    def test_signed_artifact_produces_updater_manifest_and_checksums(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "bundle" / "nsis"
            bundle.mkdir(parents=True)
            archive = bundle / "ArcVellum_0.4.0_x64-setup.nsis.zip"
            archive.write_bytes(b"signed-update")
            Path(str(archive) + ".sig").write_text("test-signature", encoding="utf-8")
            (bundle / "ArcVellum_0.4.0_x64-setup.exe").write_bytes(b"installer")
            output = root / "release"

            result = build_manifest(
                bundle_dir=root / "bundle",
                output_dir=output,
                version="0.4.0",
                base_url="https://example.test/releases/latest/download",
                notes="Release notes",
            )
            payload = json.loads((output / "latest.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["version"], "0.4.0")
        self.assertEqual(payload["platforms"]["windows-x86_64"]["signature"], "test-signature")
        self.assertTrue(payload["platforms"]["windows-x86_64"]["url"].endswith(archive.name))
        self.assertIn("SHA256SUMS.txt", result["files"])

    def test_unsigned_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "bundle"
            bundle.mkdir()
            (bundle / "ArcVellum.nsis.zip").write_bytes(b"unsigned")
            with self.assertRaisesRegex(RuntimeError, "missing its signature"):
                build_manifest(
                    bundle_dir=bundle,
                    output_dir=root / "release",
                    version="0.4.0",
                    base_url="https://example.test",
                    notes="",
                )

    def test_signed_tauri_v2_exe_is_the_updater_and_stale_installer_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "bundle" / "nsis"
            bundle.mkdir(parents=True)
            current = bundle / "ArcVellum_0.5.0_x64-setup.exe"
            current.write_bytes(b"signed-installer-and-updater")
            Path(str(current) + ".sig").write_text("current-signature", encoding="utf-8")
            (bundle / "ArcVellum_0.3.0_x64-setup.exe").write_bytes(b"stale")
            output = root / "release"

            result = build_manifest(
                bundle_dir=root / "bundle",
                output_dir=output,
                version="0.5.0",
                base_url="https://example.test/releases/latest/download",
                notes="Release notes",
            )
            payload = json.loads((output / "latest.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["platforms"]["windows-x86_64"]["signature"], "current-signature")
        self.assertTrue(payload["platforms"]["windows-x86_64"]["url"].endswith(current.name))
        self.assertIn(current.name, result["files"])
        self.assertNotIn("ArcVellum_0.3.0_x64-setup.exe", result["files"])


if __name__ == "__main__":
    unittest.main()
