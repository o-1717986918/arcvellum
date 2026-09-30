"""Published prompt examples must work with the runtime's real input contracts."""

import json
import unittest

from literary_engineering_studio_engine.public.literary import (
    CreativeIntentV1, parse_creator_material_plan, parse_scene_material_requests_v3,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from literary_engineering_studio.runtimes.pi_scene_payload import (
    creative_result_from_payload, review_result_from_payload,
)
from literary_engineering_studio.runtimes.scene_creator_material_policy import material_selection_error


def json_examples(layer_id):
    return [json.loads(line) for line in prompt_layer_spec(layer_id).default_text.splitlines()
            if line.startswith("{")]


class V2PromptExampleTests(unittest.TestCase):
    def test_creator_examples_parse_and_require_real_candidate_choices(self):
        opening, final = json_examples("scene.v2.creator.protocol")
        plan = parse_creator_material_plan(opening)
        self.assertEqual(plan.required_kinds, ("environment",))
        request, = parse_scene_material_requests_v3(opening, ["阿青"])
        self.assertEqual(request.kind, "environment")
        intent = CreativeIntentV1.from_payload(opening["creative_intent"])
        self.assertTrue(intent.reader_experience)
        result = creative_result_from_payload(final)
        self.assertTrue(result.prose)
        candidate_id = final["material_decisions"][0]["candidate_id"]
        self.assertEqual(material_selection_error(final, [candidate_id], []), "")
        self.assertTrue(material_selection_error(final, ["a-different-candidate"], []))

    def test_review_example_parses_as_a_review_not_a_commit_receipt(self):
        example, = json_examples("scene.v2.review.protocol")
        result = review_result_from_payload(example)
        self.assertEqual(result.decision.value, "pass")
        self.assertTrue(result.summary)
        self.assertEqual(result.revision_instructions, ())
        self.assertNotIn("sha256", example)


if __name__ == "__main__":
    unittest.main()
