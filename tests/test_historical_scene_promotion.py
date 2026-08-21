from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio_engine.literary.scene.promotion.historical import (
    HistoricalPromotionValidation,
    build_historical_promotion_evidence,
    validate_historical_promotion,
)
from literary_engineering_studio_engine.literary.scene.promotion.historical_context import (
    build_historical_revision_context_snapshot,
    historical_revision_context_errors,
    historical_revision_source_paths,
)
from literary_engineering_studio_engine.literary.scene.promotion.generation_gate import (
    _generation_context_issues,
)
from literary_engineering_studio_engine.literary.scene.promotion.revision import (
    build_scene_revision_task,
)
from literary_engineering_studio_engine.routes.scene.gates import (
    _promotion_gate_errors,
)
from literary_engineering_studio_engine.workflow.historical_truth import (
    preserve_historical_style_gates,
    preserve_historical_style_steps,
)


class HistoricalScenePromotionTests(unittest.TestCase):
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

            trace = root / "memory/context_packets/scene_0001.trace.json"
            trace.write_text('{"scene_id": "scene_0001", "tampered": true}\n', encoding="utf-8")
            errors = historical_revision_context_errors(
                root,
                "scene_0001",
                source_rel="drafts/scenes/scene_0001.md",
                source_sha256=self._sha(draft),
                snapshot=snapshot,
            )
            self.assertIn("historical revision context_trace digest mismatch", errors)

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
            )
        )
        return refreshed

    @staticmethod
    def _sha(path: Path) -> str:
        import hashlib

        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
