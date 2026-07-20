# Phase 90：总控面板 API 与前端实时轮询

Phase 90 把 v0.89 的只读 `workflow-dashboard` 从 CLI 产物接入 Web 控制台。

## 目标

1. 前端能实时看到平台 Agent 当前推进项目时卡在哪里。
2. 状态机证据仍由 CLI/后端统一生成，避免前端变成第二套工作流。
3. 页面只读展示，不直接完成 sidecar、不绕过 `task-next -> task-open -> task-submit -> task-complete`。

## 实现

- `GET /workflow/dashboard?project_root=...`
  - 校验 API token 和 allowed root。
  - 调用 `build_workflow_dashboard()`。
  - 返回 `summary`、`route_audits`、`next_actions`、`recent_events` 和生成的 `workflow/dashboard/*` 路径。
- 前端新增 `项目总控` 视图：
  - 使用共享 `project_root`。
  - 手动刷新或按 3-60 秒间隔轮询。
  - 展示 ready、blocked、pending sidecars、missing expected、next actions 等指标。
- 回归测试覆盖：
  - `/workflow/dashboard` 可生成 JSON/Markdown/HTML。
  - 前端包含 dashboard 入口和 API 调用。
  - 配置 token 时 dashboard endpoint 也必须鉴权。

## 边界

- 页面不允许直接写 completion marker、review、promotion 或 state patch。
- 如果 dashboard 显示阻塞，平台 Agent 仍必须回到正式 CLI 状态机处理。
- 中文内容字符是正式字数门禁；机器非空白字符只作为 dashboard 或平台诊断的辅助解释。
