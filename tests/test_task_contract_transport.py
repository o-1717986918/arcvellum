from pathlib import Path
import json
from importlib import import_module
import re
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.runtime.task_program import build_task_context
from literary_engineering_studio_engine.agent_task_status import build_agent_task_status, build_route_audit
import literary_engineering_studio_engine.agent_task_status as agent_task_status
from literary_engineering_studio_engine.workflow.audit.task_status import _route_summary
import literary_engineering_studio_engine.agent_task_inventory as agent_task_inventory
import literary_engineering_studio_engine.route_audit_common as route_audit_common
import literary_engineering_studio_engine.asset_route as asset_route
import literary_engineering_studio_engine.export_release_route as export_release_route
import literary_engineering_studio_engine.task_registry as task_registry
from literary_engineering_studio_engine.platform_agent_tasks import write_project_seed_asset_tasks
from literary_engineering_studio_engine.routes.scene.definition import _agent_reading_paths
from literary_engineering_studio_engine.task_registry import _enrich_task_payload, _render_task_markdown, complete_task, submit_task
from tests.scene_lifecycle_support import prepare_promotable_candidate


class TaskContractTransportTests(unittest.TestCase):
    def test_task_package_omits_unconsumed_transition_hints(self):
        task = _enrich_task_payload(
            {
                "task_id": "scene-development-scene_0001-context-packet",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "context-packet",
                "task_type": "deterministic-cli",
                "prompt_asset_id": "route.scene-development.context-packet.v1",
                "expected_outputs": [],
                "next_allowed_states": ["roleplay-simulation"],
            }
        )

        self.assertNotIn("next_allowed_states", task)

    def test_route_summary_counts_failed_gates_separately_from_gate_inventory(self):
        summary = _route_summary(
            "scene-development",
            [],
            [
                {"key": "sealed", "status": "pass", "severity": "blocking", "message": "ok"},
                {"key": "failed", "status": "fail", "severity": "blocking", "message": "bad"},
                {"key": "warning", "status": "fail", "severity": "warning", "message": "risk"},
                {"key": "info", "status": "pass", "severity": "info", "message": "ok"},
            ],
        )

        self.assertEqual(summary["blocking_count"], 1)
        self.assertEqual(summary["warning_count"], 1)
        self.assertEqual(summary["blocking_gate_count"], 2)
        self.assertEqual(summary["warning_gate_count"], 1)

    def test_agent_task_sidecars_are_always_studio_managed(self):
        sidecar = "plot/chapter_obligations/chapter_0001.agent_tasks.md"
        task = _enrich_task_payload(
            {
                "task_id": "scene-development-scene_0001-reader-experience-contract",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "reader-experience-contract",
                "task_type": "deterministic-cli-plus-platform-review",
                "prompt_asset_id": "route.longform-planning.reader-experience.v1",
                "expected_outputs": [
                    "plot/chapter_obligations/chapter_0001.json",
                    sidecar,
                    "plot/chapter_obligations/chapter_0001.agent_completion.json",
                ],
            }
        )

        self.assertEqual(task["core_managed_outputs"], [sidecar])
        contracts = {item["path"]: item for item in task["output_contracts"]}
        self.assertEqual(contracts[sidecar]["kind"], "deterministic")
        self.assertEqual(contracts[sidecar]["writeback_policy"], "automatic")

    def test_reader_experience_agent_context_is_current_chapter_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, body in (
                ("project.yaml", "project:\n  title: 潮线\n"),
                ("plot/word_budget/word_budget.json", "{}\n"),
                ("scenes/scene_0001.yaml", "scene_id: scene_0001\nchapter_id: chapter_0001\n"),
                ("scenes/scene_0002.yaml", "scene_id: scene_0002\nchapter_id: chapter_0001\n"),
                ("scenes/scene_0003.yaml", "scene_id: scene_0003\nchapter_id: chapter_0002\n"),
                ("memory/context_packets/scene_0001.md", "不应进入章节契约提示词\n"),
                ("canon/world_rules.yaml", "rules: []\n"),
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")

            selected = _agent_reading_paths(
                root,
                [
                    "project.yaml",
                    "scenes",
                    "plot/word_budget/word_budget.json",
                    "plot/chapter_obligations/",
                    "memory/context_packets/scene_0001.md",
                    "canon/world_rules.yaml",
                ],
                current_state="reader-experience-contract",
                scene_id="scene_0001",
            )

            self.assertIn("scenes/scene_0001.yaml", selected)
            self.assertIn("scenes/scene_0002.yaml", selected)
            self.assertIn("plot/chapter_obligations/chapter_0001.json", selected)
            self.assertNotIn("scenes/scene_0003.yaml", selected)
            self.assertNotIn("plot/chapter_obligations/chapter_0001.md", selected)
            self.assertNotIn("memory/context_packets/scene_0001.md", selected)
            self.assertNotIn("canon/world_rules.yaml", selected)

            blueprint = task_registry._blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "reader-experience-contract",
                "",
            )
            self.assertIn(
                "plot/chapter_obligations/chapter_0001.md",
                blueprint["core_managed_outputs"],
            )

    def test_project_asset_intake_is_a_concrete_deterministic_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            results = write_project_seed_asset_tasks(root)

            self.assertEqual(len(results), 2)
            self.assertTrue((root / "canon/candidates/world_rules/world-foundation.agent_tasks.md").is_file())
            self.assertTrue((root / "characters/candidates/protagonist-foundation.agent_tasks.md").is_file())
            blueprint = asset_route._asset_blueprint_for_state(
                root,
                "asset-intake",
                "",
                "",
                "asset-intake",
                "",
            )
            self.assertEqual(
                blueprint["command"],
                "python -m literary_engineering_studio_engine seed-project-assets <project>",
            )
            self.assertNotIn("<type>", blueprint["command"])
            self.assertEqual(len(blueprint["expected_outputs"]), 2)

    def test_asset_promotion_declares_the_formal_asset_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "characters/candidates/protagonist-foundation.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(
                json.dumps(
                    {
                        "candidate_id": "protagonist-foundation",
                        "asset_type": "character",
                        "character_id": "protagonist-foundation",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            blueprint = asset_route._asset_blueprint_for_state(
                root,
                "protagonist-foundation",
                "character",
                candidate.relative_to(root).as_posix(),
                "asset-promotion",
                "",
            )
            self.assertIn("characters/protagonist-foundation.yaml", blueprint["expected_outputs"])

    def test_export_and_publish_declare_every_deterministic_delivery_write(self):
        root = Path(".").resolve()
        export = export_release_route._export_release_blueprint_for_state(
            root,
            "chapter_0001",
            "export-package",
            "",
        )
        self.assertEqual(len(export["expected_outputs"]), 13)
        self.assertIn("exports/chapter_0001/chapter_0001_novel.docx", export["expected_outputs"])
        self.assertIn("exports/chapter_0001/chapter_0001_novel.layout.json", export["expected_outputs"])
        self.assertIn("exports/chapter_0001/chapter_0001_novel.inspection.json", export["expected_outputs"])

        publish = export_release_route._export_release_blueprint_for_state(
            root,
            "chapter_0001",
            "publish-release",
            "",
        )
        self.assertIn("releases/chapter_0001/formal-release/chapter_0001_novel.md", publish["expected_outputs"])
        self.assertIn("releases/chapter_0001/formal-release/chapter_0001_novel.docx", publish["expected_outputs"])
        self.assertIn("reviews/canon_lint.json", publish["expected_outputs"])
        self.assertIn("canon", publish["source_paths"])
        self.assertIn("characters", publish["source_paths"])
        self.assertIn("scenes", publish["source_paths"])
        self.assertIn("plot/chapters/chapter_0001.json", publish["source_paths"])
        self.assertIn("drafts/chapters/chapter_0001.md", publish["source_paths"])
        self.assertIn("exports/chapter_0001", publish["source_paths"])
        self.assertIn("style", publish["source_paths"])

    def test_fresh_scene_blueprint_does_not_require_future_review_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )

            blueprint = task_registry._blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "context-packet",
                "",
            )

            self.assertEqual(blueprint["task_type"], "deterministic-cli")
            self.assertIn("memory/context_packets/scene_0001.md", blueprint["expected_outputs"])
            self.assertIn("memory/index.json", blueprint["expected_outputs"])

    def test_missing_scene_characters_are_prepared_before_candidate_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\nparticipants: [林昭, 林正]\n",
                encoding="utf-8",
            )
            (root / "characters").mkdir()
            (root / "characters" / "hero.yaml").write_text("name: 林昭\n", encoding="utf-8")

            blueprint = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "scene-character-asset-tasks", ""
            )

            self.assertIn("prepare-scene-character-assets", blueprint["command"])
            self.assertEqual(
                blueprint["expected_outputs"],
                ["characters/candidates/scene-0001-林正.agent_tasks.md"],
            )
            self.assertEqual(blueprint["scene_character_assets"][0]["name"], "林正")
            payload = task_registry._build_task_payload(
                root,
                "scene-development",
                {
                    "scene_id": "scene_0001",
                    "scene": "scenes/scene_0001.yaml",
                    "current_step": "scene-character-asset-tasks",
                },
            )
            self.assertIn(
                "characters/candidates/scene-0001-林正.agent_tasks.md",
                payload["expected_outputs"],
            )

            prose = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "candidate-generation-provenance", ""
            )
            self.assertNotIn("characters/candidates/scene-0001-林正.json", prose["expected_outputs"])
            self.assertNotIn("scene_character_assets", prose)

    def test_candidate_generation_writes_to_the_current_revision_candidate(self):
        """A resumed route must never let the CLI create an untracked default candidate."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")
            revision = root / "drafts" / "revisions" / "scene_0001_revision.md"
            revision.parent.mkdir(parents=True)
            revision.write_text("旧修订候选\n", encoding="utf-8")

            blueprint = task_registry._blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "candidate-generation-provenance",
                "",
            )

            self.assertIn("--out drafts/revisions/scene_0001_revision.md", blueprint["command"])
            self.assertIn("drafts/revisions/scene_0001_revision.prompt.json", blueprint["expected_outputs"])

    def test_candidate_review_transports_its_schema_and_protects_the_cli_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")

            blueprint = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "candidate-review", ""
            )

            self.assertEqual(blueprint["candidate"], "drafts/candidates/scene_0001-platform-agent.md")
            self.assertIn("--materialization-scope scene", blueprint["command"])
            self.assertIn("--draft drafts/candidates/scene_0001-platform-agent.md", blueprint["command"])
            self.assertNotIn(" --out ", blueprint["command"])
            self.assertNotIn("schemas/agent_outputs/scene_review.v1.schema.json", blueprint["source_paths"])
            self.assertIn(
                "reviews/agent/scene_0001_scene_review.agent_tasks.md",
                blueprint["core_managed_outputs"],
            )
            self.assertIn(
                "reviews/agent/scene_0001_scene_review.context.json",
                blueprint["core_managed_outputs"],
            )

            revision = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "candidate-revision", ""
            )
            self.assertIn("drafts/revisions/scene_0001_revision.prompt.json", revision["core_managed_outputs"])
            self.assertIn("drafts/revisions/scene_0001_revision.agent_tasks.md", revision["core_managed_outputs"])
            self.assertIn("plot/chapter_obligations/chapter_0001.json", revision["source_paths"])
            self.assertIn("plot/rhythm_plan.json", revision["source_paths"])

            decision = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "candidate-human-decision", ""
            )
            self.assertEqual(decision["task_type"], "human-approval-boundary")
            self.assertEqual(decision["expected_outputs"], [])
            self.assertIn("candidate_sha256", " ".join(decision["hard_constraints"]))

    def test_scene_deterministic_handoffs_transport_upstream_completion_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 潮线\n", encoding="utf-8")
            (root / "workflow").mkdir(parents=True)
            (root / "workflow" / "longform_materialization.json").write_text(
                '{"status": "materialized", "scene_count": 1}\n', encoding="utf-8"
            )
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )

            branch = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "branch-manifest", ""
            )
            self.assertIn(
                "branches/scene_0001/roleplay_simulation.agent_tasks.md",
                branch["source_paths"],
            )
            self.assertIn(
                "branches/scene_0001/roleplay_simulation.agent_completion.json",
                branch["source_paths"],
            )
            self.assertIn(
                "branches/scene_0001/branch_selection.md",
                branch["expected_outputs"],
            )

            composition = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "composition-json", ""
            )
            self.assertIn(
                "branches/scene_0001/branch_manifest.agent_completion.json",
                composition["source_paths"],
            )
            self.assertIn("project.yaml", composition["source_paths"])

            rhythm = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "scene-rhythm-contract", ""
            )
            self.assertEqual(rhythm["expected_outputs"], ["scenes/scene_0001.yaml"])
            self.assertIn("narrative rhythm/bridge contract passes", rhythm["validation_gates"])

            generation = task_registry._blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "candidate-generation-provenance",
                "",
            )
            self.assertIn("--materialization-scope scene", generation["command"])
            for relative in (
                "branches/scene_0001/roleplay_simulation.agent_completion.json",
                "branches/scene_0001/branch_manifest.agent_completion.json",
                "drafts/compositions/scene_0001_composition.agent_completion.json",
                "workflow/longform_materialization.json",
                "plot/word_budget/word_budget.agent_tasks.md",
                "plot/word_budget/word_budget.agent_completion.json",
                "reviews/word_budget/word_budget_review.md",
            ):
                self.assertIn(relative, generation["source_paths"])

    def test_composition_gate_reads_ready_flag_from_flow_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps(
                    {
                        "selection_source": "selection",
                        "selected_branch": "branch_a",
                        "flow_gate": {"ready_for_generation": True},
                        "formal_cli_provenance": {
                            "created_by": "compose-scene",
                            "agent_tasks_requested": True,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            self.assertEqual(task_registry._composition_gate_errors(root, "scene_0001"), [])

    def test_scene_blueprint_reads_an_existing_review_when_preparing_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")
            review = root / "reviews" / "agent" / "scene_0001_scene_review.json"
            review.parent.mkdir(parents=True)
            review.write_text(
                json.dumps({"candidate": "drafts/candidates/scene_0001-platform-agent.md"}),
                encoding="utf-8",
            )

            blueprint = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "candidate-revision", ""
            )

            self.assertIn("drafts/candidates/scene_0001-platform-agent.md", blueprint["source_paths"])

    def test_revision_task_contract_accepts_an_existing_revision_as_exact_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text(
                "project:\n  title: 潮线\n",
                encoding="utf-8",
            )
            scene = root / "scenes" / "scene_0001.yaml"
            revision = root / "drafts" / "revisions" / "scene_0001_revision.md"
            review = root / "reviews" / "agent" / "scene_0001_scene_review.json"
            scene.parent.mkdir(parents=True)
            revision.parent.mkdir(parents=True)
            review.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )
            revision.write_text("上一版修订候选", encoding="utf-8")
            review.write_text(
                json.dumps(
                    {
                        "candidate": revision.relative_to(root).as_posix(),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            review.with_suffix(".md").write_text("审查证据", encoding="utf-8")

            payload = task_registry._build_task_payload(
                root,
                "scene-development",
                {
                    "scene_id": "scene_0001",
                    "scene": "scenes/scene_0001.yaml",
                    "current_step": "candidate-revision",
                    "next_action": "",
                },
            )

            exact_source = revision.relative_to(root).as_posix()
            self.assertEqual(payload["revision_source"], exact_source)
            self.assertEqual(
                payload["candidate"],
                "drafts/revisions/scene_0001_revision_02.md",
            )
            self.assertIn(
                "--out drafts/revisions/scene_0001_revision_02.md",
                payload["command"],
            )
            self.assertIn(exact_source, payload["agent_source_paths"])
            self.assertIn(exact_source, payload["context_must_inline_paths"])

    def test_continuity_apply_stages_the_promoted_draft_needed_for_digest_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")

            blueprint = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "continuity-ledger-apply", ""
            )

            self.assertIn("drafts/scenes/scene_0001.md", blueprint["source_paths"])
            self.assertIn("plot/ledger_deltas/scene_0001.json", blueprint["source_paths"])
            self.assertIn("reviews/continuity/scene_0001_ledger_review.json", blueprint["source_paths"])

    def test_revision_promotion_targets_exact_current_candidate_and_overwrites_formal_draft(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )
            revision = root / "drafts" / "revisions" / "scene_0001_revision.md"
            revision.parent.mkdir(parents=True)
            revision.write_text("## 正文候选\n\n修订正文。\n", encoding="utf-8")
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n旧正文。\n", encoding="utf-8")

            blueprint = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "promotion-manifest", ""
            )

            self.assertIn("--candidate drafts/revisions/scene_0001_revision.md", blueprint["command"])
            self.assertIn("--overwrite", blueprint["command"])
            self.assertIn("drafts/revisions/scene_0001_revision.agent_completion.json", blueprint["source_paths"])

    def test_promotion_declares_content_addressed_context_archive_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _candidate = prepare_promotable_candidate(Path(temporary))

            blueprint = task_registry._blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "promotion-manifest",
                "",
            )

            archive_outputs = [
                path
                for path in blueprint["expected_outputs"]
                if path.startswith("memory/context_history/scene_0001/")
            ]
            self.assertEqual(len(archive_outputs), 3)
            self.assertTrue(any(path.endswith("/context.md") for path in archive_outputs))
            self.assertTrue(any(path.endswith("/context.trace.json") for path in archive_outputs))
            self.assertTrue(any(path.endswith("/archive.json") for path in archive_outputs))

    def test_scene_task_selection_uses_incremental_state_instead_of_full_route_scan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            scenes = root / "scenes"
            scenes.mkdir()
            for index in range(1, 4):
                (scenes / f"scene_{index:04d}.yaml").write_text(
                    f"scene_id: scene_{index:04d}\nchapter_id: chapter_0001\n",
                    encoding="utf-8",
                )

            with patch.object(task_registry, "build_workflow_state", side_effect=AssertionError("full scan used")):
                result = task_registry.issue_next_task(root, route="scene-development")

            self.assertEqual(result.scene_id, "scene_0001")
            self.assertEqual(result.current_state, "context-packet")

    def test_every_declared_task_type_has_an_exact_execution_contract(self):
        route_modules = [
            "scene_development_route.py",
            "longform_planning_route.py",
            "source_ingest_route.py",
            "style_engineering_route.py",
            "asset_route.py",
            "review_audit_route.py",
            "export_release_route.py",
        ]
        source = "\n".join(
            Path(import_module(f"literary_engineering_studio_engine.{name.removesuffix('.py')}").__file__).read_text(encoding="utf-8")
            for name in route_modules
        )
        declared = set(re.findall(r'"task_type"\s*:\s*"([^"]+)"', source))
        self.assertTrue(declared)
        self.assertEqual(declared - set(task_registry.TASK_TYPE_EXECUTION), set())

    def test_exact_prompt_metadata_and_explicit_contract_reach_agent_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _enrich_task_payload(
                {
                    "schema": "literary-engineering-workbench/agent-task/v1",
                    "task_id": "scene-development-scene_0001-candidate-generation-provenance",
                    "status": "issued",
                    "route": "scene-development",
                    "scene_id": "scene_0001",
                    "current_state": "candidate-generation-provenance",
                    "task_type": "main-platform-agent-prose",
                    "prompt_asset_id": "route.scene-development.prose.generate.v1",
                    "command": "",
                    "required_reading": [],
                    "source_paths": ["scenes/scene_0001.yaml"],
                    "expected_outputs": [
                        "drafts/candidates/scene_0001-platform-agent.md",
                        "drafts/candidates/scene_0001-platform-agent.agent_completion.json",
                    ],
                    "hard_constraints": [],
                    "style_constraints": [],
                    "validation_gates": [],
                    "forbidden_shortcuts": [],
                    "submission_command": "lew task-submit",
                    "completion_command": "lew task-complete",
                }
            )

            prompt_asset = task["prompt_asset"]
            self.assertEqual(prompt_asset["resolved_id"], "route.scene-development.prose.generate.v1")
            self.assertTrue(prompt_asset["exact"])
            self.assertTrue(prompt_asset["required_inputs"])
            self.assertTrue(prompt_asset["hard_constraints"])
            self.assertTrue(prompt_asset["review_requirements"])
            self.assertTrue(prompt_asset["forbidden_shortcuts"])
            self.assertTrue(prompt_asset["body"])
            self.assertEqual(
                prompt_asset["output_contract"],
                [
                    "Only create the files listed under Allowed Outputs / Expected Outputs for this task. "
                    "Studio owns CLI-protected prompt sidecars, lifecycle receipts, and other system-managed files; "
                    "do not create, complete, or replace them."
                ],
            )
            self.assertEqual(task["execution_policy"], "agent-required")
            self.assertEqual(task["agent_role"], "main-creative-agent")
            self.assertEqual(task["human_gate"]["source"], "task-registry")
            self.assertEqual(
                task["runtime_capabilities_required"],
                ["read-task-sources", "write-expected-outputs"],
            )
            self.assertEqual(task["output_contracts"][0]["writeback_policy"], "preview-required")
            self.assertEqual(task["output_contracts"][1]["kind"], "completion-evidence")

            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            task_json = task_dir / f"{task['task_id']}.task.json"
            task_markdown = task_dir / f"{task['task_id']}.agent_tasks.md"
            task["task_markdown"] = task_markdown.relative_to(root).as_posix()
            task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
            task_markdown.write_text(_render_task_markdown(task, root), encoding="utf-8")

            rendered = task_markdown.read_text(encoding="utf-8")
            for heading in (
                "### Prompt Required Inputs",
                "### Prompt Context Groups",
                "### Prompt Hard Constraints",
                "### Prompt Style Constraints",
                "### Prompt Output Contract",
                "### Prompt Review Requirements",
                "### Prompt Forbidden Shortcuts",
                "### Prompt Body",
            ):
                self.assertIn(heading, rendered)
            self.assertIn("Studio owns CLI-protected prompt sidecars", rendered)
            self.assertNotIn("Write candidate Markdown, candidate manifest JSON, and completion marker", rendered)
            loaded = load_task_package(root, task_json)
            self.assertFalse(loaded.execution_contract.compatibility_derived)
            self.assertEqual(loaded.execution_contract.agent_role, "main-creative-agent")

    def test_human_boundary_is_explicit_and_has_no_runtime_capabilities(self):
        task = _enrich_task_payload(
            {
                "task_id": "export-release-chapter_0001-release-approval",
                "route": "export-and-release",
                "scene_id": "chapter_0001",
                "current_state": "release-approval",
                "task_type": "human-approval-boundary",
                "prompt_asset_id": "route.export-release.approval.v1",
                "expected_outputs": ["workflow/approvals/index.jsonl"],
            }
        )
        self.assertEqual(task["execution_policy"], "human-required")
        self.assertEqual(task["agent_role"], "human-decision")
        self.assertEqual(task["human_gate"]["reasons"], ["release-approval"])
        self.assertEqual(task["runtime_capabilities_required"], [])
        self.assertEqual(task["output_contracts"][0]["writeback_policy"], "approval-required")
        self.assertEqual(task["submission_command"], "")
        self.assertEqual(task["completion_command"], "")

    def test_route_diagnostic_boundary_cannot_enter_agent_runtime(self):
        task = _enrich_task_payload(
            {
                "task_id": "scene-development-scene_0001-route-diagnostic",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "unsupported-state",
                "task_type": "route-diagnostic-boundary",
                "prompt_asset_id": "route.scene-development.repair.v1",
                "expected_outputs": [],
            }
        )
        self.assertEqual(task["execution_policy"], "human-required")
        self.assertEqual(task["agent_role"], "maintenance-decision")
        self.assertEqual(task["runtime_capabilities_required"], [])
        self.assertEqual(task["submission_command"], "")
        self.assertEqual(task["completion_command"], "")
        self.assertNotIn("manual-route-repair", task_registry.TASK_TYPE_EXECUTION)

    def test_human_boundary_markdown_never_instructs_an_agent_to_submit_or_complete(self):
        task = _enrich_task_payload(
            {
                "task_id": "scene-development-scene_0001-candidate-human-decision",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "candidate-human-decision",
                "task_type": "human-approval-boundary",
                "prompt_asset_id": "route.scene-development.cross-asset-alignment.v1",
                "expected_outputs": [],
            }
        )
        rendered = _render_task_markdown(task, Path("."))
        self.assertIn("## Human Decision Boundary", rendered)
        self.assertNotIn("## Agent Execution", rendered)
        self.assertNotIn("task-submit", rendered)
        self.assertNotIn("task-complete", rendered)
        self.assertNotIn(".agent_completion.json", rendered)

    def test_agent_task_markdown_keeps_lifecycle_receipts_out_of_agent_outputs(self):
        task = _enrich_task_payload(
            {
                "task_id": "scene-development-scene_0001-composition-agent-task",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "composition-agent-task",
                "task_type": "platform-agent-judgment",
                "prompt_asset_id": "route.scene-development.composition.review.execute.v1",
                "expected_outputs": [
                    "drafts/compositions/scene_0001_composition_review.json",
                    "drafts/compositions/scene_0001_composition.agent_completion.json",
                ],
            }
        )

        rendered = _render_task_markdown(task, Path("."))

        expected_section = rendered.split("## Expected Outputs", 1)[1].split("## Studio Lifecycle Receipt", 1)[0]
        self.assertIn("scene_0001_composition_review.json", expected_section)
        self.assertNotIn("agent_completion.json", expected_section)
        self.assertIn("## Studio Lifecycle Receipt", rendered)
        self.assertIn("Studio Worker 在 Agent 产物通过确定性预检后自动写入", rendered)

    def test_agent_task_markdown_only_exposes_curated_agent_sources(self):
        task = _enrich_task_payload(
            {
                "task_id": "scene-development-scene_0001-candidate-review",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "candidate-review",
                "task_type": "platform-agent-review",
                "prompt_asset_id": "route.scene-development.agent-review.v1",
                "source_paths": ["scenes/scene_0001.yaml", "canon", "characters", "style"],
                "agent_source_paths": ["scenes/scene_0001.yaml", "drafts/candidates/scene_0001-platform-agent.md"],
                "expected_outputs": ["reviews/agent/scene_0001_scene_review.json"],
            }
        )

        rendered = _render_task_markdown(task, Path("."))
        source_section = rendered.split("## Source Boundary", 1)[0]

        self.assertIn("## Agent Source Artifacts", rendered)
        self.assertIn("drafts/candidates/scene_0001-platform-agent.md", source_section)
        self.assertNotIn("- `canon`", source_section)
        self.assertIn("不得遍历目录、搜索项目或读取未列路径", rendered)

    def test_agent_task_markdown_omits_unstaged_operating_manuals(self):
        task = _enrich_task_payload(
            {
                "task_id": "scene-development-scene_0001-candidate-revision",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "candidate-revision",
                "task_type": "platform-agent-revision",
                "prompt_asset_id": "route.scene-development.revision.v1",
                "required_reading": ["SKILL.md", "AGENTS.md", "references/punctuation-standard.md"],
                "agent_source_paths": ["drafts/candidates/scene_0001-platform-agent.md"],
                "expected_outputs": ["drafts/revisions/scene_0001_revision.md"],
            }
        )

        rendered = _render_task_markdown(task, Path("."))

        self.assertNotIn("- `SKILL.md`", rendered)
        self.assertNotIn("- `AGENTS.md`", rendered)
        self.assertIn("- `references/punctuation-standard.md`", rendered)

    def test_human_decision_task_is_not_counted_as_an_unfinished_agent_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            human_task = task_dir / "scene-human-decision.agent_tasks.md"
            human_task.write_text("- execution_policy: `human-required`\n", encoding="utf-8")
            (task_dir / "scene-human-decision.task.json").write_text(
                json.dumps({"execution_policy": "human-required"}), encoding="utf-8"
            )
            agent_task = task_dir / "scene-agent.agent_tasks.md"
            agent_task.write_text(
                "- route: `scene-development`\n- 创建或覆盖 `drafts/candidates/scene_0001.md`\n",
                encoding="utf-8",
            )
            (task_dir / "scene-agent.task.json").write_text(
                json.dumps({"route": "scene-development", "execution_policy": "agent-required"}), encoding="utf-8"
            )

            result = build_agent_task_status(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            self.assertEqual(result.task_count, 1)
            self.assertEqual(result.pending_count, 1)
            self.assertEqual(len(payload["tasks"]), 1)
            self.assertEqual(payload["tasks"][0]["path"], "workflow/tasks/scene-agent.agent_tasks.md")
            self.assertEqual(payload["tasks"][0]["route"], "scene-development")

    def test_agent_task_status_treats_an_unreadable_historical_source_as_missing(self):
        historical_path = unittest.mock.Mock()
        historical_path.is_absolute.return_value = True
        historical_path.exists.side_effect = PermissionError("denied")

        with patch.object(route_audit_common, "Path", return_value=historical_path):
            exists = agent_task_inventory._path_exists(Path("C:/project"), "C:\\unreadable\\runtime\\punctuation-standard.md")

        self.assertFalse(exists)

    def test_agent_task_status_retires_empty_state_patch_semantic_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_dir = root / "characters" / "state_patches"
            state_dir.mkdir(parents=True)
            patch = state_dir / "scene_0001_state_patch.json"
            patch.write_text(
                json.dumps(
                    {"scene_id": "scene_0001", "characters": [], "unresolved_changes": []},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            sidecar = state_dir / "scene_0001_state_patch.agent_tasks.md"
            sidecar.write_text("# state review\n", encoding="utf-8")
            sidecar.with_name("scene_0001_state_patch.agent_completion.json").write_text(
                json.dumps({"status": "complete"}),
                encoding="utf-8",
            )

            result = build_agent_task_status(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["summary"]["partial_count"], 0)
            self.assertEqual(payload["summary"]["superseded_count"], 1)
            self.assertEqual(payload["tasks"][0]["status"], "superseded")

    def test_submit_and_complete_require_exact_declared_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            output = root / "drafts" / "candidates" / "scene_0001.md"
            output.parent.mkdir(parents=True)
            output.write_text("正文。\n", encoding="utf-8")
            undeclared = root / "workflow" / "tasks" / "other.md"
            undeclared.write_text("not declared\n", encoding="utf-8")
            task_id = "scene-development-scene_0001-prose"
            (task_dir / f"{task_id}.task.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/agent-task/v1",
                        "task_id": task_id,
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "scene": "scenes/scene_0001.yaml",
                        "status": "opened",
                        "expected_outputs": ["drafts/candidates/scene_0001.md"],
                        "execution_policy": "agent-required",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "prior exact task-submit"):
                complete_task(root, task_id)
            with self.assertRaisesRegex(ValueError, "not declared"):
                submit_task(root, task_id, [output, undeclared])
            submitted = submit_task(root, task_id, [output])
            self.assertEqual(submitted.status, "submitted")

    def test_scene_route_audit_excludes_not_started_planned_scenes_from_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Audit Scope\n", encoding="utf-8")
            scenes = root / "scenes"
            scenes.mkdir()
            (scenes / "scene_0001.yaml").write_text("scene_id: scene_0001\n", encoding="utf-8")
            (scenes / "scene_0002.yaml").write_text("scene_id: scene_0002\n", encoding="utf-8")
            context = root / "memory" / "context_packets" / "scene_0001.md"
            context.parent.mkdir(parents=True)
            context.write_text("# started\n", encoding="utf-8")

            result = build_route_audit(root, route="scene-development")
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            keys = [str(item["key"]) for item in payload["gates"]]
            self.assertIn("scene_0001:context-packet", keys)
            self.assertNotIn("scene_0002:context-packet", keys)
            self.assertEqual(payload["summary"]["scene_scope"]["started_scene_count"], 1)
            self.assertEqual(payload["summary"]["scene_scope"]["planned_scene_count"], 1)

    def test_scene_route_audit_marks_later_stages_as_waiting_not_parallel_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Audit Stages\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
            context = root / "memory" / "context_packets" / "scene_0001.md"
            context.parent.mkdir(parents=True)
            context.write_text("# started\n", encoding="utf-8")

            result = build_route_audit(root, route="scene-development")
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            gates = {str(item["key"]): item for item in payload["gates"]}

            self.assertEqual(gates["scene_0001:context-trace"]["status"], "fail")
            self.assertEqual(gates["scene_0001:context-trace"]["severity"], "blocking")
            self.assertEqual(gates["scene_0001:roleplay-simulation"]["status"], "waiting")
            self.assertEqual(gates["scene_0001:roleplay-simulation"]["severity"], "info")
            self.assertEqual(gates["scene_0001:promotion-manifest"]["status"], "waiting")
            self.assertGreater(payload["summary"]["waiting_count"], 0)

    def test_scene_route_audit_preserves_formal_gate_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Audit Order\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
            context = root / "memory" / "context_packets" / "scene_0001.md"
            context.parent.mkdir(parents=True)
            context.write_text("# started\n", encoding="utf-8")

            result = build_route_audit(root, route="scene-development")
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            keys = [
                str(item["key"]).split(":", 1)[1]
                for item in payload["gates"]
                if str(item["key"]).startswith("scene_0001:")
            ]
            self.assertEqual(
                keys,
                [
                    "context-packet",
                    "context-trace",
                    "roleplay-simulation",
                    "roleplay-cli-provenance",
                    "roleplay-reading-receipt",
                    "roleplay-agent-tasks-resolved",
                    "roleplay-agent-task-complete",
                    "branch-manifest",
                    "branch-cli-provenance",
                    "branch-agent-task-complete",
                    "branch-selection",
                    "composition-json",
                    "composition-ready",
                    "composition-cli-provenance",
                    "composition-agent-task-complete",
                    "scene-word-budget-contract",
                    "scene-word-budget-alignment",
                    "reader-experience-contract",
                    "narrative-rhythm-contract",
                    "narrative-rhythm-explicit",
                    "prose-candidate",
                    "candidate-generation-provenance",
                    "agent-review-json",
                    "agent-review-task-complete",
                    "candidate-review-pass",
                    "agent-review-word-budget",
                    "agent-review-new-character-register",
                    "agent-review-narrative-rhythm",
                    "agent-review-canon-writeback",
                    "promotion-manifest",
                    "promoted-draft",
                    "static-review-pass",
                    "state-patch-json",
                    "state-patch-report",
                "state-agent-task-complete",
                "canon-writeback",
                "continuity-ledger-agent-task",
                "continuity-ledger-review",
                "continuity-ledger-apply",
                "scene-handoff",
            ],
            )

    def test_scene_route_audit_treats_candidate_only_scene_as_started(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Candidate Scope\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("正文。\n", encoding="utf-8")

            result = build_route_audit(root, route="scene-development")
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["scene_scope"]["started_scene_count"], 1)
            self.assertTrue(any(str(item["key"]).startswith("scene_0001:") for item in payload["gates"]))

    def test_reopening_an_explicit_future_task_preserves_its_contract(self):
        task = _enrich_task_payload(
            {
                "task_id": "future-explicit-task",
                "route": "scene-development",
                "current_state": "future-state",
                "task_type": "future-task-type",
                "prompt_asset_id": "route.scene-development.prose.generate.v1",
                "expected_outputs": [],
                "execution_policy": "agent-required",
                "agent_role": "future-agent-role",
                "human_gate": {"required": False, "reasons": [], "source": "future-registry"},
                "runtime_capabilities_required": ["read-task-sources"],
                "output_contracts": [],
            }
        )
        self.assertEqual(task["agent_role"], "future-agent-role")
        self.assertEqual(task["human_gate"]["source"], "future-registry")

    def test_active_task_auto_refreshes_when_executable_contract_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            first = task_registry.issue_next_task(root, route="character-and-world-assets")
            self.assertEqual(first.status, "issued")
            payload = json.loads(first.task_json_path.read_text(encoding="utf-8"))
            payload["status"] = "opened"
            payload["expected_outputs"] = ["obsolete/output.json"]
            first.task_json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            refreshed = task_registry.issue_next_task(root, route="character-and-world-assets")
            current = json.loads(refreshed.task_json_path.read_text(encoding="utf-8"))
            self.assertEqual(refreshed.status, "issued")
            self.assertEqual(current["refreshed_from_status"], "opened")
            self.assertNotIn("obsolete/output.json", current["expected_outputs"])

    def test_open_task_refreshes_a_legacy_active_package_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            first = task_registry.issue_next_task(root, route="character-and-world-assets")
            payload = json.loads(first.task_json_path.read_text(encoding="utf-8"))
            payload["status"] = "opened"
            payload.pop("task_contract_revision", None)
            payload["command"] = "python -m literary_engineering_studio_engine asset-create <project> --type <type>"
            first.task_json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            opened = task_registry.open_task(root, first.task_id)
            refreshed = json.loads(opened.task_json_path.read_text(encoding="utf-8"))
            self.assertEqual(opened.status, "opened")
            self.assertEqual(refreshed["task_contract_revision"], task_registry.TASK_CONTRACT_REVISION)
            self.assertEqual(refreshed["command"], "python -m literary_engineering_studio_engine seed-project-assets <project>")

    def test_scene_task_payload_carries_yaml_word_budget_and_curated_agent_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\nword_count_target: 1300\nword_count_min: 1170\nword_count_max: 1430\n",
                encoding="utf-8",
            )
            (root / "canon").mkdir()
            (root / "characters").mkdir()
            (root / "style").mkdir()
            (root / "style" / "style-profile.md").write_text("style", encoding="utf-8")

            payload = task_registry._build_task_payload(
                root,
                "scene-development",
                {
                    "scene_id": "scene_0001",
                    "scene": "scenes/scene_0001.yaml",
                    "current_step": "candidate-generation-provenance",
                    "next_action": "",
                },
            )

            self.assertEqual(payload["word_count_target"], 1300)
            self.assertEqual(payload["word_count_min"], 1170)
            self.assertEqual(payload["word_count_max"], 1430)
            self.assertNotIn("canon", payload["agent_source_paths"])
            self.assertNotIn("characters", payload["agent_source_paths"])
            self.assertNotIn("style", payload["agent_source_paths"])
            self.assertIn("style/style-profile.md", payload["agent_source_paths"])
            self.assertNotIn("plot/word_budget/word_budget.agent_tasks.md", payload["agent_source_paths"])

    def test_candidate_review_agent_sources_include_exact_candidate(self):
        from literary_engineering_studio_engine.routes.scene.definition import _agent_reading_paths

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("候选正文", encoding="utf-8")
            manifest = candidate.with_suffix(".json")
            manifest.write_text("{}", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001", encoding="utf-8")

            sources = _agent_reading_paths(
                root,
                [candidate.relative_to(root).as_posix(), manifest.relative_to(root).as_posix(), "canon"],
                current_state="candidate-review",
                scene_id="scene_0001",
            )

            self.assertIn(candidate.relative_to(root).as_posix(), sources)
            self.assertIn(manifest.relative_to(root).as_posix(), sources)
            self.assertNotIn("canon", sources)

            revision = root / "drafts" / "revisions" / "scene_0001_revision.md"
            revision.parent.mkdir(parents=True, exist_ok=True)
            revision.write_text("修订候选正文", encoding="utf-8")
            revision_manifest = revision.with_suffix(".json")
            revision_manifest.write_text("{}", encoding="utf-8")
            revision_sources = _agent_reading_paths(
                root,
                [revision.relative_to(root).as_posix(), revision_manifest.relative_to(root).as_posix(), "canon"],
                current_state="candidate-review",
                scene_id="scene_0001",
            )
            self.assertIn(revision.relative_to(root).as_posix(), revision_sources)
            self.assertIn(revision_manifest.relative_to(root).as_posix(), revision_sources)
            self.assertNotIn("canon", revision_sources)

    def test_candidate_revision_agent_sources_include_cli_draft_and_review_inputs(self):
        from literary_engineering_studio_engine.routes.scene.definition import _agent_reading_paths

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            review = root / "reviews" / "agent" / "scene_0001_scene_review.json"
            review_markdown = review.with_suffix(".md")
            scene = root / "scenes" / "scene_0001.yaml"
            candidate.parent.mkdir(parents=True)
            review.parent.mkdir(parents=True)
            scene.parent.mkdir(parents=True)
            candidate.write_text("候选正文", encoding="utf-8")
            review.write_text("{}", encoding="utf-8")
            review_markdown.write_text("审查结论", encoding="utf-8")
            scene.write_text("scene_id: scene_0001", encoding="utf-8")

            sources = _agent_reading_paths(
                root,
                [
                    candidate.relative_to(root).as_posix(),
                    review.relative_to(root).as_posix(),
                    review_markdown.relative_to(root).as_posix(),
                    "scenes",
                    "canon",
                    "characters",
                ],
                current_state="candidate-revision",
                scene_id="scene_0001",
            )

            self.assertIn(candidate.relative_to(root).as_posix(), sources)
            self.assertIn(review.relative_to(root).as_posix(), sources)
            self.assertIn(review_markdown.relative_to(root).as_posix(), sources)
            self.assertNotIn("canon", sources)
            self.assertNotIn("characters", sources)
            self.assertNotIn("scenes", sources)

            revision = root / "drafts" / "revisions" / "scene_0001_revision.md"
            revision.parent.mkdir(parents=True)
            revision.write_text("上一版修订候选", encoding="utf-8")
            revision_sources = _agent_reading_paths(
                root,
                [
                    revision.relative_to(root).as_posix(),
                    review.relative_to(root).as_posix(),
                ],
                current_state="candidate-revision",
                scene_id="scene_0001",
            )
            self.assertIn(revision.relative_to(root).as_posix(), revision_sources)

    def test_state_patch_preparation_does_not_merge_the_following_agent_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")

            preparation = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "state-patch-json", ""
            )
            review = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "state-agent-task", ""
            )

            self.assertEqual(preparation["task_type"], "deterministic-cli")
            self.assertIn(
                "drafts/compositions/scene_0001_composition.json",
                preparation["source_paths"],
            )
            self.assertIn(
                "drafts/promotions/scene_0001_promotion.json",
                preparation["source_paths"],
            )
            self.assertIn(
                "reviews/agent/scene_0001_scene_review.json",
                preparation["source_paths"],
            )
            self.assertIn("characters/state_patches/scene_0001_state_patch_review.json", preparation["expected_outputs"])
            self.assertNotIn("characters/state_patches/scene_0001_state_patch.agent_completion.json", preparation["expected_outputs"])
            self.assertIn("characters/state_patches/scene_0001_state_patch_review.json", review["expected_outputs"])
            self.assertIn("characters/state_patches/scene_0001_state_patch.agent_completion.json", review["expected_outputs"])
            self.assertIn("drafts/scenes/scene_0001.md", review["source_paths"])
            self.assertIn("drafts/compositions/scene_0001_composition.json", review["source_paths"])
            self.assertIn("drafts/promotions/scene_0001_promotion.json", review["source_paths"])
            self.assertIn("reviews/agent/scene_0001_scene_review.json", review["source_paths"])

    def test_canon_generation_and_review_share_exact_durable_fact_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")
            (root / "canon").mkdir()
            for relative in (
                "facts.json",
                "forbidden_changes.yaml",
                "locations.yaml",
                "organizations.yaml",
                "timeline.yaml",
                "world_rules.yaml",
            ):
                (root / "canon" / relative).write_text("{}\n", encoding="utf-8")

            generation = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "canon-patch-json", ""
            )
            review = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "canon-agent-task", ""
            )

            for blueprint in (generation, review):
                self.assertIn("drafts/scenes/scene_0001.md", blueprint["source_paths"])
                self.assertIn("reviews/agent/scene_0001_scene_review.json", blueprint["source_paths"])
                self.assertIn("characters/state_patches/scene_0001_state_patch.json", blueprint["source_paths"])
                self.assertIn("canon/world_rules.yaml", blueprint["source_paths"])
                self.assertIn("canon/forbidden_changes.yaml", blueprint["source_paths"])

            sidecar = "canon/patches/scene_0001_canon_patch.agent_tasks.md"
            review_json = "canon/patches/scene_0001_canon_patch_review.json"
            self.assertEqual(
                generation["core_managed_outputs"],
                [sidecar, review_json],
            )
            self.assertEqual(
                review["prompt_asset_id"],
                "route.scene-development.canon-review.v1",
            )

            payload = _enrich_task_payload(
                {
                    "schema": "literary-engineering-workbench/agent-task/v1",
                    "task_id": "scene-development-scene-0001-canon-patch-json",
                    "status": "issued",
                    "route": "scene-development",
                    "scene_id": "scene_0001",
                    "scene": "scenes/scene_0001.yaml",
                    "current_state": "canon-patch-json",
                    **generation,
                    "required_reading": [],
                    "forbidden_shortcuts": [],
                    "submission_command": "lew task-submit",
                    "completion_command": "lew task-complete",
                }
            )
            task_path = root / "task.json"
            task_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            task_markdown = root / "workflow/tasks/scene-development-scene-0001-canon-patch-json.agent_tasks.md"
            task_markdown.parent.mkdir(parents=True, exist_ok=True)
            task_markdown.write_text("# Canon candidate task\n", encoding="utf-8")
            task = load_task_package(root, task_path)
            context = build_task_context(task)

            self.assertEqual(
                [item["path"] for item in context["completion_contract"]["agent_owned_outputs"]],
                [
                    "canon/patches/scene_0001_canon_patch.md",
                    "canon/patches/scene_0001_canon_patch.json",
                ],
            )
            semantic = context["semantic_output_contract"]
            self.assertEqual(semantic["schema_name"], "canon-patch-candidate/v0.1")
            self.assertEqual(
                semantic["model_owned_fields"],
                ["canon_change", "no_canon_change_reason", "items"],
            )

    def test_state_apply_stages_the_completed_state_review_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")
            character = root / "characters" / "narrator.yaml"
            character.parent.mkdir()
            character.write_text("name: 叙述者\nstate: {}\n", encoding="utf-8")
            state_patch = root / "characters" / "state_patches" / "scene_0001_state_patch.json"
            state_patch.parent.mkdir()
            state_patch.write_text(
                json.dumps(
                    {
                        "scene_id": "scene_0001",
                        "characters": [{"character_id": "narrator"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            apply = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "state-apply", ""
            )

            self.assertEqual(apply["task_type"], "deterministic-cli")
            self.assertTrue(str(apply["command"]).startswith("python -m literary_engineering_studio_engine state-apply"))
            self.assertIn("characters/state_patches/scene_0001_state_patch.agent_tasks.md", apply["source_paths"])
            self.assertIn("characters/state_patches/scene_0001_state_patch.agent_completion.json", apply["source_paths"])
            self.assertIn("characters/state_patches/scene_0001_state_patch_review.json", apply["source_paths"])
            self.assertIn("characters/narrator.yaml", apply["source_paths"])
            self.assertIn("characters/narrator.yaml", apply["expected_outputs"])
            self.assertIn("characters/state_patches/scene_0001_state_apply.json", apply["expected_outputs"])
            self.assertIn("characters/state_patches/scene_0001_state_apply.md", apply["expected_outputs"])
            self.assertNotIn("characters/state_patches/scene_0001_state_patch_apply.json", apply["expected_outputs"])


if __name__ == "__main__":
    unittest.main()
