from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.review.longform_audit import build_longform_audit
from literary_engineering_studio_engine.literary.scene.promotion.historical import seal_historical_promotion
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
            staged = sandbox.control_workspace
            for relative in (
                "canon/facts.json",
                "characters/lead.yaml",
                "style/creative_quality_profile.json",
                "branches/scene_0001/branch_manifest.json",
                "drafts/candidates/scene_0001-platform-agent.md",
                "plot/chapter_obligations/chapter_0001.json",
                "workflow/approvals/index.jsonl",
            ):
                self.assertTrue((staged / relative).is_file(), relative)
            snapshot_paths = {item["path"] for item in payload["input_snapshot"]["files"]}
            self.assertIn("canon/facts.json", snapshot_paths)
            self.assertIn("branches/scene_0001/branch_manifest.json", snapshot_paths)

    def test_historical_promotion_prevents_future_canon_from_invalidating_scene_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root / "project.yaml", "project:\n  target_length: 0\n")
            self._write(
                root / "scenes" / "scene_0001.yaml",
                "scene_id: scene_0001\nchapter_id: chapter_0001\nlocation: 舱室\nparticipants: [林]\nscene_goal: 回家\n",
            )
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            self._write(candidate, "正文。\n")
            self._write(draft, "正文。\n")
            self._write(candidate.with_suffix(".json"), json.dumps({"style_mount_snapshot": {}}))
            manifest = {
                "schema": "literary-engineering-workbench/candidate-promotion/v0.1",
                "scene_id": "scene_0001",
                "candidate": "drafts/candidates/scene_0001-platform-agent.md",
                "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                "draft": "drafts/scenes/scene_0001.md",
                "draft_sha256": hashlib.sha256(draft.read_bytes()).hexdigest(),
                "style_mount_snapshot": {},
                "candidate_generation": {"status": "pass"},
                "candidate_review": {"status": "pass"},
                "allow_unreviewed": False,
                "allow_review_notes": False,
            }
            seal_historical_promotion(root, manifest, candidate, draft)
            self._write(
                root / "drafts" / "promotions" / "scene_0001_promotion.json",
                json.dumps(manifest, ensure_ascii=False),
            )
            self._write(root / "reviews" / "scene_0001-review.md", "- 结论： pass\n")

            result = build_longform_audit(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            categories = {item["category"] for item in payload["issues"]}

            self.assertNotIn("flow_readiness", categories)
            self.assertNotIn("memory_context", categories)
            self.assertEqual(payload["scenes"][0]["status"], "ready")

    def test_character_role_label_resolves_formal_scene_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root / "project.yaml", "project:\n  target_length: 0\n")
            self._write(root / "characters" / "lead.yaml", 'character_id: lead\nname: 林桓\nrole: "主角——维修员"\n')
            self._write(
                root / "scenes" / "scene_0001.yaml",
                "scene_id: scene_0001\nchapter_id: chapter_0001\nlocation: 舱室\nparticipants: [主角]\nscene_goal: 回家\n",
            )

            result = build_longform_audit(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertFalse(any(item["category"] == "character_inventory" for item in payload["issues"]))

    def test_longform_uses_live_scene_inventory_and_project_budget_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root / "project.yaml", "project:\n  target_length: 1000\n")
            for index in (1, 2):
                scene_id = f"scene_{index:04d}"
                self._write(
                    root / "scenes" / f"{scene_id}.yaml",
                    f"scene_id: {scene_id}\nchapter_id: chapter_0001\nlocation: 舱室\nparticipants: [林]\nscene_goal: 推进\n",
                )
                self._write(root / "drafts" / "scenes" / f"{scene_id}.md", "字" * 500)
            stale_budget = {
                "target": {"target_chinese_chars": 1000},
                "totals": {"target_words": 1000, "chapter_count": 1, "scene_count": 2},
                "chapter_budgets": [
                    {
                        "chapter_id": "chapter_0001",
                        "volume_id": "volume_01",
                        "target_words": 1000,
                        "scene_count": 2,
                        "avg_scene_words": 500,
                    }
                ],
                "outline_inventory": {"outline_path": "plot/outline.md"},
                "scene_inventory_binding": {"actual_scene_count": 0, "missing_scene_count": 2},
                "issues": [{"severity": "high", "category": "scene_inventory"}],
                "status": "needs_expansion",
            }
            self._write(root / "plot" / "word_budget" / "word_budget.json", json.dumps(stale_budget))
            self._write(root / "plot" / "outline.md", "# 第一章\n")

            result = build_longform_audit(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["summary"]["target_length"], 1000)
            self.assertEqual(payload["word_budget"]["status"], "pass")
            self.assertEqual(payload["word_budget"]["scene_inventory_binding"]["actual_scene_count"], 2)
            self.assertEqual(payload["word_budget"]["scene_inventory_binding"]["missing_scene_count"], 0)

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
            "canon/facts.json": "{}\n",
            "characters/lead.yaml": "character_id: lead\nname: 林\n",
            "style/creative_quality_profile.json": "{}\n",
            "scenes/scene_0001.yaml": "scene_id: scene_0001\nchapter_id: chapter_0001\n",
            "branches/scene_0001/roleplay_simulation.md": "读取回执\n",
            "branches/scene_0001/branch_manifest.json": '{"branches":[{"branch_id":"b1"}]}\n',
            "branches/scene_0001/branch_selection.md": "decision: selected\nselected_branch: b1\n",
            "drafts/candidates/scene_0001-platform-agent.md": "正文。\n",
            "drafts/candidates/scene_0001-platform-agent.json": "{}\n",
            "drafts/scenes/scene_0001.md": "正文。\n",
            "drafts/compositions/scene_0001_composition.json": "{}\n",
            "drafts/promotions/scene_0001_promotion.json": "{}\n",
            "memory/context_packets/scene_0001.md": "# Context\n",
            "memory/context_packets/scene_0001.trace.json": "{}\n",
            "plot/chapters/chapter_0001.json": "{}\n",
            "plot/chapter_obligations/chapter_0001.json": "{}\n",
            "plot/chapter_obligations/chapter_0001.agent_tasks.md": "# task\n",
            "plot/chapter_obligations/chapter_0001.agent_completion.json": "{}\n",
            "plot/outline.md": "# 第一章\n",
            "plot/conflict_matrix.md": "# conflict\n",
            "plot/foreshadowing.csv": "id,status\nF1,open\n",
            "plot/promises/ledger.json": "{}\n",
            "plot/reader_questions/ledger.json": "{}\n",
            "plot/rhythm_plan.json": "{}\n",
            "plot/word_budget/word_budget.json": "{}\n",
            "reviews/scene_0001-review.md": "- 结论： pass\n",
            "reviews/agent/scene_0001_scene_review.json": "{}\n",
            "workflow/approvals/index.jsonl": "{}\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
