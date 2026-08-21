from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.export.readiness import (
    final_delivery_length_errors,
)
from literary_engineering_studio_engine.literary.planning.delivery_length import (
    delivery_length_status,
)
from literary_engineering_studio_engine.literary.planning.length_repair import (
    build_target_length_repair_plan,
    scene_length_repair_allocation,
    target_length_repair_status,
)
from literary_engineering_studio_engine.literary.scene.promotion.revision import (
    build_scene_revision_task,
)
from literary_engineering_studio_engine.literary.review.longform_audit import (
    build_longform_audit,
)
from literary_engineering_studio_engine.routes.scene.blueprints import (
    _blueprint_for_state,
)
from literary_engineering_studio_engine.workflow.state_export_release import (
    _chapter_workspace_step,
    _export_package_step,
    _target_length_step,
)
from literary_engineering_studio_engine.workflow.scene_length_repair import (
    target_length_revision_step,
)


class TargetLengthRepairTests(unittest.TestCase):
    def test_plan_allocates_exact_shortfall_and_drives_scene_revision_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._project(root)

            progress = delivery_length_status(root)
            self.assertEqual(progress.target_chinese_chars, 1000)
            self.assertEqual(progress.actual_chinese_chars, 900)
            self.assertEqual(progress.shortfall_chinese_chars, 100)
            self.assertTrue(progress.inventory_complete)

            audit = build_longform_audit(root)
            audit_payload = json.loads(audit.json_path.read_text(encoding="utf-8"))
            self.assertEqual(audit_payload["summary"]["target_length_status"], "shortfall")
            self.assertEqual(audit_payload["summary"]["target_length_shortfall"], 100)
            self.assertTrue(
                any(
                    item.get("category") == "target_length_shortfall"
                    and item.get("severity") == "high"
                    for item in audit_payload["issues"]
                )
            )

            result = build_target_length_repair_plan(root)
            self.assertEqual(result.status, "ready")
            self.assertEqual(result.allocated_chinese_chars, 100)
            self.assertEqual(result.scene_count, 2)
            status = target_length_repair_status(root)
            self.assertEqual(status["status"], "pending")
            self.assertEqual(
                sum(
                    int(item["required_growth_chars"])
                    for item in status["pending_allocations"]
                ),
                100,
            )

            allocation = scene_length_repair_allocation(root, "scene_0001")
            self.assertEqual(allocation["minimum_scene_chars"], 500)
            state = target_length_revision_step(
                root,
                "scene_0001",
                root / "drafts/scenes/scene_0001.md",
            )
            self.assertEqual(state["key"], "target-length-revision")

            blueprint = _blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "target-length-revision",
                "",
            )
            self.assertIn(
                "reviews/longform/target_length_repair.json",
                blueprint["source_paths"],
            )
            self.assertIn(
                "--review reviews/longform/target_length_repair.json",
                blueprint["command"],
            )
            self.assertTrue(
                any("at least 500" in item for item in blueprint["hard_constraints"])
            )

            revision = build_scene_revision_task(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                draft=Path("drafts/scenes/scene_0001.md"),
                review=Path("reviews/longform/target_length_repair.json"),
            )
            prompt = json.loads(
                revision.prompt_manifest_path.read_text(encoding="utf-8")
            )
            repair = prompt["generation_standards"]["target_length_repair"]
            self.assertEqual(repair["scene_id"], "scene_0001")
            self.assertEqual(repair["required_growth_chars"], 50)
            self.assertEqual(repair["minimum_scene_chars"], 500)
            task_text = revision.task_path.read_text(encoding="utf-8")
            self.assertIn("至少达到 500 个中文内容字符", task_text)
            self.assertIn("禁止重复心理", task_text)

    def test_final_chapter_blocks_until_formal_drafts_meet_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._project(root)
            build_target_length_repair_plan(root)

            self.assertEqual(
                _target_length_step(root, "chapter_0001")["key"],
                "target-length-repair-scenes",
            )
            self.assertTrue(final_delivery_length_errors(root, "chapter_0001"))

            for scene_id in ("scene_0001", "scene_0002"):
                (root / "drafts/scenes" / f"{scene_id}.md").write_text(
                    "字" * 500,
                    encoding="utf-8",
                )

            progress = delivery_length_status(root)
            self.assertTrue(progress.met)
            self.assertEqual(target_length_repair_status(root)["status"], "resolved")
            self.assertEqual(
                _target_length_step(root, "chapter_0001")["key"],
                "target-length-gate",
            )
            self.assertEqual(final_delivery_length_errors(root, "chapter_0001"), [])

    def test_draft_change_invalidates_chapter_workspace_and_export_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._project(root)
            chapter_json = root / "plot/chapters/chapter_0001.json"
            chapter_md = root / "drafts/chapters/chapter_0001.md"
            self._write(
                chapter_json,
                json.dumps(
                    {"summary": {"ready_count": 2, "blocked_count": 0}},
                    ensure_ascii=False,
                ),
            )
            self._write(chapter_md, "# 第一章\n")
            self._set_mtime(root / "drafts/scenes/scene_0001.md", 10)
            self._set_mtime(root / "drafts/scenes/scene_0002.md", 10)
            self._set_mtime(chapter_json, 20)
            self._set_mtime(chapter_md, 20)
            self.assertEqual(
                _chapter_workspace_step(
                    root, "chapter_0001", chapter_json, chapter_md
                )["status"],
                "pass",
            )

            manifest = self._export_manifest(root)
            self._set_mtime(manifest, 30)
            self.assertEqual(
                _export_package_step(root, "chapter_0001", manifest)["status"],
                "pass",
            )

            self._set_mtime(root / "drafts/scenes/scene_0001.md", 40)
            self.assertEqual(
                _chapter_workspace_step(
                    root, "chapter_0001", chapter_json, chapter_md
                )["status"],
                "stale",
            )
            self.assertEqual(
                _export_package_step(root, "chapter_0001", manifest)["status"],
                "stale",
            )

    def _project(self, root: Path) -> None:
        self._write(root / "project.yaml", "project:\n  target_length: 1000\n")
        self._write(root / "plot/outline.md", "# 第一章\n")
        budget = {
            "schema": "literary-engineering-workbench/word-budget/v1",
            "target": {"target_chinese_chars": 1000},
            "totals": {
                "target_words": 1000,
                "target_chinese_chars": 1000,
                "chapter_count": 1,
                "scene_count": 2,
            },
            "chapter_budgets": [
                {
                    "chapter_id": "chapter_0001",
                    "volume_id": "volume_01",
                    "target_words": 1000,
                    "scene_count": 2,
                    "avg_scene_words": 500,
                }
            ],
            "scene_inventory_binding": {
                "actual_scene_count": 0,
                "missing_scene_count": 2,
                "chapter_rows": [],
            },
        }
        self._write(
            root / "plot/word_budget/word_budget.json",
            json.dumps(budget, ensure_ascii=False),
        )
        for index in (1, 2):
            scene_id = f"scene_{index:04d}"
            self._write(
                root / "scenes" / f"{scene_id}.yaml",
                (
                    f"scene_id: {scene_id}\n"
                    "chapter_id: chapter_0001\n"
                    "scene_function: confrontation\n"
                    "location: room\n"
                    "participants: [lead]\n"
                    "scene_goal: advance\n"
                    "word_count_target: 500\n"
                    "word_count_min: 425\n"
                    "word_count_max: 625\n"
                ),
            )
            self._write(
                root / "drafts/scenes" / f"{scene_id}.md",
                "字" * 450,
            )

    @staticmethod
    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _export_manifest(self, root: Path) -> Path:
        folder = root / "exports/chapter_0001"
        prefix = "exports/chapter_0001/chapter_0001"
        outputs: dict[str, object] = {
            "novel": f"{prefix}_novel.md",
            "screenplay": f"{prefix}_screenplay.md",
            "video_prompt_pack": f"{prefix}_video_prompt_pack.md",
            "docx": {},
            "docx_layout_plans": {},
            "docx_inspections": {},
        }
        for key in ("novel", "screenplay", "video_prompt_pack"):
            self._write(root / str(outputs[key]), "正文\n")
            for section, suffix in (
                ("docx", ".docx"),
                ("docx_layout_plans", ".layout.json"),
                ("docx_inspections", ".inspection.json"),
            ):
                relative = f"{prefix}_{key}{suffix}"
                mapping = outputs[section]
                assert isinstance(mapping, dict)
                mapping[key] = relative
                self._write(root / relative, "document\n")
        manifest = folder / "export_manifest.json"
        self._write(
            manifest,
            json.dumps(
                {
                    "requested_formats": ["md", "docx"],
                    "skipped_scenes": [],
                    "include_blocked": False,
                    "outputs": outputs,
                },
                ensure_ascii=False,
            ),
        )
        return manifest

    @staticmethod
    def _set_mtime(path: Path, value: int) -> None:
        stamp = 1_700_000_000_000_000_000 + value * 1_000_000
        os.utime(path, ns=(stamp, stamp))


if __name__ == "__main__":
    unittest.main()
