# Phase 25：候选转正与人物状态审批写回

## 状态

已在 `v0.25.0` 实现 `promote-candidate`、`state-apply`，并让 `run-workflow --promote-candidate` 支持候选稿转入草稿审查通道。`v0.72.0` 起，`promote-candidate` 默认要求候选稿先通过 candidate-specific 平台 Agent 场景审查。

## 目标

补齐两个本地工作流断点：

- 模型 provider 输出的 `drafts/candidates/` 候选稿可以被人工选择后转成标准草稿。
- `state-evolve` 生成的人物状态候选 patch 可以在 approve 审批后受控写回人物档案。

## 候选稿转草稿

命令：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-review-scene work/demo-work --scene scenes/scene_0001.yaml --draft drafts/candidates/scene_0001-platform-agent.md
# 平台 Agent 填写 reviews/agent/scene_0001_scene_review.json，source_paths 必须包含该候选路径，conclusion=pass。
python -m literary_engineering_workbench promote-candidate work/demo-work --scene scenes/scene_0001.yaml
```

指定候选：

```powershell
python -m literary_engineering_workbench promote-candidate work/demo-work `
  --scene scenes/scene_0001.yaml `
  --candidate drafts/candidates/scene_0001-dry-run-20260717T000000Z.md
```

输出：

```text
drafts/scenes/{scene_id}.md
drafts/promotions/{scene_id}_promotion.json
drafts/promotions/{scene_id}_promotion.md
```

`promote-candidate` 会把：

- `## 正文候选` 映射到 `## 正文草稿`。
- `## 状态变化候选` 下的候选项映射到正式草稿的 `## 状态变化`。
- 来源候选、场景文件、选择说明和审批 run 写入 promotion manifest。

边界：

- 它不确认 canon。
- 它不改 `characters/`。
- 它默认要求 `reviews/agent/{scene_id}_scene_review.json` 已经审查并引用了正在 promotion 的 exact candidate。
- `pass_with_notes`、warnings、revision_actions、style_notes 或 style_adherence 偏差默认阻塞 promotion，正式链路先走 `revise-scene` 并 re-review。
- 草稿仍必须运行 `review-scene`。
- 已存在草稿时默认拒绝覆盖，除非传入 `--overwrite`。
- `--allow-unreviewed` 与 `--allow-review-notes` 仅保留给维护者调试/回归测试；正式 Skill 宿主不得使用，且 route-audit 会把这些 manifest 标记为阻塞。

## Workflow 接入

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench run-workflow work/demo-work `
  --mode scene-loop `
  --generate-candidate `
  --promote-candidate `
  --provider dry-run
```

`scene-loop` 中的相关节点顺序：

1. `scene_composition`
2. `generate_candidate`（可选）
3. `promote_candidate`（可选，要求 candidate-specific review gate）
4. `draft_workspace`
5. `review_ci`
6. `state_evolution_patch`

如果 `promote_candidate` 生成了草稿，`draft_workspace` 会保留已有草稿并跳过。若候选未写入或未通过 candidate-specific review gate，promotion 会延迟或阻塞。workflow state 会记录：

- `promoted_draft`
- `promotion_manifest`
- `promotion_report`

## 人物状态审批写回

命令：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench state-apply work/demo-work `
  --patch characters/state_patches/scene_0001_state_patch.json `
  --approval-run-id scene-0001-pass-1
```

默认要求 `workflow/approvals/index.jsonl` 中存在 `decision=approve` 的审批记录。维护者调试/回归测试可用：

```powershell
python -m literary_engineering_workbench state-apply work/demo-work --allow-unapproved
```

正式 Skill 宿主不得用 `--allow-unapproved` 跳过审批。

输出：

```text
characters/state_patches/{scene_id}_state_apply.json
characters/state_patches/{scene_id}_state_apply.md
```

写回范围：

- `state.known_facts`
- `state.resources`
- `state.location`
- `state.health`
- `arc.required_trigger_events`
- `relationships`
- `memory_refs`

边界：

- 不写 `canon/facts.json`。
- 不处理未匹配人物的变化，除非显式传入 `--allow-unresolved`。
- 重复执行时会尽量去重已有列表项。
- `state-apply` 是审批后动作，不进入默认自动 workflow。

## 当前仍未闭环

- Dify Human Input 节点仍需在真实 Dify 环境中补齐并验证。
- LangGraph 仍是大节点 adapter，尚未拆成每个 CLI 节点的细粒度 StateGraph。
- 文风 profile 目前是本地统计与评测，不是可训练风格模型。
