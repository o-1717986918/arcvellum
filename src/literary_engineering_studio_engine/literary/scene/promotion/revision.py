"""Formal platform-agent scene revision workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from ....agent_tasks import write_agent_tasks
from ....anti_ai_style import ANTI_EVASION_REVISION_PROTOCOL, ANTI_EVASION_SHORT_RULE, render_ai_style_lint_block
from ....context_broker import context_trace_status, default_context_trace_path
from ....creative_quality import (
    creative_quality_profile_exists,
    creative_quality_profile_path,
    load_creative_quality_profile,
    render_creative_quality_prompt,
)
from ....context_packet import build_context_packet
from ....draft_text import count_delivery_chars, final_body_from_draft_text
from ....narrative_rhythm import narrative_rhythm_contract
from ....new_character_register import render_new_character_register_contract
from ....punctuation_standard import render_punctuation_standard_for_prompt
from ....reader_experience import reader_experience_contract
from ....word_budget import render_word_budget_generation_standard
from ...style.snapshot import (
    active_style_evidence_paths,
    active_style_mount_snapshot_payload,
    active_style_prompt_path,
)
from .revision_contract import revision_source_requires_anti_evasion_rows


@dataclass(frozen=True)
class SceneRevisionTaskResult:
    project_root: Path
    scene_id: str
    task_path: Path
    prompt_manifest_path: Path
    expected_candidate_path: Path
    expected_report_path: Path
    expected_manifest_path: Path
    source_count: int


def build_scene_revision_task(
    project_root: Path,
    *,
    scene: Path | None = None,
    draft: Path | None = None,
    review: Path | None = None,
    rebuild_context: bool = False,
    query: str = "",
    output: Path | None = None,
    report_output: Path | None = None,
    manifest_output: Path | None = None,
    prompt_manifest_output: Path | None = None,
    task_output: Path | None = None,
) -> SceneRevisionTaskResult:
    root = project_root.resolve()
    if not (root / "project.yaml").exists():
        raise FileNotFoundError(f"work project not found: {root}")
    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else _resolve(root, scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")
    scene_id = scene_path.stem
    draft_path = _resolve(root, draft) if draft else root / "drafts" / "scenes" / f"{scene_id}.md"
    if not draft_path.exists():
        raise FileNotFoundError(f"draft not found: {draft_path}")
    review_path = _resolve(root, review) if review else _find_review(root, scene_id)
    context_path = root / "memory" / "context_packets" / f"{scene_id}.md"
    context_trace_path = default_context_trace_path(context_path)
    if (
        rebuild_context
        or not context_path.exists()
        or not context_trace_path.exists()
        or not context_trace_status(root, scene_id, context_path).passed
    ):
        packet = build_context_packet(root, scene=scene_path, query=query, rebuild_index=True, output=context_path)
        context_path = packet.output_path
        context_trace_path = packet.trace_path or default_context_trace_path(context_path)

    out_dir = root / "drafts" / "revisions"
    candidate = _resolve(root, output) if output else out_dir / f"{scene_id}_revision.md"
    report = _resolve(root, report_output) if report_output else out_dir / f"{scene_id}_revision_report.md"
    manifest = _resolve(root, manifest_output) if manifest_output else out_dir / f"{scene_id}_revision.json"
    prompt_manifest = _resolve(root, prompt_manifest_output) if prompt_manifest_output else out_dir / f"{scene_id}_revision.prompt.json"
    task_path = _resolve(root, task_output) if task_output else candidate.with_suffix(".agent_tasks.md")
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = _source_paths(root, scene_path, draft_path, context_path, context_trace_path, review_path)
    payload = _prompt_manifest(
        root,
        scene_id,
        scene_path,
        draft_path,
        context_path,
        context_trace_path,
        review_path,
        sources,
        candidate,
        report,
        manifest,
    )
    prompt_manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_revision_task(root, scene_id, task_path, prompt_manifest, sources, draft_path, candidate, report, manifest, prompt_payload=payload)
    return SceneRevisionTaskResult(
        project_root=root,
        scene_id=scene_id,
        task_path=task_path,
        prompt_manifest_path=prompt_manifest,
        expected_candidate_path=candidate,
        expected_report_path=report,
        expected_manifest_path=manifest,
        source_count=len(sources),
    )


def _prompt_manifest(
    root: Path,
    scene_id: str,
    scene_path: Path,
    draft_path: Path,
    context_path: Path,
    context_trace_path: Path,
    review_path: Path | None,
    sources: list[Path],
    candidate: Path,
    report: Path,
    manifest: Path,
) -> dict[str, Any]:
    draft_text = draft_path.read_text(encoding="utf-8", errors="ignore")
    body = final_body_from_draft_text(draft_text)
    review_payload = _read_json(review_path) if review_path and review_path.suffix.lower() == ".json" else {}
    style_adherence = review_payload.get("style_adherence") if isinstance(review_payload.get("style_adherence"), dict) else {}
    quality_profile = load_creative_quality_profile(root)
    anti_evasion_rows_required = revision_source_requires_anti_evasion_rows(
        draft_path,
        quality_profile=quality_profile,
        scene_id=scene_id,
    )
    composition_path = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    rhythm = narrative_rhythm_contract(root, scene_path, composition_path if composition_path.exists() else None)
    reader = reader_experience_contract(root, scene_path)
    style_mount_snapshot = active_style_mount_snapshot_payload(root)
    return {
        "schema": "literary-engineering-workbench/scene-revision-prompt/v0.1",
        "generated_at": _now(),
        "scene_id": scene_id,
        "scene": _rel(scene_path, root),
        "draft": _rel(draft_path, root),
        "source_candidate_sha256": _sha256(draft_path),
        "context": _rel(context_path, root) if context_path.exists() else "",
        "context_trace": _rel(context_trace_path, root) if context_trace_path.exists() else "",
        "review": _rel(review_path, root) if review_path else "",
        "style_mount_snapshot": style_mount_snapshot,
        "draft_body_chars": count_delivery_chars(body),
        "expected_outputs": {
            "candidate": _rel(candidate, root),
            "report": _rel(report, root),
            "manifest": _rel(manifest, root),
        },
        "revision_inputs": {
            "agent_review_conclusion": str(review_payload.get("conclusion") or ""),
            "revision_actions": _json_list(review_payload.get("revision_actions")),
            "warnings": _json_list(review_payload.get("warnings")),
            "style_notes": _json_list(review_payload.get("style_notes")),
            "style_adherence": style_adherence,
            "blocking_issues": _json_list(review_payload.get("blocking_issues")),
        },
        "generation_standards": {
            "style_mount_snapshot": style_mount_snapshot,
            "word_budget": render_word_budget_generation_standard(root),
            "narrative_rhythm_contract": rhythm,
            "reader_experience_contract": reader,
            "punctuation": render_punctuation_standard_for_prompt(quality_profile, scope=scene_id),
            "style_lint_before": render_ai_style_lint_block(body, profile=quality_profile, scope=scene_id),
            "creative_quality_profile": quality_profile,
            "creative_quality_profile_digest": quality_profile.get("digest"),
            "creative_quality_prompt": render_creative_quality_prompt(quality_profile, scope=scene_id),
            "anti_evasion": ANTI_EVASION_REVISION_PROTOCOL,
            "anti_evasion_rows_required": anti_evasion_rows_required,
            "output_boundary": "修订候选不得写入 AGENT_TASK、prompt manifest、canon 解释、审查过程或内部 scene 编号。",
            "notes_resolution": "逐条处理 revision_actions / warnings / style_notes / style_adherence；无法处理时写入 waiver reason。",
        },
        "sources": [{"path": _rel(path, root), "chars": len(_read(path))} for path in sources],
    }


def _write_revision_task(
    root: Path,
    scene_id: str,
    task_path: Path,
    prompt_manifest: Path,
    sources: list[Path],
    source_candidate: Path,
    candidate: Path,
    report: Path,
    manifest: Path,
    *,
    prompt_payload: dict[str, Any],
) -> None:
    anti_evasion_rows_required = bool(
        prompt_payload["generation_standards"]["anti_evasion_rows_required"]
    )
    source_paths = list(sources)
    source_paths.append(prompt_manifest)
    write_agent_tasks(
        task_path,
        title=f"formal scene revision {scene_id}",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是正式场景修订闭环任务，由平台 agent 执行，不调用本地 dry-run、http-chat 或外部 agent。",
            "修订候选仍是 candidate，不得直接覆盖 drafts/scenes、canon、characters 或 plot。",
            f"完成后写入修订候选：{_rel(candidate, root)}",
            f"完成后写入修订报告：{_rel(report, root)}",
            f"完成后写入修订 manifest：{_rel(manifest, root)}",
        ],
        tasks=[
            (
                "读取修订材料并写 reading receipt",
                """读取 scene.yaml、draft、context packet、context trace、AgentReview/静态 review、style prompt/profile、word budget、canon/world_rules.yaml、canon/forbidden_changes.yaml、plot/outline.md 和 punctuation-standard.md。若 context trace 缺失、指向错误场景或报告 missing_required_context，不得继续修订，先重跑 context。在修订报告中写 reading receipt：route=scene-development，已读文件，缺失文件，仍未处理的 sidecar。""",
            ),
            (
                "诊断草稿与 review notes",
                """对照 prompt manifest 的 revision_inputs，逐条判断 revision_actions、warnings、style_notes、style_adherence、blocking_issues。若 style_adherence.status=revise_required 或挂载文风下为 not_applicable/missing，必须优先修正文风执行偏差：叙述距离、句法节奏、意象/感官、心理呈现、对白语气、标点停顿和 AI 腔规避。区分小修、局部重写、需要用户确认、不可执行项。若 review 结论是 pass_with_notes，不得静默通过；若是 revise_required/reject，不得只润色。""",
            ),
            (
                "执行反规避修订协议",
                f"""读取 prompt manifest 的 generation_standards.style_lint_before 和 generation_standards.anti_evasion。{ANTI_EVASION_SHORT_RULE}

本次 `anti_evasion_rows_required={str(anti_evasion_rows_required).lower()}`。只有实际修订了机械对照、换皮转折或保留了相关显式转折时，才建立逐字证据行：原句 / 原问题 / 修订句 / 是否仍含转折 / 是否换皮 / 批判性反驳 / 结论。不得把一般写作要求、全文合规检查、字数修复或未改动句子写成 anti_evasion_rows。若该值为 false 且本次没有额外发现真实转折风险，anti_evasion_rows 必须为空，并说明不适用原因。默认从“不合理”开始挑刺；不要用“增强节奏”“体现复杂心理”“更有文学感”作为充分理由。若原句承担信息反转、误判校正或因果揭示，优先改为动作、事实顺序、信息差、物证、对话错位或人物选择，而不是换成另一种显式转折。""",
            ),
            (
                "生成修订候选",
                f"""创建或覆盖 `{_rel(candidate, root)}`。必须包含 `## 修订正文候选`、`## 状态变化候选`、`## 新角色候选登记`、`## 需要人工确认`。正文必须执行 mounted style / style prompt、长篇字数预算、标准中文标点、降低 AI 腔约束、反规避协议、新角色登记契约和 review notes。不得输出工作流、自检表、prompt manifest、AGENT_TASK、canon 解释或 scene 编号。""",
            ),
            (
                "写入修订报告",
                f"""创建或覆盖 `{_rel(report, root)}`。报告必须列出：reading receipt、修订目标、已执行 notes、style_adherence 偏差处理、反规避表、保留显式转折的负担证明、未执行 notes 及 waiver reason、canon/人物/文风/字数/标点检查、是否建议进入 promote-candidate 或重新 review-scene。不要写入 `[AGENT_TASK: ...]`。""",
            ),
            (
                "写入修订 manifest",
                f"""创建或覆盖 `{_rel(manifest, root)}`，只填写模型负责的修订判断：revision_actions_applied、warnings_addressed、style_notes_addressed、style_adherence_addressed、anti_evasion_rows、anti_evasion_not_applicable_reason（仅在确实不适用时）、retained_transition_proofs、evasion_risks_unresolved、new_character_register、waivers。至少一组 addressed/applied 字段必须非空，并且只能登记正文中已经实际发生的修改。

schema、scene_id、source_candidate、source_candidate_sha256、candidate、candidate_sha256、report、source_paths、prompt_manifest、style_mount_snapshot、creative_quality_profile_digest、reader_experience_contract、narrative_rhythm_contract、anti_evasion_protocol_applied、ready_for_review、generated_by、provider、formal_contract_revision 和 writer_session_id 由 Studio 在提交前按精确任务证据绑定；不得猜测、复制或覆盖这些机器字段。

anti_evasion_rows 每项固定填写 source_excerpt、issue、revised_excerpt、still_uses_explicit_transition（JSON 布尔 true/false，不是字符串）、suspected_rephrase（JSON 布尔 true/false，不是字符串）、critical_objection、verdict（resolved 或 retained_with_proof）。摘录必须逐字存在于精确源正文和修订候选正文，且该行必须对应一次真实修订或有负担证明的保留；不得复制通用 requirements/checklist 充当证据。若源文没有机械对照/换皮转折风险且列表为空，必须填写 anti_evasion_not_applicable_reason；不得只写布尔值宣称完成。

{render_new_character_register_contract()}""",
            ),
        ],
    )


def _source_paths(
    root: Path,
    scene_path: Path,
    draft_path: Path,
    context_path: Path,
    context_trace_path: Path,
    review_path: Path | None,
) -> list[Path]:
    candidates = [
        scene_path,
        draft_path,
        context_path,
        context_trace_path,
        review_path,
        root / "canon" / "world_rules.yaml",
        root / "canon" / "forbidden_changes.yaml",
        root / "plot" / "outline.md",
        root / "plot" / "word_budget" / "word_budget.json",
        creative_quality_profile_path(root) if creative_quality_profile_exists(root) else None,
    ]
    candidates.extend(_style_source_paths(root))
    results: list[Path] = []
    seen = set()
    for path in candidates:
        if path is None or not path.exists():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        results.append(path)
    return results


def _style_source_paths(root: Path) -> list[Path]:
    paths = active_style_evidence_paths(root)
    if active_style_prompt_path(root) is not None:
        return paths
    style_root = root / "style"
    for candidate in [style_root / "style_prompt.md", style_root / "style-profile.md"]:
        if candidate.exists():
            paths.append(candidate)
    if style_root.exists():
        paths.extend(sorted(style_root.glob("*/style_prompt.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:2])
    return paths


def _find_review(root: Path, scene_id: str) -> Path | None:
    candidates = [
        root / "reviews" / "agent" / f"{scene_id}_scene_review.json",
        root / "reviews" / f"{scene_id}-review.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _json_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    results = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = "; ".join(f"{key}: {val}" for key, val in item.items() if val not in ("", None))
        else:
            text = str(item).strip()
        if text:
            results.append(text)
    return results


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _rel(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
