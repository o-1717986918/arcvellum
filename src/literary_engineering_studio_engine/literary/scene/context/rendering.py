"""Pure rendering for scene context packets and handoff summaries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextPacketSections:
    scene_id: str
    generated_at: str
    project_config: str
    scene_relative: str
    scene_text: str
    word_budget: str
    canon: str
    characters: str
    plot: str
    handoff: str
    style: str
    retrieval: str


_PACKET_TEMPLATE = """# 场景上下文包：{scene_id}

生成时间：{generated_at}

## 使用规则

- 本文件是写作前工作记忆，不是正稿。
- Canon、人物档案和时间线是硬约束。
- “软记忆检索”只提供参考，不得覆盖硬事实。
- `background_story` 是人物的隐性行为因果，只能影响选择、回避、误判和语气，不应在正文中直白说明。
- 写作完成后必须输出写回计划。

## 项目配置

```yaml
{project_config}
```

## 当前场景

来源：`{scene_relative}`

```yaml
{scene_text}
```

## 场景字数预算

{word_budget}

## 硬约束：Canon 与时间线

{canon}

## 人物状态

{characters}

## 剧情状态

{plot}

## 上一场正式交接

{handoff}

## 风格约束

{style}

## 软记忆检索

查询依据：当前场景字段 + 用户补充 query。

{retrieval}

## 写作任务

请基于以上上下文生成或推演当前场景。生成时必须：

1. 不违背硬 canon。
2. 人物行动符合 BDI 和当前信息差。
3. 人物背景故事只能作为隐性动因，不得变成解释性设定段落。
4. 场景输出必须包含状态变化。
5. 正文清洗后的可交付部分必须遵守“场景字数预算”的目标、上下限和叙事负载；不得用流程痕迹、状态候选、canon 说明或空泛重复填字数。
6. 风格遵守 profile，而不是只模仿表面词汇。
7. 若需要新增事实，写入候选，不直接确认为 canon。

## 写回清单

生成完成后输出：

- 新增事实候选。
- 人物状态变化。
- 关系变化。
- 伏笔变化。
- 需要进入软记忆索引的正文片段。
- 需要人工确认的重大变更。
"""


def render_context_packet(sections: ContextPacketSections) -> str:
    return _PACKET_TEMPLATE.format(**sections.__dict__)


def render_handoff(
    *,
    passed: bool,
    message: str,
    payload: dict[str, object],
) -> str:
    if not payload:
        return f"- 状态：`{'pass' if passed else 'blocked'}`\n- {message}"
    return "\n".join(
        [
            f"- 状态：`{'pass' if passed else 'blocked'}`",
            f"- {message}",
            f"- 前场：`{str(payload.get('scene_id') or '')}`",
            f"- 前场正文摘要：`{str(payload.get('promoted_draft_sha256') or '')[:12]}`",
            f"- 时间落点：{payload.get('time_after') or '未声明'}",
            f"- 地点落点：{payload.get('location_after') or '未声明'}",
            "- 未完成行动：" + _joined(payload.get("unresolved_actions")),
            "- 出场钩子：" + _joined(payload.get("outgoing_hooks")),
        ]
    )


def _joined(value: object) -> str:
    values = value if isinstance(value, list) else []
    return ", ".join(str(item) for item in values if str(item).strip()) or "未登记"


__all__ = ["ContextPacketSections", "render_context_packet", "render_handoff"]
