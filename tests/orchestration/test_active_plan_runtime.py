from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.observability.context_ledger import parse_context_ledger
from literary_engineering_studio.orchestration import (
    ActivePlanLoader,
    assisted_activate_persisted_revision,
    authorize_persisted_revision,
    persist_shadow_revision,
)
from literary_engineering_studio.orchestration.agent_protocol import (
    OrchestrationReviewReceipt,
    OrchestrationReviewVerdict,
)
from literary_engineering_studio.orchestration.audit_integrity import (
    canonical_json_digest,
)
from literary_engineering_studio.orchestration.contracts import to_primitive
from literary_engineering_studio.runtime.mutation_tracking import (
    WorkerMutationTracker,
)
from literary_engineering_studio.runtime.sandbox import stage_task
from literary_engineering_studio.runtime.task_snapshot import load_run_task_snapshot
from literary_engineering_studio.runtime.worker_results import WorkerRunResult
from literary_engineering_studio.worker import AgentWorker
from literary_engineering_studio_engine.agent_tasks import (
    write_agent_completion_marker,
)
from literary_engineering_studio_engine.approval import record_workflow_approval
from literary_engineering_studio_engine.canon_evolver import apply_canon_patch
from literary_engineering_studio_engine.character_state_apply import (
    apply_character_state_patch,
)
from literary_engineering_studio_engine.literary.scene.promotion.candidate import (
    promote_scene_candidate,
)
from literary_engineering_studio_engine.routes.scene.definition import (
    _build_task_payload,
)
from literary_engineering_studio_engine.task_registry import _enrich_task_payload

from tests.orchestration.fixtures import scene_plan_candidate
from tests.orchestration.plan_persistence_support import (
    FINGERPRINT,
    shadow_pipeline,
)
from tests.scene_lifecycle_support import prepare_promotable_candidate


class ActivePlanRuntimeTests(unittest.TestCase):
    def test_assisted_authorization_is_required_and_loader_verifies_full_chain(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, store, plan = _reviewed_revision(Path(temporary))
            with self.assertRaisesRegex(RuntimeError, "shadow-only"):
                from literary_engineering_studio.orchestration import (
                    activate_persisted_revision,
                )

                activate_persisted_revision(
                    root,
                    store=store,
                    plan_id=plan.plan_id,
                    revision=plan.revision,
                    expected_active_revision=0,
                    current_project_fingerprint=FINGERPRINT,
                )

            assisted_activate_persisted_revision(
                root,
                store=store,
                plan_id=plan.plan_id,
                revision=plan.revision,
                expected_active_revision=0,
                current_project_fingerprint=FINGERPRINT,
                authorized_by="user:test-owner",
                reason="Approve one bounded scene plan for AO-4 verification.",
            )
            active = ActivePlanLoader(
                store,
                fingerprint_provider=lambda _root: FINGERPRINT,
            ).load(root)

            self.assertIsNotNone(active)
            assert active is not None
            self.assertEqual(active.plan, plan)
            self.assertEqual(active.graph.plan_id, plan.plan_id)
            revision = store.read_creative_plan_revision(plan.plan_id, plan.revision)
            self.assertEqual(revision["review"]["lifecycle"], "assisted_authorized")
            self.assertTrue(revision["review"]["activation_eligible"])

    def test_loader_rejects_stale_and_tampered_active_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, store, plan = _active_revision(Path(temporary))
            with self.assertRaisesRegex(RuntimeError, "stale"):
                ActivePlanLoader(
                    store,
                    fingerprint_provider=lambda _root: "stale-project",
                ).load(root)

            projection_path = root / "workflow/orchestration/active_plan.json"
            projection = json.loads(projection_path.read_text(encoding="utf-8"))
            projection["authorization_digest"] = "f" * 64
            projection_path.write_text(
                json.dumps(projection, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "authorization digest"):
                ActivePlanLoader(
                    store,
                    fingerprint_provider=lambda _root: FINGERPRINT,
                ).load(root)

    def test_authorization_is_idempotent_but_conflicting_actor_or_reason_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, store, plan = _reviewed_revision(Path(temporary))
            kwargs = {
                "store": store,
                "plan_id": plan.plan_id,
                "revision": plan.revision,
                "authorized_by": "user:test-owner",
                "reason": "Approve the reviewed scene strategy.",
            }
            first = authorize_persisted_revision(root, **kwargs)
            repeated = authorize_persisted_revision(root, **kwargs)

            self.assertEqual(
                first["review"]["authorization"],
                repeated["review"]["authorization"],
            )
            with self.assertRaisesRegex(RuntimeError, "different authorization"):
                authorize_persisted_revision(
                    root,
                    **{**kwargs, "reason": "A conflicting approval rationale."},
                )

    def test_loader_rejects_audit_file_changed_after_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, store, plan = _active_revision(Path(temporary))
            revision = store.read_creative_plan_revision(
                plan.plan_id,
                plan.revision,
            )
            normalized = root / revision["normalized"]["path"]
            normalized.write_text(
                normalized.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
                ActivePlanLoader(
                    store,
                    fingerprint_provider=lambda _root: FINGERPRINT,
                ).load(root)

    def test_worker_binds_only_assisted_mode_and_falls_back_without_active_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, store, plan = _active_revision(Path(temporary))
            events: list[tuple[str, dict]] = []
            task = _scene_task(root)
            config = default_config()
            config["orchestration"].update({"enabled": True, "mode": "assisted"})
            worker = AgentWorker(
                config,
                plan_store=store,
                orchestration_fingerprint_provider=lambda _root: FINGERPRINT,
                event_sink=lambda event, data: events.append((event, data)),
            )

            bound = worker._bind_active_scene_plan(task)
            self.assertEqual(bound.payload["creative_plan_id"], plan.plan_id)
            self.assertEqual(bound.payload["creative_plan_node_id"], "roleplay")
            self.assertIn("--roleplay-depth targeted", bound.command)
            self.assertIn("orchestration.plan_bound", {event for event, _ in events})

            fixed_config = default_config()
            fixed = AgentWorker(
                fixed_config,
                plan_store=store,
                orchestration_fingerprint_provider=lambda _root: FINGERPRINT,
            )._bind_active_scene_plan(task)
            self.assertNotIn("creative_plan_id", fixed.payload)

            projection = root / "workflow/orchestration/active_plan.json"
            projection.unlink()
            fallback = worker._bind_active_scene_plan(task)
            self.assertNotIn("creative_plan_id", fallback.payload)
            self.assertEqual(events[-1][0], "orchestration.fixed_fallback")

    def test_run_snapshot_freezes_bound_task_for_recovery_and_writeback(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root, store, _ = _active_revision(Path(temporary))
            config = default_config()
            config["orchestration"].update({"enabled": True, "mode": "assisted"})
            task = AgentWorker(
                config,
                plan_store=store,
                orchestration_fingerprint_provider=lambda _root: FINGERPRINT,
            )._bind_active_scene_plan(_scene_task(root))
            sandbox = stage_task(
                task,
                Path(runs),
                runtime="opencode",
                run_id="bound-snapshot",
            )

            task.task_json_path.write_text(
                json.dumps({**task.payload, "creative_plan_revision": 99}),
                encoding="utf-8",
            )
            run = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            recovered = load_run_task_snapshot(
                sandbox.run_root,
                project_root=root,
                manifest=run,
            )
            self.assertEqual(recovered.payload["creative_plan_revision"], 1)
            self.assertEqual(recovered.payload["creative_plan_node_id"], "roleplay")

            snapshot = sandbox.run_root / "task-snapshot/task.json"
            snapshot.write_text(
                snapshot.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "snapshot digest"):
                load_run_task_snapshot(
                    sandbox.run_root,
                    project_root=root,
                    manifest=run,
                )

    def test_recovery_and_writeback_context_reload_the_frozen_task(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root, store, _ = _active_revision(Path(temporary))
            config = default_config()
            config["orchestration"].update({"enabled": True, "mode": "assisted"})
            worker = AgentWorker(
                config,
                plan_store=store,
                orchestration_fingerprint_provider=lambda _root: FINGERPRINT,
            )
            task = worker._bind_active_scene_plan(_scene_task(root))
            sandbox = stage_task(
                task,
                Path(runs),
                runtime="opencode",
                run_id="bound-recovery",
            )
            task.task_json_path.write_text(
                json.dumps({**task.payload, "creative_plan_revision": 99}),
                encoding="utf-8",
            )
            output = sandbox.workspace / task.expected_outputs[0]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("fresh roleplay evidence\n", encoding="utf-8")
            observed: list[tuple[int, str]] = []

            def completed(snapshot, _sandbox, runtime_id):
                observed.append(
                    (
                        int(snapshot.payload["creative_plan_revision"]),
                        str(snapshot.payload["creative_plan_node_id"]),
                    )
                )
                return WorkerRunResult(
                    "complete",
                    snapshot.project_root,
                    snapshot.route,
                    snapshot.task_id,
                    runtime_id,
                    _sandbox.run_root,
                    _sandbox.workspace,
                    "snapshot accepted",
                )

            passing = type("PassingPreflight", (), {"passed": True, "as_dict": lambda self: {}})()
            with (
                patch.object(worker.writeback, "validate_outputs", return_value=passing),
                patch.object(worker.writeback, "complete_outputs", side_effect=completed),
            ):
                worker.resume_from_run(sandbox.run_root)
            _run, writeback_task, _sandbox = worker.writeback._writeback_context(
                sandbox.run_root
            )

            self.assertEqual(observed, [(1, "roleplay")])
            self.assertEqual(writeback_task.payload["creative_plan_revision"], 1)
            self.assertEqual(
                writeback_task.payload["creative_plan_node_id"],
                "roleplay",
            )

    def test_real_scene_closure_uses_one_plan_and_existing_formal_writebacks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, store, plan = _active_revision(
                Path(temporary),
                candidate_payload=_full_scene_candidate(),
                initialize_project=prepare_promotable_candidate,
            )
            candidate = root / "drafts/candidates/scene_0001-platform-agent.md"
            config = default_config()
            config["orchestration"].update({"enabled": True, "mode": "assisted"})
            worker = AgentWorker(
                config,
                plan_store=store,
                orchestration_fingerprint_provider=lambda _root: FINGERPRINT,
            )
            state_nodes = {
                "roleplay-simulation": "roleplay",
                "roleplay-agent-task": "roleplay",
                "branch-manifest": "branches",
                "branch-agent-task": "branches",
                "branch-selection": "selection",
                "composition-json": "composition",
                "composition-agent-task": "composition",
                "candidate-generation-provenance": "prose",
                "candidate-review": "review",
                "candidate-revision": "revision",
                "candidate-human-decision": "revision",
                "state-patch-json": "state",
                "state-agent-task": "state",
                "state-patch-approval": "state",
                "state-apply": "state",
                "canon-patch-json": "canon",
                "canon-agent-task": "canon",
            }

            for state, node_id in state_nodes.items():
                with self.subTest(state=state):
                    original = _engine_scene_task(root, state)
                    bound = worker._bind_active_scene_plan(original)
                    self.assertEqual(bound.task_id, original.task_id)
                    self.assertEqual(bound.task_type, original.task_type)
                    self.assertEqual(bound.expected_outputs, original.expected_outputs)
                    self.assertEqual(bound.payload["creative_plan_id"], plan.plan_id)
                    self.assertEqual(
                        bound.payload["creative_plan_revision"],
                        plan.revision,
                    )
                    self.assertEqual(
                        bound.payload["creative_plan_node_id"],
                        node_id,
                    )

            promotion = worker._bind_active_scene_plan(
                _engine_scene_task(root, "promotion-manifest")
            )
            self.assertEqual(
                promotion.payload["creative_plan_binding_status"],
                "formal_lifecycle_passthrough",
            )
            promoted = promote_scene_candidate(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                candidate=candidate.relative_to(root),
                overwrite=True,
            )
            self.assertTrue(promoted.draft_path.is_file())

            state_apply = _apply_reviewed_state_patch(root)
            canon_apply = _apply_approved_canon_patch(root)
            self.assertTrue(state_apply.manifest_path.is_file())
            self.assertTrue(canon_apply.json_path.is_file())
            self.assertIn(
                "见过潮线",
                (root / "characters/e2e-li.yml").read_text(encoding="utf-8"),
            )
            self.assertTrue(
                (root / "canon/applied/scene_0001_canon_patch_apply.json").is_file()
            )

    def test_context_ledger_and_mutation_receipt_share_plan_identity(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root, store, plan = _active_revision(Path(temporary))
            config = default_config()
            config["orchestration"].update({"enabled": True, "mode": "assisted"})
            task = AgentWorker(
                config,
                plan_store=store,
                orchestration_fingerprint_provider=lambda _root: FINGERPRINT,
            )._bind_active_scene_plan(_scene_task(root))
            sandbox = stage_task(
                task,
                Path(runs),
                runtime="opencode",
                run_id="bound-evidence",
            )
            ledger = parse_context_ledger(
                json.loads(
                    (sandbox.run_root / "context-ledger.json").read_text(
                        encoding="utf-8"
                    )
                )
            )
            output = sandbox.control_workspace / "branches/scene_0001/roleplay.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("roleplay evidence\n", encoding="utf-8")
            receipt = WorkerMutationTracker(
                task,
                sandbox,
                session_id="worker-run:bound-evidence",
                event_sink=None,
            ).candidate_outputs(preflight_status="pass")[0]
            persisted = store.record_context_ledger(
                str(root),
                ledger.as_dict(),
            )

            self.assertEqual(ledger.plan_id, plan.plan_id)
            self.assertEqual(ledger.plan_revision, plan.revision)
            self.assertEqual(ledger.node_id, "roleplay")
            self.assertEqual(persisted["plan_id"], ledger.plan_id)
            self.assertEqual(persisted["plan_revision"], ledger.plan_revision)
            self.assertEqual(persisted["node_id"], ledger.node_id)
            self.assertEqual(receipt.plan_id, ledger.plan_id)
            self.assertEqual(receipt.plan_revision, ledger.plan_revision)
            self.assertEqual(receipt.node_id, ledger.node_id)
            self.assertEqual(receipt.context_ledger_id, ledger.ledger_id)


def _reviewed_revision(
    temporary: Path,
    *,
    candidate_payload=None,
    initialize_project=None,
):
    root = temporary / "work"
    root.mkdir()
    if initialize_project is None:
        (root / "project.yaml").write_text(
            "title: Active Plan Test\n",
            encoding="utf-8",
        )
    else:
        initialize_project(root)
    store = JobStore(temporary / "studio.sqlite3")
    candidate, plan, graph, lint_result, simulation = shadow_pipeline(
        candidate_payload
    )
    receipt = OrchestrationReviewReceipt(
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        planner_session_id="planner-session",
        reviewer_session_id="reviewer-session",
        context_ledger_digest="a" * 64,
        candidate_digest=plan.candidate_digest,
        plan_digest=lint_result.plan_digest,
        graph_digest=graph.graph_digest,
        simulation_digest=canonical_json_digest(to_primitive(simulation)),
        verdict=OrchestrationReviewVerdict.PASS,
        summary="Independent review confirms the bounded scene plan.",
        findings=(),
    )
    persist_shadow_revision(
        root,
        store=store,
        candidate_payload=candidate,
        plan=plan,
        graph=graph,
        lint_result=lint_result,
        simulation=simulation,
        review_receipt=receipt,
        review_context_digest="a" * 64,
    )
    return root, store, plan


def _active_revision(
    temporary: Path,
    *,
    candidate_payload=None,
    initialize_project=None,
):
    root, store, plan = _reviewed_revision(
        temporary,
        candidate_payload=candidate_payload,
        initialize_project=initialize_project,
    )
    assisted_activate_persisted_revision(
        root,
        store=store,
        plan_id=plan.plan_id,
        revision=plan.revision,
        expected_active_revision=0,
        current_project_fingerprint=FINGERPRINT,
        authorized_by="user:test-owner",
        reason="Approve one bounded scene plan for runtime verification.",
    )
    return root, store, plan


def _scene_task(root: Path) -> TaskPackage:
    task_dir = root / "workflow/tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_json = task_dir / "roleplay.task.json"
    task_markdown = task_dir / "roleplay.agent_tasks.md"
    task_markdown.write_text("# Roleplay task\n", encoding="utf-8")
    payload = _enrich_task_payload({
        "schema": "literary-engineering-workbench/agent-task/v1",
        "task_id": "scene-development-scene-0001-roleplay",
        "status": "opened",
        "route": "scene-development",
        "scene_id": "scene_0001",
        "current_state": "roleplay-simulation",
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.scene-development.roleplay.prepare.v1",
        "command": "simulate-scene <project>",
        "task_markdown": "workflow/tasks/roleplay.agent_tasks.md",
        "required_reading": [],
        "source_paths": [],
        "expected_outputs": ["branches/scene_0001/roleplay.md"],
        "hard_constraints": [],
        "validation_gates": [],
        "forbidden_shortcuts": [],
    })
    task_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return TaskPackage(root, task_json, task_markdown, payload)


def _engine_scene_task(root: Path, state: str) -> TaskPackage:
    payload = _enrich_task_payload(
        _build_task_payload(
            root,
            "scene-development",
            {
                "scene_id": "scene_0001",
                "scene": "scenes/scene_0001.yaml",
                "current_step": state,
                "next_action": "",
            },
        )
    )
    task_dir = root / "workflow/tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_json = task_dir / f"{state}.task.json"
    task_markdown = task_dir / f"{state}.agent_tasks.md"
    task_markdown.write_text(f"# {state}\n", encoding="utf-8")
    payload["task_markdown"] = task_markdown.relative_to(root).as_posix()
    task_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return TaskPackage(root, task_json, task_markdown, payload)


def _full_scene_candidate() -> dict:
    candidate = scene_plan_candidate()
    review = next(
        node for node in candidate["task_nodes"] if node["node_id"] == "review"
    )
    state = next(
        node for node in candidate["task_nodes"] if node["node_id"] == "state"
    )
    revision = deepcopy(review)
    revision.update(
        {
            "node_id": "revision",
            "kind": "scene_revision",
            "depends_on": ["review"],
        }
    )
    revision_review = deepcopy(review)
    revision_review.update(
        {
            "node_id": "revision-review",
            "depends_on": ["revision"],
        }
    )
    canon = deepcopy(state)
    canon.update(
        {
            "node_id": "canon",
            "kind": "canon_evolution",
            "depends_on": ["revision-review"],
        }
    )
    state["depends_on"] = ["canon"]
    candidate["task_nodes"].extend([revision, revision_review, canon])
    return candidate


def _apply_reviewed_state_patch(root: Path):
    character = root / "characters/e2e-li.yml"
    character.parent.mkdir(parents=True, exist_ok=True)
    character.write_text(
        "character_id: e2e-li\nname: 李\nstate:\n  known_facts: []\n",
        encoding="utf-8",
    )
    patch = root / "characters/state_patches/scene_0001_state_patch.json"
    patch.parent.mkdir(parents=True, exist_ok=True)
    patch_payload = {
        "scene_id": "scene_0001",
        "characters": [
            {
                "character_id": "e2e-li",
                "name": "李",
                "file": "characters/e2e-li.yml",
                "proposed_updates": {
                    "state": {
                        "known_facts_add": ["见过潮线"],
                        "resources_add": [],
                        "location_note": "",
                        "health_note": "",
                    },
                    "arc": {"candidate_changes": []},
                    "relationships": {"candidate_changes": []},
                },
            }
        ],
        "unresolved_changes": [],
    }
    patch.write_text(
        json.dumps(patch_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(patch.read_bytes()).hexdigest()
    review = patch.with_name("scene_0001_state_patch_review.json")
    review.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/state-patch-review/v1",
                "scene_id": "scene_0001",
                "status": "complete",
                "source_artifact": patch.relative_to(root).as_posix(),
                "state_patch_sha256": digest,
                "evidence_paths": ["drafts/scenes/scene_0001.md"],
                "verdict": "pass",
                "findings": ["正文证据支持已知事实变化。"],
                "approval_recommendation": "approve",
                "required_changes": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    sidecar = patch.with_suffix(".agent_tasks.md")
    sidecar.write_text("# state task\n", encoding="utf-8")
    write_agent_completion_marker(
        sidecar,
        root=root,
        handled_by="reviewer-session",
    )
    record_workflow_approval(
        root,
        patch.stem,
        "approve",
        subject_sha256=digest,
    )
    return apply_character_state_patch(
        root,
        patch=patch,
        approval_run_id=patch.stem,
    )


def _apply_approved_canon_patch(root: Path):
    patch = root / "canon/patches/scene_0001_canon_patch.json"
    patch.parent.mkdir(parents=True, exist_ok=True)
    patch.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/canon-patch-candidate/v0.1",
                "scene_id": "scene_0001",
                "canon_change": True,
                "no_canon_change_reason": "",
                "items": [
                    {
                        "type": "world_rule",
                        "summary": "越过潮线会留下可追踪的盐痕。",
                        "source_evidence": ["drafts/scenes/scene_0001.md#潮线"],
                        "target_files": ["canon/world_rules.yaml"],
                        "risk_level": "medium",
                        "requires_user_approval": True,
                    }
                ],
                "requires_user_approval": True,
                "status": "candidate",
                "applied": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    patch.with_suffix(".md").write_text(
        "# Canon Patch\n\n潮线规则候选。\n",
        encoding="utf-8",
    )
    sidecar = patch.with_suffix(".agent_tasks.md")
    sidecar.write_text("# canon evolve\n", encoding="utf-8")
    write_agent_completion_marker(sidecar, root=root, handled_by="main-agent")
    digest = hashlib.sha256(patch.read_bytes()).hexdigest()
    record_workflow_approval(
        root,
        patch.stem,
        "approve",
        subject_sha256=digest,
    )
    return apply_canon_patch(root, patch=patch, approval_run_id=patch.stem)


if __name__ == "__main__":
    unittest.main()
