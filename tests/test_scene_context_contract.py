from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TASK_SCHEMA, _validate_task_payload
from literary_engineering_studio_engine.routes.scene.context_contract import (
    CONTEXT_CONTRACT_REVISION,
    CONTEXT_CONTRACT_SCHEMA,
    scene_context_contract,
)
from literary_engineering_studio_engine.tasking.package_contract import (
    _normalize_context_contract,
    task_contract_fingerprint,
)
import literary_engineering_studio_engine.task_registry as task_registry


class SceneContextContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.scene_id = "scene_0001"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write(self, relative: str, content: str = "fixture\n") -> str:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return relative

    def _common_sources(self) -> list[str]:
        return [
            self._write("scenes/scene_0001.yaml", "scene_id: scene_0001\n"),
            self._write("memory/context_packets/scene_0001.md"),
            self._write("memory/context_packets/scene_0001.trace.json", "{}\n"),
            self._write("style/creative_quality_profile.json", "{}\n"),
            self._write("style/style-profile.md"),
            self._write("plot/word_budget/word_budget.json", "{}\n"),
        ]

    def _task(
        self,
        state: str,
        *,
        sources: list[str],
        sidecar: str,
        **extra: object,
    ) -> dict[str, object]:
        punctuation = self._write("references/punctuation-standard.md")
        return {
            "current_state": state,
            "scene_id": self.scene_id,
            "agent_source_paths": sources,
            "core_managed_outputs": [sidecar],
            "required_reading": [punctuation],
            **extra,
        }

    def test_generation_contract_keeps_exact_scene_evidence_inline(self) -> None:
        sources = [
            *self._common_sources(),
            self._write("branches/scene_0001/branch_selection.md"),
            self._write("drafts/compositions/scene_0001_composition.md"),
            self._write("drafts/compositions/scene_0001_composition.json", "{}\n"),
            self._write(
                "drafts/compositions/scene_0001_composition_review.json",
                "{}\n",
            ),
            self._write("plot/chapter_obligations/chapter_0001.json", "{}\n"),
        ]
        sidecar = "drafts/candidates/scene_0001-platform-agent.agent_tasks.md"
        contract = scene_context_contract(
            self.root,
            self._task(
                "candidate-generation-provenance",
                sources=sources,
                sidecar=sidecar,
            ),
        )

        mandatory = contract["context_must_inline_paths"]
        self.assertEqual(contract["context_contract_schema"], CONTEXT_CONTRACT_SCHEMA)
        self.assertEqual(
            contract["context_contract_revision"],
            CONTEXT_CONTRACT_REVISION,
        )
        self.assertEqual(contract["context_contract_status"], "shadow-ready")
        self.assertIn("scenes/scene_0001.yaml", mandatory)
        self.assertIn("memory/context_packets/scene_0001.md", mandatory)
        self.assertIn(
            "drafts/compositions/scene_0001_composition_review.json",
            mandatory,
        )
        self.assertIn("plot/chapter_obligations/chapter_0001.json", mandatory)
        self.assertIn(sidecar, mandatory)
        self.assertIn("references/punctuation-standard.md", mandatory)
        self.assertNotIn("memory/context_packets/scene_0001.trace.json", mandatory)
        self.assertNotIn("plot/word_budget/word_budget.json", mandatory)
        self.assertEqual(len(mandatory), len(set(mandatory)))

    def test_review_contract_inlines_exact_markdown_not_large_support_files(self) -> None:
        candidate = self._write(
            "drafts/candidates/scene_0001-platform-agent.md",
            "正文\n",
        )
        sources = [
            *self._common_sources(),
            candidate,
            self._write(
                "drafts/candidates/scene_0001-platform-agent.json",
                "{}\n",
            ),
            self._write(
                "drafts/compositions/scene_0001_composition_review.json",
                "{}\n",
            ),
            self._write("branches/scene_0001/branch_selection.md"),
        ]
        sidecar = "reviews/agent/scene_0001_scene_review.agent_tasks.md"
        contract = scene_context_contract(
            self.root,
            self._task(
                "candidate-review",
                sources=sources,
                sidecar=sidecar,
            ),
        )

        mandatory = contract["context_must_inline_paths"]
        self.assertIn(candidate, mandatory)
        self.assertIn(sidecar, mandatory)
        self.assertNotIn(
            "drafts/candidates/scene_0001-platform-agent.json",
            mandatory,
        )
        self.assertNotIn("memory/context_packets/scene_0001.trace.json", mandatory)
        self.assertNotIn("plot/word_budget/word_budget.json", mandatory)

    def test_revision_contract_inlines_exact_source_and_machine_review(self) -> None:
        source = self._write(
            "drafts/candidates/scene_0001-platform-agent.md",
            "待修订正文\n",
        )
        review_json = self._write(
            "reviews/agent/scene_0001_scene_review.json",
            "{}\n",
        )
        review_markdown = self._write(
            "reviews/agent/scene_0001_scene_review.md",
        )
        sources = [
            *self._common_sources(),
            source,
            review_json,
            review_markdown,
        ]
        sidecar = "drafts/revisions/scene_0001_revision.agent_tasks.md"
        contract = scene_context_contract(
            self.root,
            self._task(
                "candidate-revision",
                sources=sources,
                sidecar=sidecar,
                revision_source=source,
            ),
        )

        mandatory = contract["context_must_inline_paths"]
        self.assertIn(source, mandatory)
        self.assertIn(review_json, mandatory)
        self.assertNotIn(review_markdown, mandatory)
        self.assertIn(sidecar, mandatory)

    def test_primary_evidence_is_fail_closed(self) -> None:
        common = self._common_sources()
        with self.assertRaisesRegex(ValueError, "task sidecar"):
            scene_context_contract(
                self.root,
                {
                    "current_state": "candidate-review",
                    "scene_id": self.scene_id,
                    "agent_source_paths": common,
                    "core_managed_outputs": [],
                    "required_reading": [
                        self._write("references/punctuation-standard.md")
                    ],
                },
            )

        sidecar = "reviews/agent/scene_0001_scene_review.agent_tasks.md"
        with self.assertRaisesRegex(ValueError, "exact candidate Markdown"):
            scene_context_contract(
                self.root,
                self._task(
                    "candidate-review",
                    sources=common,
                    sidecar=sidecar,
                ),
            )

        with self.assertRaisesRegex(ValueError, "exact revision source"):
            scene_context_contract(
                self.root,
                self._task(
                    "candidate-revision",
                    sources=common,
                    sidecar="drafts/revisions/scene_0001_revision.agent_tasks.md",
                    revision_source="drafts/candidates/missing.md",
                ),
            )

    def test_contract_fields_change_task_fingerprint(self) -> None:
        base = {
            "task_id": "scene-development-scene-0001-candidate-review",
            "route": "scene-development",
            "current_state": "candidate-review",
            "context_contract_required": True,
            "context_contract_schema": CONTEXT_CONTRACT_SCHEMA,
            "context_contract_revision": CONTEXT_CONTRACT_REVISION,
            "context_contract_status": "shadow-ready",
            "context_must_inline_paths": ["scenes/scene_0001.yaml"],
        }
        changed = {
            **base,
            "context_must_inline_paths": [
                "scenes/scene_0001.yaml",
                "memory/context_packets/scene_0001.md",
            ],
        }
        self.assertNotEqual(
            task_contract_fingerprint(base),
            task_contract_fingerprint(changed),
        )

    def test_formal_scene_task_payload_transports_contract_for_three_states(self) -> None:
        sources = [
            *self._common_sources(),
            self._write("branches/scene_0001/branch_selection.md"),
            self._write("drafts/compositions/scene_0001_composition.md"),
            self._write("drafts/compositions/scene_0001_composition.json", "{}\n"),
            self._write(
                "drafts/compositions/scene_0001_composition_review.json",
                "{}\n",
            ),
            self._write("plot/chapter_obligations/chapter_0001.json", "{}\n"),
            self._write(
                "drafts/candidates/scene_0001-platform-agent.md",
                "正文\n",
            ),
            self._write(
                "drafts/candidates/scene_0001-platform-agent.json",
                "{}\n",
            ),
            self._write(
                "reviews/agent/scene_0001_scene_review.json",
                '{"candidate":"drafts/candidates/scene_0001-platform-agent.md"}\n',
            ),
            self._write("reviews/agent/scene_0001_scene_review.md"),
            self._write("references/punctuation-standard.md"),
        ]
        self.assertTrue(sources)

        for state in (
            "candidate-generation-provenance",
            "candidate-review",
            "candidate-revision",
        ):
            with self.subTest(state=state):
                payload = task_registry._build_task_payload(
                    self.root,
                    "scene-development",
                    {
                        "scene_id": self.scene_id,
                        "scene": "scenes/scene_0001.yaml",
                        "current_step": state,
                    },
                )
                enriched = task_registry._enrich_task_payload(payload)
                self.assertTrue(enriched["context_contract_required"])
                self.assertEqual(
                    enriched["context_contract_schema"],
                    CONTEXT_CONTRACT_SCHEMA,
                )
                self.assertEqual(
                    enriched["context_contract_revision"],
                    CONTEXT_CONTRACT_REVISION,
                )
                self.assertTrue(enriched["context_must_inline_paths"])
                self.assertEqual(
                    len(enriched["context_must_inline_paths"]),
                    len(set(enriched["context_must_inline_paths"])),
                )

    def test_engine_and_studio_reject_malformed_context_sources(self) -> None:
        engine_task = {
            "context_contract_required": True,
            "context_contract_schema": CONTEXT_CONTRACT_SCHEMA,
            "context_contract_revision": CONTEXT_CONTRACT_REVISION,
            "context_contract_status": "shadow-ready",
            "context_must_inline_paths": ["scenes/scene_0001.yaml"],
            "agent_source_paths": "scenes/scene_0001.yaml",
            "required_reading": [],
        }
        with self.assertRaisesRegex(ValueError, "must be a list"):
            _normalize_context_contract(engine_task)

        studio_task = {
            "schema": TASK_SCHEMA,
            "task_id": "scene-development-scene-0001-candidate-review",
            "route": "scene-development",
            "current_state": "candidate-review",
            "task_type": "platform-agent-review",
            "required_reading": [],
            "source_paths": [],
            "expected_outputs": [],
            "validation_gates": [],
            "forbidden_shortcuts": [],
            **engine_task,
        }
        with self.assertRaisesRegex(ValueError, "must be a list"):
            _validate_task_payload(studio_task)

    def test_studio_rejects_partial_or_directory_context_contract(self) -> None:
        base = {
            "schema": TASK_SCHEMA,
            "task_id": "scene-development-scene-0001-candidate-review",
            "route": "scene-development",
            "current_state": "candidate-review",
            "task_type": "platform-agent-review",
            "required_reading": [],
            "source_paths": ["scenes/scene_0001.yaml"],
            "agent_source_paths": ["scenes/scene_0001.yaml"],
            "expected_outputs": [],
            "validation_gates": [],
            "forbidden_shortcuts": [],
        }
        with self.assertRaisesRegex(ValueError, "require.*true"):
            _validate_task_payload(
                {
                    **base,
                    "context_contract_schema": CONTEXT_CONTRACT_SCHEMA,
                }
            )

        with self.assertRaisesRegex(ValueError, "identify a file"):
            _validate_task_payload(
                {
                    **base,
                    "agent_source_paths": ["scenes/"],
                    "context_contract_required": True,
                    "context_contract_schema": CONTEXT_CONTRACT_SCHEMA,
                    "context_contract_revision": CONTEXT_CONTRACT_REVISION,
                    "context_contract_status": "shadow-ready",
                    "context_must_inline_paths": ["scenes/"],
                }
            )


if __name__ == "__main__":
    unittest.main()
