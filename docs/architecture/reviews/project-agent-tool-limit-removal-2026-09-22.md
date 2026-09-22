# Project Agent 固定工具次数限制移除

```yaml
module_change_packet:
  objective: "顶层 Agent 可按任务需要连续调用工具，不再因固定 8 次工具或 6 轮模型调用而提前停止"
  primary_module: "project_agent/"
  public_entry: "ProjectAgentTurnRequest.start_envelope() 与 runProjectAgentTurn()"
  variation_point: "none"
  inputs: ["turn.start 的会话、提示词及工具 allowlist"]
  outputs: ["turn.complete 状态、回答、实际模型轮数与工具调用数"]
  invariants: ["保留请求超时与取消", "保留工具 allowlist、参数校验和领域权限", "不改正文创作 Worker 的任务预算或文学 Gate"]
  allowed_dependencies: ["Project Agent bridge runtime", "Pi Project Agent adapter", "Project Agent 合同及协议测试"]
  forbidden_dependencies: ["Engine 内部任务生命周期", "前端直接访问底层传输", "正式项目文件写入"]
  tests: ["Python turn.start 合同测试", "Pi 协议超过 8 次工具和 6 轮的回归测试", "项目架构及全量回归"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本执行记录"]
```

现状：`ProjectAgentService` 对普通与委托目标后续请求都传递固定预算；Pi 适配器达到第 8 次工具调用时报错，并在第 6 轮强制停下。该限制与用户授权、模型服务额度无关，可能使合法检索或诊断中途结束。

处理：从顶层 Agent 的跨语言启动合同移除这两个字段；Pi 适配器只在模型不再请求工具时自然结束。实际调用次数仍用于回执和观测。现有超时、取消、工具 allowlist、结构化 bridge 及领域权限维持不变。正文创作 Worker 保持原预算语义。

验证（2026-09-22）：

- Project Agent Python 合同与服务测试：39 项通过。
- Pi Project Agent 协议回归：模拟连续 10 次工具调用、11 轮模型响应，得到最终答复；Pi Worker 全套 103 项通过。
- Python 全量回归：1494 项通过，1 项因本机 Windows 符号链接不可用而跳过。
- 架构审计、模块图检查、Prompt Registry 校验、前端测试及构建均通过。
- 开发服务重启后，`/health` 返回版本 `0.99.9`，`/ui/` 返回 200；本地安装发现器指向本仓库新构建的 `workers/pi-worker/dist/main.js`。

未运行真实模型调用；因此这里只证明固定次数门槛已移除及协议回归，不声称外部模型服务无配额或网络限制。单轮请求仍受服务端超时约束。
