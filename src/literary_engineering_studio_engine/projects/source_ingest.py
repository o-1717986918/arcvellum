"""Import existing works and prepare platform-agent extraction tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from shutil import rmtree

from ..agent_tasks import write_agent_tasks
from ..literary.ingest import (
    EXTRACTOR_VERSION,
    SOURCE_INGEST_SCHEMA_V2,
    SUPPORTED_SOURCE_EXTENSIONS,
    StagedSourceImport,
    commit_import,
    import_revision,
    recover_interrupted_import,
    stage_source_import,
)


TEXT_EXTENSIONS = SUPPORTED_SOURCE_EXTENSIONS
INGEST_MODES = {"continuation", "rewrite", "adaptation", "analysis"}


@dataclass(frozen=True)
class SourceIngestResult:
    project_root: Path
    work_id: str
    import_dir: Path
    manifest_path: Path
    report_path: Path
    task_path: Path
    source_count: int
    chunk_count: int
    candidate_outputs: dict[str, str]


def ingest_existing_work(
    project_root: Path,
    *,
    source: Path | None = None,
    text: str = "",
    title: str = "",
    work_id: str = "",
    mode: str = "continuation",
    chunk_size: int = 6000,
    rights_declaration: str = "",
    overwrite: bool = False,
) -> SourceIngestResult:
    """Preserve sources and write a candidate-only reverse extraction task."""

    root = project_root.resolve()
    if not (root / "project.yaml").exists():
        raise FileNotFoundError(f"work project not found: {root}")
    if mode not in INGEST_MODES:
        raise ValueError(f"unknown source ingest mode: {mode}")
    if not source and not text:
        raise ValueError("source ingest requires a source path or inline text")

    resolved_source = source.resolve() if source else None
    resolved_id = _slug(work_id or title or (resolved_source.stem if resolved_source else "existing-work"))
    imports_dir = root / "sources" / "imports"
    import_dir = imports_dir / resolved_id
    recover_interrupted_import(import_dir)
    if import_dir.exists() and any(import_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(f"source import already exists: {import_dir}")
    staging_dir = imports_dir / f".{resolved_id}.importing"
    if staging_dir.exists():
        rmtree(staging_dir)
    try:
        artifacts = _stage_import(
            root=root,
            staging_dir=staging_dir,
            work_id=resolved_id,
            source=resolved_source,
            text=text,
            title=title,
            mode=mode,
            chunk_size=chunk_size,
            rights_declaration=rights_declaration,
        )
        commit_import(staging_dir, import_dir, overwrite=overwrite)
    except Exception:
        if staging_dir.exists():
            rmtree(staging_dir)
        raise

    manifest_path = import_dir / "source_manifest.json"
    report_path = import_dir / "source_ingest.md"
    task_path = import_dir / "extract_project_files.agent_tasks.md"

    return SourceIngestResult(
        project_root=root,
        work_id=resolved_id,
        import_dir=import_dir,
        manifest_path=manifest_path,
        report_path=report_path,
        task_path=task_path,
        source_count=int(artifacts["source_count"]),
        chunk_count=int(artifacts["chunk_count"]),
        candidate_outputs=dict(artifacts["candidate_outputs"]),
    )


def _stage_import(
    *,
    root: Path,
    staging_dir: Path,
    work_id: str,
    source: Path | None,
    text: str,
    title: str,
    mode: str,
    chunk_size: int,
    rights_declaration: str,
) -> dict[str, object]:
    _ensure_candidate_dirs(root)
    logical_import = f"sources/imports/{work_id}"
    staged = stage_source_import(
        staging_dir=staging_dir,
        logical_import=logical_import,
        work_id=work_id,
        source=source,
        text=text,
        title=title,
        rights_declaration=rights_declaration,
        chunk_size=chunk_size,
    )
    logical_evidence = f"{logical_import}/evidence_index.json"
    candidate_outputs = _candidate_outputs(work_id)
    logical_manifest = root / logical_import / "source_manifest.json"
    logical_report = root / logical_import / "source_ingest.md"
    manifest = _source_manifest(
        work_id=work_id,
        mode=mode,
        rights_declaration=rights_declaration,
        logical_evidence=logical_evidence,
        staged=staged,
        candidate_outputs=candidate_outputs,
    )
    manifest["import_revision"] = import_revision(manifest)
    (staging_dir / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (staging_dir / "source_ingest.md").write_text(
        _render_report(
            root=root,
            work_id=work_id,
            title=str(manifest["title"]),
            mode=mode,
            manifest_path=logical_manifest,
            raw_records=list(staged.raw_records),
            chunk_records=list(staged.chunk_records),
            candidate_outputs=candidate_outputs,
            evidence_path=root / logical_evidence,
            segment_count=staged.segment_count,
        ),
        encoding="utf-8",
    )
    _write_extraction_task(
        root=root,
        work_id=work_id,
        title=str(manifest["title"]),
        mode=mode,
        manifest_path=logical_manifest,
        report_path=logical_report,
        evidence_path=root / logical_evidence,
        chunk_paths=[root / str(record["path"]) for record in staged.chunk_records],
        candidate_outputs=candidate_outputs,
        task_path=staging_dir / "extract_project_files.agent_tasks.md",
        task_identity_path=root / logical_import / "extract_project_files.agent_tasks.md",
    )
    return {
        "source_count": staged.source_count,
        "chunk_count": staged.chunk_count,
        "candidate_outputs": candidate_outputs,
    }


def _source_manifest(
    *,
    work_id: str,
    mode: str,
    rights_declaration: str,
    logical_evidence: str,
    staged: StagedSourceImport,
    candidate_outputs: dict[str, str],
) -> dict[str, object]:
    return {
        "schema": SOURCE_INGEST_SCHEMA_V2,
        "work_id": work_id,
        "title": staged.title,
        "mode": mode,
        "created_at": _now(),
        "extractor_version": EXTRACTOR_VERSION,
        "rights_declaration": rights_declaration.strip(),
        "source_count": staged.source_count,
        "segment_count": staged.segment_count,
        "chunk_count": staged.chunk_count,
        "source_documents": list(staged.source_documents),
        "raw_sources": list(staged.raw_records),
        "evidence_index": {
            "path": logical_evidence,
            "revision": staged.evidence_revision,
            "segment_count": staged.segment_count,
            "evidence_count": staged.segment_count,
        },
        "chunks": list(staged.chunk_records),
        "candidate_outputs": candidate_outputs,
        "guardrails": [
            "Source extraction is evidence, not canon.",
            "All extracted facts, characters, world rules, outlines, and style notes remain candidates.",
            "Use evidence ids and bounded source ranges instead of copying long source passages.",
            "Do not write directly to confirmed canon, character files, official plot files, drafts, exports, or releases.",
        ],
    }


def _candidate_outputs(work_id: str) -> dict[str, str]:
    stem = _slug(work_id)
    return {
        "project_brief": f"sources/imports/{stem}/extracted/project_brief.md",
        "characters": f"characters/candidates/extracted/{stem}_characters.md",
        "world": f"canon/candidates/extracted/{stem}_world.md",
        "outline": f"plot/candidates/extracted/{stem}_outline.md",
        "timeline": f"plot/candidates/extracted/{stem}_timeline.md",
        "foreshadowing": f"plot/candidates/extracted/{stem}_foreshadowing.md",
        "style_notes": f"style/candidates/{stem}_style_generation_notes.md",
        "review": f"reviews/source_ingest/{stem}_extraction_review.md",
    }


def _ensure_candidate_dirs(root: Path) -> None:
    for rel in (
        "characters/candidates/extracted",
        "canon/candidates/extracted",
        "plot/candidates/extracted",
        "style/candidates",
        "reviews/source_ingest",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)


def _write_extraction_task(
    *,
    root: Path,
    work_id: str,
    title: str,
    mode: str,
    manifest_path: Path,
    report_path: Path,
    evidence_path: Path,
    chunk_paths: list[Path],
    candidate_outputs: dict[str, str],
    task_path: Path,
    task_identity_path: Path,
) -> None:
    source_paths = [
        root / "project.yaml",
        manifest_path,
        report_path,
        evidence_path,
        *chunk_paths,
    ]
    output_lines = "\n".join(f"- {key}: `{path}`" for key, path in candidate_outputs.items())
    write_agent_tasks(
        task_path,
        title=f"existing work reverse extraction {work_id}",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是已有作品反推标准项目文件的正式平台 Agent 任务。",
            "CLI 只完成导入、分块和任务说明；人物、世界观、剧情、文风的判断由平台 agent 完成。",
            "所有输出都写入候选区或 source_ingest review，不得自动晋升为 canon。",
            "每条候选结论必须引用 evidence_index.json 中存在的 evidence id，不得自造引用。",
            f"提取模式：{mode}",
        ],
        tasks=[
            (
                "读取源作品与边界",
                f"""读取 `project.yaml`、`{_rel(manifest_path, root)}`、`{_rel(report_path, root)}`、`{_rel(evidence_path, root)}` 和所有 chunk。确认作品标题 `{title or work_id}`、使用目的 `{mode}`、项目身份和清单中声明的边界。不要尝试读取 task package 未列出的项目资料；只使用证据索引中可解析的 evidence id。""",
            ),
            (
                "反推项目简报",
                f"""创建或覆盖 `{candidate_outputs['project_brief']}`。用标准项目语言概括 premise、类型、叙事视角、核心冲突、主题压力、读者预期、续写/改写入口和未知项。每条关键结论必须标注 evidence_refs（chunk id 或 raw source label）和 confidence。""",
            ),
            (
                "提取人物与隐藏背景候选",
                f"""创建或覆盖 `{candidate_outputs['characters']}`。区分 major / secondary / cameo。对每个角色提取 identity、role、importance、relationships、belief/desire/intention、fear、secret、moral_line、background_story 推断、speech_style、state、arc、unknowns、evidence_refs、confidence。background_story 只能作为后续行为因果，不得默认直接 exposition。""",
            ),
            (
                "提取世界观与剧情结构候选",
                f"""创建或覆盖 `{candidate_outputs['world']}`、`{candidate_outputs['outline']}`、`{candidate_outputs['timeline']}` 和 `{candidate_outputs['foreshadowing']}`。分别提取世界规则、地点/组织、情节阶段、事件顺序、伏笔/回收、矛盾和未解问题。任何不确定内容写为 hypothesis，不得写成 confirmed canon。""",
            ),
            (
                "提取可生成文风说明",
                f"""创建或覆盖 `{candidate_outputs['style_notes']}`。输出可转化为 Style Skill 的生成约束草案：叙述距离、句法节奏、段落长度、标点节奏、意象和感官路由、心理呈现、对白密度、AI 腔规避、禁止倾向。若涉及非公版或未授权作品，只能抽象高层 craft 特征，不做精确仿写承诺。""",
            ),
            (
                "写入审查报告",
                f"""创建或覆盖 `{candidate_outputs['review']}`。审查本次反推结果的证据强度、矛盾、缺漏、版权/授权和续写风险，列出可晋升候选、必须人工确认项、建议下一步。不要写入 `[AGENT_TASK: ...]`。候选输出清单：\n{output_lines}""",
            ),
        ],
        identity_path=task_identity_path,
    )


def _render_report(
    *,
    root: Path,
    work_id: str,
    title: str,
    mode: str,
    manifest_path: Path,
    raw_records: list[dict[str, object]],
    chunk_records: list[dict[str, object]],
    candidate_outputs: dict[str, str],
    evidence_path: Path,
    segment_count: int,
) -> str:
    lines = [
        f"# 源作品导入：{title or work_id}",
        "",
        f"- work_id: `{work_id}`",
        f"- mode: `{mode}`",
        f"- manifest: `{_rel(manifest_path, root)}`",
        f"- source_count: {len(raw_records)}",
        f"- segment_count: {segment_count}",
        f"- chunk_count: {len(chunk_records)}",
        f"- evidence_index: `{_rel(evidence_path, root)}`",
        "",
        "## Raw Sources",
        "",
    ]
    for record in raw_records:
        lines.append(
            f"- `{record['source_id']}` → `{record['raw_path']}`：{record['char_count']} chars"
        )
    lines.extend(["", "## Chunks", ""])
    for record in chunk_records:
        lines.append(
            f"- `{record['chunk_id']}` `{record['path']}` "
            f"segments={len(record.get('segment_ids', []))} "
            f"evidence={len(record.get('evidence_refs', []))} "
            f"chars {record['char_start']}-{record['char_end']}"
        )
    lines.extend(
        [
            "",
            "## Candidate Outputs",
            "",
        ]
    )
    for key, value in candidate_outputs.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Agent Boundary",
            "",
            "本报告只是导入清单。源作品的设定、人物、剧情、文风反推必须由装载本 Skill 的平台 Agent 执行，并写入候选区。",
            "所有提取结果都必须带证据引用、置信度、未知项和人工确认边界，不得直接覆盖正式 canon、characters、plot 或 draft。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _slug(value: str) -> str:
    text = re.sub(r"\s+", "-", str(value).strip().lower())
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", text).strip("-")
    return text[:64].strip("-") or "item"


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
