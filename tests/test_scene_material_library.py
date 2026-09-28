from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.runtimes.scene_material_library import SceneMaterialLibrary


class SceneMaterialLibraryTests(unittest.TestCase):
    def test_candidate_prose_is_only_in_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = SceneMaterialLibrary(Path(directory) / "materials")
            packet = {"beats": [{"beat_id": "b1"}], "director_turns": [{"cue": "让读者先相信他"}],
                      "actor_entries": [{"entry_id": "t1:1", "speaker": "甲", "spoken": "我没有拿信。"}],
                      "description_candidates": [{"candidate_id": "d1:1", "kind": "event-narration",
                                                  "target": "昨夜取信", "purpose": "改变读者认知",
                                                  "scene_moment": "承认之前", "text": "昨夜信被人取走。",
                                                  "basis": "confirmed", "source_note": "已确认的信件记录"}]}
            directory_text = library.write("可编辑文学引导\n第二行引导\n" + json.dumps(packet, ensure_ascii=False))
            self.assertIn("d1:1", directory_text)
            self.assertNotIn("昨夜信被人取走", directory_text)
            self.assertNotIn("我没有拿信", directory_text)
            index = json.loads((library.root / "index.json").read_text(encoding="utf-8"))
            self.assertEqual([entry["candidate_id"] for entry in index["entries"]],
                             ["scene-context", "t1:1", "d1:1"])
            self.assertEqual(index["entries"][-1]["basis"], "confirmed")
            event_file = library.root / index["entries"][-1]["file"]
            self.assertIn("昨夜信被人取走", event_file.read_text(encoding="utf-8"))

    def test_empty_library_still_has_an_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = SceneMaterialLibrary(Path(directory) / "materials")
            library.write("")
            index = json.loads((library.root / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["entries"], [])


if __name__ == "__main__":
    unittest.main()
