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
        "AUTHORIZED_DEMO_PROJECT_SCHEMA",
        "TEXT_EXTENSIONS",
        "AuthorizedDemoProjectResult",
        "DistributionScope",
        "InitOptions",
        "atomic_write_batch",
        "atomic_write_text",
        "build_authorized_demo_project",
        "engine_root",
        "ingest_existing_work",
        "init_work_project",
        "is_authorized_demo_reference",
        "load_authorized_work_manifest",
        "seal_authorized_demo_project",
    ),
    "tasking": (
        "agent_task_completion_status",
        "branch_selection_status",
        "derive_execution_policy",
        "ENGINE_OPERATION_SCHEMA",
        "EngineOperation",
        "HumanGate",
        "infer_human_gate",
        "issue_next_task",
        "operation_from_legacy_command",
        "operation_from_payload",
        "operation_parameters",
        "OPERATION_REGISTRY",
        "OutputContract",
        "parse_execution_contract",
        "parse_output_contracts",
        "parse_task_document",
        "resolve_operation_argv",
        "semantic_artifact_definition",
        "semantic_artifact_errors",
        "semantic_artifact_relative_path",
        "semantic_artifact_template",
        "SCENE_CANDIDATE_STATES",
        "SCENE_REVISION_STATES",
        "TaskDocument",
        "TaskExecutionContract",
        "TaskIdentity",
        "TaskIntent",
        "TaskLifecycle",
        "TaskOperations",
        "TaskResourceRef",
        "TaskSpec",
        "TASK_SCHEMA_V1",
        "TASK_SCHEMA_V2",
        "task_document_to_v2",
        "task_semantic_fingerprint",
        "validated_branch_proposal_ids",
        "write_agent_completion_marker",
    ),
    "workflow": (
        "asset_candidate_states",
        "build_task_package_summary",
        "build_workflow_activity",
        "build_workflow_state",
        "next_scene_workflow_state",
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
        "build_current_human_choices",
        "build_narrative_evidence",
        "build_project_library",
        "count_delivery_chars",
        "count_delivery_chinese_content_chars",
        "display_counts",
        "final_body_from_workbench_text",
        "finalize_human_choice",
        "load_authorized_reader_units",
        "markdown_to_display_text",
        "read_authorized_reader_body",
        "record_human_choice",
        "record_ui_note",
        "save_display_field",
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
        self.assertIs(workflow.next_scene_workflow_state, internal_workflow.next_scene_workflow_state)
        self.assertIs(workflow.project_workflow_state, internal_workflow.project_workflow_state)
        self.assertIs(prompting.validate_payload, internal_schema.validate_payload)
        self.assertIs(projections.display_counts, display_cleaner.display_counts)
        self.assertIs(orchestration.PlanNodeKind, internal_orchestration.PlanNodeKind)


if __name__ == "__main__":
    unittest.main()
