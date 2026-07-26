"""Platform-Agent task sidecar construction for roleplay simulation."""

from __future__ import annotations

from pathlib import Path

from ....agent_tasks import default_agent_tasks_path, write_agent_tasks
from ....context_broker import default_context_trace_path
from ....semantic_task_contracts import (
    semantic_artifact_relative_path,
    write_semantic_artifact_template,
)
from .depth import roleplay_depth_contract
from .models import CharacterCard


def world_agent_task() -> str:
    return """基于上方每个角色的行动提案，评估：
1. 这些行动在当前场景（时间、地点、参与者）中会产生什么直接后果？
2. 哪些行动与 canon 约束冲突？（对照 canon/world_rules.yaml 和 canon/forbidden_changes.yaml，如文件不存在则说明缺失）
3. 这些行动会如何影响下一场景（next_hooks）？
将答案填入下方"后果记录"列表，并遵守标准中文标点。"""


def branch_agent_task() -> str:
    return """基于角色行动提案和 World Agent 后果记录，补全 Branch A/B/C：
1. Branch A 优先人物最合理，不追求便利剧情。
2. Branch B 优先戏剧冲突最强，但不能突破 canon 和人物道德边界。
3. Branch C 优先文学余味最强，强调选择后的关系余波和主题回声。
每个分支都要填写行动链、代价、新事实候选和后续钩子，并遵守标准中文标点。"""


def director_agent_task() -> str:
    return """基于 Branch A/B/C，补全评分表：
1. 人物合理性：是否能由 BDI、fear、moral_line、background_story 解释。
2. Canon 安全：是否触碰硬设定、时间线、适用范围或禁止变化。
3. 戏剧张力：是否产生可持续冲突。
4. 文学性：是否有余味、隐性动因和非直白表达。
5. 后续展开：是否能自然导向 next_hooks。
风险栏必须写明不可自动合并的原因。"""


def canon_agent_task() -> str:
    return """审查所有分支：
1. 标出违背硬设定或缺少依据的分支。
2. 列出需要人工确认的新 canon。
3. 列出不允许直接合并的人物状态、关系、地点、组织或规则变化。
如果缺少 canon 文件或 scene.yaml 中 canon_refs 不足，也要明确写出。"""


def merge_agent_task() -> str:
    return """基于 Director Agent 评分表，选择推荐分支并给出理由。如果不只选一个，说明保留哪些另一分支的元素。不要把推荐分支当作自动决定；合并前必须列出需要用户确认的事项。"""


def writeback_agent_task() -> str:
    return """基于推荐分支和 Canon Auditor 结果，整理写回候选：
1. 新增事实候选。
2. 人物状态变化。
3. 关系变化。
4. 伏笔变化。
5. 下一场景输入状态。
所有写回项必须保持候选，不得直接写入 canon 或 characters/*.yaml。"""


def initialize_roleplay_agent_outputs(
    root: Path,
    scene_path: Path,
    context_path: Path,
    output_path: Path,
    cards: list[CharacterCard],
    roleplay_depth: str,
) -> Path:
    scene_id = scene_path.stem or "scene"
    write_semantic_artifact_template(
        root,
        "roleplay-agent-task",
        scene_id,
        source=output_path.relative_to(root).as_posix(),
        overwrite=True,
    )
    return _write_roleplay_agent_tasks(
        root,
        scene_path,
        context_path,
        output_path,
        cards,
        roleplay_depth,
    )


def _write_roleplay_agent_tasks(
    root: Path,
    scene_path: Path,
    context_path: Path,
    output_path: Path,
    cards: list[CharacterCard],
    roleplay_depth: str,
) -> Path:
    scene_rel = scene_path.relative_to(root).as_posix()
    context_rel = context_path.relative_to(root).as_posix()
    trace_path = default_context_trace_path(context_path)
    trace_rel = trace_path.relative_to(root).as_posix()
    result_rel = semantic_artifact_relative_path(
        "roleplay-agent-task",
        scene_path.stem or "scene",
    )
    source_paths = _source_paths(
        root,
        scene_path,
        context_path,
        trace_path,
        output_path,
        result_rel,
        cards,
    )
    return write_agent_tasks(
        default_agent_tasks_path(output_path),
        title=f"simulate-scene {scene_path.stem}",
        root=root,
        source_paths=source_paths,
        notes=_task_notes(result_rel, roleplay_depth),
        tasks=_task_steps(
            root,
            cards,
            scene_rel=scene_rel,
            context_rel=context_rel,
            trace_rel=trace_rel,
            result_rel=result_rel,
        ),
    )


def _source_paths(
    root: Path,
    scene_path: Path,
    context_path: Path,
    trace_path: Path,
    output_path: Path,
    result_rel: str,
    cards: list[CharacterCard],
) -> list[Path]:
    return [
        scene_path,
        context_path,
        trace_path,
        *(card.file for card in cards),
        root / "canon" / "world_rules.yaml",
        root / "canon" / "forbidden_changes.yaml",
        root / "plot" / "outline.md",
        root / "plot" / "foreshadowing.csv",
        output_path,
        root / result_rel,
    ]


def _task_notes(result_rel: str, roleplay_depth: str) -> list[str]:
    return [
        "roleplay_simulation.md 是可读工作台，不再内嵌 AGENT_TASK 标记。",
        f"RP 的正式语义结论必须写入：{result_rel}",
        f"本轮 RP 深度契约：{roleplay_depth_contract(roleplay_depth)}",
        "不要改写 roleplay_simulation.md；它是 CLI 生成的输入工作台。",
        "必须写入同名 agent_completion.json；否则 branch-simulate --agent 会阻塞。",
    ]


def _task_steps(
    root: Path,
    cards: list[CharacterCard],
    *,
    scene_rel: str,
    context_rel: str,
    trace_rel: str,
    result_rel: str,
) -> list[tuple[str, str]]:
    character_task = _character_task(root, cards)
    return [
        (
            "完成读取回执",
            f"""读取 `{scene_rel}`、`{context_rel}`、`{trace_rel}`、参与角色文件、canon/world_rules.yaml、canon/forbidden_changes.yaml、plot/outline.md 和 plot/foreshadowing.csv。先用 context trace 核对本次上下文实际加载的文件。把实际读取证据写入 `{result_rel}` 的 evidence_paths，并在 findings 中记录缺失文件、不可突破硬约束和写回边界。""",
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
将每个角色的结论写入 `{result_rel}` 的 character_actions。每项必须含角色标识、belief_or_desire、chosen_action、rejected_convenient_action、cost_to_next_scene 和 background_story_influence。""",
        ),
        (
            "补全 World Agent 后果推演",
            world_agent_task() + f"\n将结果写入 `{result_rel}` 的 world_consequences。",
        ),
        (
            "补全分支候选",
            branch_agent_task() + f"\n将结果写入 `{result_rel}` 的 branch_pressures。每项要说明分支可利用的压力、代价和下一场景钩子。",
        ),
        (
            "补全 Director 评分",
            director_agent_task() + f"\n将评分理由浓缩进 `{result_rel}` 的 findings，避免只写空泛分数。",
        ),
        (
            "补全 Canon Auditor",
            canon_agent_task() + f"\n将风险写入 `{result_rel}` 的 canon_risks。",
        ),
        (
            "补全合并建议与写回候选",
            merge_agent_task()
            + "\n\n"
            + writeback_agent_task()
            + f"\n将可追踪的写回候选写入 `{result_rel}` 的 writeback_candidates。完成时把 status 设为 complete、needs_revision 或 blocked；不得保留 pending_agent_judgment。",
        ),
    ]


def _character_task(root: Path, cards: list[CharacterCard]) -> str:
    tasks = "\n".join(
        f"- 读取 `{card.file.relative_to(root).as_posix()}`，以 {card.name or card.character_id} 第一人称回答 belief / desire / intention / fear / secret / moral_line / background_story 如何影响本场景行动。"
        for card in cards
    )
    return tasks or "- 未发现正式人物档案时，在输出文件中标注依据不足，要求先补人物档案。"
