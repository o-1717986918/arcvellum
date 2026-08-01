# W6-9A 创作策略读模型与 typed SSE（计划）

## 目标

按 W6-9（AO-8）要求建立创作策略页面的数据底座：

1. 后端只读投影：`GET /project/strategy` 返回编排设置、active plan 摘要
   与 Rolling Horizon 占位；写入仍归正式 CLI/Engine。
2. typed SSE：`GET /project/strategy/events` 以 `plan-event` 事件名与稳定
   event id 流式输出审计目录中的 typed plan events。
3. 客户端数据层：策略类型、`strategyClient`（fetch + observe）、
   `useStrategyStore`（加载/连接/事件日志/fail-friendly）。

## 边界

- 本批只读；不创建计划、不审批、不写项目事实。
- 事件来源为 `workflow/orchestration/runs/*/events.jsonl`，仅暴露安全摘要
  字段，不含 Prompt、正文、凭证或绝对路径。
- 页面 UI（diff/模拟/审批面板）属 W6-9B。

## 交付物

- `api/routers/strategy.py`、`application/strategy_projection.py`、
  `api/streaming.py::stream_typed_events`。
- `client/src/features/strategy/{types.ts,services,stores}`。
- 测试：`tests/test_strategy_router.py`、`client/.../strategy.spec.ts`。

## 验收

- 策略投影缺省为 fixed/disabled；active_plan.json 存在时返回安全摘要。
- SSE 流含 typed event、稳定 id 与完成注释；非法行跳过。
- 客户端 store 只接收 `plan-event`，重载关闭旧流，错误可读。
- Architecture Audit 不新增债务；Python/前端全量测试与生产构建通过。
