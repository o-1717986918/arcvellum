from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.branch_lab import build_branch_simulation
from literary_engineering_studio_engine.roleplay_lab import build_roleplay_simulation
from literary_engineering_studio_engine.semantic_task_contracts import (
    read_semantic_artifact,
    semantic_artifact_errors,
    semantic_artifact_relative_path,
    semantic_artifact_template,
)
from literary_engineering_studio_engine import task_registry


class SemanticTaskContractTests(unittest.TestCase):
    def _project(self, root: Path) -> Path:
        (root / "project.yaml").write_text("project:\n  title: Semantic Contract\n", encoding="utf-8")
        (root / "scenes").mkdir(parents=True)
        (root / "scenes" / "scene_0001.yaml").write_text(
            "scene_id: scene_0001\nchapter_id: chapter_0001\nlocation: observatory\nscene_goal: test a choice\nparticipants:\n  - lin\n",
            encoding="utf-8",
        )
        (root / "characters").mkdir()
        (root / "characters" / "lin.yaml").write_text(
            "character_id: lin\nname: Lin\nrole: lead\nbelief:\n  - evidence matters\ndesire:\n  - protect a friend\nintention:\n  - verify the signal\nfear:\n  - losing trust\nmoral_line: no false evidence\n",
            encoding="utf-8",
        )
        (root / "canon").mkdir()
        (root / "canon" / "world_rules.yaml").write_text("rules: []\n", encoding="utf-8")
        (root / "canon" / "forbidden_changes.yaml").write_text("forbidden: []\n", encoding="utf-8")
        (root / "plot").mkdir()
        (root / "plot" / "outline.md").write_text("# Outline\n", encoding="utf-8")
        (root / "plot" / "foreshadowing.csv").write_text("id,note\n", encoding="utf-8")
        return root

    def test_roleplay_semantic_result_is_required_and_consumed_by_branch_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary))
            result = build_roleplay_simulation(root, scene=Path("scenes/scene_0001.yaml"), agent_mode=True)
            self.assertIsNotNone(result.agent_tasks_path)
            semantic_path = root / semantic_artifact_relative_path("roleplay-agent-task", "scene_0001")
            payload = semantic_artifact_template(
                "roleplay-agent-task",
                "scene_0001",
                source="branches/scene_0001/roleplay_simulation.md",
            )
            payload.update(
                {
                    "status": "complete",
                    "evidence_paths": ["scenes/scene_0001.yaml", "characters/lin.yaml"],
                    "character_actions": [{"character_id": "lin", "chosen_action": "Lin verifies the signal before accusing anyone."}],
                    "world_consequences": ["The observatory log becomes contested evidence."],
                    "branch_pressures": ["Verification costs Lin the only chance to warn a friend."],
                    "canon_risks": ["Do not establish the signal source as fact yet."],
                    "writeback_candidates": ["Record the disputed observatory log as a candidate clue."],
                }
            )
            semantic_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            write_agent_completion_marker(result.agent_tasks_path, root=root, handled_by="test")

            branch = build_branch_simulation(root, scene=Path("scenes/scene_0001.yaml"), agent_tasks=True)
            manifest = json.loads(branch.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["roleplay_result"], semantic_path.relative_to(root).as_posix())
            self.assertEqual(manifest["roleplay_evidence"]["status"], "complete")
            self.assertIn("RP 角色行动依据", "\n".join(manifest["branches"][0]["action_chain"]))

    def test_roleplay_depth_changes_scope_without_waiving_semantic_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary))
            (root / "characters" / "outsider.yaml").write_text(
                "character_id: outsider\nname: Outsider\nrole: minor\n",
                encoding="utf-8",
            )

            light = build_roleplay_simulation(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                agent_mode=True,
                roleplay_depth="light",
                output=Path("branches/scene_0001/light_roleplay.md"),
            )
            full = build_roleplay_simulation(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                agent_mode=True,
                roleplay_depth="full",
                output=Path("branches/scene_0001/full_roleplay.md"),
            )

            self.assertEqual(light.character_count, 1)
            self.assertEqual(full.character_count, 2)
            light_text = light.output_path.read_text(encoding="utf-8")
            self.assertIn("RP 深度：`light`", light_text)
            self.assertIn("不得把 light 理解为跳过 RP", light_text)
            self.assertIn("roleplay_result.json", light.agent_tasks_path.read_text(encoding="utf-8"))

    def test_composition_semantic_evidence_binds_to_exact_source_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "drafts" / "compositions" / "scene_0001_composition.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"scene_id":"scene_0001"}', encoding="utf-8")
            relative = semantic_artifact_relative_path("composition-agent-task", "scene_0001")
            artifact = root / relative
            artifact.parent.mkdir(parents=True, exist_ok=True)
            payload = semantic_artifact_template("composition-agent-task", "scene_0001", source=source.relative_to(root).as_posix())
            payload.update(
                {
                    "status": "complete",
                    "composition_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "evidence_paths": ["drafts/compositions/scene_0001_composition.json"],
                    "verdict": "pass",
                    "findings": ["branch and rhythm contracts align"],
                    "required_changes": [],
                    "ready_for_generation": True,
                }
            )
            artifact.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(semantic_artifact_errors(root, "composition-agent-task", "scene_0001"), [])
            payload["composition_sha256"] = "stale"
            artifact.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(semantic_artifact_errors(root, "composition-agent-task", "scene_0001"))

    def test_branch_proposals_require_distinct_causality_cost_and_writeback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary))
            source = root / "branches" / "scene_0001" / "branch_manifest.json"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('{"branch_count": 2, "branches": []}\n', encoding="utf-8")
            relative = semantic_artifact_relative_path("branch-agent-task", "scene_0001")
            artifact = root / relative
            artifact.parent.mkdir(parents=True, exist_ok=True)
            payload = semantic_artifact_template(
                "branch-agent-task",
                "scene_0001",
                source="branches/scene_0001/branch_manifest.json",
            )
            proposal = {
                "branch_id": "agent_branch_verify",
                "title": "先核验再公开",
                "strategy": "让核验延迟警告并损伤信任",
                "causal_premise": "林选择核验信号，因此错过即时警告。",
                "action_chain": ["复核日志", "延迟警告", "盟友独自行动"],
                "cost": "盟友不再相信林会优先保护自己。",
                "reader_effect": "短暂安心转为关系焦虑。",
                "state_writeback": {
                    "relationship_changes": ["林与盟友的信任下降"],
                    "next_scene_inputs": ["盟友绕开林调查"],
                },
                "beat_plan": [
                    {
                        "beat_id": "verify_open",
                        "function": "接住警报",
                        "visible_action": "林先核对观测记录。",
                        "causal_change": "即时警告被推迟。",
                        "pace": "compressed",
                        "detail_level": "lean",
                        "serves": ["incoming_bridge", "goal"],
                    },
                    {
                        "beat_id": "verify_cost",
                        "function": "核验代价",
                        "visible_action": "盟友在等待中独自离开。",
                        "causal_change": "事实更清晰，关系却恶化。",
                        "pace": "slow",
                        "detail_level": "expanded",
                        "serves": ["turn", "cost", "reader_effect", "outgoing_hook"],
                    },
                ],
            }
            payload.update(
                {
                    "status": "complete",
                    "evidence_paths": [
                        "branches/scene_0001/roleplay_result.json",
                        "branches/scene_0001/branch_manifest.json",
                    ],
                    "findings": ["两个方向必须改变不同的因果链和关系代价。"],
                    "proposals": [proposal, {**proposal, "branch_id": "agent_branch_repeat", "title": "换名复核"}],
                }
            )
            artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            errors = semantic_artifact_errors(root, "branch-agent-task", "scene_0001")
            self.assertTrue(any("distinct action chains" in item for item in errors))
            self.assertTrue(any("distinct costs" in item for item in errors))
            self.assertTrue(any("distinct state writebacks" in item for item in errors))

            payload["proposals"][1].update(
                {
                    "strategy": "立即公开，但把来源保持为未证实",
                    "causal_premise": "林立即发出警告，因此暴露自己掌握了禁区日志。",
                    "action_chain": ["发送有限警告", "拒绝解释来源", "调查者锁定林"],
                    "cost": "林成为调查对象并失去秘密取证空间。",
                    "reader_effect": "行动紧迫感转为身份暴露压力。",
                    "state_writeback": {
                        "new_facts": ["调查者知道林接触过禁区日志"],
                        "next_scene_inputs": ["林必须解释信息来源"],
                    },
                    "beat_plan": [
                        {
                            "beat_id": "warn_open",
                            "function": "发送警告",
                            "visible_action": "林发出隐去来源的警告。",
                            "causal_change": "盟友获得行动窗口。",
                            "pace": "fast",
                            "detail_level": "standard",
                            "serves": ["incoming_bridge", "goal", "turn"],
                        },
                        {
                            "beat_id": "warn_exposure",
                            "function": "暴露来源",
                            "visible_action": "调查者反查警告通道。",
                            "causal_change": "林进入调查名单。",
                            "pace": "decelerating",
                            "detail_level": "expanded",
                            "serves": ["cost", "reader_effect", "outgoing_hook"],
                        },
                    ],
                }
            )
            artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertEqual(semantic_artifact_errors(root, "branch-agent-task", "scene_0001"), [])
            loaded = read_semantic_artifact(root, "branch-agent-task", "scene_0001")
            self.assertEqual(len(loaded["proposals"]), 2)

            source.write_text('{"branch_count": 3, "branches": []}\n', encoding="utf-8")
            errors = semantic_artifact_errors(root, "branch-agent-task", "scene_0001")
            self.assertTrue(any("Creative Policy Graph" in item and "exactly 3" in item for item in errors))
            source.write_text('{"branch_count": 2, "branches": []}\n', encoding="utf-8")

            payload["proposals"][1]["beat_plan"][1]["serves"] = ["cost"]
            artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            errors = semantic_artifact_errors(root, "branch-agent-task", "scene_0001")
            self.assertTrue(any("reader_effect" in item and "outgoing_hook" in item for item in errors))

    def test_task_blueprint_declares_typed_semantic_output_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary))
            task = task_registry._enrich_task_payload(
                task_registry._build_task_payload(
                    root,
                    "scene-development",
                    {"scene_id": "scene_0001", "scene": "scenes/scene_0001.yaml", "current_step": "roleplay-agent-task", "next_action": ""},
                )
            )
            semantic = task["semantic_artifact"]
            self.assertEqual(semantic["schema_name"], "roleplay_result.v1")
            semantic_contract = next(item for item in task["output_contracts"] if item["path"] == semantic["path"])
            self.assertEqual(semantic_contract["consumed_by"], "branch-manifest")
            self.assertEqual(semantic_contract["schema_name"], "roleplay_result.v1")

            branch_task = task_registry._enrich_task_payload(
                task_registry._build_task_payload(
                    root,
                    "scene-development",
                    {
                        "scene_id": "scene_0001",
                        "scene": "scenes/scene_0001.yaml",
                        "current_step": "branch-agent-task",
                        "next_action": "",
                    },
                )
            )
            branch_semantic = branch_task["semantic_artifact"]
            self.assertEqual(branch_semantic["schema_name"], "branch_proposals.v1")
            self.assertIn(branch_semantic["path"], branch_task["expected_outputs"])
            self.assertIn(branch_semantic["path"], branch_task["agent_source_paths"])


if __name__ == "__main__":
    unittest.main()
