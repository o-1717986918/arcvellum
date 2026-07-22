from pathlib import Path
import json
import tempfile
import threading
import unittest
from unittest.mock import patch

from literary_engineering_studio.autopilot import (
    AutopilotService,
    DelegationPolicy,
    ROUTE_ORDER,
    default_policy,
    is_revision_task,
    next_revision_count,
    normalize_policy,
)
from literary_engineering_studio.creative_steward import _decision_prompt, _parse_decision
from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.project_manager import record_direction
from literary_engineering_studio.worker import WorkerRunResult
from literary_engineering_studio.whole_book_release import WholeBookReleaseCoordinator
from literary_engineering_studio_engine.project_interaction import record_human_choice


class _Audit:
    fields = {"status": "pass", "blocking_count": "0"}


class AutopilotTests(unittest.TestCase):
    def test_revision_counter_covers_semantic_revision_task_names(self):
        run = {"consecutive_revisions": 2}
        self.assertTrue(is_revision_task("character-and-world-assets-protagonist-asset-review-pass"))
        self.assertTrue(is_revision_task("review-and-audit-canon-review-pass"))
        self.assertTrue(is_revision_task("scene-development-scene-0001-candidate-revision"))
        self.assertFalse(is_revision_task("scene-development-scene-0001-agent-review-task"))
        self.assertEqual(next_revision_count(run, "character-and-world-assets-protagonist-asset-review-pass"), 3)
        self.assertEqual(next_revision_count(run, "scene-development-scene-0001-agent-review-task"), 0)

    def test_policy_modes_bound_decisions_and_limits(self):
        collaborative = DelegationPolicy(default_policy("collaborative"))
        self.assertFalse(collaborative.permits("scene-development", "branch_selection"))
        supervised = DelegationPolicy(default_policy("supervised_auto"))
        self.assertTrue(supervised.permits("scene-development", "branch_selection"))
        self.assertFalse(supervised.permits("export-and-release", "release_approval"))
        full = DelegationPolicy(default_policy("full_auto"))
        self.assertTrue(full.permits_writeback("scene-development"))
        self.assertTrue(full.permits("export-and-release", "release_approval"))
        self.assertFalse(full.permits("scene-development", "cross_asset_alignment"))
        normalized = normalize_policy({"mode": "full_auto", "limits": {"max_tasks": 999999, "max_cost": -1}})
        self.assertEqual(normalized["limits"]["max_tasks"], 10000)
        self.assertEqual(normalized["limits"]["max_cost"], 0)

    def test_cancelled_steward_decision_never_records_a_choice(self):
        class CancellingSteward:
            def decide(self, project, choice, *, project_direction="", timeout=180, cancel_event=None):
                assert cancel_event is not None
                cancel_event.set()
                return {
                    "selected_option": "approve",
                    "rationale": "would have approved",
                    "evidence": [],
                    "alternatives": [],
                    "confidence": 1.0,
                    "requires_human": False,
                    "human_reason": "",
                }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "project.yaml").write_text("title: Tide\n", encoding="utf-8")
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("full_auto")
            run = store.create_autopilot_run(str(project.resolve()), mode="full_auto", runtime="opencode", policy=policy)
            service = AutopilotService({"application": {"data_root": str(root)}}, store)
            stop = threading.Event()
            handled = service._delegate_choice(
                run["run_id"],
                project,
                "character-and-world-assets",
                DelegationPolicy(policy),
                CancellingSteward(),
                {
                    "choice_id": "choice.asset.cancel",
                    "route": "character-and-world-assets",
                    "decision_type": "asset_approval",
                    "target": {"target_id": "asset"},
                    "options": [{"id": "approve"}, {"id": "revise"}],
                },
                stop=stop,
            )

            self.assertFalse(handled)
            self.assertEqual(store.delegated_decisions(run["run_id"]), [])
            events = store.autopilot_events_since(run["run_id"])
            self.assertTrue(any(item["event"] == "decision.cancelled" for item in events))

    def test_run_policy_events_and_decisions_survive_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            store = JobStore(database)
            policy = default_policy("supervised_auto")
            store.save_delegation_policy("C:/work", policy)
            run = store.create_autopilot_run("C:/work", mode=policy["mode"], runtime="opencode", policy=policy)
            decision = store.record_delegated_decision(
                run["run_id"],
                {
                    "project_root": "C:/work",
                    "decision_type": "branch_selection",
                    "selected_option": "branch-b",
                    "principal_type": "delegated-agent",
                },
            )
            restarted = JobStore(database)
            recovered = restarted.recover_autopilot_runs()
            loaded = restarted.read_autopilot_run(run["run_id"])
            self.assertEqual(recovered, 1)
            self.assertEqual(loaded["status"], "paused")
            self.assertEqual(restarted.delegated_decisions(run["run_id"])[0]["decision_id"], decision["decision_id"])
            self.assertTrue(restarted.autopilot_events_since(run["run_id"]))

    def test_resume_clears_stale_finished_timestamp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("supervised_auto")
            run = store.create_autopilot_run(str(root), mode=policy["mode"], runtime="opencode", policy=policy)
            store.update_autopilot_run(
                run["run_id"],
                status="paused",
                stop_reason="application-restart",
                finished_at="2026-01-01T00:00:00+00:00",
            )
            service = AutopilotService({"application": {"data_root": str(root)}}, store)

            with patch.object(service, "_launch") as launch:
                resumed = service.resume(run["run_id"])

            self.assertEqual(resumed["status"], "running")
            self.assertEqual(resumed["finished_at"], "")
            launch.assert_called_once_with(run["run_id"])

    def test_explicit_authorization_renewal_updates_the_paused_run_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = JobStore(root / "studio.sqlite3")
            original = default_policy("supervised_auto")
            original["limits"]["max_runtime_hours"] = 1
            run = store.create_autopilot_run(str(root), mode="supervised_auto", runtime="opencode", policy=original)
            store.update_autopilot_run(run["run_id"], status="paused", stop_reason="runtime-limit")
            service = AutopilotService({"application": {"data_root": str(root)}}, store)
            renewed = {**original, "limits": {**original["limits"], "max_runtime_hours": 12}}

            result = service.save_policy(root, renewed)

            resumed_policy = store.read_autopilot_run(run["run_id"])["policy"]
            self.assertEqual(resumed_policy["limits"]["max_runtime_hours"], 12)
            self.assertTrue(resumed_policy.get("runtime_window_started_at"))
            self.assertNotEqual(
                DelegationPolicy(resumed_policy).limit_reason({**run, "started_at": "2020-01-01T00:00:00+00:00"}),
                "runtime-limit",
            )
            self.assertEqual(result["run"]["run_id"], run["run_id"])
            events = store.autopilot_events_since(run["run_id"])
            self.assertTrue(any(event["event"] == "autopilot.authorization_updated" for event in events))

    def test_runtime_failure_recovers_complete_sandbox_before_retrying(self):
        class RecoveringWorker:
            run_calls = 0
            resume_calls = 0

            def __init__(self, config, **kwargs):
                self.config = config

            def run_once(self, project, *, route, runtime_id):
                self.__class__.run_calls += 1
                if self.__class__.run_calls == 1:
                    return WorkerRunResult(
                        "runtime_failed", project, route, "budget-task", runtime_id,
                        project / "run-budget", project / "run-budget" / "workspace", "timeout",
                    )
                return WorkerRunResult("route_ready", project, route, "", runtime_id, None, None, "路线已完成。")

            def resume_from_run(self, run_root):
                self.__class__.resume_calls += 1
                return WorkerRunResult(
                    "complete", project, "longform-planning", "budget-task", "opencode",
                    run_root, run_root / "workspace", "recovered",
                )

        class FakeRelease:
            def __init__(self, config):
                self.config = config

            def release(self, project, *, approved_by, autopilot_run_id=""):
                return {"ok": True, "manifest_path": "release.json"}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("full_auto")
            run = store.create_autopilot_run(str(project.resolve()), mode="full_auto", runtime="opencode", policy=policy)
            service = AutopilotService({"application": {"data_root": str(root)}}, store)

            with (
                patch("literary_engineering_studio.autopilot.AgentWorker", RecoveringWorker),
                patch("literary_engineering_studio.autopilot.WholeBookReleaseCoordinator", FakeRelease),
                patch("literary_engineering_studio.autopilot.current_choices", return_value={"choices": []}),
                patch("literary_engineering_studio.autopilot.ROUTE_ORDER", ("longform-planning",)),
            ):
                service._run(run["run_id"], threading.Event())

            events = store.autopilot_events_since(run["run_id"])
            self.assertEqual(store.read_autopilot_run(run["run_id"])["status"], "complete")
            self.assertEqual(RecoveringWorker.resume_calls, 1)
            self.assertTrue(any(event["event"] == "task.recovery_succeeded" for event in events))

    def test_structured_approval_choice_materializes_core_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            result = record_human_choice(
                root,
                {
                    "choice_id": "choice-asset",
                    "route": "character-and-world-assets",
                    "decision_type": "asset_approval",
                    "target": {"target_id": "character-lin"},
                    "selected": "approve",
                    "rationale": "人物动机与既有设定一致。",
                    "actor": "delegated-agent:creative-steward",
                    "materialize": True,
                },
            )
            approval = root / result["materialized"]
            self.assertTrue(approval.is_file())
            record = json.loads(approval.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(record["run_id"], "character-lin")
            self.assertEqual(record["decision"], "approve")
            self.assertEqual(record["actor"], "delegated-agent:creative-steward")

    def test_full_auto_crosses_routes_and_materializes_steward_decision(self):
        class FakeWorker:
            approval_waited = False

            def __init__(self, config, **kwargs):
                self.config = config

            def run_once(self, project, *, route, runtime_id):
                if route == "character-and-world-assets" and not self.__class__.approval_waited:
                    self.__class__.approval_waited = True
                    return WorkerRunResult(
                        "waiting_human", project, route, "asset-approval-task", runtime_id,
                        None, None, "需要批准候选人物。",
                    )
                return WorkerRunResult("route_ready", project, route, "", runtime_id, None, None, "路线已完成。")

        class FakeSteward:
            def __init__(self, config):
                self.config = config

            def decide(self, project, choice, *, project_direction="", timeout=180):
                return {
                    "selected_option": "approve",
                    "rationale": "人物设定完整且没有 canon 冲突。",
                    "evidence": [],
                    "alternatives": [],
                    "confidence": 0.9,
                    "requires_human": False,
                    "human_reason": "",
                    "principal_type": "delegated-agent",
                    "principal_id": "creative-steward",
                    "decision_type": "asset_approval",
                }

        class FakeRelease:
            calls = 0

            def __init__(self, config):
                self.config = config

            def release(self, project, *, approved_by, autopilot_run_id=""):
                self.__class__.calls += 1
                return {"ok": True, "manifest_path": "releases/whole-book/release_manifest.json"}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("full_auto")
            store.save_delegation_policy(str(project.resolve()), policy)
            run = store.create_autopilot_run(str(project.resolve()), mode="full_auto", runtime="opencode", policy=policy)
            choices = {
                "choices": [
                    {
                        "choice_id": "choice-asset-character-lin",
                        "route": "character-and-world-assets",
                        "decision_type": "asset_approval",
                        "target": {"target_id": "character-lin"},
                        "options": [
                            {"id": "approve", "label": "批准"},
                            {"id": "revise", "label": "修改"},
                        ],
                    }
                ]
            }
            service = AutopilotService({"application": {"data_root": str(root)}}, store)
            with (
                patch("literary_engineering_studio.autopilot.AgentWorker", FakeWorker),
                patch("literary_engineering_studio.autopilot.CreativeSteward", FakeSteward),
                patch("literary_engineering_studio.autopilot.WholeBookReleaseCoordinator", FakeRelease),
                patch("literary_engineering_studio.autopilot.current_choices", return_value=choices),
            ):
                service._run(run["run_id"], threading.Event())

            completed = store.read_autopilot_run(run["run_id"])
            events = store.autopilot_events_since(run["run_id"])
            self.assertEqual(completed["status"], "complete")
            self.assertEqual(FakeRelease.calls, 1)
            self.assertEqual(
                [event["data"].get("route") for event in events if event["event"] == "route.ready"],
                list(ROUTE_ORDER),
            )
            self.assertEqual(store.delegated_decisions(run["run_id"])[0]["principal_id"], "creative-steward")
            self.assertTrue((project / "workflow" / "approvals" / "character-lin.jsonl").is_file())

    def test_steward_parser_preserves_escalation(self):
        payload = _parse_decision(
            '{"selected_option":"branch-a","rationale":"因果更强","evidence":[],"alternatives":[],'
            '"confidence":0.42,"requires_human":true,"human_reason":"设定证据冲突"}'
        )
        self.assertTrue(payload["requires_human"])
        self.assertEqual(payload["human_reason"], "设定证据冲突")

    def test_steward_release_prompt_respects_explicit_delegation(self):
        prompt = _decision_prompt(
            {
                "choice_id": "release-choice",
                "route": "export-and-release",
                "decision_type": "release_approval",
                "options": [{"id": "approve"}, {"id": "revise"}],
            },
            "完成三章后交付正式版本。",
        )
        self.assertIn("already passed DelegationPolicy authorization", prompt)
        self.assertNotIn("or the decision is release approval", prompt)

    def test_proactive_steward_direction_reaches_worker_sandbox_contract(self):
        class FakeWorker:
            def __init__(self, config, **kwargs):
                self.config = config

            def run_once(self, project, *, route, runtime_id):
                return WorkerRunResult("route_ready", project, route, "", runtime_id, None, None, "路线已完成。")

        class FakeSteward:
            calls = 0

            def __init__(self, config):
                self.config = config

            def decide(self, project, choice, *, project_direction="", timeout=180):
                self.__class__.calls += 1
                return {
                    "selected_option": "fix_logic_first",
                    "rationale": "先修复因果断裂，避免文风调整掩盖结构问题。",
                    "evidence": [],
                    "alternatives": [],
                    "confidence": 0.88,
                    "requires_human": False,
                    "human_reason": "",
                    "principal_type": "delegated-agent",
                    "principal_id": "creative-steward",
                    "decision_type": "revision_direction",
                }

        class FakeRelease:
            def __init__(self, config):
                self.config = config

            def release(self, project, *, approved_by, autopilot_run_id=""):
                return {"ok": True, "manifest_path": "releases/whole-book/release_manifest.json"}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("full_auto")
            store.save_delegation_policy(str(project.resolve()), policy)
            run = store.create_autopilot_run(str(project.resolve()), mode="full_auto", runtime="opencode", policy=policy)
            choice = {
                "choice_id": "volatile-id",
                "route": "scene-development",
                "decision_type": "revision_direction",
                "title": "scene_0001 需要确认修订方向",
                "target": {"target_id": "scene_0001"},
                "source_paths": ["reviews/agent/scene_0001_scene_review.json"],
                "options": [
                    {"id": "fix_logic_first", "label": "先修因果逻辑"},
                    {"id": "fix_style_first", "label": "先修文风"},
                ],
            }
            service = AutopilotService({"application": {"data_root": str(root)}}, store)
            with (
                patch("literary_engineering_studio.autopilot.AgentWorker", FakeWorker),
                patch("literary_engineering_studio.autopilot.CreativeSteward", FakeSteward),
                patch("literary_engineering_studio.autopilot.WholeBookReleaseCoordinator", FakeRelease),
                patch("literary_engineering_studio.autopilot.current_choices", return_value={"choices": [choice]}),
            ):
                service._run(run["run_id"], threading.Event())

            self.assertEqual(FakeSteward.calls, 1)
            direction = (project / "workflow" / "studio" / "user_directions.md").read_text(encoding="utf-8")
            self.assertIn("先修因果逻辑", direction)
            decisions = store.delegated_decisions(run["run_id"])
            self.assertEqual(len(decisions), 1)
            self.assertTrue(decisions[0]["choice_fingerprint"])

    def test_whole_book_release_is_clean_and_auditable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir(parents=True)
            (root / "project.yaml").write_text("title: 潮汐之书\n", encoding="utf-8")
            chapter_bodies = [
                "海水退去，她终于看见那封信。",
                "第二次退潮时，信纸上的日期向前走了一天。",
                "灯塔熄灭以前，她把最后一页交给了港口。",
            ]
            for index, body in enumerate(chapter_bodies, start=1):
                chapter = root / "exports" / f"chapter_{index:02d}"
                chapter.mkdir(parents=True)
                (chapter / f"chapter_{index:02d}_novel.md").write_text(
                    f"# 第{index}章\n\n{body}\n\n## 世界状态变化\n\n- 不应进入正文\n",
                    encoding="utf-8",
                )
            coordinator = WholeBookReleaseCoordinator({"engine": {"python": "python", "module": "literary_engineering_studio_engine"}})
            coordinator.bridge.route_audit = lambda root, route: _Audit()
            result = coordinator.release(root, approved_by="studio-user")
            manuscript = root / result["manifest"]["outputs"]["markdown"]["path"]
            docx = root / result["manifest"]["outputs"]["docx"]["path"]
            manuscript_text = manuscript.read_text(encoding="utf-8")
            self.assertTrue(manuscript.is_file())
            self.assertTrue(docx.is_file())
            self.assertEqual(len(result["manifest"]["source_chapters"]), 3)
            self.assertEqual(
                result["manifest"]["source_chapters"],
                [f"exports/chapter_{index:02d}/chapter_{index:02d}_novel.md" for index in range(1, 4)],
            )
            self.assertTrue(all(body in manuscript_text for body in chapter_bodies))
            self.assertLess(manuscript_text.index(chapter_bodies[0]), manuscript_text.index(chapter_bodies[1]))
            self.assertLess(manuscript_text.index(chapter_bodies[1]), manuscript_text.index(chapter_bodies[2]))
            self.assertNotIn("scene_", manuscript_text)
            self.assertNotIn("世界状态变化", manuscript_text)
            self.assertNotIn("不应进入正文", manuscript_text)
            self.assertEqual(result["manifest"]["clean_delivery_checks"]["docx_inspection_warnings"], 0)

    def test_full_auto_three_chapter_direction_to_docx(self):
        class ThreeChapterWorker:
            created = False

            def __init__(self, config, **kwargs):
                self.config = config

            def run_once(self, project, *, route, runtime_id):
                if route == "scene-development" and not self.__class__.created:
                    self.__class__.created = True
                    for index, body in enumerate(
                        [
                            "退潮后，档案员在礁石间拾到第一张日志。",
                            "第二张日志写着尚未发生的失踪案。",
                            "第三次退潮时，她把证据交给了仍未失踪的人。",
                        ],
                        start=1,
                    ):
                        chapter = project / "exports" / f"chapter_{index:02d}"
                        chapter.mkdir(parents=True, exist_ok=True)
                        (chapter / f"chapter_{index:02d}_novel.md").write_text(
                            f"# 第{index}章\n\n{body}\n",
                            encoding="utf-8",
                        )
                return WorkerRunResult("route_ready", project, route, "", runtime_id, None, None, "路线已完成。")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "project.yaml").write_text("title: 潮声档案\n", encoding="utf-8")
            direction = "写一部三章悬疑小说：不存在的航海日志每天在退潮后出现。"
            record_direction(project, direction, actor="studio-user")
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("full_auto")
            store.save_delegation_policy(str(project.resolve()), policy)
            run = store.create_autopilot_run(str(project.resolve()), mode="full_auto", runtime="opencode", policy=policy)
            service = AutopilotService({"application": {"data_root": str(root)}}, store)

            with (
                patch("literary_engineering_studio.autopilot.AgentWorker", ThreeChapterWorker),
                patch("literary_engineering_studio.autopilot.current_choices", return_value={"choices": []}),
                patch("literary_engineering_studio.whole_book_release.CoreBridge.route_audit", return_value=_Audit()),
            ):
                service._run(run["run_id"], threading.Event())

            completed = store.read_autopilot_run(run["run_id"])
            manifest_path = project / "releases" / "whole-book" / "release_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manuscript = project / manifest["outputs"]["markdown"]["path"]
            docx = project / manifest["outputs"]["docx"]["path"]
            self.assertEqual(completed["status"], "complete")
            self.assertEqual(len(manifest["source_chapters"]), 3)
            self.assertTrue(docx.is_file())
            self.assertIn(direction, (project / "workflow" / "studio" / "user_directions.md").read_text(encoding="utf-8"))
            self.assertEqual(manuscript.read_text(encoding="utf-8").count("退潮"), 2)

    def test_scene_route_yields_to_pending_character_asset_then_resumes(self):
        class DependencyWorker:
            calls = []

            def __init__(self, config, **kwargs):
                self.config = config

            def run_once(self, project, *, route, runtime_id):
                self.__class__.calls.append(route)
                status = "complete" if route == "scene-development" and len(self.__class__.calls) == 1 else "route_ready"
                return WorkerRunResult(status, project, route, f"{route}-task", runtime_id, None, None, "ok")

        class FakeRelease:
            def __init__(self, config):
                self.config = config

            def release(self, project, *, approved_by, autopilot_run_id=""):
                return {"ok": True}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("full_auto")
            run = store.create_autopilot_run(str(project.resolve()), mode="full_auto", runtime="opencode", policy=policy)
            service = AutopilotService({"application": {"data_root": str(root)}}, store)

            with (
                patch("literary_engineering_studio.autopilot.AgentWorker", DependencyWorker),
                patch("literary_engineering_studio.autopilot.WholeBookReleaseCoordinator", FakeRelease),
                patch("literary_engineering_studio.autopilot.current_choices", return_value={"choices": []}),
                patch("literary_engineering_studio.autopilot.ROUTE_ORDER", ("scene-development",)),
                patch("literary_engineering_studio.autopilot._pending_asset_dependency", side_effect=[False, True, False]),
            ):
                service._run(run["run_id"], threading.Event())

            self.assertEqual(DependencyWorker.calls, ["scene-development", "character-and-world-assets", "scene-development"])
            events = store.autopilot_events_since(run["run_id"])
            self.assertTrue(any(event["event"] == "route.dependency_entered" for event in events))
            self.assertTrue(any(event["event"] == "route.dependency_ready" for event in events))


if __name__ == "__main__":
    unittest.main()
