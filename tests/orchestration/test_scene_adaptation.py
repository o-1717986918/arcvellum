from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.orchestration import (
    FreedomBudget,
    NormalizationContext,
    PlanLintContext,
    bind_scene_task,
    creative_plan_digest,
    evaluate_scene_plan_patch,
    parse_scene_plan_patch,
)

from tests.orchestration.fixtures import freedom_budget, scene_plan_candidate
from tests.orchestration.plan_persistence_support import (
    FINGERPRINT,
    shadow_pipeline,
    simulation_context_for_graph,
)


class SceneAdaptiveOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.candidate, self.plan, self.graph, _, _ = shadow_pipeline()
        self.budget = FreedomBudget(**freedom_budget())
        self.normalization = NormalizationContext(
            base_project_fingerprint=FINGERPRINT,
            approved_budget=self.budget,
            created_at="2026-07-27T00:00:00+00:00",
        )
        self.lint = PlanLintContext(
            current_project_fingerprint=FINGERPRINT,
            known_scope_refs=frozenset({"chapter_01", "scene_0001"}),
            allowed_capability_ids=frozenset({"project.query"}),
            authorized_budget=self.budget,
        )

    def test_strategy_is_projected_into_compiled_nodes(self):
        parameters = {
            node.node_id: {item.name: item.value for item in node.parameters}
            for node in self.graph.nodes
        }

        self.assertEqual(parameters["roleplay"]["roleplay_depth"], "targeted")
        self.assertEqual(parameters["branches"]["branch_count"], 3)
        self.assertEqual(parameters["prose"]["narrative_distance"], "close_to_medium")
        self.assertEqual(parameters["prose"]["target_hanzi"], 1800)

    def test_formal_tasks_receive_machine_bound_scene_policy(self):
        roleplay = bind_scene_task(
            _task("roleplay-simulation", "deterministic-cli", "simulate-scene <project>"),
            plan=self.plan,
            graph=self.graph,
            current_project_fingerprint=FINGERPRINT,
        )
        branch = bind_scene_task(
            _task("branch-manifest", "deterministic-cli", "branch-simulate <project>"),
            plan=self.plan,
            graph=self.graph,
            current_project_fingerprint=FINGERPRINT,
        )
        promotion = bind_scene_task(
            _task("promotion-manifest", "deterministic-cli", "promote-candidate <project>"),
            plan=self.plan,
            graph=self.graph,
            current_project_fingerprint=FINGERPRINT,
        )

        self.assertEqual(roleplay.status, "bound")
        self.assertEqual(roleplay.node_id, "roleplay")
        self.assertIn("--roleplay-depth targeted", roleplay.task.command)
        self.assertEqual(
            roleplay.task.payload["creative_plan_id"],
            self.plan.plan_id,
        )
        self.assertIn("--branch-count 3", branch.task.command)
        self.assertEqual(
            branch.task.payload["creative_scene_policy"]["branch_count"],
            3,
        )
        self.assertEqual(promotion.status, "formal_lifecycle_passthrough")
        self.assertNotIn("creative_plan_node_id", promotion.task.payload)

    def test_binding_rejects_stale_and_out_of_scope_tasks(self):
        task = _task("roleplay-agent-task", "platform-agent-judgment", "")
        with self.assertRaisesRegex(RuntimeError, "stale"):
            bind_scene_task(
                task,
                plan=self.plan,
                graph=self.graph,
                current_project_fingerprint="new-project-state",
            )
        foreign = replace(
            task,
            payload={**task.payload, "scene_id": "scene_9999"},
        )
        with self.assertRaisesRegex(ValueError, "outside"):
            bind_scene_task(
                foreign,
                plan=self.plan,
                graph=self.graph,
                current_project_fingerprint=FINGERPRINT,
            )

    def test_scene_patch_creates_a_new_valid_revision_without_mutating_history(self):
        original = scene_plan_candidate()
        patch = parse_scene_plan_patch(
            {
                "schema": "arcvellum/creative-execution-plan-patch/v1",
                "plan_id": self.plan.plan_id,
                "base_revision": self.plan.revision,
                "base_plan_digest": creative_plan_digest(self.plan),
                "scope": {
                    "kind": "scene",
                    "key": "scene_0001",
                    "scene_ids": ["scene_0001"],
                },
                "trigger": "review_failed",
                "reason": "The first review exposed weak causal pressure.",
                "operations": [
                    {
                        "op": "replace_strategy",
                        "path": "/strategy/branch_count",
                        "value": 4,
                    },
                    {
                        "op": "replace_strategy",
                        "path": "/strategy/scene_inventory/scene_0001/roleplay_depth",
                        "value": "full",
                    },
                    {
                        "op": "replace_strategy",
                        "path": "/strategy/fallback_level",
                        "value": "return_to_branch",
                    },
                ],
                "affected_outputs": ["branches/scene_0001/branch_manifest.json"],
            }
        )

        result = evaluate_scene_plan_patch(
            original,
            base_plan=self.plan,
            patch=patch,
            normalization_context=self.normalization,
            lint_context=self.lint,
            simulation_context_factory=simulation_context_for_graph,
        )

        self.assertTrue(result.passed, result.evaluation.lint_result.issues)
        self.assertEqual(result.evaluation.plan.revision, 2)
        self.assertEqual(result.evaluation.plan.plan_id, self.plan.plan_id)
        self.assertEqual(result.evaluation.plan.strategy.branch_count, 4)
        self.assertEqual(
            result.evaluation.plan.strategy.fallback_level.value,
            "return_to_branch",
        )
        roleplay = next(
            node
            for node in result.evaluation.graph.nodes
            if node.node_id == "roleplay"
        )
        self.assertEqual(
            {item.name: item.value for item in roleplay.parameters}["roleplay_depth"],
            "full",
        )
        self.assertEqual(original["strategy"]["branch_count"], 3)
        self.assertNotEqual(result.base_plan_digest, result.new_plan_digest)
        self.assertEqual(len(result.diffs), 3)

    def test_scene_patch_rejects_stale_unsafe_and_unbound_dynamic_work(self):
        base = {
            "schema": "arcvellum/creative-execution-plan-patch/v1",
            "plan_id": self.plan.plan_id,
            "base_revision": self.plan.revision,
            "base_plan_digest": creative_plan_digest(self.plan),
            "scope": {
                "kind": "scene",
                "key": "scene_0001",
                "scene_ids": ["scene_0001"],
            },
            "trigger": "review_failed",
            "reason": "Replan within the scene boundary.",
            "operations": [
                {
                    "op": "replace_strategy",
                    "path": "/strategy/branch_count",
                    "value": 4,
                }
            ],
            "affected_outputs": [],
        }
        stale = parse_scene_plan_patch({**base, "base_revision": 99})
        with self.assertRaisesRegex(RuntimeError, "stale"):
            evaluate_scene_plan_patch(
                self.candidate,
                base_plan=self.plan,
                patch=stale,
                normalization_context=self.normalization,
                lint_context=self.lint,
                simulation_context_factory=simulation_context_for_graph,
            )
        with self.assertRaisesRegex(ValueError, "unsafe"):
            parse_scene_plan_patch(
                {**base, "affected_outputs": ["../canon/world_rules.yaml"]}
            )
        add_node = dict(base)
        add_node["operations"] = [
            {
                "op": "add_node",
                "node": self.candidate["task_nodes"][1],
            }
        ]
        parsed = parse_scene_plan_patch(add_node)
        with self.assertRaisesRegex(ValueError, "reserved until"):
            evaluate_scene_plan_patch(
                self.candidate,
                base_plan=self.plan,
                patch=parsed,
                normalization_context=self.normalization,
                lint_context=self.lint,
                simulation_context_factory=simulation_context_for_graph,
            )


def _task(current_state: str, task_type: str, command: str) -> TaskPackage:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        return TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": f"scene-development--scene_0001--{current_state}",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": current_state,
                "task_type": task_type,
                "command": command,
                "source_paths": ["scenes/scene_0001.yaml"],
                "required_reading": [],
                "expected_outputs": [],
                "hard_constraints": [],
            },
        )


if __name__ == "__main__":
    unittest.main()
