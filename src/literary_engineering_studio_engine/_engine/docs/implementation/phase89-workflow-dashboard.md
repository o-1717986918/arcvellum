# Phase 89：跨路线 Workflow Dashboard

状态：completed in v0.89.0

## 背景

Phase 84-88 已经把七条正式路线接入 CLI-mediated task loop、Prompt Registry、Context Trace、New Character Register、Workflow Contract Validation、Reader Experience Contract。剩余问题不是单个 gate 不存在，而是平台 Agent 或用户需要在一个视图里看见：

1. 当前每条路线卡在哪一步；
2. 哪些 `.agent_tasks.md` 还没有 completion marker；
3. 哪些 route-audit gate 正在 blocking；
4. 最近 task events 发生了什么；
5. 下一步最该修什么。

如果这些信息分散在 `workflow-state`、`agent-task-status`、`route-audit`、`workflow-events` 中，平台 Agent 仍可能为了速度只看其中一个报告。

## 实现

新增 `workflow_dashboard.py` 和 CLI 命令：

```powershell
python -m literary_engineering_workbench workflow-dashboard <project>
```

命令会刷新并读取：

- `workflow-state --route overall`
- `agent-task-status`
- 七条正式 route audit
- `workflow/events/task_events.jsonl`

输出：

```text
workflow/dashboard/workflow_dashboard.json
workflow/dashboard/workflow_dashboard.md
workflow/dashboard/workflow_dashboard.html
```

## 设计约束

- Dashboard 只读，不调用 `task-complete`，不写 creative artifacts，不晋升候选，不批准发布。
- 它不是第二套状态机，所有判断仍来自已有正式事实源。
- HTML 是静态 cockpit，可直接打开；本地前端也可以轮询 JSON。
- blocking row 不代表“可以跳过”，而是下一项修复任务。

## 验证

新增 `tests/test_workflow_dashboard.py`：

- 检查 dashboard 能生成 JSON/Markdown/HTML；
- 检查七条 route audit 都进入汇总；
- 检查 recent events 会包含 task event；
- 检查 CLI 暴露并能运行 `workflow-dashboard`。

## 后续

可把本地前端的 workflow 页面改为读取 `workflow/dashboard/workflow_dashboard.json`，并在运行 platform Agent 自动推进时定期刷新该命令，让用户看到项目维护行为流。
