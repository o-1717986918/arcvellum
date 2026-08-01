# W6-8B 恢复阶梯与 bounded replan 契约（计划）

## 目标

按统一实施方案 §21.2 与 W6-8（AO-7）要求建立无人值守的故障处理底座：

1. `recovery_step`：六类失败（provider / crash / authorization /
   version / no-progress / budget）映射到固定有界阶梯
   （retry → session-renew → checkpoint-restore → bounded-replan →
   stop-with-evidence），永不无限重试或静默改计划。
2. `replan_allowed`：按 scope 的 Freedom Budget 限制重规划次数，预算
   耗尽后停止或回退。

## 边界

- 本批不创建任务、不调用 Worker、不持久化、不激活计划。
- 阶梯只输出下一步决策；执行由未来 Campaign 执行器负责。

## 交付物

- `orchestration/recovery.py` 与 `orchestration/replan.py`。
- `tests/orchestration/test_recovery_replan.py`。

## 验收

- 每类失败在各级 attempt 的决策确定；未知失败/非法 attempt fail closed。
- no-progress 只允许一次 bounded replan，第二次 stop-with-evidence。
- 重规划预算耗尽与用户方向二次重规划被拒绝；非法预算状态有 violation。
- Architecture Audit 不新增债务；全量测试通过。
