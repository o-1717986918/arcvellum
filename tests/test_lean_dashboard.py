import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.projections.core_read_models import build_dashboard


class LeanDashboardTests(unittest.TestCase):
    def test_lean_project_does_not_build_legacy_workflow_dashboard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "plot" / "word_budget").mkdir(parents=True)
            (root / "plot" / "lean_project_plan.json").write_text(
                json.dumps({"chapters": [{"chapter_id": "chapter_0001"}], "scenes": [{"scene_id": "scene_0001"}]}),
                encoding="utf-8",
            )
            (root / "plot" / "word_budget" / "word_budget.json").write_text(
                json.dumps({"totals": {"scene_count": 2}}), encoding="utf-8",
            )
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text("scene_id: scene_0001\n", encoding="utf-8")
            (root / "workflow" / "scene_commits").mkdir(parents=True)
            (root / "workflow" / "scene_commits" / "scene_0001.json").write_text("{}", encoding="utf-8")
            with patch(
                "literary_engineering_studio.projections.core_read_models.project_workflow_dashboard",
                side_effect=AssertionError("legacy dashboard called"),
            ):
                dashboard = build_dashboard({}, root, literary_kernel="lean-v2")
            self.assertEqual(dashboard["summary"]["literary_kernel"], "lean-v2")
            self.assertEqual(dashboard["summary"]["target_scene_count"], 2)
            self.assertEqual(dashboard["summary"]["pending_task_count"], 0)
            self.assertEqual(dashboard["route_audits"][1]["blocking_count"], 1)


if __name__ == "__main__":
    unittest.main()
