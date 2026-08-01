# W6-9B 创作策略页（计划）

## 目标

在 W6-9A 数据层之上交付用户可读的创作策略页：

1. 编排设置卡片（模式/预设/开关）与激活计划卡片（计划/版本/状态/范围）。
2. 实时 typed 计划事件流面板：只渲染正式审计产生的 `plan-event`。
3. 明确只读边界：页面不提供审批或写回入口。

## 设计方向（frontend-design skill）

- 沿用 ArcVellum 现有 Studio 控制台视觉语言（深色、信息密度克制、真实数据），
  不另起视觉锚点；差异化动作是“实时事件流”面板，用真实事件类型/计划/版本/
  时间渲染。
- 内容纪律：空态说明真实缺失（“还没有激活的创作计划”），无虚构数据、无
  filler 标签；标准 UI 文案（重新读取、断开事件流、连接事件流）。

## 边界

- 只读页面；计划 diff/模拟结果与审批状态只展示正式审计证据。
- 正式审批与写回仍由 CLI/Engine 门禁完成。

## 交付物

- `client/src/features/strategy/CreationStrategyView.vue`。
- `client/src/features/strategy/CreationStrategyView.spec.ts`。
- `client/src/router.ts` 新增 `/strategy` 路由。

## 验收

- 页面渲染真实策略设置与激活计划；无计划时给出诚实空态。
- typed 事件在实时流中渲染；断开/连接可切换且不重复建流。
- 前端全量测试与生产构建通过；`git diff --check` 通过。
