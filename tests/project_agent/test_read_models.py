import unittest
from pathlib import Path
import tempfile

from literary_engineering_studio.project_agent.read_models import dependencies_from_read_models
from literary_engineering_studio.project_agent.scope import work_id_for_root


class _ReadModels:
    def dashboard(self, _root):
        return {
            "summary": {"stage": "scene-development"},
            "next_actions": [{"label": "完成场景审查"}],
            "route_audits": [{"route": "scene-development", "blocking_count": 1}],
            "recent_events": [{"event": "review.started"}],
        }

    def progress(self, _root):
        return {"overall_percent": 36.5}

    def library(self, _root):
        return {
            "sections": {
                "characters": [{
                    "id": "lin-che", "title": "林澈", "importance": "major",
                    "subtitle": "档案保管员", "excerpt": "必须决定是否公开档案",
                }],
                "scenes": [
                    {
                        "id": "scene_0001", "title": "雨夜开图",
                        "subtitle": "chapter_0001", "excerpt": "林澈打开旧地图",
                        "participants": ["林澈"],
                    },
                    {
                        "id": "scene_0002", "title": "追问来源",
                        "subtitle": "chapter_0002", "excerpt": "查清地图来历",
                        "participants": ["林澈"],
                    },
                ],
                "rhythm": [{"id": "scene_0001", "excerpt": "隐瞒转为调查"}],
                "continuity": [
                    {"title": "林澈决定公开旧物", "subtitle": "人物状态变化", "status": "recorded"},
                    {"title": "旧物来源仍未知", "subtitle": "读者问题推进", "status": "open"},
                ],
                "drafts": [{
                    "id": "promoted__scene_0001", "status": "promoted",
                    "path": "drafts/scenes/scene_0001.md",
                    "body": "林澈已经打开旧物。追问之后，他把它交给了调度员。",
                }],
            }
        }

    def reader(self, _root):
        return {
            "unit_count": 1,
            "total_chinese_content_chars": 1200,
            "units": [{
                "title": "雨夜开图", "scene_id": "scene_0001",
                "chapter_id": "chapter_0001", "coverage": ["scene_0001"],
            }],
            "warnings": [],
        }

    def workspace(self, root):
        return {
            "autopilot_status": {"status": "running"},
            "agent_observability": {"active": 1},
            "dashboard": self.dashboard(root),
        }

    def delivery(self, _root):
        return {"ready": False, "blockers": ["正文尚未完成"]}


class ProjectAgentReadModelTests(unittest.TestCase):
    def setUp(self):
        self.dependencies = dependencies_from_read_models(_ReadModels())

    def test_overview_uses_cached_projection_contract(self):
        value = self.dependencies.project_overview(_root(), {"focus": "blocker"})
        self.assertEqual(value["summary"]["stage"], "scene-development")
        self.assertEqual(value["progress"]["overall_percent"], 36.5)
        story = value["story_brief"]
        self.assertEqual(story["formal_units"]["count"], 1)
        self.assertEqual(story["completed_beats"][0]["planned_story_move"], "隐瞒转为调查")
        self.assertNotIn("story_move", story["completed_beats"][0])
        self.assertIn("他把它交给了调度员", story["completed_beats"][0]["actual_prose_tail"])
        self.assertEqual(story["main_characters"][0]["name"], "林澈")
        self.assertEqual(story["next_planned_scene"]["scene_id"], "scene_0002")
        self.assertEqual(story["recent_changes"][0]["summary"], "林澈决定公开旧物")
        self.assertEqual(story["open_threads"][0]["title"], "旧物来源仍未知")
        self.assertEqual(story["continuity_status"]["state"], "tracked")

    def test_search_returns_bounded_index_hits(self):
        value = self.dependencies.project_search(_root(), {"query": "地图", "limit": 5})
        self.assertEqual(value["count"], 2)
        self.assertTrue(all("path" in item for item in value["hits"]))

    def test_creation_observe_exposes_current_run_without_file_access(self):
        value = self.dependencies.creation_observe(_root(), {})
        self.assertEqual(value["autopilot"]["status"], "running")
        self.assertEqual(value["recent_events"][0]["event"], "review.started")

    def test_control_projection_selects_one_bounded_domain(self):
        dependencies = dependencies_from_read_models(
            _ReadModels(),
            choices=lambda _root: {"choices": [{"choice_id": "choice-1"}]},
            quality=lambda _root: {"profile": "plain"},
            rhythm=lambda _root: {"entries": [{"chapter": 1}]},
            style_mounts=lambda _root: {"status": "active"},
            archive_candidates=lambda _root: ({"candidate_id": "character-lin-che"},),
        )

        decisions = dependencies.project_controls(_root(), {"section": "decisions"})
        all_controls = dependencies.project_controls(_root(), {"section": "all"})

        self.assertEqual(decisions["decisions"]["choices"][0]["choice_id"], "choice-1")
        self.assertNotIn("quality", decisions)
        self.assertEqual(all_controls["style"]["status"], "active")
        self.assertEqual(all_controls["archive"]["candidates"][0]["candidate_id"], "character-lin-che")
        self.assertFalse(all_controls["delivery"]["ready"])

    def test_workspace_catalog_uses_stable_ids_and_resolves_only_registered_works(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            for project in (first, second):
                project.joinpath("project.yaml").write_text("title: test\n", encoding="utf-8")
            catalog = {
                "current_project": str(first),
                "projects": [
                    {"path": str(first), "title": "第一部", "status": "writing"},
                    {"path": str(second), "title": "第二部", "status": "planning"},
                ],
            }
            dependencies = dependencies_from_read_models(_ReadModels(), project_catalog=lambda: catalog)

            result = dependencies.workspace_catalog(root, {})
            resolved = dependencies.resolve_project(root, {"work_id": work_id_for_root(second)})

            self.assertEqual(result["count"], 2)
            self.assertEqual(result["current_work_id"], work_id_for_root(first))
            self.assertNotIn("path", result["works"][0])
            self.assertEqual(resolved, second.resolve())
            with self.assertRaisesRegex(ValueError, "unknown or unregistered"):
                dependencies.resolve_project(root, {"work_id": "work-0000000000000000"})
            with self.assertRaisesRegex(ValueError, "needs a work_id"):
                dependencies.resolve_project(root, {})
            self.assertEqual(dependencies.resolve_project(first, {}), first.resolve())

    def test_diagnose_identifies_pending_decision_before_recovery(self):
        dependencies = dependencies_from_read_models(
            _ReadModels(),
            choices=lambda _root: {"choices": [{"choice_id": "choice-1"}]},
        )

        result = dependencies.project_diagnose(_root(), {})

        self.assertEqual(result["classification"], "decision_required")
        self.assertFalse(result["recoverable"])
        self.assertEqual(result["recommended_tool"], "project_decision_resolve")


def _root():
    from pathlib import Path

    return Path("C:/work")


if __name__ == "__main__":
    unittest.main()
