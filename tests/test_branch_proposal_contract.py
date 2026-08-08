from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.scene.composition.composer import _build_beats, _load_branch_choice
from literary_engineering_studio_engine.literary.scene.composition.beats import composition_obligations
from literary_engineering_studio_engine.literary.scene.composition.execution_contract import (
    build_prose_execution_contract,
    load_prose_execution_contract,
    render_prose_execution_contract,
)
from literary_engineering_studio_engine.literary.scene.facts import SceneFacts
from literary_engineering_studio_engine.routes.scene.gates import _branch_selection_gate
from literary_engineering_studio_engine.prompting.pack import _sources
from literary_engineering_studio_engine.semantic_task_contracts import (
    semantic_artifact_relative_path,
    semantic_artifact_template,
)


class BranchProposalContractTests(unittest.TestCase):
    @staticmethod
    def _beats(prefix: str, count: int) -> list[dict[str, object]]:
        obligations = ["incoming_bridge", "goal", "turn", "cost", "reader_effect", "outgoing_hook"]
        return [
            {
                "beat_id": f"{prefix}_{index + 1}",
                "function": f"推进阶段 {index + 1}",
                "visible_action": f"角色完成第 {index + 1} 个可观察行动。",
                "causal_change": f"该行动把因果推进到状态 {index + 1}。",
                "pace": "measured" if index == 0 else "accelerating",
                "detail_level": "standard" if index == 0 else "expanded",
                "serves": obligations[index::count],
            }
            for index in range(count)
        ]

    def _write_manifest(self, root: Path, *, declare_proposals: bool) -> Path:
        directory = root / "branches" / "scene_0001"
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "formal_cli_provenance": {
                "created_by": "branch-simulate",
                "agent_tasks_requested": True,
            },
            "recommended_branch": "branch_fallback",
            "branch_count": 2,
            "branches": [
                {
                    "branch_id": "branch_fallback",
                    "title": "确定性回退",
                    "strategy": "fallback",
                    "premise": "在 Agent 提案不可用时保留可审计路线。",
                    "action_chain": ["保守推进", "留下后果"],
                    "writeback_candidates": {"next_scene_inputs": ["继续核验"]},
                }
            ],
        }
        if declare_proposals:
            payload["agent_proposals"] = semantic_artifact_relative_path("branch-agent-task", "scene_0001")
        path = directory / "branch_manifest.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _write_proposals(self, root: Path) -> Path:
        relative = semantic_artifact_relative_path("branch-agent-task", "scene_0001")
        path = root / relative
        payload = semantic_artifact_template(
            "branch-agent-task",
            "scene_0001",
            source="branches/scene_0001/branch_manifest.json",
        )
        payload.update(
            {
                "status": "complete",
                "evidence_paths": ["branches/scene_0001/roleplay_result.json"],
                "findings": ["分支在行动、代价和后续写回上均不同。"],
                "proposals": [
                    {
                        "branch_id": "agent_branch_warn",
                        "title": "有限警告",
                        "strategy": "以信息暴露换取同伴生存窗口",
                        "causal_premise": "林发出有限警告，因此调查者确认日志已经泄露。",
                        "action_chain": ["发送警告", "隐去来源", "调查者追索泄露者"],
                        "cost": "林失去秘密调查空间。",
                        "reader_effect": "即时缓解转为身份暴露压力。",
                        "state_writeback": {
                            "new_facts": ["调查者确认日志已经泄露"],
                            "next_scene_inputs": ["林被列为调查对象"],
                        },
                        "beat_plan": self._beats("warn", 3),
                    },
                    {
                        "branch_id": "agent_branch_verify",
                        "title": "延迟核验",
                        "strategy": "以关系信任换取事实确定性",
                        "causal_premise": "林延迟警告以核验信号，因此盟友独自承担风险。",
                        "action_chain": ["核验信号", "错过联络", "盟友独自行动"],
                        "cost": "盟友对林的信任下降。",
                        "reader_effect": "事实更清晰，但关系更危险。",
                        "state_writeback": {
                            "relationship_changes": ["盟友对林的信任下降"],
                            "next_scene_inputs": ["盟友绕开林行动"],
                        },
                        "beat_plan": self._beats("verify", 4),
                    },
                ],
            }
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_formal_gate_and_composition_accept_valid_agent_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._write_manifest(root, declare_proposals=True)
            proposal_path = self._write_proposals(root)
            selection = manifest.parent / "branch_selection.md"
            selection.write_text(
                "decision: selected\nselected_branch: agent_branch_warn\n",
                encoding="utf-8",
            )

            errors, notes = _branch_selection_gate(root, "scene_0001")
            self.assertEqual(errors, [])
            self.assertIn("agent_branch_warn", notes[0])
            branch = _load_branch_choice(root, "scene_0001", None, None, False, False)
            self.assertEqual(branch["branch_id"], "agent_branch_warn")
            self.assertEqual(branch["premise"], "林发出有限警告，因此调查者确认日志已经泄露。")
            self.assertEqual(branch["branch_origin"], "agent-proposal")
            self.assertEqual(branch["proposal_path"], proposal_path)
            self.assertEqual(len(branch["beat_plan"]), 3)

    def test_historical_manifest_without_proposal_contract_keeps_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._write_manifest(root, declare_proposals=False)
            (manifest.parent / "branch_selection.md").write_text(
                "decision: selected\nselected_branch: branch_fallback\n",
                encoding="utf-8",
            )

            errors, _notes = _branch_selection_gate(root, "scene_0001")
            self.assertEqual(errors, [])
            branch = _load_branch_choice(root, "scene_0001", None, None, False, False)
            self.assertEqual(branch["branch_id"], "branch_fallback")
            self.assertEqual(branch["branch_origin"], "deterministic-fallback")
            self.assertEqual(branch["fallback_reason"], "no-validated-agent-proposal")

    def test_valid_agent_proposals_require_reason_before_fixed_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._write_manifest(root, declare_proposals=True)
            self._write_proposals(root)
            selection = manifest.parent / "branch_selection.md"
            selection.write_text(
                "decision: selected\nselected_branch: branch_fallback\n",
                encoding="utf-8",
            )

            errors, _notes = _branch_selection_gate(root, "scene_0001")
            self.assertIn("requires a concrete fallback_reason", errors[0])
            with self.assertRaisesRegex(RuntimeError, "fallback_reason"):
                _load_branch_choice(root, "scene_0001", None, None, False, False)

            reason = "两个 Agent 提案都会提前泄露核心身份，本场只能保守维持观察窗口。"
            selection.write_text(
                f"decision: selected\nselected_branch: branch_fallback\nfallback_reason: {reason}\n",
                encoding="utf-8",
            )
            errors, notes = _branch_selection_gate(root, "scene_0001")
            self.assertEqual(errors, [])
            self.assertIn(reason, notes[0])
            branch = _load_branch_choice(root, "scene_0001", None, None, False, False)
            self.assertEqual(branch["fallback_reason"], reason)
            self.assertTrue(branch["validated_agent_proposals_available"])

    def test_agent_plan_controls_variable_beats_while_fallback_keeps_five(self) -> None:
        facts = SceneFacts(
            scene_id="scene_0001",
            chapter_id="chapter_0001",
            location="观测站",
            participants=[],
            canon_refs=[],
            active_foreshadowing=[],
            scene_goal="判断是否发出警告",
            external_conflict="调查者正在监听频道",
            internal_conflict="林不愿再次失去盟友信任",
            style_constraints=[],
            next_hooks=["调查者开始追索警告来源"],
        )
        agent_branch = {
            "premise": "林发出有限警告，因此暴露掌握日志的事实。",
            "cost": "林失去秘密调查空间。",
            "reader_effect": "即时缓解转为身份暴露压力。",
            "beat_plan": self._beats("warn", 3),
        }

        agent_beats = _build_beats(facts, [], agent_branch)
        fallback_beats = _build_beats(facts, [], {"action_chain": []})

        self.assertEqual(len(agent_beats), 3)
        self.assertEqual(agent_beats[0]["source"], "agent-branch-plan")
        self.assertIn("incoming_bridge", agent_beats[0]["serves"])
        self.assertEqual(len(fallback_beats), 5)
        self.assertTrue(all(item["source"] == "deterministic-fallback" for item in fallback_beats))

        obligations = composition_obligations(
            facts,
            agent_branch,
            {
                "narrative_rhythm": {"scene_turn": "警告变成暴露证据", "reader_effect": "安全感转为追索压力"},
                "scene_bridge": {"incoming_pressure": "盟友正在等待答复", "outgoing_hook": "调查者锁定林"},
            },
            {"target_chinese_chars": 1800, "count_unit": "chinese_content_chars"},
        )
        self.assertEqual(obligations["word_target_hanzi"], 1800)
        self.assertEqual(obligations["turn"], "警告变成暴露证据")
        self.assertEqual(obligations["cost"], "林失去秘密调查空间。")

        composition = {
            "scene_id": facts.scene_id,
            "selected_branch": "agent_branch_warn",
            "selection_source": "selection",
            "formal_cli_provenance": {"input_contract_digest": "abc123"},
            "branch": {
                **agent_branch,
                "branch_id": "agent_branch_warn",
                "branch_origin": "agent-proposal",
                "title": "有限警告",
                "strategy": "以信息暴露换取同伴生存窗口",
                "causal_premise": agent_branch["premise"],
                "action_chain": ["发送警告", "调查者追索来源"],
            },
            "beats": agent_beats,
            "composition_obligations": obligations,
            "writeback_candidates": {"next_scene_inputs": ["调查者锁定林"]},
        }
        contract = build_prose_execution_contract(composition)

        self.assertEqual(contract["status"], "pass")
        self.assertEqual(contract["errors"], [])
        self.assertEqual(contract["selection"]["branch_origin"], "agent-proposal")
        self.assertEqual(contract["obligations"]["reader_effect"], "安全感转为追索压力")
        self.assertIn("incoming_bridge", contract["beats"][0]["serves"])
        rendered = render_prose_execution_contract(contract)
        self.assertIn("正文执行契约", rendered)
        self.assertIn('"word_target_hanzi": 1800', rendered)

    def test_prose_execution_contract_rejects_missing_causal_obligation(self) -> None:
        contract = build_prose_execution_contract(
            {
                "scene_id": "scene_0001",
                "selected_branch": "agent_branch_warn",
                "selection_source": "selection",
                "formal_cli_provenance": {"input_contract_digest": "abc123"},
                "branch": {
                    "branch_origin": "agent-proposal",
                    "causal_premise": "警告暴露了信息来源。",
                    "action_chain": ["发送警告", "调查者追索来源"],
                },
                "beats": self._beats("warn", 3),
                "composition_obligations": {
                    "goal": "保护盟友",
                    "turn": "",
                    "incoming_bridge": "盟友等待答复",
                    "outgoing_hook": "调查者锁定林",
                    "cost": "林失去秘密调查空间",
                    "reader_effect": "安全感转为追索压力",
                    "word_target_hanzi": 1800,
                },
                "writeback_candidates": {},
            }
        )

        self.assertEqual(contract["status"], "incomplete")
        self.assertIn("missing obligations.turn", contract["errors"])

    def test_loading_legacy_composition_requires_recompose(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scene_0001_composition.json"
            path.write_text(json.dumps({"scene_id": "scene_0001"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "rerun compose-scene"):
                load_prose_execution_contract(path)

    def test_prompt_sources_include_human_and_machine_composition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            context = root / "memory" / "context_packets" / "scene_0001.md"
            trace = context.with_suffix(".trace.json")
            composition = root / "drafts" / "compositions" / "scene_0001_composition.md"
            composition_json = composition.with_suffix(".json")
            for path in (scene, context, trace, composition, composition_json):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")

            sources = _sources(
                root,
                scene,
                context,
                trace,
                composition,
                None,
                None,
                None,
                None,
            )

            paths = {item["path"] for item in sources}
            self.assertIn("drafts/compositions/scene_0001_composition.md", paths)
            self.assertIn("drafts/compositions/scene_0001_composition.json", paths)


if __name__ == "__main__":
    unittest.main()
