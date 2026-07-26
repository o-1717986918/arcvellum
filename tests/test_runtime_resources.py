from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.runtime.resources import (
    ResourceClaim,
    claims_conflict,
    derive_resource_claim,
    paths_overlap,
)
from literary_engineering_studio_engine.task_registry import _enrich_task_payload


class RuntimeResourceTests(unittest.TestCase):
    def _task(self, root: Path, *, task_id: str, source: str, output: str):
        (root / "project.yaml").write_text("title: Resource demo\n", encoding="utf-8")
        source_path = root / source
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("source\n", encoding="utf-8")
        task_dir = root / "workflow" / "tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        markdown = task_dir / f"{task_id}.agent_tasks.md"
        markdown.write_text("# task\n", encoding="utf-8")
        payload = {
            "schema": "literary-engineering-workbench/agent-task/v1",
            "task_id": task_id,
            "status": "opened",
            "route": "scene-development",
            "current_state": "prose-generation",
            "task_type": "main-platform-agent-prose",
            "prompt_asset_id": "route.scene-development.prose.generate.v1",
            "required_reading": [],
            "source_paths": [source],
            "agent_source_paths": [source],
            "expected_outputs": [output],
            "submission_command": "lew task-submit",
            "completion_command": "lew task-complete",
            "validation_gates": [],
            "forbidden_shortcuts": [],
            "task_markdown": f"workflow/tasks/{task_id}.agent_tasks.md",
        }
        task_json = task_dir / f"{task_id}.task.json"
        task_json.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
        return load_task_package(root, task_json)

    def test_path_overlap_treats_declared_directories_as_prefixes(self):
        self.assertTrue(paths_overlap("canon", "canon/world_rules.yaml"))
        self.assertTrue(paths_overlap("drafts/scenes/scene_0001.md", "drafts/scenes/scene_0001.md"))
        self.assertFalse(paths_overlap("canon", "characters/protagonist.yaml"))
        with self.assertRaises(ValueError):
            paths_overlap("../outside", "canon")

    def test_read_read_is_compatible_but_write_read_and_write_write_conflict(self):
        base = {
            "project_id": "project-demo",
            "runtime_slot": "worker",
            "model_slot": "creative",
            "network": "none",
            "exclusive_barriers": (),
        }
        first = ResourceClaim("first", reads=("canon",), writes=(), **base)
        second = ResourceClaim("second", reads=("canon/world_rules.yaml",), writes=(), **base)
        self.assertFalse(claims_conflict(first, second).conflicts)

        writer = ResourceClaim("writer", reads=(), writes=("canon/world_rules.yaml",), **base)
        result = claims_conflict(writer, second)
        self.assertTrue(result.conflicts)
        self.assertTrue(any(reason.startswith("write-read:") for reason in result.reasons))

        other_writer = ResourceClaim("writer-2", reads=(), writes=("canon",), **base)
        self.assertTrue(claims_conflict(writer, other_writer).conflicts)

    def test_different_projects_do_not_conflict_and_barriers_do(self):
        first = ResourceClaim(
            "first",
            "project-a",
            (),
            ("workflow/approvals/index.jsonl",),
            "worker",
            "review",
            "none",
            ("approval-ledger-write",),
        )
        other_project = ResourceClaim(
            "other",
            "project-b",
            (),
            ("workflow/approvals/index.jsonl",),
            "worker",
            "review",
            "none",
            ("approval-ledger-write",),
        )
        self.assertFalse(claims_conflict(first, other_project).conflicts)
        same_project = ResourceClaim(
            "same",
            "project-a",
            (),
            ("decisions/other.json",),
            "worker",
            "review",
            "none",
            ("approval-ledger-write",),
        )
        self.assertIn("exclusive-barrier:approval-ledger-write", claims_conflict(first, same_project).reasons)

    def test_claim_is_derived_from_formal_task_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = self._task(
                root,
                task_id="scene-prose",
                source="memory/context_packets/scene_0001.md",
                output="drafts/scenes/scene_0001.md",
            )
            claim = derive_resource_claim(task, runtime_slot="opencode", model_slot="creative-primary")
            self.assertEqual(claim.task_node_id, "scene-prose")
            self.assertEqual(claim.reads, ("memory/context_packets/scene_0001.md",))
            self.assertEqual(claim.writes, ("drafts/scenes/scene_0001.md",))
            self.assertEqual(claim.network, "none")
            self.assertIn("formal-prose-write", claim.exclusive_barriers)
            self.assertTrue(claim.project_id.startswith("project-"))


if __name__ == "__main__":
    unittest.main()
