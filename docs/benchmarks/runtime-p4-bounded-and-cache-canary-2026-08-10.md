# P4 Bounded Context 评估与 Prepared Cache Canary 证据

> 日期：2026-08-10  
> 范围：`scene-development / candidate-review`  
> Runtime：OpenCode  
> 模型：`opencode/deepseek-v4-flash-free`

## 1. 正式样例

Runtime benchmark catalog 新增 `review-scene-candidate`。该样例不是手工构造 TaskPackage：

1. 从嵌入式引擎初始化脱敏文学项目；
2. 沿正式 scene-development route 完成 context、RP、branch 和 composition 前置链；
3. 由真实 `generate-scene` 命令生成 prompt manifest 与 Agent sidecar；
4. 写入稳定脱敏候选和满足正式 provenance 的 manifest；
5. 由状态机签发真实 `candidate-review` 任务；
6. `agent-review-scene` 生成 exact-candidate context evidence、Style Lint、字数、节奏和输出 schema 合同。

该样例与 prose benchmark 共用同一场景夹具，但目标任务不同；catalog 现在是 6 个 ready case、5 种 Runtime 任务类别。

## 2. 同模型 A/B

Shadow 与 bounded 使用同一源任务、同一模型和隔离项目副本。源项目摘要在实验前后相同。

| 指标 | Shadow | Bounded | 变化 |
|---|---:|---:|---:|
| 首轮可见字符 | 45,846 | 15,978 | -65.15% |
| 非缓存输入 token | 38,863 | 13,165 | -66.12% |
| 总 token | 308,012 | 101,602 | -67.01% |
| 总耗时 | 261.042 s | 146.255 s | -114.787 s |
| 模型轮次 | 1 | 1 | 0 |
| repair / retry | 0 / 0 | 0 / 0 | 0 |
| 首次 preflight | pass | pass | 不劣化 |
| review | pass_with_notes | pass | 不劣化 |

两臂 review schema 相同；bounded mandatory 缺失为 0，tier overlap 为 0，exact-on-demand 没有发生额外读取。单次报告的自动化 canary criteria 均通过。候选项目的确定性证据把字数合同标为 `not_required`，Style Lint、节奏和衔接均为 pass，因此 bounded 的 clean pass 与夹具预期一致；shadow 的额外批注不能被解释为 bounded 漏审的直接证据。

此结果证明 bounded candidate-review 值得继续验证，不证明所有题材、所有场景或所有模型的文学质量都已非劣。现有 multi-scene suite 仍要求至少 3 个样本，并且尚未完成独立文学盲评，因此默认 bounded rollout 保持关闭，只允许显式实验开启。

## 3. 回滚演练

对同一正式任务执行确定性 rollout drill：

- allowlist 开启：`bounded-ready` candidate-review 进入 bounded；
- allowlist 关闭：立即恢复 shadow；
- policy digest 发生变化；
- TaskPackage 内容摘要不变；
- 5 项回滚标准全部通过。

实验 allowlist 只允许：

```text
route = scene-development
state = candidate-review
contract_status = bounded-ready
```

任何未匹配任务继续使用 shadow；显式 bounded 且合同不完整时仍 fail closed。

## 4. Prepared Context Cache

缓存实验与模型 A/B 分开运行，不调用模型。第一次准备为 miss，后续 6 次为 hit：

| 指标 | 结果 |
|---|---:|
| 首次 miss | 366.218 ms |
| hit 中位数 | 308.200 ms |
| 本地准备耗时改善 | 15.84% |
| 内容摘要一致 | pass |
| context budget 摘要一致 | pass |
| cache key 一致 | pass |
| 源项目未修改 | pass |

实验还发现并修复了一个真实边界错误：candidate-review 的 context trace 会按 bounded 合同从 Agent workspace 排除，但缓存键过去也从 Agent workspace 读取 trace，导致安全 bypass。现在版本身份从受信任的 control workspace 读取，模型可见内容仍只来自 Agent workspace。

默认只开启 cache canary，范围同样限于 `scene-development / candidate-review`，最多保留 32 个进程内可重建投影；应用退出时清空。它减少上下文准备的 CPU/本地文件 IO，不减少模型 token，也不保存 Canon 或正文的第二份权威副本。bounded rollout 默认关闭。

## 5. 验证与回滚

- 定向回归：23 项通过；
- 后端全量回归：964 项通过，1 项跳过；
- 前端回归：159 项通过；
- 架构审计、编译与 `git diff --check`：通过；
- cache 内容变化失效测试：通过；
- 原始 reasoning、prompt、正文和绝对项目路径未写入证据文档；
- 回滚 bounded：设置 `worker.context_budget.bounded_rollout.enabled=false`；
- 回滚 cache：设置 `worker.prepared_context_cache.enabled=false`；
- 旧用户显式配置继续优先，不由迁移逻辑强制开启。

## 6. 结论

P4 的实现、正式单场 A/B、回滚与 cache micro-benchmark 已完成。Prepared Context Cache 达到窄 canary 条件；bounded context 因样本数与独立文学盲评不足，保持显式 opt-in，不进入默认产品流。扩大到其他 review、analysis、structured 或 prose 任务仍需独立样例和 A/B。
