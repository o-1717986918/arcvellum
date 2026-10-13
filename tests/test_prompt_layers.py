from pathlib import Path
import unittest

from literary_engineering_studio_engine.public.prompting import (
    PromptLayerOverride, list_prompt_layer_specs, prompt_assembly_manifest,
    prompt_layer_spec, resolve_prompt_layer,
)


class PromptLayerTests(unittest.TestCase):
    def test_project_override_beats_global_and_manifest_records_digest(self):
        spec = prompt_layer_spec("scene.creator.identity")
        self.assertEqual(resolve_prompt_layer(spec).version, str(spec.package_version))
        global_edit = PromptLayerOverride(spec.layer_id, "global", 3, "全局主创")
        project_edit = PromptLayerOverride(spec.layer_id, "project", 2, "本作主创")
        effective = resolve_prompt_layer(spec, global_override=global_edit, project_override=project_edit)
        self.assertEqual((effective.source, effective.text, effective.version), ("project", "本作主创", "2"))
        self.assertEqual(len(prompt_assembly_manifest([effective])["digest"]), 64)

    def test_protocol_cannot_be_edited(self):
        spec = prompt_layer_spec("scene.protocol")
        with self.assertRaises(ValueError):
            resolve_prompt_layer(spec, global_override=PromptLayerOverride(spec.layer_id, "global", 1, "越权"))

    def test_material_request_protocol_defines_target_for_each_kind(self):
        spec = prompt_layer_spec("scene.creator.material-request.protocol")
        self.assertEqual(spec.package_version, 4)
        for phrase in (
            "actor 与 character-description 使用已有参与人物的精确姓名",
            "environment 可选地方、景观、季节或感官主题",
            "event-narration 可选世界机制、风俗、历史或场外事件",
            "scene-description 可选空间、群像或并行言行",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, spec.default_text)

    def test_worker_profile_registry_mirrors_runtime_sources(self):
        repository = Path(__file__).resolve().parents[1]
        for name, layer_id in (
            ("main-creative-agent", "pi.worker.main-creative.protocol"),
            ("incremental-repair", "pi.worker.incremental-repair.protocol"),
            ("generic-role", "pi.worker.generic-role.protocol"),
            ("conversation-system", "pi.conversation.system"),
        ):
            with self.subTest(profile=name):
                actual = (repository / "workers" / "pi-worker" / "profiles" / f"{name}.md").read_text(encoding="utf-8")
                self.assertEqual(prompt_layer_spec(layer_id).default_text, actual.strip())

    def test_registered_layer_files_are_complete_and_no_resource_is_orphaned(self):
        repository = Path(__file__).resolve().parents[1]
        resources = repository / "src" / "literary_engineering_studio_engine" / "_engine" / "templates" / "prompt_layers"
        from_files = {path.stem for path in resources.glob("*.md")}
        from_catalog = {spec.layer_id for spec in list_prompt_layer_specs()}
        self.assertEqual(from_files, from_catalog)
        for retired in ("legacy.template.scene_generation_system", "scene.length.legacy",
                        "scene.sources", "scene.interaction.direction.protocol"):
            with self.subTest(retired=retired), self.assertRaisesRegex(ValueError, "unknown prompt layer"):
                prompt_layer_spec(retired)


if __name__ == "__main__":
    unittest.main()
