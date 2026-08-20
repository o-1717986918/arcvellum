from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest

from literary_engineering_studio.application.compatibility import (
    compatibility_summary,
    load_compatibility_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class CompatibilityManifestTests(unittest.TestCase):
    def test_manifest_declares_runtime_defaults_and_deprecated_aliases(self):
        manifest = load_compatibility_manifest()

        self.assertEqual(
            manifest["schema"],
            "arcvellum/compatibility-manifest/v1",
        )
        self.assertEqual(
            manifest["runtime_defaults"]["scene_generation"],
            "platform-agent-task",
        )
        self.assertEqual(
            manifest["runtime_defaults"]["model_invocation"],
            "runner-managed",
        )
        aliases = manifest["deprecated_aliases"]
        self.assertTrue(aliases)
        self.assertTrue(
            all(item["canonical_module"] for item in aliases),
        )
        providers = {
            item["id"]: item for item in manifest["legacy_providers"]
        }
        self.assertFalse(providers["http-chat"]["production_default"])
        self.assertFalse(providers["dry-run"]["production_default"])
        public_api = manifest["engine_public_api"]
        self.assertEqual(public_api["status"], "stable-cross-package-surface")
        self.assertFalse(public_api["internal_imports_allowed"])
        self.assertEqual(len(public_api["modules"]), 7)
        self.assertTrue(
            all(
                module.startswith("literary_engineering_studio_engine.public.")
                for module in public_api["modules"]
            )
        )

    def test_summary_does_not_expose_a_second_runtime_default(self):
        summary = compatibility_summary()

        self.assertEqual(summary["default_agent_runtime"], "opencode")
        self.assertEqual(summary["model_invocation"], "runner-managed")
        self.assertGreater(summary["deprecated_alias_count"], 0)

    def test_release_audit_accepts_the_current_source_tree(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "verify_compatibility_surface.py"),
                "--root",
                str(ROOT),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("compatibility surface: pass", result.stdout)


if __name__ == "__main__":
    unittest.main()
