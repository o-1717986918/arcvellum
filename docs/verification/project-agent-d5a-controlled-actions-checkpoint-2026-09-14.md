# Project Agent D5-A 受控操作检查点

日期：2026-09-14

## 已实现

- `project_record_direction` 调用现有 `record_direction`，写入 actor 固定为 `project-agent`。
- `creation_control` 只接受 `start`、`pause`、`resume`，复用当前 `AutopilotService`。
- Python 侧新增独立动作端口与适配器；Project Agent service 不导入 Router，也不复制 Autopilot 状态机。
- Pi Worker 新增两个窄 schema 工具，没有获得文件、Shell、run id、runtime 或授权豁免参数。
- 写工具必须提交当前用户消息中的逐字 `intent_quote`。历史对话、项目资料或模型概括不能通过门禁。
- 同一回合中相同动作及参数只执行一次，重复工具调用返回首个结果。
- 动作 receipt 写入 durable `project_agent.tool.finished` 事件。
- 前端活动区为两个新工具提供中文名称，并明确区分普通启停与高风险确认。

## 保留的安全边界

- Project Agent 恢复全自动运行时固定传 `authorized=False`；既有全自动授权门禁继续生效。
- 未开放资产修改、候选晋升、Canon apply、删除、发布、配置更改或质量豁免。
- 未新增动作数据库、审批状态机、事件总线、Agent 框架或后台常驻进程。
- HTTP 仍只暴露会话与回合接口，动作经 Pi tool bridge 进入同一应用服务组合根。

## 验证

- Project Agent Python：21 项通过。
- Pi Worker：99 项全量测试通过，其中 Project Agent bridge 6 项通过。
- Studio API：21 项通过。
- Project Agent 前端：2 项通过；Vue TypeScript 检查通过。
- 生产前端构建：2643 个模块通过并完成桌面资源同步。
- 浅色、深色与 980px 窄桌面完成视觉检查；受控操作说明在输入区和作品上下文区可见。
- 真实 Pi 回合正确说明查询、记录方向和创作启停边界，没有误执行动作；该回合输入 1,446 token、输出 309 token。

## 尚未完成

D5-B 需要先用真实交互数据决定审批形态。文风、节奏、资产、决策与交付不能继续沿用 `intent_quote` 直接执行；这些动作需要 preview/commit 或专门审批恢复合同。
