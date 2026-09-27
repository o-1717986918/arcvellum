from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.project_agent.actions import dependencies_from_actions
from literary_engineering_studio_engine.public.literary import save_actor_persona


class _Autopilot:
    def __init__(self):
        self.run = None
        self.authorized = None
        self.current_policy = {"literary_kernel": "strict-v1"}
        self.managed_goals = []

    def policy(self, _root):
        return {"policy": dict(self.current_policy)}

    def migrate_kernel(self, _root, *, target_kernel):
        self.current_policy["literary_kernel"] = target_kernel
        return {"policy": dict(self.current_policy)}

    def save_policy(self, _root, payload):
        self.current_policy = {**self.current_policy, **payload}
        result = {"policy": dict(self.current_policy)}
        if self.run is not None and self.run["status"] in {"paused", "blocked", "failed"}:
            self.run = {**self.run, "policy": dict(self.current_policy)}
            result["run"] = self.run
        return result

    def start(self, root):
        self.run = {
            "run_id": "run-1",
            "project_root": str(root),
            "status": "running",
            "policy": dict(self.current_policy),
        }
        return self.run

    def start_managed_goal(self, root, policy):
        self.managed_goals.append((root, dict(policy)))
        self.save_policy(root, policy)
        return self.start(root)

    def status(self, _root):
        return {"ok": True, "run": self.run}

    def pause(self, run_id, *, reason):
        self.run = {**self.run, "run_id": run_id, "status": "paused", "stop_reason": reason}
        return self.run

    def resume(self, run_id, *, authorized):
        self.authorized = authorized
        self.run = {**self.run, "run_id": run_id, "status": "running"}
        return self.run


class _StyleMounts:
    def preview(self, _root, **_identity):
        return {"revision": "preview-1"}

    def mount_confirmed(self, _root, **arguments):
        return {"status": "mounted", "impact": {"stale": 2}, **arguments}


class _CandidatePromotions:
    def detail(self, _root, candidate_id):
        return {"candidate_id": candidate_id, "preview_digest": "sha256:preview"}

    def worker_request(self, _root, candidate_id, *, preview_digest):
        return {
            "project_root": "C:/work",
            "route": "character-and-world-assets",
            "runtime": "pi-worker",
            "scene": candidate_id,
            "task_id": "",
            "idempotency_key": preview_digest,
        }


class ProjectAgentActionTests(unittest.TestCase):
    def test_actor_persona_update_uses_engine_service_and_returns_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            characters = root / "characters"
            characters.mkdir()
            (characters / "lin.yaml").write_text(
                "character_id: character/lin\nname: 林\n", encoding="utf-8"
            )
            invalidations = []
            actions = dependencies_from_actions(
                record_direction=lambda *_args, **_kwargs: {}, autopilot=_Autopilot(),
                save_actor_persona=save_actor_persona,
                invalidate_project=lambda path, reason: invalidations.append((path, reason)),
            )
            sections = {
                "PERSONA_LOAD": ["SELF_CLAIM_LIN"], "PERSONALITY_CORE": ["TRAIT_RESTLESS"],
                "PERSONALITY_PUBLIC": ["TRAIT_WITTY"], "LANGUAGE_STYLE": ["POLISHED"],
                "LITERATURE_STYLE": ["ABSURDITY_STYLE"],
            }
            result = actions.update_actor_persona(root, {"character_id": "character/lin", "sections": sections})
            self.assertEqual(result["profile"]["sections"], sections)
            self.assertEqual(result["effect"], "future-scene-transactions")
            self.assertTrue(result["receipt"]["token"])
            self.assertEqual(invalidations, [(root, "project-agent-actor-persona")])

    def test_profile_only_rhythm_update_preserves_current_scene_entries(self):
        current = [
            {"scene_id": "scene_0001", "rhythm_role": "setup", "source": "rhythm-plan"},
            {"scene_id": "scene_0002", "rhythm_role": "escalation", "source": "scene-yaml"},
        ]
        captured = []
        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {}, autopilot=_Autopilot(),
            load_rhythm=lambda _root: {"entries": current},
            save_rhythm=lambda _root, entries, **kwargs: captured.append((entries, kwargs)) or {"digest": "new"},
        )
        result = actions.update_rhythm(Path("C:/work"), {"book_profile": {"directive": "新的章序"}})
        self.assertEqual(captured[0][0], current[:1])
        self.assertEqual(captured[0][1]["book_profile"], {"directive": "新的章序"})
        self.assertEqual(result["plan"]["digest"], "new")

    def test_chapter_extension_is_a_scoped_domain_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls = []
            actions = dependencies_from_actions(
                record_direction=lambda *_args, **_kwargs: {}, autopilot=_Autopilot(),
                extend_chapter=lambda project, **kwargs: calls.append((project, kwargs)) or {
                    "chapter_id": kwargs["chapter_id"], "appended_scene_ids": ["scene_0007"],
                },
            )
            result = actions.extend_chapter(root, {
                "chapter_id": "chapter_0002", "additional_scenes": 1,
                "target_per_scene": 3300, "direction": "承接已晋升末场",
            })
            self.assertEqual(calls[0][0], root)
            self.assertEqual(calls[0][1]["additional_scenes"], 1)
            self.assertEqual(result["appended_scene_ids"], ["scene_0007"])
            self.assertTrue(result["receipt"]["token"])

    def test_planned_scene_without_formal_prose_uses_lean_kernel(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\n", encoding="utf-8",
            )
            autopilot = _Autopilot()
            actions = dependencies_from_actions(
                record_direction=lambda *_args, **_kwargs: {},
                autopilot=autopilot,
            )
            result = actions.manage_goal(root, {"operation": "start", "objective": "续写这一章"})
            self.assertEqual(result["run"]["policy"]["literary_kernel"], "lean-v2")
            self.assertEqual(autopilot.managed_goals[0][1]["literary_kernel"], "lean-v2")

    def test_creation_control_accepts_a_planned_scene_without_formal_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
            autopilot = _Autopilot()
            autopilot.current_policy["literary_kernel"] = "lean-v2"
            actions = dependencies_from_actions(
                record_direction=lambda *_args, **_kwargs: {}, autopilot=autopilot,
            )

            result = actions.creation_control(root, {"operation": "start"})

            self.assertEqual(result["literary_kernel"], "lean-v2")
            self.assertEqual(result["run"]["status"], "running")

    def test_unreceipted_scene_delta_remains_a_historical_formal_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            delta = root / "workflow" / "scene_deltas" / "scene_0001.json"
            delta.parent.mkdir(parents=True)
            delta.write_text("{}", encoding="utf-8")
            autopilot = _Autopilot()
            autopilot.current_policy["literary_kernel"] = "lean-v2"
            actions = dependencies_from_actions(
                record_direction=lambda *_args, **_kwargs: {}, autopilot=autopilot,
            )

            with self.assertRaisesRegex(ValueError, "历史正式正文"):
                actions.manage_goal(root, {"operation": "start", "objective": "续写"})

    def test_historical_formal_prose_keeps_strict_kernel(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("旧正式正文", encoding="utf-8")
            autopilot = _Autopilot()
            actions = dependencies_from_actions(
                record_direction=lambda *_args, **_kwargs: {}, autopilot=autopilot,
            )

            result = actions.manage_goal(root, {"operation": "start", "objective": "续写这一章"})

            self.assertEqual(result["run"]["policy"]["literary_kernel"], "strict-v1")

    def test_lean_with_unmigrated_prose_rejects_without_recording_direction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("旧正式正文", encoding="utf-8")
            autopilot = _Autopilot()
            autopilot.current_policy["literary_kernel"] = "lean-v2"
            recorded = []
            actions = dependencies_from_actions(
                record_direction=lambda *_args, **_kwargs: recorded.append(True) or {},
                autopilot=autopilot,
            )

            with self.assertRaisesRegex(ValueError, "历史正式正文"):
                actions.manage_goal(root, {"operation": "start", "objective": "续写这一章"})
            self.assertEqual(recorded, [])

    def test_planning_prepare_reuses_standard_service_without_starting_autopilot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8",
            )
            autopilot = _Autopilot()
            autopilot.current_policy["literary_kernel"] = "lean-v2"
            prepared = []
            actions = dependencies_from_actions(
                record_direction=lambda *_args, **_kwargs: {}, autopilot=autopilot,
                prepare_plan=lambda project: prepared.append(project) or {
                    "chapters": [{"chapter_id": "chapter_0001"}],
                    "scenes": [{"scene_id": "scene_0001"}],
                },
            )

            result = actions.prepare_plan(root, {})

            self.assertEqual(result["status"], "prepared")
            self.assertEqual(result["scene_ids"], ["scene_0001"])
            self.assertFalse(result["autopilot_started"])
            self.assertIsNone(autopilot.run)
            self.assertEqual(prepared, [root])

    def test_planning_prepare_rejects_genuine_unmigrated_formal_prose(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("旧正式正文", encoding="utf-8")
            prepared = []
            actions = dependencies_from_actions(
                record_direction=lambda *_args, **_kwargs: {}, autopilot=_Autopilot(),
                prepare_plan=lambda project: prepared.append(project) or {},
            )

            with self.assertRaisesRegex(ValueError, "历史正式正文"):
                actions.prepare_plan(root, {})
            self.assertEqual(prepared, [])

    def test_actions_reuse_direction_and_autopilot_services(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorded = []
            autopilot = _Autopilot()
            actions = dependencies_from_actions(
                record_direction=lambda project, message, actor: recorded.append(
                    (project, message, actor)
                ) or {"record": {"message": message, "actor": actor}, "digest": "directions.md"},
                autopilot=autopilot,
            )

            direction = actions.record_direction(root, {"message": "保留开放结局"})
            started = actions.creation_control(root, {"operation": "start"})
            resumed = actions.creation_control(root, {"operation": "resume"})

            self.assertEqual(recorded[0], (root, "保留开放结局", "project-agent"))
            self.assertEqual(direction["operation"], "record_direction")
            self.assertEqual(started["run"]["status"], "running")
            self.assertEqual(resumed["run"]["status"], "running")
            self.assertTrue(autopilot.authorized)
            self.assertEqual(started["literary_kernel"], "lean-v2")
            self.assertTrue(direction["receipt"]["token"])

    def test_control_requires_an_existing_run(self):
        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {},
            autopilot=_Autopilot(),
        )
        with self.assertRaisesRegex(ValueError, "existing creation run"):
            actions.creation_control(Path("."), {"operation": "pause"})

    def test_domain_actions_reuse_existing_services_without_user_approval(self):
        autopilot = _Autopilot()
        autopilot.run = {
            "run_id": "run-2",
            "status": "paused",
            "stop_reason": "human-decision-required",
            "policy": {"literary_kernel": "lean-v2"},
        }
        captured = {}

        def record_decision(_config, _root, payload):
            captured["choice"] = payload
            return {"consumed": True, "effect": {"summary": "已选择 B"}}

        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {},
            autopilot=autopilot,
            config={"application": {"name": "ArcVellum"}},
            current_choices=lambda _config, _root: {
                "choices": [{
                    "choice_id": "choice-1",
                    "options": [{"id": "branch-b", "label": "选择 B"}],
                }],
            },
            record_choice=record_decision,
            save_quality=lambda _root, profile, **_kwargs: {**profile, "digest": "quality-1"},
            save_rhythm=lambda _root, entries, **_kwargs: {"entries": entries, "digest": "rhythm-1"},
            style_mounts=_StyleMounts(),
            candidate_promotions=_CandidatePromotions(),
            launch_worker=lambda request: {
                "job_id": "job-promotion",
                "status": "queued",
                "request": request,
            },
        )

        decision = actions.resolve_decision(Path("."), {
            "choice_id": "choice-1",
            "selected": "branch-b",
            "rationale": "B 分支保留更强的因果压力。",
        })
        quality = actions.update_quality(Path("."), {"profile": {"punctuation": {"dash": 0.02}}})
        rhythm = actions.update_rhythm(Path("."), {"entries": [{"chapter": "chapter_01"}]})
        style = actions.mount_style(Path("."), {
            "style_id": "plain-prose",
            "version_id": "v1",
            "content_hash": "sha256:12345678",
        })
        promotion = actions.promote_asset(Path("."), {"candidate_id": "character-lin-che"})

        self.assertTrue(decision["consumed"])
        self.assertTrue(autopilot.authorized)
        self.assertEqual(captured["choice"]["actor"], "project-agent")
        self.assertEqual(quality["profile"]["digest"], "quality-1")
        self.assertEqual(rhythm["plan"]["digest"], "rhythm-1")
        self.assertEqual(style["status"], "mounted")
        self.assertEqual(promotion["job_id"], "job-promotion")

    def test_long_running_goal_uses_full_auto_lean_kernel_and_can_recover(self):
        root = Path("C:/work")
        recorded = []
        autopilot = _Autopilot()
        actions = dependencies_from_actions(
            record_direction=lambda project, message, actor: recorded.append((project, message, actor)) or {},
            autopilot=autopilot,
            current_choices=lambda _config, _root: {"choices": []},
            goal_evidence=lambda _root: {
                "unit_count": 3,
                "total_chinese_content_chars": 5281,
                "units": [{}, {}, {}],
            },
        )

        started = actions.manage_goal(root, {
            "operation": "start",
            "objective": "完成全书并通过交付门禁",
            "stop_after_formal_units": 5,
        })
        autopilot.run = {**autopilot.run, "status": "blocked", "stop_reason": "runtime-failure"}
        recovered = actions.manage_goal(root, {"operation": "recover"})

        self.assertEqual(recorded[0], (root, "长期创作目标：完成全书并通过交付门禁", "project-agent"))
        self.assertEqual(autopilot.current_policy["mode"], "full_auto")
        self.assertEqual(autopilot.current_policy["literary_kernel"], "lean-v2")
        self.assertEqual(autopilot.current_policy["release_policy"], "delegated")
        self.assertTrue(autopilot.current_policy["editorial_scene_checkpoint"])
        self.assertEqual(autopilot.current_policy["limits"]["stop_after_formal_units"], 5)
        self.assertEqual(len(autopilot.managed_goals), 1)
        self.assertEqual(started["run"]["status"], "running")
        self.assertEqual(started["receipt"]["run_id"], "run-1")
        self.assertEqual(started["receipt"]["run_status"], "running")
        self.assertEqual(started["receipt"]["operation"], "goal_start")
        self.assertEqual(recovered["run"]["status"], "running")
        self.assertEqual(recovered["formal_work"]["unit_count"], 3)
        self.assertEqual(recovered["formal_work"]["chinese_content_chars"], 5281)
        self.assertNotEqual(
            recovered["formal_work"]["unit_count"],
            int(recovered["run"].get("tasks_completed") or 0),
        )

    def test_long_running_goal_defers_to_pending_literary_decision(self):
        autopilot = _Autopilot()
        autopilot.run = {
            "run_id": "run-2",
            "status": "blocked",
            "stop_reason": "decision",
            "mode": "full_auto",
            "policy": {
                "mode": "full_auto",
                "literary_kernel": "lean-v2",
                "release_policy": "delegated",
            },
        }
        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {},
            autopilot=autopilot,
            current_choices=lambda _config, _root: {"choices": [{"choice_id": "branch-1"}]},
        )

        result = actions.manage_goal(Path("C:/work"), {"operation": "recover"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "decision_required")
        self.assertEqual(result["recommended_tool"], "project_decision_resolve")

    def test_resume_updates_formal_scene_checkpoint_before_running(self):
        root = Path("C:/work")
        autopilot = _Autopilot()
        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {}, autopilot=autopilot,
        )
        actions.manage_goal(root, {
            "operation": "start", "objective": "完成全书", "stop_after_formal_units": 0,
        })
        autopilot.pause("run-1", reason="user-request")

        result = actions.manage_goal(root, {
            "operation": "resume", "stop_after_formal_units": 7,
        })

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["run"]["policy"]["limits"]["stop_after_formal_units"], 7)
        self.assertEqual(autopilot.current_policy["limits"]["stop_after_formal_units"], 7)

    def test_checkpoint_mismatch_does_not_change_formal_scene_limit(self):
        root = Path("C:/work")
        autopilot = _Autopilot()
        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {}, autopilot=autopilot,
        )
        actions.manage_goal(root, {
            "operation": "start", "objective": "完成全书", "stop_after_formal_units": 5,
        })
        autopilot.pause("run-1", reason="controller-error")

        result = actions.manage_goal(root, {
            "operation": "recover", "expected_stop_reason": "goal-scope-complete",
            "stop_after_formal_units": 7,
        })

        self.assertEqual(result["status"], "checkpoint_changed")
        self.assertEqual(autopilot.current_policy["limits"]["stop_after_formal_units"], 5)
        self.assertIsNone(autopilot.authorized)

    def test_checkpoint_recover_preserves_newer_user_pause(self):
        autopilot = _Autopilot()
        autopilot.run = {
            "run_id": "run-checkpoint", "status": "paused", "stop_reason": "user-request",
            "mode": "full_auto",
            "policy": {"mode": "full_auto", "literary_kernel": "lean-v2", "release_policy": "delegated"},
        }
        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {}, autopilot=autopilot,
        )

        result = actions.manage_goal(Path("C:/work"), {
            "operation": "recover", "expected_stop_reason": "scene-editorial-checkpoint",
        })

        self.assertEqual(result["status"], "checkpoint_changed")
        self.assertIsNone(autopilot.authorized)

    def test_old_non_goal_run_is_not_resumed_without_a_new_objective(self):
        autopilot = _Autopilot()
        autopilot.run = {
            "run_id": "run-old",
            "status": "paused",
            "mode": "collaborative",
            "policy": {"mode": "collaborative", "literary_kernel": "strict-v1"},
        }
        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {},
            autopilot=autopilot,
        )

        result = actions.manage_goal(Path("C:/work"), {"operation": "recover"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "goal_objective_required")
        self.assertIsNone(autopilot.authorized)

    def test_agent_can_create_a_work_through_the_project_service(self):
        created = []

        def create_project(**arguments):
            created.append(arguments)
            return {
                "path": "C:/Works/tide",
                "title": arguments["title"],
                "work_type": arguments["work_type"],
                "status": "planning",
            }

        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {},
            autopilot=_Autopilot(),
            create_project=create_project,
        )

        result = actions.create_project(Path("C:/Works"), {
            "title": "潮汐之后",
            "target_length": 120000,
            "genre": "现实主义",
        })

        self.assertTrue(result["ok"])
        self.assertEqual(result["work"]["title"], "潮汐之后")
        self.assertTrue(result["work"]["work_id"].startswith("work-"))
        self.assertEqual(created[0]["target_length"], 120000)


if __name__ == "__main__":
    unittest.main()
