# Phase 14：工作流持久化基础

## 目标

在不引入新外部依赖的前提下，让工作流运行具备可追踪、可检索和可关联重试的基础。

## 新增能力

`run-workflow` 新增：

- `--run-id`：指定稳定 run id。
- `--resume-run-id`：创建一个与旧 run 关联的新运行。
- `--overwrite-run`：显式允许覆盖同名 run 目录。

`run-langgraph` 新增：

- `--thread-id`：传入外部编排线程 id，并写入 LangGraph 状态。

每次 `run_workflow` 完成后，会追加：

```text
workflow/runs/index.jsonl
```

索引记录包含：

- `run_id`
- `mode`
- `status`
- `scene`
- `chapter_id`
- `started_at`
- `ended_at`
- `human_approval_required`
- `resumed_from`
- `state_path`
- `log_path`

## 运行示例

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench run-workflow work/demo-work `
  --mode scene-loop `
  --run-id scene-0001-pass-1
```

关联重试：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench run-workflow work/demo-work `
  --mode scene-loop `
  --run-id scene-0001-pass-2 `
  --resume-run-id scene-0001-pass-1
```

LangGraph thread id：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench run-langgraph work/demo-work `
  --thread-id demo-thread-001
```

## 边界

- `--resume-run-id` 当前是“关联重试”，不是节点级断点续跑。
- 同名 `--run-id` 默认拒绝覆盖，必须显式传 `--overwrite-run`。
- 当前环境没有 `langgraph.checkpoint.sqlite`，因此 SQLite checkpointer 未作为硬依赖接入。
- 后续如引入 `langgraph-checkpoint-sqlite`，应保持文件 backed `workflow/runs/index.jsonl` 作为稳定审计层。
