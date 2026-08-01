# W6-8C 无人值守 Campaign 契约（审查）

## 结论

**状态：完成。** 本批按
`docs/architecture/reviews/w6-8c-campaign-plan.md` 实现。

## 实现

- `orchestration/campaign.py`：
  - `CampaignPauseReason`（human-decision/approval/release-gate/
    no-progress/recovery-exhausted/budget-exhausted/user-direction）；
  - `CampaignPolicy`（scope、最大自主步数、checkpoint 间隔、暂停白名单）；
  - `CampaignState` 与 `campaign_step_allowed`：白名单原因暂停、
    未处理原因 fail closed、最大步数停止；
  - `checkpoint_due` 正间隔倍数触发；
  - `campaign_violations` 拒绝 scope 不匹配、非法 scope kind、负数计数、
    非正上限。
- `orchestration/__init__.py` 导出。

## 证据

- 定向测试：`tests/orchestration/test_campaign.py`，7 tests passed。
- Python 全量：815 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check`：passed，无新增债务。

## 边界确认

- 未创建任务、未调用 Worker、未持久化、未激活计划；执行器接线留后续批次。

## 下一步

W6-8 Exit Audit 收口 AO-7（见 `docs/architecture/reviews/w6-8-exit-audit.md`）。
