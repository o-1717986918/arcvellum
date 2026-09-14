# Project Agent D8 收敛验证

> 日期：2026-09-14
>
> 分支：`feat/lean-literary-kernel-v2`
> 范围：项目桌面、会话恢复、展示入口保护、旧前端外壳收敛

## 结论

D8 已把 Project Agent 从“可用的新入口”收敛为可恢复的项目桌面。默认操作路径保持在 `/agent`，原有作品阅读、创作现场、档案、文风、质量、Agent 运行现场、星仪和交付能力仍可从同一桌面到达。此轮没有增加 Agent 工具、文学 Gate、模型请求或新项目文件格式。

## 会话与桌面恢复

- 用户消息持久化 `turn_id` 与 `job_id`，会话读模型只暴露仍在 `queued`、`running` 或 `stopping` 的当前任务。
- 页面重新打开、窗口重新获得焦点或桌面从休眠恢复时，前端读取同一会话并续接已有 SSE job，不会重新提交用户消息。
- 终态和已中断任务不会伪装为可恢复任务，避免界面永久等待一个不会继续产生事件的 job。
- 对话超过 80 条时只渲染最新内容并报告省略数量，持久化历史仍完整保留。
- SSE 客户端沿用 cursor 重连，重复事件由游标边界过滤。

## 功能保护

以下工作区拥有显式注册表测试，默认路径简化时不得删除：

- 正文阅读；
- 创作现场；
- 作品档案；
- 文风工作台；
- 质量与审查；
- Agent 运行现场；
- 叙事星仪；
- 交付状态。

`/overview` 继续作为叙事星仪的一等路由；旧查看 URL 只承担兼容跳转，不再形成第二套主页。

## 视觉验收

在实际开发 Web 客户端中逐页检查设置、质量、交付、帮助与 Agent 运行现场：

- 子工作区统一为紧凑单行工具栏，减少重复标题占用；
- 交付状态改为可读的赭色或绿色状态牌，消除浅色文字落在白底的问题；
- Agent 运行现场使用友好任务名作为主信息，原始 task id 与 event id 只保留为次级证据；
- Worker 会话列表具备固定高度和滚动，不再把状态文字挤成竖排；
- 设置和质量页采用项目桌面中性令牌，Creative Live 与档案 IDE 保留深色专业表面。

## 成本与性能边界

- 工作区切换不调用模型。
- 会话恢复增加一次 session read 和对既有 job 的 SSE 续接，不创建新 turn。
- Prompt、上下文包和 Pi Worker 执行协议均未改变，因此单次模型 token 上限与正文 Worker 成本不变。
- 首响应时间取决于已有 Project Agent runtime；D8 没有在用户无消息时增加后台模型活动。
- 本轮未消耗真实供应商额度做基准测试。真实首 token 延迟和完成率应在用户主动选择的发布 smoke test 中记录，不能由本地 mock 推断。

## 兼容边界

旧 Advisor 前端外壳和重复动作入口已经删除。以下内容暂时保留：

- Advisor 后端/API 与既有数据表；
- `strict-v1` 兼容路线；
- 已登记的 Engine facade 和别名。

这些内容仍受兼容清单和架构债务棘轮约束。后续删除必须先确认安装版迁移、历史项目读取和公开 API 均不再依赖，不能为了代码数量提前移除。

## 架构审计边界

在只包含提交 `fb2beda` 的干净 worktree 中执行架构审计，D8 新增文件和函数没有产生新的边界或复杂度违规。全仓库仍有 7 项在 D8 之前已经存在的基线债务：`api_server.py`、`automation/controller.py`、`persistence/job_store.py`、`persistence/sessions.py` 的文件预算，`create_app`、`dependencies_from_actions.resolve_decision` 与 `ProjectAgentRuntime.run_turn` 的函数预算。它们应作为后续独立重构批次处理，不能混进本轮会话恢复和界面收敛提交。

## 验证命令

```text
python -m unittest discover -s tests/project_agent -v
npm run client:test
npm run client:build
python scripts/architecture_audit.py
python scripts/verify_compatibility_surface.py
git diff --check
```

签名更新器的最终验证依赖真实 release manifest、签名和安装包，应在下一次正式发布流水线中完成。
