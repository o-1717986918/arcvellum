from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from literary_engineering_studio import core_read_models
from literary_engineering_studio_engine import project_interaction
from literary_engineering_studio_engine import workflow_state


class RouteLocalChoiceTests(unittest.TestCase):
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
                project_interaction,
                "build_workflow_dashboard",
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
            state_path = root / "workflow" / "runtime_choices" / "character-and-world-assets.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                '{"assets":[{"status":"blocked","scene_id":"scene_0001",'
                '"candidate_id":"scene-0001-林正","target_id":"scene-0001-林正",'
                '"current_step":"asset-approval","next_action":"approve"}]}\n',
                encoding="utf-8",
            )

            with patch.object(
                project_interaction,
                "build_workflow_state",
                return_value=SimpleNamespace(json_path=state_path),
            ):
                payload = project_interaction.build_current_human_choices(
                    root,
                    route="character-and-world-assets",
                )

            choice = payload["choices"][0]
            self.assertEqual(choice["target"]["target_id"], "scene-0001-林正")
            self.assertTrue(choice["target"]["candidate_sha256"])
            recorded = project_interaction.record_human_choice(
                root,
                {**choice, "selected": "approve", "rationale": "角色候选通过审查。", "materialize": True},
            )
            approval = root / recorded["materialized"]
            self.assertEqual(
                json.loads(approval.read_text(encoding="utf-8").splitlines()[-1])["run_id"],
                "scene-0001-林正",
            )

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
                project_interaction,
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


if __name__ == "__main__":
    unittest.main()
