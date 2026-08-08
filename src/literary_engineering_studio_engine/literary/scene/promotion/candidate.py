"""Promote a generated scene candidate into the reviewed draft lane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from ....anti_ai_style import style_lint_gate_message
from ....flow_gates import FlowGateError
from .gate_support import (
    candidate_body as _candidate_body,
    canon_writeback_declaration as _canon_writeback_declaration,
    read_text as _read,
    relative_path as _rel,
    section as _section,
)
from .generation_gate import candidate_generation_gate
from .historical import seal_historical_promotion
from .review_gate import (
    _candidate_review_content_match,
    _human_decision_notes,
    _review_session_independence,
    _unresolved_review_notes,
    candidate_review_gate,
)
from .style_gate import candidate_style_snapshot


@dataclass(frozen=True)
class CandidatePromotionResult:
    project_root: Path
    candidate_path: Path
    draft_path: Path
    manifest_path: Path
    report_path: Path
    scene_id: str
    chars: int
    approval_run_id: str


def promote_scene_candidate(
    project_root: Path,
    scene: Path | None = None,
    candidate: Path | None = None,
    output: Path | None = None,
    overwrite: bool = False,
    approval_run_id: str = "",
    selection_note: str = "",
    allow_unreviewed: bool = False,
    allow_review_notes: bool = False,
) -> CandidatePromotionResult:
    """Convert a provider candidate into a standard scene draft workspace."""

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else _resolve(root, scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")
    scene_id = scene_path.stem or "scene"
    candidate_path = _resolve_candidate(root, scene_id, candidate)
    candidate_text = _read(candidate_path)
    if not candidate_text:
        raise FileNotFoundError(f"candidate not found or empty: {candidate_path}")
    draft_path = _resolve(root, output, root / "drafts" / "scenes" / f"{scene_id}.md")
    if draft_path.exists() and not overwrite:
        raise FileExistsError(f"draft already exists: {draft_path}. pass overwrite=True to replace it")
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    body = _candidate_body(candidate_text)
    if not body:
        raise ValueError(f"candidate has no usable body: {candidate_path}")
    generation_gate = candidate_generation_gate(root, scene_id, candidate_path)
    if not allow_unreviewed:
        _ensure_candidate_generation_provenance(generation_gate)
    review_gate = candidate_review_gate(root, scene_id, candidate_path)
    if not allow_unreviewed:
        _ensure_candidate_reviewed(review_gate, allow_review_notes=allow_review_notes)
    sections = _candidate_writeback_sections(candidate_text)
    generated_at = _now()
    draft = _render_draft(
        scene_id=scene_id,
        scene_path=_rel(scene_path, root),
        candidate_path=_rel(candidate_path, root),
        generated_at=generated_at,
        body=body,
        sections=sections,
    )
    draft_path.write_text(draft, encoding="utf-8")
    manifest_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    report_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.md"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = _promotion_manifest(
        root=root,
        scene_path=scene_path,
        candidate_path=candidate_path,
        draft_path=draft_path,
        scene_id=scene_id,
        generated_at=generated_at,
        approval_run_id=approval_run_id,
        selection_note=selection_note,
        review_gate=review_gate,
        generation_gate=generation_gate,
        allow_unreviewed=allow_unreviewed,
        allow_review_notes=allow_review_notes,
        draft=draft,
        sections=sections,
    )
    manifest = seal_historical_promotion(root, manifest, candidate_path, draft_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(manifest), encoding="utf-8")
    return CandidatePromotionResult(
        project_root=root,
        candidate_path=candidate_path,
        draft_path=draft_path,
        manifest_path=manifest_path,
        report_path=report_path,
        scene_id=scene_id,
        chars=len(draft),
        approval_run_id=approval_run_id,
    )


def _candidate_writeback_sections(candidate_text: str) -> dict[str, list[str]]:
    return {
        "new_facts": _candidate_bullets(candidate_text, "新增事实候选"),
        "character_changes": _candidate_bullets(candidate_text, "人物状态变化"),
        "relationship_changes": _candidate_bullets(candidate_text, "关系变化"),
        "foreshadowing_changes": _candidate_bullets(candidate_text, "伏笔变化"),
        "approval_items": _candidate_bullets(candidate_text, "需要人工确认"),
    }


def _promotion_manifest(
    *,
    root: Path,
    scene_path: Path,
    candidate_path: Path,
    draft_path: Path,
    scene_id: str,
    generated_at: str,
    approval_run_id: str,
    selection_note: str,
    review_gate: dict[str, object],
    generation_gate: dict[str, object],
    allow_unreviewed: bool,
    allow_review_notes: bool,
    draft: str,
    sections: dict[str, list[str]],
) -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/candidate-promotion/v0.1",
        "promoted_at": generated_at,
        "scene_id": scene_id,
        "scene": _rel(scene_path, root),
        "candidate": _rel(candidate_path, root),
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "draft": _rel(draft_path, root),
        "draft_sha256": hashlib.sha256(draft_path.read_bytes()).hexdigest(),
        "approval_run_id": approval_run_id,
        "selection_note": selection_note,
        "candidate_review": review_gate,
        "candidate_generation": generation_gate,
        "style_mount_snapshot": candidate_style_snapshot(candidate_path),
        "style_lint_gate": review_gate.get("style_lint", {}),
        "allow_unreviewed": allow_unreviewed,
        "allow_review_notes": allow_review_notes,
        "chars": len(draft),
        "writeback_sections": sections,
        "canon_writeback": _canon_writeback_declaration(root, candidate_path),
        "guardrails": [
            "本命令只把候选稿转入草稿审查通道，不确认 canon。",
            "默认必须先完成针对该候选稿的正式平台 Agent 场景审查。",
            "默认必须先完成正式生成 provenance：CLI prompt manifest、.agent_tasks.md 和平台 Agent candidate manifest。",
            "候选正文必须通过 Style Lint Gate：机械对照句式和 medium+ AI 腔风险阻塞 promotion，low 风险进入审查 notes。",
            "转正后的草稿仍必须运行 review-scene 和后续平台 Agent 场景审查。",
            "人物、关系和 canon 写回仍必须走单独审批链路。",
        ],
    }


def _resolve_candidate(root: Path, scene_id: str, candidate: Path | None) -> Path:
    if candidate is not None:
        return _resolve(root, candidate)
    candidates = sorted(
        (root / "drafts" / "candidates").glob(f"{scene_id}-*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"no candidate found for scene: {scene_id}")
    return candidates[0]


def _ensure_candidate_generation_provenance(gate: dict[str, object]) -> None:
    if gate.get("status") == "pass":
        return
    candidate = str(gate.get("candidate") or "")
    missing = gate.get("missing")
    invalid = gate.get("invalid")
    details: list[str] = []
    if isinstance(missing, list) and missing:
        details.append("missing=" + ", ".join(str(item) for item in missing))
    if isinstance(invalid, list) and invalid:
        details.append("invalid=" + ", ".join(str(item) for item in invalid))
    suffix = (" " + "; ".join(details) + ".") if details else ""
    raise FlowGateError(
        "formal CLI generation provenance required before promote-candidate: "
        f"{candidate} is not a formal platform-agent candidate.{suffix} "
        "Run generate-scene to create the prompt manifest and .agent_tasks.md, have the main platform agent write the candidate Markdown and manifest JSON with constraint flags, "
        "then run agent-review-scene on that exact candidate. Manual files are exploratory/debug-only; --allow-unreviewed is maintainer/debug-only."
    )


def _ensure_candidate_reviewed(gate: dict[str, object], *, allow_review_notes: bool) -> None:
    if gate.get("status") == "pass":
        return
    if allow_review_notes and gate.get("status") == "notes_unresolved":
        return
    message = str(gate.get("message") or "candidate review gate failed")
    review = str(gate.get("review") or "")
    candidate = str(gate.get("candidate") or "")
    lint_gate = gate.get("style_lint")
    lint_hint = ""
    if isinstance(lint_gate, dict) and lint_gate.get("status") == "blocking":
        lint_hint = f" Style Lint Gate: {style_lint_gate_message(lint_gate)}."
    raise FlowGateError(
        "formal candidate review required before promote-candidate: "
        f"{message}.{lint_hint} Run agent-review-scene with --draft {candidate}, have the platform agent write {review}, "
        "and promote only after conclusion=pass with this candidate listed in source_paths. "
        "Formal Skill hosts must not use --allow-unreviewed to bypass this gate; that flag is maintainer/debug-only."
    )


def _candidate_bullets(text: str, heading: str) -> list[str]:
    section = _section(text, heading, level=3)
    items = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped.lstrip("-").strip()
        if item and item not in {"无。", "待真实 provider 补全。"}:
            items.append(item)
    return items or ["无。"]


def _render_draft(
    scene_id: str,
    scene_path: str,
    candidate_path: str,
    generated_at: str,
    body: str,
    sections: dict[str, list[str]],
) -> str:
    return f"""# 场景草稿工作台：{scene_id}

生成时间：{generated_at}

来源候选：`{candidate_path}`
场景文件：`{scene_path}`

## 使用规则

- 本文件由模型候选转入草稿通道，不是最终正稿。
- 写作时必须遵守上下文包中的硬 canon、人物状态和风格约束。
- 审查未通过前，不得把正文移动到正稿。
- 新事实、人物状态、关系和伏笔变化只列为候选，等待人工确认。

## 正文草稿

{body.strip()}

## 状态变化

### 新增事实候选

{_md_list(sections["new_facts"])}

### 人物状态变化

{_md_list(sections["character_changes"])}

### 关系变化

{_md_list(sections["relationship_changes"])}

### 伏笔变化

{_md_list(sections["foreshadowing_changes"])}

### 需要人工确认

{_md_list(sections["approval_items"])}

## 自检

- [ ] 未违背硬 canon。
- [ ] 人物行动符合当前 BDI。
- [ ] 背景故事没有被直白交代，只转化为行为和潜台词。
- [ ] 场景有明确冲突和输出状态。
- [ ] 文风约束被执行。
- [ ] 新事实已列入候选而非直接确认为 canon。
"""


def _render_report(manifest: dict[str, object]) -> str:
    lines = [
        f"# Candidate Promotion：{manifest['scene_id']}",
        "",
        f"- 候选：`{manifest['candidate']}`",
        f"- 草稿：`{manifest['draft']}`",
        f"- 时间：{manifest['promoted_at']}",
        f"- 审批 run：`{manifest.get('approval_run_id') or 'n/a'}`",
        "",
        "## 边界",
        "",
        _md_list(list(manifest["guardrails"])),
    ]
    note = str(manifest.get("selection_note") or "").strip()
    if note:
        lines.extend(["", "## 选择说明", "", note])
    return "\n".join(lines) + "\n"


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- 无。"


def _resolve(root: Path, value: Path | None, default: Path | None = None) -> Path:
    if value is None:
        if default is None:
            raise ValueError("default path is required when value is None")
        return default
    return value if value.is_absolute() else root / value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
