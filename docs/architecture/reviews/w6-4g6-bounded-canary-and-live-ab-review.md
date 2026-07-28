# W6-4G6 Bounded Canary 与真实同模型 A/B Review

> 日期：2026-07-28
> 结论：单样本 canary 候选成立；不得全局激活 bounded。

## 范围

本批只验证 `scene-development/candidate-review` 的合同驱动 bounded canary，以及同一
任务、同一 provider/model 在两个临时项目副本中的真实 A/B。它不改变文学 Gate、正式
项目写权限、Agent 角色、任务顺序或全局默认模式。

## 架构结果

### Rollout 所有权

`runtime/context_rollout.py` 只把请求模式、Engine 合同状态和配置白名单编译为不可变
rollout decision。Engine 拥有 `bounded-ready` 声明，Studio 只消费；Runtime Adapter
不解释文学状态或灰度规则。

默认配置保持：

```json
{
  "mode": "shadow",
  "bounded_rollout": {
    "enabled": false,
    "routes": ["scene-development"],
    "states": ["candidate-review"],
    "contract_statuses": ["bounded-ready"]
  }
}
```

显式 `off` 不可被 canary 覆盖；显式 `bounded` 遇未就绪合同 fail closed；shadow 只有
三组白名单全部命中才可灰度。决策带稳定 policy digest，并进入预算、运行清单和安全
观测投影。

### 隔离实验

`runtime/context_ab.py` 负责编排两个一次性项目副本，复用现有 Task Registry、
AgentWorker、Sandbox、preflight、preview writeback、submit/complete 和
`approve_writeback()`。它不复制 Gate，也不直接移动模型产物。

每一臂独占并最终关闭 RuntimePool 与 ProcessManager。报告路径不得位于源项目内；报告
只保存任务身份、模式、计数、usage、时延、preflight 与 review 结论，不保存 Prompt、
正文、隐藏推理、凭证或绝对作品内容。

### 历史合同 replay

Engine 的维护命令 `task-contract-replay` 只在隔离项目副本中按当前任务合同重签历史
任务。它用于比较合同版本，不成为普通创作流程的旁路，也不能写回源项目。

## 真实运行证据

项目：`1+1=2`

任务：`scene-development-scene-0004-candidate-review`

模型：`deepseek/deepseek-v4-flash`

| 指标 | shadow | bounded |
| --- | ---: | ---: |
| 完成状态 | complete | complete |
| 首轮可见字符 | 139668 | 63967 |
| exact-on-demand 字符 | 0 | 74689 |
| 非缓存输入 Token | 69535 | 75950 |
| 运行时长 | 140.579 s | 142.284 s |
| 首次 preflight | pass | pass |
| Review conclusion | pass | pass_with_notes |
| Repair / Retry | 0 / 0 | 0 / 0 |

首轮可见上下文下降 54.20%，mandatory 零缺失、tier 零重叠、两臂同模型、审查 schema
合法，原项目 digest 不变。与此同时，bounded 的非缓存输入 Token 增加 9.23%，耗时
增加 1.705 秒。较小首轮上下文并没有在这一个样本中转化为更低总 Token。

## 失败经验

历史 `scene_0004 candidate-revision` 的 `sandbox output still fails deterministic
preflight` 并非 bounded 合同失败。该 Agent 在 Allowed Outputs 之外创建了
`characters/candidates/scene-0004-母亲.json`，后来只把内容清空为 `{}`，文件本身仍是
越界改动，故旧 preflight 正确拒绝。

当前 W6-4G5 已在模型 repair 之前确定性恢复可证明的越界改动：新建越权文件删除，已有
文件从 staged baseline/control workspace 恢复；无法证明可恢复的路径继续 fail closed。
回归测试锁住这一行为，不把自动清理变成权限豁免。

## 决策

- `canary_candidate=true`；
- 全局 `mode` 继续为 `shadow`；
- `bounded_rollout.enabled` 继续为 `false`；
- 不把单样本 54.20% 可见字符下降表述为 Token 或时延优化完成；
- 只有多场景样本满足中位数/P95、Review/Preflight 不退化、Repair/Retry 不增加并完成
  rollback 演练后，才讨论生产灰度。

## 后续

1. 覆盖不同字数、Review 结论和资料规模的多个 candidate-review 样本。
2. 解释 bounded exact-on-demand 工具轮次为何导致本样本总输入 Token 上升。
3. 统计中位数、P95、首次 preflight、repair/retry 和 Review 结论分布。
4. 演练 canary 配置回退到 shadow，并证明新旧任务均能继续执行。
5. candidate-generation、candidate-revision 与 static-revision 各自完成合同和真实 A/B
   前，保持 `shadow-ready`。

## 验收

- Python：691 tests passed，1 skipped；
- Client：48 files、141 tests passed；
- Client production build：passed，164 frontend assets、8 WebP assets，桌面资源同步通过；
- Prompt Registry：54 assets、89 task prompt IDs、0 errors/warnings；
- Architecture Audit：passed，34 个既有 file debt、221 个既有 function debt、0 cycle，
  无新增 violation；
- `python -m compileall -q src tests scripts benchmarks`：passed；
- `git diff --check`：passed。
