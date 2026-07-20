# Phase 28：Agent JSON Schema 与修复循环

## 目标

把 Agent 输出从“可以解析 JSON”提升为“必须符合明确 schema”。本阶段建立 schema registry、校验命令和修复命令，为后续审查、提示词生成、JSON patch plan、多 Agent 汇总提供统一门禁。

## 新增能力

- `schemas/agent_outputs/*.schema.json`：轻量 schema 规范。
- `agent_schema.py`：加载 schema、校验 `parsed_output.json`、生成最小 dry-run payload、执行 repair。
- `agent-validate`：校验指定 agent run。
- `agent-repair`：把原始输出、解析输出和校验错误交给 repair agent，输出到 `repair_attempts/`。

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-validate work/demo --run-id api-agent-test --schema generic_agent_output.v1
python -m literary_engineering_workbench agent-repair work/demo --run-id api-agent-test --schema scene_review.v1 --provider dry-run
```

## 产物

- `agents/runs/{run_id}/schema_validation.json`
- `agents/runs/{run_id}/repair_attempts/{timestamp}/`

## 边界

Schema 通过只代表机器契约通过，不代表 canon、人物状态或正稿可自动写回。
