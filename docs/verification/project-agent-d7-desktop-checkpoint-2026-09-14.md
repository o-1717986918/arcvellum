# Project Agent D7 桌面迁移验收记录

> 日期：2026-09-14
>
> 范围：D7 双主界面、Agent 子工作区、旧查看入口兼容和顶层 Agent 无审批语义

## 1. 交付结论

D7 已完成。作品创建、打开、继续和演示项目入口均进入 `/agent`。叙事星仪保留为 `/overview` 平级主界面；设置保留为独立页面。

“查看作品”已经从旧路由导航改为 Agent 桌面内部工作区切换。正文长卷、创作现场、作品档案、文风成果、质量与节奏、创作策略、Agent 观测、作品考古和交付状态均在同一项目桌面按需加载，切换时不离开 `/agent`。

顶层 Agent 不创建用户审批、确认卡或 `intent_quote` 授权票据。开放工具由 Agent 自主调用，正式变化继续受新内核、输入 schema、版本、并发、审查、晋升与交付 Gate 约束；删除、外部发布和密钥修改未暴露为 Project Agent 工具。

## 2. 代码边界

- `client/src/features/project-agent/workspaces.ts` 是 Agent 子工作区唯一注册表，集中管理标题、说明、图标与懒加载组件。
- `AgentSubworkspace.vue` 提供统一返回、刷新、全屏、加载和滚动容器，不复制子工作区业务状态。
- `AgentThreadRail.vue` 与 `AgentContextInspector.vue` 只发出工作区意图，不调用旧 Router 页面。
- `AgentWorkspaceView.vue` 持有当前子工作区的本地 UI 状态；旧 URL 查询参数只用于兼容导入。
- `router.ts` 将旧 `/reader`、`/archive`、`/style`、`/quality`、`/strategy`、`/observatory`、`/archaeology` 和 `/delivery` 重定向到 Agent 桌面。
- 旧 `SpatialWorkspaceRoute.vue` 已删除。Archive、Style、Quality 等成熟业务组件和原有 API/store 保持复用。

## 3. 验收证据

### 自动化

- `npm run client:build`：通过；2,650 个模块完成生产构建，桌面前端同步与 v0.9 build verify 通过。
- `npm run client:test -- --reporter dot`：73 个测试文件、217 项测试通过。
- `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests\\project_agent -v`：23 项 Project Agent 测试通过。
- 路由测试覆盖旧查看 URL 到 `/agent?workspace=...` 的兼容重定向。
- 组件测试覆盖“查看作品”按钮发出工作区意图，不产生 RouterLink 跳转。

### 真实界面

在 `1280 x 720` 开发界面完成以下检查：

1. 从 Agent 左栏打开正文长卷，URL 保持 `/agent`，阅读器可滚动并可全屏。
2. 打开作品档案，旧深色 IDE 作为子工作区完整呈现，文本、资产树和编辑器可读。
3. 打开创作现场，候选内容、审查轨迹、会话与状态投影在同一桌面显示。
4. 打开质量与节奏，规则预设、阈值控件和样文检查正常呈现。
5. 全屏工作区会隐藏左右侧栏，退出后布局恢复。
6. 浅色、深色、跟随系统和高对比度外观均可切换，高对比度焦点样式有效。

## 4. D8 边界

D8 可以继续删除长期无访问量的旧页面外壳和 Advisor 兼容入口，并补桌面休眠恢复、长会话与完整用户路径 E2E。D8 不应扩大 Project Agent 工具域，也不应重写星仪、阅读器、档案或文风业务组件。
