from __future__ import annotations

import unittest

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
