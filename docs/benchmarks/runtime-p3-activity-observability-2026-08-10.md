# P3 运行时活性与安全可观测性证据

> 日期：2026-08-10  
> 基线提交：`b434b06`  
> 适用范围：OpenCode Runtime、Worker、Autopilot、Agent Observability v3  
> 结论：P3 的代码目标已经实现并通过完整回归。

## 1. 先核对现实

P3 没有从零引入 reasoning。此前 OpenCode 已把供应商返回的 reasoning part 转成不含正文的 `runner.reasoning.activity`，但存在四个实际缺口：

1. `first_event_timeout` 只认 text/tool/file，真实 reasoning 仍可能被误判为完全无活动；
2. reasoning 只有单点 activity，没有 started/completed 生命周期；
3. OpenCode run log、Worker Job Store、Autopilot Event Store 使用分散的瞬时事件名单；
4. Agent Observability 无法区分“运行时仍活着”和“已经产生可验证内容”。

完整偏差审计见 `runtime-p3-p5-reality-audit-2026-08-10.md`。

## 2. 已实现行为

### 2.1 两套时钟

- runtime liveness：reasoning、transport 和 session activity 会刷新；
- productive progress：仅 text、tool 和 file output 会成立；
- 首事件超时只表示“完全没有运行时活动”；
- reasoning 持续但没有产出时，运行继续受 total timeout 约束，并只产生一次 `runner.no_productive_progress` 安全诊断；
- reasoning 或其他活动停止后，inter-event timeout 仍能终止失活会话。

### 2.2 安全 reasoning 生命周期

- 首个真实 reasoning part 产生 `runner.reasoning.started`；
- 后续 activity 最多每 5 秒形成一次无内容脉冲；
- 首个 text/tool/file output 或 session 结束产生 `runner.reasoning.completed`；
- activity 只保留事件数、字符计数和耗时，不把原始 reasoning 文本传给 Studio sink；
- 没有 reasoning part 的模型不会生成伪造的推演状态。

### 2.3 持久化边界

| 通道 | reasoning activity | started/completed | 原始 reasoning 文本 |
|---|---:|---:|---:|
| `runtime.events.jsonl` | 不持久化 | 持久化安全摘要 | 不存在 |
| Worker Job Store | 不持久化 | 持久化安全摘要 | 不存在 |
| Autopilot Event Store | 不持久化 | 持久化安全摘要 | 不存在 |
| LiveEventBus | 有界、可合并 | 可发送 | 不存在 |
| Agent session ledger | 每 5 秒刷新一次用户安全状态 | 保留状态 | 不存在 |

统一分类由 `observability/event_policy.py` 提供。session ledger 刻意保留节流后的活性状态，以便快照 SSE 能证明会话仍在运行；它不保存 reasoning payload。

### 2.4 前端合同

Agent Observability 升级为 `arcvellum/agent-observability/v3`，增加：

- 当前活动阶段和等待原因；
- runtime 是否活跃；
- 当前可见阶段是否已形成 productive progress；
- 上下文任务类型、模式、tier 数量和不可逆 digest；
- 任务完成后可用的读取次数与重复读取摘要。

该投影不返回 prompt、绝对路径、凭证、正文或 reasoning 内容。当前 SSE 仍是安全快照 SSE，不宣称为原始 reasoning 实时流。

## 3. 验证证据

- 定向后端回归：31 项通过；
- 前端完整回归：159 项通过；
- 架构审计：通过，未提高既有预算；
- `git diff --check`：通过；
- 完整后端回归：961 项通过，1 项按设计跳过；

确定性测试覆盖：

- reasoning 活性阻止错误的 first-event timeout；
- reasoning 停止后触发 inter-event timeout；
- `no_productive_progress` 只发一次且不提前停止活会话；
- reasoning started/activity/completed 不含原始内容；
- 高频 activity 不进入 OpenCode run JSONL；
- Observability v3 不泄露测试注入的私有字段。

历史 P0 真实 OpenCode 样本记录了 12 秒首次 reasoning、174.8 秒首次 text/tool 和 232.6 秒总耗时。该样本证明 reasoning 与可见产出确实可能相隔很久，但没有超过 180 秒；P3 的“超过阈值仍不误杀”结论来自确定性时钟测试，不把历史样本夸大为 180 秒实测。

## 4. 未在 P3 声称完成的事项

- 不展示供应商未返回的隐藏思维链；
- 不保存 raw reasoning 历史；
- 不把 `no_productive_progress` 变成单独的强制终止 Gate；最终无产出仍由 total timeout、preflight 和 progress digest 处理；
- 不在 P3 重做完整 Agent 观测台；
- 不把上下文准备缓存的 CPU/IO 收益误称为 token 收益。
