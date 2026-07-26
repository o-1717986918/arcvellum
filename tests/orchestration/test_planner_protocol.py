import hashlib
import json
from pathlib import Path
import unittest

from literary_engineering_studio.observability.context_ledger import CONTEXT_LEDGER_SCHEMA
from literary_engineering_studio.orchestration.agent_protocol import (
    AGENT_REQUEST_SCHEMA,
    REVIEW_JUDGMENT_SCHEMA,
    REVIEW_RECEIPT_SCHEMA,
    OrchestrationAgentRequest,
    OrchestrationReviewVerdict,
    parse_review_judgment,
    seal_orchestration_review,
)
from literary_engineering_studio.orchestration.context_builder import (
    PlanningSourceDocument,
    assemble_planning_context,
)
from literary_engineering_studio.orchestration.profiles import (
    OrchestrationAgentRole,
    orchestration_profile,
)
from literary_engineering_studio.orchestration.truth_partition import (
    AssertionKind,
    ProvenanceRef,
    TruthPartition,
    partition_can_satisfy_formal_gate,
)


DIGEST = hashlib.sha256(b"evidence").hexdigest()
ROOT = Path(__file__).resolve().parents[2]


class PlannerProtocolTests(unittest.TestCase):
    def test_future_intent_cannot_claim_fact_or_satisfy_formal_gate(self):
        with self.assertRaisesRegex(ValueError, "future intent"):
            ProvenanceRef(
                source_ref="plan:candidate",
                digest=DIGEST,
                partition=TruthPartition.FUTURE_INTENT,
                assertion_kind=AssertionKind.FACT,
                purpose="next scene proposal",
            )
        proposal = ProvenanceRef(
            source_ref="plan:candidate",
            digest=DIGEST,
            partition=TruthPartition.FUTURE_INTENT,
            assertion_kind=AssertionKind.PROPOSAL,
            purpose="next scene proposal",
        )
        self.assertEqual(proposal.as_dict()["assertion_kind"], "proposal")
        self.assertFalse(partition_can_satisfy_formal_gate(TruthPartition.FUTURE_INTENT))
        self.assertFalse(partition_can_satisfy_formal_gate(TruthPartition.EVIDENCE))
        self.assertTrue(partition_can_satisfy_formal_gate(TruthPartition.CURRENT_STATE))

    def test_profiles_are_machine_owned_read_only_and_independent(self):
        planner = orchestration_profile(OrchestrationAgentRole.PLANNER)
        reviewer = orchestration_profile(OrchestrationAgentRole.REVIEWER)
        self.assertFalse(planner.can_write_formal_files)
        self.assertFalse(reviewer.can_write_formal_files)
        self.assertFalse(planner.can_activate_plan)
        self.assertFalse(reviewer.can_activate_plan)
        self.assertEqual(planner.network_policy, "deny")
        self.assertTrue(reviewer.requires_independent_session)
        self.assertNotEqual(planner.output_schema, reviewer.output_schema)

    def test_context_prioritizes_mandatory_sources_and_records_redacted_truncation(self):
        context = assemble_planning_context(
            (
                PlanningSourceDocument(
                    "notes/optional.md",
                    "Optional",
                    "secondary idea",
                    TruthPartition.EVIDENCE,
                    "optional text",
                ),
                PlanningSourceDocument(
                    "canon/world.yaml",
                    "Canon",
                    "mandatory world truth",
                    TruthPartition.STABLE_KNOWLEDGE,
                    "api_key=very-secret-value " + "世" * 100,
                    mandatory=True,
                ),
                PlanningSourceDocument(
                    "characters/state.yaml",
                    "State",
                    "mandatory current state",
                    TruthPartition.CURRENT_STATE,
                    "current state",
                    mandatory=True,
                ),
            ),
            project_root_hash="project-hash",
            session_id="planner-session",
            operation_id="plan-op:chapter-1",
            max_source_characters=30,
            max_total_characters=45,
        )
        self.assertEqual(context.ledger.entries[0].source_ref, "canon/world.yaml")
        self.assertEqual(context.ledger.entries[1].source_ref, "characters/state.yaml")
        self.assertTrue(context.ledger.entries[0].truncated)
        self.assertIn("[REDACTED]", context.ledger.entries[0].preview)
        self.assertNotIn("very-secret-value", json.dumps(context.ledger.as_dict()))
        self.assertEqual(
            context.ledger.assembled_sha256,
            hashlib.sha256(context.text.encode("utf-8")).hexdigest(),
        )

    def test_context_digest_changes_with_visible_content_and_duplicate_sources_fail(self):
        def build(content: str):
            return assemble_planning_context(
                (
                    PlanningSourceDocument(
                        "canon/world.yaml",
                        "Canon",
                        "world",
                        TruthPartition.STABLE_KNOWLEDGE,
                        content,
                        mandatory=True,
                    ),
                ),
                project_root_hash="project-hash",
                session_id="planner-session",
                operation_id="plan-op",
            )

        self.assertNotEqual(build("alpha").ledger.digest, build("beta").ledger.digest)
        with self.assertRaisesRegex(ValueError, "unique"):
            assemble_planning_context(
                (
                    PlanningSourceDocument("same", "A", "a", TruthPartition.EVIDENCE, "a"),
                    PlanningSourceDocument("same", "B", "b", TruthPartition.EVIDENCE, "b"),
                ),
                project_root_hash="project-hash",
                session_id="planner-session",
                operation_id="plan-op",
            )

    def test_agent_request_transports_profile_without_formal_write_authority(self):
        context = assemble_planning_context(
            (
                PlanningSourceDocument(
                    "plot/outline.md",
                    "Outline",
                    "chapter objective",
                    TruthPartition.FUTURE_INTENT,
                    "chapter outline",
                    mandatory=True,
                ),
            ),
            project_root_hash="project-hash",
            session_id="planner-session",
            operation_id="plan-op",
        )
        request = OrchestrationAgentRequest(
            request_id="plan-request-1",
            session_id="planner-session",
            role=OrchestrationAgentRole.PLANNER,
            objective="plan chapter one",
            context_ledger_id=context.ledger.ledger_id,
            context_ledger_digest=context.ledger.digest,
            subject_digests=(DIGEST,),
        ).as_dict()
        self.assertEqual(request["schema"], AGENT_REQUEST_SCHEMA)
        self.assertFalse(request["profile"]["can_write_formal_files"])
        self.assertEqual(request["emission_mode"], "structured_response")

    def test_review_candidate_cannot_forge_machine_identity_and_session_must_be_independent(self):
        with self.assertRaisesRegex(ValueError, "machine-owned"):
            parse_review_judgment(
                {
                    "schema": REVIEW_JUDGMENT_SCHEMA,
                    "verdict": "pass",
                    "summary": "looks valid",
                    "findings": [],
                    "reviewer_session_id": "forged",
                }
            )
        judgment = parse_review_judgment(
            {
                "schema": REVIEW_JUDGMENT_SCHEMA,
                "verdict": "pass_with_notes",
                "summary": "valid with one non-blocking concern",
                "findings": [
                    {
                        "severity": "warning",
                        "rule_id": "reader-effect-specificity",
                        "message": "reader effect is broad",
                        "required_change": "make it concrete before activation",
                    }
                ],
            }
        )
        kwargs = {
            "plan_id": "plan-1",
            "plan_revision": 1,
            "planner_session_id": "session-a",
            "reviewer_session_id": "session-a",
            "context_ledger_digest": DIGEST,
            "candidate_digest": DIGEST,
            "plan_digest": DIGEST,
            "graph_digest": DIGEST,
            "simulation_digest": DIGEST,
        }
        with self.assertRaisesRegex(ValueError, "independent"):
            seal_orchestration_review(judgment, **kwargs)
        kwargs["reviewer_session_id"] = "session-b"
        receipt = seal_orchestration_review(judgment, **kwargs)
        self.assertEqual(receipt.verdict, OrchestrationReviewVerdict.PASS_WITH_NOTES)
        self.assertTrue(receipt.activation_eligible)
        self.assertEqual(receipt.as_dict()["schema"], REVIEW_RECEIPT_SCHEMA)
        empty_notes = parse_review_judgment(
            {
                "schema": REVIEW_JUDGMENT_SCHEMA,
                "verdict": "pass_with_notes",
                "summary": "claims notes without evidence",
                "findings": [],
            }
        )
        with self.assertRaisesRegex(ValueError, "at least one"):
            seal_orchestration_review(empty_notes, **kwargs)

    def test_protocol_schema_ids_match_runtime_contracts(self):
        expected = {
            "context-ledger.v1.schema.json": CONTEXT_LEDGER_SCHEMA,
            "orchestration-agent-request.v1.schema.json": AGENT_REQUEST_SCHEMA,
            "orchestration-review.v1.schema.json": REVIEW_RECEIPT_SCHEMA,
        }
        for filename, schema_id in expected.items():
            payload = json.loads(
                (ROOT / "protocol" / "orchestration" / filename).read_text(encoding="utf-8")
            )
            self.assertEqual(payload["$id"], schema_id)


if __name__ == "__main__":
    unittest.main()
