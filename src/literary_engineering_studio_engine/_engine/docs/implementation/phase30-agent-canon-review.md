# Phase 30：Agent Canon / Continuity 审查

## 目标

> Current project-type skill override: `agent-canon-review` writes a platform-agent task sidecar and expected review paths. It does not call local `dry-run`, `http-chat`, or external agent services.

在 `canon-lint` 的规则输出之上增加 Agent 语义审查，识别跨章节连续性、未确认事实、时间线风险和发布前阻断项。

## 新增能力

- `agent_canon_review.py`
- `agent-canon-review`
- `reviews/agent/canon_review.md`
- `reviews/agent/canon_review.json`

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-canon-review work/demo
```

## 边界

Agent canon 审查必须引用输入来源路径。检索、规则 lint 和 Agent 判断都不能直接把候选事实提升为 confirmed canon。
