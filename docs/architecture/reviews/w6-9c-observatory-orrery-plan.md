# W6-9C Agent Observatory 与星仪轻量计划投影（计划）

## 目标

按 W6-9（AO-8）要求补齐可观测性与星仪投影：

1. `projectPlanOverlay`：把策略投影 + typed 事件流转换为星仪轻量叠加
   （scope 节点 + 最近 12 个事件节点），只渲染真实数据。
2. 创作策略页新增“计划投影”条带。
3. `AgentObservatoryView`：展示 Worker 状态、活动任务、会话与最近事件的
   安全投影（复用现有 `/agent-observability` 读模型）。

## 边界

- 观测台只展示审计安全字段，不暴露正文、凭证或推理链。
- 页面只读；计划审批与写回仍由 CLI/Engine 正式 Gate 完成。

## 交付物

- `features/strategy/orreryPlanProjection.ts` + spec。
- `features/observatory/AgentObservatoryView.vue` + spec。
- 路由 `/observatory` 与策略页投影条带。

## 验收

- 叠加节点稳定：scope 在前、事件按序、上限 12。
- 观测台渲染真实 status/active_task/sessions/recent_events，空态诚实。
- 前端全量测试与生产构建通过；`git diff --check` 通过。
