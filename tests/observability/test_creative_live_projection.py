from __future__ import annotations

import unittest
import json
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from literary_engineering_studio.observability.creative_live.projector import (
    project_runtime_event,
)
from literary_engineering_studio.observability.creative_live.snapshot import (
    SNAPSHOT_SCHEMA,
    build_creative_live_snapshot,
)
from literary_engineering_studio.observability.creative_live.artifact_revisions import (
    artifact_revisions,
)


class CreativeLiveProjectionTests(unittest.TestCase):
    def test_projects_prose_preview_without_promoting_it(self):
        event = project_runtime_event(
            {
                "sequence": 4,
                "event": "artifact.preview.delta",
                "at": "2026-08-31T00:00:00+00:00",
                "data": {
                    "runtime_event_id": "event-4",
                    "run_id": "run-1",
                    "session_id": "session-1",
                    "task_id": "scene-0001-prose",
                    "route": "scene-development",
                    "attempt_id": "attempt-1",
                    "path": "drafts/scenes/scene_0001.md",
                    "kind": "prose",
                    "format": "markdown",
                    "identity": "streaming_preview",
                    "revision": 1,
                    "delta": "第一段。",
                    "characters": 4,
                },
            },
            ".",
        )

        self.assertEqual(event["channel"], "artifact")
        self.assertEqual(event["artifact"]["identity"], "streaming_preview")
        self.assertIn("尚未成为正式正文", event["data"]["message"])

    def test_snapshot_reduces_deltas_and_checkpoints(self):
        raw = [
            _raw(1, "artifact.preview.delta", {"delta": "第一段。", "characters": 4}),
            _raw(2, "artifact.preview.delta", {"delta": "第二段。", "characters": 8}),
            _raw(
                3,
                "artifact.checkpoint.written",
                {
                    "identity": "candidate_written",
                    "characters": 8,
                    "sha256": "a" * 64,
                    "validation_passed": True,
                },
            ),
        ]

        snapshot = build_creative_live_snapshot(
            ".",
            raw,
            run={
                "run_id": "run-1",
                "status": "running",
                "current_task_id": "scene-0001-prose",
                "current_route": "scene-development",
            },
        )

        self.assertEqual(snapshot["schema"], SNAPSHOT_SCHEMA)
        self.assertEqual(snapshot["status"], "active")
        self.assertEqual(len(snapshot["artifacts"]), 1)
        self.assertEqual(snapshot["artifacts"][0]["content"], "第一段。第二段。")
        self.assertEqual(snapshot["artifacts"][0]["identity"], "candidate_written")

    def test_snapshot_tolerates_legacy_redacted_usage_metrics(self):
        snapshot = build_creative_live_snapshot(
            ".",
            [
                {
                    "sequence": 1,
                    "event": "usage.updated",
                    "at": "2026-08-31T00:00:00+00:00",
                    "data": {
                        "runtime_event_id": "usage-1",
                        "usage": {"total_tokens": "[REDACTED]"},
                        "cost_usd": "[REDACTED]",
                    },
                }
            ],
        )

        self.assertEqual(snapshot["usage"], {"total_tokens": 0, "cost_usd": 0.0, "updates": 1})

    def test_projection_redacts_credentials_and_host_paths(self):
        event = project_runtime_event(
            {
                "sequence": 1,
                "event": "runner.warning",
                "at": "2026-08-31T00:00:00+00:00",
                "data": {
                    "api_key": "sk-this-is-a-real-looking-secret-value",
                    "detail": "failed at C:\\Users\\Private\\secret.json",
                },
            },
            ".",
        )

        self.assertEqual(event["data"]["api_key"], "<redacted>")
        self.assertNotIn("Users", event["data"]["detail"])

    def test_revision_history_uses_real_snapshots_and_produces_a_diff(self):
        raw = [
            _raw(1, "artifact.preview.snapshot", {"content": "第一版。", "replace": True}),
            _raw(
                2,
                "artifact.preview.snapshot",
                {"content": "第二版。\n增加一段。", "replace": True, "revision": 2, "finding_refs": ["style-1"]},
            ),
        ]
        projected = project_runtime_event(raw[0], ".")
        revisions = artifact_revisions(".", raw, projected["artifact"]["artifact_id"])

        self.assertEqual(len(revisions), 2)
        self.assertIn("第二版", revisions[1]["diff"])
        self.assertEqual(revisions[1]["finding_refs"], ["style-1"])

    def test_mutation_receipt_promotes_only_formal_effects(self):
        event = project_runtime_event(
            {
                "sequence": 8,
                "event": "mutation.receipt",
                "at": "2026-08-31T00:00:08+00:00",
                "data": {
                    "runtime_event_id": "receipt-8",
                    "attempt_id": "attempt-1",
                    "receipt": {
                        "target": "drafts/scenes/scene_0001.md",
                        "action": "formal_promoted",
                        "formal_effect": "formal",
                        "preflight_status": "pass",
                        "result_sha256": "b" * 64,
                    },
                },
            },
            ".",
        )

        self.assertEqual(event["artifact"]["identity"], "promoted")
        self.assertEqual(event["channel"], "artifact")

    def test_exact_review_digest_advances_only_the_matching_candidate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            review_path = root / "reviews" / "agent" / "scene_0001_scene_review.json"
            review_path.parent.mkdir(parents=True)
            review_path.write_text(json.dumps({
                "schema": "scene_review.v1",
                "scene_id": "scene_0001",
                "candidate_sha256": "a" * 64,
                "conclusion": "pass",
                "summary": "人物选择与当前设定一致。",
                "findings": [],
            }), encoding="utf-8")
            raw = [
                _raw(1, "artifact.checkpoint.written", {
                    "identity": "candidate_written", "sha256": "a" * 64,
                }),
                _raw(2, "artifact.checkpoint.written", {
                    "path": "reviews/agent/scene_0001_scene_review.json",
                    "kind": "review", "format": "json", "identity": "candidate_written",
                    "sha256": "b" * 64,
                }),
            ]

            snapshot = build_creative_live_snapshot(root, raw)
            candidate = next(item for item in snapshot["artifacts"] if item["path"].startswith("drafts/"))

            self.assertEqual(candidate["identity"], "semantic_review_passed")
            self.assertEqual(snapshot["reviews"][0]["status"], "pass")
            self.assertEqual(snapshot["reviews"][0]["message"], "人物选择与当前设定一致。")

    def test_snapshot_hydrates_a_readable_project_artifact_after_reconnect(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "characters" / "protagonist-foundation.md"
            path.parent.mkdir(parents=True)
            content = "# 林遥\n\n她在城市停电后仍坚持寻找失踪的妹妹。"
            path.write_text(content, encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            raw = [_raw(1, "artifact.checkpoint.written", {
                "path": "characters/protagonist-foundation.md",
                "kind": "character",
                "sha256": digest,
                "identity": "candidate_written",
            })]

            snapshot = build_creative_live_snapshot(root, raw)

            self.assertEqual(len(snapshot["artifacts"]), 1)
            self.assertEqual(snapshot["artifacts"][0]["content"], content)
            self.assertEqual(snapshot["artifacts"][0]["kind"], "character")

    def test_snapshot_does_not_hydrate_stale_or_machine_artifacts(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            readable = root / "plot" / "story.md"
            machine = root / "plot" / "story.agent_completion.json"
            readable.parent.mkdir(parents=True)
            readable.write_text("current content", encoding="utf-8")
            machine.write_text('{"complete": true}', encoding="utf-8")
            raw = [
                _raw(1, "artifact.checkpoint.written", {
                    "path": "plot/story.md", "kind": "planning", "sha256": "f" * 64,
                }),
                _raw(2, "artifact.checkpoint.written", {
                    "path": "plot/story.agent_completion.json", "kind": "planning",
                }),
            ]

            snapshot = build_creative_live_snapshot(root, raw)

            self.assertEqual([item["path"] for item in snapshot["artifacts"]], ["plot/story.md"])
            self.assertEqual(snapshot["artifacts"][0]["content"], "")

    def test_snapshot_excludes_protocol_noise_and_restores_completed_message(self):
        raw = [
            {
                "sequence": 1,
                "event": "runner.warning",
                "at": "2026-08-31T00:00:01+00:00",
                "data": {
                    "runtime_event_id": "warning-1",
                    "run_id": "run-1",
                    "session_id": "session-1",
                    "task_id": "task-1",
                    "route": "longform-planning",
                    "kind": "worker_protocol",
                    "detail": "unknown worker event omitted",
                },
            },
            {
                "sequence": 2,
                "event": "agent.message.completed",
                "at": "2026-08-31T00:00:02+00:00",
                "data": {
                    "runtime_event_id": "message-2",
                    "run_id": "run-1",
                    "session_id": "session-1",
                    "task_id": "task-1",
                    "route": "longform-planning",
                    "text": "人物设定已经完成，正在进入审查。",
                },
            },
        ]

        snapshot = build_creative_live_snapshot(
            ".",
            raw,
            run={"status": "running", "current_task_id": "task-1", "current_route": "longform-planning"},
        )

        self.assertFalse(any(item["event"] == "runner.warning" for item in snapshot["activity"]))
        self.assertEqual(snapshot["sessions"][0]["transcript"], "人物设定已经完成，正在进入审查。")
        self.assertNotEqual(snapshot["active_task"]["last_event"], "runner.warning")

    def test_paused_controller_overrides_stale_running_session(self):
        snapshot = build_creative_live_snapshot(
            ".",
            [],
            sessions=[{
                "session_id": "session-1",
                "controller_id": "run-1",
                "status": "running",
                "route": "scene-development",
                "task_id": "scene-1",
            }],
            run={
                "run_id": "run-1",
                "status": "paused",
                "current_route": "scene-development",
                "current_task_id": "scene-1",
                "last_error": "自动创作已暂停。",
            },
        )

        self.assertEqual(snapshot["status"], "paused")
        self.assertEqual(snapshot["sessions"][0]["status"], "paused")
        self.assertEqual(snapshot["active_task"]["message"], "自动创作已暂停。")


def _raw(sequence: int, event: str, changes: dict) -> dict:
    return {
        "sequence": sequence,
        "event": event,
        "at": f"2026-08-31T00:00:0{sequence}+00:00",
        "data": {
            "runtime_event_id": f"event-{sequence}",
            "run_id": "run-1",
            "session_id": "session-1",
            "task_id": "scene-0001-prose",
            "route": "scene-development",
            "attempt_id": "attempt-1",
            "path": "drafts/scenes/scene_0001.md",
            "kind": "prose",
            "format": "markdown",
            "identity": "streaming_preview",
            "revision": 1,
            **changes,
        },
    }


if __name__ == "__main__":
    unittest.main()
