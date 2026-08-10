# P5 -> P6 同模型门禁复测

> 日期：2026-08-10
> Pi：`0.84.1`，固定提交 `936aff00918de1187f085f123c2812d8f2d67745`
> 对照模型：`deepseek/deepseek-v4-flash`
> 结论：**不进入 P6**。

## 1. 复测原因

P5 初次评估时，Pi 没有可用凭证，无法与 OpenCode 做同 Provider、同模型、同任务比较。用户随后在 Pi 自有凭证库中配置了 DeepSeek API。复测确认：

- Pi 与 OpenCode 均能访问 `deepseek/deepseek-v4-flash`；
- 每一对样本使用相同 benchmark case、task fingerprint 和 prepared context 字符数；
- 凭证仍由各 Runner 自有存储管理，报告不包含凭证、提示词、作品内容或绝对路径；
- 两侧均复用相同 Task Package、sandbox、deterministic preflight 和 writeback approval 边界。

## 2. 结果

| 样本 | Runtime | 状态 | 总耗时 | 费用 | 非缓存输入 | 总 token | 工具 | 修复 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `review-scene-candidate` | OpenCode | awaiting writeback approval | 231,596 ms | $0.012957 | 28,637 | 206,575 | 4 | 0 |
| `review-scene-candidate` | Pi RPC | awaiting writeback approval | 323,876 ms | $0.016103 | 29,799 | 247,538 | 4 | 0 |
| `structured-world-foundation` | OpenCode | awaiting writeback approval | 103,144 ms | $0.006747 | 22,585 | 62,253 | 4 | 0 |
| `structured-world-foundation` | Pi RPC | awaiting writeback approval | 219,322 ms | $0.011132 | 23,315 | 132,894 | 4 | 0 |

相对 OpenCode：

- review 样本中，Pi 总耗时增加约 **39.8%**，费用增加约 **24.3%**；
- structured 样本中，Pi 总耗时增加约 **112.6%**，费用增加约 **65.0%**；
- 两类样本均一次通过 deterministic preflight，没有 repair，说明协议与正式产物边界可用，但没有证明吞吐或成本价值。

## 3. 观测缺口

Pi 当前能产生真实 reasoning 活动，但 P5 适配器没有把 Pi 事件正确投影为 benchmark 的首活动时间字段，因此 `time_to_first_*` 仍为 unavailable。review 探针完成前已观察到至少 34,528 条逐增量 `reasoning.activity` 记录，说明当前事件接入存在明显写放大。

这不是模型输出正确性问题，而是 Runtime telemetry 边界问题：高频增量应进入有界内存流，并按时间窗或累计量聚合为持久摘要，不应逐条写入运行 JSONL。

## 4. 门禁判定

| P6 晋升条件 | 结果 |
|---|---|
| 首个真实活动 P50 改善至少 25%，或消除误超时 | **无合格证据**：Pi 首活动指标未正确汇总，两侧也没有误超时 |
| 总时长/费用至少一项改善 20%，另一项不恶化超过 10% | **失败**：两个指标在两类样本中均明显恶化 |
| preflight 首次通过率不低于 OpenCode | **通过当前探针**：两侧均首次通过 |
| 文学盲评非劣 | **未执行**：硬性能门禁已失败，不追加真实模型成本 |
| 正式项目越权写回为 0 | **通过当前探针**：两侧均停在 writeback approval，没有自动写回 |

根据既定证据纪律，协议可用不能替代产品价值证据。本轮不进入 P6，也不把 Pi 暴露到普通 `task-run`、设置页、安装包或默认 Runtime。

## 5. 重新开放门禁前的必要工作

1. 在 P5 适配层聚合 Pi reasoning 增量，恢复首活动、首工具、首输出和 session model 的完整指标。
2. 核对 Pi 与 OpenCode 的 reasoning、缓存和最大输出策略是否等价；不等价时报告必须明确变量，不能宣称 Agent loop 对比。
3. 增加显式完成语义，减少通用 coding-agent 在已经形成合格产物后继续推理或检查的倾向。
4. 使用交错顺序与至少三个样本重跑 structured/review；只有出现接近晋升阈值的信号，才追加 analysis/prose 与文学盲评。
5. 保持 Pi 默认禁用、短生命周期和脱敏 fixture 约束；OS 级外部读取隔离未建立前，不使用用户作品做实验。
