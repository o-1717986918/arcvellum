from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.advisor.advisor_snapshot import create_advisor_snapshot
from literary_engineering_studio.advisor.creative_steward import (
    _decision_evidence_packet,
    _decision_prompt,
)
from literary_engineering_studio import core_read_models
from literary_engineering_studio_engine import project_interaction
from literary_engineering_studio_engine import project_interaction_choices
from literary_engineering_studio_engine import workflow_state
from literary_engineering_studio_engine.routes.export.blueprints import (
    export_release_blueprint_for_state,
)
from literary_engineering_studio_engine.projections.interaction.choice_builders import (
    approval_choice,
)


class RouteLocalChoiceTests(unittest.TestCase):
    def test_release_approval_choice_projects_the_complete_bounded_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            root.mkdir()
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            chapter_id = "chapter_0001"
            export_dir = root / "exports" / chapter_id
            export_dir.mkdir(parents=True)
            outputs = {}
            for kind in ("novel", "screenplay", "video_prompt_pack"):
                relative = f"exports/{chapter_id}/{chapter_id}_{kind}.md"
                path = root / relative
                path.write_text(f"# {kind}\n读者可见正文。\n", encoding="utf-8")
                outputs[kind] = relative
                (export_dir / f"{chapter_id}_{kind}.inspection.json").write_text(
                    '{"status":"pass","trace_hits":[]}\n',
                    encoding="utf-8",
                )
            (export_dir / "export_manifest.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/export-package/v0.1",
                        "chapter_id": chapter_id,
                        "include_blocked": False,
                        "outputs": outputs,
                        "exported_scenes": [{"scene_id": "scene_0001", "status": "ready"}],
                        "skipped_scenes": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            for relative, content in (
                (f"plot/chapters/{chapter_id}.json", '{"summary":{"ready_count":1,"blocked_count":0}}\n'),
                ("reviews/longform/longform_audit.json", '{"status":"pass","issues":[]}\n'),
                ("reviews/agent/committee_project-final-audit.json", '{"final_recommendation":"approve"}\n'),
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            with patch.object(
                project_interaction_choices,
                "_route_choice_actions",
                return_value=([{
                    "route": "export-and-release",
                    "target": chapter_id,
                    "current_step": "release-approval",
                    "next_action": "approve current release",
                }], ""),
            ):
                payload = project_interaction.build_current_human_choices(
                    root,
                    route="export-and-release",
                )

            choice = payload["choices"][0]
            self.assertTrue(choice["target"]["candidate_sha256"])
            self.assertEqual(
                choice["source_paths"],
                [
                    f"exports/{chapter_id}/export_manifest.json",
                    f"exports/{chapter_id}/{chapter_id}_novel.inspection.json",
                    f"exports/{chapter_id}/{chapter_id}_screenplay.inspection.json",
                    f"exports/{chapter_id}/{chapter_id}_video_prompt_pack.inspection.json",
                    "reviews/longform/longform_audit.json",
                    f"exports/{chapter_id}/{chapter_id}_novel.md",
                    f"plot/chapters/{chapter_id}.json",
                    "reviews/agent/committee_project-final-audit.json",
                ],
            )
            blueprint = export_release_blueprint_for_state(
                root,
                chapter_id,
                "release-approval",
                "approve current release",
            )
            self.assertEqual(blueprint["source_paths"], choice["source_paths"])
            snapshot = create_advisor_snapshot(root, base / "snapshots")
            packet = _decision_evidence_packet(snapshot.workspace, choice)
            self.assertNotIn('status="missing"', packet)
            self.assertIn(f'<source path="exports/{chapter_id}/export_manifest.json">', packet)
            self.assertIn(f'<source path="exports/{chapter_id}/{chapter_id}_novel.md">', packet)
            self.assertIn('<source path="reviews/longform/longform_audit.json">', packet)

    def test_non_final_release_choice_excludes_whole_work_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenes = root / "scenes"
            scenes.mkdir()
            (scenes / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )
            (scenes / "scene_0002.yaml").write_text(
                "scene_id: scene_0002\nchapter_id: chapter_0002\n",
                encoding="utf-8",
            )

            choice = approval_choice(
                root,
                "export-and-release",
                "chapter_0001",
                "release_approval",
                "发布前需要你确认是否放行。",
            )
            self.assertEqual(choice["target"]["release_scope"], "chapter-only")
            self.assertEqual(choice["target"]["is_final_chapter"], "false")
            self.assertNotIn("reviews/longform/longform_audit.json", choice["source_paths"])
            self.assertNotIn(
                "reviews/agent/committee_project-final-audit.json",
                choice["source_paths"],
            )
            prompt = _decision_prompt(choice, "完成两章作品")
            self.assertIn("do not apply whole-work target length", prompt)
            blueprint = export_release_blueprint_for_state(
                root,
                "chapter_0001",
                "release-approval",
                "approve current release",
            )
            self.assertEqual(blueprint["source_paths"], choice["source_paths"])

    def test_scene_choice_projection_does_not_build_the_whole_dashboard(self):
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

            with patch.object(
                project_interaction_choices,
                "project_workflow_dashboard",
                side_effect=AssertionError("whole-project dashboard scan used"),
            ):
                payload = project_interaction.build_current_human_choices(
                    root,
                    route="scene-development",
                )

            self.assertEqual(payload["dashboard"], "")
            self.assertEqual(payload["choices"], [])

    def test_studio_read_model_forwards_route_to_engine(self):
        calls = []

        def fake_builder(project_root, *, route=""):
            calls.append((project_root, route))
            return {"choices": []}

        with patch.object(core_read_models, "_function", return_value=fake_builder):
            payload = core_read_models.current_choices(
                {},
                Path("C:/work/project"),
                route="scene-development",
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(calls[0][1], "scene-development")

    def test_asset_approval_choice_uses_candidate_id_not_source_scene_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            candidate = root / "characters" / "candidates" / "scene-0001-林正.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text('{"candidate_id":"scene-0001-林正"}\n', encoding="utf-8")
            candidate.with_suffix(".md").write_text("# 林正\n", encoding="utf-8")
            review_dir = root / "reviews" / "assets"
            review_dir.mkdir(parents=True)
            (review_dir / "scene-0001-林正_review.json").write_text('{"status":"pass"}\n', encoding="utf-8")
            (review_dir / "scene-0001-林正_review.md").write_text("# 独立审查\n", encoding="utf-8")
            state_path = root / "workflow" / "runtime_choices" / "character-and-world-assets.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                '{"assets":[{"status":"blocked","scene_id":"scene_0001",'
                '"candidate_id":"scene-0001-林正","target_id":"scene-0001-林正",'
                '"current_step":"asset-approval","next_action":"approve"}]}\n',
                encoding="utf-8",
            )

            with patch.object(
                project_interaction_choices,
                "project_workflow_state",
                return_value=json.loads(state_path.read_text(encoding="utf-8")),
            ):
                payload = project_interaction.build_current_human_choices(
                    root,
                    route="character-and-world-assets",
                )
                repeated = project_interaction.build_current_human_choices(
                    root,
                    route="character-and-world-assets",
                )

            choice = payload["choices"][0]
            self.assertEqual(choice["choice_id"], repeated["choices"][0]["choice_id"])
            self.assertEqual(choice["target"]["target_id"], "scene-0001-林正")
            self.assertTrue(choice["target"]["candidate_sha256"])
            self.assertEqual(
                choice["source_paths"],
                [
                    "reviews/assets/scene-0001-林正_review.json",
                    "reviews/assets/scene-0001-林正_review.md",
                    "characters/candidates/scene-0001-林正.json",
                    "characters/candidates/scene-0001-林正.md",
                    "workflow/approvals/index.jsonl",
                ],
            )
            recorded = project_interaction.record_human_choice(
                root,
                {**choice, "selected": "approve", "rationale": "角色候选通过审查。", "materialize": True},
            )
            approval = root / recorded["materialized"]
            self.assertEqual(
                json.loads(approval.read_text(encoding="utf-8").splitlines()[-1])["run_id"],
                "scene-0001-林正",
            )
            with patch.object(
                project_interaction_choices,
                "project_workflow_state",
                return_value=json.loads(state_path.read_text(encoding="utf-8")),
            ):
                after = project_interaction.build_current_human_choices(
                    root,
                    route="character-and-world-assets",
                )
            self.assertEqual(after["choices"], [])

    def test_cross_asset_scene_review_exposes_a_hash_bound_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            review = root / "reviews" / "agent" / "scene_0001_scene_review.json"
            review.parent.mkdir(parents=True)
            review.write_text(
                json.dumps(
                    {
                        "candidate_sha256": "a" * 64,
                        "warnings": [
                            {
                                "id": "W-001",
                                "description": "正文年龄和正式角色资产冲突。",
                                "resolution": "needs_human_review",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.object(
                project_interaction_choices,
                "_route_choice_actions",
                return_value=([
                    {
                        "route": "scene-development",
                        "target": "scene_0001",
                        "current_step": "candidate-human-decision",
                        "next_action": "choose",
                    }
                ], ""),
            ):
                payload = project_interaction.build_current_human_choices(root, route="scene-development")

            choice = payload["choices"][0]
            self.assertEqual(choice["decision_type"], "cross_asset_alignment")
            self.assertEqual(choice["recommended"], "align_prose_to_formal_asset")
            self.assertEqual(choice["target"]["candidate_sha256"], "a" * 64)
            self.assertEqual(choice["options"][1]["id"], "hold_for_asset_revision")

    def test_pending_scene_review_does_not_emit_a_revision_direction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            for step in ("candidate-review", "agent-review-task", "static-review"):
                with self.subTest(step=step), patch.object(
                    project_interaction_choices,
                    "_route_choice_actions",
                    return_value=([{
                        "route": "scene-development",
                        "target": "scene_0001",
                        "current_step": step,
                        "next_action": "run the pending review task",
                    }], ""),
                ):
                    payload = project_interaction.build_current_human_choices(
                        root, route="scene-development"
                    )
                self.assertEqual(payload["choices"], [])

    def test_failed_scene_review_emits_a_revision_direction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("当前候选。\n", encoding="utf-8")
            review = root / "reviews" / "agent" / "scene_0001_scene_review.json"
            review.parent.mkdir(parents=True)
            review.write_text(
                json.dumps(
                    {
                        "candidate_path": "drafts/candidates/scene_0001-platform-agent.md",
                        "candidate_sha256": "old-review-digest",
                        "conclusion": "pass_with_notes",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            review.with_suffix(".md").write_text("# 审查\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
            for step in ("candidate-revision", "static-revision"):
                if step == "static-revision":
                    draft = root / "drafts" / "scenes" / "scene_0001.md"
                    draft.parent.mkdir(parents=True, exist_ok=True)
                    draft.write_text("已晋升正文。\n", encoding="utf-8")
                    static_review = root / "reviews" / "scene_0001-review.md"
                    static_review.parent.mkdir(parents=True, exist_ok=True)
                    static_review.write_text("# 静态审查\n", encoding="utf-8")
                with self.subTest(step=step), patch.object(
                    project_interaction_choices,
                    "_route_choice_actions",
                    return_value=([{
                        "route": "scene-development",
                        "target": "scene_0001",
                        "current_step": step,
                        "next_action": "revise the exact reviewed candidate",
                    }], ""),
                ):
                    payload = project_interaction.build_current_human_choices(
                        root, route="scene-development"
                    )
                self.assertEqual(len(payload["choices"]), 1)
                choice = payload["choices"][0]
                self.assertEqual(choice["decision_type"], "revision_direction")
                self.assertEqual(choice["task_step"], step)
                self.assertTrue(choice["target"]["candidate_sha256"])
                self.assertTrue(all(not path.endswith("/") for path in choice["source_paths"]))
                self.assertIn("scenes/scene_0001.yaml", choice["source_paths"])
                if step == "candidate-revision":
                    self.assertEqual(
                        choice["target"]["candidate_path"],
                        "drafts/candidates/scene_0001-platform-agent.md",
                    )
                    self.assertIn(
                        "reviews/agent/scene_0001_scene_review.json",
                        choice["source_paths"],
                    )
                else:
                    self.assertEqual(
                        choice["target"]["candidate_path"],
                        "drafts/scenes/scene_0001.md",
                    )
                    self.assertIn("reviews/scene_0001-review.md", choice["source_paths"])

    def test_route_local_choices_do_not_take_the_dashboard_projection_lock(self):
        entered = []

        class BombLock:
            def __enter__(self):
                raise AssertionError("dashboard lock used")

            def __exit__(self, exc_type, exc, traceback):
                return False

        def fake_builder(project_root, *, route=""):
            entered.append(route)
            return {"choices": []}

        with (
            patch.object(core_read_models, "_function", return_value=fake_builder),
            patch.object(core_read_models, "ENGINE_ACCESS_LOCK", BombLock()),
        ):
            payload = core_read_models.current_choices(
                {}, Path("C:/work/project"), route="scene-development"
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(entered, ["scene-development"])

    def test_scene_scoped_state_refresh_does_not_scan_every_scene(self):
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

            with patch.object(
                workflow_state,
                "_scene_states",
                side_effect=AssertionError("full scene scan used"),
            ):
                result = workflow_state.build_workflow_state(
                    root,
                    route="scene-development",
                    scene="scenes/scene_0002.yaml",
                    output=root / "workflow/runtime_choices/scene.md",
                    json_output=root / "workflow/runtime_choices/scene.json",
                )

            self.assertEqual(result.scene_count, 1)

    def test_dashboard_scope_observes_frontier_without_expanding_every_planned_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            scenes = root / "scenes"
            scenes.mkdir()
            for index in range(1, 31):
                (scenes / f"scene_{index:04d}.yaml").write_text(
                    f"scene_id: scene_{index:04d}\nchapter_id: chapter_0001\n",
                    encoding="utf-8",
                )

            observed: list[str] = []
            original = workflow_state._scene_state

            def record_scene(project_root, scene_path):
                observed.append(scene_path.stem)
                return original(project_root, scene_path)

            with patch.object(workflow_state, "_scene_state", side_effect=record_scene):
                result = workflow_state.build_workflow_state(
                    root,
                    route="overall",
                    scene_scope="dashboard",
                    output=root / "workflow/dashboard/route_state.md",
                    json_output=root / "workflow/dashboard/route_state.json",
                )

            payload = json.loads((root / "workflow/dashboard/route_state.json").read_text(encoding="utf-8"))
            self.assertEqual(result.scene_count, 30)
            self.assertEqual(observed, ["scene_0001"])
            self.assertEqual(payload["summary"]["scene_scope"]["mode"], "active-frontier")
            self.assertTrue(payload["summary"]["scene_scope"]["truncated"])

    def test_workflow_state_preserves_stable_payload_and_summary_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: State Contract\n", encoding="utf-8")
            result = workflow_state.build_workflow_state(root, route="overall")
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertEqual(
                list(payload),
                [
                    "schema",
                    "generated_at",
                    "project_root",
                    "route",
                    "summary",
                    "scenes",
                    "longform",
                    "source_ingests",
                    "styles",
                    "assets",
                    "audits",
                    "exports",
                    "rules",
                ],
            )
            self.assertEqual(
                list(payload["summary"]),
                [
                    "route",
                    "scene_count",
                    "scene_detail_count",
                    "scene_scope",
                    "source_ingest_count",
                    "style_profile_count",
                    "asset_count",
                    "audit_count",
                    "export_count",
                    "ready_count",
                    "blocked_count",
                    "next_action_count",
                    "longform_status",
                ],
            )
            self.assertEqual(len(payload["rules"]), 3)


if __name__ == "__main__":
    unittest.main()
