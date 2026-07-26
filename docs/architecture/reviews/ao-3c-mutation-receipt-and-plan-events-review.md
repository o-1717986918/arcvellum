# AO-3C Mutation Receipt 与 Typed Plan Events 架构评审

## 1. 评审范围

本评审覆盖 W6-4C：

- Worker 候选、确定性预检、写回预览、应用、回滚和晋升事实；
- task/run/session/plan/context ledger 的回执绑定；
- SQLite schema 14 的 Mutation Receipt 索引；
- Creative Plan Event 的固定枚举、Schema 和 display-only 边界；
- Worker 写回模块拆分后的依赖方向、失败恢复与兼容性。

不覆盖 Planner/Reviewer 真实会话服务、AO-4 场景级自适应执行、并发 Scheduler 或前端
receipt 时间线；这些分别属于 W6-4D、W6-5、W6-7 与 W6-9。

## 2. 关键结论

### 2.1 正式写回所有权没有迁移

Mutation Receipt 是既有事务的证据，不是新事务：

1. Sandbox 仍负责 expected-output-only 视图、preview digest、备份和逐目标原子替换。
2. Worker 仍通过 Engine `task-submit` / `task-complete` 接受正式 Gate。
3. Core Gate 失败时仍先恢复文件，再调用 `task-revert-submission`。
4. Receipt recorder 只能观察上述结果，不能批准、应用或晋升任何文件。

因此 Studio 未建立第二套 promotion、state、canon 或 release 写回系统。

### 2.2 Agent 不能伪造 Worker Receipt

- 回执只写入 `run_root/mutation-receipts.jsonl`；
- 该路径不在 Agent workspace、task source、expected outputs 或正式项目内；
- `authority` 固定为 `studio-machine`；
- receipt ID 由 change group、task、run、session、action、target、digest 和状态计算；
- parser 同时验证 receipt ID 与完整 body digest；
- rollback 结构在 DTO 层强制 `formal_effect=none`。

Archive owner transaction 已使用 `arcvellum/mutation-receipt/v1`。为避免一个 `$id`
对应两种不兼容结构，Worker 使用独立
`arcvellum/worker-mutation-receipt/v1`，概念统一但协议不碰撞。

### 2.3 三阶段事实链

每个有输出的 Worker task 至少形成：

- `candidate_created` / `candidate_modified`：记录正式目标与 control candidate digest；
- `writeback_previewed`：记录确定性 preflight=pass 和 preview 前后 digest；
- `writeback_applied` 或 `writeback_rolled_back`：记录最终事务效果。

预检失败额外形成 `preflight_rejected`。promotion task 在 Engine Gate 通过后形成
`formal_promoted`。非 promotion 输出标为 candidate effect；rollback 永远没有正式效果。

OpenCode repair loop、其他 Runtime、deterministic CLI 和 recovery 统一调用同一个
`_validate_outputs`，不会因适配器不同而缺少预检证据。

### 2.4 计划事件不能再自由命名

`CreativePlanEventType` 是唯一事件词表。持久化入口会在 SQL 前拒绝未知事件；
`plan.candidate.delta` 只能向实时观察面展示，不能写入 durable event ledger。

模型流式文本只有被机器封装为 `plan.candidate.completed` 后，才能由
`completed_candidate_from_event` 交给 Normalize/Lint。当前 AO-2 固定/测试调用仍可直接
使用静态候选；W6-4D 的 Planner Service 必须使用 completed-event 入口。

## 3. 模块边界

```text
observability/mutation_receipts.py
  immutable DTO, enum, digest, parser

observability/change_groups.py
  stable run/task grouping and read projection

runtime/mutation_tracking.py
  run-root recorder and Worker transaction observation

runtime/worker_writeback.py
  preflight, preview, approval, apply, core gate, rollback

persistence/mutation_receipts.py
  metadata/query index only

orchestration/plan_events.py
  typed event and completed-candidate boundary

persistence/creative_plan_events.py
  durable enum-validated events only
```

`worker.py` 不再承载写回全生命周期；结果 DTO、run manifest 与路径验证也拆入独立模块。
这次拆分没有引入 facade duplication 或反向依赖。

## 4. 持久化与查询

SQLite schema 14 新增：

- `mutation_receipts`；
- task/run/session/plan/change-group 查询索引；
- `creative_plan_events.session_id`。

API Worker 经 `track_agent_session_event` 的统一可观测入口写 receipt；Autopilot 复用同一
入口；用户批准/拒绝写回的 API 恢复路径直接调用 receipt tracker。CLI 直跑没有 Studio
数据库时仍保留 run-root JSONL，不丢失便携证据。

数据库是可重建索引，不拥有正式作品。数据库迁移沿用现有 backup 机制。

## 5. 失败语义

- Agent 候选不满足确定性预检：不生成 preview，不触碰正式项目。
- preview 后项目 base digest 改变：既有 stale check 拒绝 apply。
- 多文件导入中途失败：既有 backup index 恢复已导入目标。
- Engine submit/complete 失败：恢复全部 expected outputs，撤销 submission evidence，
  写 rollback receipt。
- Receipt persistence 失败：API/Autopilot event 汇聚失败并暴露，不静默声称已审计。
- 重试同一阶段：receipt ID 去重；候选 digest 变化则形成新 receipt。

## 6. 架构质量

W6-4C 未扩大 Architecture Audit baseline：

- `worker.py`：677 行降至 334 行；
- Architecture Audit：35 个既有 file debt、224 个既有 function debt、0 cycle；
- 新模块按 runtime / observability / persistence / orchestration 归属；
- Archive owner receipt 与 Worker receipt 使用不同协议 ID；
- `.tmp/` 未纳入版本控制。

## 7. 后续约束

W6-4D 必须：

1. Planner delta 只走实时 event，不写 SQLite；
2. 完整候选必须先形成 `plan.candidate.completed`；
3. Reviewer 使用独立 session；
4. Planner/Reviewer 只能写 orchestration audit 目录；
5. 只有 Plan Lint、Simulation、independent Review 均通过的 revision 才能进入现有
   activation transaction；
6. feature-off、stale context 或任一 Agent 失败必须回退 fixed route。
