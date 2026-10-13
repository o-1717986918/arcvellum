from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.project_manager import create_project
from literary_engineering_studio.runtimes.pi_scene_transaction import (
    PiSceneTransactionRuntime,
)
from literary_engineering_studio_engine.foundation.resources import engine_root
from literary_engineering_studio_engine.public.literary import (
    LengthTarget,
    RhythmDirective,
    SceneBrief,
    SceneRisk,
    SceneRiskLevel,
    StyleMountRef,
    render_style_reference_selection,
)
from literary_engineering_studio_engine.literary.style.defaults import (
    DEFAULT_STYLE_ID,
    ensure_default_style_mount,
    refresh_default_style_mount,
)
from literary_engineering_studio_engine.literary.style.lab import active_project_style
from literary_engineering_studio_engine.literary.style.prompt import (
    style_prompt_quality_report,
)
from literary_engineering_studio_engine.literary.style.snapshot import (
    active_style_evidence_paths,
)
from literary_engineering_studio_engine.prompting.style_context import (
    resolve_style_prompt_context,
)
from literary_engineering_studio_engine.prompting.platform_task_support import (
    style_source_paths,
)
from literary_engineering_studio_engine.workflow.state import (
    _style_engineering_states,
)


class DefaultStylePresetTests(unittest.TestCase):
    def test_curated_prompt_generates_soft_style_and_preserves_hard_review_rules(self):
        template_root = (
            engine_root() / "templates" / "style" / "default-clear-plain"
        )
        prompt = (template_root / "prompt.md").read_text(encoding="utf-8")
        route_prompt = (
            engine_root()
            / "templates"
            / "prompt_assets"
            / "route.scene-development.prose.generate.v1.md"
        ).read_text(encoding="utf-8")
        review_prompt = (
            engine_root()
            / "templates"
            / "prompt_assets"
            / "route.scene-development.agent-review.v1.md"
        ).read_text(encoding="utf-8")
        revision_prompt = (
            engine_root()
            / "templates"
            / "prompt_assets"
            / "route.scene-development.revision.v1.md"
        ).read_text(encoding="utf-8")

        quality = style_prompt_quality_report(prompt)
        self.assertTrue(quality["length_ok"])
        self.assertTrue(quality["structure_ok"])
        self.assertLess(len(prompt), 2_000)
        for mode in ("世界与风俗", "人物现场", "抒情与内心", "群像与传奇"):
            self.assertIn(mode, prompt)
        for old in ("承压才", "情绪必须", "你不能", "你不是", "硬边界"):
            self.assertNotIn(old, prompt)
        self.assertIn("version: v15", route_prompt)
        self.assertIn("本场选中的完整参考", route_prompt)
        self.assertIn("expression plan", route_prompt)
        self.assertIn("旧 prose_seed 仅为历史证据", route_prompt)
        self.assertIn("Style Lint 与 AgentReview 继续核验违禁表达", route_prompt)
        self.assertIn("项目禁用表达、机械对照及换皮、中文标点", route_prompt)
        self.assertIn("do not invent a numeric density threshold", review_prompt)
        self.assertIn("routine gesture counts, and incidental object counts", review_prompt)
        self.assertNotIn("do not batch-delete digits", revision_prompt)
        self.assertIn("at least one real function", revision_prompt)
        self.assertNotIn("five-part necessity test", revision_prompt)

        corpus = (template_root / "training-sample.md").read_text(
            encoding="utf-8"
        ).strip()
        blocks = re.split(r"\n{2,}", corpus)
        self.assertEqual(len(blocks), 25)
        self.assertEqual(
            hashlib.sha256(corpus.encode("utf-8")).hexdigest(),
            "35c5ecf515618fa59677c063d778572f53cd653f7fc302e75cc10ec55b26a03e",
        )
        self.assertTrue(corpus.startswith("今天晚上，很好的月光。"))
        self.assertTrue(corpus.endswith("将人彻底包裹。"))
        self.assertNotIn("https://", corpus)
        self.assertNotIn("作者：", corpus)
        self.assertIn(
            "陈禾",
            (template_root / "holdout-sample.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "七号球衣",
            (template_root / "evaluation-candidate.md").read_text(encoding="utf-8"),
        )

    def test_studio_project_creation_mounts_reviewed_default_through_formal_mount(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                project = create_project(
                    parent_directory=str(base),
                    title="清简叙事验证",
                    folder_name="work",
                )

            root = Path(project["path"])
            self.assertFalse(list(root.rglob("*.agent_tasks.md")))
            self.assertFalse(list(root.rglob("*.agent_completion.json")))
            active = active_project_style(root)
            self.assertEqual(active["style_id"], DEFAULT_STYLE_ID)
            self.assertEqual(active["integrity"]["status"], "pass")
            self.assertEqual(active["scope"], "project")
            self.assertEqual(active["priority"], "highest")
            self.assertEqual(
                active["enforcement"],
                {
                    "director": "required",
                    "composition": "required",
                    "generation": "required",
                    "revision": "required",
                    "review": "required",
                },
            )

            context = resolve_style_prompt_context(root, text_limit=20000)
            self.assertIsNotNone(context.path)
            assert context.path is not None
            self.assertTrue(context.path.is_relative_to(root / "style" / "mounted"))
            self.assertEqual(context.snapshot["style_id"], DEFAULT_STYLE_ID)
            quality = style_prompt_quality_report(
                context.path.read_text(encoding="utf-8")
            )
            self.assertTrue(quality["length_ok"])
            self.assertTrue(quality["structure_ok"])
            self.assertGreaterEqual(int(quality["detail_chars"]), 500)
            self.assertLessEqual(int(quality["detail_chars"]), 2500)

            mounted_profile = context.path.parent / "style-profile.md"
            profile_text = mounted_profile.read_text(encoding="utf-8")
            corpus_text = (
                engine_root()
                / "templates"
                / "style"
                / "default-clear-plain"
                / "training-sample.md"
            ).read_text(encoding="utf-8").strip()
            for block in re.split(r"\n{2,}", corpus_text):
                self.assertIn(block, profile_text)
            self.assertIn("R01—R25", profile_text)
            self.assertIn("出处核验的文学参照", profile_text)
            self.assertIn("https://www.gutenberg.org/", profile_text)
            self.assertIn(
                mounted_profile.resolve(),
                {path.resolve() for path in style_source_paths(root)},
            )
            evidence = active_style_evidence_paths(root)
            self.assertIn(mounted_profile.resolve(), [path.resolve() for path in evidence])
            self.assertLess(
                [path.name for path in evidence].index("prompt.md"),
                [path.name for path in evidence].index("style-profile.md"),
            )
            brief = SceneBrief(
                scene_id="scene_0001",
                objective="雨夜离别时人物在压力下作出选择",
                scene_function="relationship-turn",
                participants=("主角",),
                canon_constraints=(),
                incoming_handoff=(),
                chapter_obligations=(),
                rhythm=RhythmDirective(),
                length=LengthTarget(),
                style_mount=StyleMountRef(active["style_id"], active["version_id"]),
                risk=SceneRisk(SceneRiskLevel.STANDARD),
                source_refs=tuple(path.relative_to(root).as_posix() for path in evidence),
            )
            runtime = PiSceneTransactionRuntime(
                {}, project_root=root, data_root=base / "pi-runtime"
            )
            lean_sources = runtime._source_evidence(brief, purpose="create")
            self.assertNotIn(profile_text.strip(), lean_sources)
            selection = runtime._style_projection(brief)
            self.assertEqual(selection["status"], "selected")
            self.assertEqual(selection["references"][0]["unit_id"], "R17")
            self.assertIn(selection["references"][0]["text"], render_style_reference_selection(selection))
            author_style = runtime._author_style_reference(runtime._style_reference(selection))
            self.assertIn("项目已挂载文风", author_style)
            self.assertIn("让人与世界之间的感情充分展开", author_style)
            self.assertIn("### 主参考 R17", author_style)

            config = json.loads(
                (root / "style" / "default_style.json").read_text(encoding="utf-8")
            )
            self.assertEqual(config["style_id"], DEFAULT_STYLE_ID)
            self.assertEqual(config["version_id"], active["version_id"])
            self.assertTrue(config["replaceable"])

            session = json.loads(
                (
                    root
                    / "style"
                    / "atelier"
                    / "arcvellum"
                    / "clear-plain-prose"
                    / "style_session.json"
                ).read_text(encoding="utf-8")
            )
            source_rows = [
                *session["training_sources"],
                *session["holdout_sources"],
            ]
            self.assertTrue(source_rows)
            self.assertEqual(
                [row["rights"]["mode"] for row in source_rows],
                ["user-supplied", "project-original"],
            )

            self.assertEqual(_style_engineering_states(root), [])
            project_yaml = root / "project.yaml"
            project_yaml.write_text(
                project_yaml.read_text(encoding="utf-8")
                + "\npremise: 项目方向可演化而不重开已发布默认文风。\n",
                encoding="utf-8",
            )
            self.assertEqual(_style_engineering_states(root), [])

    def test_default_mount_is_idempotent_and_does_not_replace_an_active_style(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                project = create_project(
                    parent_directory=str(base),
                    title="幂等验证",
                    folder_name="work",
                )
            root = Path(project["path"])
            before = active_project_style(root)

            repeated = ensure_default_style_mount(root)
            after = active_project_style(root)

            self.assertFalse(repeated.mounted)
            self.assertIn("already has an active style", repeated.skipped_reason)
            self.assertEqual(before["style_id"], after["style_id"])
            self.assertEqual(before["version_id"], after["version_id"])
            self.assertEqual(before["content_hash"], after["content_hash"])

    def test_refresh_rebuilds_the_bundled_default_as_a_new_verified_mount(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                project = create_project(parent_directory=str(base), title="新版默认文风", folder_name="work")
            root = Path(project["path"])
            first = active_project_style(root)
            refreshed = refresh_default_style_mount(root)
            current = active_project_style(root)
            self.assertEqual(refreshed.version_id, current["version_id"])
            self.assertEqual(first["content_hash"], current["content_hash"])
            self.assertIn("文学身份与写作志趣", (
                root / current["prompt"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
