"""Engine contracts for creator-authored actor system cards."""

from copy import deepcopy
import unittest

from literary_engineering_studio_engine.public.literary import (
    ACTOR_CARD_SECTIONS, parse_actor_character_card, render_actor_character_card,
    parse_scene_material_requests_v3,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from tests.actor_card_fixtures import actor_card_payload


class ActorCharacterCardTests(unittest.TestCase):
    def setUp(self):
        self.payload = actor_card_payload()
        self.template = prompt_layer_spec("scene.v2.material.actor").default_text

    def test_card_roundtrip_and_system_render_keep_audit_private(self):
        card = parse_actor_character_card(self.payload, "阿青")
        self.assertEqual(card.to_dict(), self.payload)
        rendered = render_actor_character_card(self.template, card)
        self.assertIn("目标角色：阿青", rendered)
        self.assertIn("director_reference_archive", rendered)
        self.assertNotIn("{{", rendered)
        self.assertNotIn("DIRECTOR_ONLY", rendered)
        self.assertNotIn("characters/阿青.yaml:1", rendered)

    def test_card_rejects_target_mismatch_missing_extra_and_placeholder_sections(self):
        with self.assertRaisesRegex(ValueError, "target"):
            parse_actor_character_card(self.payload, "阿白")
        for edit in ("missing", "extra", "placeholder", "empty"):
            value = deepcopy(self.payload)
            if edit == "missing":
                del value["sections"]["PERSONA_LOAD"]
            elif edit == "extra":
                value["sections"]["PLOT_PLAN"] = "额外段落"
            else:
                value["sections"]["PERSONA_LOAD"] = "{{PERSONA_LOAD}}" if edit == "placeholder" else " "
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                parse_actor_character_card(value, "阿青")

    def test_card_budget_is_explicit_and_never_clips(self):
        self.payload["sections"] = {key: "字" * 800 for key in ACTOR_CARD_SECTIONS}
        with self.assertRaisesRegex(ValueError, "total context budget"):
            parse_actor_character_card(self.payload, "阿青")

    def test_template_requires_every_token_exactly_once(self):
        card = parse_actor_character_card(self.payload, "阿青")
        for template in (self.template + "{{PERSONA_LOAD}}",
                         self.template.replace("{{PERSONA_LOAD}}", ""),
                         self.template.replace("{{PERSONA_LOAD}}", "{{UNKNOWN}}")):
            with self.subTest(template=template[-50:]), self.assertRaisesRegex(ValueError, "exactly once"):
                render_actor_character_card(template, card)

    def test_v3_actor_request_preserves_card_and_nonactor_rejects_it(self):
        request = {"kind": "actor", "target": "阿青", "purpose": "听出迟疑",
                   "scene_moment": "看见空信封", "cue": "询问信件去向",
                   "author_prompt": "从自身处境回应。", "character_card": self.payload}
        parsed = parse_scene_material_requests_v3({"material_requests": [request]}, ["阿青"])[0]
        self.assertEqual(parsed.to_dict()["character_card"], self.payload)
        self.assertEqual(parse_scene_material_requests_v3(
            {"material_requests": [parsed.to_dict()]}, ["阿青"])[0], parsed)
        request["kind"] = "character-description"
        with self.assertRaisesRegex(ValueError, "only applies to actor"):
            parse_scene_material_requests_v3({"material_requests": [request]}, ["阿青"])


if __name__ == "__main__":
    unittest.main()
