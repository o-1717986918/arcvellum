# W6-9C Agent Observatory 与星仪轻量计划投影（审查）

## 结论

**状态：完成。** 本批按
`docs/architecture/reviews/w6-9c-observatory-orrery-plan.md` 实现。

## 实现

- `features/strategy/orreryPlanProjection.ts`：
  - `projectPlanOverlay` 生成 scope 节点 + 最近 12 个事件节点；
  - 无计划/无事件时返回空叠加，不虚构数据。
- `CreationStrategyView` 新增“计划投影”条带：真实 plan_id/scope/事件计数。
- `features/observatory/AgentObservatoryView.vue`：
  - 运行状态、活动任务（角色/路线/任务/阶段）、Worker 会话与最近事件；
  - 空态说明真实缺失；复用 app store 的 `/agent-observability` 读模型。
- `router.ts` 新增 `/observatory`（Agent 观测台）。
- 桌面前端同步产物 `desktop/dist/index.html` 一并更新。

## 证据

- 前端定向测试：strategy 9（含 projection 3）+ observatory 2 = 11 tests
  passed。
- 前端全量：52 files、152 tests passed。
- `client:build`（vue-tsc + vite + desktop sync）通过，产物含新页面。
- `git diff --check` 通过；本批未触碰 Python 侧，架构基线不变。

## 边界确认

- 观测台仅展示安全投影；页面只读，审批与写回未开放 UI 入口。

## 下一步

W6-9 Exit Audit 收口 AO-8（见 `docs/architecture/reviews/w6-9-exit-audit.md`）。
