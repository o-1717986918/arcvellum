from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from ....context_broker import context_trace_status, default_context_trace_path
from ....context_packet import build_context_packet
from ....punctuation_standard import PUNCTUATION_STANDARD_SHORT_RULE
from .agent_tasks import (
    branch_agent_task,
    canon_agent_task,
    director_agent_task,
    initialize_roleplay_agent_outputs,
    merge_agent_task,
    world_agent_task,
    writeback_agent_task,
)
from .depth import (
    normalize_roleplay_depth,
    roleplay_depth_contract,
    select_cards_for_depth,
)
from .models import CharacterCard, SimulationResult


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _scene_id(scene_path: Path) -> str:
    return scene_path.stem or "scene"


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.*?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    if value in {"null", "[]", "{}"}:
        return ""
    return value.strip('"')


def _list_after(text: str, key: str) -> list[str]:
    lines = text.splitlines()
    results: list[str] = []
    for i, line in enumerate(lines):
        if re.match(rf"^\s*{re.escape(key)}:\s*$", line):
            base_indent = len(line) - len(line.lstrip())
            for sub in lines[i + 1 :]:
                if not sub.strip():
                    continue
                indent = len(sub) - len(sub.lstrip())
                stripped = sub.strip()
                # YAML permits an indentationless sequence immediately below
                # a mapping key (``aliases:\n- name``).  Treat that standard
                # form as part of the value instead of ending the block.
                if indent <= base_indent and not stripped.startswith("-"):
                    break
                if stripped.startswith("-"):
                    item = stripped[1:].strip()
                    if item:
                        results.append(item.strip('"'))
            break
    return results


def _nested_scalar(text: str, section: str, key: str) -> str:
    match = re.search(rf"(?ms)^\s*{re.escape(section)}:\s*\n(.*?)(?=^\S|\Z)", text)
    if not match:
        return ""
    return _scalar(match.group(1), key)


def _nested_list(text: str, section: str, key: str) -> list[str]:
    match = re.search(rf"(?ms)^\s*{re.escape(section)}:\s*\n(.*?)(?=^\S|\Z)", text)
    if not match:
        return []
    return _list_after(match.group(1), key)


def _load_characters(root: Path) -> list[CharacterCard]:
    chars_dir = root / "characters"
    if not chars_dir.exists():
        return []
    cards: list[CharacterCard] = []
    for path in sorted(chars_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = _read(path)
        if not text:
            continue
        cards.append(
            CharacterCard(
                file=path,
                character_id=_scalar(text, "character_id") or path.stem,
                name=_scalar(text, "name") or path.stem,
                role=_scalar(text, "role"),
                belief=_nested_list(text, "bdi", "belief"),
                desire=_nested_list(text, "bdi", "desire"),
                intention=_nested_list(text, "bdi", "intention"),
                fear=_nested_list(text, "psychology", "fear"),
                secret=_nested_list(text, "psychology", "secret"),
                background_summary=_nested_scalar(text, "background_story", "summary")
                or _nested_scalar(text, "identity", "background"),
                formative_events=_nested_list(text, "background_story", "formative_events"),
                behavior_influences=_nested_list(text, "background_story", "behavior_influences"),
                reveal_policy=_nested_scalar(text, "background_story", "reveal_policy") or "implicit_only",
                moral_line=_nested_scalar(text, "psychology", "moral_line"),
                speech_style=_nested_scalar(text, "speech_style", "rhythm")
                or _nested_scalar(text, "speech_style", "vocabulary"),
            )
        )
    return cards


def _bullets(items: list[str]) -> str:
    if not items:
        return "- 未填写"
    return "\n".join(f"- {item}" for item in items)


def _character_prompt(card: CharacterCard, root: Path, *, agent_mode: bool = False) -> str:
    rel = card.file.relative_to(root).as_posix()
    action_task = ""
    if agent_mode:
        action_task = "平台 Agent 待办见同名 `.agent_tasks.md`；补全后保留证据，不要把任务标记写回本文件。\n\n"
    return f"""## Character Agent：{card.name}

来源：`{rel}`

- 身份/职责：{card.role or "未填写"}
- 道德边界：{card.moral_line or "未填写"}
- 语言习惯：{card.speech_style or "未填写"}

### Belief

{_bullets(card.belief)}

### Desire

{_bullets(card.desire)}

### Intention

{_bullets(card.intention)}

### Fear / Secret

Fear:

{_bullets(card.fear)}

Secret:

{_bullets(card.secret)}

### 内部背景故事（只作为行为因果，不得直白输出）

- 概要：{card.background_summary or "未填写"}
- 呈现策略：{card.reveal_policy or "implicit_only"}

塑形事件：

{_bullets(card.formative_events)}

行为影响：

{_bullets(card.behavior_influences)}

### 推演任务

请只以该角色的已知信息、误解、欲望和当前意图为依据回答：

1. 我现在相信什么？
2. 我最想避免什么？
3. 我会采取什么行动？
4. 我为什么不会采取另一个更方便剧情的行动？
5. 我的行动会给下一场景留下什么代价？
6. 背景故事如何通过选择、回避、误判或语气间接影响行动，而不是被直接说明？

### 行动提案

{action_task}-
"""


def _agent_task_if(enabled: bool, instruction: str) -> str:
    if not enabled:
        return ""
    return "平台 Agent 待办见同名 `.agent_tasks.md`；补全后删除空占位或改写为正式推演记录。\n\n"


def _agent_mode_execution_gate(
    enabled: bool,
    *,
    root: Path,
    scene_rel: str,
    context_rel: str,
    context_trace_rel: str,
    cards: list[CharacterCard],
) -> str:
    if not enabled:
        return ""
    character_files = "\n".join(f"- `{card.file.relative_to(root).as_posix()}`" for card in cards) or "- 未发现正式人物档案。"
    return f"""## 平台 Agent 执行门禁

执行任务已写入同名 `.agent_tasks.md`。在补全任何 RP 推演内容前，平台 Agent 必须先完成读取回执：

1. 读取场景文件 `{scene_rel}`。
2. 读取上下文包 `{context_rel}`。
3. 读取上下文来源证明 `{context_trace_rel}`，核对本轮实际加载的 canon、character、style、plot、word-budget 与 retrieval 文件。
4. 读取本轮参与角色或所有正式人物档案：
{character_files}
5. 读取存在的 canon/world_rules.yaml、canon/forbidden_changes.yaml、plot/outline.md、plot/foreshadowing.csv。
6. 用下方“读取回执”列出已读文件、缺失文件、不可突破硬约束和写回边界。
7. 若关键资料缺失，仍可提出候选推演，但必须标注“依据不足”，不得把候选当成 canon。

### 读取回执

- 已读取：
- 缺失文件：
- 不可突破硬约束：
- 写回边界：本文件只生成推演与候选，不直接写入 canon、characters、scenes 或 drafts。

"""


def _agent_mode_usage_rule(enabled: bool) -> str:
    if not enabled:
        return ""
    return (
        "- 本工作台不内嵌任务指令块；平台 Agent 必须读取同名 `.agent_tasks.md`，完成后写入 `.agent_completion.json`。\n"
        f"- 平台 agent 补全文档时必须执行标点规范：{PUNCTUATION_STANDARD_SHORT_RULE}\n"
    )


def _simulation_result(
    root: Path,
    output_path: Path,
    context_path: Path,
    scene_id: str,
    cards: list[CharacterCard],
    agent_tasks_path: Path | None,
) -> SimulationResult:
    return SimulationResult(
        project_root=root,
        output_path=output_path,
        context_path=context_path,
        scene_id=scene_id,
        character_count=len(cards),
        agent_tasks_path=agent_tasks_path,
    )


def build_roleplay_simulation(
    project_root: Path,
    scene: Path | None = None,
    context: Path | None = None,
    query: str = "",
    rebuild_context: bool = False,
    output: Path | None = None,
    agent_mode: bool = False,
    roleplay_depth: str = "targeted",
) -> SimulationResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else (scene if scene.is_absolute() else root / scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")

    sid = _scene_id(scene_path)
    context_path = context if context and context.is_absolute() else (
        root / context if context else root / "memory" / "context_packets" / f"{sid}.md"
    )
    if (
        rebuild_context
        or not context_path.exists()
        or not default_context_trace_path(context_path).exists()
        or not context_trace_status(root, sid, context_path).passed
    ):
        context_result = build_context_packet(root, scene=scene_path, query=query, rebuild_index=True, output=context_path)
        context_path = context_result.output_path

    roleplay_depth = normalize_roleplay_depth(roleplay_depth)
    scene_text = _read(scene_path)
    cards = select_cards_for_depth(_load_characters(root), scene_text, roleplay_depth)
    output_path = output if output and output.is_absolute() else (
        root / output if output else root / "branches" / sid / "roleplay_simulation.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    character_sections = "\n\n".join(_character_prompt(card, root, agent_mode=agent_mode) for card in cards)
    if not character_sections:
        character_sections = "未发现正式人物档案。请先在 `characters/` 下创建非 `_template.yaml` 的人物文件。"
    scene_rel = scene_path.relative_to(root).as_posix()
    context_rel = context_path.relative_to(root).as_posix()
    context_trace_rel = default_context_trace_path(context_path).relative_to(root).as_posix()

    content = f"""# 角色推演实验室：{sid}

生成时间：{datetime.now(timezone.utc).isoformat()}

正式 CLI 来源：`simulate-scene`
RP 深度：`{roleplay_depth}`
RP 深度契约：{roleplay_depth_contract(roleplay_depth)}

场景文件：`{scene_rel}`
上下文包：`{context_rel}`
上下文 Trace：`{context_trace_rel}`

## 使用规则

- 本文件用于剧情分支推演，不是正文草稿。
- Character Agent 只负责角色行动合理性，不负责最终叙事文本。
- World Agent 负责判断行动后果。
- Director Agent 负责比较戏剧张力、主题价值和后续展开空间。
- Canon Auditor 必须否决违背硬设定的分支。
- 合并任何分支前必须人工确认。
{_agent_mode_usage_rule(agent_mode)}

{_agent_mode_execution_gate(agent_mode, root=root, scene_rel=scene_rel, context_rel=context_rel, context_trace_rel=context_trace_rel, cards=cards)}
## 场景摘要

```yaml
{_read(scene_path)}
```

## 角色代理

{character_sections}

## World Agent：后果推演

请基于 canon、地点、资源、时间线和世界规则评估每个角色行动的后果。

{_agent_task_if(agent_mode, world_agent_task())}### 后果记录

- <!-- 填写世界后果 -->

## 分支候选

{_agent_task_if(agent_mode, branch_agent_task())}### Branch A：人物最合理

- 行动链：
- 代价：
- 新事实候选：
- 后续钩子：

### Branch B：戏剧冲突最强

- 行动链：
- 代价：
- 新事实候选：
- 后续钩子：

### Branch C：文学余味最强

- 行动链：
- 代价：
- 新事实候选：
- 后续钩子：

## Director Agent：分支评分

{_agent_task_if(agent_mode, director_agent_task())}| 分支 | 人物合理性 | Canon 安全 | 戏剧张力 | 文学性 | 后续展开 | 风险 | 总评 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| A | 0 | 0 | 0 | 0 | 0 |  |  |
| B | 0 | 0 | 0 | 0 | 0 |  |  |
| C | 0 | 0 | 0 | 0 | 0 |  |  |

## Canon Auditor

{_agent_task_if(agent_mode, canon_agent_task())}- 违背硬设定的分支：
- 需要人工确认的新 canon：
- 不允许直接合并的变化：

## 合并建议

{_agent_task_if(agent_mode, merge_agent_task())}- 推荐分支：
- 推荐理由：
- 需要保留的另一分支元素：
- 合并前必须确认：

## 写回候选

{_agent_task_if(agent_mode, writeback_agent_task())}- 新增事实候选：
- 人物状态变化：
- 关系变化：
- 伏笔变化：
- 下一场景输入状态：
"""
    output_path.write_text(content, encoding="utf-8")
    agent_tasks_path = None
    if agent_mode:
        agent_tasks_path = initialize_roleplay_agent_outputs(
            root,
            scene_path,
            context_path,
            output_path,
            cards,
            roleplay_depth,
        )
    return _simulation_result(root, output_path, context_path, sid, cards, agent_tasks_path)
