import unittest

from literary_engineering_studio_engine.literary.style.anti_ai import lint_ai_style


class AntiAiStyleTests(unittest.TestCase):
    def test_concrete_abstract_nouns_do_not_trigger_summary_density(self):
        text = "。".join(["他核对了一遍记录"] * 170 + ["答案写在表格里", "真相仍待核验", "设备本身没有故障"])

        rules = {issue.rule for issue in lint_ai_style(text)}

        self.assertNotIn("abstract-summary-density", rules)

    def test_like_is_owned_by_simile_rule_not_abstract_summary(self):
        text = "。".join(["他继续核对记录"] * 170 + ["划痕像是被刃口压过"] * 5)

        rules = {issue.rule for issue in lint_ai_style(text)}

        self.assertIn("simile-dependency", rules)
        self.assertNotIn("abstract-summary-density", rules)

    def test_dense_abstract_summary_templates_remain_blocking(self):
        text = "。".join(["他继续核对记录"] * 100 + ["这一刻他终于明白全部"] * 4)

        issues = [issue for issue in lint_ai_style(text) if issue.rule == "abstract-summary-density"]

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "medium")
        self.assertIn("阈值", issues[0].message)


if __name__ == "__main__":
    unittest.main()
