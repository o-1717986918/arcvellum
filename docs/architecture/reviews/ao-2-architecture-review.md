# AO-2 架构审查：Lint、Compiler、Simulator 与 Shadow

## 结论

AO-2 已完成两轮独立审查整改并正式关闭。当前代码没有接入 Autopilot 或 Worker，仍是
shadow-only；Compiler、Simulator 和持久化审计不会改变正式任务顺序。

## 1. 模块变化

- 确定性域：`normalizer.py`、`budget_policy.py`、`lint.py`、
  `literary_policy.py`、`writer_policy.py`。
- 编译域：`compiler_registry.py`、`compiler.py`、compiled graph schema。
- 模拟域：`simulator.py`、`shadow.py`。
- 审计协调：`orchestration/persistence.py`、`audit_integrity.py`。
- SQLite：`creative_plans.py`、`creative_plan_events.py`、
  `creative_plan_activation.py`、`creative_plan_primitives.py`，schema 12。

## 2. 依赖图变化

```text
Candidate -> Normalizer -> Lint -> Compiler -> Simulator
                         Engine Catalog     Runtime ResourceClaim
Project audit writer -> immutable results -> CreativePlan index
```

Compiler 不 import JobStore；Simulator 不 import persistence；SQLite 不 import API、Runtime
或前端。`orchestration/persistence.py` 只通过 Protocol 使用索引。

## 3. 公共合同变化

- `TaskBinding`、`CompiledTaskNode`、`CompiledTaskGraph`。
- `FormalTaskObservation`、`PlanSimulationContext/Result`。
- `OrchestrationAuditArtifacts`、Shadow timing/result。
- 新增 creative plan 三张表、append-only plan events 和 schema 12。
- 未新增 API、CLI 命令或 Autopilot execution source。

## 4. 重复职责检查

- Compiler 只绑定正式 task type，不签发 task。
- Simulator 只消费调用方提供的 observation/claim，不搜索项目。
- Gate 仍由 Engine Catalog 注入，Compiler 不重定义。
- SQLite 保存索引摘要；完整 JSON 只在项目审计目录。
- 不保存 plan node 可写运行状态；未来 Scheduler 只能投影 Engine 正式 task receipt。
- activation 只改变计划意图，不执行 task 或写 Canon/正文。

未发现第二套 task lifecycle、formal writeback 或独立资源冲突算法。

## 5. Facade

AO-2 未增加 facade。公共 `orchestration/__init__.py` 是显式 domain export，不含兼容逻辑。

## 6. 文件与函数预算

- `creative_plans.py`、activation、events、shared primitives 按事务职责拆分。
- `lint.py` 将文学链和单 Writer 规则下沉为纯 policy 模块。
- `persistence.py` 与 `audit_integrity.py` 分离 I/O 协调和语义完整性验证。
- Architecture Audit 未增加 400/500 行、60/80 行函数或 complexity 债务。

## 7. Feature-off 路径

没有生产调用方引用 `evaluate_shadow_candidate()`、`compile_plan()` 或
`activate_persisted_revision()`。Autopilot、AgentWorker、task-next 与 route order 未改。

## 8. 固定路线兼容

fixed macro 编译为空 graph nodes，并保留原 route sequence。Compiler Registry 的 route
支持集包含固定 macro route，但不会展开或执行它们。Shadow 不改变正式选择顺序。

## 9. 确定性审计

- Commits：`997d3e7`、`2ebed05`，AO-2C 待提交。
- Plan Lint receipt 绑定 plan digest，Compiler 拒绝 lint 后篡改。
- Compiled graph 使用独立 digest，Simulator 拒绝篡改。
- 动态风险 Gate 在编译结果中保留。
- state/canon/release mutation 注入串行机器边。
- Resource conflict 复用 W5 `claims_conflict()`。
- 计划审计文件逐文件 hash、revision digest 和 provenance 三重验证。
- candidate、normalized plan、Lint receipt、compiled graph、simulation 与 provenance
  额外形成可验证语义链。
- SQLite 在文件写入前 reserve revision digest；不同 digest 冲突不会覆盖文件，原子写入
  失败可从 reserved 状态恢复。
- activation 使用 expected revision、fingerprint、passing lint/simulation/review、
  verified audit digest 和单项目唯一 active 约束；event/SQL 失败恢复文件投影。
- 全量 Python：598 passed，1 skipped。
- Architecture Audit：36 个既有 file debt、226 个既有 function debt、0 cycle。

## 10. 首轮独立审查与整改

独立 reviewer 首轮提出 9 项问题，当前整改如下：

1. revision 文件先写后冲突：改为 SQLite reserve -> atomic write -> ready。
2. `creative_plan_nodes` 形成第二套生命周期：删除，仅保留 append-only plan event。
3. prose/revision 可并行：Plan Lint 对同 scope Writer 强制串行。
4. 默认 plan ID 跨项目碰撞：身份摘要加入 project fingerprint。
5. 审计只有文件 hash：补 candidate/plan/lint/graph/simulation/provenance 语义链。
6. 多 active 与文件/SQLite 竞态：增加单项目唯一索引，在 SQLite 写事务内协调投影并补偿。
7. 空 orchestration settings 解析失败：Enum 默认值改用 `.value`。
8. mixin 依赖 sibling 私有方法：plan event 改为独立事务函数。
9. analysis ratio 仅 warning：改为 hard error。

聚焦测试覆盖 digest 冲突不覆盖、reserved 重试、双 Store 并发激活、activation event
失败回滚和跨产物语义错配。

第二轮复核继续发现 2 个 P1，当前整改如下：

10. 调用方可把 plan 初始状态写为 active，并用便利入口无文件标记 ready：删除便利入口，
    初始状态固定为 shadow，ready 前由 Store 核验六类审计文件存在且 hash 匹配。
11. `connection.commit()` 失败发生在原补偿范围之外：activation 改为显式 transaction，
    在取得 SQLite 写锁后采集文件快照，SQL/event/commit 任一失败均恢复投影并 rollback。

新增故障注入测试覆盖 status/ready 伪造和 commit 失败。独立 reviewer 最终确认两个
P1 均关闭，未发现新 P0/P1，AO-2 可关闭。

## 11. 下一阶段前债务

- AO-3 才建立独立 Planner/Reviewer profile 和 planning Context Broker。
- 当前 `FormalTaskObservation` 必须由未来 formal-state adapter 显式提供，不能由 Simulator
  猜测。
- 进程在文件替换后、SQLite commit 前被操作系统强杀的极小窗口，后续需由恢复扫描核对
  SQLite 与 `active_plan.json`；当前普通异常已补偿。
- 曾运行过未提交 AO-2 草案的 schema 12 开发数据库可能残留
  `creative_plan_nodes`；正式发布前的恢复扫描/迁移需忽略或清理该旧草案表。
- Scheduler 接入后，节点状态必须来自 Engine task receipt，不能回建 Studio-owned
  writable lifecycle。

## Reviewer

实现者复核：两轮 findings 已逐项修复，未发现剩余实现 blocker。

独立 reviewer：AO-2 close = Yes。Bundle Compiler 不是本阶段退出条件，按统一实施方案
留到 AO-6/v0.99。
