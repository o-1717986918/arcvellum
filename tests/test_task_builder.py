from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.tasking.builder import (
    TaskBuilder,
    WordCountContract,
    file_sha256,
)


class TaskBuilderTests(unittest.TestCase):
    def test_builds_normalized_shared_envelope_and_blueprint_contracts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "drafts" / "candidate.md"
            target.parent.mkdir(parents=True)
            target.write_text("candidate", encoding="utf-8")
            blueprint = {
                "task_type": "platform-agent-review",
                "prompt_asset_id": "route.example.review.v1",
                "command": "",
                "required_reading": ["project.yaml"],
                "source_paths": ["drafts\\candidate.md", "drafts/candidate.md"],
                "agent_source_paths": ["drafts\\candidate.md"],
                "expected_outputs": ["reviews\\result.json", "workflow/task.agent_tasks.md"],
                "core_managed_outputs": ["workflow\\task.agent_tasks.md", "ignored.json"],
                "repair_targets": ["drafts\\candidate.md"],
                "hard_constraints": ["review exact source"],
                "style_constraints": [],
                "validation_gates": ["review exists"],
                "next_allowed_states": ["complete"],
            }

            payload = TaskBuilder(
                root=root,
                route="review-and-audit",
                target_id="candidate",
                scene_id="scene_0001",
                current_state="review",
                blueprint=blueprint,
                required_reading=["fallback.md"],
                forbidden_shortcuts=["do not bypass"],
                route_fields={"patch_id": "candidate"},
                word_count=WordCountContract(1200, 1000, 1400),
            ).build()

            self.assertEqual(payload["source_paths"], ["drafts/candidate.md"])
            self.assertEqual(payload["agent_source_paths"], ["drafts/candidate.md"])
            self.assertEqual(payload["core_managed_outputs"], ["workflow/task.agent_tasks.md"])
            self.assertEqual(payload["repair_targets"], ["drafts/candidate.md"])
            self.assertEqual(
                payload["repair_target_sha256_before_revision"],
                {"drafts/candidate.md": file_sha256(target)},
            )
            self.assertEqual(payload["required_reading"], ["project.yaml"])
            self.assertEqual(payload["word_count_target"], 1200)
            self.assertIn("task-submit", payload["submission_command"])
            self.assertIn(str(payload["task_id"]), payload["completion_command"])

    def test_can_keep_route_target_distinct_from_task_identity(self):
        blueprint = {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.example.prepare.v1",
            "command": "python -m literary_engineering_studio_engine example",
            "source_paths": [],
            "expected_outputs": [],
            "hard_constraints": [],
            "style_constraints": [],
            "validation_gates": [],
            "next_allowed_states": [],
        }
        payload = TaskBuilder(
            route="source-ingest",
            target_id="work--chunk-1",
            scene_id="work",
            current_state="extract",
            blueprint=blueprint,
            required_reading=[],
            forbidden_shortcuts=[],
            route_fields={"target_id": "work", "chunk_id": "chunk-1"},
        ).build()

        self.assertIn("work-chunk-1", payload["task_id"])
        self.assertEqual(payload["target_id"], "work")
        self.assertEqual(payload["chunk_id"], "chunk-1")


if __name__ == "__main__":
    unittest.main()
