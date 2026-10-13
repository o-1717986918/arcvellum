from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.application.project_manager import record_direction, read_directions
from literary_engineering_studio.application.creator_persona import CreatorPersonaStore


class DirectionProvenanceTests(unittest.TestCase):
    def test_tool_transport_is_rejected_before_persona_becomes_ready(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); (root / "project.yaml").write_text("title: 作品", encoding="utf-8")
            store = CreatorPersonaStore(root / "data")
            with self.assertRaisesRegex(ValueError, "tool-call"):
                store.save(root, '<｜｜DSML｜｜ invoke name="project_creator_persona_read">接口调用</｜｜DSML｜｜ invoke>', reason="作品初次加载人格")
            self.assertEqual(store.read(root)["status"], "missing")

    def test_continuity_correction_supersedes_agent_guess_without_changing_persona_intent(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"; root.mkdir(); (root / "project.yaml").write_text("title: 作品", encoding="utf-8")
            record_direction(root, "浪漫奇幻，丰盛而有趣的叙述")
            store = CreatorPersonaStore(Path(temporary) / "data"); before = store.direction_digest(root)
            old = record_direction(root, "硬币仍在窗台", actor="project-agent")["record"]
            record_direction(root, "已提交正文后段硬币进入小费罐", actor="continuity-reconciliation", source_kind="continuity",
                evidence=["drafts/scenes/scene_0001.md:后段"], supersedes=[old["record_id"]])
            rows = read_directions(root)
            self.assertEqual(rows[-2]["status"], "superseded")
            self.assertEqual(rows[-1]["source_kind"], "continuity")
            self.assertEqual(store.direction_digest(root), before)
            record_direction(root, "增加长时段风俗讲述与热情的人物声音")
            self.assertNotEqual(store.direction_digest(root), before)
