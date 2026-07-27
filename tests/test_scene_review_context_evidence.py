from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import (
    load_task_package,
    normalize_relative_path,
)
from literary_engineering_studio.protocols.review_context import (
    validate_materialized_review_context,
    validate_optional_review_context_declaration,
)
from literary_engineering_studio.runtime.context_budget import (
    resolve_task_context_budget,
)
from literary_engineering_studio.runtime.sandbox import stage_task
from literary_engineering_studio_engine.literary.review.context_evidence import (
    REVIEW_CONTEXT_SCHEMA,
    scene_review_context_declaration,
    scene_review_context_path,
)
from literary_engineering_studio_engine.prompting.platform_tasks import (
    write_platform_scene_review_task,
)
from literary_engineering_studio_engine.tasking import registry
from literary_engineering_studio_engine.tasking.paths import (
    relative_path,
    task_json_path,
    task_markdown_path,
)


class SceneReviewContextEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "project.yaml").write_text(
            "project:\n  title: 潮线\n  target_words: 0\n",
            encoding="utf-8",
        )
        self.scene = self.root / "scenes" / "scene_0001.yaml"
        self.scene.parent.mkdir(parents=True)
        self.scene.write_text(
            "scene_id: scene_0001\nchapter_id: chapter_0001\n",
            encoding="utf-8",
        )
        self.candidate = (
            self.root
            / "drafts"
            / "candidates"
            / "scene_0001-platform-agent.md"
        )
        self.candidate.parent.mkdir(parents=True)
        self.candidate.write_text(
            "# 第一场\n\n潮水退下去，林正看见石阶上的信。\n",
            encoding="utf-8",
        )
        self.result = write_platform_scene_review_task(
            self.root,
            scene_path=self.scene,
            draft_path=self.candidate,
            materialization_scope="scene",
        )
        self.compact = scene_review_context_path(
            self.result.expected_json_path
        )
        self.payload = self._task_payload()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _task_payload(self) -> dict[str, object]:
        candidate = self.candidate.relative_to(self.root).as_posix()
        sidecar = self.result.task_path.relative_to(self.root).as_posix()
        compact = self.compact.relative_to(self.root).as_posix()
        review_json = (
            self.result.expected_json_path.relative_to(self.root).as_posix()
        )
        report = (
            self.result.expected_report_path.relative_to(self.root).as_posix()
        )
        declaration = scene_review_context_declaration(
            scene_id="scene_0001",
            candidate_path=candidate,
            artifact_path=compact,
            sidecar_path=sidecar,
            review_json_path=review_json,
            review_report_path=report,
        )
        return {
            "current_state": "candidate-review",
            "context_contract_revision": "scene-v2",
            "scene_id": "scene_0001",
            "agent_source_paths": [candidate],
            "context_must_inline_paths": [candidate, compact],
            "context_exact_on_demand_paths": [sidecar],
            "expected_outputs": [
                review_json,
                report,
                sidecar,
                compact,
            ],
            "core_managed_outputs": [sidecar, compact],
            "context_evidence_contract": declaration,
        }

    def test_compact_evidence_is_digest_bound_and_studio_validates_it(
        self,
    ) -> None:
        artifact = json.loads(self.compact.read_text(encoding="utf-8"))

        self.assertEqual(artifact["schema"], REVIEW_CONTEXT_SCHEMA)
        self.assertLess(
            self.compact.stat().st_size,
            self.result.task_path.stat().st_size,
        )
        self.assertEqual(
            artifact["candidate"]["sha256"],
            hashlib.sha256(self.candidate.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            artifact["full_sidecar"]["sha256"],
            hashlib.sha256(self.result.task_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            artifact["full_sidecar"]["visibility"],
            "exact_on_demand",
        )
        validate_optional_review_context_declaration(
            self.payload,
            normalize_path=normalize_relative_path,
        )
        validate_materialized_review_context(
            self.payload,
            self.root,
            normalize_path=normalize_relative_path,
            require=True,
        )

    def test_candidate_tampering_fails_closed(self) -> None:
        self.candidate.write_text("被替换的候选\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "candidate digest"):
            validate_materialized_review_context(
                self.payload,
                self.root,
                normalize_path=normalize_relative_path,
                require=True,
            )

    def test_sidecar_tampering_fails_closed(self) -> None:
        self.result.task_path.write_text(
            self.result.task_path.read_text(encoding="utf-8") + "\n篡改\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "sidecar digest"):
            validate_materialized_review_context(
                self.payload,
                self.root,
                normalize_path=normalize_relative_path,
                require=True,
            )

    def test_embedded_schema_tampering_fails_closed(self) -> None:
        artifact = json.loads(self.compact.read_text(encoding="utf-8"))
        artifact["output_schema"]["contract"]["required"].append(
            "invented_field"
        )
        self.compact.write_text(
            json.dumps(artifact, ensure_ascii=False),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "schema digest"):
            validate_materialized_review_context(
                self.payload,
                self.root,
                normalize_path=normalize_relative_path,
                require=True,
            )

    def test_bounded_review_rejects_legacy_task_without_compact_contract(
        self,
    ) -> None:
        legacy = {
            key: value
            for key, value in self.payload.items()
            if key != "context_evidence_contract"
        }

        with self.assertRaisesRegex(ValueError, "requires compact"):
            validate_materialized_review_context(
                legacy,
                self.root,
                normalize_path=normalize_relative_path,
                require=True,
            )

    def test_formal_bounded_sandbox_inlines_compact_and_defers_sidecar(
        self,
    ) -> None:
        payload = registry._enrich_task_payload(
            registry._build_task_payload(
                self.root,
                "scene-development",
                {
                    "scene_id": "scene_0001",
                    "scene": "scenes/scene_0001.yaml",
                    "current_step": "candidate-review",
                },
            )
        )
        task_json = task_json_path(self.root, str(payload["task_id"]))
        task_markdown = task_markdown_path(
            self.root,
            str(payload["task_id"]),
        )
        payload["task_json"] = relative_path(task_json, self.root)
        payload["task_markdown"] = relative_path(
            task_markdown,
            self.root,
        )
        task_json.parent.mkdir(parents=True, exist_ok=True)
        task_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        task_markdown.write_text(
            registry._render_task_markdown(payload, self.root),
            encoding="utf-8",
        )
        task = load_task_package(self.root, task_json)
        budget = resolve_task_context_budget(
            task,
            {"context_budget": {"mode": "bounded"}},
        )
        sandbox = stage_task(
            task,
            self.root / ".runs",
            runtime="test",
            run_id="bounded-review",
            context_budget=budget,
        )
        task_context = json.loads(
            (sandbox.workspace / "TASK_CONTEXT.json").read_text(
                encoding="utf-8"
            )
        )
        execution = task_context["execution_context"]
        compact = self.compact.relative_to(self.root).as_posix()
        sidecar = self.result.task_path.relative_to(
            self.root
        ).as_posix()

        self.assertIn(compact, execution["must_inline"])
        self.assertIn(sidecar, execution["exact_on_demand"])
        self.assertFalse(
            set(execution["must_inline"])
            & set(execution["exact_on_demand"])
        )
        self.assertFalse(
            set(payload["context_must_inline_paths"])
            - set(execution["must_inline"])
        )
        manifest = json.loads(
            sandbox.manifest_path.read_text(encoding="utf-8")
        )
        ledger = json.loads(
            (sandbox.run_root / "context-ledger.json").read_text(
                encoding="utf-8"
            )
        )
        digest = execution["context_digest"]
        self.assertEqual(
            manifest["execution_context"]["digest"],
            digest,
        )
        self.assertEqual(ledger["execution_context_digest"], digest)
        self.assertIn(digest, sandbox.prompt_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
