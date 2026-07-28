# W6-4G6 Bounded Canary 与真实同模型 A/B 实施计划

> 日期：2026-07-28
> 状态：单样本实现与真实 A/B 已完成；生产默认保持 shadow
> 范围：`scene-development/candidate-review` 的合同驱动灰度激活与临时副本真实 A/B。

## 1. 现状结论

W6-4G1 至 G5 已经具备：

- provider usage 分类与 task/scene/model/context attribution；
- task 级 budget shadow；
- 唯一 `ExecutionContextEnvelope`；
- `must_inline`、`exact_on_demand`、`summary_reference`、`excluded` 四级资料合同；
- candidate-review digest-bound 紧凑审查证据；
- 同 session 增量 Repair Context 与越权改动确定性恢复。

但生产配置仍为 `shadow`。现有 Engine 只给四类高成本场景状态声明上下文合同，并统一
标记为 `shadow-ready`。只有 `candidate-review` 已通过紧凑证据、独立消费端校验和真实
项目无模型 50% 字符下降验收。若直接把全局 `worker.context_budget.mode` 改为
`bounded`，未声明合同的任务会 fail closed，尚未完成真实 A/B 的状态也会被错误激活。

## 2. 目标

1. 让 Engine 明确区分 `shadow-ready` 与 `bounded-ready`，不由 Studio 猜测。
2. 在保持默认 shadow 的前提下，增加按 route/state/contract status 白名单的 bounded
   canary。
3. canary 决策进入 Task Context、Run Manifest、Context Ledger 和安全 throughput
   投影，且拥有稳定 policy digest。
4. 使用同一项目、同一 task ID、同一 provider/model，在两个临时项目副本上执行
   shadow/bounded 全流程 A/B。
5. 原正式项目在 A/B 前后内容 digest 完全不变。
6. A/B 记录首轮可见字符、usage 分类、模型轮次、repair/retry、时延、首次 preflight、
   exact review conclusion 与输出 schema，不保存正文、Prompt、隐藏推理或凭证。
7. 任一文学 Gate、上下文身份或审查质量退化时，生产保持 shadow。

## 3. 非目标

- 不把 global default 直接改成 bounded。
- 不激活 candidate-generation、candidate-revision 或 static-revision。
- 不实现 ContextCacheKey、跨任务 session lease、Execution Bundle 或并发。
- 不给 Agent 新的路径、Shell、网络或正式项目权限。
- 不把两次随机模型输出要求为逐字相同。
- 不用模型自评代替正式 candidate-review preflight 与审查结论。

## 4. 合同与灰度设计

### 4.1 Engine 合同状态

`routes/scene/context_contract.py`：

- `candidate-review`：`bounded-ready`；
- 其余当前场景合同：继续 `shadow-ready`。

状态进入现有 task fingerprint。旧任务不能用旧 completion evidence 冒充新合同已执行。

### 4.2 Studio rollout policy

默认配置新增：

```json
{
  "worker": {
    "context_budget": {
      "mode": "shadow",
      "bounded_rollout": {
        "enabled": false,
        "routes": ["scene-development"],
        "states": ["candidate-review"],
        "contract_statuses": ["bounded-ready"]
      }
    }
  }
}
```

确定性决策顺序：

1. `mode=off`：永远 off，rollout 不得覆盖；
2. `mode=bounded`：只有 `bounded-ready` 合同可执行，否则 fail closed；
3. `mode=shadow` 且 rollout disabled：保持 shadow；
4. `mode=shadow` 且 rollout enabled：route/state/status 三组白名单全部命中才 bounded；
5. 任何未知/空配置回到 shadow，不静默放宽。

决策至少包含：

- requested/effective mode；
- enabled 与 matched；
- route/state/contract status；
- machine reason code；
- canonical policy digest。

## 5. 真实 A/B 工具

新增工程验收模块与脚本：

```text
runtime/context_ab.py
scripts/context_ab_experiment.py
```

执行：

1. 对原项目做内容 digest；
2. 分别创建 shadow/bounded 临时副本；
3. 在副本内重新 `task-open`，确保当前 task contract 生效；
4. 使用相同 Runner、provider、model、task ID 和 repair 上限执行完整 Worker；
5. 允许副本内正常 submit/complete，禁止写回原项目；
6. 从 typed events、run manifest 和 review JSON 提取安全指标；
7. 完成后再次计算原项目 digest；
8. 输出 `arcvellum/context-ab-report/v1`，报告只含身份摘要、数值、状态和 conclusion。

A/B 工具不得成为普通用户绕过状态机的入口。它只接受已有正式 task ID，内部仍使用
`AgentWorker`、同一 Sandbox、preflight、writeback 与 Engine lifecycle；唯一差别是整个
正式项目位于一次性临时副本。

## 6. 质量与退出判定

单个 candidate-review 样本至少要求：

- shadow 与 bounded 都完成 exact task preflight；
- 两者 review schema 合法；
- 两者 conclusion 都不是 `fail`；
- bounded mandatory 0 missing、tier 0 overlap；
- bounded 首轮可见字符相对 shadow 下降至少 50%；
- 原项目 digest 不变；
- provider/model 身份一致；
- 不出现新的 repair/retry 或运行失败。

单样本只允许开启 canary，不足以宣布全任务族 W6-4G 完成。最终生产默认激活还需要：

- 多场景等价样本；
- 非缓存 input token 中位数下降至少 40%；
- 首轮可见字符中位数下降至少 50%；
- repair + retry 模型轮次下降至少 25%，或在零基线时保持为零；
- 首次 preflight 与 AgentReview 通过率不下降；
- Canon、人物状态、文风、字数、节奏、promotion/writeback Gate 零缺失；
- 明确 rollback 演练。

## 7. 测试矩阵

### 单元

- off 不被 rollout 覆盖；
- shadow disabled 保持 shadow；
- 三白名单全命中才 bounded；
- `shadow-ready`、错误 route/state 均不激活；
- global bounded 遇非 `bounded-ready` fail closed；
- policy digest 稳定且对规则变化敏感；
-预算报告和安全投影不泄露路径或正文。

### 集成

- candidate-review 任务签发为 `bounded-ready`；
-其他场景合同保持 `shadow-ready`；
- Worker run manifest 记录同一 rollout identity；
- temp-copy A/B 不改变原项目；
- mock Runner 下 shadow/bounded 使用同 task/model 并产生可比较报告；
-任一 arm 失败时报告 fail closed，不给出误导性“提升”结论。

### 工程门禁

- 全量 Python 与 Client；
- Prompt Registry；
- Client production build；
- Architecture Audit；
- `compileall` 与 `git diff --check`；
- 真实项目临时副本 A/B。

## 8. 架构约束

- Engine 拥有 task context readiness；Studio 只消费，不反向导入 Engine。
- rollout policy 只决定执行上下文模式，不改变 task、Gate 或 writeback。
- A/B runner 只组合公开 Worker 与安全投影，不复制 preflight、review 或 task lifecycle。
- Runtime Adapter 不理解 canary policy。
- throughput projection 只消费 typed events。
- 新实现不得扩大 Architecture Audit baseline，不得把实验逻辑塞回 `worker.py`。
- `.tmp/` 不纳入 Git。

## 9. Git 闭环

本批形成一个单一目的提交，至少包含：

- bounded readiness 与 rollout policy；
- A/B 工具及测试；
-真实项目无写回和真实模型指标；
- 模块边界、进度和 Architecture Review；
- 全量门禁结果。

若真实 provider 不可用，代码与确定性验收仍可提交，但必须把真实 A/B 标记为未完成，
不得启用 canary 或宣称 W6-4G 已关闭。

## 10. 实施结果

本计划的单样本范围已经完成：

- Engine 将 `candidate-review` 标记为 `bounded-ready`，其他当前场景合同继续
  `shadow-ready`；
- Studio 增加合同驱动的 rollout policy。`off` 不可被覆盖，显式 bounded 遇到未就绪
  合同 fail closed，默认 shadow 只有在 route、state 和 contract status 三组白名单全部
  命中时才进入 canary；
- requested/effective mode、contract status、reason 与 policy digest 已进入安全预算、
  Run Manifest 和 throughput 投影；
- A/B 两臂使用各自临时项目副本、独立 RuntimePool 与 ProcessManager，运行结束后主动
  关闭实验拥有的进程；
- 两臂均通过现有 Worker 的 preview writeback 和正式
  `approve_writeback()` 路径完成副本内 submit/complete，没有复制或弱化 Gate；
- 增加历史任务合同 replay，旧任务可在隔离副本中按当前合同重新签发，不修改正式项目。

2026-07-28 在项目 `1+1=2`、任务
`scene-development-scene-0004-candidate-review`、模型
`deepseek/deepseek-v4-flash` 上完成一次真实同模型 A/B：

| 指标 | shadow | bounded |
| --- | ---: | ---: |
| 状态 | complete | complete |
| 首轮可见字符 | 139668 | 63967 |
| exact-on-demand 字符 | 0 | 74689 |
| 非缓存输入 Token | 69535 | 75950 |
| 耗时 | 140.579 s | 142.284 s |
| Review | pass | pass_with_notes |
| Repair / Retry 增量 | 0 | 0 |

判定结果：

- 首轮可见上下文下降 **54.20%**；
- mandatory 资料完整、tier 无重叠、两臂首次 preflight 均通过；
- 两臂使用相同 provider/model，审查 schema 合法且结论均非 fail；
- 原正式项目执行前后 digest 完全一致；
- bounded 本样本非缓存输入 Token 比 shadow **增加 9.23%**，耗时增加 1.705 秒。

因此该结果只支持把当前实现认定为 `canary_candidate=true`。它证明合同、隔离、Gate、
写回和进程回收闭环可用，但不能证明总体 Token 或时延改善。生产配置继续
`mode=shadow`、`bounded_rollout.enabled=false`；W6-4G 的最终退出仍需多场景样本、
中位数/P95、质量不退化证据和 rollback 演练。
