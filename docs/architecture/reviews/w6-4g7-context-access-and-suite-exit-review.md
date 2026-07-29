# W6-4G7 Context Access 与多样本退出证据 Review

> 日期：2026-07-29
> 结论：实现与退出证据通过；生产默认仍保持 `shadow`

## 1. 结论

W6-4G7 已完成 Context Access 语义统一、安全读取遥测、多样本 A/B 汇总和
bounded-to-shadow 回滚演练。

真实项目 `1+1=2` 的三个不同 candidate-review 任务使用同一
`deepseek/deepseek-v4-flash` 模型、同一路线和相同 Runtime 完成隔离 A/B：

- 三组 shadow / bounded 均完整结束；
- 六次审查结论均为 `pass`；
- 六次首次 deterministic preflight 均通过；
- repair 与 retry 基线和 bounded 结果均为 0；
- mandatory context 零缺失、tier 零重叠；
- 三次执行前后正式项目 digest 均不变；
- 非缓存输入 Token 降幅中位数为 **47.18%**；
- 首轮可见字符降幅中位数为 **62.64%**；
- 回滚演练全部条件通过。

`arcvellum/context-ab-suite-report/v1` 因而给出 `exit_candidate=true`。这关闭
W6-4G 的实现与证据工作，但不把新版本安装或升级静默转成 bounded。生产默认继续
`mode=shadow`、`bounded_rollout.enabled=false`；运维方可以显式启用
candidate-review 白名单，并可只改配置立即回滚。

## 2. 实现复核

### 2.1 Context Access 语义

`runtime/context_access_policy.py` 把 protected output 分成三类：

1. 已作为 `must_inline` 提供的受保护产物直接使用首轮快照；
2. `exact_on_demand` 受保护产物只在具体判断缺证据时读取；
3. 没有进入 Execution Context 分类的受保护产物继续 fail closed。

`task_program.py` 和 `worker_program_template.py` 共用该策略，不再同时出现
“按需读取”和“所有 protected output 必须读取”的冲突指令。

### 2.2 Candidate Review 合同

候选审查首轮保留：

- 精确候选 Markdown；
- scene YAML；
- compact review evidence；
- composition review；
- branch selection；
- creative quality profile；
- mounted style profile；
- punctuation standard。

完整 context packet 不被删除，也不进入 excluded tier；它进入
`exact_on_demand`，在人物、Canon 或长程因果判断出现具体疑点时仍可精确读取。
候选 manifest、context trace 和 raw word-budget JSON 由 control workspace 保留，
Agent workspace 不重复暴露。

`preflight/scene_review_metadata.py` 只规范化任务所有的 schema、scene/candidate
身份、source paths、reviewer session、style snapshot 和 creative-quality digest。
它不改 candidate SHA、审查结论、文学证据、问题或修订建议。

### 2.3 安全遥测

`runtime/context_access.py` 只输出读取次数、类别、字符量和重复读取计数。它不保存：

- Prompt 或正文；
- 工具返回内容；
- 绝对路径；
- 凭证；
- 隐藏推理。

OpenCode Runtime 发出 typed context-access event，throughput projection 只投影安全
数值。未知读取、must-inline 重读和 exact-on-demand 实际读取可以分别观察。

### 2.4 A/B 与回滚

- `context_ab.py` 继续只负责单任务、双隔离副本执行；
- `context_ab_reporting.py` 继续只负责单样本安全报告；
- `context_ab_suite.py` 与 `context_ab_suite_facts.py` 聚合三个以上样本；
- `context_rollout_drill.py` 只验证策略切换和任务合同不变，不调用模型；
- 每个 A/B arm 独占并关闭 RuntimePool 与 ProcessManager；
- 原项目不接收实验写回。

## 3. 真实 A/B 证据

| 场景 | 首轮可见字符 shadow -> bounded | 降幅 | 非缓存输入 shadow -> bounded | 降幅 | Review | Repair/Retry |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| scene_0001 | 81,644 -> 34,942 | 57.20% | 49,400 -> 22,964 | 53.51% | pass / pass | 0 / 0 |
| scene_0002 | 82,770 -> 30,919 | 62.64% | 45,711 -> 31,179 | 31.79% | pass / pass | 0 / 0 |
| scene_0003 | 81,967 -> 30,071 | 63.31% | 57,469 -> 30,356 | 47.18% | pass / pass | 0 / 0 |

汇总：

- 非缓存输入降幅：minimum 31.79%，median 47.18%，P95 53.51%；
- 首轮可见字符降幅：minimum 57.20%，median 62.64%，P95 63.31%；
- bounded exact-on-demand 实际读取字符中位数：0；
- shadow / bounded repair+retry 总数：0 / 0；
- 三个 bounded arm 都在不读取完整 context packet 的情况下给出合法 `pass`。

## 4. 负面证据与限制

额外执行的 scene_0004 没有被隐藏：

- shadow 为 `pass`；
- bounded 为 `pass_with_notes`；
- bounded 准确指出正文对白中两处破折号使密度达到 2.9%，高于 2% 规则阈值；
- 该结论来自首轮内联的 deterministic style evidence，不是缺少完整 context packet。

因此它不证明 bounded 文学审查退化，反而暴露了模型结论的随机性和当前 ordinal
比较的保守性。但按照既定 `pass > pass_with_notes` 规则，这个样本不能作为退出通过
样本。后续质量评估可以增加“确定性证据覆盖是否改善”的并列指标，但不得回改本轮
报告来迁就结果。

其他限制：

- 当前只证明 `candidate-review` 任务族；generation、revision 和其他路线仍是
  `shadow-ready`；
- 单场 token 降幅存在波动，scene_0002 只有 31.79%，不能用中位数掩盖长尾；
- 本批不提供跨任务 session reuse、ContextCacheKey、Execution Bundle 或并发；
- 生产默认没有自动切换，显式灰度启用后仍应持续观察 Review 结论与 repair 长尾。

## 5. 回滚演练

在隔离项目副本中先 replay 当前任务合同，再启用 candidate-review bounded 白名单：

- 三个 `bounded-ready` 任务全部进入 bounded；
- 关闭 rollout 后三个任务全部恢复 shadow；
- policy digest 发生预期变化；
- task payload digest 前后完全一致；
- 没有修改正式项目或历史任务。

回滚只需要：

```json
{
  "mode": "shadow",
  "bounded_rollout": {
    "enabled": false
  }
}
```

## 6. 工程门禁

- Python：702 tests passed，1 skipped；
- Client：48 files、141 tests passed；
- `python -m compileall -q src tests`：passed；
- Prompt Registry：54 assets、89 task prompt IDs、0 errors/warnings；
- Client production build：passed，桌面静态资源同步验证通过；
- Architecture Audit：34 existing file debts、220 existing function debts、0 cycles，
  无新增 violation；
- `git diff --check`：passed。

## 7. 后续

W6-4G 已具备关闭条件。下一批按既定路线进入 W6-5B：将已验证的 scene adaptive plan
通过 active-plan loader、run-scoped immutable snapshot、Context Ledger 和 Mutation
Receipt 接入现有正式 Worker 生命周期。W6-5B 不得重新实现 task、Review、promotion
或 state lifecycle。
