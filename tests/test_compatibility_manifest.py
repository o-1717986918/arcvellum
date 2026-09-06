from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
import unittest
import warnings

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
            "arcvellum/compatibility-manifest/v2",
        )
        current = manifest["current_release"]
        self.assertEqual(current["version"], "0.99.5")
        self.assertEqual(
            current["defaults"]["agent_runtime"],
            "pi-worker",
        )
        self.assertEqual(
            current["defaults"]["scene_generation"],
            "arcvellum-worker-task",
        )
        self.assertEqual(
            current["defaults"]["model_invocation"],
            "runner-managed",
        )
        compatibility = manifest["compatibility"]
        aliases = compatibility["deprecated_aliases"]
        self.assertTrue(aliases)
        self.assertTrue(
            all(item["canonical_module"] for item in aliases),
        )
        providers = {
            item["id"]: item for item in compatibility["legacy_providers"]
        }
        self.assertFalse(providers["http-chat"]["production_default"])
        self.assertFalse(providers["dry-run"]["production_default"])
        public_api = compatibility["engine_public_api"]
        self.assertEqual(public_api["status"], "stable-cross-package-surface")
        self.assertFalse(public_api["internal_imports_allowed"])
        self.assertEqual(len(public_api["modules"]), 7)
        self.assertTrue(
            all(
                module.startswith("literary_engineering_studio_engine.public.")
                for module in public_api["modules"]
            )
        )
        migration = compatibility["schema_migration"]
        self.assertEqual(migration["native_project_schema"], "arcvellum/project/v2")
        self.assertEqual(migration["native_task_schema"], "arcvellum/task/v2")
        self.assertEqual(migration["unknown_schema_policy"], "retain-and-report")
        history = manifest["history"]["runtime_defaults"]
        self.assertIn(
            {"release_line": "0.97", "agent_runtime": "opencode", "status": "retired-default"},
            history,
        )

    def test_summary_does_not_expose_a_second_runtime_default(self):
        summary = compatibility_summary()

        self.assertEqual(summary["release_version"], "0.99.5")
        self.assertEqual(summary["default_agent_runtime"], "pi-worker")
        self.assertEqual(summary["model_invocation"], "runner-managed")
        self.assertGreater(summary["deprecated_alias_count"], 0)

    def test_declared_deprecated_aliases_warn_and_resolve_to_canonical_modules(self):
        aliases = load_compatibility_manifest()["compatibility"]["deprecated_aliases"]

        for item in aliases:
            alias = item["module"]
            canonical = item["canonical_module"]
            sys.modules.pop(alias, None)
            with self.subTest(alias=alias), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                imported = importlib.import_module(alias)
                implementation = importlib.import_module(canonical)
                self.assertIs(imported, implementation)
                self.assertTrue(any(issubclass(entry.category, DeprecationWarning) for entry in caught))

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
