from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.scene.composition.composer import _load_branch_choice
from literary_engineering_studio_engine.routes.scene.gates import _branch_selection_gate
from literary_engineering_studio_engine.semantic_task_contracts import (
    semantic_artifact_relative_path,
    semantic_artifact_template,
)


class BranchProposalContractTests(unittest.TestCase):
    def _write_manifest(self, root: Path, *, declare_proposals: bool) -> Path:
        directory = root / "branches" / "scene_0001"
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "formal_cli_provenance": {
                "created_by": "branch-simulate",
                "agent_tasks_requested": True,
            },
            "recommended_branch": "branch_fallback",
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


if __name__ == "__main__":
    unittest.main()
