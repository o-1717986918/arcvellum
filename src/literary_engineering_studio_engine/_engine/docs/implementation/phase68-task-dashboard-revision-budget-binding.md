# Phase 68：平台 Agent 总控、场景修订闭环与场景库存绑定

本阶段补齐三个长期流程漏洞：任务侧车越来越多但缺统一看板；`pass_with_notes` 缺正式修订入口；长篇字数预算和实际章节/场景库存绑定不够强。

## 已实现能力

- 新增 `agent-task-status`：扫描工作项目中的 `.agent_tasks.md`，统计 pending / complete / unknown，检查预期产物是否存在。
- 新增 `route-audit`：在任务看板基础上按 route 检查完成门禁，输出 blocking / warnings。
- `route-audit --route scene-development` 会检查 `pass_with_notes` / warnings / revise_required 是否已有修订报告和修订 manifest。
- `v0.71.0` 起，`route-audit --route scene-development` 会在挂载 Style Skill 时检查 `style_adherence.status`，防止文风只进入 prompt、没有进入正式审查门禁。
- 新增 `revise-scene`：读取场景、草稿、AgentReview notes、上下文包、文风、canon、标点规范和字数预算，生成平台 Agent 可执行的修订任务。
- 增强 `word-budget`：生成分章预算、扫描场景库存、读取清洗后正文长度、列出缺失场景和扩场景任务。

## 新增命令

```powershell
python -m literary_engineering_workbench agent-task-status "<work-dir>"
python -m literary_engineering_workbench route-audit "<work-dir>" --route scene-development
python -m literary_engineering_workbench revise-scene "<work-dir>" --scene scenes/scene_0001.yaml
```

## 关键产物

任务总控：

- `workflow/agent_task_status.md`
- `workflow/agent_task_status.json`

Route 审计：

- `workflow/route_audit.md`
- `workflow/route_audit.json`

场景修订：

- `drafts/revisions/{scene_id}_revision.prompt.json`
- `drafts/revisions/{scene_id}_revision.agent_tasks.md`
- `drafts/revisions/{scene_id}_revision.md`
- `drafts/revisions/{scene_id}_revision_report.md`
- `drafts/revisions/{scene_id}_revision.json`

长篇场景库存绑定：

- `plot/word_budget/scene_inventory_expansion.agent_tasks.md`
- `plot/candidates/scenes/word_budget_scene_inventory.md`
- `reviews/word_budget/scene_inventory_review.md`

## 设计边界

`agent-task-status` 和 `route-audit` 只做诊断，不替平台 Agent 完成创作判断。它们可以指出 sidecar 未处理、预期产物缺失、route gate 未完成、review notes 未解决，但不能直接让候选成为 canon、正式正文或发布稿。

`revise-scene` 也不直接修改 `drafts/scenes/{scene_id}.md`。它准备一份修订 prompt manifest 和任务侧车，平台 Agent 写出修订候选和修订报告。修订候选通过审查和批准后，才可以进入正式草稿或发布链路。

`word-budget` 的场景库存绑定只负责可重复计算：章节目标、场景数、正文字数、缺口和任务入口。扩哪些场景、补哪些冲突、如何避免灌水，仍由平台 Agent 依据文学判断完成。

## 完成标准

- `agent-task-status` 可扫描 sidecar 并报告缺失预期产物。
- `route-audit` 可检查 route gate，并输出 Markdown / JSON 面板；挂载文风时可阻塞缺失或未通过的 `style_adherence`。
- `revise-scene` 可生成修订任务、prompt manifest 和预期输出路径。
- `word-budget` 可输出 `chapter_budgets` 与 `scene_inventory_binding`，并生成扩场景任务侧车。
- `SKILL.md`、`AGENTS.md`、`agentread.yaml`、`references/cli-run-protocol.md`、`references/workflows.md` 和 `references/artifact-contracts.md` 均纳入新链路。
- 回归测试覆盖新增 CLI、修订任务和字数库存绑定。
