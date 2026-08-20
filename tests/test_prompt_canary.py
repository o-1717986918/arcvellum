from __future__ import annotations

import unittest

from literary_engineering_studio.observability.prompt_canary import (
    _REDUCTION_GATES,
    _reduction,
    _safe_metrics,
    render_prompt_canary_markdown,
)


class PromptCanaryTests(unittest.TestCase):
    def test_every_benchmark_class_has_a_nonzero_reduction_gate(self):
        self.assertEqual(
            set(_REDUCTION_GATES),
            {"structured", "analysis", "prose", "review", "planning"},
        )
        self.assertTrue(all(value > 0 for value in _REDUCTION_GATES.values()))

    def test_reduction_uses_fair_post_tier_baseline(self):
        self.assertEqual(
            _reduction({"total_characters": 20000}, {"total_characters": 12000}),
            0.4,
        )
        self.assertEqual(_reduction({}, {"total_characters": 1}), 0.0)

    def test_safe_metrics_excludes_prompt_content(self):
        projected = _safe_metrics(
            {
                "total_characters": 100,
                "estimated_input_tokens": 25,
                "prompt_sha256": "a" * 64,
                "prompt_body": "secret prose",
            }
        )
        self.assertNotIn("prompt_body", projected)
        self.assertEqual(projected["total_characters"], 100)

    def test_markdown_renderer_keeps_only_safe_metrics(self):
        markdown = render_prompt_canary_markdown(
            {
                "revision": "abc",
                "status": "pass",
                "samples": [
                    {
                        "case_id": "review",
                        "benchmark_class": "review",
                        "runtime_task_kind": "review",
                        "actual_character_reduction": 0.4,
                        "required_character_reduction": 0.4,
                        "v2": {"total_characters": 100},
                        "v3": {"total_characters": 60, "duplicate_character_ratio": 0.0},
                        "v3_lint_status": "pass",
                        "status": "pass",
                    }
                ],
                "limitations": ["live pending"],
            }
        )
        self.assertIn("40.0%", markdown)
        self.assertIn("live pending", markdown)
        self.assertIn("compile pass does not authorize", markdown)


if __name__ == "__main__":
    unittest.main()
