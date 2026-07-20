# Phase 24：人物状态演化候选 Patch

## 状态

已在 `v0.24.0` 实现 `state-evolve`。

## 目标

把场景草稿、模型候选、场景编排包中的“人物状态变化”和“关系变化”整理为可审查的人物状态演化候选 patch。该阶段只生成候选，不自动修改人物档案。

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench state-evolve work/demo-work --scene scenes/scene_0001.yaml
```

生成平台 agent 审查任务：

```powershell
python -m literary_engineering_workbench state-evolve work/demo-work --scene scenes/scene_0001.yaml --agent-tasks
```

指定来源产物：

```powershell
python -m literary_engineering_workbench state-evolve work/demo-work `
  --scene scenes/scene_0001.yaml `
  --source drafts/scenes/scene_0001.md
```

`--source` 可指向：

- `drafts/scenes/{scene_id}.md`
- `drafts/candidates/{scene_id}-{provider}-{timestamp}.md`
- `drafts/compositions/{scene_id}_composition.md`
- `drafts/compositions/{scene_id}_composition.json`

当 source 是 composition artifact 时，`state-evolve` 会检查 composition 是否来自正式 `branch_selection.md`。`selection_source: recommended` 或 fallback composition 只能作为内部讨论材料，不能直接推导人物状态 patch。

未指定时，优先使用场景草稿；若无草稿，则尝试最新候选正文；再尝试场景编排 JSON。

## 输出

```text
characters/state_patches/{scene_id}_state_patch.md
characters/state_patches/{scene_id}_state_patch.json
characters/state_patches/{scene_id}_state_patch.agent_tasks.md
```

JSON 包含：

- `scene_id`
- `source_artifact`
- `status: pending_human_approval`
- `characters`
- `unresolved_changes`
- `source_changes`
- `approval_required`
- `guardrails`

## Patch 内容

每个人物 patch 包含：

- 当前状态快照：`state.location`、`state.health`、`state.resources`、`state.known_facts`、`state.unknown_facts`。
- 当前弧光快照：`arc.current_stage`、`arc.expected_change`、`arc.required_trigger_events`。
- 候选新增已知事实。
- 候选资源、位置、健康备注。
- 候选弧光变化。
- 候选关系变化。

## 工作流接入

`run-workflow --mode scene-loop` 已在 `review_ci` 后追加 `state_evolution_patch` 节点。只要草稿存在，workflow state 会记录：

- `state_patch`
- `state_patch_json`
- `state_patch_agent_tasks`（使用 `--agent-tasks` 时）

若草稿不存在，该节点跳过，不从模型候选直接写回人物档案。

## 边界

- `state-evolve` 不修改 `characters/*.yaml`。
- 人物重大转折必须人工确认。
- 未匹配到人物的变化进入 `unresolved_changes`。
- 写回命令应在后续阶段单独实现，并要求审批记录。

## 后续

- `state-apply` 审批后写回命令已由 Phase 25 实现。
- 后续可增加跨章节人物弧光审计。
