from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.context_broker import context_trace_status
from literary_engineering_studio_engine.context_packet import build_context_packet
from literary_engineering_studio_engine.literary.review.scene_agent import (
    review_scene_with_agent,
)
from literary_engineering_studio_engine.literary.scene.composition.composer import (
    build_scene_composition,
)
from literary_engineering_studio_engine.literary.scene.generation_provider import (
    generate_scene_candidate,
)
from literary_engineering_studio_engine.literary.scene.promotion.candidate import (
    candidate_generation_gate,
    candidate_review_gate,
)
from literary_engineering_studio_engine.literary.scene.promotion.revision import (
    build_scene_revision_task,
)
from literary_engineering_studio_engine.literary.style.mount import (
    mount_style_profile_version,
)
from literary_engineering_studio_engine.literary.style.version import (
    build_style_profile_version,
)
from tests.test_style_profile_version import _formal_reviewed_profile


class StyleMountSceneChainTests(unittest.TestCase):
    def test_scene_chain_uses_one_exact_snapshot_and_switch_marks_it_stale(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            self._write_scene_fixture(root)
            first_version = build_style_profile_version(
                root,
                profile,
                target_id=target_id,
            )
            semantic_review = (
                profile
                / "evaluation_results"
                / "formal"
                / "style_semantic_review.json"
            )
            review_payload = self._payload(semantic_review)
            review_payload["summary"] = (
                str(review_payload.get("summary") or "")
                + " 第二版本补充对场景衔接的约束。"
            )
            semantic_review.write_text(
                json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            second_version = build_style_profile_version(
                root,
                profile,
                target_id=target_id,
            )
            self.assertNotEqual(
                second_version.content_hash,
                first_version.content_hash,
            )

            mount_style_profile_version(
                root,
                style_id=first_version.style_id,
                version_id=first_version.version_id,
                content_hash=first_version.content_hash,
            )

            context = build_context_packet(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                rebuild_index=True,
            )
            composition = build_scene_composition(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                allow_missing_branch=True,
            )
            generation = generate_scene_candidate(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                context=context.output_path.relative_to(root),
                composition=composition.output_path.relative_to(root),
                provider="dry-run",
                allow_unselected_composition=True,
            )
            review = review_scene_with_agent(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                draft=generation.candidate_path.relative_to(root),
                provider="dry-run",
            )
            revision = build_scene_revision_task(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                draft=generation.candidate_path.relative_to(root),
                review=review.json_path.relative_to(root),
            )

            artifacts = {
                "context": self._payload(context.trace_path),
                "composition": self._payload(composition.json_path),
                "prompt": self._payload(generation.prompt_manifest_path),
                "candidate": self._payload(generation.manifest_path),
                "review": self._payload(review.json_path),
                "revision": self._payload(revision.prompt_manifest_path),
            }
            snapshots = {
                label: payload.get("style_mount_snapshot")
                for label, payload in artifacts.items()
            }
            expected = snapshots["context"]
            self.assertTrue(expected)
            self.assertEqual(
                {snapshot.get("digest") for snapshot in snapshots.values()},
                {expected["digest"]},
            )
            self.assertTrue(all(snapshot == expected for snapshot in snapshots.values()))

            mount_style_profile_version(
                root,
                style_id=second_version.style_id,
                version_id=second_version.version_id,
                content_hash=second_version.content_hash,
            )

            self.assertEqual(
                context_trace_status(root, "scene_0001").status,
                "stale",
            )
            generation_gate = candidate_generation_gate(
                root,
                "scene_0001",
                generation.candidate_path,
            )
            self.assertTrue(
                any(
                    "style mount snapshot stale" in item
                    for item in generation_gate["invalid"]
                ),
                generation_gate,
            )
            review_gate = candidate_review_gate(
                root,
                "scene_0001",
                generation.candidate_path,
            )
            self.assertTrue(
                review_gate["style_mount_snapshot_errors"],
                review_gate,
            )

    @staticmethod
    def _write_scene_fixture(root: Path) -> None:
        characters = root / "characters"
        scenes = root / "scenes"
        characters.mkdir(parents=True, exist_ok=True)
        scenes.mkdir(parents=True, exist_ok=True)
        (characters / "gatekeeper.yaml").write_text(
            """character_id: gatekeeper
name: 守门人
role: 主角
background_story:
  summary: 他曾因一次草率判断让来客失踪，因此坚持先验证再行动。
bdi:
  belief: [城市边界正在后退]
  desire: [确认界桩移动的原因]
  intention: [检查雨后的界桩]
psychology:
  fear: [再次误判]
  moral_line: 不把风险转嫁给陌生人
state:
  location: 城门
""",
            encoding="utf-8",
        )
        (scenes / "scene_0001.yaml").write_text(
            """scene_id: scene_0001
chapter_id: chapter_0001
location: 城门
participants: [gatekeeper]
input_state:
  canon_refs: []
  active_foreshadowing: [后退的界桩]
scene_goal: 守门人确认界桩确实向城内移动。
conflict:
  external: 雨水抹去了大部分痕迹。
  internal: 他担心自己再次误判。
style_constraints: [克制叙述]
output_state:
  next_hooks: [界桩底部留下陌生刻痕]
""",
            encoding="utf-8",
        )

    @staticmethod
    def _payload(path: Path | None) -> dict[str, object]:
        assert path is not None
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
