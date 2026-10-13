from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio.project_agent.contracts import (
    ProjectAgentActionDependencies, ProjectAgentDependencies, ProjectAgentToolCall,
)
from literary_engineering_studio.project_agent.creator_persona_actions import creator_persona_update_action
from literary_engineering_studio.project_agent.prompt_policy import creator_persona_guidance
from literary_engineering_studio.project_agent.tools import (
    ACTION_TOOLS, READ_TOOLS, ProjectAgentToolDispatcher,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec


class CreatorPersonaToolTests(unittest.TestCase):
    def test_generator_and_top_agent_use_their_actual_delivery_roles(self) -> None:
        prompt = prompt_layer_spec("project_agent.creator_persona.v2").default_text

        wrapper = prompt_layer_spec("project_agent.v2.system.write.protocol").default_text
        self.assertNotIn("project_creator_persona_read", prompt)
        self.assertIn("project_creator_persona_read", wrapper)
        self.assertIn("project_creator_persona_update", wrapper)
        self.assertIn("project_creator_persona_read", READ_TOOLS)
        self.assertIn("project_creator_persona_update", ACTION_TOOLS)
        self.assertNotRegex(prompt, r"(?<!project_)creator_persona_(?:read|update)")

    def test_top_agent_can_save_and_read_versioned_creator_persona(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            (root / "project.yaml").write_text("creative_brief: {premise: rain}", encoding="utf-8")
            store = CreatorPersonaStore(Path(temporary) / "studio")
            noop = lambda _root, _arguments: {}
            reads = ProjectAgentDependencies(noop, noop, noop,
                                              creator_persona=lambda project, _args: store.read_current(project))
            actions = ProjectAgentActionDependencies(noop, noop,
                update_creator_persona=creator_persona_update_action(store.save))
            dispatcher = ProjectAgentToolDispatcher(root, reads, actions=actions,
                enabled=("project_creator_persona_read", "project_creator_persona_update"))
            result = dispatcher(ProjectAgentToolCall("request", "turn", "project_creator_persona_update", {
                "persona_text": "以读者的疑问为线索，保持人物自主行动与作品方向的稳定连续。",
                "reason": "根据初始作品要求建立主创人格",
            }))
            self.assertEqual(result["persona"]["version"], 1)
            read = dispatcher(ProjectAgentToolCall("request-2", "turn", "project_creator_persona_read", {}))
            self.assertEqual(read["active_version"], 1)
            self.assertIn("人物自主", read["active"]["text"])

    def test_top_agent_guidance_waits_for_designed_prompt(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("creative_brief: {}\n", encoding="utf-8")
            settings = {"application": {"scene_creator_v2": {"enabled": True}}}
            with self.assertRaisesRegex(RuntimeError, "prompt design is incomplete"):
                creator_persona_guidance(settings, lambda _key, _root: "[PENDING_PROMPT_DESIGN: persona]", root)
            self.assertEqual(creator_persona_guidance(settings, lambda _key, _root: "已设计的人格说明", root),
                             "已设计的人格说明")

    def test_evidence_based_repair_keeps_prior_text_and_allows_same_intent_correction(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)/'work'; root.mkdir()
            (root/'project.yaml').write_text('title: 浮月\n', encoding='utf-8')
            store = CreatorPersonaStore(Path(temporary)/'studio')
            first = store.save(root, '在任何单元里让人物坐下对话，把所有世界交给细节。', reason='初始化主创人格')
            pending = store.request_repair(root, expected_version=1, reason='单一现场偏好削弱世界讲述。', evidence=['在任何单元里让人物坐下对话'])
            self.assertEqual(pending['status'], 'needs-repair')
            self.assertEqual(pending['last_generated']['text'], first['text'])
            store.save(root, '你热爱世界、风俗与时间的广阔讲述，发展奇幻、浪漫、群体经验与鲜明人物声音。', reason='落实原作者对多种章节价值的要求')
            current = store.read_current(root)
            self.assertEqual(current['status'], 'ready')
            self.assertEqual(current['active_version'], 2)
            self.assertEqual(current['history'][0]['text'], first['text'])


if __name__ == "__main__":
    unittest.main()
