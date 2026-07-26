# ArcVellum v0.96.0 创作吞吐优化评审

> 日期：2026-07-26
> 范围：固定正式路线的模型往返、沙箱准备和吞吐计量。

## 结论

本批优化没有减少任何文学任务、Gate 或正式写回。它只减少同一任务内部的重复读取与
重复沙箱准备，并修正吞吐观测对累计 usage 快照的重复计数。

## 实际瓶颈

真实项目 `1+1=2` 的最新可归因任务显示：

- task selection 平均约 1.1 秒；
- sandbox preparation 约 0.08 秒；
- model execution 约 189 秒；
- validation/writeback 约 1.5 秒。

因此模型轮次和上下文往返是主瓶颈，单纯增加 Worker 线程或取消 Gate 不会有效改善
创作吞吐。

## 已实施

### 首轮准备上下文

`runtime/prompt_context.py` 把 Agent 已获许可读取的 Source、Reference 和 CLI Protected
Outputs 组成逐文件、带摘要、不可截断的首轮快照：

- 只读取当前沙箱许可内的 UTF-8 文件；
- 默认最多 180,000 字符；
- 文件只有完整内联或完整省略两种状态；
- 省略文件继续留在沙箱，并明确要求 Agent 按原方式读取；
- 项目文本被标记为资料，不能提升权限或覆盖 Worker Program；
- Context Ledger 的 prompt hash 会随内联资料变化。

真实 `scene_0003 roleplay` 任务可在约 0.24 秒内把 9 份、81,263 字符的许可资料完整
放入首轮任务，没有 omitted 文件。目标是减少 Agent 逐文件读取时产生的多次模型续轮，
而不是减少作品上下文。

### 延迟 Agent 沙箱

Worker 现在：

- 对确定性任务只建立最小校验沙箱；
- 对带 CLI 前置命令的 Agent 任务，等命令产出 Protected Outputs 后只构建一次 Agent
  视图；
- 对无 CLI 前置的 Agent 任务保持原有立即构建行为。

在真实 `scene_0003 context-packet` 依赖集上，单次 staging 从约 0.371 秒降至约
0.092 秒，约减少 75% 准备耗时。正式命令、预检和 task lifecycle 均未改变。

### 用量快照去重

OpenCode 的 `message.updated` 是同一消息的累计 token 快照。新实现以稳定 `usage_id`
计算增量，避免把同一消息从 10k、12k、15k 的快照误记为 37k。没有稳定 ID 的旧事件
仍按原语义处理，保持历史兼容。

## 未在 0.96.0 提前开放

- 不并发生成连续正文；
- 不复用 Writer 与 Reviewer 会话；
- 不执行 Execution Bundle；
- 不启用同项目正式并发写；
- 不用小模型替换高风险文学任务；
- 不把 context cache 或 cache token 覆盖率伪报为已完成。

Execution Bundle、Rolling Horizon、受限只读并发和真正的 session lease 继续属于
AO-5/AO-6，见发布剩余事项。
