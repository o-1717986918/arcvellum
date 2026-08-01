# W6-6B 章节规划事实投影与 shadow 验证（计划）

## 目标

在 W6-6A 契约之上，把章节级规划事实确定性投影为 AO-5 可消费的窗口与风险画像：

1. `ChapterPlanningFacts` / `ScenePlanningFact`：场景库存顺序、字数目标、
   节奏契约 hash、承诺义务 ID 与确定性风险信号。
2. `project_chapter_horizon`：从事实生成 `RollingHorizonWindow` 与全部规划
   场景的 `SceneRiskProfile`。
3. `evaluate_chapter_horizon_shadow`：measure-only shadow 入口，只计算与
   计时，不执行、不持久化、不激活。

## 边界

- 本批不读文件系统：磁盘事实装配由后续 W6-6C 适配器负责。
- 本批不创建任务、不调用 Worker、不写项目事实、不改变正式 Engine lifecycle。
- 风险画像覆盖章节全部规划场景，深度窗口只影响推演/分支规划范围。
- 事实非法（重复场景、负数风险特征、空库存）时 fail closed，不产出窗口。

## 交付物

- `orchestration/chapter_facts.py`：事实 DTO 与结构校验。
- `orchestration/chapter_horizon.py`：投影、聚合 violation 与 shadow 评估。
- `tests/orchestration/test_chapter_horizon_shadow.py`：确定性测试。

## 验收

- 窗口深度顺序与事实库存一致，默认 2-4 深度窗口只含活动场景之后场景。
- 每个规划场景都有风险画像，机器最低等级不能被 Planner 建议降低。
- 非法事实、越界活动场景、缺失 base revision 均产生 violation 且无窗口。
- shadow 评估 `executed=False`，与直接投影结果一致。
- Architecture Audit 不新增债务；全量 Python 测试通过。
