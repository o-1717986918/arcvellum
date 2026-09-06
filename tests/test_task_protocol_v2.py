from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import (
    load_task_package,
    normalize_relative_path,
)
from literary_engineering_studio_engine.public.tasking import (
    TASK_SCHEMA_V1,
    TASK_SCHEMA_V2,
    parse_task_document,
    task_document_to_v2,
    task_semantic_fingerprint,
)
from literary_engineering_studio_engine.tasking.registry import issue_next_task, open_task
from literary_engineering_studio_engine.tasking.package_contract import enrich_task_payload
from literary_engineering_studio_engine.tasking.paths import load_task


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "task_protocol"
    / "v1_route_envelopes.json"
)


class TaskProtocolV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]

    def test_every_v1_route_adapts_to_v2_without_semantic_drift(self):
        for case in self.cases:
            with self.subTest(route=case["name"]):
                v1 = enrich_task_payload(case["payload"])
                before = parse_task_document(v1, normalize_path=normalize_relative_path)
                v2 = task_document_to_v2(before)
                after = parse_task_document(v2, normalize_path=normalize_relative_path)

                self.assertEqual(v2["schema"], TASK_SCHEMA_V2)
                self.assertEqual(
                    task_semantic_fingerprint(before),
                    task_semantic_fingerprint(after),
                )
                self.assertEqual(after.to_v1_payload(), v1)

    def test_v2_rejects_unregistered_core_and_extension_fields(self):
        document = parse_task_document(
            enrich_task_payload(self.cases[0]["payload"]),
            normalize_path=normalize_relative_path,
        )
        payload = task_document_to_v2(document)
        payload["spec"]["surprise"] = True
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            parse_task_document(payload, normalize_path=normalize_relative_path)

        payload = task_document_to_v2(document)
        payload["spec"]["extensions"]["task_id"] = "shadow"
        with self.assertRaisesRegex(ValueError, "reserved fields"):
            parse_task_document(payload, normalize_path=normalize_relative_path)

    def test_new_task_is_stored_as_v2_and_studio_reads_compatibility_view(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: v2 fixture\n", encoding="utf-8")

            issued = issue_next_task(root, route="character-and-world-assets")
            raw = json.loads(issued.task_json_path.read_text(encoding="utf-8"))
            package = load_task_package(root, issued.task_json_path)

            self.assertEqual(raw["schema"], TASK_SCHEMA_V2)
            self.assertIn("spec", raw)
            self.assertIn("lifecycle", raw)
            self.assertNotIn("task_id", raw)
            self.assertEqual(package.task_id, issued.task_id)
            self.assertEqual(package.payload["schema"], TASK_SCHEMA_V1)
            self.assertEqual(package.prepare_operation, package.task_spec.operations.prepare)

    def test_v2_lifecycle_update_does_not_mutate_spec(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: v2 fixture\n", encoding="utf-8")
            issued = issue_next_task(root, route="character-and-world-assets")
            before = json.loads(issued.task_json_path.read_text(encoding="utf-8"))

            opened = open_task(root, issued.task_id)
            after = json.loads(opened.task_json_path.read_text(encoding="utf-8"))

            self.assertEqual(after["schema"], TASK_SCHEMA_V2)
            self.assertEqual(after["spec"], before["spec"])
            self.assertEqual(after["lifecycle"]["status"], "opened")
            self.assertTrue(after["lifecycle"]["opened_at"])

    def test_existing_v1_task_remains_readable_and_writes_v1(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: v1 fixture\n", encoding="utf-8")
            issued = issue_next_task(root, route="character-and-world-assets")
            compatible = load_task(issued.task_json_path)
            issued.task_json_path.write_text(
                json.dumps(compatible, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            opened = open_task(root, issued.task_id)
            raw = json.loads(opened.task_json_path.read_text(encoding="utf-8"))

            self.assertEqual(raw["schema"], TASK_SCHEMA_V1)
            self.assertEqual(raw["status"], "opened")


if __name__ == "__main__":
    unittest.main()
