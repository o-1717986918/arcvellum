# Phase 31：Agent JSON 草案与受控 Patch Plan

## 目标

允许 Agent 根据 schema 生成 JSON 草案和写回计划，但工程层只接收 patch plan，不让模型直接修改源文件。

## 新增能力

- `agent_json_builder.py`
- `agent-build-json`
- `agent-plan-patch`
- `agents/patch_plans/{target}_patch_plan.md`
- `agents/patch_plans/{target}_patch_plan.json`

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-plan-patch work/demo --target characters/linzhou.yaml --source drafts/scenes/scene_0001.md
```

## 写回边界

默认允许 patch plan 指向 `characters/`、`scenes/`、`plot/`、`style/`、`drafts/` 和 `reviews/`。不允许直接指向 `canon/`。所有 patch plan 默认 `approval_required=true`。
