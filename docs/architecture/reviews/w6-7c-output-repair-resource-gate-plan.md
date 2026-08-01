# W6-7C OutputRepair 与 ResourceGate 只读并发准入（计划）

## 目标

按统一实施方案 §11.9/§15.2 建立 AO-6 的修复与并发准入确定性底座：

1. `OutputRepairRequest`：只修复缺失或结构无效的 expected outputs；
   已通过产物只读；语义不合格不得伪装成格式修复；修复次数有界。
2. `admission_plan`：只读且互不冲突的 `ResourceClaim` 进入并行组；
   任何写声明或排他 barrier 一律串行；复用既有 `claims_conflict`。

## 边界

- 本批不执行 Worker、不修改 sandbox、不持久化、不激活计划。
- 修复后重跑完整 deterministic preflight 属于执行器职责，本批固定契约。
- 并发准入不改变正式 Gate 与写回原子性。

## 交付物

- `runtime/output_repair.py` 与 `orchestration/resource_gate.py`。
- `tests/runtime/test_output_repair.py` 与
  `tests/orchestration/test_resource_gate.py`。

## 验收

- 修复请求拒绝：空任务/包、空 invalid outputs、空 preflight 证据、
  越界 attempt、指向 preserved outputs。
- 并行组只含无写、无 barrier、两两不冲突的只读声明；写者全部串行；
  重复声明/非法并行上限 fail closed。
- Architecture Audit 不新增债务；全量测试通过。
