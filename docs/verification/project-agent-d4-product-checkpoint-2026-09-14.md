# Project Agent D4 产品检查点

日期：2026-09-14
范围：只读顶层 Agent 的后端、生产 Vue 界面与真实工具调用闭环。

## 交付边界

D4 只解决“用户能否通过一个持续对话理解当前文学项目”。Project Agent 可以查询项目概览、搜索作品资料、观察创作现场；它不能改写项目、推进状态机、批准决策或修改正式资产。写操作继续由 D5 单独设计和审查。

## 架构结果

- 复用现有 Pi Worker、Advisor 会话表、Worker Job、`run_events`、SSE 和 Project Read Models。
- Python `project_agent` 包承担合同、只读模型、工具分派、双向 Runtime 与应用服务；HTTP Router 只做传输适配。
- Vue 功能集中在 `client/src/features/project-agent/`，由类型、传输、会话编排和展示组件四层组成。
- UI 不建立第二个全局 store；项目选择与现有 `useAppStore` 保持一致。
- 每次回答创建 durable job。刷新或网络断开后可从事件游标恢复，实时 delta 不承担正式存储职责。
- Pi 子进程在回合结束、失败或取消后回收，不保留无用途后台进程。

## 真实链路验收

在开发 API `127.0.0.1:8791` 与 Vite `127.0.0.1:5174` 上，通过 `/ui/#/agent` 发起问题：

> 当前创作进行到哪里？有没有阻断或异常？

Project Agent 实际调用：

1. `project_overview`
2. `creation_observe`

最终回答正确识别：当前作品整体进度、正式正文字数、`scene_0001` 修订位置、模型余额阻断、未闭环审查与建议处理顺序。界面同步显示工具活动、回答正文和本轮 token 统计。

## 自动验证

- `python -m unittest discover -s tests/project_agent -v`：17 项通过。
- `python -m unittest tests.test_api_server -v`：21 项通过，包含生产前端静态服务、桌面鉴权、SSE 恢复与旧 Advisor 路径。
- Project Agent 前端传输与会话 composable：2 项通过。
- `npm run client:build`：通过，2643 个模块完成生产构建并同步桌面静态资源。
- Pi Project Agent 协议：5 项通过；Pi Worker TypeScript 生产编译通过。
- OpenAPI 与 TypeScript 合同已重新生成。

## 视觉与交互验收

- Agent 与星仪形成平级双入口。
- 左侧会话栏、中部对话、右侧作品上下文均有稳定尺寸和独立滚动。
- 长回答使用正文排版；工具活动折叠显示，不把 JSON 暴露给用户。
- 输入期间显示明确忙碌状态，防止重复创建会话或并发发送。
- Reader、Creative Live、Archive、Style、Quality 与 Delivery 仍作为展示工作区保留。

## 后续门禁

D5 只能先实现少量、类型化、可审计的写接口。任何 mutation 必须复用现有 Application Service，返回 receipt 与 concurrency token，并遵守单项目单 mutation 约束。当前 UI 和三个只读工具不得因 D5 扩展而回退。
