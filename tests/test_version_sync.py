import importlib.util
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory
import shutil


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_version_sync", ROOT / "scripts" / "verify_version_sync.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VersionSyncTests(unittest.TestCase):
    def test_stale_desktop_lock_cannot_pass_release_version_verification(self):
        files=('src/literary_engineering_studio/__init__.py','pyproject.toml','package.json',
               'package-lock.json','workers/pi-worker/package.json','workers/pi-worker/package-lock.json',
               'workers/pi-worker/src/main.ts','desktop/src-tauri/Cargo.toml',
               'desktop/src-tauri/Cargo.lock','desktop/src-tauri/tauri.conf.json',
               'src/literary_engineering_studio/application/compatibility_manifest.json')
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            for path in files:
                target=root/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,target)
            lock=root/'desktop/src-tauri/Cargo.lock'
            version=MODULE.verify_versions(ROOT)['version']
            lock.write_text(lock.read_text(encoding='utf-8').replace(
                'name = "arcvellum-desktop"\nversion = "'+version+'"',
                'name = "arcvellum-desktop"\nversion = "0.0.0"'),encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError,'cargo-lock'):
                MODULE.verify_versions(root)

    def test_all_public_version_declarations_match(self):
        result = MODULE.verify_versions(ROOT)
        self.assertTrue(result["ok"])
        self.assertRegex(result["version"], r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
