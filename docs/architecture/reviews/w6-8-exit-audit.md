# W6-8 Exit Audit：AO-7 全书重规划与无人值守（契约层收口）

## 范围

W6-8（AO-7）按批次 A/B/C 完成确定性契约底座：

- W6-8A：`ProgressFingerprint`（正式事实 only）+ `no_progress_detected`
  + `ChapterCheckpoint`（双指纹匹配恢复）。
- W6-8B：`recovery_step` 六类失败固定有界阶梯 + `replan_allowed`
  Freedom Budget 限制。
- W6-8C：`CampaignPolicy`/`CampaignState` 无人值守边界（暂停白名单、
  最大步数、checkpoint 间隔、fail-closed）。

## 需求对照

| AO-7 要求 | 证据 |
| --- | --- |
| Progress Fingerprint（不接受 Agent 自报） | W6-8A：正式产物/任务/gate/字数/义务/review 绑定 → SHA-256 |
| no-progress fallback（连续两轮无正式增量暂停） | W6-8A `no_progress_detected`；W6-8B no-progress 阶梯 1 次 replan → stop |
| checkpoint（安全状态恢复） | W6-8A `ChapterCheckpoint` + `checkpoint_matches` 双指纹验证 + ISO 排序 |
| 恢复阶梯（provider/crash/授权/版本冲突） | W6-8B 六类失败固定阶梯，未知失败 fail closed |
| bounded replan | W6-8B `replan_allowed`（预算耗尽/用户方向限制） |
| 无人值守安全推进与诚实停止 | W6-8C 暂停白名单、最大自主步数、未处理原因 fail closed |

## 边界确认

- 未创建任务、未调用 Worker、未持久化、未激活计划；正式 Gate 与写回
  原子性未改变。
- Campaign 执行器（恢复接线、长跑循环、通知、provider failover 集成）
  属后续执行器批次，不冒充生产无人值守已开放。

## 证据汇总

- 定向测试：W6-8A 9 + W6-8B 11 + W6-8C 7 = 27 tests passed。
- Python 全量：815 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check` 全部通过，无新增架构债务。
- 分支/PR：W6-8A `feat/v097-progress-checkpoint`（PR #13）、
  W6-8B `feat/v097-recovery-replan`（PR #14）、
  W6-8C `feat/v097-campaign`（PR #15），均待审批合入。

## 结论

AO-7 契约层满足本批退出门禁。无人值守生产执行与恢复接线列为 W6-10
生产硬化前的执行器批次，不冒充已完成。
