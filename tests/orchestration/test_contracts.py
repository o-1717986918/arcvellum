from __future__ import annotations

import json
from pathlib import Path
import unittest

from ruamel.yaml import YAML

from literary_engineering_studio.automation.controller import ROUTE_ORDER
from literary_engineering_studio.orchestration import (
    CANDIDATE_SCHEMA,
    COMPILED_GRAPH_SCHEMA,
    PLAN_SCHEMA,
    DefaultPlanFactory,
    constitution_v1,
    parse_plan_candidate,
    to_primitive,
)
from literary_engineering_studio_engine.orchestration import (
    check_default_plan_compatibility,
)
from literary_engineering_studio_engine.tasking.registry import SUPPORTED_ROUTES


ROOT = Path(__file__).resolve().parents[2]


class OrchestrationContractTests(unittest.TestCase):
    def test_candidate_strips_machine_fields_and_preserves_explicit_zero_budget(self):
        payload = _candidate_payload()
        payload["plan_id"] = "model-forged"
        payload["revision"] = 99
        payload["freedom_request"]["max_added_tasks"] = 0

        parsed = parse_plan_candidate(payload)

        self.assertEqual(parsed.candidate.schema, CANDIDATE_SCHEMA)
        self.assertEqual(parsed.candidate.freedom_request.max_added_tasks, 0)
        self.assertIn("machine-owned field ignored: plan_id", parsed.warnings)
        self.assertIn("machine-owned field ignored: revision", parsed.warnings)
        self.assertNotIn("plan_id", to_primitive(parsed.candidate))

    def test_candidate_rejects_arbitrary_command_and_unknown_node_kind(self):
        with_command = _candidate_payload()
        with_command["task_nodes"][0]["command"] = "python arbitrary.py"
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            parse_plan_candidate(with_command)

        unknown_kind = _candidate_payload()
        unknown_kind["task_nodes"][0]["kind"] = "skip_review"
        with self.assertRaises(ValueError):
            parse_plan_candidate(unknown_kind)

        hidden_command = _candidate_payload()
        hidden_command["task_nodes"][0]["parameters"] = {"command": "python arbitrary.py"}
        with self.assertRaisesRegex(ValueError, "commands or arbitrary paths"):
            parse_plan_candidate(hidden_command)

    def test_default_plan_is_deterministic_and_fixed_route_equivalent(self):
        factory = DefaultPlanFactory()
        plan = factory.create(
            base_project_fingerprint="project-revision-1",
            created_at="2026-07-26T00:00:00+00:00",
        )
        repeated = factory.create(
            base_project_fingerprint="project-revision-1",
            created_at="2026-07-26T00:00:00+00:00",
        )

        self.assertEqual(plan, repeated)
        self.assertEqual(plan.schema, PLAN_SCHEMA)
        self.assertEqual(plan.route_sequence, ROUTE_ORDER)
        self.assertEqual(plan.task_nodes, ())
        self.assertEqual(plan.freedom_budget.max_added_tasks, 0)
        self.assertEqual(plan.strategy.branch_count, 1)
        compatibility = check_default_plan_compatibility(
            route_macro_id=plan.route_macro_id,
            route_sequence=plan.route_sequence,
            supported_routes=SUPPORTED_ROUTES,
        )
        self.assertTrue(compatibility.compatible, compatibility.issues)

    def test_default_plan_compatibility_rejects_reordering(self):
        plan = DefaultPlanFactory().create(
            base_project_fingerprint="project-revision-1",
            created_at="2026-07-26T00:00:00+00:00",
        )
        compatibility = check_default_plan_compatibility(
            route_macro_id=plan.route_macro_id,
            route_sequence=tuple(reversed(plan.route_sequence)),
            supported_routes=SUPPORTED_ROUTES,
        )

        self.assertFalse(compatibility.compatible)
        self.assertTrue(any("route sequence" in issue for issue in compatibility.issues))

    def test_protocol_files_match_runtime_schema_and_constitution(self):
        candidate_schema = json.loads(
            (ROOT / "protocol/orchestration/creative-execution-plan-candidate.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        plan_schema = json.loads(
            (ROOT / "protocol/orchestration/creative-execution-plan.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        compiled_graph_schema = json.loads(
            (ROOT / "protocol/orchestration/compiled-task-graph.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        constitution_payload = YAML(typ="safe").load(
            (ROOT / "protocol/orchestration/constitution.v1.yaml").read_text(encoding="utf-8")
        )

        self.assertEqual(candidate_schema["$id"], CANDIDATE_SCHEMA)
        self.assertEqual(plan_schema["$id"], PLAN_SCHEMA)
        self.assertEqual(compiled_graph_schema["$id"], COMPILED_GRAPH_SCHEMA)
        self.assertEqual(str(constitution_payload["version"]), constitution_v1().version)
        self.assertEqual(
            {item["id"] for item in constitution_payload["rules"]},
            {rule.rule_id for rule in constitution_v1().rules},
        )
        self.assertEqual(len(constitution_v1().digest), 64)


def _candidate_payload() -> dict:
    return {
        "schema": CANDIDATE_SCHEMA,
        "scope": {
            "kind": "chapter",
            "key": "chapter_03",
            "volume_id": "volume_01",
            "chapter_ids": ["chapter_03"],
            "scene_ids": ["scene_0021"],
        },
        "objective": "完成第三章并强化主角对盟友的不信任。",
        "interpretation": {
            "dramatic_problem": "主角必须合作，但无法确认盟友是否泄密。",
            "reader_effect": "从短暂安心转为新的怀疑。",
            "chapter_function": "改变关系并制造下一章行动压力。",
            "assumptions": [
                {
                    "statement": "盟友仍不知道主角掌握了第二封信。",
                    "evidence_refs": ["canon/timeline.yaml"],
                }
            ],
            "uncertainties": ["盟友是否主动泄密尚未成为 Canon。"],
        },
        "strategy": {
            "scene_inventory": [
                {
                    "scene_ref": "scene_0021",
                    "function": "confrontation",
                    "pace": "slow",
                    "roleplay_depth": "full",
                }
            ],
            "branch_count": 4,
            "revision_policy": "targeted_then_rewrite",
            "narrative_distance": "close_to_medium",
            "promise_policy": {"resolve": [], "defer": ["promise_0008"]},
        },
        "task_nodes": [
            {
                "node_id": "pressure-analysis",
                "kind": "creative_analysis",
                "scope_refs": ["chapter_03"],
                "depends_on": [],
                "requested_capabilities": ["project.query"],
                "parameters": {"depth": "standard"},
                "contribution": {
                    "kind": "evidence",
                    "description": "形成角色压力与误判依据。",
                },
                "progress_contract": {
                    "formal_artifact_delta": [],
                    "obligations_fulfilled": [],
                    "obligations_deferred": [],
                    "target_hanzi": 0,
                    "word_tolerance": 0.08,
                    "maximum_open_review_notes": 0,
                    "expected_state_patch": "",
                },
            }
        ],
        "replan_rules": [
            {
                "trigger": "review_failed",
                "threshold": 2,
                "action": "reconsider_branch_or_rewrite",
            }
        ],
        "freedom_request": {
            "max_added_tasks": 6,
            "max_replans_per_scope": 2,
            "max_parallel_read_tasks": 3,
            "max_branch_count": 4,
            "max_research_tasks": 0,
            "max_research_cost": 0.0,
            "max_analysis_to_production_ratio": 0.35,
            "max_plan_depth": 32,
            "max_plan_stall_cycles": 2,
        },
    }


if __name__ == "__main__":
    unittest.main()
