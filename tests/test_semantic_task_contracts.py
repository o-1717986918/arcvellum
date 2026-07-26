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


if __name__ == "__main__":
    unittest.main()
