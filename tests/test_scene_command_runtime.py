from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio_engine.command_line.commands import scene
from literary_engineering_studio_engine.command_line.commands import scene_prose


class SceneCommandRuntimeTests(unittest.TestCase):
    def test_generate_scene_rebuilds_missing_context_without_runtime_name_errors(self):
        """Exercise the command branch the autopilot uses before prose work."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene_path = root / "scenes" / "scene_0001.yaml"
            scene_path.parent.mkdir(parents=True)
            scene_path.write_text("scene_id: scene_0001\n", encoding="utf-8")
            args = Namespace(
                command="generate-scene",
                project=str(root),
                scene="scenes/scene_0001.yaml",
                context="",
                rebuild_context=False,
                query="",
                composition="",
                out="",
                allow_unselected_composition=False,
                allow_missing_composition=False,
                materialization_scope="scene",
            )
            context = root / "memory" / "context_packets" / "scene_0001.md"
            prompt_manifest = root / "drafts" / "candidates" / "scene_0001-platform-agent.prompt.json"
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"

            class _ContextResult:
                output_path = context

            class _PromptPack:
                composition_path = root / "drafts" / "compositions" / "scene_0001_composition.json"

            class _GenerationResult:
                task_path = root / "drafts" / "candidates" / "scene_0001-platform-agent.agent_tasks.md"
                expected_report_path = candidate
                expected_json_path = candidate.with_suffix(".json")

            with (
                patch.object(scene_prose, "build_context_packet", return_value=_ContextResult()) as build_context,
                patch.object(scene_prose, "ensure_scene_pre_generation_tasks_completed"),
                patch.object(scene_prose, "build_scene_prompt_pack", return_value=_PromptPack()),
                patch.object(scene_prose, "scene_character_asset_requirements", return_value=[]),
                patch.object(scene_prose, "write_prompt_manifest"),
                patch.object(scene_prose, "write_platform_scene_generation_task", return_value=_GenerationResult()),
                patch.object(scene_prose, "print_agent_task_notice"),
            ):
                self.assertEqual(scene.handle(args, parser=None), 0)

            build_context.assert_called_once()


if __name__ == "__main__":
    unittest.main()
