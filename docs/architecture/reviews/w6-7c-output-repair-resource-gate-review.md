# W6-7C OutputRepair 与 ResourceGate 只读并发准入（审查）

## 结论

**状态：完成。** 本批按
`docs/architecture/reviews/w6-7c-output-repair-resource-gate-plan.md` 实现。

## 实现

- `runtime/output_repair.py`：
  - `OutputRepairRequest` 不可变契约；
  - `repair_request_violations` 拒绝空 task/bundle、空 invalid outputs、
    空 preflight 证据、越界 attempt、指向 preserved outputs；
  - `repair_allowed` 输出原因码。
- `orchestration/resource_gate.py`：
  - `admission_plan` 把无写、无 barrier、两两不冲突的只读声明分入并行组
    （受 `max_parallel_read_tasks` 限制），写者与 barrier 声明全部串行；
  - 重复声明、空声明 ID、非法并行上限 fail closed；
  - 复用 `runtime.resources.claims_conflict`，未引入第二套冲突判定。
- `orchestration/__init__.py` 导出闸门契约。

## 证据

- 定向测试：`tests/runtime/test_output_repair.py`（5）+ 
  `tests/orchestration/test_resource_gate.py`（7）= 12 tests passed。
- Python 全量：788 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check`：passed，无新增债务。

## 边界确认

- 未执行 Worker、未修改 sandbox、未持久化、未激活计划。
- 修复后全量 preflight 与正式 Gate 顺序由执行器保证，本批固定契约。

## 下一批

W6-7 Exit Audit 收口 AO-6。
