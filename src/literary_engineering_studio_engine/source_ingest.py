"""Import existing works and prepare platform-agent extraction tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from shutil import rmtree

from .agent_tasks import write_agent_tasks


TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
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
    overwrite: bool = False,
) -> SourceIngestResult:
    """Store source text and write an agent task for reverse project extraction."""

    root = project_root.resolve()
    if not (root / "project.yaml").exists():
        raise FileNotFoundError(f"work project not found: {root}")
    if mode not in INGEST_MODES:
        raise ValueError(f"unknown source ingest mode: {mode}")
    if not source and not text:
        raise ValueError("source ingest requires a source path or inline text")

    resolved_source = source.resolve() if source else None
    resolved_id = _slug(work_id or title or (resolved_source.stem if resolved_source else "existing-work"))
    import_dir = root / "sources" / "imports" / resolved_id
    if import_dir.exists() and any(import_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(f"source import already exists: {import_dir}")
        rmtree(import_dir)

    raw_dir = import_dir / "raw"
    chunk_dir = import_dir / "chunks"
    extracted_dir = import_dir / "extracted"
    raw_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)
    _ensure_candidate_dirs(root)

    source_records = _read_sources(resolved_source, text=text, title=title)
    raw_records: list[dict[str, object]] = []
    combined_sections: list[str] = []
    for index, record in enumerate(source_records, start=1):
        raw_name = f"{index:03d}-{_safe_filename(record['label'])}.txt"
        raw_path = raw_dir / raw_name
        raw_path.write_text(str(record["text"]), encoding="utf-8")
        raw_records.append(
            {
                "label": record["label"],
                "input_path": record.get("input_path", ""),
                "raw_path": _rel(raw_path, root),
                "char_count": len(str(record["text"])),
            }
        )
        combined_sections.append(f"\n\n[source:{index:03d} label={record['label']}]\n\n{record['text']}")

    normalized = _normalize_text("\n".join(combined_sections))
    chunks = _chunks(normalized, chunk_size)
    chunk_records: list[dict[str, object]] = []
    offset = 0
    for index, chunk in enumerate(chunks, start=1):
        chunk_path = chunk_dir / f"chunk_{index:04d}.md"
        chunk_path.write_text(_render_chunk(resolved_id, index, chunk, offset), encoding="utf-8")
        chunk_records.append(
            {
                "chunk_id": f"chunk_{index:04d}",
                "path": _rel(chunk_path, root),
                "char_start": offset,
                "char_end": offset + len(chunk),
                "char_count": len(chunk),
            }
        )
        offset += len(chunk)

    candidate_outputs = _candidate_outputs(resolved_id)
    manifest_path = import_dir / "source_manifest.json"
    report_path = import_dir / "source_ingest.md"
    task_path = import_dir / "extract_project_files.agent_tasks.md"

    manifest = {
        "schema": "literary-engineering-workbench/source-ingest/v1",
        "work_id": resolved_id,
        "title": title,
        "mode": mode,
        "created_at": _now(),
        "source_count": len(raw_records),
        "chunk_count": len(chunk_records),
        "raw_sources": raw_records,
        "chunks": chunk_records,
        "candidate_outputs": candidate_outputs,
        "guardrails": [
            "Source extraction is evidence, not canon.",
            "All extracted facts, characters, world rules, outlines, and style notes remain candidates.",
            "Use short evidence references instead of copying long source passages.",
            "Do not write directly to confirmed canon, character files, official plot files, drafts, exports, or releases.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(
        _render_report(
            root=root,
            work_id=resolved_id,
            title=title,
            mode=mode,
            manifest_path=manifest_path,
            raw_records=raw_records,
            chunk_records=chunk_records,
            candidate_outputs=candidate_outputs,
        ),
        encoding="utf-8",
    )
    _write_extraction_task(
        root=root,
        work_id=resolved_id,
        title=title,
        mode=mode,
        manifest_path=manifest_path,
        report_path=report_path,
        chunk_paths=[root / record["path"] for record in chunk_records],
        candidate_outputs=candidate_outputs,
        task_path=task_path,
    )

    return SourceIngestResult(
        project_root=root,
        work_id=resolved_id,
        import_dir=import_dir,
        manifest_path=manifest_path,
        report_path=report_path,
        task_path=task_path,
        source_count=len(raw_records),
        chunk_count=len(chunk_records),
        candidate_outputs=candidate_outputs,
    )


def _read_sources(source: Path | None, *, text: str, title: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    if source:
        files = _collect_source_files(source)
        for file in files:
            records.append(
                {
                    "label": file.stem,
                    "input_path": str(file),
                    "text": file.read_text(encoding="utf-8"),
                }
            )
    if text:
        records.append(
            {
                "label": title or "inline-source",
                "input_path": "",
                "text": text,
            }
        )
    if not records:
        raise ValueError("no readable text sources found")
    return records


def _collect_source_files(source: Path) -> list[Path]:
    if not source.exists():
        raise FileNotFoundError(f"source path does not exist: {source}")
    if source.is_file():
        if source.suffix.lower() not in TEXT_EXTENSIONS:
            raise ValueError(f"unsupported source text extension: {source.suffix}")
        return [source]
    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            parts = path.relative_to(source).parts
        except ValueError:
            parts = path.parts
        if any(part.startswith(".") for part in parts):
            continue
        files.append(path)
    if not files:
        raise ValueError(f"no .txt/.md source files found under: {source}")
    return files


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
    chunk_paths: list[Path],
    candidate_outputs: dict[str, str],
    task_path: Path,
) -> None:
    source_paths = [manifest_path, report_path, *chunk_paths]
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
            f"提取模式：{mode}",
        ],
        tasks=[
            (
                "读取源作品与边界",
                f"""读取 `{_rel(manifest_path, root)}`、`{_rel(report_path, root)}` 和所有 chunk。确认作品标题 `{title or work_id}`、使用目的 `{mode}`、已有项目的 canon/characters/plot/style 现状，以及任何用户给出的续写、改写或分析边界。""",
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
) -> str:
    lines = [
        f"# 源作品导入：{title or work_id}",
        "",
        f"- work_id: `{work_id}`",
        f"- mode: `{mode}`",
        f"- manifest: `{_rel(manifest_path, root)}`",
        f"- source_count: {len(raw_records)}",
        f"- chunk_count: {len(chunk_records)}",
        "",
        "## Raw Sources",
        "",
    ]
    for record in raw_records:
        lines.append(f"- `{record['raw_path']}`：{record['char_count']} chars")
    lines.extend(["", "## Chunks", ""])
    for record in chunk_records:
        lines.append(
            f"- `{record['chunk_id']}` `{record['path']}` chars {record['char_start']}-{record['char_end']}"
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


def _render_chunk(work_id: str, index: int, text: str, offset: int) -> str:
    return "\n".join(
        [
            f"# Source Chunk {index:04d}",
            "",
            f"- work_id: `{work_id}`",
            f"- chunk_id: `chunk_{index:04d}`",
            f"- char_start: {offset}",
            f"- char_end: {offset + len(text)}",
            "",
            "## Text",
            "",
            text.strip(),
            "",
        ]
    )


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip() + "\n"


def _chunks(text: str, chunk_size: int) -> list[str]:
    size = max(int(chunk_size or 6000), 200)
    return [text[index : index + size] for index in range(0, len(text), size)] or [text]


def _safe_filename(value: object) -> str:
    return _slug(str(value))[:60] or "source"


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
