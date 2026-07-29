from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.orchestration.agent_protocol import (
    REVIEW_JUDGMENT_SCHEMA,
)
from literary_engineering_studio.orchestration.agent_transport import (
    OrchestrationAgentResponse,
    RuntimeOrchestrationAgentTransport,
    parse_structured_agent_response,
)
from literary_engineering_studio.orchestration.context_builder import (
    PlanningSourceDocument,
)
from literary_engineering_studio.orchestration.contracts import FreedomBudget
from literary_engineering_studio.orchestration.lint import PlanLintContext
from literary_engineering_studio.orchestration.normalizer import (
    NormalizationContext,
)
from literary_engineering_studio.orchestration.profiles import (
    OrchestrationAgentRole,
)
from literary_engineering_studio.orchestration.service import (
    ShadowOrchestrationService,
    ShadowPlanningInput,
)
from literary_engineering_studio.orchestration.activation import (
    activate_persisted_revision,
)
from literary_engineering_studio.orchestration.settings import (
    OrchestrationMode,
    OrchestrationSettings,
    StrategyPreset,
)
from literary_engineering_studio.orchestration.truth_partition import (
    TruthPartition,
)

from tests.orchestration.fixtures import freedom_budget, scene_plan_candidate
from tests.orchestration.plan_persistence_support import (
    FINGERPRINT,
    simulation_context_for_graph,
)


class _Transport:
    def __init__(
        self,
        *,
        fail_role: OrchestrationAgentRole | None = None,
        same_session: bool = False,
        review_verdict: str = "pass",
        planner_payload: dict | None = None,
    ):
        self.fail_role = fail_role
        self.same_session = same_session
        self.review_verdict = review_verdict
        self.planner_payload = planner_payload or scene_plan_candidate()
        self.calls: list[tuple[OrchestrationAgentRole, Path]] = []

    def invoke(self, role, *, prompt, audit_root):
        self.calls.append((role, audit_root))
        if self.fail_role is role:
            raise RuntimeError(f"{role.value} fixture failure")
        if role is OrchestrationAgentRole.PLANNER:
            return OrchestrationAgentResponse(
                role=role,
                session_id="runtime-planner",
                payload=self.planner_payload,
                raw_text="planner candidate",
                deltas=("candidate ", "ready"),
                elapsed_ms=11.0,
            )
        findings = []
        if self.review_verdict == "fail":
            findings.append(
                {
                    "severity": "error",
                    "rule_id": "literary-coherence",
                    "message": "The plan does not sustain its reader promise.",
                    "required_change": "Rebuild the scene strategy before activation.",
                }
            )
        return OrchestrationAgentResponse(
            role=role,
            session_id="runtime-planner" if self.same_session else "runtime-reviewer",
            payload={
                "schema": REVIEW_JUDGMENT_SCHEMA,
                "verdict": self.review_verdict,
                "summary": "Exact evidence reviewed.",
                "findings": findings,
            },
            raw_text="review judgment",
            deltas=(),
            elapsed_ms=7.0,
        )


class ShadowAgentServiceTests(unittest.TestCase):
    def test_structured_response_accepts_one_object_and_rejects_commentary(self):
        self.assertEqual(
            parse_structured_agent_response('```json\n{"status": "ok"}\n```'),
            {"status": "ok"},
        )
        with self.assertRaisesRegex(ValueError, "one JSON object"):
            parse_structured_agent_response('Result: {"status": "ok"}')
        with self.assertRaisesRegex(ValueError, "role-isolated OpenCode"):
            RuntimeOrchestrationAgentTransport({}, runtime_id="host-agent")

    def test_shadow_run_uses_independent_sessions_and_never_activates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            transport = _Transport()
            service = ShadowOrchestrationService(_settings(True), transport)

            result = service.run(_request(root, store=store))

            self.assertTrue(result.shadow_completed)
            self.assertEqual(result.execution_route, "fixed")
            self.assertEqual(result.planner_session_id, "runtime-planner")
            self.assertEqual(result.reviewer_session_id, "runtime-reviewer")
            self.assertNotEqual(result.planner_session_id, result.reviewer_session_id)
            self.assertEqual(
                [role for role, _ in transport.calls],
                [OrchestrationAgentRole.PLANNER, OrchestrationAgentRole.REVIEWER],
            )
            self.assertTrue(all(root in path.resolve().parents for _, path in transport.calls))
            self.assertIsNotNone(result.artifacts)
            indexed = store.read_creative_plan_revision(result.plan_id, 1)
            self.assertEqual(indexed["review"]["status"], "pass")
            self.assertFalse(indexed["review"]["activation_eligible"])
            with self.assertRaisesRegex(RuntimeError, "shadow-only"):
                activate_persisted_revision(
                    root,
                    store=store,
                    plan_id=result.plan_id,
                    revision=1,
                    expected_active_revision=0,
                    current_project_fingerprint=FINGERPRINT,
                )
            self.assertFalse((root / "workflow" / "orchestration" / "active_plan.json").exists())
            audit = root / result.audit_root
            self.assertTrue((audit / "candidate.completed.json").is_file())
            self.assertTrue((audit / "review.json").is_file())
            self.assertTrue((audit / "comparison.json").is_file())
            self.assertTrue((audit / "planner" / "context-ledger.json").is_file())
            self.assertTrue((audit / "reviewer" / "context-ledger.json").is_file())
            self.assertTrue(result.comparison.fixed_route_unchanged)
            self.assertGreater(result.comparison.injected_gate_count, 0)
            self.assertEqual(result.events[-1].event_type.value, "plan.review.completed")
            durable_events = (audit / "events.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("plan.candidate.delta", durable_events)
            self.assertFalse(any(event.display_only for event in result.events))

    def test_feature_off_planner_failure_review_failure_and_stale_context_fallback(self):
        cases = (
            ("feature_off", _settings(False), _Transport(), [FINGERPRINT]),
            (
                "planner_failed",
                _settings(True),
                _Transport(fail_role=OrchestrationAgentRole.PLANNER),
                [FINGERPRINT, FINGERPRINT],
            ),
            (
                "review_failed",
                _settings(True),
                _Transport(fail_role=OrchestrationAgentRole.REVIEWER),
                [FINGERPRINT, FINGERPRINT, FINGERPRINT],
            ),
            (
                "stale_context_after_planner",
                _settings(True),
                _Transport(),
                [FINGERPRINT, "project-revision-2"],
            ),
        )
        for expected, settings, transport, fingerprints in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "work"
                root.mkdir()
                request = _request(root, fingerprints=fingerprints)
                result = ShadowOrchestrationService(settings, transport).run(request)
                self.assertEqual(result.status, "fixed_fallback")
                self.assertEqual(result.execution_route, "fixed")
                self.assertEqual(result.fallback_reason, expected)
                self.assertTrue(result.comparison.fixed_route_unchanged)
                self.assertTrue((root / result.audit_root / "fallback.json").is_file())
                self.assertFalse(
                    (root / "workflow" / "orchestration" / "active_plan.json").exists()
                )

    def test_rejected_review_and_same_session_are_safe_fallbacks(self):
        cases = (
            ("orchestration_review_rejected", _Transport(review_verdict="fail")),
            ("review_failed", _Transport(same_session=True)),
        )
        for expected, transport in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "work"
                root.mkdir()
                result = ShadowOrchestrationService(
                    _settings(True),
                    transport,
                ).run(_request(root))
                self.assertEqual(result.status, "fixed_fallback")
                self.assertEqual(result.fallback_reason, expected)
                self.assertFalse(
                    (root / "workflow" / "orchestration" / "active_plan.json").exists()
                )

    def test_oversized_exact_review_context_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            candidate = scene_plan_candidate()
            candidate["objective"] = "长" * 181_000
            result = ShadowOrchestrationService(
                _settings(True),
                _Transport(planner_payload=candidate),
            ).run(_request(root))
            self.assertEqual(result.status, "fixed_fallback")
            self.assertEqual(result.fallback_reason, "review_failed")

    def test_runtime_oserror_and_late_staleness_keep_the_fixed_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()

            class BrokenTransport(_Transport):
                def invoke(self, role, *, prompt, audit_root):
                    raise OSError("runtime connection closed")

            failed = ShadowOrchestrationService(
                _settings(True),
                BrokenTransport(),
            ).run(_request(root))
            self.assertEqual(failed.status, "fixed_fallback")
            self.assertEqual(failed.fallback_reason, "planner_failed")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            stale = ShadowOrchestrationService(
                _settings(True),
                _Transport(),
            ).run(
                _request(
                    root,
                    fingerprints=[
                        FINGERPRINT,
                        FINGERPRINT,
                        FINGERPRINT,
                        FINGERPRINT,
                        "project-revision-2",
                    ],
                )
            )
            self.assertEqual(stale.status, "fixed_fallback")
            self.assertEqual(stale.fallback_reason, "stale_context_before_persistence")

    def test_feature_off_does_not_call_the_project_fingerprint_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            request = _request(root)
            request = ShadowPlanningInput(
                **{
                    **request.__dict__,
                    "fingerprint_provider": lambda: (_ for _ in ()).throw(
                        OSError("must not be called")
                    ),
                }
            )
            result = ShadowOrchestrationService(
                _settings(False),
                _Transport(),
            ).run(request)
            self.assertEqual(result.fallback_reason, "feature_off")


def _settings(enabled: bool) -> OrchestrationSettings:
    return OrchestrationSettings(
        enabled=enabled,
        configured_mode=OrchestrationMode.SHADOW,
        effective_mode=OrchestrationMode.SHADOW if enabled else OrchestrationMode.FIXED,
        strategy_preset=StrategyPreset.BALANCED,
        constitution_version="1",
    )


def _request(
    root: Path,
    *,
    store=None,
    fingerprints: list[str] | None = None,
) -> ShadowPlanningInput:
    values = iter(fingerprints or [FINGERPRINT, FINGERPRINT, FINGERPRINT])
    last = FINGERPRINT

    def fingerprint() -> str:
        nonlocal last
        try:
            last = next(values)
        except StopIteration:
            pass
        return last

    budget = FreedomBudget(**freedom_budget())
    return ShadowPlanningInput(
        project_root=root,
        objective="Complete the first scene without weakening formal gates.",
        sources=(
            PlanningSourceDocument(
                "canon/world.yaml",
                "World canon",
                "stable world constraints",
                TruthPartition.STABLE_KNOWLEDGE,
                "The protagonist cannot leave the city before dawn.",
                mandatory=True,
            ),
            PlanningSourceDocument(
                "plot/chapter_01.yaml",
                "Chapter intent",
                "future chapter objective",
                TruthPartition.FUTURE_INTENT,
                "The protagonist accepts a costly promise.",
                mandatory=True,
            ),
        ),
        normalization_context=NormalizationContext(
            base_project_fingerprint=FINGERPRINT,
            approved_budget=budget,
            created_at="2026-07-26T00:00:00+00:00",
        ),
        lint_context=PlanLintContext(
            current_project_fingerprint=FINGERPRINT,
            known_scope_refs=frozenset({"chapter_01", "scene_0001"}),
            allowed_capability_ids=frozenset({"project.query"}),
            authorized_budget=budget,
        ),
        simulation_context_factory=simulation_context_for_graph,
        fingerprint_provider=fingerprint,
        store=store,
    )


if __name__ == "__main__":
    unittest.main()
