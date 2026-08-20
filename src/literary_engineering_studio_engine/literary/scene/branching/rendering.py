"""Pure Markdown rendering for scene branch simulation artifacts."""

from __future__ import annotations

from pathlib import Path

from ..facts import SceneFacts


def render_branch_report(
    root: Path,
    scene_path: Path,
    context_path: Path,
    payload: dict[str, object],
) -> str:
    lines = [
        f"# 多分支剧情推演：{payload['scene_id']}",
        "",
        *_metadata_lines(root, scene_path, context_path, payload),
        "",
        *_usage_lines(),
        "",
        *_scene_lines(payload["scene_facts"]),
        "",
        *_score_table(payload["branches"]),
        "",
        "## 分支候选",
        "",
    ]
    for branch in payload["branches"]:
        lines.extend(_branch_lines(branch))
    lines.extend(
        [
            "## 人工选择",
            "",
            "请在 `branch_selection.md` 中记录选择、理由、合并元素和必须确认的 canon 写回项。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_branch_selection(scene: SceneFacts, payload: dict[str, object]) -> str:
    manifest_dir = str(payload["selection_record"]).rsplit("/", 1)[0]
    return f"""# Branch Selection：{scene.scene_id}

来源 manifest：`{manifest_dir}/branch_manifest.json`
推荐分支：`{payload['recommended_branch'] or 'n/a'}`

## 人工决定

- decision: pending
- selected_branch:
- fallback_reason: <!-- 仅当已有有效 Agent 提案却选择固定回退时，具体说明提案为何不成立 -->
- reviewer:
- selected_at:

## 选择理由

- <!-- 填写选择理由 -->

## 合并策略

- 保留的主分支：
- 吸收的其他分支元素：
- 放弃的元素：
- 下一场景输入：

## Canon 写回确认

- 新增事实：
- 人物状态变化：
- 关系变化：
- 伏笔变化：
- 禁止自动写回项：

## 审查要求

- 合并前运行 `canon-lint`。
- 正文草稿生成后运行 `review-scene`。
- 若涉及主线方向改变，保留本选择记录作为审批证据。
"""


def _metadata_lines(
    root: Path,
    scene_path: Path,
    context_path: Path,
    payload: dict[str, object],
) -> list[str]:
    return [
        f"- 生成时间：{payload['generated_at']}",
        "- 正式 CLI 来源：`branch-simulate`",
        f"- 场景文件：`{_relative(scene_path, root)}`",
        f"- 上下文包：`{_relative(context_path, root)}`",
        f"- 上下文 Trace：`{payload.get('context_trace', '')}`",
        f"- 推荐分支：`{payload['recommended_branch'] or 'n/a'}`",
        f"- 人工选择记录：`{payload['selection_record']}`",
    ]


def _usage_lines() -> list[str]:
    return [
        "## 使用规则",
        "",
        "- 分支不是 canon。",
        "- 推荐分支只代表当前启发式评分最高，不是自动合并决定。",
        "- 新事实、人物重大转折和主线分支合并必须人工确认。",
        "- 进入正稿前应继续运行 `canon-lint`、`review-scene` 或章节级审查。",
    ]


def _scene_lines(scene: object) -> list[str]:
    data = scene if isinstance(scene, dict) else {}
    participants = data.get("participants") or []
    return [
        "## 场景摘要",
        "",
        f"- 章节：`{data.get('chapter_id') or 'n/a'}`",
        f"- 地点：{data.get('location') or '未填写'}",
        f"- 参与者：{', '.join(participants) if participants else '未填写'}",
        f"- 场景目标：{data.get('scene_goal') or '未填写'}",
        f"- 外部冲突：{data.get('external_conflict') or '未填写'}",
        f"- 内部冲突：{data.get('internal_conflict') or '未填写'}",
    ]


def _score_table(branches: object) -> list[str]:
    rows = branches if isinstance(branches, list) else []
    lines = [
        "## 分支评分总览",
        "",
        "| 分支 | 状态 | 人物逻辑 | Canon 安全 | 戏剧张力 | 文学潜力 | 长线收益 | 总分 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for branch in rows:
        scores = branch["scores"]
        lines.append(
            "| `{}` {} | {} | {} | {} | {} | {} | {} | {} |".format(
                branch["branch_id"],
                _escape_pipe(branch["title"]),
                branch["status"],
                scores["character_logic"],
                scores["canon_safety"],
                scores["dramatic_tension"],
                scores["literary_potential"],
                scores["longterm_payoff"],
                branch["total_score"],
            )
        )
    return lines


def _branch_lines(branch: dict[str, object]) -> list[str]:
    return [
        f"### {branch['title']} `{branch['branch_id']}`",
        "",
        f"- 策略：{branch['strategy']}",
        f"- 前提：{branch['premise']}",
        f"- 状态：`{branch['status']}`",
        "",
        "行动链：",
        "",
        _md_list(branch["action_chain"]),
        "",
        "人物测试：",
        "",
        _md_list(branch["character_tests"]),
        "",
        "Canon 检查：",
        "",
        _md_list(branch["canon_checks"]),
        "",
        "风险：",
        "",
        _md_list(branch["risks"]),
        "",
        "写回候选：",
        "",
        _writeback_markdown(branch["writeback_candidates"]),
        "",
    ]


def _writeback_markdown(data: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for key, values in data.items():
        lines.append(f"- `{key}`")
        lines.extend(f"  - {value}" for value in values)
    return "\n".join(lines)


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- 无。"


def _escape_pipe(value: object) -> str:
    return str(value).replace("|", "\\|")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


__all__ = ["render_branch_report", "render_branch_selection"]
