"""v2 layers are observable in the existing prompt tree without a fallback."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.application.prompt_workbench import PromptWorkbenchService
from literary_engineering_studio.application.prompt_flow import stage_for_prompt
from literary_engineering_studio.persistence.prompt_layers import FilePromptLayerRepository
from literary_engineering_studio_engine.public.prompting import list_prompt_layer_specs


class V2PromptFlowTests(unittest.TestCase):
    def test_all_v2_layers_appear_once_in_the_actual_catalog(self):
        with TemporaryDirectory() as directory:
            catalog = PromptWorkbenchService(FilePromptLayerRepository(Path(directory))).catalog()
        layers = {row["layer_id"]: row for row in catalog["layers"]}
        leaves = [leaf["layer_id"] for group in catalog["flow_tree"]
                  for stage in group["children"] for leaf in stage["children"]]
        v2 = [spec.layer_id for spec in list_prompt_layer_specs()
              if spec.layer_id.startswith(("scene.v2.", "project_agent.v2.")) or spec.layer_id == "project_agent.creator_persona.v2"]
        self.assertEqual(len(v2), 27)
        for layer_id in v2:
            with self.subTest(layer=layer_id):
                self.assertEqual(leaves.count(layer_id), 1)
                self.assertTrue(layers[layer_id]["effective_text"])
        self.assertEqual(layers["scene.v2.creator.create"]["flow_stage"], "scene.prose")
        self.assertEqual(layers["scene.v2.material.actor"]["flow_stage"], "scene.actor")
        self.assertEqual(layers["scene.v2.material.event-narration"]["flow_stage"], "scene.event")
        self.assertEqual(layers["project_agent.creator_persona.v2"]["flow_stage"], "direction.project")

    def test_unknown_v2_layer_still_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, "no creative flow location"):
            stage_for_prompt({"layer_id": "scene.v2.unknown", "responsibility": "stage"})


if __name__ == "__main__":
    unittest.main()
