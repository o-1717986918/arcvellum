"""LLM/Agent-backed scene review artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .anti_ai_style import ANTI_EVASION_REVISION_PROTOCOL, ANTI_EVASION_SHORT_RULE, lint_ai_style, render_ai_style_lint_block
from .agent_provider import run_agent_task
from .agent_schema import validate_agent_run
from .context_broker import default_context_trace_path
from .draft_text import final_body_from_workbench_text
from .narrative_rhythm import render_narrative_rhythm_contract
from .new_character_register import empty_new_character_register, render_new_character_register_contract
from .reader_experience import reader_experience_adherence_for_body, scene_chapter_obligation_id
from .word_budget import word_budget_adherence_for_body


@dataclass(frozen=True)
class AgentSceneReviewResult:
    project_root: Path
    scene_id: str
    run_dir: Path
    report_path: Path
    json_path: Path
    validation_path: Path
    conclusion: str


def review_scene_with_agent(
    project_root: Path,
    *,
    scene: Path | None = None,
    draft: Path | None = None,
    provider: str = "auto",
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentSceneReviewResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    scene_path = _resolve_scene(root, scene)
    scene_id = scene_path.stem
    draft_path = _resolve_draft(root, scene_id, draft)
    context_path = root / "memory" / "context_packets" / f"{scene_id}.md"
    context_trace_path = default_context_trace_path(context_path)
    style_prompt_path = _first_existing(_style_source_candidates(root))
    source_paths = [_rel_str(scene_path, root)]
    if draft_path.exists():
        source_paths.append(_rel_str(draft_path, root))
    if context_path.exists():
        source_paths.append(_rel_str(context_path, root))
    if context_trace_path.exists():
        source_paths.append(_rel_str(context_trace_path, root))
    if style_prompt_path and style_prompt_path.exists():
        source_paths.append(_rel_str(style_prompt_path, root))
    composition_json = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    if composition_json.exists():
        source_paths.append(_rel_str(composition_json, root))
    obligation_path = root / "plot" / "chapter_obligations" / f"{scene_chapter_obligation_id(root, scene_path)}.json"
    if obligation_path.exists():
        source_paths.append(_rel_str(obligation_path, root))

    scene_text = _read(scene_path)
    draft_text = _read(draft_path) if draft_path.exists() else ""
    draft_body = final_body_from_workbench_text(draft_text) or draft_text
    context_text = _read(context_path) if context_path.exists() else ""
    context_trace_text = _read(context_trace_path) if context_trace_path.exists() else ""
    style_text = _read(style_prompt_path) if style_prompt_path else ""
    word_budget_adherence = word_budget_adherence_for_body(root, scene_path, draft_body)
    reader_adherence = reader_experience_adherence_for_body(root, scene_path, draft_body)
    rhythm_contract_text = render_narrative_rhythm_contract(root, scene_path, composition_json if composition_json.exists() else None)
    dry_payload = _dry_scene_review(scene_id, draft_text, source_paths, word_budget_adherence, reader_adherence)
    run_result = run_agent_task(
        root,
        agent_id="scene-reviewer",
        task=f"review-scene:{scene_id}",
        system_prompt=_system_prompt(),
        user_prompt=_user_prompt(scene_text, draft_text, context_text, context_trace_text, style_text, source_paths, word_budget_adherence, reader_adherence, rhythm_contract_text),
        provider=provider,
        metadata={"schema_name": "scene_review.v1", "scene_id": scene_id, "source_paths": source_paths},
        dry_run_output=dry_payload,
    )
    validation = validate_agent_run(root, run_dir=run_result.run_dir, schema_name="scene_review.v1")
    parsed = json.loads(run_result.parsed_output_path.read_text(encoding="utf-8"))
    parsed["agent_run_dir"] = _rel_str(run_result.run_dir, root)
    parsed["schema_validation"] = _rel_str(validation.validation_path, root)

    report_path = _resolve_output(root, output, "reviews", "agent", f"{scene_id}_scene_review.md")
    json_path = _resolve_output(root, json_output, "reviews", "agent", f"{scene_id}_scene_review.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(parsed, validation.status), encoding="utf-8")
    return AgentSceneReviewResult(
        project_root=root,
        scene_id=scene_id,
        run_dir=run_result.run_dir,
        report_path=report_path,
        json_path=json_path,
        validation_path=validation.validation_path,
        conclusion=str(parsed.get("conclusion", "")),
    )


def _system_prompt() -> str:
    return """You are a literary engineering scene review agent.

Review the scene as a workbench artifact, not as final praise. Judge character logic, canon safety, plot movement, reader-experience payoff, narrative rhythm and scene bridge, mounted style adherence, punctuation rhythm, deterministic Style Lint evidence, anti-evasion revision integrity, cleaned-body word-budget adherence, new character registration, canon writeback declaration, and revision actions. Output JSON only using schema scene_review.v1, including structured style_adherence, word_budget_adherence, reader_experience_adherence, narrative_rhythm_adherence, canon_writeback, new_character_register, and revision_integrity objects."""


def _user_prompt(
    scene_text: str,
    draft_text: str,
    context_text: str,
    context_trace_text: str,
    style_text: str,
    source_paths: list[str],
    word_budget_adherence: dict[str, object],
    reader_adherence: dict[str, object],
    rhythm_contract_text: str,
) -> str:
    draft_body = final_body_from_workbench_text(draft_text) or draft_text
    return f"""Source paths: {source_paths}

{render_ai_style_lint_block(draft_body)}

{ANTI_EVASION_REVISION_PROTOCOL}

审查时必须执行：{ANTI_EVASION_SHORT_RULE}

## Word Budget Gate

以下是用清洗后的可交付正文统计出的确定性字数门禁。正式门禁按中文内容字符判断，计入汉字和中文标点；机器非空白字符只作为诊断映射。不得统计状态变化候选、canon 说明、workflow 痕迹、scene 编号或文件路径：

```json
{json.dumps(word_budget_adherence, ensure_ascii=False, indent=2)}
```

若 status 不是 pass 或 not_required，`conclusion` 不得为 pass。若 status 已通过，也必须判断 narrative_load_satisfied；不能靠重复心理解释、空泛描写或流程文本填字数。

## Reader Experience Gate

以下是章节义务与读者体验契约的确定性结构门禁。语义判断由平台 Agent 完成，但若 status 不是 pass 或 not_required，`conclusion` 不得为 pass。即使结构通过，也必须判断正文是否推进了读者问题、承诺回报、暂扣信息、兑现/延迟、情绪曲线、张力来源、新鲜度、反摘要要求和读后余味；不能只复述事件梗概：

```json
{json.dumps(reader_adherence, ensure_ascii=False, indent=2)}
```

## Narrative Rhythm / Scene Bridge Gate

{rhythm_contract_text}

若正文没有接住入场压力、没有完成本场 scene_turn、没有详略节奏差异，或结尾没有给下一场留下可接续钩子，`conclusion` 不得为 pass。必须在 JSON 中填写 `narrative_rhythm_adherence`。

同时检查 Scene Function Gate、Reader Question / Promise-Payoff、Narrative Distance 和 Texture Variety：本场不能只是补设定或聊天；必须有推进主线、改变关系、制造误判、兑现/设置问题、改变人物选择、扩大代价或转移读者认知之一。若读者问题没有管理、承诺没有兑现/延迟说明、叙述距离持续贴脸解释心理，或章节内连续场景材料过于单一，不能 clean pass。

## Scene YAML

```yaml
{scene_text[:6000]}
```

## Draft

```markdown
{draft_text[:9000] or "Draft missing."}
```

## Context Packet

```markdown
{context_text[:6000] or "Context packet missing."}
```

## Context Trace

```json
{context_trace_text[:6000] or "Context trace missing. Clean pass is forbidden for formal review until `context` is rerun and the trace is inspected."}
```

## Style Prompt / Profile

```markdown
{style_text[:5000] or "Style prompt/profile missing."}
```

## New Character Register Contract

{render_new_character_register_contract()}
"""


def _dry_scene_review(
    scene_id: str,
    draft_text: str,
    source_paths: list[str],
    word_budget_adherence: dict[str, object],
    reader_adherence: dict[str, object],
) -> dict[str, object]:
    draft_body = final_body_from_workbench_text(draft_text) or draft_text
    has_body = bool(draft_body.strip()) and "<!-- 在这里写入场景正文。 -->" not in draft_body
    lint_issues = lint_ai_style(draft_body) if has_body else []
    blocking_lint = [issue for issue in lint_issues if issue.severity not in {"low"}]
    budget_status = str(word_budget_adherence.get("status") or "").strip().lower()
    budget_blocked = budget_status not in {"pass", "not_required"}
    reader_status = str(reader_adherence.get("status") or "").strip().lower()
    reader_blocked = reader_status not in {"pass", "not_required"}
    conclusion = "revise_required" if not has_body or blocking_lint or budget_blocked or reader_blocked else "pass_with_notes"
    warnings = [] if has_body else ["场景草稿缺少可审查正文，需先补正文或提升生成候选。"]
    warnings.extend(f"Style lint: {issue.rule} - {issue.message}" for issue in blocking_lint)
    if budget_blocked:
        warnings.append(f"Word budget gate: {word_budget_adherence.get('message')}")
    if reader_blocked:
        warnings.append(f"Reader experience gate: {reader_adherence.get('message')}")
    style_source = _style_source_label(source_paths)
    style_status = "pass_with_notes" if style_source and has_body else ("revise_required" if style_source else "not_applicable")
    style_revision_actions = (
        ["真实平台审查需确认挂载文风已经影响叙述距离、句法节奏、意象系统、对白语气和标点停顿。"] if style_source else []
    )
    lint_revision_actions = [
        f"按确定性 Style Lint 逐句复核 `{issue.sample}`，修订 {issue.rule}，不得用脚本直接删改造成语义反转。"
        for issue in blocking_lint
        if issue.sample
    ]
    return {
        "schema": "literary-engineering-workbench/scene-review-agent/v1",
        "scene_id": scene_id,
        "conclusion": conclusion,
        "summary": "dry-run scene reviewer preserved the review contract and source trace.",
        "blocking_issues": [],
        "warnings": warnings,
        "revision_actions": ["保留人工确认点；不要把候选事实直接写入 canon。"] + lint_revision_actions,
        "character_logic": [
            {
                "character": "all",
                "assessment": "检查人物 BDI、背景故事隐性动因和当前状态是否共同支持行动。",
            }
        ],
        "canon_risks": [],
        "style_notes": [
            "后续真实模型审查应核对 style_prompt.md 是否影响句法、叙述距离和意象调度。",
            *[f"确定性 Style Lint 检出 {issue.rule}: {issue.sample}" for issue in lint_issues],
        ],
        "style_adherence": {
            "status": style_status,
            "style_profile": style_source or "n/a",
            "evidence": ["dry-run 仅保持审查契约；真实平台 agent 需要引用正文证据。"] if style_source else [],
            "deviations": [],
            "revision_actions": style_revision_actions,
        },
        "word_budget_adherence": {
            **word_budget_adherence,
            "narrative_load_satisfied": budget_status in {"pass", "not_required"},
        },
        "reader_experience_adherence": {
            **reader_adherence,
            "reader_promise_satisfied": reader_status in {"pass", "not_required"},
            "semantic_review_required": reader_adherence.get("requires_platform_agent_semantic_review", True),
        },
        "narrative_rhythm_adherence": {
            "status": "pass_with_notes" if has_body else "revise_required",
            "rhythm_executed": has_body,
            "bridge_executed": has_body,
            "flatness_risks": ["dry-run cannot semantically judge rhythm; platform agent must verify scene turn and bridge."],
            "revision_actions": [],
        },
        "canon_writeback": {
            "status": "unknown",
            "canon_change": "unknown",
            "no_canon_change_reason": "",
            "candidate_patch": "",
        },
        "new_character_register": empty_new_character_register(),
        "revision_integrity": {
            "status": "pass" if not blocking_lint else "revise_required",
            "anti_evasion_checked": True,
            "evasion_risks": [f"{issue.rule}: {issue.sample}" for issue in blocking_lint if issue.rule in {"mechanical-contrast-frame", "contrast-evasion-frame"}],
            "evasion_risks_unresolved": [f"{issue.rule}: {issue.sample}" for issue in blocking_lint if issue.rule in {"mechanical-contrast-frame", "contrast-evasion-frame"}],
            "retained_transitions": [],
            "burden_of_proof": [],
            "message": "dry-run deterministic review; platform agent must perform semantic revision-integrity review.",
        },
        "source_paths": source_paths,
        "agent_confidence": "dry-run",
        "next_gate": "schema_validation_then_human_review",
    }


def _render_report(payload: dict[str, object], validation_status: str) -> str:
    lines = [
        f"# Agent 场景审查：{payload.get('scene_id', '')}",
        "",
        f"- 结论：`{payload.get('conclusion', '')}`",
        f"- Schema：`{validation_status}`",
        f"- Agent Run：`{payload.get('agent_run_dir', '')}`",
        "",
        "## 字数预算门禁",
        "",
        f"- 状态：`{(payload.get('word_budget_adherence') if isinstance(payload.get('word_budget_adherence'), dict) else {}).get('status', '')}`",
        f"- 清洗后正文中文内容字符：`{(payload.get('word_budget_adherence') if isinstance(payload.get('word_budget_adherence'), dict) else {}).get('clean_body_chinese_chars', '')}`",
        f"- 机器非空白字符诊断：`{(payload.get('word_budget_adherence') if isinstance(payload.get('word_budget_adherence'), dict) else {}).get('clean_body_machine_chars', '')}`",
        "",
        "## 读者体验门禁",
        "",
        f"- 状态：`{(payload.get('reader_experience_adherence') if isinstance(payload.get('reader_experience_adherence'), dict) else {}).get('status', '')}`",
        f"- 信息：{(payload.get('reader_experience_adherence') if isinstance(payload.get('reader_experience_adherence'), dict) else {}).get('message', '')}",
        f"- 语义复核：`{(payload.get('reader_experience_adherence') if isinstance(payload.get('reader_experience_adherence'), dict) else {}).get('semantic_review_required', '')}`",
        "",
        "## 叙事节奏与场景桥接门禁",
        "",
        f"- 状态：`{(payload.get('narrative_rhythm_adherence') if isinstance(payload.get('narrative_rhythm_adherence'), dict) else {}).get('status', '')}`",
        f"- 节奏执行：`{(payload.get('narrative_rhythm_adherence') if isinstance(payload.get('narrative_rhythm_adherence'), dict) else {}).get('rhythm_executed', '')}`",
        f"- 桥接执行：`{(payload.get('narrative_rhythm_adherence') if isinstance(payload.get('narrative_rhythm_adherence'), dict) else {}).get('bridge_executed', '')}`",
        "",
        "## Canon 写回判断",
        "",
        f"- 状态：`{(payload.get('canon_writeback') if isinstance(payload.get('canon_writeback'), dict) else {}).get('status', '')}`",
        f"- Canon 变化：`{(payload.get('canon_writeback') if isinstance(payload.get('canon_writeback'), dict) else {}).get('canon_change', '')}`",
        f"- 无变化理由：{(payload.get('canon_writeback') if isinstance(payload.get('canon_writeback'), dict) else {}).get('no_canon_change_reason', '')}",
        "",
        "## 摘要",
        "",
        str(payload.get("summary", "")),
        "",
        "## 修订动作",
        "",
    ]
    for item in payload.get("revision_actions", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## 风险", ""])
    for item in payload.get("blocking_issues", []) or []:
        lines.append(f"- BLOCKING: {item}")
    for item in payload.get("warnings", []) or []:
        lines.append(f"- WARNING: {item}")
    return "\n".join(lines) + "\n"


def _resolve_scene(root: Path, scene: Path | None) -> Path:
    path = root / "scenes" / "scene_0001.yaml" if scene is None else (scene if scene.is_absolute() else root / scene)
    if not path.exists():
        raise FileNotFoundError(f"scene file not found: {path}")
    return path.resolve()


def _resolve_draft(root: Path, scene_id: str, draft: Path | None) -> Path:
    if draft is None:
        return root / "drafts" / "scenes" / f"{scene_id}.md"
    return draft if draft.is_absolute() else root / draft


def _resolve_output(root: Path, value: Path | None, *default_parts: str) -> Path:
    if value is None:
        return root.joinpath(*default_parts)
    return value if value.is_absolute() else root / value


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _style_source_candidates(root: Path) -> list[Path]:
    candidates = [
        root / "style" / "active_style_skill.json",
        root / "style" / "style_prompt.md",
        root / "style" / "demo-author" / "style_prompt.md",
        root / "style" / "style-profile.md",
    ]
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        try:
            payload = json.loads(active.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        for key in ("prompt", "style_skill", "mount_path"):
            value = str(payload.get(key) or "").strip()
            if not value:
                continue
            path = root / value
            if path.is_dir():
                candidates.extend([path / "prompt.md", path / "style_skill.json", path / "style-profile.md"])
            else:
                candidates.append(path)
    return candidates


def _style_source_label(source_paths: list[str]) -> str:
    for value in source_paths:
        normalized = value.replace("\\", "/")
        if normalized.startswith("style/") and (
            "active_style_skill.json" in normalized
            or "style_prompt.md" in normalized
            or "prompt.md" in normalized
            or "style-profile.md" in normalized
        ):
            return normalized
    return ""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
