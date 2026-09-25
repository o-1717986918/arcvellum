from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from literary_engineering_studio.project_agent.contracts import (
    ProjectAgentActionDependencies,
    ProjectAgentDependencies,
    ProjectAgentToolCall,
)
from literary_engineering_studio.project_agent.tools import ProjectAgentToolDispatcher
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio_engine.public.literary import (
    actor_personas_for_participants,
    list_actor_personas,
    save_actor_persona,
)
from tests.test_lean_kernel_v2_pi_runtime import _brief


class ActorPersonaTests(unittest.TestCase):
    def test_existing_four_section_profile_loads_with_empty_literary_style(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "characters").mkdir()
            (root / "characters" / "xu_yao.yaml").write_text(
                "character_id: character/xu_yao\nname: 许遥\n", encoding="utf-8"
            )
            old = {
                "PERSONA_LOAD": ["SELF_CLAIM_XU_YAO"],
                "PERSONALITY_CORE": ["TRAIT_WARY"],
                "PERSONALITY_PUBLIC": ["TRAIT_PLAYFUL"],
                "LANGUAGE_STYLE": ["POLISHED"],
            }
            (root / "characters" / "_actor_personas.json").write_text(
                json.dumps({"schema": "arcvellum/actor-personas/v1", "profiles": {"character/xu_yao": old}}),
                encoding="utf-8",
            )
            profile = list_actor_personas(root)["characters"][0]["sections"]
            self.assertEqual(profile["LITERATURE_STYLE"], [])
            initialization = actor_personas_for_participants(root, ["character/xu_yao"])["character/xu_yao"]
            self.assertIn("[LITERATURE_STYLE]", initialization)

    def test_project_agent_can_read_and_replace_every_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.yaml").write_text("title: test\n", encoding="utf-8")
            characters = root / "characters"
            characters.mkdir()
            (characters / "xu_yao.yaml").write_text(
                "character_id: character/xu_yao\nname: 许遥\nrole: 飞行员\n", encoding="utf-8"
            )
            read = lambda path, _args: list_actor_personas(path)
            write = lambda path, args: save_actor_persona(path, args["character_id"], args["sections"])
            dependencies = ProjectAgentDependencies(read, read, read, actor_personas=read)
            actions = ProjectAgentActionDependencies(write, write, update_actor_persona=write)
            dispatcher = ProjectAgentToolDispatcher(
                root, dependencies, actions=actions,
                enabled=("project_actor_personas", "project_actor_persona_update"),
            )
            before = dispatcher(ProjectAgentToolCall("r1", "t1", "project_actor_personas", {}))
            self.assertFalse(before["characters"][0]["configured"])
            self.assertEqual(before["default_language_style"], ["ANTI_PLAIN", "POLISHED", "ANTI_SHORT_SENTENCES"])

            sections = {
                "PERSONA_LOAD": ["SELF_CLAIM_XU_YAO", "IDENTITY_PILOT"],
                "PERSONALITY_CORE": ["TRAIT_STUBBORN"],
                "PERSONALITY_PUBLIC": ["TRAIT_PLAYFUL", "ANTI_CONCISE"],
                "LANGUAGE_STYLE": ["POLISHED", "SPOKEN_AND_WARM"],
                "LITERATURE_STYLE": ["KAFKA_LIKE", "ABSURDITY_STYLE"],
            }
            dispatcher(ProjectAgentToolCall("r2", "t1", "project_actor_persona_update", {
                "character_id": "character/xu_yao", "sections": sections,
            }))
            after = dispatcher(ProjectAgentToolCall("r3", "t1", "project_actor_personas", {}))
            self.assertEqual(after["characters"][0]["sections"], sections)
            prompt = actor_personas_for_participants(root, ["character/xu_yao"])["character/xu_yao"]
            self.assertIn("[LANGUAGE_STYLE]\nPOLISHED\nSPOKEN_AND_WARM", prompt)
            self.assertIn("[LITERATURE_STYLE]\nKAFKA_LIKE\nABSURDITY_STYLE", prompt)
            self.assertNotIn("ANTI_SIMPLISTIC", prompt)

            changed = {**sections, "PERSONALITY_PUBLIC": ["TRAIT_SEVERE"], "LANGUAGE_STYLE": []}
            save_actor_persona(root, "character/xu_yao", changed)
            self.assertEqual(list_actor_personas(root)["characters"][0]["sections"], changed)
            with self.assertRaisesRegex(ValueError, "existing character_id"):
                save_actor_persona(root, "character/missing", sections)
            with self.assertRaisesRegex(ValueError, "uppercase English"):
                save_actor_persona(root, "character/xu_yao", {**sections, "PERSONALITY_CORE": ["傲娇"]})

    def test_existing_scene_transaction_keeps_its_actor_persona_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            characters = root / "characters"
            characters.mkdir()
            (characters / "brother.yaml").write_text(
                "character_id: character/protagonist\nname: 哥哥\nrole: 家人\n", encoding="utf-8"
            )
            sections = {
                "PERSONA_LOAD": ["SELF_CLAIM_OLDER_BROTHER"],
                "PERSONALITY_CORE": ["TRAIT_GUARDED"],
                "PERSONALITY_PUBLIC": ["TRAIT_QUIET"],
                "LANGUAGE_STYLE": ["POLISHED"],
                "LITERATURE_STYLE": [],
            }
            save_actor_persona(root, "character/protagonist", sections)
            runtime = PiSceneTransactionRuntime({}, project_root=root, data_root=root / "runtime")
            original = runtime._expression_projection(_brief(), "scene-run-1")
            save_actor_persona(root, "character/protagonist", {**sections, "PERSONALITY_PUBLIC": ["TRAIT_WITTY"]})
            same_transaction = runtime._expression_projection(_brief(), "scene-run-1")
            next_transaction = runtime._expression_projection(_brief(), "scene-run-2")
            self.assertEqual(same_transaction, original)
            self.assertIn("TRAIT_WITTY", next_transaction["actor_personas"]["character/protagonist"])
            self.assertNotEqual(next_transaction, original)


if __name__ == "__main__":
    unittest.main()
