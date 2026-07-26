from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.orchestration import (
    FreedomBudget,
    NormalizationContext,
    PlanLintContext,
    PlanSimulationContext,
    activate_persisted_revision,
    evaluate_shadow_candidate,
    persist_shadow_revision,
    verify_persisted_revision,
)
from literary_engineering_studio.orchestration.agent_protocol import (
    OrchestrationReviewReceipt,
    OrchestrationReviewVerdict,
)

from tests.orchestration.fixtures import freedom_budget, scene_plan_candidate
from tests.orchestration.plan_persistence_support import (
    FINGERPRINT,
    PROJECT_ID,
    shadow_pipeline,
    simulation_context_for_graph,
)


class CreativePlanPersistenceTests(unittest.TestCase):
    def test_shadow_revision_writes_portable_files_and_small_sqlite_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            candidate, plan, graph, lint_result, simulation = shadow_pipeline()

            artifacts = persist_shadow_revision(
                root,
                store=store,
                candidate_payload=candidate,
                plan=plan,
                graph=graph,
                lint_result=lint_result,
                simulation=simulation,
            )
            repeated = persist_shadow_revision(
                root,
                store=store,
                candidate_payload=candidate,
                plan=plan,
                graph=graph,
                lint_result=lint_result,
                simulation=simulation,
            )

            self.assertEqual(artifacts, repeated)
            self.assertTrue(all((root / path).is_file() for path, _ in artifacts.files))
            indexed = store.read_creative_plan_revision(plan.plan_id, plan.revision)
            self.assertEqual(indexed["digest"], artifacts.revision_digest)
            self.assertEqual(set(indexed["candidate"]), {"path", "sha256"})
            self.assertNotIn("objective", json.dumps(indexed["candidate"]))
            self.assertEqual(len(store.creative_plan_events(plan.plan_id)), 2)
            self.assertEqual(
                verify_persisted_revision(root, indexed),
                artifacts.revision_digest,
            )

            (root / indexed["candidate"]["path"]).write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
                verify_persisted_revision(root, indexed)

    def test_failed_activation_restores_absent_active_plan_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            candidate, plan, graph, lint_result, simulation = shadow_pipeline()
            persist_shadow_revision(
                root,
                store=store,
                candidate_payload=candidate,
                plan=plan,
                graph=graph,
                lint_result=lint_result,
                simulation=simulation,
            )

            with self.assertRaisesRegex(RuntimeError, "shadow-only"):
                activate_persisted_revision(
                    root,
                    store=store,
                    plan_id=plan.plan_id,
                    revision=plan.revision,
                    expected_active_revision=0,
                    current_project_fingerprint=FINGERPRINT,
                )

            self.assertFalse(
                (root / "workflow" / "orchestration" / "active_plan.json").exists()
            )

    def test_shadow_persistence_rejects_cross_artifact_semantic_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            candidate, plan, graph, lint_result, simulation = shadow_pipeline()

            with self.assertRaisesRegex(ValueError, "candidate payload"):
                persist_shadow_revision(
                    root,
                    store=store,
                    candidate_payload={**candidate, "objective": "Unrelated objective"},
                    plan=plan,
                    graph=graph,
                    lint_result=lint_result,
                    simulation=simulation,
                )
            with self.assertRaisesRegex(ValueError, "Simulation"):
                persist_shadow_revision(
                    root,
                    store=store,
                    candidate_payload=candidate,
                    plan=plan,
                    graph=graph,
                    lint_result=lint_result,
                    simulation=replace(simulation, graph_digest="b" * 64),
                )
            forged_review = OrchestrationReviewReceipt(
                plan_id="plan-forged-review",
                plan_revision=plan.revision,
                planner_session_id="planner-session",
                reviewer_session_id="reviewer-session",
                context_ledger_digest="a" * 64,
                candidate_digest="a" * 64,
                plan_digest="a" * 64,
                graph_digest="a" * 64,
                simulation_digest="a" * 64,
                verdict=OrchestrationReviewVerdict.PASS,
                summary="Forged cross-plan receipt.",
                findings=(),
            )
            with self.assertRaisesRegex(ValueError, "review receipt"):
                persist_shadow_revision(
                    root,
                    store=store,
                    candidate_payload=candidate,
                    plan=plan,
                    graph=graph,
                    lint_result=lint_result,
                    simulation=simulation,
                    review_receipt=forged_review,
                    review_context_digest="a" * 64,
                )

    def test_measure_only_shadow_pipeline_stops_after_failed_lint(self):
        candidate = scene_plan_candidate()
        budget = FreedomBudget(**freedom_budget())
        candidate["task_nodes"] = [candidate["task_nodes"][0]]
        candidate["task_nodes"][0]["requested_capabilities"] = ["shell.exec"]

        evaluation = evaluate_shadow_candidate(
            candidate,
            normalization_context=_normalization_context(budget),
            lint_context=PlanLintContext(
                current_project_fingerprint=FINGERPRINT,
                known_scope_refs=frozenset({"scene_0001"}),
                allowed_capability_ids=frozenset({"project.query"}),
                authorized_budget=budget,
            ),
            simulation_context_factory=lambda _graph: PlanSimulationContext(
                current_project_fingerprint=FINGERPRINT,
                project_id=PROJECT_ID,
                task_observations=(),
                resource_claims=(),
            ),
        )

        self.assertFalse(evaluation.passed)
        self.assertIsNone(evaluation.graph)
        self.assertIsNone(evaluation.simulation)
        self.assertEqual(evaluation.timing.compile_ms, 0.0)
        self.assertEqual(evaluation.timing.simulate_ms, 0.0)

    def test_measure_only_shadow_pipeline_compiles_and_simulates_valid_plan(self):
        candidate = scene_plan_candidate()
        budget = FreedomBudget(**freedom_budget())

        evaluation = evaluate_shadow_candidate(
            candidate,
            normalization_context=_normalization_context(budget),
            lint_context=PlanLintContext(
                current_project_fingerprint=FINGERPRINT,
                known_scope_refs=frozenset({"chapter_01", "scene_0001"}),
                allowed_capability_ids=frozenset({"project.query"}),
                authorized_budget=budget,
            ),
            simulation_context_factory=simulation_context_for_graph,
        )

        self.assertTrue(evaluation.passed)
        self.assertIsNotNone(evaluation.graph)
        self.assertIsNotNone(evaluation.simulation)

    def test_revision_reservation_prevents_file_overwrite_on_digest_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            candidate, plan, graph, lint_result, simulation = shadow_pipeline()
            initial = persist_shadow_revision(
                root,
                store=store,
                candidate_payload=candidate,
                plan=plan,
                graph=graph,
                lint_result=lint_result,
                simulation=simulation,
            )
            before = {path: (root / path).read_bytes() for path, _ in initial.files}
            changed = scene_plan_candidate()
            changed["objective"] = "A different objective must not overwrite revision one."
            changed_pipeline = shadow_pipeline(changed, plan_id=plan.plan_id)

            with self.assertRaisesRegex(ValueError, "conflicts"):
                persist_shadow_revision(
                    root,
                    store=store,
                    candidate_payload=changed_pipeline[0],
                    plan=changed_pipeline[1],
                    graph=changed_pipeline[2],
                    lint_result=changed_pipeline[3],
                    simulation=changed_pipeline[4],
                )

            self.assertEqual(before, {path: (root / path).read_bytes() for path in before})
            verify_persisted_revision(
                root,
                store.read_creative_plan_revision(plan.plan_id, plan.revision),
            )

    def test_reserved_revision_can_resume_after_atomic_file_write_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            candidate, plan, graph, lint_result, simulation = shadow_pipeline()
            arguments = {
                "store": store,
                "candidate_payload": candidate,
                "plan": plan,
                "graph": graph,
                "lint_result": lint_result,
                "simulation": simulation,
            }

            with patch(
                "literary_engineering_studio.orchestration.persistence.atomic_write_batch",
                side_effect=OSError("write failed"),
            ):
                with self.assertRaisesRegex(OSError, "write failed"):
                    persist_shadow_revision(root, **arguments)
            self.assertEqual(
                store.read_creative_plan_revision(
                    plan.plan_id,
                    plan.revision,
                )["artifact_state"],
                "reserved",
            )

            persist_shadow_revision(root, **arguments)
            self.assertEqual(
                store.read_creative_plan_revision(
                    plan.plan_id,
                    plan.revision,
                )["artifact_state"],
                "ready",
            )


def _normalization_context(budget: FreedomBudget) -> NormalizationContext:
    return NormalizationContext(
        base_project_fingerprint=FINGERPRINT,
        approved_budget=budget,
        created_at="2026-07-26T00:00:00+00:00",
    )


if __name__ == "__main__":
    unittest.main()
