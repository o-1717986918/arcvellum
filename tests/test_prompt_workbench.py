from pathlib import Path
import json
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from literary_engineering_studio.api.routers.prompts import build_prompts_router
from literary_engineering_studio.application.prompt_workbench import PromptWorkbenchService
from literary_engineering_studio.persistence.prompt_layers import FilePromptLayerRepository


class PromptWorkbenchTests(unittest.TestCase):
    def test_project_precedence_history_activation_and_fixed_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "work"
            project.mkdir()
            (project / "project.yaml").write_text("title: Test\n", encoding="utf-8")
            service = PromptWorkbenchService(FilePromptLayerRepository(root / "app"))
            layer_id = "scene.creator.identity"
            service.save(layer_id, "全局引导", scope="global")
            service.save(layer_id, "作品引导甲", scope="project", project_root=project)
            service.save(layer_id, "作品引导乙", scope="project", project_root=project)
            self.assertEqual(service.resolve(layer_id, project).text, "作品引导乙")
            self.assertEqual(service.resolve(layer_id).text, "全局引导")
            service.activate(layer_id, 1, scope="project", project_root=project)
            self.assertEqual(service.resolve(layer_id, project).text, "作品引导甲")
            self.assertEqual(len(service.history(layer_id, scope="project", project_root=project)["versions"]), 2)
            service.reset(layer_id, scope="project", project_root=project)
            self.assertEqual(service.resolve(layer_id, project).text, "全局引导")
            service.reset(layer_id, scope="global")
            self.assertEqual(service.resolve(layer_id, project).source, "package")
            self.assertEqual(len(service.history(layer_id, scope="project", project_root=project)["versions"]), 2)
            with self.assertRaisesRegex(ValueError, "changed since"):
                service.save(layer_id, "覆盖别人修改", scope="project", project_root=project,
                             expected_digest="0" * 64)
            with self.assertRaises(ValueError):
                service.save("scene.protocol", "越权", scope="global")

    def test_http_catalog_preview_and_edit_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            service = PromptWorkbenchService(FilePromptLayerRepository(Path(directory)))
            app = FastAPI()
            app.include_router(build_prompts_router(service))
            client = TestClient(app)
            catalog = client.get("/prompts/catalog")
            self.assertEqual(catalog.status_code, 200)
            self.assertEqual(catalog.json()["schema"], "arcvellum/prompt-workbench/v2")
            self.assertTrue(catalog.json()["formal_assets"])
            self.assertTrue(catalog.json()["flow_tree"])
            formal = next(layer for layer in catalog.json()["layers"]
                          if layer["responsibility"] == "formal-asset")
            self.assertTrue(formal["editable"])
            self.assertTrue(formal["effective_text"])
            formal_saved = client.put(
                f"/prompts/layers/{formal['layer_id']}",
                json={"scope": "global", "text": "新的正式任务正文。"},
            )
            self.assertEqual(formal_saved.status_code, 200)
            formal_preview = client.post(
                "/prompts/preview", json={"layer_ids": [formal["layer_id"]]},
            )
            self.assertEqual(formal_preview.json()["texts"][formal["layer_id"]], "新的正式任务正文。")
            self.assertIn("新的正式任务正文。", formal_preview.json()["assembled_template"])
            self.assertIn("## Allowed Outputs", formal_preview.json()["assembled_template"])
            denied = client.put("/prompts/layers/scene.protocol", json={"scope": "global", "text": "越权"})
            self.assertEqual(denied.status_code, 400)
            saved = client.put("/prompts/layers/scene.creator.create", json={"scope": "global", "text": "让读者多看一眼空杯"})
            self.assertEqual(saved.status_code, 200)
            preview = client.post("/prompts/preview", json={"layer_ids": ["scene.protocol", "scene.creator.create"]})
            self.assertEqual(preview.json()["texts"]["scene.creator.create"], "让读者多看一眼空杯")
            self.assertIn("让读者多看一眼空杯", preview.json()["assembled_template"])
            self.assertIn("〈运行时资料 1〉", preview.json()["assembled_template"])
            self.assertEqual(preview.json()["assembly_kind"], "template-with-runtime-slots")
            reset = client.post("/prompts/layers/scene.creator.create/reset",
                                json={"scope": "global", "expected_digest": saved.json()["effective"]["digest"]})
            self.assertEqual(reset.status_code, 200)
            self.assertEqual(reset.json()["effective"]["source"], "package")
            catalog_ids = {layer["layer_id"] for layer in catalog.json()["layers"]}
            self.assertIn("formal.asset.route.longform-planning.reader-experience.v1", catalog_ids)
            self.assertIn("scene.describer.event", catalog_ids)
            self.assertNotIn("scene.describer.object", catalog_ids)
            leaves = {leaf["layer_id"] for group in catalog.json()["flow_tree"]
                      for stage in group["children"] for leaf in stage["children"]}
            self.assertEqual(catalog_ids, leaves)
            self.assertNotIn("scene.length.legacy", catalog_ids)
            self.assertNotIn("legacy.template.scene_generation_system", catalog_ids)
            self.assertNotIn("formal.asset.route.scene-development.state-apply.v1", catalog_ids)
            self.assertEqual([group["id"] for group in catalog.json()["flow_tree"]],
                             ["direction", "source", "planning", "scene", "audit", "release", "execution"])
            self.assertEqual(next(layer for layer in catalog.json()["layers"]
                                  if layer["layer_id"] == "scene.actor.interaction.protocol")["editable"], False)
            self.assertIn("[[ARCVELLUM_PROMPT_", next(layer for layer in catalog.json()["layers"]
                          if layer["layer_id"] == "scene.actor.interaction.protocol")["effective_text"])
            denied_non_model = client.put("/prompts/layers/formal.asset.route.scene-development.state-apply.v1",
                                          json={"scope": "global", "text": "不会成为模型提示"})
            self.assertEqual(denied_non_model.status_code, 400)

    def test_steward_guidance_is_versioned_but_decision_contract_is_fixed(self):
        from literary_engineering_studio.advisor.creative_steward import _decision_prompt

        with tempfile.TemporaryDirectory() as directory:
            service = PromptWorkbenchService(FilePromptLayerRepository(Path(directory)))
            service.save("steward.identity", "比较角色是否保留有意沉默。", scope="global")
            guidance = service.resolve("steward.identity").text
            rendered = _decision_prompt({"options": [{"id": "yes"}]}, "继续写", literary_guidance=guidance)
            self.assertIn(guidance, rendered)
            self.assertIn("Return JSON only", rendered)
            self.assertIn("selected_option", rendered)
            assembled = service.snapshot(("steward.identity",))
            self.assertIn(guidance, assembled["assembled_template"])

    def test_identity_previews_place_persona_after_fixed_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            service = PromptWorkbenchService(FilePromptLayerRepository(Path(directory)))
            service.save("advisor.persona.cold-reader", "只根据已给出的正文判断读者能否回看线索。", scope="global")
            advisor = service.snapshot(("advisor.persona.cold-reader",))["assembled_template"]
            self.assertIn("只根据已给出的正文判断读者能否回看线索。", advisor)
            self.assertLess(advisor.index("顾问宪法"), advisor.index("只根据已给出的正文"))
            self.assertIn(service.resolve("advisor.identity").text, advisor)
            actor = service.snapshot(("scene.actor.identity",))["assembled_template"]
            self.assertIn("〈运行时作品人设与语言标签〉", actor)
            self.assertIn(service.resolve("scene.actor.identity").text, actor)
            self.assertIn("scene.actor.immersion.protocol", [entry["layer_id"] for entry in
                                                         service.snapshot(("scene.actor.identity",))["layers"]])
            environment = service.snapshot(("scene.environment.identity",))["assembled_template"]
            self.assertIn("〈导演生成的环境六区块人格初始化〉", environment)

    def test_corrupt_active_history_is_rejected_instead_of_falling_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "prompt-layers" / "global" / "scene.creator.identity.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"schema": "arcvellum/prompt-layer-history/v1",
                                        "active": 7, "versions": []}), encoding="utf-8")
            service = PromptWorkbenchService(FilePromptLayerRepository(root))
            with self.assertRaisesRegex(ValueError, "invalid active version"):
                service.resolve("scene.creator.identity")

    def test_retired_project_template_edit_endpoints_are_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            service = PromptWorkbenchService(FilePromptLayerRepository(Path(directory)))
            for layer_id in ("legacy.template.scene_generation_system", "legacy.template.scene_generation_user"):
                with self.subTest(layer_id=layer_id), self.assertRaisesRegex(ValueError, "unknown prompt layer"):
                    service.save(layer_id, "旧项目覆盖", scope="global")


if __name__ == "__main__":
    unittest.main()
