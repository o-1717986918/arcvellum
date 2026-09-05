from __future__ import annotations

from pathlib import Path
import unittest

from literary_engineering_studio_engine.public.tasking import (
    EngineOperation,
    OPERATION_REGISTRY,
    operation_from_legacy_command,
    operation_parameters,
    resolve_operation_argv,
)
from literary_engineering_studio_engine.tasking.operations import (
    TASK_COMPLETE_OPERATION,
    TASK_SUBMIT_OPERATION,
)


class EngineOperationTests(unittest.TestCase):
    def test_registered_prepare_operation_preserves_unicode_path_as_one_argument(self):
        operation = operation_from_legacy_command(
            "python -m literary_engineering_studio_engine word-budget "
            "<project> --target-words 30000"
        )
        self.assertIsNotNone(operation)

        project = Path("C:/Users/example/Documents/长篇项目")
        argv = resolve_operation_argv(operation, project)

        self.assertEqual(argv[0], "word-budget")
        self.assertEqual(argv[1], str(project.resolve()))
        self.assertEqual(argv[2:], ("--target-words", "30000"))

    def test_unknown_operation_fails_closed(self):
        operation = EngineOperation("arcvellum.engine/unknown.v1", {})
        with self.assertRaisesRegex(ValueError, "unknown Engine operation"):
            resolve_operation_argv(operation, Path("C:/project"))

    def test_legacy_shell_control_token_is_rejected(self):
        operation = operation_from_legacy_command(
            "python -m literary_engineering_studio_engine word-budget "
            "<project> && echo bypass"
        )
        with self.assertRaisesRegex(ValueError, "unsupported shell syntax"):
            resolve_operation_argv(operation, Path("C:/project"))

    def test_unresolved_prepare_parameters_are_explicit(self):
        operation = operation_from_legacy_command(
            "python -m literary_engineering_studio_engine asset-create "
            "<project> --type <type> --brief <user brief> [--source <path>]"
        )
        self.assertEqual(
            operation_parameters(operation),
            ("type", "user brief", "--source <path>"),
        )

    def test_submit_and_complete_operations_bind_runtime_values(self):
        submit = EngineOperation(TASK_SUBMIT_OPERATION, {"task_id": "scene-task"})
        complete = EngineOperation(TASK_COMPLETE_OPERATION, {"task_id": "scene-task"})
        project = Path("C:/project")

        submit_argv = resolve_operation_argv(
            submit,
            project,
            artifacts=("drafts/candidate.md",),
            note="ready",
        )
        complete_argv = resolve_operation_argv(
            complete,
            project,
            handled_by="pi-worker",
        )

        self.assertEqual(submit_argv[0], "task-submit")
        self.assertIn("drafts/candidate.md", submit_argv)
        self.assertEqual(complete_argv[-1], "pi-worker")

    def test_registry_contains_distinct_prepare_and_lifecycle_operations(self):
        self.assertIn("arcvellum.engine/compose-scene.v1", OPERATION_REGISTRY)
        self.assertIn(TASK_SUBMIT_OPERATION, OPERATION_REGISTRY)
        self.assertIn(TASK_COMPLETE_OPERATION, OPERATION_REGISTRY)


if __name__ == "__main__":
    unittest.main()
