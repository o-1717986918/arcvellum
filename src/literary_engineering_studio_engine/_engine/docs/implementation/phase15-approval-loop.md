# Phase 15：审批闭环

## 目标

让人工审批结果进入工程循环：不仅记录 `approve / revise / reject`，还要建立审批索引和后续任务。

## 新增能力

审批记录模块：

- `record_workflow_approval`
- `build_approval_summary`

CLI：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench approval-summary work/demo-work
```

API：

```text
POST /workflow/approve
```

返回：

- `approval_path`
- `index_path`
- `task_path`

## 文件协议

每个 run 的审批记录：

```text
workflow/approvals/{run_id}.jsonl
```

全局审批索引：

```text
workflow/approvals/index.jsonl
```

汇总报告：

```text
workflow/approvals/approval_summary.md
```

revise / reject 后续任务：

```text
workflow/tasks/{run_id}-{decision}-{timestamp}.md
```

## 决策语义

- `approve`：记录通过，可进入发布候选，但不自动写 canon。
- `revise`：保留可用部分，生成修订任务。
- `reject`：当前产物不得进入发布候选，生成重做任务。

## 边界

- 审批闭环只产生记录、汇总和任务，不直接改写 `canon/`。
- Dify 只需调用 `/workflow/approve`，后端负责落盘。
- 后续发布命令必须读取审批记录，而不是相信 UI 状态。
