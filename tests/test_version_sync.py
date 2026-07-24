import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_version_sync", ROOT / "scripts" / "verify_version_sync.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VersionSyncTests(unittest.TestCase):
    def test_all_public_version_declarations_match(self):
        result = MODULE.verify_versions(ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "0.95.0")


if __name__ == "__main__":
    unittest.main()
