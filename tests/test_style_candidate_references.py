from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.style.compiler import StyleCompileOptions, compile_style_profile
from literary_engineering_studio_engine.literary.style.reference_projection import validate_reference_index
from literary_engineering_studio_engine.literary.style.version import _reference_index_errors


class StyleCandidateReferenceTests(unittest.TestCase):
    def test_custom_compile_produces_bounded_complete_and_validated_units(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            corpus.mkdir()
            (corpus / "dialogue.txt").write_text("版权：测试授权。\n\n“你回来？”她问。\n\n“我还没走。”他答。", encoding="utf-8")
            (corpus / "street.txt").write_text("雨落在街上。\n\n门里的人一直没有出来。", encoding="utf-8")
            profile = root / "profile"
            compile_style_profile(StyleCompileOptions(corpus=corpus, output_dir=profile, name="测试文风"))
            text = (profile / "style-profile.md").read_text(encoding="utf-8")
            index = json.loads((profile / "reference-index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index["units"]), 2)
            self.assertNotIn("版权：测试授权", text[text.index("## 候选参考选段"):])
            validate_reference_index(text, index)
            self.assertEqual(_reference_index_errors(profile), [])
            for row in index["units"]:
                self.assertLessEqual(row["span"]["end"] - row["span"]["start"], 1200)
                self.assertIn(text[row["span"]["start"]:row["span"]["end"]], text)
            index["units"][0]["source_digest"] = "bad"
            (profile / "reference-index.json").write_text(json.dumps(index), encoding="utf-8")
            self.assertTrue(_reference_index_errors(profile))


if __name__ == "__main__":
    unittest.main()
