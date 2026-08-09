from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.runtime.context_cache_experiment import (
    CONTEXT_CACHE_EXPERIMENT_SCHEMA,
    measure_prepared_context_cache_reuse,
)


class ContextCacheExperimentTests(unittest.TestCase):
    def test_repeated_preparations_share_exact_content_without_model_claims(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = _cacheable_task(Path(temporary))
            report = measure_prepared_context_cache_reuse(
                task,
                runs_root=Path(runs),
                worker_config={"context_budget": {"mode": "shadow"}},
                repetitions=3,
            )

        self.assertEqual(report["schema"], CONTEXT_CACHE_EXPERIMENT_SCHEMA)
        self.assertEqual(
            [item["cache_status"] for item in report["samples"]],
            ["miss", "hit", "hit"],
        )
        self.assertTrue(report["criteria"]["prepared_content_is_identical"])
        self.assertTrue(report["criteria"]["context_budget_is_identical"])
        self.assertFalse(report["claims"]["model_invoked"])
        self.assertFalse(report["claims"]["model_token_reduction"])


def _cacheable_task(root: Path):
    (root / "project.yaml").write_text("title: Cache experiment\n", encoding="utf-8")
    scene = root / "scenes" / "scene_0001.yaml"
    scene.parent.mkdir(parents=True)
    scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
    trace = root / "memory" / "context_packets" / "scene_0001.trace.json"
    trace.parent.mkdir(parents=True)
    trace.write_text(
        json.dumps(
            {
                "scene_id": "scene_0001",
                "project_revision": "project-1",
                "canon_revision": "canon-1",
                "state_revision": "state-1",
                "style_mount_revision": "style-1",
                "word_budget_revision": "budget-1",
                "rhythm_plan_revision": "rhythm-1",
                "previous_promoted_scene_sha": "previous-1",
            }
        ),
        encoding="utf-8",
    )
    task_dir = root / "workflow" / "tasks"
    task_dir.mkdir(parents=True)
    task_md = task_dir / "cache.agent_tasks.md"
    task_md.write_text("# Cache task\n", encoding="utf-8")
    payload = {
        "schema": "literary-engineering-workbench/agent-task/v1",
        "task_id": "cache-task",
        "status": "opened",
        "route": "scene-development",
        "current_state": "candidate-review",
        "task_type": "platform-agent-review",
        "prompt_asset_id": "route.scene-development.agent-review.v1",
        "scene_id": "scene_0001",
        "context_trace": "memory/context_packets/scene_0001.trace.json",
        "required_reading": [],
        "source_paths": [
            "scenes/scene_0001.yaml",
            "memory/context_packets/scene_0001.trace.json",
        ],
        "context_excluded_paths": [
            "memory/context_packets/scene_0001.trace.json",
        ],
        "expected_outputs": ["reviews/agent/scene_0001_scene_review.json"],
        "submission_command": "lew task-submit",
        "completion_command": "lew task-complete",
        "validation_gates": [],
        "forbidden_shortcuts": [],
        "task_markdown": "workflow/tasks/cache.agent_tasks.md",
    }
    task_json = task_dir / "cache.task.json"
    task_json.write_text(json.dumps(payload), encoding="utf-8")
    return load_task_package(root, task_json)


if __name__ == "__main__":
    unittest.main()
