# W6-8C 无人值守 Campaign 契约（计划）

## 目标

按 W6-8（AO-7）要求建立无人值守运行的安全边界：

1. `CampaignPolicy`：章节/全书 scope、最大自主步数、checkpoint 间隔、
   需暂停的原因白名单。
2. `campaign_step_allowed`：政策边界内才继续；任何 pending 暂停原因
   立即停止；白名单外原因 fail closed。
3. `checkpoint_due`：按间隔触发检查点。

## 边界

- 本批不创建任务、不调用 Worker、不持久化、不激活计划。
- Campaign 执行器（恢复接线、通知、长跑循环）属后续批次；本批固定决策
  契约。

## 交付物

- `orchestration/campaign.py`。
- `tests/orchestration/test_campaign.py`。

## 验收

- 政策内继续；human-decision 等白名单原因暂停；未处理原因 fail closed；
  最大自主步数停止。
- checkpoint 只在正间隔倍数触发。
- 非法 scope/负数/非正上限有 violation。
- Architecture Audit 不新增债务；全量测试通过。
