from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.canon_lint import build_canon_lint


class CanonLintCharacterIdentityTests(unittest.TestCase):
    def test_symbolic_protagonist_uses_the_shared_formal_identity_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_minimum_project(root, role="主角——轨道维修员")

            result = build_canon_lint(root)

            issues = self._issues(result.json_path, "scene-participant-unknown")
            self.assertEqual(issues, [])

    def test_secondary_protagonist_does_not_claim_the_primary_symbolic_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_minimum_project(root, role="次要主角——往访工程师")

            result = build_canon_lint(root)

            issues = self._issues(result.json_path, "scene-participant-unknown")
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0]["evidence"], "主角")

    def test_explicit_no_change_sections_do_not_create_canon_debt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_minimum_project(root, role="主角——轨道维修员")
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text(
                "# Draft\n\n## 正文草稿\n\n正文。\n\n## 状态变化\n\n"
                "### 新增事实候选\n\n- 无。\n\n"
                "### 人物状态变化\n\n- none\n\n"
                "### 关系变化\n\n- no change\n\n"
                "### 伏笔变化\n\n- N/A\n\n"
                "### 需要人工确认\n\n- not applicable\n",
                encoding="utf-8",
            )

            result = build_canon_lint(root)

            self.assertEqual(self._issues(result.json_path, "draft-unconfirmed-candidate"), [])

    @staticmethod
    def _write_minimum_project(root: Path, *, role: str) -> None:
        files = {
            "project.yaml": "title: 潮线\n",
            "canon/world_rules.yaml": "rules: []\n",
            "canon/timeline.yaml": "events: []\n",
            "canon/facts.json": '{"facts": [], "conflicts": [], "candidates": []}\n',
            "canon/locations.yaml": "locations: []\n",
            "canon/forbidden_changes.yaml": "forbidden_changes: []\n",
            "plot/outline.md": "# Outline\n",
            "plot/foreshadowing.csv": "foreshadow_id,setup_scene,expected_payoff,status\n",
            "characters/lin-huan.yaml": (
                'character_id: "lin-huan"\n'
                'name: "林桓"\n'
                f'role: "{role}"\n'
                "aliases: []\n"
                "bdi:\n  belief: [守住事实]\n  desire: [完成任务]\n  intention: [核验信号]\n"
                "background_story:\n  summary: 轨道维修经历塑造了他的判断。\n"
            ),
            "scenes/scene_0001.yaml": (
                "scene_id: scene_0001\nchapter_id: chapter_0001\nstatus: ready\n"
                "location: 轨道舱\nparticipants: [主角]\n"
            ),
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    @staticmethod
    def _issues(path: Path, check_id: str) -> list[dict[str, object]]:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in payload["issues"] if item["check_id"] == check_id]


if __name__ == "__main__":
    unittest.main()
