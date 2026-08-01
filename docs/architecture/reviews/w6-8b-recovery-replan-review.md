# W6-8B 恢复阶梯与 bounded replan 契约（审查）

## 结论

**状态：完成。** 本批按
`docs/architecture/reviews/w6-8b-recovery-replan-plan.md` 实现。

## 实现

- `orchestration/recovery.py`：
  - `RecoveryStep` 枚举（retry/session-renew/checkpoint-restore/
    bounded-replan/stop-with-evidence）；
  - `_LADDER` 固定映射：provider 1-2 retry→3 renew→4+ stop；crash 与
    version 1 restore→2 replan→3+ stop；authorization 1 renew→2+ stop；
    no-progress 1 replan→2+ stop；budget 直接 stop；
  - `recovery_step`/`recovery_violations` 对未知失败与非法 attempt
    fail closed。
- `orchestration/replan.py`：
  - `ReplanBudgetState`（scope/replan_count/max_replans）；
  - `replan_allowed` 预算耗尽与用户方向二次重规划拒绝；
  - `replan_budget_violations` 拒绝空 scope、负计数与非正上限。
- `orchestration/__init__.py` 导出。

## 证据

- 定向测试：`tests/orchestration/test_recovery_replan.py`，11 tests
  passed（六类失败阶梯、fail-closed、预算边界、violation 矩阵）。
- Python 全量：808 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check`：passed，无新增债务。

## 边界确认

- 未创建任务、未调用 Worker、未持久化、未激活计划；阶梯只输出决策。

## 下一批

W6-8C：无人值守 Campaign 契约与 W6-8 Exit Audit。
