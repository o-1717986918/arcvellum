# W6-4G7 Context Access 与多样本退出证据实施计划

> 日期：2026-07-28
> 状态：已完成（退出证据见同目录 Review）
> 前置：W6-4G6 单样本 canary 候选成立，生产默认仍为 `shadow`

## 1. 问题结论

真实 `scene_0004 candidate-review` A/B 中，首轮可见字符下降 54.20%，但 bounded
非缓存输入 Token 反而增加 9.23%。当前证据只能说明 Sandbox、Gate 和合同成立，不能
说明吞吐改善。

代码审计发现一条确定性冲突：

- Worker 总体规则要求 Exact On Demand 只在精确判断缺证据时读取；
- `CLI Protected Outputs` 段却要求所有未内联 protected outputs 必须逐一读取；
- candidate-review 的完整 `.agent_tasks.md` 是 exact-on-demand recovery sidecar，
  compact review context 和机器可读 semantic contract 已经覆盖正常审查所需合同；
- 因而模型被迫开启第二轮读取，首轮节省的上下文重新进入会话，并承担会话历史重传成本。

W6-4G7 不通过删除文学证据、降低 Gate 或继续放大预算解决问题。

## 2. 本批目标

1. 统一 Protected Output 与 Execution Context 语义：
   - 已内联 protected output 直接使用快照；
   - exact-on-demand protected output 只作为精确恢复证据，正常流程不得强制读取；
   - 未被 Execution Context 分类的 protected output 继续 fail closed。
2. 增加安全 Context Access 遥测：
   - 从 OpenCode 完成消息的工具记录计算读取次数；
   - 只记录计数、字符数、重复读取和权限类别，不保存正文、工具输出、绝对路径或隐藏推理；
   - 区分 exact-on-demand 实际读取、must-inline 重读、其他授权读取和未映射读取。
3. 增加多样本 A/B Suite 报告：
   - 至少三个不同 scene task；
   - 统计非缓存输入、首轮可见字符、repair/retry 和时延的中位数与 P95；
   - 检查首次 preflight、Review 结论、mandatory/tier、原项目不变和模型身份；
   - 单样本 `canary_candidate` 不得冒充 W6-4G 退出。
4. 增加 bounded rollout 回滚演练：
   - canary 时只有 `bounded-ready` 白名单任务进入 bounded；
   - 关闭 rollout 后所有任务恢复 shadow；
   - task contract 内容和 digest 不变；
   - 回滚证据只证明策略切换，不冒充真实 provider 任务完成。

## 3. 模块边界

| 模块 | 责任 | 禁止 |
| --- | --- | --- |
| `runtime/task_program.py` | 消除 read-rule 冲突 | 改 Engine Gate 或 task lifecycle |
| `runtime/context_access.py` | 从完成消息生成安全读取摘要 | 保存 Prompt、正文、工具输出、绝对路径 |
| `runtimes/opencode.py` | 调用摘要器并发出 typed event | 解释文学内容或修改任务合同 |
| `runtime/context_ab_suite.py` | 聚合既有 v1 A/B 报告并判断退出候选 | 执行 Worker、复制 preflight、改变生产配置 |
| `runtime/context_rollout_drill.py` | 验证 canary 到 shadow 的合同回滚 | 调模型、写正式项目 |

`context_ab.py` 继续只编排单任务隔离 A/B；`context_ab_reporting.py` 继续只负责单样本
安全报告。多样本聚合不得塞回这两个已有大文件。

## 4. 安全读取遥测合同

输出采用 `arcvellum/context-access-summary/v1`，只允许：

- `read_tool_calls`
- `unique_read_targets`
- `exact_on_demand_read_calls`
- `exact_on_demand_unique_files`
- `exact_on_demand_read_characters`
- `must_inline_reread_calls`
- `other_authorized_read_calls`
- `unmapped_read_calls`
- `redundant_read_calls`
- `digest`

字符数按沙箱内合同文件计算，不从模型返回的工具正文计算。目录遍历、glob 和 grep 不被
伪装成精确文件读取；它们计入未映射读取，供后续诊断。

## 5. Suite 退出判定

`exit_candidate=true` 必须同时满足：

1. 不同 task ID 至少 3 个，全部是同 route/runtime 的合法 v1 报告；
2. 全部样本保持同模型、两臂完成、首次 preflight 通过、原项目不变；
3. bounded mandatory 缺失和 tier overlap 均为 0；
4. bounded Review 不比同样本 shadow 更差，且 schema 一致；
5. 非缓存输入 Token 降幅中位数至少 40%；
6. 首轮可见字符降幅中位数至少 50%；
7. repair+retry 有非零基线时降幅中位数至少 25%，零基线时 bounded 保持为 0；
8. 回滚演练通过。

P95 作为风险证据展示，不用一次低中位数掩盖长尾。若 provider usage 缺失，Token
指标明确失败，不用字符估算替代。

## 6. 测试与验收

### 确定性

- Protected Output 三类读取规则测试；
- OpenCode 工具消息路径归一化、重复读取、越界与内容脱敏测试；
- Suite 中位数/P95、Review 退化、零 repair 基线和缺失 usage 测试；
- Rollout enabled/disabled、白名单、不就绪合同和 task digest 不变测试。

### 真实项目

使用 `C:\Users\26532\Documents\ArcVellum\Works\1+1=2` 的不同 candidate-review
历史任务，在隔离副本中 replay 当前合同并执行同模型 A/B。报告写在项目外。

若样本不足或真实模型不可用：

- 可提交确定性实现与回滚演练；
- 生产默认继续 `shadow`；
- 不关闭 W6-4G，不进入 W6-5B。

## 7. 退出与回滚

- 本批代码本身可由单一 Git commit 回滚；
- 配置回滚只需设置 `mode=shadow` 且
  `bounded_rollout.enabled=false`；
- 不迁移项目数据，不改变正式 task schema，不删除旧报告；
- Architecture Audit 不得增加新循环依赖或扩大既有 file/function debt。
