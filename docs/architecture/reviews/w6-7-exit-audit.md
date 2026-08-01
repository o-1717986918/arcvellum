# W6-7 Exit Audit：AO-6 资源锁与有限并发（契约与准入层）

## 范围

W6-7（AO-6）按批次 A/B/C 完成确定性契约与准入底座：

- W6-7A：`ExecutionBundle` + 五个白名单模板编译器（单角色隔离）。
- W6-7B：`ContextCacheKey` 精确失效 + `SessionLease` 复用决策。
- W6-7C：`OutputRepairRequest` 有界修复 + `admission_plan` 只读并发准入。

## 需求对照

| AO-6 要求 | 证据 |
| --- | --- |
| Execution Bundle（白名单模板、单角色、stop 边界、不创建第二套 lifecycle） | W6-7A：五个模板、编译图→Bundle、结构 violation、稳定 bundle_id |
| 上下文缓存（依赖 hash 失效） | W6-7B：`ContextCacheKey` 十字段身份 + `partition_reusable` 精确失效 |
| 局部修复（只修缺失/结构无效、已通过产物只读、次数有界） | W6-7C：`OutputRepairRequest` + `repair_request_violations`/`repair_allowed` |
| session lease（角色/项目/模型/文风/Ledger/预算复用条件） | W6-7B：`SessionLease` + `session_reusable` 九类原因 |
| Resource Gate / 只读并发（冲突任务必定串行） | W6-7C：`admission_plan` 只读并行组 + 写者/barrier 串行，复用 `claims_conflict` |

## 边界确认

- 未创建任务、未调用 Worker、未持久化、未激活计划；正式 Gate 与写回原子性
  未改变。
- 本批是契约与准入层；按统一实施方案 §11.12 分阶段启用，生产默认仍为
  fixed 路线。Bundle 执行器、缓存存储、session pool 与并行审查调度属于
  后续执行器接线，不得据此声称生产并发已开放。

## 证据汇总

- 定向测试：W6-7A 10 + W6-7B 10 + W6-7C 12 = 32 tests passed。
- Python 全量：788 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check` 全部通过，无新增架构债务。
- 分支/PR：W6-7A `feat/v097-execution-bundles`（PR #9）、
  W6-7B `feat/v097-context-cache-session-lease`（PR #10）、
  W6-7C `feat/v097-output-repair-resource-gate`（PR #11），均待审批合入。

## 结论

AO-6 契约与准入层满足本批退出门禁。生产并发执行、Bundle 执行器与缓存
存储接线列为 W6-10 生产硬化前的执行器批次，不冒充已完成。
