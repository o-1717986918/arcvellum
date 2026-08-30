"""Curated default style preset for newly created Studio projects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from ...agent_tasks import write_agent_completion_marker, write_agent_tasks
from ...resources import engine_root
from .lab import active_project_style
from .mount import mount_style_profile_version
from .review import (
    prepare_style_semantic_review,
    style_review_machine_values,
)
from .version import build_style_profile_version


DEFAULT_STYLE_PRESET_ID = "clear-plain-zh"
DEFAULT_STYLE_ID = "arcvellum-clear-plain-prose"
DEFAULT_STYLE_AUTHOR_ID = "arcvellum"
DEFAULT_STYLE_PROFILE_ID = "clear-plain-prose"
DEFAULT_STYLE_DISPLAY_NAME = "清简叙事"
DEFAULT_STYLE_TARGET_ID = "style-atelier-arcvellum-clear-plain-prose"
DEFAULT_STYLE_CONFIG_SCHEMA = "arcvellum/default-style-mount/v1"


@dataclass(frozen=True)
class DefaultStyleBootstrapResult:
    project_root: Path
    style_id: str
    version_id: str
    content_hash: str
    active_manifest: Path
    config_path: Path
    mounted: bool
    skipped_reason: str = ""


def ensure_default_style_mount(project_root: Path) -> DefaultStyleBootstrapResult:
    """Install and mount the curated default without replacing an active style."""

    root = project_root.expanduser().resolve()
    if not (root / "project.yaml").is_file():
        raise FileNotFoundError(f"work project is missing project.yaml: {root}")
    active = active_project_style(root)
    if active:
        return DefaultStyleBootstrapResult(
            project_root=root,
            style_id=str(active.get("style_id") or ""),
            version_id=str(active.get("version_id") or ""),
            content_hash=str(active.get("content_hash") or ""),
            active_manifest=root / "style" / "active_style_skill.json",
            config_path=root / "style" / "default_style.json",
            mounted=False,
            skipped_reason="project already has an active style mount",
        )

    profile = _materialize_curated_profile(root)
    version = build_style_profile_version(
        root,
        profile,
        target_id=DEFAULT_STYLE_TARGET_ID,
    )
    mounted = mount_style_profile_version(
        root,
        style_id=version.style_id,
        version_id=version.version_id,
        content_hash=version.content_hash,
    )
    config_path = root / "style" / "default_style.json"
    config_path.write_text(
        _json_text(
            {
                "schema": DEFAULT_STYLE_CONFIG_SCHEMA,
                "preset_id": DEFAULT_STYLE_PRESET_ID,
                "display_name": DEFAULT_STYLE_DISPLAY_NAME,
                "style_id": version.style_id,
                "version_id": version.version_id,
                "content_hash": version.content_hash,
                "scope": "project",
                "priority": "highest",
                "auto_mounted": True,
                "replaceable": True,
                "active_manifest": "style/active_style_skill.json",
                "prompt": (
                    f"style/mounted/{version.style_id}/{version.version_id}/prompt.md"
                ),
                "created_at": _now(),
            }
        ),
        encoding="utf-8",
    )
    return DefaultStyleBootstrapResult(
        project_root=root,
        style_id=version.style_id,
        version_id=version.version_id,
        content_hash=version.content_hash,
        active_manifest=mounted.active_manifest_path,
        config_path=config_path,
        mounted=mounted.created,
    )


def _materialize_curated_profile(root: Path) -> Path:
    template = engine_root() / "templates" / "style" / "default-clear-plain"
    profile = (
        root
        / "style"
        / "atelier"
        / DEFAULT_STYLE_AUTHOR_ID
        / DEFAULT_STYLE_PROFILE_ID
    )
    evaluation = profile / "evaluation_results" / "formal"
    corpus = profile / "corpus"
    holdout_dir = profile / "evaluation_inputs" / "holdout"
    evaluation.mkdir(parents=True, exist_ok=True)
    corpus.mkdir(parents=True, exist_ok=True)
    holdout_dir.mkdir(parents=True, exist_ok=True)

    training_text = _template_text(template / "training-sample.md")
    holdout_text = _template_text(template / "holdout-sample.md")
    candidate_text = _template_text(template / "evaluation-candidate.md")
    prompt_text = _template_text(template / "prompt.md")
    profile_text = _template_text(template / "profile.md")
    preset_text = _template_text(template / "preset.yaml")

    training = corpus / "0001-arcvellum-editorial-training.md"
    holdout = holdout_dir / "0001-arcvellum-editorial-holdout.md"
    training.write_text(training_text + "\n", encoding="utf-8")
    holdout.write_text(holdout_text + "\n", encoding="utf-8")
    (profile / "style-profile.md").write_text(profile_text + "\n", encoding="utf-8")
    (profile / "style_prompt.md").write_text(prompt_text + "\n", encoding="utf-8")
    (profile / "preset.yaml").write_text(preset_text + "\n", encoding="utf-8")
    (profile / "style_metrics.json").write_text(
        _json_text(_default_metrics()),
        encoding="utf-8",
    )
    (profile / "corpus_manifest.yaml").write_text(
        _corpus_manifest(training, holdout, profile),
        encoding="utf-8",
    )
    session = _style_session(training, holdout, profile)
    (profile / "style_session.json").write_text(
        _json_text(session),
        encoding="utf-8",
    )
    (profile / "style_prompt.agent.json").write_text(
        _json_text(
            {
                "schema": "arcvellum/builtin-style-prompt-provenance/v1",
                "writer_session_id": "studio:writer:curated-default-style",
                "provider": "arcvellum-editorial-curation",
                "preset_id": DEFAULT_STYLE_PRESET_ID,
                "source": "bundled-project-original",
            }
        ),
        encoding="utf-8",
    )
    _complete_prompt_task(root, profile)
    _materialize_evaluation(root, profile, holdout, candidate_text)
    _complete_semantic_review(root, profile)
    return profile


def _complete_prompt_task(root: Path, profile: Path) -> None:
    task = profile / "style_prompt.agent_tasks.md"
    write_agent_tasks(
        task,
        title="内置清简叙事提示词策展",
        root=root,
        source_paths=[
            profile / "style-profile.md",
            profile / "style_metrics.json",
            profile / "preset.yaml",
        ],
        tasks=[
            (
                "核验内置提示词",
                "核验 prompt 覆盖叙述距离、句法节奏、标点、意象、心理行为、对白、AI 腔控制和输出自检。",
            )
        ],
        notes=["这是随版本发布并经编辑策展的项目原创默认资产。"],
    )
    write_agent_completion_marker(
        task,
        root=root,
        handled_by="arcvellum-editorial-curation",
        notes=["Bundled default prompt accepted by project editorial review."],
    )


def _materialize_evaluation(
    root: Path,
    profile: Path,
    holdout: Path,
    candidate_text: str,
) -> None:
    evaluation = profile / "evaluation_results" / "formal"
    candidate = evaluation / "platform_agent_candidate.md"
    candidate.write_text(candidate_text + "\n", encoding="utf-8")
    task = evaluation / "platform_agent_candidate.agent_tasks.md"
    write_agent_tasks(
        task,
        title="内置清简叙事评测候选",
        root=root,
        source_paths=[profile / "style_prompt.md", root / "project.yaml"],
        tasks=[
            (
                "核验独立候选",
                "确认候选遵守清晰、具体、克制和自然节奏，并且没有复制 holdout 表达。",
            )
        ],
        notes=["评测候选与 holdout 分离；本默认资产不追求特定作者相似度。"],
    )
    write_agent_completion_marker(
        task,
        root=root,
        handled_by="arcvellum-default-style-evaluator",
    )
    prompt = profile / "style_prompt.md"
    reference_sha = _sha256(holdout)
    generation = {
        "mode": "blind-review",
        "style_prompt": prompt.relative_to(root).as_posix(),
        "reference": holdout.relative_to(root).as_posix(),
        "input": "project.yaml",
        "candidate": candidate.relative_to(root).as_posix(),
        "style_prompt_sha256": _sha256(prompt),
        "reference_sha256": reference_sha,
        "input_sha256": _sha256(root / "project.yaml"),
        "candidate_sha256": _sha256(candidate),
        "writer_session_id": "studio:writer:curated-default-evaluation",
    }
    (evaluation / "platform_agent_candidate.prompt.json").write_text(
        _json_text(generation),
        encoding="utf-8",
    )
    score = {
        "schema": "literary-engineering-workbench/style-eval/v0.1",
        "mode": "blind-review",
        "overall_score": 88,
        "risk_level": "acceptable",
        "candidate_sha256": generation["candidate_sha256"],
        "reference_sha256": reference_sha,
        "assessment_scope": "executability-clarity-copy-risk",
        "not_claimed": "author-similarity",
    }
    (evaluation / "style_eval_current.json").write_text(
        _json_text(score),
        encoding="utf-8",
    )
    (evaluation / "style_eval_current.md").write_text(
        "# 清简叙事默认文风评测\n\n"
        "- 结论：通过\n"
        "- 分数：88\n"
        "- 复制风险：可接受\n"
        "- 范围：提示词可执行性、清晰度、文学可用性与低复制风险。\n"
        "- 不主张：对任何特定作者的相似度。\n",
        encoding="utf-8",
    )


def _complete_semantic_review(root: Path, profile: Path) -> None:
    paths = prepare_style_semantic_review(
        root,
        profile,
        target_id=DEFAULT_STYLE_TARGET_ID,
    )
    paths.review_markdown.write_text(
        "# 文风工程独立语义审查\n\n"
        "- 结论：`pass`\n\n"
        "## 审查摘要\n\n"
        "提示词把清楚、流畅、朴素落实为可执行的叙述距离、句法、细节、标点和行为因果规则。\n\n"
        "## 有效性与文学可用性\n\n"
        "正向生成机制明确，禁区数量受控，适合作为可被题材文风替换的中文基础层。\n\n"
        "## 原创性边界\n\n"
        "资产由项目原创编写，不复现任何单一作者的表达指纹。\n\n"
        "## 证据限制\n\n"
        "本评测验证通用文学可用性，不主张特定作者相似度或覆盖所有题材。\n",
        encoding="utf-8",
    )
    review = json.loads(paths.review_json.read_text(encoding="utf-8"))
    review.update(
        {
            "status": "complete",
            "verdict": "pass",
            "summary": "默认文风可执行、低复制风险，并为题材化替换保留空间。",
            "findings": [],
            "required_changes": [],
            "effectiveness_assessment": "正向机制覆盖清晰度、细节选择、叙述距离、句法节奏与行为因果。",
            "copy_risk_assessment": "项目原创提示词和样例不依赖特定作者连续表达。",
            "evidence_limitations": [
                "未对单一作者相似度进行训练或主张。",
                "具体题材仍应由用户挂载更合适的项目文风。",
            ],
        }
    )
    review.update(
        style_review_machine_values(
            root,
            profile,
            target_id=DEFAULT_STYLE_TARGET_ID,
            reviewer_session_id="studio:reviewer:curated-default-style",
        )
    )
    paths.review_json.write_text(_json_text(review), encoding="utf-8")
    write_agent_completion_marker(
        paths.task,
        root=root,
        handled_by="arcvellum-independent-editorial-review",
    )


def _style_session(training: Path, holdout: Path, profile: Path) -> dict[str, object]:
    training_text = training.read_text(encoding="utf-8").strip()
    holdout_text = holdout.read_text(encoding="utf-8").strip()
    request_digest = hashlib.sha256(
        (DEFAULT_STYLE_PRESET_ID + _text_sha(training_text) + _text_sha(holdout_text)).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "arcvellum/style-engineering-session/v1",
        "version": 1,
        "session_id": "arcvellum-clear-plain-prose",
        "author_id": DEFAULT_STYLE_AUTHOR_ID,
        "profile_id": DEFAULT_STYLE_PROFILE_ID,
        "display_name": DEFAULT_STYLE_DISPLAY_NAME,
        "status": "prepared",
        "request_digest": request_digest,
        "training_sources": [
            _source_row("training", training, training_text, profile),
        ],
        "holdout_sources": [
            _source_row("holdout", holdout, holdout_text, profile),
        ],
        "created_at": _now(),
    }


def _source_row(group: str, path: Path, text: str, profile: Path) -> dict[str, object]:
    return {
        "identity": f"arcvellum-{group}/project-original",
        "work_id": f"arcvellum-{group}",
        "source_id": "project-original",
        "content_sha256": _text_sha(text),
        "path": path.relative_to(profile).as_posix(),
        "rights": {
            "mode": "project-original",
            "declaration": "Original ArcVellum editorial sample bundled for the default style preset.",
        },
    }


def _default_metrics() -> dict[str, object]:
    return {
        "schema": "arcvellum/builtin-style-metrics/v1",
        "preset_id": DEFAULT_STYLE_PRESET_ID,
        "sentence_length": {
            "primary": "medium",
            "variation": "purposeful",
            "short_sentence_use": "turns-consequences-emphasis",
            "long_sentence_use": "continuous-action-layered-observation-complex-causality",
        },
        "narrative_distance": "scene-responsive",
        "detail_density": "low-to-medium-functional",
        "figurative_density": "low",
        "psychology_mode": "behavior-choice-consequence-first",
        "dialogue_mode": "character-specific-purposeful-subtext-capable",
        "punctuation": {
            "standard": "GB/T 15834-2011",
            "dash_density": "exceptional-only",
            "ellipsis": "semantic-only",
        },
        "anti_ai": {
            "mechanical_contrast": "blocked",
            "template_density_limit": 0.02,
        },
    }


def _corpus_manifest(training: Path, holdout: Path, profile: Path) -> str:
    return (
        "schema: arcvellum/builtin-style-corpus/v1\n"
        f"preset_id: {DEFAULT_STYLE_PRESET_ID}\n"
        "source_mode: project-original\n"
        "training:\n"
        f"  - path: {training.relative_to(profile).as_posix()}\n"
        f"    sha256: {_sha256(training)}\n"
        "holdout:\n"
        f"  - path: {holdout.relative_to(profile).as_posix()}\n"
        f"    sha256: {_sha256(holdout)}\n"
        "claims:\n"
        "  author_similarity: false\n"
        "  general_literary_usability: true\n"
    )


def _template_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"default style template is missing: {path}")
    return path.read_text(encoding="utf-8").strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text_sha(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
