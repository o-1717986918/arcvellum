from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.review.longform_audit import build_longform_audit
from literary_engineering_studio_engine.literary.review.longform_contract import (
    LONGFORM_AUDIT_SCHEMA,
    LONGFORM_AUDIT_SOURCE_PATHS,
    audit_continuity_ledgers,
    longform_audit_gate_errors,
    longform_input_snapshot,
)
from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.sandbox import stage_task
from literary_engineering_studio_engine.routes.review.blueprints import review_audit_blueprint_for_state
from literary_engineering_studio_engine.routes.review.definition import _committee_review_gate_errors
from literary_engineering_studio_engine.workflow.audit.service import build_route_gates


class LongformQualityContractTests(unittest.TestCase):
    def test_longform_blueprint_stages_every_freshness_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            self._write_representative_longform_inputs(project)
            task_markdown = project / "workflow" / "tasks" / "longform.agent_tasks.md"
            task_markdown.parent.mkdir(parents=True)
            task_markdown.write_text("# deterministic longform audit\n", encoding="utf-8")
            blueprint = review_audit_blueprint_for_state(
                project,
                "longform-audit-file",
                "run longform audit",
            )
            self.assertEqual(tuple(blueprint["source_paths"]), LONGFORM_AUDIT_SOURCE_PATHS)
            task = TaskPackage(
                project_root=project,
                task_json_path=project / "workflow" / "tasks" / "longform.task.json",
                task_markdown_path=task_markdown,
                payload={
                    "task_id": "review-and-audit-project-review-longform-audit-file",
                    "route": "review-and-audit",
                    "current_state": "longform-audit-file",
                    **blueprint,
                },
            )

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="deterministic-engine",
                materialize_agent_view=False,
            )
            result = build_longform_audit(sandbox.control_workspace, target_length=0)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["input_snapshot"], longform_input_snapshot(project))
            self.assertEqual(payload["input_snapshot"]["file_count"], 15)

    def test_quality_gate_recomputes_blockers_and_input_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            scene = root / "scenes" / "scene_0001.yaml"
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")
            payload = {
                "schema": LONGFORM_AUDIT_SCHEMA,
                "input_snapshot": longform_input_snapshot(root),
                "summary": {"blocking_issue_count": 1},
                "issues": [
                    {
                        "severity": "medium",
                        "category": "word_budget",
                        "subject": "plot/word_budget/word_budget.json",
                        "message": "剧情库存不足",
                    }
                ],
            }

            self.assertEqual(longform_audit_gate_errors(root, payload, require_clean=False), [])
            clean_errors = longform_audit_gate_errors(root, payload, require_clean=True)
            self.assertIn("deterministic blocking", clean_errors[-1])

            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0002\n", encoding="utf-8")
            stale = longform_audit_gate_errors(root, payload, require_clean=False)
            self.assertIn("stale", stale[0])

    def test_continuity_ledger_reports_overdue_and_unsupported_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            questions = root / "plot" / "reader_questions" / "ledger.json"
            promises = root / "plot" / "promises" / "ledger.json"
            questions.parent.mkdir(parents=True)
            promises.parent.mkdir(parents=True)
            schema = "literary-engineering-workbench/continuity-ledger/v1"
            questions.write_text(
                json.dumps(
                    {
                        "schema": schema,
                        "reader_questions": [
                            {"id": "q1", "status": "open", "target_window": "scene_0001"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            promises.write_text(
                json.dumps(
                    {
                        "schema": schema,
                        "promises": [
                            {"id": "p1", "status": "resolved", "due_window": "scene_0002"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            audit = audit_continuity_ledgers(root, ["scene_0001", "scene_0002"])

            self.assertEqual(audit["collections"]["reader_questions"]["overdue_count"], 1)
            messages = [item["message"] for item in audit["issues"]]
            self.assertTrue(any("越过目标窗口" in message for message in messages))
            self.assertTrue(any("缺少正文兑现证据" in message for message in messages))

    def test_longform_audit_consumes_book_rhythm_and_optional_viewpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "project.yaml").write_text("project:\n  target_length: 0\n", encoding="utf-8")
            for index, viewpoint in ((1, "林"), (2, "林")):
                (root / "scenes" / f"scene_{index:04d}.yaml").write_text(
                    "\n".join(
                        [
                            f"scene_id: scene_{index:04d}",
                            "volume_id: volume_01",
                            f"chapter_id: chapter_{index:04d}",
                            "location: 塔楼",
                            "participants: [林]",
                            f"viewpoint: {viewpoint}",
                            "scene_goal: 识别信号",
                            "narrative_rhythm:",
                            "  rhythm_role: conflict",
                            "  pace: balanced",
                            "  scene_function: [推进主线]",
                            "  scene_turn: 信号指向盟友",
                            "  reader_effect: 安心转为怀疑",
                            "  tension_curve: [2, 4, 3]",
                            "scene_bridge:",
                            "  incoming_pressure: 上一场留下未解信号",
                            "  outgoing_hook: 盟友即将抵达",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )

            result = build_longform_audit(root, target_length=0)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertIn("book", payload["macro_rhythm"])
            self.assertIn("volumes", payload["macro_rhythm"])
            self.assertEqual(payload["summary"]["viewpoint_distribution"], {"林": 2})
            self.assertEqual(payload["input_snapshot"], longform_input_snapshot(root))

    def test_committee_and_export_cannot_override_longform_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: Gate\n", encoding="utf-8")
            longform_dir = root / "reviews" / "longform"
            agent_dir = root / "reviews" / "agent"
            longform_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)
            (root / "plot").mkdir(exist_ok=True)
            blocker = {
                "severity": "high",
                "category": "narrative_rhythm_curve",
                "subject": "chapter_0001",
                "message": "缺少张力曲线",
            }
            audit = {
                "schema": LONGFORM_AUDIT_SCHEMA,
                "input_snapshot": longform_input_snapshot(root),
                "summary": {"blocking_issue_count": 1},
                "issues": [blocker],
            }
            (longform_dir / "longform_audit.json").write_text(json.dumps(audit), encoding="utf-8")
            (longform_dir / "longform_audit.md").write_text("# audit\n", encoding="utf-8")
            (root / "plot" / "longform_graph.json").write_text("{}", encoding="utf-8")
            committee = {
                "schema": "literary-engineering-workbench/committee-review-agent/v1",
                "subject": "project-final-audit",
                "final_recommendation": "approve",
                "reviewers": [],
                "disagreements": [],
                "action_items": [],
                "source_paths": ["reviews/longform/longform_audit.json"],
            }
            (agent_dir / "committee_project-final-audit.json").write_text(json.dumps(committee), encoding="utf-8")
            (agent_dir / "committee_project-final-audit.md").write_text("# committee\n", encoding="utf-8")

            committee_errors = _committee_review_gate_errors(root, require_approve=True)
            self.assertTrue(any("deterministic blocking" in error for error in committee_errors))
            gates = build_route_gates(root, "export-and-release", [])
            longform_gate = next(item for item in gates if item["key"] == "review:longform-audit")
            self.assertEqual(longform_gate["status"], "fail")

    @staticmethod
    def _write_representative_longform_inputs(root: Path) -> None:
        files = {
            "project.yaml": "project:\n  title: Contract\n",
            "scenes/scene_0001.yaml": "scene_id: scene_0001\nchapter_id: chapter_0001\n",
            "drafts/scenes/scene_0001.md": "正文。\n",
            "drafts/compositions/scene_0001_composition.json": "{}\n",
            "drafts/promotions/scene_0001_promotion.json": "{}\n",
            "memory/context_packets/scene_0001.md": "# Context\n",
            "memory/context_packets/scene_0001.trace.json": "{}\n",
            "plot/chapters/chapter_0001.json": "{}\n",
            "plot/foreshadowing.csv": "id,status\nF1,open\n",
            "plot/promises/ledger.json": "{}\n",
            "plot/reader_questions/ledger.json": "{}\n",
            "plot/rhythm_plan.json": "{}\n",
            "plot/word_budget/word_budget.json": "{}\n",
            "reviews/scene_0001-review.md": "- 结论： pass\n",
            "reviews/agent/scene_0001_scene_review.json": "{}\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
