from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.project_manager import create_project
from literary_engineering_studio_engine.public.literary import (
    active_style_mount_snapshot_payload,
    recent_formal_reference_ids,
    render_style_reference_selection,
    select_active_style_references,
)
from literary_engineering_studio_engine.literary.style.snapshot import active_style_prompt_path
from literary_engineering_studio.runtimes.pi_scene_style_history import scene_reference_context


class StyleReferenceProjectionTests(unittest.TestCase):
    def test_all_25_complete_units_are_indexed_reachable_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                root = Path(create_project(
                    parent_directory=str(base), title="选段验证", folder_name="work",
                )["path"])
            prompt = active_style_prompt_path(root)
            assert prompt is not None
            profile = (prompt.parent / "style-profile.md").read_text(encoding="utf-8")
            index = json.loads((prompt.parent / "reference-index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index["units"]), 25)
            self.assertEqual(
                [row["unit_id"] for row in index["units"]],
                [f"R{number:02d}" for number in range(1, 26)],
            )
            for row in index["units"]:
                excerpt = profile[row["span"]["start"]:row["span"]["end"]]
                self.assertEqual(hashlib.sha256(excerpt.encode()).hexdigest(), row["source_digest"])
                unique_term = next(term for term in row["match_terms"] if sum(
                    term in other["match_terms"] for other in index["units"]
                ) == 1)
                selected = select_active_style_references(root, unique_term)
                self.assertEqual(selected["references"][0]["unit_id"], row["unit_id"])
                self.assertIn(excerpt, render_style_reference_selection(selected))
            self.assertEqual(select_active_style_references(root, "无匹配场景")["status"], "no-scene-match")

    def test_recent_reuse_loses_a_tie_without_hiding_relevant_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                root = Path(create_project(
                    parent_directory=str(base), title="邻场验证", folder_name="work",
                )["path"])
            self.assertEqual(select_active_style_references(root, "离别")["references"][0]["unit_id"], "R03")
            self.assertEqual(
                select_active_style_references(root, "离别", recent_unit_ids=("R03",))["references"][0]["unit_id"],
                "R17",
            )
            self.assertEqual(
                select_active_style_references(root, "渡口离别", recent_unit_ids=("R03",))["references"][0]["unit_id"],
                "R03",
            )

    def test_formal_history_reads_distinct_scenes_for_current_mount(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                root = Path(create_project(parent_directory=str(base), title="近场历史", folder_name="work")["path"])
            candidates = root / "drafts" / "candidates"
            candidates.mkdir(parents=True, exist_ok=True)
            mount = active_style_mount_snapshot_payload(root)
            for index, (name, scene, unit) in enumerate((("a", "scene_0001", "R03"),
                                                        ("b", "scene_0001", "R17"),
                                                        ("c", "scene_0002", "R21"))):
                path = candidates / f"{name}.prompt.json"
                path.write_text(json.dumps({
                    "scene": f"plot/scenes/{scene}.yaml", "style_mount_snapshot": mount,
                    "style_reference_selection": {"status": "selected", "references": [{"unit_id": unit}]},
                }), encoding="utf-8")
                os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))
            self.assertEqual(set(recent_formal_reference_ids(root)), {"R17", "R21"})
            self.assertEqual(recent_formal_reference_ids(root, exclude_scene_id="scene_0002"), ("R17",))

    def test_lean_selection_uses_scene_facts_without_generic_rhythm_boilerplate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                root = Path(create_project(parent_directory=str(base), title="场景线索", folder_name="work")["path"])
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True, exist_ok=True)
            scene.write_text("title: 雨夜值班室\nscene_goal: 证词使人物重新怀疑旧案\nnarrative_rhythm:\n  paragraph_shape: 过场简短\n", encoding="utf-8")
            context = scene_reference_context(root, "scene_0001", {"objective": "打开旧案"})
            self.assertIn("雨夜", context)
            self.assertNotIn("过场简短", context)
            selected = select_active_style_references(root, context)
            self.assertEqual(selected["status"], "selected")
            self.assertIn(selected["references"][0]["unit_id"], {"R01", "R17"})

    def test_lean_selection_ignores_future_scene_terms_and_generic_broadcast_topic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                root = Path(create_project(parent_directory=str(base), title="对话参考", folder_name="work")["path"])
            scene = root / "scenes" / "scene_0002.yaml"
            scene.parent.mkdir(parents=True, exist_ok=True)
            scene.write_text("title: 证人试探对话\nscene_goal: 通过盘问发现证词回避\n", encoding="utf-8")
            context = scene_reference_context(root, "scene_0002", {
                "objective": "证人试探", "canon_constraints": ["未来在黑暗控制室发现广播录音"],
            })
            self.assertNotIn("控制室", context)
            self.assertNotIn("广播", context)
            selected = select_active_style_references(root, context)
            self.assertEqual(selected["status"], "selected")
            self.assertNotIn("R23", [row["unit_id"] for row in selected["references"]])
            self.assertEqual(select_active_style_references(root, "广播")["status"], "no-scene-match")


if __name__ == "__main__":
    unittest.main()
