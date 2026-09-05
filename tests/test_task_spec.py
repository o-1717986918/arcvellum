import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import (
    TaskPackage,
    normalize_relative_path,
)
from literary_engineering_studio_engine.tasking.package_contract import (
    enrich_task_payload,
)
from literary_engineering_studio_engine.public.tasking import (
    parse_task_document,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "task_protocol"
    / "v1_route_envelopes.json"
)


class TaskSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.cases = fixture["cases"]

    def test_every_v1_route_round_trips_without_contract_drift(self):
        for case in self.cases:
            with self.subTest(route=case["name"]):
                payload = enrich_task_payload(case["payload"])
                document = parse_task_document(
                    payload,
                    normalize_path=normalize_relative_path,
                )
                self.assertEqual(document.to_v1_payload(), payload)

    def test_spec_separates_identity_intent_resources_and_lifecycle(self):
        payload = enrich_task_payload(self.cases[0]["payload"])
        document = parse_task_document(
            payload,
            normalize_path=normalize_relative_path,
        )

        self.assertEqual(
            document.spec.identity.task_id,
            "scene-development-scene-0001-prose-generation",
        )
        self.assertEqual(document.spec.intent.current_state, "prose-generation")
        self.assertEqual(
            document.spec.source_paths[0].uri,
            "project://scenes/scene_0001.yaml",
        )
        self.assertEqual(document.lifecycle.status, "issued")
        self.assertNotIn("status", document.spec.extensions)

    def test_spec_and_nested_extension_values_are_immutable(self):
        payload = enrich_task_payload(self.cases[0]["payload"])
        spec = parse_task_document(
            payload,
            normalize_path=normalize_relative_path,
        ).spec

        with self.assertRaises(TypeError):
            spec.extensions["new"] = "value"
        with self.assertRaises(TypeError):
            spec.extensions["prompt_asset"]["version"] = "changed"

    def test_legacy_commands_are_typed_as_compatibility_operations(self):
        payload = enrich_task_payload(self.cases[1]["payload"])
        spec = parse_task_document(
            payload,
            normalize_path=normalize_relative_path,
        ).spec

        self.assertEqual(
            spec.operations.prepare.operation_id,
            "legacy.command.prepare",
        )
        self.assertEqual(
            spec.operations.prepare.arguments["command"],
            payload["command"],
        )
        self.assertEqual(
            spec.operations.submit.display_command,
            payload["submission_command"],
        )

    def test_task_package_projects_properties_from_current_typed_spec(self):
        payload = enrich_task_payload(self.cases[0]["payload"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = TaskPackage(
                root,
                root / "task.json",
                root / "task.md",
                payload,
            )

            self.assertEqual(task.task_id, payload["task_id"])
            self.assertEqual(
                task.expected_outputs,
                tuple(payload["expected_outputs"]),
            )
            self.assertFalse(task.execution_contract.compatibility_derived)

            payload["current_state"] = "candidate-review"
            self.assertEqual(task.current_state, "candidate-review")


if __name__ == "__main__":
    unittest.main()
