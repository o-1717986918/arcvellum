from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from .agent_tasks import default_agent_tasks_path, write_agent_tasks
from .context_broker import default_context_trace_path
from .context_packet import build_context_packet
from .punctuation_standard import PUNCTUATION_STANDARD_SHORT_RULE


@dataclass(frozen=True)
class CharacterCard:
    file: Path
    character_id: str
    name: str
    role: str
    belief: list[str]
    desire: list[str]
    intention: list[str]
    fear: list[str]
    secret: list[str]
    background_summary: str
    formative_events: list[str]
    behavior_influences: list[str]
    reveal_policy: str
    moral_line: str
    speech_style: str


@dataclass(frozen=True)
class SimulationResult:
    project_root: Path
    output_path: Path
    context_path: Path
    scene_id: str
    character_count: int
    agent_tasks_path: Path | None = None


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
                if indent <= base_indent:
                    break
                stripped = sub.strip()
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


def _world_agent_task() -> str:
    return """基于上方每个角色的行动提案，评估：
1. 这些行动在当前场景（时间、地点、参与者）中会产生什么直接后果？
2. 哪些行动与 canon 约束冲突？（对照 canon/world_rules.yaml 和 canon/forbidden_changes.yaml，如文件不存在则说明缺失）
3. 这些行动会如何影响下一场景（next_hooks）？
将答案填入下方"后果记录"列表，并遵守标准中文标点。"""


def _branch_agent_task() -> str:
    return """基于角色行动提案和 World Agent 后果记录，补全 Branch A/B/C：
1. Branch A 优先人物最合理，不追求便利剧情。
2. Branch B 优先戏剧冲突最强，但不能突破 canon 和人物道德边界。
3. Branch C 优先文学余味最强，强调选择后的关系余波和主题回声。
每个分支都要填写行动链、代价、新事实候选和后续钩子，并遵守标准中文标点。"""


def _director_agent_task() -> str:
    return """基于 Branch A/B/C，补全评分表：
1. 人物合理性：是否能由 BDI、fear、moral_line、background_story 解释。
2. Canon 安全：是否触碰硬设定、时间线、适用范围或禁止变化。
3. 戏剧张力：是否产生可持续冲突。
4. 文学性：是否有余味、隐性动因和非直白表达。
5. 后续展开：是否能自然导向 next_hooks。
风险栏必须写明不可自动合并的原因。"""


def _canon_agent_task() -> str:
    return """审查所有分支：
1. 标出违背硬设定或缺少依据的分支。
2. 列出需要人工确认的新 canon。
3. 列出不允许直接合并的人物状态、关系、地点、组织或规则变化。
如果缺少 canon 文件或 scene.yaml 中 canon_refs 不足，也要明确写出。"""


def _merge_agent_task() -> str:
    return """基于 Director Agent 评分表，选择推荐分支并给出理由。如果不只选一个，说明保留哪些另一分支的元素。不要把推荐分支当作自动决定；合并前必须列出需要用户确认的事项。"""


def _writeback_agent_task() -> str:
    return """基于推荐分支和 Canon Auditor 结果，整理写回候选：
1. 新增事实候选。
2. 人物状态变化。
3. 关系变化。
4. 伏笔变化。
5. 下一场景输入状态。
所有写回项必须保持候选，不得直接写入 canon 或 characters/*.yaml。"""


def _write_roleplay_agent_tasks(
    root: Path,
    scene_path: Path,
    context_path: Path,
    output_path: Path,
    cards: list[CharacterCard],
) -> Path:
    scene_rel = scene_path.relative_to(root).as_posix()
    context_rel = context_path.relative_to(root).as_posix()
    context_trace_path = default_context_trace_path(context_path)
    context_trace_rel = context_trace_path.relative_to(root).as_posix()
    character_sources = [card.file for card in cards]
    source_paths = [
        scene_path,
        context_path,
        context_trace_path,
        *character_sources,
        root / "canon" / "world_rules.yaml",
        root / "canon" / "forbidden_changes.yaml",
        root / "plot" / "outline.md",
        root / "plot" / "foreshadowing.csv",
        output_path,
    ]
    character_task = "\n".join(
        f"- 读取 `{card.file.relative_to(root).as_posix()}`，以 {card.name or card.character_id} 第一人称回答 belief / desire / intention / fear / secret / moral_line / background_story 如何影响本场景行动。"
        for card in cards
    ) or "- 未发现正式人物档案时，在输出文件中标注依据不足，要求先补人物档案。"
    return write_agent_tasks(
        default_agent_tasks_path(output_path),
        title=f"simulate-scene {scene_path.stem}",
        root=root,
        source_paths=source_paths,
        notes=[
            "roleplay_simulation.md 是可读工作台，不再内嵌 AGENT_TASK 标记。",
            f"完成后更新 RP 工作台：{output_path.relative_to(root).as_posix()}",
            "必须写入同名 agent_completion.json；否则 branch-simulate --agent 会阻塞。",
        ],
        tasks=[
            (
                "完成读取回执",
                f"""读取 `{scene_rel}`、`{context_rel}`、`{context_trace_rel}`、参与角色文件、canon/world_rules.yaml、canon/forbidden_changes.yaml、plot/outline.md 和 plot/foreshadowing.csv。先用 context trace 核对本次上下文实际加载的文件，再更新 `{output_path.relative_to(root).as_posix()}` 的“读取回执”：已读文件、缺失文件、不可突破硬约束、写回边界。""",
            ),
            (
                "补全 Character Agent 行动提案",
                f"""{character_task}
每个角色必须回答：
1. 在当前场景中我相信什么。
2. 我最想避免什么。
3. 我会采取什么具体行动。
4. 我为什么不会采取另一个更方便剧情的行动。
5. 我的行动会给下一场景留下什么代价。
6. background_story 如何通过选择、回避、误判或语气间接影响行动，而不是被直接说明。
将答案写回 `{output_path.relative_to(root).as_posix()}` 的对应角色“行动提案”。""",
            ),
            (
                "补全 World Agent 后果推演",
                _world_agent_task() + f"\n将结果写回 `{output_path.relative_to(root).as_posix()}` 的“后果记录”。",
            ),
            (
                "补全分支候选",
                _branch_agent_task() + f"\n将结果写回 `{output_path.relative_to(root).as_posix()}` 的 Branch A/B/C。",
            ),
            (
                "补全 Director 评分",
                _director_agent_task() + f"\n将评分写回 `{output_path.relative_to(root).as_posix()}` 的分支评分表。",
            ),
            (
                "补全 Canon Auditor",
                _canon_agent_task() + f"\n将审查结果写回 `{output_path.relative_to(root).as_posix()}`。",
            ),
            (
                "补全合并建议与写回候选",
                _merge_agent_task() + "\n\n" + _writeback_agent_task() + f"\n将推荐、确认项和写回候选写回 `{output_path.relative_to(root).as_posix()}`。",
            ),
        ],
    )


def build_roleplay_simulation(
    project_root: Path,
    scene: Path | None = None,
    context: Path | None = None,
    query: str = "",
    rebuild_context: bool = False,
    output: Path | None = None,
    agent_mode: bool = False,
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
    if rebuild_context or not context_path.exists() or not default_context_trace_path(context_path).exists():
        context_result = build_context_packet(root, scene=scene_path, query=query, rebuild_index=True, output=context_path)
        context_path = context_result.output_path

    cards = _load_characters(root)
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

{_agent_task_if(agent_mode, _world_agent_task())}### 后果记录

- <!-- 填写世界后果 -->

## 分支候选

{_agent_task_if(agent_mode, _branch_agent_task())}### Branch A：人物最合理

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

{_agent_task_if(agent_mode, _director_agent_task())}| 分支 | 人物合理性 | Canon 安全 | 戏剧张力 | 文学性 | 后续展开 | 风险 | 总评 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| A | 0 | 0 | 0 | 0 | 0 |  |  |
| B | 0 | 0 | 0 | 0 | 0 |  |  |
| C | 0 | 0 | 0 | 0 | 0 |  |  |

## Canon Auditor

{_agent_task_if(agent_mode, _canon_agent_task())}- 违背硬设定的分支：
- 需要人工确认的新 canon：
- 不允许直接合并的变化：

## 合并建议

{_agent_task_if(agent_mode, _merge_agent_task())}- 推荐分支：
- 推荐理由：
- 需要保留的另一分支元素：
- 合并前必须确认：

## 写回候选

{_agent_task_if(agent_mode, _writeback_agent_task())}- 新增事实候选：
- 人物状态变化：
- 关系变化：
- 伏笔变化：
- 下一场景输入状态：
"""
    output_path.write_text(content, encoding="utf-8")
    agent_tasks_path = None
    if agent_mode:
        agent_tasks_path = _write_roleplay_agent_tasks(root, scene_path, context_path, output_path, cards)
    return SimulationResult(
        project_root=root,
        output_path=output_path,
        context_path=context_path,
        scene_id=sid,
        character_count=len(cards),
        agent_tasks_path=agent_tasks_path,
    )
