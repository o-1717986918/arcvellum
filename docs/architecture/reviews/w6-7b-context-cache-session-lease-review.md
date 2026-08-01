# W6-7B ContextCacheKey 与 session lease 契约（审查）

## 结论

**状态：完成。** 本批按
`docs/architecture/reviews/w6-7b-context-cache-session-lease-plan.md` 实现。

## 实现

- `runtime/context_cache.py`：
  - `ContextCacheKey` 不可变契约与 `context_cache_key_fingerprint`；
  - `cache_key_violations` 拒绝空身份字段与非法 scope kind；
  - `partition_reusable` 要求十个身份字段完全一致。
- `runtime/session_lease.py`：
  - `SessionRole`（planner/writer/reviewer/state-analyst/advisor-steward）；
  - `SessionLease` 与 `session_reusable` 决策（角色/项目/模型/文风/Ledger
    纪元/完成态/token/时间/失败预算）；
  - `session_lease_violations` 拒绝空 ID 与负数预算。
- `tests/runtime/__init__.py` 补齐子包，保证 `unittest discover` 覆盖。

## 证据

- 定向测试：`tests/runtime/test_context_cache_session_lease.py`，10 tests
  passed（fingerprint 稳定性、失效矩阵、会话复用九类原因、结构 violation）。
- Python 全量：776 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check`：passed，无新增债务。

## 边界确认

- 未读文件系统、未创建任务、未调用 Worker、未持久化、未激活计划。
- Writer/Reviewer 角色隔离由复用决策强制。

## 下一批

W6-7C：OutputRepairRequest 与 ResourceGate 只读并发准入。
