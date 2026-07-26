"""Atomic storage and human-readable rendering for archaeology candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...agent_tasks import (
    agent_task_completion_status,
    write_agent_completion_marker,
    write_agent_tasks,
)


def commit_materialization(
    root: Path,
    records: list[dict[str, Any]],
    *,
    output: Path,
    report: Path,
    manifest: dict[str, Any],
) -> None:
    planned = _planned_paths(root, records, output, report)
    snapshots = {path: path.read_bytes() if path.is_file() else None for path in planned}
    try:
        for item in records:
            _write_archive_candidate(root, item)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report.write_text(_render_materialization(manifest), encoding="utf-8")
    except Exception:
        _restore_snapshots(snapshots)
        raise


def _planned_paths(
    root: Path,
    records: list[dict[str, Any]],
    output: Path,
    report: Path,
) -> list[Path]:
    planned = [output, report]
    for item in records:
        candidate = root / str(item["candidate_path"])
        planned.extend(
            [
                candidate,
                candidate.with_suffix(".md"),
                candidate.with_suffix(".agent_tasks.md"),
                candidate.with_suffix(".agent_completion.json"),
            ]
        )
    return planned


def _write_archive_candidate(root: Path, record: dict[str, Any]) -> None:
    candidate = root / str(record["candidate_path"])
    candidate.parent.mkdir(parents=True, exist_ok=True)
    _write_if_changed(candidate, str(record["encoded"]).encode("utf-8"))
    report = candidate.with_suffix(".md")
    _write_text_if_changed(report, _render_candidate(record["payload"]))
    task = candidate.with_suffix(".agent_tasks.md")
    _write_materialization_sidecar(root, task, record)
    if agent_task_completion_status(task, root=root).get("complete") is not True:
        write_agent_completion_marker(
            task,
            root=root,
            handled_by="archaeology-materializer",
            notes=["Derived from passed archaeology domain review."],
        )


def _write_materialization_sidecar(
    root: Path,
    task: Path,
    record: dict[str, Any],
) -> None:
    provenance = record["payload"]["archaeology_provenance"]
    write_agent_tasks(
        task,
        title=f"archaeology materialized Archive candidate {record['candidate_id']}",
        root=root,
        source_paths=[
            root / path
            for path in provenance.values()
            if isinstance(path, str) and path.endswith((".json", ".md"))
        ],
        notes=[
            "This sidecar records deterministic materialization from an Agent-reviewed reconstruction.",
            "The candidate remains provisional and still requires an independent Archive review and user approval.",
        ],
        tasks=[
            (
                "确认候选物化边界",
                "确认候选文件只位于注册候选目录，保留考古证据与未决项，并未直接修改正式 Canon、人物或情节资产。",
            )
        ],
        identity_path=task,
    )


def _render_candidate(payload: dict[str, Any]) -> str:
    provenance = payload.get("archaeology_provenance") or {}
    title = payload.get("name") or payload.get("title") or payload.get("candidate_id")
    return "\n".join(
        [
            f"# 考古候选：{title}",
            "",
            f"- candidate_id: `{payload.get('candidate_id', '')}`",
            f"- asset_type: `{payload.get('asset_type', '')}`",
            f"- work_id: `{provenance.get('work_id', '')}`",
            f"- mode: `{provenance.get('mode', '')}`",
            f"- confidence: `{provenance.get('confidence', '')}`",
            f"- evidence_refs: {len(provenance.get('evidence_refs') or [])}",
            f"- unresolved_refs: {len(provenance.get('unresolved_refs') or [])}",
            "",
            "本文件是经考古领域审查后生成的 Archive 候选，不是正式项目事实。"
            "必须继续完成独立候选审查、用户批准和正式晋升。",
            "",
        ]
    )


def _render_materialization(payload: dict[str, Any]) -> str:
    lines = [
        "# Project Archaeology 候选物化",
        "",
        f"- work_id: `{payload.get('work_id', '')}`",
        f"- mode: `{payload.get('mode', '')}`",
        f"- status: `{payload.get('status', '')}`",
        f"- materialized: {len(payload.get('materialized_assets') or [])}",
        f"- deferred: {len(payload.get('deferred_assets') or [])}",
        "",
        "## Archive Candidates",
        "",
    ]
    lines.extend(
        f"- `{item.get('candidate_id', '')}` → `{item.get('candidate_path', '')}`"
        for item in payload.get("materialized_assets") or []
    )
    lines.extend(
        [
            "",
            "这些文件仍是候选。每个候选必须通过 Archive 独立审查、内容摘要绑定批准和原子晋升。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_if_changed(path: Path, content: bytes) -> None:
    if not path.is_file() or path.read_bytes() != content:
        path.write_bytes(content)


def _write_text_if_changed(path: Path, content: str) -> None:
    if not path.is_file() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")


def _restore_snapshots(snapshots: dict[Path, bytes | None]) -> None:
    for path, content in snapshots.items():
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
