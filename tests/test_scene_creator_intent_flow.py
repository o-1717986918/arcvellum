from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.application.prompt_workbench import PromptWorkbenchService
from literary_engineering_studio.persistence.prompt_layers import FilePromptLayerRepository
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_creator_material_policy import (
    initial_material_choice_error, material_selection_error,
)
from literary_engineering_studio_engine.public.literary import VerificationReport
from tests.test_lean_kernel_v2_pi_runtime import _brief
from tests.test_scene_interaction import _fixture


_INTENT = {"reader_experience": "先让取信一事显得平常，稍后才使它成为关系裂缝的线索",
           "reader_misreads": "读者暂信取信只是误会", "withheld": "谁先发现了空抽屉"}


class _IntentGateway:
    def __init__(self, *, request: bool):
        self.request = request
        self.calls: list[tuple[str, str]] = []
        self.role_turns: list[tuple[str, int]] = []

    def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
        self.calls.append((role, prompt))
        if role == "reviewer":
            answer = {"decision": "pass", "summary": "有线索的短场成立", "evidence": [], "revision_instructions": []}
        elif self.request and len([item for item in self.calls if item[0] == "worker"]) == 1:
            answer = {"creative_intent": _INTENT, "material_requests": [{
                "kind": "event-narration", "target": "昨夜取信", "purpose": "让读者重新理解今日的沉默",
                "scene_moment": "承认取信之前", "cue": "已确认信在昨夜被取走",
            }]}
        else:
            answer = {"creative_intent": _INTENT, "prose": "她把信推了过去，眼睛仍盯着空抽屉。",
                      "decision_summary": "以日常动作留下疑问。", "material_skip_reason": "现有日常动作已经承载留白，额外取材会让这个短场解释过度。", "scene_delta": {},
                      "material_decisions": [{"candidate_id": "d1:1", "decision": "adapt", "reason": "保留缺口，删去解释"}]}
        return RoleConversationResult("pi-worker", "fake", "test/model", json.dumps(answer, ensure_ascii=False))

    def run_role_turn(self, workspace, *, role, initialization, history, prompt, timeout, event_sink=None):
        self.role_turns.append((role, len(history)))
        candidate = {"text": "昨夜信被取走时，抽屉尚未上锁；今晨妹妹才发现空处。", "focus": "把已发生的事延迟交给读者"}
        if role == "event-narrator":
            candidate.update({"basis": "confirmed", "source_note": "场景已确认来源：昨夜取信"})
        answer = {"candidates": [candidate]}
        return RoleConversationResult("pi-worker", "desc", "test/model", json.dumps(answer, ensure_ascii=False))


class CreatorIntentFlowTests(unittest.TestCase):
    def test_empty_library_is_not_a_literary_reason_to_skip_agents(self):
        self.assertIn("empty candidate library", initial_material_choice_error({
            "material_requests": [],
            "material_skip_reason": "只读素材库为空，没有候选可读，所以由主创直接成稿。",
        }))
        self.assertEqual(initial_material_choice_error({
            "material_requests": [],
            "material_skip_reason": "这一短场只需保留人物停顿，另取素材会解释掉读者能推想的空白。",
        }), "")

    def test_material_choice_must_name_a_real_candidate(self):
        known = ["d1:1"]
        self.assertIn("real candidate", material_selection_error({"material_decisions": []}, known, []))
        self.assertIn("known candidate IDs", material_selection_error({"material_decisions": [
            {"candidate_id": "", "decision": "discard", "reason": "目录为空"},
        ]}, known, []))
        self.assertEqual(material_selection_error({"material_decisions": [
            {"candidate_id": "d1:1", "decision": "adapt", "reason": "保留可回看的线索"},
        ]}, known, []), "")

    def test_empty_library_reason_is_repaired_into_creator_directed_material_request(self):
        class Gateway(_IntentGateway):
            def __init__(self):
                super().__init__(request=False)

            def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
                if role == "worker" and len(self.calls) < 2:
                    self.calls.append((role, prompt))
                    answer = ({"creative_intent": _INTENT, "prose": "她还在等。", "scene_delta": {},
                               "material_requests": [], "material_skip_reason": "素材库为空，没有候选可读。"}
                              if len(self.calls) == 1 else
                              {"creative_intent": _INTENT, "material_requests": [{
                                  "kind": "event-narration", "target": "昨夜取信",
                                  "purpose": "让读者重新理解今日沉默里被藏起的信",
                                  "scene_moment": "她推信之前", "cue": "信已在昨夜被取走",
                              }]})
                    return RoleConversationResult("pi-worker", "fake", "test/model", json.dumps(answer, ensure_ascii=False))
                return super().run(workspace, prompt, role=role, timeout=timeout,
                                   event_sink=event_sink, cancel_event=cancel_event)

        material = "一级候选\n" + json.dumps({"description_candidates": [{
            "candidate_id": "d1:1", "kind": "event-narration", "target": "昨夜取信",
            "purpose": "改变读者认知", "scene_moment": "她推信之前", "text": "信昨夜已不在抽屉。",
            "basis": "confirmed", "source_note": "已确认来源",
        }]}, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = Gateway()
            runtime = PiSceneTransactionRuntime({"application": {"scene_performance_agents": {"enabled": True}}},
                                                project_root=root, data_root=root / ".studio", gateway=gateway)
            with patch("literary_engineering_studio.runtimes.pi_scene_transaction.fulfill_scene_material_requests",
                       return_value=material) as fulfill:
                result = runtime.create_scene("tx-empty-repair", _brief())
            self.assertIn("空抽屉", result.prose)
            self.assertEqual(fulfill.call_count, 1)
            self.assertEqual(len([role for role, _ in gateway.calls if role == "worker"]), 3)
            self.assertIn("空素材目录是正常初态", gateway.calls[1][1])
            self.assertNotIn("信昨夜已不在抽屉", gateway.calls[-1][1])

    def test_creator_repairs_a_fabricated_material_decision(self):
        class Gateway(_IntentGateway):
            def __init__(self):
                super().__init__(request=True)

            def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
                if role == "worker" and len([item for item in self.calls if item[0] == "worker"]) == 1:
                    self.calls.append((role, prompt))
                    answer = {"creative_intent": _INTENT, "prose": "她把信推了过去。", "scene_delta": {},
                              "material_decisions": [{"candidate_id": "", "decision": "discard",
                                                      "reason": "目录为空"}]}
                    return RoleConversationResult("pi-worker", "fake", "test/model", json.dumps(answer, ensure_ascii=False))
                return super().run(workspace, prompt, role=role, timeout=timeout,
                                   event_sink=event_sink, cancel_event=cancel_event)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = Gateway()
            runtime = PiSceneTransactionRuntime({"application": {"scene_performance_agents": {"enabled": True}}},
                                                project_root=root, data_root=root / ".studio", gateway=gateway)
            runtime.create_scene("tx-selection-repair", _brief())
            workers = [prompt for role, prompt in gateway.calls if role == "worker"]
            self.assertEqual(len(workers), 3)
            self.assertIn("上一回答没有给出可核验的素材取舍", workers[-1])
            memory = json.loads((root / ".studio/scene-transactions/tx-selection-repair/scene_creator_memory.json")
                                .read_text(encoding="utf-8"))
            self.assertEqual(memory["material_decisions"][0]["candidate_id"], "d1:1")

    def test_enabled_materials_require_a_reason_for_first_direct_draft(self):
        class UnreasonedGateway(_IntentGateway):
            def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
                result = super().run(workspace, prompt, role=role, timeout=timeout,
                                     event_sink=event_sink, cancel_event=cancel_event)
                payload = json.loads(result.answer)
                payload.pop("material_skip_reason", None)
                return RoleConversationResult(result.runtime, result.run_id, result.model,
                                              json.dumps(payload, ensure_ascii=False))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = PiSceneTransactionRuntime({"application": {"scene_performance_agents": {"enabled": True}}},
                                                project_root=root, data_root=root / ".studio",
                                                gateway=UnreasonedGateway(request=False))
            with self.assertRaisesRegex(ValueError, "material_skip_reason"):
                runtime.create_scene("tx-unreasoned", _brief())

    def test_creator_prompt_versions_stay_fixed_through_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.yaml").write_text("title: Test\n", encoding="utf-8")
            workbench = PromptWorkbenchService(FilePromptLayerRepository(root / ".studio"))
            workbench.save("scene.creator.identity", "以旧杯子的使用痕迹观察关系。", scope="global")
            gateway = _IntentGateway(request=False)
            runtime = PiSceneTransactionRuntime({}, project_root=root, data_root=root / ".studio",
                                                gateway=gateway, prompt_snapshot_provider=workbench.snapshot)
            first = runtime.create_scene("tx-pinned-a", _brief())
            self.assertIn("以旧杯子的使用痕迹观察关系。", gateway.calls[-1][1])
            workbench.save("scene.creator.identity", "以窗外的声音观察关系。", scope="global")
            runtime.review_scene("tx-pinned-a", _brief(), first,
                                 VerificationReport("scene_0001", len(first.prose)))
            snapshot = json.loads((root / ".studio/scene-transactions/tx-pinned-a/prompt_assembly_v1.json").read_text(encoding="utf-8"))
            self.assertEqual(snapshot["texts"]["scene.creator.identity"], "以旧杯子的使用痕迹观察关系。")
            runtime.create_scene("tx-pinned-b", _brief())
            self.assertIn("以窗外的声音观察关系。", gateway.calls[-1][1])
            self.assertNotIn("你是本场小说主创。你要先判断", gateway.calls[-1][1])

    def test_interrupted_material_batch_resumes_without_repeating_completed_calls(self):
        class Gateway(_IntentGateway):
            def __init__(self):
                super().__init__(request=True)
                self.fail_scene_once = True

            def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
                if role == "worker" and not any(item[0] == "worker" for item in self.calls):
                    self.calls.append((role, prompt))
                    answer = {"creative_intent": _INTENT, "material_requests": [
                        {"kind": "event-narration", "target": "昨夜取信", "purpose": "留下可回看线索",
                         "scene_moment": "承认之前", "cue": "信昨夜被取走"},
                        {"kind": "scene-description", "target": "饭桌", "purpose": "让距离可见",
                         "scene_moment": "递杯之后", "cue": "两人沉默"},
                    ]}
                    return RoleConversationResult("pi-worker", "fake", "test/model", json.dumps(answer, ensure_ascii=False))
                return super().run(workspace, prompt, role=role, timeout=timeout,
                                   event_sink=event_sink, cancel_event=cancel_event)

            def run_role_turn(self, workspace, *, role, initialization, history, prompt, timeout, event_sink=None):
                if role == "scene-describer" and self.fail_scene_once:
                    self.fail_scene_once = False
                    self.role_turns.append((role, len(history)))
                    raise RuntimeError("interrupted")
                return super().run_role_turn(workspace, role=role, initialization=initialization,
                                             history=history, prompt=prompt, timeout=timeout, event_sink=event_sink)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = Gateway()
            runtime = PiSceneTransactionRuntime({"application": {"scene_performance_agents": {"enabled": True}}},
                                                project_root=root, data_root=root / ".studio", gateway=gateway)
            _, plan = _fixture(["character/protagonist", "character/sister"])
            with patch("literary_engineering_studio.runtimes.scene_performance._generate_performance_plan", return_value=plan):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    runtime.create_scene("tx-resume", _brief())
                memory_path = root / ".studio/scene-transactions/tx-resume/scene_creator_memory.json"
                self.assertEqual(json.loads(memory_path.read_text(encoding="utf-8"))["phase"], "requesting-material")
                result = runtime.create_scene("tx-resume", _brief())
            self.assertIn("信", result.prose)
            self.assertEqual([role for role, _ in gateway.calls].count("worker"), 2)
            self.assertEqual([role for role, _ in gateway.role_turns].count("event-narrator"), 1)
            self.assertEqual([role for role, _ in gateway.role_turns].count("scene-describer"), 2)
            memory = json.loads(memory_path.read_text(encoding="utf-8"))
            self.assertIsNone(memory["pending_request"])
            self.assertEqual(memory["candidate_ids"], ["d1:1", "d2:1"])

    def test_direct_short_scene_keeps_intent_without_automatic_padding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = _IntentGateway(request=False)
            runtime = PiSceneTransactionRuntime({"application": {"scene_performance_agents": {"enabled": True}}},
                                                project_root=root, data_root=root / ".studio", gateway=gateway)
            with patch("literary_engineering_studio.runtimes.scene_performance._generate_performance_plan") as plan:
                result = runtime.create_scene("tx-direct", _brief())
            plan.assert_not_called()
            self.assertLess(len(result.prose), _brief().length.soft_min)
            memory = json.loads((root / ".studio/scene-transactions/tx-direct/scene_creator_memory.json").read_text(encoding="utf-8"))
            self.assertEqual(memory["intent"]["reader_experience"], _INTENT["reader_experience"])
            self.assertIn("解释过度", memory["material_skip_reason"])
            self.assertEqual([role for role, _ in gateway.calls], ["worker"])

    def test_requested_describer_candidate_reaches_creator_and_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = _IntentGateway(request=True)
            runtime = PiSceneTransactionRuntime({"application": {"scene_performance_agents": {"enabled": True}}},
                                                project_root=root, data_root=root / ".studio", gateway=gateway)
            _, plan = _fixture(["character/protagonist", "character/sister"])
            with patch("literary_engineering_studio.runtimes.scene_performance._generate_performance_plan", return_value=plan) as planner:
                result = runtime.create_scene("tx-object", _brief())
            planner.assert_not_called()
            self.assertEqual(gateway.role_turns, [("event-narrator", 0)])
            self.assertNotIn("昨夜信被取走时，抽屉尚未上锁", gateway.calls[1][1])
            self.assertIn("d1:1", gateway.calls[1][1])
            library = root / ".studio/scene-transactions/tx-object/materials"
            index = json.loads((library / "index.json").read_text(encoding="utf-8"))
            item = next(row for row in index["entries"] if row["candidate_id"] == "d1:1")
            self.assertIn("昨夜信被取走时", (library / item["file"]).read_text(encoding="utf-8"))
            memory = json.loads((root / ".studio/scene-transactions/tx-object/scene_creator_memory.json").read_text(encoding="utf-8"))
            self.assertEqual(memory["candidate_ids"], ["d1:1"])
            self.assertEqual(memory["material_decisions"][0]["decision"], "adapt")
            runtime.review_scene("tx-object", _brief(), result, VerificationReport("scene_0001", len(result.prose)))
            self.assertIn("reader_misreads", gateway.calls[-1][1])


if __name__ == "__main__":
    unittest.main()
