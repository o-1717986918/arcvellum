"""Actor card freezing, resumption, and system-prompt adapter tests."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_creator_memory import SceneCreatorMemoryV1
from literary_engineering_studio.runtimes.scene_creator_v2_materials import SceneCreatorV2MaterialCoordinator
from literary_engineering_studio.runtimes.scene_creator_workspace import SceneCreatorWorkspace
from literary_engineering_studio_engine.public.literary import (
    CreatorMaterialPlanV1, LengthTarget, RhythmDirective, SceneBrief, SceneMaterialRequestV3,
    SceneRisk, SceneRiskLevel, StyleMountRef, parse_actor_character_card,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from tests.actor_card_fixtures import actor_card_payload


class ActorCardRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "work"
        self.project.mkdir()
        (self.project / "project.yaml").write_text("creative_brief:\n  premise: 空信封\n", encoding="utf-8")
        self.studio = self.root / "studio"
        self.layers = {key: "designed" for key in (
            "scene.v2.material.shared.protocol", "scene.v2.material.output.protocol")}
        self.layers["scene.v2.material.actor"] = prompt_layer_spec("scene.v2.material.actor").default_text
        self.coordinator = SceneCreatorV2MaterialCoordinator(
            self.root / "tx", SceneCreatorWorkspace(self.project, self.studio), self.layers,
            scene_id="s1", actor_personas={"阿青": "LEGACY_SOURCE_ONLY"})
        self.coordinator.save_plan(CreatorMaterialPlanV1(("actor",), "先听人物回应"))
        self.request = SceneMaterialRequestV3(
            "actor", "阿青", "维持误会", "发现空信封时", "只看见空信封", "依据自身处境自主回应。",
            character_card=parse_actor_character_card(actor_card_payload(), "阿青"))
        self.calls = []

    def invoke(self, call):
        self.calls.append(call)
        return {"candidates": [{"spoken": "信呢？", "first_person_action": "我捏住信封。",
                                "focus": "迟疑"}], "__answer": "actor-answer",
                "__initialization_answer": "initialized"}

    def test_first_card_required_then_reuses_frozen_card_and_history(self):
        with self.assertRaisesRegex(ValueError, "first actor request"):
            self.coordinator.execute(replace(self.request, character_card=None), self.invoke)
        self.coordinator.execute(self.request, self.invoke)
        followup = replace(self.request, cue="有人追问信去了哪", character_card=None)
        self.coordinator.execute(followup, self.invoke)
        self.assertEqual(self.calls[0].initialization, self.calls[1].initialization)
        self.assertEqual(self.calls[1].history, ((self.calls[0].prompt, "actor-answer"),))
        self.assertEqual(self.calls[1].initialization_answer, "initialized")
        self.assertNotIn("LEGACY_SOURCE_ONLY", self.calls[0].initialization)
        self.assertNotIn("DIRECTOR_ONLY", self.calls[0].initialization)
        records = [json.loads(path.read_text(encoding="utf-8"))
                   for path in (self.coordinator.root / "calls").glob("*.json")]
        self.assertEqual({row["character_card_digest"] for row in records},
                         {self.calls[0].character_card_digest})
        self.assertEqual(len(self.calls[0].character_card_digest), 64)
        self.coordinator.assert_ready_for_prose()

    def test_different_card_rejected_and_original_card_available_to_creator(self):
        self.coordinator.execute(self.request, self.invoke)
        value = deepcopy(actor_card_payload())
        value["sections"]["CORE_IDENTITY"] = "姓名：阿青；改写身份。"
        with self.assertRaisesRegex(ValueError, "frozen"):
            self.coordinator.execute(replace(self.request, character_card=parse_actor_character_card(
                value, "阿青")), self.invoke)
        context = self.coordinator.creator_card_context()
        self.assertEqual(context["stable_persona_sources"]["阿青"], "LEGACY_SOURCE_ONLY")
        self.assertEqual(context["frozen_scene_cards"][0]["card"], self.request.character_card.to_dict())
        self.assertEqual(len(self.calls), 1)

    def test_interrupted_call_can_resume_without_resubmitting_card(self):
        def interrupted(_call):
            raise RuntimeError("interrupted")
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            self.coordinator.execute(self.request, interrupted)
        resumed = SceneCreatorV2MaterialCoordinator(
            self.coordinator.root, self.coordinator.workspace, self.layers, scene_id="s1")
        resumed.execute(replace(self.request, character_card=None), self.invoke)
        self.assertIn("目标角色：阿青", self.calls[0].initialization)
        self.assertFalse(self.calls[0].history)

    def test_v2_memory_saves_whole_large_card_and_keeps_legacy_limit(self):
        value = actor_card_payload()
        value["sections"] = {key: text + "文" * 520 for key, text in value["sections"].items()}
        request = replace(self.request, character_card=parse_actor_character_card(value, "阿青"))
        payload = {"material_requests": [request.to_dict()]}
        brief = self.brief()
        with self.assertRaisesRegex(ValueError, "memory limit"):
            SceneCreatorMemoryV1("s1").record_creator(payload, brief, prompt="test")
        memory = SceneCreatorMemoryV1("s1")
        memory.record_creator(payload, brief, prompt="test", request_limit_chars=160_000)
        path = self.root / "memory.json"
        memory.save(path)
        self.assertEqual(SceneCreatorMemoryV1.load(path, "s1", request_limit_chars=160_000).pending_request,
                         payload)
        with self.assertRaisesRegex(ValueError, "memory limit"):
            SceneCreatorMemoryV1.load(path, "s1")

    def test_opted_in_actor_transaction_resumes_with_the_rendered_system_card(self):
        CreatorPersonaStore(self.studio).save(
            self.project, "保留误会，以人物的迟疑和空信封维持读者疑问。", reason="作品初始意图")
        value = actor_card_payload()
        value["sections"] = {key: text + "文" * 520 for key, text in value["sections"].items()}
        gateway = ActorGateway(replace(self.request, character_card=parse_actor_character_card(value, "阿青")))
        runtime = PiSceneTransactionRuntime(
            {"application": {"scene_creator_v2": {"enabled": True}}},
            project_root=self.project, data_root=self.studio, gateway=gateway,
            prompt_snapshot_provider=lambda ids, _root: {
                "schema": "arcvellum/prompt-assembly/v1", "digest": "test-designed", "layers": [],
                "texts": {key: self.layers.get(key, "designed") for key in ids}})
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            runtime.create_scene("tx-actor", self.brief())
        result = runtime.create_scene("tx-actor", self.brief())
        self.assertIn("空信封", result.prose)
        self.assertEqual(gateway.creator_calls, 2)
        self.assertEqual(gateway.actor_attempts, 2)
        self.assertIn("目标角色：阿青", gateway.initialization)
        self.assertNotIn("{{PERSONA_LOAD}}", gateway.initialization)
        self.assertNotIn("DIRECTOR_ONLY", gateway.initialization)
        self.assertEqual(gateway.creator_context["frozen_scene_cards"][0]["card"], value)

    @staticmethod
    def brief():
        return SceneBrief("s1", "寻找信", "误会尚未解开", ("阿青",), (), (), (),
                          RhythmDirective(), LengthTarget(), StyleMountRef(),
                          SceneRisk(SceneRiskLevel.LOW), ())


class ActorGateway:
    def __init__(self, request):
        self.request = request
        self.creator_calls = 0
        self.actor_attempts = 0
        self.initialization = ""
        self.creator_context = {}

    def run(self, _root, prompt, **_kwargs):
        task = json.loads(json.loads(prompt)["prompt"])
        self.creator_calls += 1
        if self.creator_calls == 1:
            answer = {"material_plan": {"required_kinds": ["actor"], "reason": "人物先回应"},
                      "material_requests": [self.request.to_dict()]}
        else:
            self.creator_context = task["actor_card_context"]
            identifier = re.search(r"v2:[a-f0-9]+:1", task["material_index"]).group()
            answer = {"prose": "阿青捏住空信封，轻声问：‘信呢？’", "decision_summary": "保留迟疑。",
                      "material_decisions": [{"candidate_id": identifier, "decision": "adapt",
                                               "reason": "调整成正文叙述"}], "scene_delta": {}}
        return RoleConversationResult("pi-worker", "run", "test/model", json.dumps(answer, ensure_ascii=False))

    def run_actor_turn(self, _root, *, initialization, **_kwargs):
        self.actor_attempts += 1
        self.initialization = initialization
        if self.actor_attempts == 1:
            raise RuntimeError("interrupted")
        answer = {"candidates": [{"spoken": "信呢？", "first_person_action": "我捏住空信封。",
                                  "focus": "迟疑"}]}
        return RoleConversationResult("pi-worker", "run", "test/model", json.dumps(answer, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
