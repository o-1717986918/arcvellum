from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio_engine.literary.scene.promotion.historical import (
    HistoricalPromotionValidation,
    build_historical_promotion_evidence,
    validate_historical_promotion,
)
from literary_engineering_studio_engine.literary.scene.promotion.context_archive import (
    context_archive_output_paths,
    seal_context_archive,
)
from literary_engineering_studio_engine.literary.scene.promotion.context_migration import (
    migrate_legacy_historical_context,
)
from literary_engineering_studio_engine.literary.scene.promotion.historical_context import (
    build_historical_revision_context_snapshot,
    historical_revision_candidate_source_paths,
    historical_revision_context_errors,
    historical_revision_source_paths,
)
from literary_engineering_studio_engine.literary.scene.promotion.generation_gate import (
    _generation_context_issues,
)
from literary_engineering_studio_engine.literary.scene.promotion.historical_readiness import (
    historical_scene_readiness,
)
from literary_engineering_studio_engine.literary.scene.promotion.revision import (
    build_scene_revision_task,
)
from literary_engineering_studio_engine.routes.scene.gates import (
    _promotion_gate_errors,
)
from literary_engineering_studio_engine.workflow.historical_truth import (
    preserve_current_historical_style_steps,
    preserve_historical_style_gates,
    preserve_historical_style_steps,
    preserve_valid_revision_preparation_steps,
)
import literary_engineering_studio_engine.task_registry as task_registry


class HistoricalScenePromotionTests(unittest.TestCase):
    def test_current_promotion_seals_preparation_but_requires_exact_static_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _manifest, _candidate, draft = self._sealed_promotion(
                Path(temporary)
            )
            review = root / "reviews/scene_0001-review.md"
            review.parent.mkdir(parents=True, exist_ok=True)
            review.write_text(
                "# review\n\n- 审查对象 SHA-256：`" + "0" * 64 + "`\n- 结论：pass\n",
                encoding="utf-8",
            )

            status, issues = historical_scene_readiness(root, "scene_0001") or ("", ())
            self.assertEqual(status, "needs_review")
            self.assertIn("exact post-promotion static review", issues[0])

            steps = [
                {"key": "branch-selection", "status": "stale", "next_action": "rerun"},
                {"key": "static-review", "status": "stale", "next_action": "review"},
                {"key": "state-agent-task", "status": "stale", "next_action": "state"},
            ]
            projected = preserve_current_historical_style_steps(
                root,
                "scene_0001",
                steps,
            )
            by_key = {str(item["key"]): item for item in projected}
            self.assertEqual(by_key["branch-selection"]["status"], "pass")
            self.assertEqual(by_key["static-review"]["status"], "stale")
            self.assertEqual(by_key["state-agent-task"]["status"], "stale")

            review.write_text(
                "# review\n\n- 审查对象 SHA-256：`"
                + self._sha(draft)
                + "`\n- 结论：pass\n",
                encoding="utf-8",
            )
            self.assertEqual(
                historical_scene_readiness(root, "scene_0001"),
                ("ready", ()),
            )

    def test_sealed_promotion_survives_future_style_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest, candidate, _draft = self._sealed_promotion(
                Path(temporary)
            )
            validation = validate_historical_promotion(
                root,
                "scene_0001",
                manifest,
            )

            self.assertTrue(validation.passed, validation.errors)
            self.assertTrue(validation.current)
            task = {
                "scene_id": "scene_0001",
                "source_paths": [candidate.relative_to(root).as_posix()],
            }
            with (
                patch(
                    "literary_engineering_studio_engine.routes.scene.gates."
                    "_candidate_generation_gate_errors",
                    side_effect=AssertionError(
                        "sealed history must not use the active style gate"
                    ),
                ),
                patch(
                    "literary_engineering_studio_engine.routes.scene.gates."
                    "_candidate_review_gate_errors",
                    side_effect=AssertionError(
                        "sealed history must not use the active style review"
                    ),
                ),
            ):
                self.assertEqual(_promotion_gate_errors(root, task), [])

    def test_tamper_or_new_candidate_cannot_hide_behind_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest, candidate, draft = self._sealed_promotion(
                Path(temporary)
            )
            draft.write_text(
                draft.read_text(encoding="utf-8") + "\n篡改。\n",
                encoding="utf-8",
            )
            invalid = validate_historical_promotion(
                root,
                "scene_0001",
                manifest,
            )
            self.assertFalse(invalid.passed)
            self.assertIn(
                "historical promotion draft digest mismatch",
                invalid.errors,
            )

            draft.write_text(
                "# 场景草稿\n\n## 正文草稿\n\n旧城的门仍然关着。\n",
                encoding="utf-8",
            )
            manifest = self._refresh_evidence(root, manifest, candidate, draft)
            promotion_path = (
                root
                / "drafts"
                / "promotions"
                / "scene_0001_promotion.json"
            )
            promotion_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            newer = root / "drafts" / "candidates" / "scene_0001-new.md"
            newer.write_text("## 正文候选\n\n新的候选。\n", encoding="utf-8")
            future = promotion_path.stat().st_mtime_ns + 10_000_000
            os.utime(newer, ns=(future, future))

            superseded = validate_historical_promotion(
                root,
                "scene_0001",
                manifest,
            )
            self.assertTrue(superseded.passed, superseded.errors)
            self.assertFalse(superseded.current)

            manifest_future = newer.stat().st_mtime_ns + 10_000_000
            os.utime(promotion_path, ns=(manifest_future, manifest_future))
            after_metadata_update = validate_historical_promotion(
                root,
                "scene_0001",
                manifest,
            )
            self.assertFalse(after_metadata_update.current)

    def test_numbered_static_revision_supersedes_historical_promotion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest, _candidate, _draft = self._sealed_promotion(
                Path(temporary)
            )
            promotion_path = (
                root
                / "drafts"
                / "promotions"
                / "scene_0001_promotion.json"
            )
            numbered = (
                root
                / "drafts"
                / "revisions"
                / "scene_0001_revision_02.md"
            )
            numbered.parent.mkdir(parents=True, exist_ok=True)
            numbered.write_text(
                "## 修订正文候选\n\n静态审查后的新候选。\n",
                encoding="utf-8",
            )
            future = promotion_path.stat().st_mtime_ns + 10_000_000
            os.utime(numbered, ns=(future, future))

            superseded = validate_historical_promotion(
                root,
                "scene_0001",
                manifest,
            )

            self.assertTrue(superseded.passed, superseded.errors)
            self.assertFalse(superseded.current)

    def test_state_and_audit_only_seal_declared_historical_style_gates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest, candidate, draft = self._sealed_promotion(
                Path(temporary)
            )
            validation = HistoricalPromotionValidation(
                status="pass",
                errors=(),
                candidate_path=candidate,
                draft_path=draft,
                current=True,
            )
            steps = [
                {
                    "key": "context-trace",
                    "status": "stale",
                    "message": "active style changed",
                    "next_action": "rebuild",
                },
                {
                    "key": "roleplay-simulation",
                    "status": "missing",
                    "message": "missing",
                    "next_action": "build",
                },
                {
                    "key": "candidate-revision",
                    "status": "context_trace_stale",
                    "message": "a later character asset changed",
                    "next_action": "revise",
                },
                {
                    "key": "candidate-human-decision",
                    "status": "human_required",
                    "message": "a later asset now conflicts",
                    "next_action": "decide",
                },
            ]
            sealed_steps = preserve_historical_style_steps(
                root,
                steps,
                validation,
            )
            self.assertEqual(sealed_steps[0]["status"], "pass")
            self.assertTrue(sealed_steps[0]["historical_truth"])
            self.assertEqual(sealed_steps[1]["status"], "missing")
            self.assertEqual(sealed_steps[2]["status"], "pass")
            self.assertTrue(sealed_steps[2]["historical_truth"])
            self.assertEqual(sealed_steps[3]["status"], "pass")

            gates = [
                {
                    "key": "scene_0001:context-trace",
                    "status": "fail",
                    "severity": "blocking",
                    "message": "active style changed",
                },
                {
                    "key": "scene_0001:roleplay-simulation",
                    "status": "fail",
                    "severity": "blocking",
                    "message": "missing",
                },
            ]
            preserve_historical_style_gates(
                gates,
                "scene_0001",
                validation,
            )
            self.assertEqual(gates[0]["status"], "pass")
            self.assertEqual(gates[1]["status"], "fail")

    def test_historical_revision_context_seals_exact_scene_time_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _manifest, _candidate, draft = self._sealed_promotion(
                Path(temporary)
            )
            snapshot = build_historical_revision_context_snapshot(
                root,
                "scene_0001",
                draft,
            )

            self.assertTrue(snapshot)
            self.assertEqual(snapshot["source_draft"], "drafts/scenes/scene_0001.md")
            source_paths = historical_revision_source_paths(
                root,
                "scene_0001",
                draft,
            )
            self.assertIn(
                "drafts/promotions/scene_0001_promotion.json",
                source_paths,
            )
            self.assertEqual(
                historical_revision_context_errors(
                    root,
                    "scene_0001",
                    source_rel="drafts/scenes/scene_0001.md",
                    source_sha256=self._sha(draft),
                    snapshot=snapshot,
                ),
                [],
            )

            revision = root / "drafts/revisions/scene_0001_revision_02.md"
            revision.parent.mkdir(parents=True, exist_ok=True)
            revision.write_text("## 修订正文候选\n\n旧城的门仍然关着。又过了一刻。", encoding="utf-8")
            payload = {
                "source_candidate": "drafts/scenes/scene_0001.md",
                "source_candidate_sha256": self._sha(draft),
                "historical_context_snapshot": snapshot,
            }
            prompt = {"historical_context_snapshot": snapshot}
            self.assertEqual(
                _generation_context_issues(
                    root,
                    "scene_0001",
                    revision,
                    payload,
                    prompt,
                ),
                [],
            )

            trace = root / snapshot["context_trace"]
            trace.write_text('{"scene_id": "scene_0001", "tampered": true}\n', encoding="utf-8")
            errors = historical_revision_context_errors(
                root,
                "scene_0001",
                source_rel="drafts/scenes/scene_0001.md",
                source_sha256=self._sha(draft),
                snapshot=snapshot,
            )
            self.assertIn("historical revision source promotion is not valid", errors)

    def test_revision_promotion_blueprint_stages_historical_proof_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _manifest, old_candidate, draft = self._sealed_promotion(
                Path(temporary)
            )
            snapshot = build_historical_revision_context_snapshot(
                root,
                "scene_0001",
                draft,
            )
            revision = root / "drafts/revisions/scene_0001_revision_02.md"
            revision.parent.mkdir(parents=True, exist_ok=True)
            revision.write_text(
                "## 修订正文候选\n\n旧城的门仍然关着。门后传来第二次电流声。\n",
                encoding="utf-8",
            )
            prompt = revision.with_suffix(".prompt.json")
            prompt_payload = {"historical_context_snapshot": snapshot}
            prompt.write_text(
                json.dumps(prompt_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            revision_payload = {
                "source_candidate": draft.relative_to(root).as_posix(),
                "source_candidate_sha256": self._sha(draft),
                "historical_context_snapshot": snapshot,
                "prompt_manifest": prompt.relative_to(root).as_posix(),
            }
            revision.with_suffix(".json").write_text(
                json.dumps(revision_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            proof_paths = historical_revision_candidate_source_paths(
                root,
                "scene_0001",
                revision,
            )
            archive = _manifest["historical_evidence"]["context_archive"]
            expected = {
                draft.relative_to(root).as_posix(),
                "drafts/promotions/scene_0001_promotion.json",
                old_candidate.relative_to(root).as_posix(),
                old_candidate.with_suffix(".json").relative_to(root).as_posix(),
                old_candidate.with_suffix(".prompt.json").relative_to(root).as_posix(),
                archive["archived_context_packet"],
                archive["archived_context_trace"],
                archive["archive_manifest"],
            }
            self.assertEqual(set(proof_paths), expected)

            blueprint = task_registry._blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "promotion-manifest",
                "",
            )
            self.assertIn(
                "--candidate drafts/revisions/scene_0001_revision_02.md",
                blueprint["command"],
            )
            self.assertTrue(expected.issubset(set(blueprint["source_paths"])))
            immutable_identity_proof = {
                old_candidate.relative_to(root).as_posix(),
                old_candidate.with_suffix(".json").relative_to(root).as_posix(),
                old_candidate.with_suffix(".prompt.json").relative_to(root).as_posix(),
            }
            self.assertTrue(
                immutable_identity_proof.isdisjoint(
                    set(blueprint["expected_outputs"])
                )
            )

            sandbox = Path(temporary) / "sandbox"
            staged = set(blueprint["source_paths"])
            staged.update(
                {
                    revision.relative_to(root).as_posix(),
                    revision.with_suffix(".json").relative_to(root).as_posix(),
                    prompt.relative_to(root).as_posix(),
                }
            )
            for relative in staged:
                source = root / relative
                if not source.is_file():
                    continue
                target = sandbox / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            sandbox_payload = json.loads(
                (sandbox / revision.with_suffix(".json").relative_to(root)).read_text(
                    encoding="utf-8"
                )
            )
            sandbox_prompt = json.loads(
                (sandbox / prompt.relative_to(root)).read_text(encoding="utf-8")
            )
            self.assertEqual(
                _generation_context_issues(
                    sandbox,
                    "scene_0001",
                    sandbox / revision.relative_to(root),
                    sandbox_payload,
                    sandbox_prompt,
                ),
                [],
            )

            (sandbox / old_candidate.relative_to(root)).unlink()
            self.assertIn(
                "historical revision source promotion is not valid",
                _generation_context_issues(
                    sandbox,
                    "scene_0001",
                    sandbox / revision.relative_to(root),
                    sandbox_payload,
                    sandbox_prompt,
                ),
            )

    def test_mutable_context_refresh_does_not_change_archived_revision_truth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _manifest, _candidate, draft = self._sealed_promotion(Path(temporary))
            snapshot = build_historical_revision_context_snapshot(
                root,
                "scene_0001",
                draft,
            )
            (root / "memory/context_packets/scene_0001.md").write_text(
                "# future context\n",
                encoding="utf-8",
            )
            (root / "memory/context_packets/scene_0001.trace.json").write_text(
                '{"scene_id":"scene_0001","canon_revision":"future"}\n',
                encoding="utf-8",
            )

            self.assertEqual(
                historical_revision_context_errors(
                    root,
                    "scene_0001",
                    source_rel="drafts/scenes/scene_0001.md",
                    source_sha256=self._sha(draft),
                    snapshot=snapshot,
                ),
                [],
            )

    def test_historical_revision_keeps_scene_time_context_instead_of_rebuilding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _manifest, _candidate, draft = self._sealed_promotion(
                Path(temporary)
            )

            with patch(
                "literary_engineering_studio_engine.literary.scene.promotion."
                "revision.build_context_packet",
                side_effect=AssertionError(
                    "historical revision must not rebuild from future Canon"
                ),
            ):
                result = build_scene_revision_task(
                    root,
                    scene=Path("scenes/scene_0001.yaml"),
                    draft=draft.relative_to(root),
                )

            prompt = json.loads(
                result.prompt_manifest_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                prompt["historical_context_snapshot"]["source_draft_sha256"],
                self._sha(draft),
            )

    def test_valid_revision_seals_only_pre_generation_creative_work(self):
        steps = [
            {"key": "context-trace", "status": "stale", "next_action": "refresh"},
            {"key": "roleplay-simulation", "status": "stale", "next_action": "rerun"},
            {"key": "branch-manifest", "status": "stale", "next_action": "rerun"},
            {"key": "composition-json", "status": "stale", "next_action": "rerun"},
            {"key": "candidate-review", "status": "missing", "next_action": "review"},
            {"key": "promotion-manifest", "status": "missing", "next_action": "promote"},
        ]
        candidate = Path("C:/project/drafts/revisions/scene_0001_revision_02.md")
        with patch(
            "literary_engineering_studio_engine.workflow.historical_truth."
            "candidate_generation_gate",
            return_value={"status": "pass"},
        ):
            result = preserve_valid_revision_preparation_steps(
                Path("C:/project"),
                "scene_0001",
                candidate,
                steps,
            )

        by_key = {str(item["key"]): item for item in result}
        self.assertEqual(by_key["context-trace"]["status"], "stale")
        self.assertEqual(by_key["roleplay-simulation"]["status"], "pass")
        self.assertEqual(by_key["branch-manifest"]["status"], "pass")
        self.assertEqual(by_key["composition-json"]["status"], "pass")
        self.assertEqual(by_key["candidate-review"]["status"], "missing")
        self.assertEqual(by_key["promotion-manifest"]["status"], "missing")

    def test_legacy_snapshot_migration_preserves_exact_old_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest, candidate, draft = self._sealed_promotion(Path(temporary))
            archive = manifest["historical_evidence"]["context_archive"]
            recovery_packet = root / archive["archived_context_packet"]
            recovery_trace = root / archive["archived_context_trace"]
            evidence = dict(manifest["historical_evidence"])
            evidence["schema"] = "arcvellum/historical-scene-promotion/v1"
            evidence.pop("context_archive", None)
            evidence.pop("migration_predecessor", None)
            evidence.pop("evidence_sha256", None)
            evidence["evidence_sha256"] = self._payload_sha(evidence)
            legacy = dict(manifest)
            legacy["historical_evidence"] = evidence
            promotion_path = root / "drafts/promotions/scene_0001_promotion.json"
            promotion_path.write_text(
                json.dumps(legacy, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            snapshot = {
                "schema": "arcvellum/historical-revision-context/v1",
                "scene_id": "scene_0001",
                "source_draft": "drafts/scenes/scene_0001.md",
                "source_draft_sha256": self._sha(draft),
                "promotion_manifest": "drafts/promotions/scene_0001_promotion.json",
                "promotion_manifest_sha256": self._sha(promotion_path),
                "promotion_evidence_sha256": evidence["evidence_sha256"],
                "promoted_candidate": candidate.relative_to(root).as_posix(),
                "promoted_candidate_sha256": self._sha(candidate),
                "candidate_manifest": candidate.with_suffix(".json").relative_to(root).as_posix(),
                "candidate_manifest_sha256": self._sha(candidate.with_suffix(".json")),
                "source_prompt_manifest": candidate.with_suffix(".prompt.json").relative_to(root).as_posix(),
                "source_prompt_manifest_sha256": self._sha(candidate.with_suffix(".prompt.json")),
                "context_packet": "memory/context_packets/scene_0001.md",
                "context_packet_sha256": self._sha(recovery_packet),
                "context_trace": "memory/context_packets/scene_0001.trace.json",
                "context_trace_sha256": self._sha(recovery_trace),
            }
            snapshot["snapshot_sha256"] = self._payload_sha(snapshot)
            revision_prompt = root / "drafts/revisions/scene_0001_revision_02.prompt.json"
            revision_prompt.parent.mkdir(parents=True, exist_ok=True)
            revision_prompt.write_text(
                json.dumps({"historical_context_snapshot": snapshot}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (root / "memory/context_packets/scene_0001.md").write_text("future\n", encoding="utf-8")
            (root / "memory/context_packets/scene_0001.trace.json").write_text("{}\n", encoding="utf-8")

            result = migrate_legacy_historical_context(
                root,
                "scene_0001",
                snapshot_prompt=revision_prompt.relative_to(root),
                packet_source=recovery_packet,
                trace_source=recovery_trace,
            )

            self.assertTrue(result.receipt.is_file())
            self.assertTrue(validate_historical_promotion(root, "scene_0001").passed)
            self.assertEqual(
                historical_revision_context_errors(
                    root,
                    "scene_0001",
                    source_rel="drafts/scenes/scene_0001.md",
                    source_sha256=self._sha(draft),
                    snapshot=snapshot,
                ),
                [],
            )
            self.assertEqual(len(context_archive_output_paths(root, "scene_0001", candidate)), 3)

    def _sealed_promotion(
        self,
        base: Path,
    ) -> tuple[Path, dict[str, object], Path, Path]:
        root = base / "work"
        candidate = (
            root
            / "drafts"
            / "candidates"
            / "scene_0001-platform-agent.md"
        )
        draft = root / "drafts" / "scenes" / "scene_0001.md"
        promotion_path = (
            root
            / "drafts"
            / "promotions"
            / "scene_0001_promotion.json"
        )
        candidate.parent.mkdir(parents=True)
        draft.parent.mkdir(parents=True)
        promotion_path.parent.mkdir(parents=True)
        (root / "scenes").mkdir(parents=True, exist_ok=True)
        (root / "project.yaml").write_text(
            "project:\n  title: historical-test\n",
            encoding="utf-8",
        )
        (root / "scenes/scene_0001.yaml").write_text(
            "scene_id: scene_0001\nchapter_id: chapter_0001\n",
            encoding="utf-8",
        )
        candidate.write_text(
            "## 正文候选\n\n旧城的门仍然关着。\n",
            encoding="utf-8",
        )
        draft.write_text(
            "# 场景草稿\n\n## 正文草稿\n\n旧城的门仍然关着。\n",
            encoding="utf-8",
        )
        style_snapshot = {
            "schema": "arcvellum/style-mount-snapshot/v1",
            "style_id": "measured-prose",
            "version_id": "v-test",
            "content_hash": "a" * 64,
            "prompt_sha256": "b" * 64,
            "digest": "c" * 64,
        }
        candidate.with_suffix(".json").write_text(
            json.dumps(
                {
                    "style_mount_snapshot": style_snapshot,
                    "prompt_manifest": "drafts/candidates/scene_0001-platform-agent.prompt.json",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        context = root / "memory/context_packets/scene_0001.md"
        trace = root / "memory/context_packets/scene_0001.trace.json"
        context.parent.mkdir(parents=True, exist_ok=True)
        context.write_text("# scene-time context\n", encoding="utf-8")
        trace.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/context-trace/v2",
                    "scene_id": "scene_0001",
                    "project_revision": "project-v1",
                    "state_revision": "state-v1",
                    "canon_revision": "canon-v1",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        candidate.with_suffix(".prompt.json").write_text(
            json.dumps(
                {
                    "context": "memory/context_packets/scene_0001.md",
                    "context_trace": "memory/context_packets/scene_0001.trace.json",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        generation_gate = {"status": "pass", "candidate": "scene_0001"}
        review_gate = {"status": "pass", "candidate": "scene_0001"}
        context_archive = seal_context_archive(root, "scene_0001", candidate)
        manifest = {
            "schema": "literary-engineering-workbench/candidate-promotion/v0.1",
            "scene_id": "scene_0001",
            "candidate": candidate.relative_to(root).as_posix(),
            "candidate_sha256": self._sha(candidate),
            "draft": draft.relative_to(root).as_posix(),
            "draft_sha256": self._sha(draft),
            "candidate_generation": generation_gate,
            "candidate_review": review_gate,
            "style_mount_snapshot": style_snapshot,
            "allow_unreviewed": False,
            "allow_review_notes": False,
        }
        manifest["historical_evidence"] = (
            build_historical_promotion_evidence(
                root,
                scene_id="scene_0001",
                candidate_path=candidate,
                draft_path=draft,
                generation_gate=generation_gate,
                review_gate=review_gate,
                style_mount_snapshot=style_snapshot,
                context_archive=context_archive,
            )
        )
        promotion_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return root, manifest, candidate, draft

    def _refresh_evidence(
        self,
        root: Path,
        manifest: dict[str, object],
        candidate: Path,
        draft: Path,
    ) -> dict[str, object]:
        refreshed = dict(manifest)
        refreshed["draft_sha256"] = self._sha(draft)
        refreshed["historical_evidence"] = (
            build_historical_promotion_evidence(
                root,
                scene_id="scene_0001",
                candidate_path=candidate,
                draft_path=draft,
                generation_gate=refreshed["candidate_generation"],
                review_gate=refreshed["candidate_review"],
                style_mount_snapshot=refreshed["style_mount_snapshot"],
                context_archive=refreshed["historical_evidence"]["context_archive"],
            )
        )
        return refreshed

    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _payload_sha(payload: object) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


if __name__ == "__main__":
    unittest.main()
