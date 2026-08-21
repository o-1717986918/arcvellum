from __future__ import annotations

import unittest

from literary_engineering_studio_engine import orchestration as internal_orchestration
from literary_engineering_studio_engine.foundation import atomic_io, display_cleaner
from literary_engineering_studio_engine.projects import init as internal_projects
from literary_engineering_studio_engine.prompting.agents import schema as internal_schema
from literary_engineering_studio_engine.tasking import registry as internal_tasking
from literary_engineering_studio_engine.workflow import state as internal_workflow
from literary_engineering_studio_engine.public import (
    literary,
    orchestration,
    projections,
    projects,
    prompting,
    tasking,
    workflow,
)


EXPECTED_SYMBOLS = {
    "projects": (
        "INGEST_MODES",
        "TEXT_EXTENSIONS",
        "InitOptions",
        "atomic_write_batch",
        "atomic_write_text",
        "engine_root",
        "ingest_existing_work",
        "init_work_project",
    ),
    "tasking": (
        "agent_task_completion_status",
        "branch_selection_status",
        "issue_next_task",
        "semantic_artifact_definition",
        "semantic_artifact_errors",
        "semantic_artifact_relative_path",
        "semantic_artifact_template",
        "SCENE_CANDIDATE_STATES",
        "SCENE_REVISION_STATES",
        "validated_branch_proposal_ids",
        "write_agent_completion_marker",
    ),
    "workflow": (
        "asset_candidate_states",
        "build_workflow_state",
        "project_workflow_dashboard",
        "project_workflow_state",
    ),
    "prompting": (
        "list_prompt_assets",
        "load_schema_spec",
        "resolve_prompt_asset",
        "validate_payload",
    ),
    "projections": (
        "count_delivery_chars",
        "count_delivery_chinese_content_chars",
        "display_counts",
        "final_body_from_workbench_text",
        "markdown_to_display_text",
        "scalar_from_yaml_text",
    ),
    "orchestration": (
        "DEFAULT_ROUTE_ORDER",
        "DefaultPlanEquivalence",
        "FormalTaskCapability",
        "GateId",
        "PlanNodeKind",
        "RouteMacro",
        "check_default_plan_compatibility",
        "default_route_macro",
        "formal_task_capabilities",
        "formal_task_capability",
        "mandatory_gates_for",
        "scene_plan_node_kind",
    ),
}


class EnginePublicApiTests(unittest.TestCase):
    def test_public_symbol_snapshots_are_explicit_and_stable(self):
        modules = {
            "projects": projects,
            "tasking": tasking,
            "workflow": workflow,
            "prompting": prompting,
            "projections": projections,
            "orchestration": orchestration,
        }
        for name, expected in EXPECTED_SYMBOLS.items():
            with self.subTest(module=name):
                self.assertEqual(tuple(modules[name].__all__), expected)
        self.assertGreater(len(literary.__all__), 50)
        self.assertEqual(literary.__all__, sorted(literary.__all__))

    def test_public_surface_reexports_original_objects(self):
        self.assertIs(projects.init_work_project, internal_projects.init_work_project)
        self.assertIs(projects.atomic_write_text, atomic_io.atomic_write_text)
        self.assertIs(tasking.issue_next_task, internal_tasking.issue_next_task)
        self.assertIs(workflow.build_workflow_state, internal_workflow.build_workflow_state)
        self.assertIs(workflow.project_workflow_state, internal_workflow.project_workflow_state)
        self.assertIs(prompting.validate_payload, internal_schema.validate_payload)
        self.assertIs(projections.display_counts, display_cleaner.display_counts)
        self.assertIs(orchestration.PlanNodeKind, internal_orchestration.PlanNodeKind)


if __name__ == "__main__":
    unittest.main()
