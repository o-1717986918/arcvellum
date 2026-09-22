import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.application.lean_assets import ensure_lean_planning_assets
from literary_engineering_studio.application.lean_asset_enrichment import enrich_lean_planning_assets


class _Gateway:
    def __init__(self):
        self.calls = 0

    def run(self, workspace, prompt, *, role, timeout):
        self.calls += 1
        self.prompt = prompt
        payload = {
            "characters": [{
                "name": "林昭", "summary": "曾因守约失去同伴信任，因而不敢轻易答应。",
                "formative_events": ["曾替同伴隐瞒失约，最终被共同追责。"],
                "hidden_wound": "害怕自己的承诺再次伤人",
                "behavior_influences": ["面对请求先追问代价，再作承诺。"],
                "reveal_policy": "implicit_only",
            }],
            "world": {
                "rules": ["借阅原件须在场登记；私自带出将失去继续查阅资格。"],
                "constraints": ["夜间无人值守时不能取得原件，人物只能等待或寻求正式授权。"],
                "open_questions": ["旧登记簿是否仍在馆内？"],
            },
        }
        return type("Response", (), {"answer": json.dumps(payload, ensure_ascii=False)})()


class LeanAssetsTests(unittest.TestCase):
    def test_generated_stubs_receive_independent_background_and_world_detail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder in ("plot", "canon", "characters"):
                (root / folder).mkdir()
            (root / "project.yaml").write_text("project:\n  premise: 寻找遗失的信\n", encoding="utf-8")
            (root / "plot" / "lean_project_plan.json").write_text(json.dumps({
                "characters": [{"name": "林昭", "role": "主角", "importance": "major", "background": "馆员", "desire": "履约"}],
                "world_facts": ["馆藏原件需要登记"],
            }, ensure_ascii=False), encoding="utf-8")
            ensure_lean_planning_assets(root)
            gateway = _Gateway()
            self.assertEqual(enrich_lean_planning_assets(root, gateway), {
                "background_stories_created": 1, "world_rules_enriched": 1,
            })
            self.assertIn("formative_events", (root / "characters" / "林昭.yaml").read_text(encoding="utf-8"))
            self.assertIn("失去继续查阅资格", (root / "canon" / "world_rules.yaml").read_text(encoding="utf-8"))
            self.assertEqual(enrich_lean_planning_assets(root, gateway), {
                "background_stories_created": 0, "world_rules_enriched": 0,
            })
            self.assertEqual(gateway.calls, 1)

    def test_existing_user_assets_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "plot").mkdir()
            (root / "canon").mkdir()
            (root / "characters").mkdir()
            (root / "characters" / "林昭.yaml").write_text(
                'name: "林昭"\nidentity:\n  background: "用户确认的背景"\n',
                encoding="utf-8",
            )
            (root / "canon" / "world_rules.yaml").write_text(
                "rules: [用户规则]\n", encoding="utf-8",
            )
            (root / "plot" / "lean_project_plan.json").write_text(
                json.dumps({
                    "characters": [{
                        "name": "林昭", "role": "主角", "importance": "major",
                        "background": "模型建议", "desire": "履约",
                    }],
                    "world_facts": ["模型建议的规则"],
                }, ensure_ascii=False), encoding="utf-8",
            )
            self.assertEqual(
                ensure_lean_planning_assets(root),
                {"characters_created": 0, "world_rules_created": 0},
            )
            self.assertIn("用户确认的背景", (root / "characters" / "林昭.yaml").read_text(encoding="utf-8"))
            self.assertEqual(
                (root / "canon" / "world_rules.yaml").read_text(encoding="utf-8"),
                "rules: [用户规则]\n",
            )


if __name__ == "__main__":
    unittest.main()
