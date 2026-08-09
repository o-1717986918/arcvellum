# P3-P5 实施前现实核对

> 日期：2026-08-10  
> Studio 提交：`746de1d`  
> Pi 固定提交：`936aff00918de1187f085f123c2812d8f2d67745`  
> 结论：P3-P5 的目标仍成立，但原执行描述含有会导致重复实现、错误持久化或无效验收的假设，必须按本文修正后实施。

## 1. P3：可观测性与 watchdog

### 已经存在

- OpenCode reasoning part 已被归一为不含正文的 `runner.reasoning.activity`，并会刷新运行时 `last_activity`。
- 首次 reasoning、text、tool、output 的计时字段已经存在。
- `LiveEventBus` 已是有界内存队列；Worker SSE 已能发送瞬时事件。
- Context Ledger、context budget、最终 context access summary 和吞吐投影已经存在。

### 与原规划不一致的地方

1. 原规划写“reasoning 被直接丢弃”，实际已经有 content-free activity；P3 应升级生命周期，而不是从零接入。
2. `first_event_timeout` 仍只检查 `public_activity`。reasoning 虽刷新 `last_activity`，仍可能在 180 秒被误判为首事件超时。
3. 事件有三条持久化路径：OpenCode 的 `runtime.events.jsonl`、手动 Worker Job Store、Autopilot Event Store。只扩充 `EPHEMERAL_WORKER_EVENTS` 不能保证 reasoning 不落盘。
4. `track_agent_session_event()` 会接收新的 reasoning 事件；若不区分 pulse 与 lifecycle，高频 delta 会持续写 SQLite。
5. Agent Observability SSE 当前是按秒重建安全快照，不直接订阅 Worker 的 `LiveEventBus`。它能展示持久的 started/completed 和聚合信息，但不能假装已经拥有 raw reasoning 流。
6. 当前没有独立的“productive progress timeout”。reasoning 活性可以阻止 silence timeout，但只有总超时和任务完成后的 progress digest 能最终认定无产出，不能把这误写成已有实时空转 Gate。

### 修正后的 P3 顺序

1. 建立单一事件持久化策略，供 OpenCode run log、Worker API、Autopilot 和 session ledger 共同使用。
2. 将 reasoning 规范为 content-free `started/activity/completed`；不把原始 reasoning 文本带出 normalizer。
3. watchdog 分离 runtime liveness 与 productive progress：reasoning、status、transport 更新前者；text、tool、file 更新后者。
4. 首事件超时只针对“完全无运行时活动”；只有 reasoning 的任务继续运行，但在超过 productive 阈值时发出安全诊断，最终仍受 total timeout 约束。
5. 高频 activity 只进入有界内存流或被节流为摘要；started/completed 和摘要可以持久化，原始 delta 永不进入 JSONL、SQLite 或项目。
6. Agent Observability 只展示真实存在的 activity、等待原因、context tier/count/digest 和已完成的 context access 摘要。当前任务尚未产生读取摘要时明确显示“执行完成后可用”。

## 2. P4：bounded context 与 prepared cache

> 实施状态：已按本节修正顺序完成工程实现。真实 candidate-review A/B、回滚演练和独立 cache micro-benchmark 的结果见 `runtime-p4-bounded-and-cache-canary-2026-08-10.md`。cache 进入默认窄 canary；bounded 因尚缺多样本与独立文学盲评，保持显式 opt-in。

### 已经存在

- `context_rollout.py` 已实现 contract-driven shadow/bounded 决策和 rollback reason。
- `context_ab.py` 已实现同任务、同模型、隔离项目副本的双臂运行。
- `context_ab_suite.py`、rollback drill、报告和测试已经存在。
- `PreparedContextCache` 已实现线程安全 LRU、精确 cache key、命中/未命中/绕过统计。

### 与原规划不一致的地方

1. runtime benchmark catalog 的 review 样本是 canon review，不是计划要求的 scene `candidate-review`。
2. A/B 报告的文学质量判断只识别 `*_scene_review.json`；直接用现有 canon review 样本不会得到有效 canary verdict。
3. prose benchmark 只推进到 candidate generation，尚未提供可重建的 candidate-review 任务。
4. `context_ab.py` 直接创建 `AgentWorker`，没有注入 `PreparedContextCache`。因此它不能作为 cache canary 工具。
5. prepared cache 复用的是可重建 prompt 投影，减少 CPU/文件读取和准备延迟，不减少发送给模型的 token。不得把 cache 命中宣传为模型费用优化。

### 修正后的 P4 顺序

1. 先扩展脱敏 scene fixture，使其能生成合法候选并领取真实 candidate-review 任务。
2. 对 candidate-review 运行 shadow/bounded；只有同模型、双臂完成、首轮 preflight、review 结论和上下文完整性均通过，才允许进入 canary 配置。
3. 运行 rollback drill，确认关闭 allowlist 后立即恢复 shadow。
4. bounded 结论冻结后，新增独立 cache micro-benchmark；同一 lifecycle、同一精确 key 至少产生一次 miss 和一次 hit，并比较准备耗时与内容 digest。
5. cache 只在证明内容完全一致、失效正确且准备耗时有实际收益后启用小范围 canary；不与 bounded 同批开启。

## 3. P5：Pi 固定构建与 RPC 适配

### 已经确认

- fork 和固定 commit 存在，本机 Node `v24.16.0` 满足 `>=22.19.0`。
- 固定版本 `@earendil-works/pi-coding-agent` 为 `0.84.1`。
- RPC 的真实入口为 `pi --mode rpc`，协议为 LF JSONL，支持 request id、`prompt`、`abort`、`get_state` 和 `get_session_stats`。
- Pi coding agent 默认包含 read/bash/edit/write 等编码工具，不提供足以证明 OS 级边界的内建权限系统。

### 与原规划不一致的地方

1. 本地 fork 是 partial clone + sparse checkout，当前没有物化 `packages/coding-agent`，也没有可用 `pi` 命令。
2. 顶层 build 依赖 `tui`、`telemetry`、`ai`、`agent`、`sqlite-node`、`protocol`、`client`、`server` 和 `coding-agent`；不能只增加一个目录后假设构建成立。
3. 当前 Runtime Registry 对每个注册项都直接 `build_runtime()`；默认禁用的 Pi 会让整批状态探测失败。注册与启用语义必须先修复。
4. OpenCode 基线模型 `opencode/deepseek-v4-flash-free` 不保证能被 Pi 以同一供应商、同一模型调用。没有同模型条件时，只能交付“适配器可用，价值证据不足”。
5. P5 只能验证通用 Pi RPC 适配价值，不能证明专用文学 Worker 的 typed tools 已经成立。

### 修正后的 P5 顺序

1. 在固定提交上物化 coding-agent 及其完整构建依赖闭包；网络或 promisor object 不可用时明确阻塞，不修改上游源码绕过。
2. 使用 lockfile 安装、按真实 package scripts 构建，生成不含绝对用户路径和凭证的安装收据与 SHA-256。
3. 先修复 Runtime Registry 的 registered/enabled/probed 语义，再以默认禁用方式注册 Pi。
4. 先做无模型 LF JSONL framing、request correlation、get_state、abort、退出和进程回收测试。
5. 再做短生命周期 `PiRpcRuntime`，仅运行脱敏 benchmark，capability 如实报告 `read_control=false`、`external_directory_control=false`。
6. 只有 Pi 自身认证可用且能与 OpenCode 对齐同一模型时才运行正式 A/B；否则停止在“证据不足”，不进入 P6。

## 4. 防偏移门禁

每个后续阶段开始前必须重新核对：

- 当前 Git HEAD 与本记录是否一致；
- 规划中的目标文件、命令、事件和测试是否真实存在；
- 是否已有同职责模块，避免建立第二套权威；
- 验收数据是否能由当前实现真实产生；
- 任何“节省 token”“不落盘”“安全沙箱”“同模型”结论是否有直接证据；
- 阶段完成后更新主路线、证据文档和独立 Git 提交。
