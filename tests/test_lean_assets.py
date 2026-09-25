import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.application.lean_assets import ensure_lean_planning_assets
from literary_engineering_studio.application.lean_asset_enrichment import enrich_lean_planning_assets, _validated_rows


class _Gateway:
    def __init__(self):
        self.calls = 0

    def run(self, workspace, prompt, *, role, timeout):
        self.calls += 1
        self.prompt = prompt
        if prompt.startswith("# 人物语言声音"):
            return type("Response", (), {"answer": json.dumps({"voices": {"林昭": {
                "vocabulary": "谈承诺时先提谁来承担后果；与同伴独处时会用旧称呼",
                "rhythm": "平时完整地铺陈条件，焦急时反复换一个开头才说出请求",
                "taboo_words": [],
                "signature_patterns": ["在对方答应前先把代价说透，真想挽留时却故意把结尾放轻。"],
            }}}, ensure_ascii=False)})()
        world_only = "## 待补人物\n[]" in prompt
        payload = {
            "characters": [] if world_only else [{
                "name": "林昭", "summary": "曾因守约失去同伴信任，因而不敢轻易答应。",
                "formative_events": ["曾替同伴隐瞒失约，最终被共同追责。"],
                "hidden_wound": "害怕自己的承诺再次伤人",
                "behavior_influences": ["面对请求先追问代价，再作承诺。"],
                "reveal_policy": "implicit_only",
                "appearance": "肩背略紧，思考时会把视线落到对方手边。",
                "clothing": "工作日穿耐磨深色外套，口袋留给登记笔。",
                "beliefs": ["承诺必须能说明代价。"],
                "intentions": ["先查清原件流转再答应同伴。"],
                "fears": ["再次替别人担下无法兑现的承诺。"],
                "secrets": [],
                "public_private_contrast": "公开场合耐心守规；独处时会反复核对已经确认的条目。",
                "moral_line": "不伪造登记，也不把同伴推出去顶责。",
                "relationships": ["同伴：公开合作；私下互不完全信任；林昭欠对方一次解释。"],
            }],
            "world": {
                "rules": [{
                    "rule": "借阅原件须在场登记",
                    "condition": "任何人接触馆藏原件时",
                    "boundary": "值班馆员可代填，但借阅人仍须签名",
                    "consequence": "私自带出将失去继续查阅资格",
                }],
                "constraints": [],
                "open_questions": ["旧登记簿是否仍在馆内？"],
            } if world_only else {},
        }
        return type("Response", (), {"answer": json.dumps(payload, ensure_ascii=False)})()


class LeanAssetsTests(unittest.TestCase):
    def test_extra_character_is_ignored_but_requested_name_is_required_once(self):
        gateway = _Gateway()
        payload = json.loads(gateway.run(None, "", role="worker", timeout=1).answer)
        extra = dict(payload["characters"][0], name="未请求者")
        payload["characters"].append(extra)
        requested = {"林昭": Path("林昭.yaml")}
        self.assertEqual([row["name"] for row in _validated_rows(payload, requested)], ["林昭"])
        with self.assertRaisesRegex(ValueError, "cover each eligible"):
            _validated_rows({"characters": [extra]}, requested)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            _validated_rows({"characters": [payload["characters"][0]] * 2}, requested)

    def test_offstage_character_may_have_no_present_intention(self):
        payload = json.loads(_Gateway().run(None, "", role="worker", timeout=1).answer)
        payload["characters"][0]["intentions"] = []
        self.assertEqual(_validated_rows(payload, {"林昭": Path("林昭.yaml")})[0]["intentions"], [])

    def test_relationship_objects_are_preserved_as_readable_asset_lines(self):
        payload = json.loads(_Gateway().run(None, "", role="worker", timeout=1).answer)
        payload["characters"][0]["relationships"] = [{
            "对象": "同伴", "公开": "一起守馆", "私下": "欠一次解释",
        }]
        rows = _validated_rows(payload, {"林昭": Path("林昭.yaml")})
        self.assertEqual(rows[0]["relationships"], ["对象：同伴；公开：一起守馆；私下：欠一次解释"])

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
            character = (root / "characters" / "林昭.yaml").read_text(encoding="utf-8")
            self.assertIn("appearance:", character)
            self.assertIn("speech_style:", character)
            self.assertIn("真想挽留时却故意把结尾放轻", character)
            self.assertIn("relationships:", character)
            self.assertIn("失去继续查阅资格", (root / "canon" / "world_rules.yaml").read_text(encoding="utf-8"))
            self.assertIn("适用条件", (root / "canon" / "world_rules.yaml").read_text(encoding="utf-8"))
            self.assertEqual(enrich_lean_planning_assets(root, gateway), {
                "background_stories_created": 0, "world_rules_enriched": 0,
            })
            self.assertEqual(gateway.calls, 3)

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
