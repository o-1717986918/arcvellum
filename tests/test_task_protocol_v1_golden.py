import json
from pathlib import Path
import unittest

from literary_engineering_studio_engine.routes.catalog import ROUTE_READY_MESSAGES
from literary_engineering_studio_engine.tasking.package_contract import (
    TASK_CONTRACT_REVISION,
    enrich_task_payload,
    task_contract_fingerprint,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "task_protocol"
    / "v1_route_envelopes.json"
)


class TaskProtocolV1GoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_covers_every_formal_route_once(self):
        routes = [case["name"] for case in self.fixture["cases"]]
        self.assertEqual(len(routes), len(set(routes)))
        self.assertEqual(set(routes), set(ROUTE_READY_MESSAGES))

    def test_v1_route_envelopes_keep_their_execution_contracts(self):
        for case in self.fixture["cases"]:
            with self.subTest(route=case["name"]):
                enriched = enrich_task_payload(case["payload"])
                expected = case["expected"]

                self.assertEqual(enriched["schema"], case["payload"]["schema"])
                self.assertEqual(
                    enriched["task_contract_revision"], TASK_CONTRACT_REVISION
                )
                self.assertEqual(
                    enriched["execution_policy"], expected["execution_policy"]
                )
                self.assertEqual(enriched["agent_role"], expected["agent_role"])
                self.assertEqual(
                    enriched["runtime_capabilities_required"],
                    expected["runtime_capabilities_required"],
                )
                self.assertEqual(
                    enriched["human_gate"]["required"],
                    expected["human_gate_required"],
                )
                policies = {
                    item["path"]: item["writeback_policy"]
                    for item in enriched["output_contracts"]
                }
                self.assertEqual(policies, expected["output_policies"])
                receipts = enriched["system_owned_fields"]["lifecycle"][
                    "completion_receipts"
                ]
                self.assertEqual(
                    len(receipts), expected["completion_receipts"]
                )
                self.assertIn("operations", enriched)
                if str(enriched.get("command") or "").startswith("python -m "):
                    self.assertIn("prepare", enriched["operations"])
                if enriched.get("submission_command"):
                    self.assertIn("submit", enriched["operations"])
                if enriched.get("completion_command"):
                    self.assertIn("complete", enriched["operations"])
                self.assertEqual(
                    task_contract_fingerprint(enriched),
                    expected["fingerprint"],
                )

    def test_v1_fingerprint_excludes_mutable_lifecycle_fields(self):
        payload = enrich_task_payload(self.fixture["cases"][0]["payload"])
        baseline = task_contract_fingerprint(payload)
        payload.update(
            {
                "status": "complete",
                "opened_at": "2030-01-01T00:00:00Z",
                "completed_at": "2030-01-01T00:01:00Z",
                "submission": "workflow/tasks/example.submission.json",
                "validation": {"status": "pass"},
            }
        )
        self.assertEqual(task_contract_fingerprint(payload), baseline)


if __name__ == "__main__":
    unittest.main()
