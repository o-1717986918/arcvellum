# Project Agent D4 后端检查点

日期：2026-09-13  
范围：只读顶层 Agent 后端，不含生产 Vue 界面与写工具。

## 已完成

- 在既有 `advisor_sessions` 上增加 `session_kind`，复用同一 SQLite 和内存适配器；旧 Advisor 列表只返回 `advisor` 会话。
- 每个 Project Agent 回合创建现有 Worker Job，并将桥接活动写入现有 `run_events`。
- `ProjectAgentService` 负责会话顺序、有界历史、Pi 子进程调用、错误落盘和最终答复持久化。
- Pi Worker 正式支持 `project_overview`、`project_search`、`creation_observe` 三项只读工具。
- 三项工具只读取现有 `ProjectReadModels`，不扫描任意文件，也不导入 API Router。
- HTTP 接口采用 `POST turn -> job_id -> GET durable SSE`，支持 `Last-Event-ID` 游标恢复。
- Project Agent 复用当前项目已选择的 Advisor 人格；人格只影响交流方式，不能扩大工具权限。

## 反过度工程核对

- 没有新增数据库、事件总线、任务仓库、状态机或通用 Agent 框架。
- 没有修改正式 `AgentRuntime.execute()`；双向协议仍在独立 Runtime 中。
- 没有新增项目文件格式，也没有增加文学门禁。
- Project Agent 每回合结束后关闭并回收独立 Pi 子进程。
- 实时 delta 只作为 `run_events` 的投影，浏览器断线不会丢失正式回合证据。

## 验证

- Project Agent、持久化、Advisor 兼容和 API 定向测试：34 项通过。
- Pi Project Agent bridge：5 项通过。
- Pi Worker TypeScript 生产编译：通过。
- `tests.test_api_server`：20 项通过，1 项因当前工作树缺少已构建旧前端静态产物而返回 404；与本批后端协议无关，生产前端构建时复核。
- `git diff --check`：通过。

## 仍需完成

- 生产 Vue Agent UI、会话侧栏、工具活动和正文产物展示。
- 前端连接 durable SSE 并验证刷新、断线与游标恢复。
- 真实 Project Agent API 回合基线：首字延迟、总耗时、工具选择和 token 使用。
- 同一会话并发消息的明确排队状态与停止入口。
- D5 前继续禁止任何写工具。
