# W6-6B 章节规划事实投影与 shadow 验证（审查）

## 结论

**状态：完成。** 本批按
`docs/architecture/reviews/w6-6b-chapter-horizon-shadow-plan.md` 实现。

## 实现

- `orchestration/chapter_facts.py`：
  - `ScenePlanningFact`（场景引用、字数目标、功能/节奏、七个风险信号、义务）；
  - `ChapterPlanningFacts`（章节 ID、有序场景、章节字数、节奏 hash、承诺义务、
    base revision）；
  - `chapter_facts_violations` 拒绝空章节/空库存、重复场景、空场景引用、
    负数或非整数风险特征与字数。
- `orchestration/chapter_horizon.py`：
  - `project_chapter_horizon` 把事实投影为 `RollingHorizonWindow` +
    全部场景的 `SceneRiskProfile`；结构性错误 fail closed；
  - `ChapterHorizonProjection.passed` 只在窗口存在且无 violation 时为真；
  - `evaluate_chapter_horizon_shadow` 返回 measure-only 评估
    （`executed=False` 与毫秒耗时），不执行、不持久化、不激活。
- `orchestration/__init__.py` 导出新契约。

## 证据

- 定向测试：`tests/orchestration/test_chapter_horizon_shadow.py`，9 tests
  passed（窗口投影、全场景风险画像、只升不降、fail-closed 矩阵、shadow
  等值）。
- Python 全量：745 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check`：passed，无新增债务。

## 边界确认

- 未读文件系统；未创建任务、未调用 Worker、未持久化、未激活计划。
- 风险画像覆盖全部规划场景；正式独立 AgentReview 永不豁免。

## 下一批

W6-6C：磁盘事实适配器（字数预算、节奏、承诺义务读取）接入
`project_chapter_horizon`，并把章节级窗口/风险画像接入 shadow 管线与
章节计划编译/模拟。
