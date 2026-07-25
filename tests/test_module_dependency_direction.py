"""Architecture guardrails for the Studio -> Engine dependency direction."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from scripts.architecture_audit import scan_dependency_violations


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPOSITORY_ROOT / "src" / "literary_engineering_studio_engine"


class ModuleDependencyDirectionTests(unittest.TestCase):
    def test_embedded_engine_never_imports_studio_runtime(self):
        violations: list[str] = []
        for path in ENGINE_ROOT.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                if any(name == "literary_engineering_studio" or name.startswith("literary_engineering_studio.") for name in names):
                    violations.append(path.relative_to(REPOSITORY_ROOT).as_posix())
                    break
        self.assertEqual(violations, [])

    def test_studio_domain_boundaries_do_not_gain_forbidden_imports(self):
        self.assertEqual(scan_dependency_violations(REPOSITORY_ROOT), [])


if __name__ == "__main__":
    unittest.main()
