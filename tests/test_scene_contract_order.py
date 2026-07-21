from pathlib import Path
import json
import tempfile
import unittest

from literary_engineering_studio_engine.narrative_rhythm import narrative_rhythm_contract
from literary_engineering_studio_engine.scene_composer import composition_input_digest
from literary_engineering_studio_engine.workflow_state import _composition_step, _scene_state


class SceneContractOrderTests(unittest.TestCase):
    def test_explicit_rhythm_contract_precedes_composition(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                """scene_id: scene_0001
chapter_id: chapter_0001
narrative_rhythm:
  scene_function: [setup]
  scene_turn: 门打开了
  reader_effect: 读者知道风险将至
  tension_curve:
    entry: 1
    peak: 3
    exit: 2
scene_bridge:
  incoming_pressure: 全书开场的平静即将结束
  outgoing_hook: 门后有未知声音
""",
                encoding="utf-8",
            )
            state = _scene_state(root, scene)
            keys = [str(item["key"]) for item in state["steps"]]
            self.assertLess(keys.index("scene-rhythm-contract"), keys.index("composition-json"))

    def test_composition_without_current_contract_digest_is_stale(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps(
                    {"formal_cli_provenance": {"created_by": "compose-scene"}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.assertEqual(_composition_step(root, scene)["status"], "stale")

            composition.write_text(
                json.dumps(
                    {
                        "formal_cli_provenance": {
                            "created_by": "compose-scene",
                            "input_contract_digest": composition_input_digest(root, scene),
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.assertEqual(_composition_step(root, scene)["status"], "pass")

    def test_current_scene_rhythm_overrides_stale_composition_rhythm(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                """scene_id: scene_0001
chapter_id: chapter_0001
narrative_rhythm:
  scene_function: [setup]
  scene_turn: 门打开了
  reader_effect: 读者知道风险将至
  tension_curve:
    entry: 1
    peak: 3
    exit: 2
scene_bridge:
  incoming_pressure: 全书开场的平静即将结束
  outgoing_hook: 门后有未知声音
""",
                encoding="utf-8",
            )
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps(
                    {
                        "narrative_rhythm": {"tension_curve": "setup"},
                        "scene_bridge": {"incoming_pressure": "旧的泛化描述"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            contract = narrative_rhythm_contract(root, scene)

            self.assertEqual(contract["status"], "pass")
            self.assertEqual(contract["narrative_rhythm"]["tension_curve"], {"entry": "1", "peak": "3", "exit": "2"})
            self.assertEqual(contract["scene_bridge"]["incoming_pressure"], "全书开场的平静即将结束")


if __name__ == "__main__":
    unittest.main()
