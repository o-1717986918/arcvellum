# W6-9 Exit Audit：AO-8 前端产品化收口

## 范围

W6-9（AO-8）按批次 A/B/C 完成：

- W6-9A：只读策略投影 API + typed plan-event SSE + 客户端数据层。
- W6-9B：创作策略页（设置/激活计划/实时事件流/只读边界）。
- W6-9C：星仪轻量计划投影 + Agent 观测台页面。

## 需求对照

| AO-8 要求 | 证据 |
| --- | --- |
| 创作策略页 | W6-9B：`/strategy` 页面渲染真实设置、激活计划与事件流 |
| typed SSE | W6-9A：`/project/strategy/events` 稳定 event id + `plan-event` 类型；客户端只消费该类型 |
| 计划 diff/模拟/审批 | 页面只读展示正式审计证据（plan/status/事件），明确“审批与写回由 CLI/Engine 门禁完成”；不开放绕过 Gate 的 UI 入口 |
| Agent Observatory | W6-9C：`/observatory` 页面展示 status/active_task/sessions/recent_events 安全投影 |
| 星仪投影 | W6-9C：`projectPlanOverlay` 轻量叠加 + 策略页投影条带 |

## 边界确认

- 观测台不暴露正文、凭证或推理链；页面均只读。
- 计划 diff/模拟结果与审批状态以正式审计证据为准；交互式审批入口属于
  后续产品批次，本批不冒充完成。

## 证据汇总

- 前端定向测试：W6-9A 3 + W6-9B 6 + W6-9C 11 = 20 tests passed。
- 前端全量：52 files、152 tests passed；`client:build` 通过。
- Python 全量：822 tests passed、1 skipped（W6-9A 后端 7 测试）。
- Architecture Audit 34 file / 220 function debt、0 cycle，无新增债务。
- 分支/PR：W6-9A `feat/v098-strategy-typed-sse`（PR #16）、
  W6-9B `feat/v098-strategy-page`（PR #17）、
  W6-9C `feat/v098-observatory-orrery`（PR #18），均待审批合入。

## 结论

AO-8 产品化数据底座与页面满足本批退出门禁。交互式计划审批入口与
生产执行器接线明确列为后续批次，不冒充完成。
