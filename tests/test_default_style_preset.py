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
)
from literary_engineering_studio_engine.literary.style.defaults import (
    DEFAULT_STYLE_ID,
    ensure_default_style_mount,
)
from literary_engineering_studio_engine.literary.style.lab import active_project_style
from literary_engineering_studio_engine.literary.style.prompt import (
    style_prompt_quality_report,
)
from literary_engineering_studio_engine.literary.style.snapshot import (
    active_style_evidence_paths,
)
from literary_engineering_studio_engine.literary.style.prompt_agent import (
    _dry_style_prompt,
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
        generated_prompt = _dry_style_prompt([])["prompt_markdown"]
        generated_quality = style_prompt_quality_report(str(generated_prompt))
        self.assertTrue(quality["length_ok"])
        self.assertTrue(quality["structure_ok"])
        self.assertTrue(generated_quality["length_ok"])
        self.assertTrue(generated_quality["structure_ok"])
        self.assertIn("抽象文风要求必须在初稿中落实", prompt)
        self.assertIn("机械“不是……而是……”", prompt)
        self.assertIn("“不再是……而是……”", prompt)
        self.assertIn("“没有再……而是……”", prompt)
        self.assertIn("中文正文统一使用全角标点", prompt)
        self.assertIn("继续接受后续 Style Lint 与 AgentReview 核验", prompt)
        self.assertIn("无关精确数字默认不用", prompt)
        self.assertIn("一个又一个", prompt)
        self.assertIn("不要求五项同时成立", prompt)
        self.assertIn("人物的词汇范围、礼貌程度、句子完整度和回避方式应可辨", prompt)
        self.assertIn("场景合同和参考语料不自动豁免装饰性数字", prompt)
        self.assertIn("已确定金额、日期、数量和差值必须准确", prompt)
        self.assertIn("普通陈设和日常动作不为显得具体而记账", prompt)
        self.assertIn("选最贴合本场的一篇作表达主参照", prompt)
        self.assertIn("主动模仿其叙述距离、句群呼吸", prompt)
        self.assertIn("所选样例的叙述距离、句群节奏", prompt)
        self.assertIn("一张桌、两把椅子、拧两下、看几秒", prompt)
        self.assertIn("抽象文风软约束转译为本场", route_prompt)
        self.assertIn("一篇最贴合本场功能的表达主参照", route_prompt)
        self.assertIn("Style Lint 与 AgentReview 继续核验违禁表达", route_prompt)
        self.assertIn("一个又一个", route_prompt)
        self.assertIn("一项实际功能足以保留精度", route_prompt)
        self.assertIn("人物说话从已有身份、欲望、关系压力", route_prompt)
        self.assertIn("不做批量删除和机械模糊化", route_prompt)
        self.assertIn("do not invent a numeric density threshold", review_prompt)
        self.assertIn("routine gesture counts, and incidental object counts", review_prompt)
        self.assertIn("do not batch-delete digits", revision_prompt)
        self.assertIn("无关精确数字默认不用", generated_prompt)
        self.assertIn("一个又一个", generated_prompt)
        self.assertIn("一项实际功能", generated_prompt)
        self.assertIn("不批量删除，也不机械换成模糊量词", generated_prompt)

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
            self.assertIn("R01—R07", profile_text)
            self.assertIn("R17—R25", profile_text)
            self.assertIn("类型氛围与空间定调", profile_text)
            self.assertNotIn("类型氛围反例", profile_text)
            self.assertNotIn("https://", profile_text)
            self.assertNotIn("作者：", profile_text)
            self.assertNotIn("版权", profile_text)
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
                objective="人物在压力下作出选择",
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
            self.assertIn(profile_text.strip(), lean_sources)
            self.assertIn("将人彻底包裹。", lean_sources)

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


if __name__ == "__main__":
    unittest.main()
