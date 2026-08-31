from __future__ import annotations

import json
from pathlib import Path
import unittest

from literary_engineering_studio.observability.creative_live.contracts import (
    ARTIFACT_IDENTITIES,
    CHANNELS,
    CREATIVE_LIVE_SCHEMA,
    VISIBILITIES,
    ArtifactIdentity,
    CreativeLiveEvent,
    EventChannel,
    EventVisibility,
    artifact_id,
    project_channel,
)
from literary_engineering_studio.observability.event_policy import (
    EventDurability,
    classify_runtime_event,
)


ROOT = Path(__file__).resolve().parents[2]


class CreativeLiveContractTests(unittest.TestCase):
    def test_protocol_schema_matches_runtime_enums(self):
        schema = json.loads(
            (ROOT / "protocol/observability/creative-live-event.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(schema["$id"], CREATIVE_LIVE_SCHEMA)
        self.assertEqual(set(schema["properties"]["channel"]["enum"]), CHANNELS)
        self.assertEqual(set(schema["properties"]["visibility"]["enum"]), VISIBILITIES)
        identities = schema["properties"]["artifact"]["properties"]["identity"]["enum"]
        self.assertEqual(set(identities), ARTIFACT_IDENTITIES)

    def test_event_keeps_formal_identity_explicit(self):
        event = CreativeLiveEvent.create(
            event="artifact.preview.snapshot",
            channel=EventChannel.ARTIFACT,
            visibility=EventVisibility.USER,
            durability="ephemeral",
            sequence=7,
            project_id="project-1",
            run_id="run-1",
            session_id="session-1",
            task_id="scene-1-prose",
            route="scene-development",
            attempt_id="attempt-2",
            artifact={
                "artifact_id": "artifact-1",
                "path": "candidates/scene_0001.md",
                "kind": "prose",
                "format": "markdown",
                "identity": ArtifactIdentity.STREAMING_PREVIEW.value,
                "revision": 2,
            },
            data={"content": "第一段。"},
        ).as_dict()

        self.assertEqual(event["schema"], CREATIVE_LIVE_SCHEMA)
        self.assertEqual(event["artifact"]["identity"], "streaming_preview")
        self.assertEqual(event["attempt_id"], "attempt-2")

    def test_project_and_artifact_channels_are_stable(self):
        root = ROOT / "examples" / "sample"
        self.assertEqual(project_channel(root), project_channel(root))
        self.assertEqual(
            artifact_id("project-1", "drafts/scene.md", "attempt-1"),
            artifact_id("project-1", "drafts/scene.md", "attempt-1"),
        )

    def test_artifact_preview_events_are_ephemeral(self):
        self.assertIs(
            classify_runtime_event("artifact.preview.delta"),
            EventDurability.EPHEMERAL,
        )
        self.assertIs(
            classify_runtime_event("worker.artifact.preview.snapshot"),
            EventDurability.EPHEMERAL,
        )


if __name__ == "__main__":
    unittest.main()
