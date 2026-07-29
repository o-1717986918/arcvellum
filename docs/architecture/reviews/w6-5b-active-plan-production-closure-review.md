# W6-5B Active Plan 生产激活与场景闭环 Review

> 日期：2026-07-29
> 结论：实现与退出门禁通过；W6-6 Rolling Horizon 尚未开始

## 1. 结论

W6-5B 已把 AO-4 场景自适应计划接入现有正式 Worker 生命周期。计划仍是
`Future Intent`，不能签发任务、判定 Review、晋升正文或写回项目事实；Engine
继续拥有唯一的 task、Review、promotion、state/canon 生命周期。

正式接线具备以下性质：

- `shadow` revision 不能直接激活；
- assisted activation 必须拥有独立 Review、显式授权和完整审计链；
- Worker 只在 assisted/adaptive 模式读取已验证 active plan；
- 缺少有效计划时可观察地回退 fixed route；
- 篡改 active projection 或审计文件时 fail closed；
- 绑定后的 task package 在 run 内冻结，恢复、预检和写回读取同一快照；
- Context Ledger 与 Mutation Receipt 记录同一 plan/revision/node；
- 同一真实项目夹具完成正式正文晋升、人物状态审批写回和 Canon 审批写回。

本批没有实现 Scheduler、Execution Bundle、跨场景并发、章节滚动窗口或第二套任务
状态机。

## 2. 激活与完整性

`orchestration/active_plan.py` 是生产读取入口。它同时验证：

1. `active_plan.json` 投影；
2. SQLite 中唯一 active revision；
3. candidate、normalized plan、compiled graph、Lint、simulation、Review 审计文件；
4. 文件 SHA-256 与 revision digest；
5. assisted authorization digest；
6. normalized plan 与 compiled graph 的 plan/revision/fingerprint 身份；
7. 当前 planning project fingerprint。

`orchestration/activation.py` 只编排授权后的激活事务；
`persistence/creative_plan_authorization.py` 只验证独立 Review 与授权候选。
相同 actor/reason/revision 的重复授权幂等，不同授权内容冲突并拒绝。

planning fingerprint 只覆盖规划事实，排除候选、patch、state patch、task run 和
worker run 等执行产物。正式写作不会仅因产生计划内产物而把当前计划立即判旧；Canon、
人物、场景或规划事实改变仍会使计划失效。

## 3. Worker 与不可变快照

`AgentWorker` 在 Engine `task-open` 之后、Sandbox staging 之前尝试绑定当前 scene
task。它不解释或修复计划，只消费 `ActivePlanLoader` 返回的已验证值。

绑定只增加机器拥有的：

- creative plan ID、revision、node ID/kind；
- RP 深度、分支数量、修订策略、叙事距离；
- Engine catalog 注入的 required gates；
- 对现有命令的受控参数。

task ID、task type、expected outputs、formal route 顺序与生命周期不被替换。
`promotion-manifest` 等没有对应创意节点的正式状态保持 passthrough。

`runtime/task_snapshot.py` 在 run 根冻结绑定后的 task JSON 与 Markdown。
Run Manifest 保存快照路径、文件 hash 与整体 digest。恢复、预检、审批和写回均重载
并验证快照；项目中的原 task JSON 后续变化不能改变正在运行的任务，快照本身变化会被
拒绝。

## 4. 正式场景闭环证据

组合验收使用受控 Agent 文学产物夹具，所有确定性 Gate 和正式写回使用生产代码：

1. 同一 active plan 绑定 Context/RP、分支、选支、Composition、正文、Review、
   Revision、State 与 Canon 节点；
2. RP 深度和分支数进入现有 Engine task，而非新建任务；
3. candidate-generation 与独立 exact-candidate Review 通过现有 Gate；
4. `promote_scene_candidate()` 生成正式 draft 与 promotion manifest；
5. digest-bound state review 与用户批准后，`apply_character_state_patch()` 原子写回
   人物状态；
6. digest-bound Canon patch 与用户批准后，`apply_canon_patch()` 写入 apply receipt；
7. fixed 模式、缺少 active plan 与无效计划均不改变现有正式路线。

Revision 在干净候选成功路径中不必强制发生，但完整计划和 Engine 的
`candidate-revision`、fresh review 状态已做节点绑定回归；它不能绕过重新 Review 和
promotion。

## 5. 工程门禁

- Python：711 tests passed，1 skipped；
- Client：48 files、141 tests passed；
- Client production build：passed，桌面静态资源同步验证通过；
- `python -m compileall -q src tests`：passed；
- Prompt Registry：54 assets、89 task prompt IDs、0 errors/warnings；
- Architecture Audit：34 existing file debts、220 existing function debts、0 cycles，
  无新增 violation；
- `git diff --check`：passed。

符号链接测试只因当前 Windows 环境无法创建测试用 symlink 而跳过。

## 6. 回滚

生产行为继续由配置控制：

```json
{
  "orchestration": {
    "enabled": false,
    "mode": "fixed"
  }
}
```

关闭后 Worker 使用原 fixed route。已有计划、授权和审计证据保留但不参与任务执行。

## 7. 后续边界

下一批才允许进入 W6-6 Rolling Horizon。W6-6 应复用本批的：

- verified active-plan loader；
- Engine 正式 task receipt；
- run-scoped task snapshot；
- Context Ledger 与 Mutation Receipt；
- 固定回退和 project fingerprint。

它不得新增第二套任务完成状态、并发正式写回、任意 Agent command/path 或静默自动
激活。
