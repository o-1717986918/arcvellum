# Phase 20：多分支剧情推演

## 目标

把单场景角色推演升级为可追踪的多分支候选系统。每个分支都必须保留来源场景、上下文包、评分、风险、写回候选和人工选择记录。

## 新增命令

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench branch-simulate work/demo-work --scene scenes/scene_0001.yaml --rebuild-context
```

常用参数：

- `--branch-count 2..5`：生成候选分支数量，默认 4。
- `--out`：自定义 Markdown 工作台路径。
- `--json-out`：自定义 JSON manifest 路径。
- `--selection-out`：自定义人工选择记录路径。
- `--agent` / `--agent-tasks`：生成 `branch_manifest.agent_tasks.md`，供平台 agent 审查分支和评分。

## 输出

默认输出到 `branches/{scene_id}/`：

- `branch_simulation.md`：面向人类和 Agent 的分支工作台。
- `branch_manifest.json`：结构化分支候选、评分和风险。
- `branch_selection.md`：人工选择、合并策略和 canon 写回确认记录。
- `branch_manifest.agent_tasks.md`：可选平台 agent 任务说明，不写入 JSON。

## 评分维度

- `character_logic`：分支是否能由人物 BDI、恐惧、秘密和道德边界解释。
- `canon_safety`：是否依赖未确认事实，是否触碰硬设定。
- `dramatic_tension`：外部阻碍和内部矛盾是否有效推进。
- `literary_potential`：是否具有主题余味、意象延展和人物深度。
- `longterm_payoff`：是否服务伏笔、下一场景输入和长线结构。

## 分支类型

默认分支：

- 人物逻辑优先。
- 冲突升级优先。
- 伏笔收益优先。
- 道德代价优先。
- 余波沉淀优先。

## 边界

- 分支不是 canon。
- 推荐分支不是自动合并决定。
- `branch_selection.md` 是人工审批记录，不是自动写回动作。
- 新事实、人物重大转折、主线方向改变必须继续走人工确认。
- 正稿发布前仍应运行 `canon-lint`、`review-scene` 或章节级审查。
