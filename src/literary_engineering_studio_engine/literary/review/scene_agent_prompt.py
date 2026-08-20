"""Prompt rendering for provider-backed scene review."""

from __future__ import annotations

import json

from ...anti_ai_style import (
    ANTI_EVASION_REVISION_PROTOCOL,
    ANTI_EVASION_SHORT_RULE,
    render_ai_style_lint_block,
)
from ...creative_quality import render_creative_quality_prompt
from ...draft_text import final_body_from_workbench_text
from ...new_character_register import render_new_character_register_contract


USER_PROMPT_TEMPLATE = """Source paths: {source_paths}
Exact candidate SHA-256: {candidate_sha256}
The JSON field `candidate_sha256` must equal this value exactly.

{style_lint}

{quality_prompt}

{anti_evasion_protocol}

审查时必须执行：{anti_evasion_rule}

## Word Budget Gate

以下是用清洗后的可交付正文统计出的确定性字数门禁。正式门禁按中文内容字符判断，计入汉字和中文标点；机器非空白字符只作为诊断映射。不得统计状态变化候选、canon 说明、workflow 痕迹、scene 编号或文件路径：

```json
{word_budget}
```

若 status 不是 pass 或 not_required，`conclusion` 不得为 pass。若 status 已通过，也必须判断 narrative_load_satisfied；不能靠重复心理解释、空泛描写或流程文本填字数。

## Reader Experience Gate

以下是章节义务与读者体验契约的确定性结构门禁。语义判断由平台 Agent 完成，但若 status 不是 pass 或 not_required，`conclusion` 不得为 pass。即使结构通过，也必须判断正文是否推进了读者问题、承诺回报、暂扣信息、兑现/延迟、情绪曲线、张力来源、新鲜度、反摘要要求和读后余味；不能只复述事件梗概：

```json
{reader_adherence}
```

## Narrative Rhythm / Scene Bridge Gate

{rhythm_contract}

若正文没有接住入场压力、没有完成本场 scene_turn、没有按 tension_curve 的 entry / peak / exit 形成可辨识的升降、没有详略节奏差异，或结尾没有给下一场留下可接续钩子，`conclusion` 不得为 pass。不得只因元数据填写完整就判断通过；必须结合正文中的动作、信息、选择与代价验证曲线，并在 JSON 中填写 `narrative_rhythm_adherence`。

同时检查 Scene Function Gate、Reader Question / Promise-Payoff、Narrative Distance 和 Texture Variety：本场不能只是补设定或聊天；必须有推进主线、改变关系、制造误判、兑现/设置问题、改变人物选择、扩大代价或转移读者认知之一。若读者问题没有管理、承诺没有兑现/延迟说明、叙述距离持续贴脸解释心理，或章节内连续场景材料过于单一，不能 clean pass。

## Scene YAML

```yaml
{scene_text}
```

## Draft

```markdown
{draft_text}
```

## Context Packet

```markdown
{context_text}
```

## Context Trace

```json
{context_trace_text}
```

## Style Prompt / Profile

```markdown
{style_text}
```

## New Character Register Contract

{new_character_contract}
"""


def scene_review_system_prompt() -> str:
    return """You are a literary engineering scene review agent.

Review the scene as a workbench artifact, not as final praise. Judge character logic, canon safety, plot movement, reader-experience payoff, narrative rhythm and scene bridge, mounted style adherence, punctuation rhythm, deterministic Style Lint evidence, anti-evasion revision integrity, cleaned-body word-budget adherence, new character registration, canon writeback declaration, and revision actions. Output JSON only using schema scene_review.v1, including structured style_adherence, word_budget_adherence, reader_experience_adherence, narrative_rhythm_adherence, canon_writeback, new_character_register, and revision_integrity objects."""


def scene_review_user_prompt(
    scene_text: str,
    draft_text: str,
    context_text: str,
    context_trace_text: str,
    style_text: str,
    source_paths: list[str],
    word_budget_adherence: dict[str, object],
    reader_adherence: dict[str, object],
    rhythm_contract_text: str,
    quality_profile: dict[str, object],
    scene_id: str,
    candidate_sha256: str,
) -> str:
    draft_body = final_body_from_workbench_text(draft_text) or draft_text
    return USER_PROMPT_TEMPLATE.format(
        source_paths=source_paths,
        candidate_sha256=candidate_sha256,
        style_lint=render_ai_style_lint_block(draft_body, profile=quality_profile, scope=scene_id),
        quality_prompt=render_creative_quality_prompt(quality_profile, scope=scene_id),
        anti_evasion_protocol=ANTI_EVASION_REVISION_PROTOCOL,
        anti_evasion_rule=ANTI_EVASION_SHORT_RULE,
        word_budget=json.dumps(word_budget_adherence, ensure_ascii=False, indent=2),
        reader_adherence=json.dumps(reader_adherence, ensure_ascii=False, indent=2),
        rhythm_contract=rhythm_contract_text,
        scene_text=scene_text[:6000],
        draft_text=draft_text[:9000] or "Draft missing.",
        context_text=context_text[:6000] or "Context packet missing.",
        context_trace_text=context_trace_text[:6000]
        or "Context trace missing. Clean pass is forbidden for formal review until `context` is rerun and the trace is inspected.",
        style_text=style_text[:5000] or "Style prompt/profile missing.",
        new_character_contract=render_new_character_register_contract(),
    )


__all__ = ["scene_review_system_prompt", "scene_review_user_prompt"]
