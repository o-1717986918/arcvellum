from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import install_core_import_path
from literary_engineering_studio.worker import AgentWorker
from literary_engineering_studio_engine.agent_tasks import (
    write_agent_completion_marker,
    write_agent_tasks,
)
from literary_engineering_studio_engine.literary.style.lab import mount_style_skill
from literary_engineering_studio_engine.literary.style.review import (
    prepare_style_semantic_review,
    style_review_machine_values,
)
from literary_engineering_studio_engine.literary.style.version import (
    StyleVersionError,
    StyleVersionConflictError,
    build_style_profile_version,
    plan_style_profile_version,
    style_profile_version_errors,
)
from literary_engineering_studio_engine.workflow_state import _style_engineering_state


class StyleProfileVersionTests(unittest.TestCase):
    def test_worker_builds_idempotent_immutable_version_with_legacy_mount_shape(self):
        config = default_config()
        install_core_import_path(config)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, profile, target_id = _formal_reviewed_profile(base)
            state = _style_engineering_state(root, profile)
            self.assertEqual(state["current_step"], "style-version-build")

            config["worker"]["runs_root"] = str(base / "runs")
            with patch(
                "literary_engineering_studio.worker.build_runtime",
                side_effect=AssertionError("version build must remain deterministic"),
            ):
                worker_result = AgentWorker(config).run_once(
                    root,
                    route="style-engineering",
                    runtime_id="opencode",
                    scene=profile.relative_to(root).as_posix(),
                )

            self.assertEqual(worker_result.status, "complete")
            self.assertEqual(worker_result.runtime, "deterministic-engine")
            self.assertEqual(_style_engineering_state(root, profile)["status"], "ready")
            plan = plan_style_profile_version(root, profile, target_id=target_id)
            self.assertEqual(style_profile_version_errors(plan), [])
            manifest = json.loads(plan.paths.manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema"], "arcvellum/style-profile-version/v1")
            self.assertEqual(manifest["review_status"], "pass")
            self.assertEqual(manifest["content_hash"], plan.content_hash)
            self.assertIn(
                "semantic_review_sha256",
                manifest["review_evidence"],
            )
            self.assertIn(
                "semantic_review_completion_sha256",
                manifest["review_evidence"],
            )
            self.assertEqual(manifest["source_evidence"][0]["rights"]["mode"], "public-domain")
            self.assertGreaterEqual(manifest["prompt_quality"]["detail_chars"], 500)
            self.assertLessEqual(manifest["prompt_quality"]["detail_chars"], 2500)

            repeated = build_style_profile_version(
                root,
                profile,
                target_id=target_id,
            )
            self.assertFalse(repeated.created)
            self.assertEqual(repeated.version_id, plan.version_id)

            library = base / "style-library"
            (library / "authors" / "classic-author" / "style_skills").mkdir(parents=True)
            (library / "library.json").write_text("{}\n", encoding="utf-8")
            compatibility_dir = (
                library
                / "authors"
                / "classic-author"
                / "style_skills"
                / plan.style_id
            )
            shutil.copytree(plan.paths.version_dir, compatibility_dir)
            mounted = mount_style_skill(
                root,
                library_root=library,
                style_id=plan.style_id,
            )
            self.assertTrue(mounted.mount_manifest_path.is_file())

    def test_existing_content_addressed_version_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            result = build_style_profile_version(root, profile, target_id=target_id)
            result.manifest_path.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(
                StyleVersionConflictError,
                "immutable style version conflicts",
            ):
                build_style_profile_version(root, profile, target_id=target_id)
            state = _style_engineering_state(root, profile)
            self.assertEqual(state["current_step"], "style-version-conflict")

    def test_reviewer_content_is_part_of_the_version_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            original = plan_style_profile_version(root, profile, target_id=target_id)
            review_path = profile / "evaluation_results/formal/style_semantic_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["summary"] = "同一证据下，独立 Reviewer 提交了新的正式结论摘要。"
            review_path.write_text(
                json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            revised = plan_style_profile_version(root, profile, target_id=target_id)

            self.assertEqual(revised.errors, ())
            self.assertNotEqual(revised.content_hash, original.content_hash)
            self.assertNotEqual(revised.version_id, original.version_id)

    def test_build_rejects_prompt_changed_after_semantic_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, profile, target_id = _formal_reviewed_profile(Path(temporary))
            prompt = profile / "style_prompt.md"
            prompt.write_text(
                prompt.read_text(encoding="utf-8") + "\n审查完成后追加的未复核约束。\n",
                encoding="utf-8",
            )

            plan = plan_style_profile_version(root, profile, target_id=target_id)

            self.assertTrue(plan.errors)
            with self.assertRaisesRegex(
                StyleVersionError,
                "style version evidence is not ready",
            ):
                build_style_profile_version(root, profile, target_id=target_id)


def _formal_reviewed_profile(base: Path) -> tuple[Path, Path, str]:
    root = base / "work"
    profile = root / "style" / "atelier" / "classic-author" / "measured-prose"
    evaluation = profile / "evaluation_results" / "formal"
    corpus = profile / "corpus"
    holdout_dir = profile / "evaluation_inputs" / "holdout"
    evaluation.mkdir(parents=True)
    corpus.mkdir(parents=True)
    holdout_dir.mkdir(parents=True)
    project_yaml = root / "project.yaml"
    project_yaml.write_text(
        "title: 潮线\npremise: 一个守门人发现城市边界正在后退。\n",
        encoding="utf-8",
    )
    training_text = "旧城的钟声从河面慢慢传来。守门人没有回头，只把钥匙放回原处。" * 30
    holdout_text = "雨停以后，石阶上留下细窄的水纹。来客看了一会儿，才敲第二次门。" * 30
    training = corpus / "0001-training-work-source.txt"
    holdout = holdout_dir / "0001-holdout-work-source.txt"
    training.write_text(training_text + "\n", encoding="utf-8")
    holdout.write_text(holdout_text + "\n", encoding="utf-8")
    session = {
        "schema": "arcvellum/style-engineering-session/v1",
        "version": 1,
        "session_id": "classic-author-measured-prose",
        "author_id": "classic-author",
        "profile_id": "measured-prose",
        "display_name": "Measured prose",
        "status": "prepared",
        "request_digest": "request-digest-fixture",
        "training_sources": [
            _source_row(
                "training_sources",
                "training-work",
                "source",
                training_text,
                training.relative_to(profile).as_posix(),
            )
        ],
        "holdout_sources": [
            _source_row(
                "holdout_sources",
                "holdout-work",
                "source",
                holdout_text,
                holdout.relative_to(profile).as_posix(),
            )
        ],
        "created_at": "2026-07-26T00:00:00+00:00",
    }
    (profile / "style_session.json").write_text(
        json.dumps(session, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (profile / "style-profile.md").write_text("# 风格档案\n", encoding="utf-8")
    (profile / "style_metrics.json").write_text("{}\n", encoding="utf-8")
    (profile / "corpus_manifest.yaml").write_text("sources: 1\n", encoding="utf-8")
    prompt = profile / "style_prompt.md"
    prompt.write_text(_quality_prompt(), encoding="utf-8")
    (profile / "style_prompt.agent.json").write_text(
        json.dumps({"writer_session_id": "studio:writer:style-prompt"}),
        encoding="utf-8",
    )
    prompt_task = profile / "style_prompt.agent_tasks.md"
    write_agent_tasks(
        prompt_task,
        title="Style prompt",
        root=root,
        source_paths=[profile / "style-profile.md", profile / "style_metrics.json"],
        tasks=[("Write prompt", "Write the exact prompt artifacts.")],
    )
    write_agent_completion_marker(prompt_task, root=root, handled_by="style-writer")

    candidate = evaluation / "platform_agent_candidate.md"
    candidate.write_text("守门人换班时发现界桩向城内挪了三步。昨夜值守的人都说没有看见来客。\n" * 15, encoding="utf-8")
    eval_task = evaluation / "platform_agent_candidate.agent_tasks.md"
    write_agent_tasks(
        eval_task,
        title="Style evaluation",
        root=root,
        source_paths=[prompt, project_yaml],
        tasks=[("Generate candidate", "Write the exact evaluation candidate.")],
    )
    write_agent_completion_marker(eval_task, root=root, handled_by="evaluation-writer")
    reference_sha = hashlib.sha256(holdout.read_bytes()).hexdigest()
    generation = {
        "mode": "blind-review",
        "style_prompt": prompt.relative_to(root).as_posix(),
        "reference": holdout.relative_to(root).as_posix(),
        "input": "project.yaml",
        "candidate": candidate.relative_to(root).as_posix(),
        "style_prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
        "reference_sha256": reference_sha,
        "input_sha256": hashlib.sha256(project_yaml.read_bytes()).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        "writer_session_id": "studio:writer:style-evaluation",
    }
    (evaluation / "platform_agent_candidate.prompt.json").write_text(
        json.dumps(generation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    score = {
        "schema": "literary-engineering-workbench/style-eval/v0.1",
        "mode": "blind-review",
        "overall_score": 82,
        "risk_level": "acceptable",
        "candidate_sha256": generation["candidate_sha256"],
        "reference_sha256": reference_sha,
    }
    (evaluation / "style_eval_current.json").write_text(
        json.dumps(score, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (evaluation / "style_eval_current.md").write_text("# Score\n\n82\n", encoding="utf-8")
    target_id = "style-atelier-classic-author-measured-prose"
    review_paths = prepare_style_semantic_review(
        root,
        profile,
        target_id=target_id,
    )
    review_paths.review_markdown.write_text(
        "# 文风工程独立语义审查\n\n- 结论：`pass`\n\n提示词可执行，证据链完整。\n",
        encoding="utf-8",
    )
    review = json.loads(review_paths.review_json.read_text(encoding="utf-8"))
    review.update(
        {
            "status": "complete",
            "verdict": "pass",
            "summary": "提示词可执行，确定性证据支持其文学可用性。",
            "findings": [],
            "required_changes": [],
            "effectiveness_assessment": "叙述距离、节奏与行为因果约束清晰。",
            "copy_risk_assessment": "没有依赖连续原文表达。",
            "evidence_limitations": ["Reviewer 未读取原始 holdout 正文。"],
        }
    )
    review.update(
        style_review_machine_values(
            root,
            profile,
            target_id=target_id,
            reviewer_session_id="studio:reviewer:independent-style-review",
        )
    )
    review_paths.review_json.write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(
        review_paths.task,
        root=root,
        handled_by="independent-style-reviewer",
    )
    return root, profile, target_id


def _source_row(
    group: str,
    work_id: str,
    source_id: str,
    content: str,
    path: str,
) -> dict[str, object]:
    return {
        "identity": f"{work_id}/{source_id}",
        "work_id": work_id,
        "source_id": source_id,
        "content_sha256": hashlib.sha256(content.strip().encode("utf-8")).hexdigest(),
        "path": path,
        "rights": {
            "mode": "public-domain",
            "declaration": f"Public-domain {group} fixture.",
        },
    }


def _quality_prompt() -> str:
    blocks = [
        "使用身份与适用边界",
        "核心风格机制",
        "叙述距离与视角",
        "句法与节奏",
        "标点节奏",
        "意象与感官调度",
        "心理呈现与行为因果",
        "对白与语气",
        "AI腔控制",
        "禁止倾向",
        "输出自检",
    ]
    rule = (
        "先交代可观察动作，再让心理从选择和代价中显露。句号与逗号按语义层级分配，"
        "不使用机械对照和破折号变体。正例强调具体行动，反例避免抽象形容。"
    )
    return "\n\n".join(f"## {block}\n\n{rule}" for block in blocks) + "\n"


if __name__ == "__main__":
    unittest.main()
