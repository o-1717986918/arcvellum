"""Export chapter artifacts into multiple delivery formats."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .creative_quality import load_creative_quality_profile
from typing import Sequence

from .chapter_pipeline import build_chapter_workspace
from .docx_export import export_markdown_to_docx
from .draft_text import count_delivery_chars, count_delivery_chinese_content_chars, final_body_from_draft_text
from .flow_gates import FlowGateError
from .punctuation_standard import normalize_punctuation_for_delivery


EXPORT_FORMATS = {"md", "docx"}


@dataclass(frozen=True)
class ExportPackageResult:
    project_root: Path
    output_dir: Path
    manifest_path: Path
    novel_path: Path
    screenplay_path: Path
    video_prompt_path: Path
    docx_outputs: dict[str, Path]
    docx_layout_plans: dict[str, Path]
    docx_inspections: dict[str, Path]
    requested_formats: tuple[str, ...]
    chapter_id: str
    exported_scene_count: int
    skipped_scene_count: int


def build_export_package(
    project_root: Path,
    chapter_id: str = "chapter_0001",
    include_blocked: bool = False,
    rebuild_chapter: bool = False,
    output_dir: Path | None = None,
    formats: str | Sequence[str] | None = None,
) -> ExportPackageResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    requested_formats = normalize_export_formats(formats)

    chapter_json = root / "plot" / "chapters" / f"{chapter_id}.json"
    chapter_markdown = root / "drafts" / "chapters" / f"{chapter_id}.md"
    if rebuild_chapter or not chapter_json.is_file() or not chapter_markdown.is_file():
        build_chapter_workspace(root, chapter_id=chapter_id, build_missing=False, review_drafts=False)
    if not chapter_json.exists():
        raise FileNotFoundError(f"chapter JSON not found: {chapter_json}")

    chapter = json.loads(chapter_json.read_text(encoding="utf-8"))
    scenes = chapter.get("scenes", [])
    exportable = []
    skipped = []
    for scene in scenes:
        if _is_export_ready(scene) or include_blocked:
            exportable.append(scene)
        else:
            skipped.append(scene)
    if skipped and not include_blocked:
        raise FlowGateError(
            f"export-package blocked: chapter {chapter_id} has {len(skipped)} non-ready scene(s). "
            "Run chapter-workspace, route-audit --route scene-development, agent-review-scene/revise-scene as needed. "
            "For internal previews only, pass --include-blocked."
        )

    out_dir = (output_dir if output_dir and output_dir.is_absolute() else root / output_dir) if output_dir else root / "exports" / chapter_id
    out_dir.mkdir(parents=True, exist_ok=True)

    novel_path = out_dir / f"{chapter_id}_novel.md"
    screenplay_path = out_dir / f"{chapter_id}_screenplay.md"
    video_prompt_path = out_dir / f"{chapter_id}_video_prompt_pack.md"
    manifest_path = out_dir / "export_manifest.json"

    novel_path.write_text(_render_novel(root, chapter_id, exportable, skipped, include_blocked), encoding="utf-8")
    screenplay_path.write_text(_render_screenplay(root, chapter_id, exportable, skipped, include_blocked), encoding="utf-8")
    video_prompt_path.write_text(_render_video_prompt_pack(root, chapter_id, exportable, skipped, include_blocked), encoding="utf-8")
    docx_outputs: dict[str, Path] = {}
    docx_layout_plans: dict[str, Path] = {}
    docx_inspections: dict[str, Path] = {}
    if "docx" in requested_formats:
        novel_docx = export_markdown_to_docx(
            novel_path,
            title=f"{_public_chapter_title(chapter_id)} 正文",
            kind="novel",
        )
        docx_outputs["novel"] = novel_docx.docx_path
        docx_layout_plans["novel"] = novel_docx.layout_plan_path
        docx_inspections["novel"] = novel_docx.inspection_path
        screenplay_docx = export_markdown_to_docx(
            screenplay_path,
            title=f"{_public_chapter_title(chapter_id)} 剧本工作稿",
            kind="screenplay",
        )
        docx_outputs["screenplay"] = screenplay_docx.docx_path
        docx_layout_plans["screenplay"] = screenplay_docx.layout_plan_path
        docx_inspections["screenplay"] = screenplay_docx.inspection_path
        video_docx = export_markdown_to_docx(
            video_prompt_path,
            title=f"{_public_chapter_title(chapter_id)} 长视频提示词包",
            kind="video_prompt_pack",
        )
        docx_outputs["video_prompt_pack"] = video_docx.docx_path
        docx_layout_plans["video_prompt_pack"] = video_docx.layout_plan_path
        docx_inspections["video_prompt_pack"] = video_docx.inspection_path

    manifest = {
        "schema": "literary-engineering-workbench/export-package/v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chapter_id": chapter_id,
        "include_blocked": include_blocked,
        "requested_formats": list(requested_formats),
        "source_chapter_json": _rel_str(chapter_json, root),
        "creative_quality_profile": load_creative_quality_profile(root),
        "outputs": {
            "novel": _rel_str(novel_path, root),
            "screenplay": _rel_str(screenplay_path, root),
            "video_prompt_pack": _rel_str(video_prompt_path, root),
            "docx": {key: _rel_str(path, root) for key, path in docx_outputs.items()},
            "docx_layout_plans": {key: _rel_str(path, root) for key, path in docx_layout_plans.items()},
            "docx_inspections": {key: _rel_str(path, root) for key, path in docx_inspections.items()},
        },
        "exported_scenes": [_scene_manifest(root, scene) for scene in exportable],
        "skipped_scenes": [_scene_manifest(root, scene) for scene in skipped],
        "warnings": _warnings(exportable, skipped, include_blocked),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return ExportPackageResult(
        project_root=root,
        output_dir=out_dir,
        manifest_path=manifest_path,
        novel_path=novel_path,
        screenplay_path=screenplay_path,
        video_prompt_path=video_prompt_path,
        docx_outputs=docx_outputs,
        docx_layout_plans=docx_layout_plans,
        docx_inspections=docx_inspections,
        requested_formats=requested_formats,
        chapter_id=chapter_id,
        exported_scene_count=len(exportable),
        skipped_scene_count=len(skipped),
    )


def load_export_package(project_root: Path, chapter_id: str) -> ExportPackageResult:
    """Load an existing formal export without mutating approved artifacts."""

    root = project_root.resolve()
    out_dir = root / "exports" / chapter_id
    manifest_path = out_dir / "export_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"export manifest not found: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "literary-engineering-workbench/export-package/v0.1":
        raise ValueError("export manifest has wrong or missing schema")
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}

    def path_for(value: object) -> Path:
        relative = str(value or "").replace("\\", "/")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError(f"unsafe or missing export output path: {relative or 'missing'}")
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"export output not found: {path}")
        return path

    docx = outputs.get("docx") if isinstance(outputs.get("docx"), dict) else {}
    layouts = outputs.get("docx_layout_plans") if isinstance(outputs.get("docx_layout_plans"), dict) else {}
    inspections = outputs.get("docx_inspections") if isinstance(outputs.get("docx_inspections"), dict) else {}
    return ExportPackageResult(
        project_root=root,
        output_dir=out_dir,
        manifest_path=manifest_path,
        novel_path=path_for(outputs.get("novel")),
        screenplay_path=path_for(outputs.get("screenplay")),
        video_prompt_path=path_for(outputs.get("video_prompt_pack")),
        docx_outputs={str(key): path_for(value) for key, value in docx.items()},
        docx_layout_plans={str(key): path_for(value) for key, value in layouts.items()},
        docx_inspections={str(key): path_for(value) for key, value in inspections.items()},
        requested_formats=tuple(str(item) for item in payload.get("requested_formats", []) if str(item)),
        chapter_id=str(payload.get("chapter_id") or chapter_id),
        exported_scene_count=len(payload.get("exported_scenes", []) if isinstance(payload.get("exported_scenes"), list) else []),
        skipped_scene_count=len(payload.get("skipped_scenes", []) if isinstance(payload.get("skipped_scenes"), list) else []),
    )


def normalize_export_formats(formats: str | Sequence[str] | None) -> tuple[str, ...]:
    if formats is None:
        return ("md",)
    if isinstance(formats, str):
        items = [item.strip().lower() for item in formats.split(",")]
    else:
        items = [str(item).strip().lower() for item in formats]
    normalized: list[str] = []
    for item in items:
        if not item:
            continue
        if item not in EXPORT_FORMATS:
            raise ValueError(f"unsupported export format: {item}; supported: {', '.join(sorted(EXPORT_FORMATS))}")
        if item not in normalized:
            normalized.append(item)
    return tuple(normalized or ["md"])


def _render_novel(root: Path, chapter_id: str, scenes: list[dict], skipped: list[dict], include_blocked: bool) -> str:
    lines = [
        f"# {_public_chapter_title(chapter_id)}",
        "",
    ]
    if include_blocked:
        lines.append("> 内部预览版本。")
        lines.append("")
    if not scenes:
        lines.append("## 无可导出场景")
        lines.append("")
        lines.append("- 当前章节没有 ready 场景。")
        lines.append("")
    for scene in scenes:
        body = _draft_body(root, scene)
        lines.append(body or "- 未读取到正文。")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_screenplay(root: Path, chapter_id: str, scenes: list[dict], skipped: list[dict], include_blocked: bool) -> str:
    lines = [
        f"# 剧本导出草稿：{_public_chapter_title(chapter_id)}",
        "",
        "## 使用规则",
        "",
        "- 本文件是由场景草稿转换的剧本工作稿，不是最终拍摄剧本。",
        "- 场景调度、对白拆分和镜头编号需要人工二次整理。",
        "",
    ]
    if include_blocked:
        lines.extend(["> 注意：包含未通过审查的场景。", ""])
    for index, scene in enumerate(scenes, 1):
        location = scene.get("location") or "未填写地点"
        participants = "、".join(scene.get("participants") or []) or "未填写"
        lines.extend(
            [
                f"## {_public_scene_label(index)}",
                "",
                f"**场景**：{location}",
                f"**人物**：{participants}",
                "",
                "### 剧本文本",
                "",
                _screenplay_body(_draft_body(root, scene)),
                "",
            ]
        )
    if skipped:
        lines.extend(["## 未进入剧本导出的场景", ""])
        for index, scene in enumerate(skipped, 1):
            lines.append(f"- 未导出条目 {index}：{scene.get('status', 'unknown')}")
    return "\n".join(lines).rstrip() + "\n"


def _render_video_prompt_pack(root: Path, chapter_id: str, scenes: list[dict], skipped: list[dict], include_blocked: bool) -> str:
    lines = [
        f"# 长视频提示词包：{_public_chapter_title(chapter_id)}",
        "",
        f"生成时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        "## 全局约束",
        "",
        "- 只依据已导出的场景草稿生成画面提示，不新增剧情事实。",
        "- 视觉连续性必须服从地点、人物、时间线和 canon。",
        "- 人物外观、服装、道具一旦确认，应写回角色或地点档案。",
        "- 输出给视频模型前，应由人工确认镜头长度、平台比例和禁用内容。",
        "",
    ]
    if include_blocked:
        lines.extend(["> 注意：包含未通过审查的场景，视频提示词仅供内部探索。", ""])
    if not scenes:
        lines.extend(["## 无可生成视频提示词的场景", "", "- 当前章节没有 ready 场景。", ""])
    for index, scene in enumerate(scenes, 1):
        body = _draft_body(root, scene)
        summary = _compact(body, 260)
        participants = "、".join(scene.get("participants") or []) or "未填写"
        location = scene.get("location") or "未填写地点"
        lines.extend(
            [
                f"## 镜头组 {index}",
                "",
                f"- 地点：{location}",
                f"- 人物：{participants}",
                "",
                "### 场景摘要",
                "",
                summary or "未读取到正文。",
                "",
                "### 镜头设计",
                "",
                "- 建立镜头：交代地点、时间、主要人物和空间关系。",
                "- 推进镜头：跟随关键动作与信息揭示，不添加草稿之外的新事件。",
                "- 情绪镜头：突出人物的迟疑、选择、冲突或隐瞒。",
                "- 收束镜头：保留下一场景的状态变化或悬念。",
                "",
                "### 视频生成提示词",
                "",
                _video_prompt(scene, summary),
                "",
                "### 负面提示",
                "",
                "- 不要新增未确认角色。",
                "- 不要改变人物关系和场景结果。",
                "- 不要使用夸张娱乐化表演。",
                "- 不要制造与 canon 冲突的道具、地点或时间。",
                "",
                "### 声音与字幕",
                "",
                "- 环境声应服务地点和情绪。",
                "- 旁白只可压缩草稿信息，不可替代剧情推进。",
                "- 字幕保留人物姓名、地点和关键信息，不扩写新事实。",
                "",
            ]
        )
    if skipped:
        lines.extend(["## 未生成视频提示词的场景", ""])
        for index, scene in enumerate(skipped, 1):
            lines.append(f"- 未生成条目 {index}：{scene.get('status', 'unknown')}")
    return "\n".join(lines).rstrip() + "\n"


def _scene_manifest(root: Path, scene: dict) -> dict:
    body = _draft_body(root, scene)
    return {
        "scene_id": scene.get("scene_id", ""),
        "status": scene.get("status", ""),
        "review_conclusion": scene.get("review_conclusion", ""),
        "agent_review_conclusion": scene.get("agent_review_conclusion", ""),
        "agent_review_schema_status": scene.get("agent_review_schema_status", ""),
        "agent_review_json": scene.get("agent_review_json", ""),
        "draft_path": scene.get("draft_path", ""),
        "draft_chars": count_delivery_chinese_content_chars(body),
        "draft_chinese_chars": count_delivery_chinese_content_chars(body),
        "draft_machine_chars": count_delivery_chars(body),
        "count_unit": "chinese_content_chars_including_chinese_punctuation",
        "machine_count_unit": "machine_nonspace_chars",
    }


def _warnings(exportable: list[dict], skipped: list[dict], include_blocked: bool) -> list[str]:
    warnings = []
    if include_blocked:
        warnings.append("本次导出包含未通过审查或未完成的场景，仅可内部预览。")
    if skipped:
        warnings.append("存在未导出的场景，请回到 chapter-workspace、review-scene 或平台 Agent 场景审查修订。")
    if not exportable:
        warnings.append("没有可导出的 ready 场景。")
    return warnings


def _draft_body(root: Path, scene: dict) -> str:
    rel = scene.get("draft_path") or ""
    if not rel:
        return ""
    path = Path(rel)
    draft_path = path if path.is_absolute() else root / path
    if not draft_path.exists():
        return ""
    body = final_body_from_draft_text(draft_path.read_text(encoding="utf-8", errors="ignore")).strip()
    return normalize_punctuation_for_delivery(body)


def _public_chapter_title(chapter_id: str) -> str:
    match = re.search(r"(?:chapter|卷|章)[_-]?0*(\d+)", chapter_id, flags=re.IGNORECASE)
    if not match:
        return "正文"
    return f"第{int(match.group(1))}章"


def _public_scene_label(index: int) -> str:
    return f"第{index}场"


def _is_export_ready(scene: dict) -> bool:
    return (
        scene.get("status") == "ready"
        and scene.get("review_conclusion") == "pass"
        and scene.get("agent_review_conclusion") == "pass"
        and scene.get("agent_review_schema_status") == "pass"
        and scene.get("agent_review_source_match") is True
        and not scene.get("agent_review_unresolved_notes")
        and not scene.get("flow_gate_issues")
        and not scene.get("readiness_issues")
    )


def _screenplay_body(body: str) -> str:
    if not body:
        return "- 未读取到正文。"
    paragraphs = [item.strip() for item in body.splitlines() if item.strip()]
    if not paragraphs:
        paragraphs = [body.strip()]
    lines = []
    for paragraph in paragraphs:
        lines.append(paragraph)
        lines.append("")
    return "\n".join(lines).rstrip()


def _video_prompt(scene: dict, summary: str) -> str:
    location = scene.get("location") or "未填写地点"
    participants = "、".join(scene.get("participants") or []) or "未填写人物"
    goal = scene.get("scene_goal") or "未填写场景目标"
    return (
        f"在{location}，围绕{participants}展开一段严肃克制、叙事清晰的长视频场景。"
        f"核心目标是：{goal}。画面应表现以下内容：{summary or '依据场景草稿呈现人物行动与情绪变化。'}"
        "镜头语言保持现实质感，注重空间、动作、情绪和信息揭示的连续性。"
    )


def _compact(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "..."


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)
