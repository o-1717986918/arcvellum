"""Creator style targets compile into metric-specific, source-relative prose guidance."""
from copy import deepcopy
import unittest

from stylometric_prompt_lab.creator_fragment import (
    HIGHER_GUIDANCE, LOWER_GUIDANCE, compile_creator_fragment, default_creator_controls,
    metric_catalog,
)
from stylometric_prompt_lab.extended_metrics import SECONDARY_AXES, secondary_summary_key
from stylometric_prompt_lab.dependency_metrics import seal_parse
from stylometric_prompt_lab.io import digest
from stylometric_prompt_lab.metrics import AXES


def profile_fixture():
    profile = {
        "schema": "stylometric-profile/v1",
        "axes": {
            "sentence_length_han": {"median": 20, "p25": 12, "p75": 28, "window_count": 8},
            "paragraph_length_han": {"median": 75, "p25": 50, "p75": 100, "window_count": 8},
            "dialogue_share": {"median": .3, "p25": .2, "p75": .4, "window_count": 8},
            "punctuation_per_1000_han": {"median": 22, "p25": 15, "p75": 30, "window_count": 8},
        },
        "extended_window_summary": {},
        "extended_diagnostics": {"grammar": {"function_word_top": [
            {"word": "就", "per_1000_words": 10, "count": 8},
        ]}},
    }
    for key in SECONDARY_AXES:
        if key in {"short_sentence_share_le20_han", "long_sentence_share_gt30_han",
                   "word_mattr_50", "activity_v_over_v_plus_a", "nominality_n_over_n_plus_v",
                   "function_pos_share_proxy"}:
            values = {"median": .4, "p25": .3, "p75": .5, "window_count": 8}
        elif key == "word_length_mean_han":
            values = {"median": 2.0, "p25": 1.5, "p75": 2.5, "window_count": 8}
        else:
            values = {"median": 3, "p25": 2, "p75": 4, "window_count": 8}
        profile["extended_window_summary"][secondary_summary_key(key)] = values
    profile["profile_sha256"] = digest(profile)
    return profile


class StylometricCreatorGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.profile = profile_fixture()
        forms = list("甲乙丙丁戊己庚辛")
        heads = [3, 4, 4, 0, 4, 5, 5, 7]
        text = "".join(forms)
        tokens = [{"id": index, "form": form, "head": head, "pos": "n",
                   "relation": "HED" if head == 0 else "ATT"}
                  for index, (form, head) in enumerate(zip(forms, heads), 1)]
        self.tree = seal_parse({"text": text, "sentences": [{"id": 1, "text": text,
            "start": 0, "end": len(text), "tokens": tokens}],
            "annotation_scheme": {"name": "guidance_fixture", "punctuation_pos": ["wp"],
                                  "punctuation_relations": ["WP"]},
            "annotator": {"name": "guidance_fixture", "domain_validity": "fixture_only"}})
        self.catalog = {row["id"]: row for row in metric_catalog(self.profile, self.tree)}

    def _fragment(self, identifier, relation):
        controls = deepcopy(default_creator_controls(self.profile, self.tree))
        selected = next(row for row in controls["targets"] if row["id"] == identifier)
        for row in controls["targets"]:
            row["enabled"] = row is selected
        meta = self.catalog[identifier]
        low, high = meta["source_range"]["p25"], meta["source_range"]["p75"]
        if relation == "lower":
            selected["min"], selected["max"] = meta["floor"], (meta["floor"] + low) / 2
        elif relation == "higher":
            ceiling = meta["ceiling"]
            ceiling = ceiling if ceiling is not None else high + max(high - low, 1)
            selected["min"], selected["max"] = (high + ceiling) / 2, ceiling
        else:
            selected["min"], selected["max"] = low, high
        return compile_creator_fragment(self.profile, controls, dependency_parse=self.tree)["fragment_text"]

    def test_every_measured_metric_has_distinct_lower_and_higher_literary_guidance(self):
        dependency_ids = {"mdd", "mdd_without_punctuation", "mhd", "head_precedes_share",
                          "adjacent_arc_share", "mean_nonleaf_branching", "leaf_share"}
        expected_ids = {"dep:" + key if key in dependency_ids else key for key in HIGHER_GUIDANCE} | {"word:就"}
        self.assertEqual(expected_ids, set(self.catalog))
        for identifier in sorted(expected_ids):
            with self.subTest(metric=identifier):
                lower = self._fragment(identifier, "lower")
                higher = self._fragment(identifier, "higher")
                self.assertNotEqual(lower, higher)
                if identifier != "word:就":
                    key = identifier.removeprefix("dep:")
                    self.assertIn(LOWER_GUIDANCE[key], lower)
                    self.assertIn(HIGHER_GUIDANCE[key], higher)
                self.assertIn("样本中位数", lower)
                self.assertIn("目标", higher)

    def test_target_inside_source_range_keeps_neutral_observation_guidance(self):
        neutral = self._fragment("sentence_length_han", "within")
        self.assertIn("让长短变化承接人物当下的注意力", neutral)
        self.assertNotIn(LOWER_GUIDANCE["sentence_length_han"], neutral)
        self.assertNotIn(HIGHER_GUIDANCE["sentence_length_han"], neutral)

    def test_compiler_version_changes_and_prompt_uses_positive_whole_work_guidance(self):
        controls = default_creator_controls(self.profile)
        result = compile_creator_fragment(self.profile, controls)
        self.assertEqual(result["compiler_version"], "creator-1.1")
        self.assertEqual(result["generation_effect"], "not-verified")
        for wording in ("你不是", "你不能", "不得", "不要", "没有权限", "逐句配额"):
            self.assertNotIn(wording, result["fragment_text"])
        self.assertIn("整篇语言分布", result["fragment_text"])


if __name__ == "__main__":
    unittest.main()
