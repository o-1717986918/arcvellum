from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.architecture_audit import (
    audit_repository,
    baseline_from_report,
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
            _write(
                root / "src/literary_engineering_studio/projections/write_bad.py",
                "from ..application.assets.promotion import promote\n",
            )
            _write(
                root / "src/literary_engineering_studio/runtimes/route_bad.py",
                "from literary_engineering_studio_engine.routes.scene import definition\n",
            )

            violations = scan_dependency_violations(root)

        self.assertEqual(len(violations), 6)
        self.assertTrue(any("Engine must not import Studio" in item for item in violations))
        self.assertTrue(any("projections must not import writeback/promotion" in item for item in violations))
        self.assertTrue(any("orchestration must not import API" in item for item in violations))
        self.assertTrue(any("automation must not import Engine route implementations" in item for item in violations))
        self.assertTrue(any("projections must not import application write services" in item for item in violations))
        self.assertTrue(any("Runtime adapters must not import Engine route implementations" in item for item in violations))

    def test_new_layer_debt_is_rejected_while_existing_debt_can_shrink(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / "src/literary_engineering_studio/application/legacy.py",
                "from literary_engineering_studio.api_server import create_app\n",
            )
            _write(
                root / "src/literary_engineering_studio/legacy_engine.py",
                "from literary_engineering_studio_engine.literary.style import style_status\n",
            )
            _write(
                root / "src/literary_engineering_studio/projections/legacy.py",
                "from ..application.assets.loader import AssetLoader\n",
            )
            _write(
                root / "client/src/features/alpha/Alpha.vue",
                'import Beta from "@/features/beta/Beta.vue";\n',
            )
            baseline = baseline_from_report(audit_repository(root))

            _write(
                root / "src/literary_engineering_studio/application/new_debt.py",
                "from literary_engineering_studio.runtimes.opencode import OpenCodeRuntime\n",
            )
            _write(
                root / "src/literary_engineering_studio/new_engine.py",
                "from literary_engineering_studio_engine.workflow.runner import run_workflow\n",
            )
            _write(
                root / "src/literary_engineering_studio/projections/new_debt.py",
                "from ..application.assets.loader import AssetLoader\n",
            )
            _write(
                root / "client/src/features/alpha/New.vue",
                'import Gamma from "@/features/gamma/Gamma.vue";\n',
            )
            violations = compare_with_baseline(audit_repository(root), baseline)

        self.assertTrue(any("new application-to-adapter dependency" in item for item in violations))
        self.assertTrue(any("new Studio-to-Engine dependency" in item for item in violations))
        self.assertTrue(any("new projection-to-application dependency" in item for item in violations))
        self.assertTrue(any("new cross-feature Vue component dependency" in item for item in violations))

    def test_engine_public_api_is_not_counted_as_internal_layout_debt(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / "src/literary_engineering_studio/public_consumer.py",
                "from literary_engineering_studio_engine.public.projects import init_work_project\n",
            )

            report = audit_repository(root)

        self.assertEqual(report["studio_engine_dependencies"], {})

    def test_studio_engine_internal_import_is_a_zero_tolerance_violation(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / "src/literary_engineering_studio/internal_consumer.py",
                "from literary_engineering_studio_engine.workflow.state import build_workflow_state\n",
            )

            violations = scan_dependency_violations(root)

        self.assertEqual(len(violations), 1)
        self.assertIn("Studio must use Engine public API", violations[0])

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

    def test_generated_client_contract_is_not_manual_file_debt(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated = root / "client/src/types/generated/api-schema.d.ts"
            _write(generated, "\n".join(["export type Generated = unknown;"] * 700) + "\n")

            report = audit_repository(root)

        self.assertNotIn("client/src/types/generated/api-schema.d.ts", report["oversized_files"])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
