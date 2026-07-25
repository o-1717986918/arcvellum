from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.architecture_audit import (
    audit_repository,
    compare_with_baseline,
    load_baseline,
    scan_dependency_violations,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPOSITORY_ROOT / "architecture" / "quality-baseline.json"


class ArchitectureAuditTests(unittest.TestCase):
    def test_committed_baseline_accepts_the_current_repository(self):
        report = audit_repository(REPOSITORY_ROOT)
        violations = compare_with_baseline(report, load_baseline(BASELINE_PATH))

        self.assertEqual(violations, [])

    def test_dependency_rules_reject_each_forbidden_direction(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "src/literary_engineering_studio/projections/bad.py", "from ..runtime import writeback\n")
            _write(root / "src/literary_engineering_studio/orchestration/bad.py", "from ..api import routers\n")
            _write(
                root / "src/literary_engineering_studio/automation/bad.py",
                "from literary_engineering_studio_engine.routes.scene import definition\n",
            )
            _write(
                root / "src/literary_engineering_studio_engine/bad.py",
                "from literary_engineering_studio.runtime import worker\n",
            )

            violations = scan_dependency_violations(root)

        self.assertEqual(len(violations), 4)
        self.assertTrue(any("Engine must not import Studio" in item for item in violations))
        self.assertTrue(any("projections must not import writeback/promotion" in item for item in violations))
        self.assertTrue(any("orchestration must not import API" in item for item in violations))
        self.assertTrue(any("automation must not import Engine route implementations" in item for item in violations))

    def test_synthetic_repository_exposes_budget_cycle_facade_and_route_debt(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "src/literary_engineering_studio/sample"
            _write(sample / "__init__.py", "")
            _write(sample / "a.py", "from . import b\n")
            _write(sample / "b.py", "from . import a\n")
            _write(
                sample / "legacy.py",
                '"""Compatibility facade."""\nfrom . import a\n',
            )
            _write(
                sample / "large.py",
                "\n".join(["value = 1"] * 501) + "\n",
            )
            route_source = (
                "router = object()\n"
                "@router.get('/duplicate')\n"
                "def endpoint():\n"
                "    return None\n"
            )
            _write(root / "src/literary_engineering_studio/api/routers/one.py", route_source)
            _write(root / "src/literary_engineering_studio/api/routers/two.py", route_source)

            report = audit_repository(root)

        self.assertIn("src/literary_engineering_studio/sample/large.py", report["oversized_files"])
        self.assertIn(
            [
                "literary_engineering_studio.sample.a",
                "literary_engineering_studio.sample.b",
            ],
            report["import_cycles"],
        )
        self.assertEqual(
            report["facade_dependencies"]["literary_engineering_studio.sample.legacy"],
            ["literary_engineering_studio.sample.a"],
        )
        self.assertEqual(
            report["duplicate_routes"]["studio:GET:/duplicate"],
            [
                "src/literary_engineering_studio/api/routers/one.py",
                "src/literary_engineering_studio/api/routers/two.py",
            ],
        )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
