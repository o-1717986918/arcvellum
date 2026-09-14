from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.project_agent.actions import dependencies_from_actions


class _Autopilot:
    def __init__(self):
        self.run = None
        self.authorized = None
        self.current_policy = {"literary_kernel": "strict-v1"}

    def policy(self, _root):
        return {"policy": dict(self.current_policy)}

    def migrate_kernel(self, _root, *, target_kernel):
        self.current_policy["literary_kernel"] = target_kernel
        return {"policy": dict(self.current_policy)}

    def start(self, root):
        self.run = {
            "run_id": "run-1",
            "project_root": str(root),
            "status": "running",
            "policy": dict(self.current_policy),
        }
        return self.run

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


if __name__ == "__main__":
    unittest.main()
