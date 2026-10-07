"""The author and optional editor share one transaction style, including measured targets."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from literary_engineering_studio.runtimes.scene_creator_briefing import scene_creator_style
from literary_engineering_studio.runtimes.scene_natural_output import creator_style
from tests.runtimes.test_less_ai_tone_experiment import runtime, brief
from tests.runtimes.test_creator_stylometry import snapshot


class ToneStyleAlignmentTests(unittest.TestCase):
    def test_append_replace_observe_share_exact_frozen_style(self):
        for combine, usage, expected in (
            ("append", "guide", "作者声音\n\n正式文风\n\n计量目标"),
            ("replace", "guide", "作者声音\n\n计量目标"),
            ("replace", "observe", "作者声音\n\n正式文风"),
        ):
            with self.subTest(combine=combine, usage=usage), TemporaryDirectory() as tmp:
                adapter = runtime(Path(tmp))
                target = snapshot("计量目标", combine=combine, usage=usage)
                adapter._creator_style_snapshot_provider = lambda _: target
                style_path = adapter._project_root / "style/owner_style_directive.md"
                style_path.parent.mkdir()
                style_path.write_text("作者声音", encoding="utf-8")
                with patch("literary_engineering_studio.runtimes.scene_creator_briefing.active_style_prompt_text", return_value="正式文风"):
                    mount = adapter._tone_mount("shared", brief())
                target = replace(target, fragment_text="新的目标")
                style_path.write_text("新的作者声音", encoding="utf-8")
                packet = {"style": scene_creator_style(adapter._project_root)}
                adapter._creator_style_briefing("shared", packet)
                self.assertEqual(mount["style"], expected)
                self.assertEqual(creator_style(packet), expected)
                self.assertEqual(adapter._tone_mount("shared"), mount)

    def test_creator_first_and_old_editor_mount_keep_original_snapshot(self):
        with TemporaryDirectory() as tmp:
            adapter = runtime(Path(tmp))
            packet = {"style": {"author_directive": {"content": "先冻结的作者声音"}, "mounted": {"content": "旧正式文风"}}}
            adapter._creator_style_briefing("author-first", packet)
            self.assertEqual(adapter._tone_mount("author-first")["style"], creator_style(packet))
            path = adapter._cache_path("legacy", "less-ai-tone/mount.json")
            path.parent.mkdir(parents=True)
            original = '{"schema":"arcvellum/less-ai-tone-mount/v1","enabled":true,"style":"旧编辑快照"}'
            path.write_text(original, encoding="utf-8")
            self.assertEqual(adapter._tone_mount("legacy")["style"], "旧编辑快照")
            self.assertEqual(path.read_text(encoding="utf-8"), original)
