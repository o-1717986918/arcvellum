# P6 Pi Agent Core 专用 Worker 原型报告

> 日期：2026-08-10
> Studio 基线：`220116e`，原型提交 `525cf3b..bf5db1e`
> Pi fork 基线：`936aff00918de1187f085f123c2812d8f2d67745`，Worker 提交 `24a9d53b..85bf8eff`
> 模型：`deepseek/deepseek-v4-flash`
> 判定：**原型成立，保留实验代码；不替代 OpenCode、不进入安装包或 Autopilot。**

## 1. 验证的问题

P5 已证明完整 Pi coding-agent RPC 能遵守 ArcVellum 产物合同，但比 OpenCode 更慢、更贵，并造成 reasoning 事件写放大。本轮不再包装 coding-agent，而是直接使用 Pi Agent Core 与 Pi AI，验证：

> 去掉编码提示、Shell、Git、任意文件工具、Skill、扩展和通用会话后，窄工具文学 Worker 是否具有独立工程价值。

Studio 继续拥有 TaskPackage、沙箱、上下文编译、正式 preflight、写回和 route gate。Worker 只执行一个任务，只有七个领域工具，不能领取任务、运行命令或写正式项目。

## 2. 实现结果

Pi fork 新增 `packages/arcvellum-worker`：

- 使用固定版本 Pi Agent Core / Pi AI；
- 只读 Pi 自有认证文件；Studio 不读取或保存密钥；
- 只允许读取 exact-on-demand 与写入 Agent-owned expected outputs；
- 拒绝绝对路径、越级路径和符号链接；
- 支持批量提交多个正式产物；
- 完成必须通过本地验证和显式 `complete_task`；
- 有工具、回合、修复和无进展预算；
- reasoning 与 text delta 均聚合后写入 JSONL；
- 一任务一进程，不复用跨任务对话历史。

Studio 新增默认禁用且需要实验授权的 `pi-worker` Runtime，并把现有 execution profile 的 thinking、turn、tool、repair 和 timeout 投影到 Worker。OpenCode 默认链路没有改变。

## 3. 原型期间发现并修复的问题

| 问题 | 根因 | 修复 |
|---|---|---|
| 多输出任务在两次工具调用内不可能完成 | 通用画像未考虑每个正式产物都需受控写入 | 工具预算增加“Agent 产物数 + 上下文/验证/完成”的任务下限 |
| 两个文件需要多个模型往返 | 写工具一次只接收一个文件 | 同一白名单工具支持原子单文件与有界批量写入 |
| 验证通过被判为无进展 | progress digest 只记录 issue，未记录 `validationPassed` | 把验证状态纳入进度指纹 |
| 产物已完成但来不及显式 complete | 画像没有为完成工具预留末回合 | 为有显式提交语义的执行画像保留完成回合 |
| 失败只显示 `runtime_failed` | 基础 Runtime 丢失 Worker 终止事件 | 恢复 completed/blocked/incomplete、失败类型和重试语义 |
| 首事件指标 unavailable | 基础短进程适配器未写阶段时序元数据 | benchmark 从安全 JSONL 事件回填时序和事件计数 |
| 保留调试目录在长仓库路径下无法启动 | Windows 运行目录叠加后超过可靠路径深度 | benchmark 对过深 `--workdir` fail fast，建议系统临时短路径 |

这些问题说明专用 Worker 的价值不只在模型速度，也在于把“完成、验证、进度和权限”变成机器合同；同时说明不能把通用编码 Agent 的预算参数原样套用到领域 Worker。

## 4. 同模型结果

| 样本 | Runtime | 正式状态 | 总耗时 | 费用 | 非缓存输入 | 总 token | 工具 |
|---|---|---|---:|---:|---:|---:|---:|
| structured | OpenCode | awaiting writeback approval | 103,144 ms | $0.006747 | 22,585 | 62,253 | 4 |
| structured | 完整 Pi RPC | awaiting writeback approval | 219,322 ms | $0.011132 | 23,315 | 132,894 | 4 |
| structured | Pi Worker | awaiting writeback approval | 130,158 ms | $0.005736 | 9,341 | 92,191 | 5 |
| review | OpenCode | awaiting writeback approval | 231,596 ms | $0.012957 | 28,637 | 206,575 | 4 |
| review | 完整 Pi RPC | awaiting writeback approval | 323,876 ms | $0.016103 | 29,799 | 247,538 | 4 |
| review | Pi Worker | awaiting writeback approval | 225,791 ms | $0.014789 | 44,492 | 215,976 | 5 |

Pi Worker 相对完整 Pi RPC：

- structured：总时长减少约 **40.7%**，费用减少约 **48.5%**；
- review：总时长减少约 **30.3%**，费用减少约 **8.2%**；
- 两类样本均通过 Studio 正式 preflight，未发生越界写回或 completion evidence 伪造。

Pi Worker 相对 OpenCode：

- structured：费用减少约 **15.0%**，但总时长增加约 **26.2%**；
- review：总时长减少约 **2.5%**，但费用增加约 **14.1%**；
- 未达到“至少一项改善 20%，另一项不显著恶化”的默认替代门禁。

## 5. 事件与可观测性

通过样本的安全持久事件：

| 样本 | 全部事件 | reasoning activity | text delta | 首 reasoning | 首工具 | 首文件输出 |
|---|---:|---:|---:|---:|---:|---:|
| structured | 195 | 144 | 9 | 2,395 ms | 109,502 ms | 124,473 ms |
| review | 298 | 249 | 7 | 1,854 ms | 190,213 ms | 220,261 ms |

完整 Pi RPC 的 review 探针曾写入至少 34,528 条 reasoning 增量。专用 Worker 降至 249 条，持久化事件减少约 **99.3%**，通过“至少下降 95%”门禁。报告只保存字符数、阶段和用量，不保存 raw reasoning 文本。

## 6. 批判性结论

### 已证明

- 直接使用 Pi Agent Core 比复用完整 coding-agent 更适合 ArcVellum；
- 七工具边界、显式完成、批量产物和 Studio 正式 preflight 可以协同工作；
- 进程、工具和文件权限可以比通用 Agent 更窄；
- 事件写放大可以在 Worker 边界解决；
- structured/review 两类真实任务可端到端到达 writeback approval。

### 未证明

- 未证明 Pi Worker 比 OpenCode 更快或更便宜；
- review 非缓存输入反而增加，说明提示词与上下文仍需压缩；
- 仅有各一份通过样本，不足以估计方差；
- 没有进行匿名文学质量盲评；
- 没有验证 prose、planning、analysis、Autopilot 或安装包；
- 当前隔离仍是受控工作区与路径策略，不是 OS 级进程沙箱。

## 7. 决策

1. 保留 Pi fork 与 Studio `pi-worker` 实验适配器；
2. 默认配置继续禁用，必须显式实验授权；
3. 不进入普通设置页、安装资源、Autopilot、Campaign 或默认 Runtime；
4. 不继续扩展 prose/planning，先解决 review 上下文重复与模型回合成本；
5. 若继续评估，至少做三次交错 structured/review 复测和匿名质量审查；
6. 只有相对 OpenCode 达到既定性能门禁，才讨论 P7 产品化。

这轮验证支持的准确结论是：

> **为 ArcVellum 从 Pi Agent Core 底层搭建专用 Agent 是正确方向；当前原型已经比完整 Pi coding-agent 显著更合适，但还不是更好的默认产品运行时。**
