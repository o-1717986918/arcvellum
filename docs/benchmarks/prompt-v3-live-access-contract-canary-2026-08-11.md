# Prompt v3 编译后访问合同首轮 Live Canary

> 日期：2026-08-11
> 模型：DeepSeek `deepseek-v4-flash`
> Runtime：ArcVellum Pi Worker
> 结论：structured/review 首轮技术样本通过；尚未完成三次交错 A/B 与文学盲评。

## 问题

Prompt v3 会把完整 sidecar 和恢复资料从首轮证据降为 exact-on-demand。此前 `TASK_CONTEXT.json` 仍只携带编译前 `ExecutionContextEnvelope`，导致 Prompt 展示的按需资料不在 Pi Worker 的实际按需读取集合中。模型会尝试读取、被拒绝，再凭不完整 Schema 猜测输出。

这不是 Provider、推理等级或 Studio 预检故障，而是编译后可见性与 Runtime 授权之间缺少显式合同。

## 修复

- 新增内容安全的 `arcvellum/prompt-access/v1` 投影，记录最终正式 Prompt 的版本、renderer、inline 路径、exact-on-demand 路径和 digest。
- Capability Manifest 继续作为读取权限硬上界；`prompt_access` 只能收窄或重新分层已授权资料，不能增加项目权限。
- Pi Worker 优先消费 `prompt_access`；旧任务包缺少该字段时回退 `execution_context.exact_on_demand`。
- compact scene review Schema 使用 `required_type_groups` 携带必填字段类型，避免模型猜测 `character_logic` 等字段应为 list 还是 dict。
- 运行时说明去除重复表达，review v3 compile canary 仍保持 40% 字符缩减门槛。

## 结果

| 样本 | 状态 | Prompt 字符 | 总耗时 | Provider 请求 | Reasoning tokens | Preflight |
|---|---:|---:|---:|---:|---:|---:|
| structured v3 | waiting_writeback | 8,465 | 73.0 s | 4 | 0 | 0 issues |
| review v3，缺类型投影 | preflight_failed | 14,240 | 34.8 s | 4 | 0 | `character_logic` type error |
| review v3，类型分组修复 | waiting_writeback | 14,111 | 68.4 s | 3 | 0 | 0 issues |

对应内容安全机器证据：

- `prompt-v3-live-structured-access-contract-2026-08-11.json`
- `prompt-v3-live-review-access-contract-2026-08-11.json`
- `prompt-v3-live-review-schema-contract-2026-08-11.json`

## 尚未证明

- 单次成功不能替代三次交错 v2/v3 A/B；
- 尚未完成匿名文学质量评审；
- DeepSeek 只支持向下安全钳制到 `off`，不代表精确执行 512/768 reasoning-token 单请求预算；
- Prompt v3 不应在上述门禁完成前扩展到 planning、prose 或产品全局默认。
