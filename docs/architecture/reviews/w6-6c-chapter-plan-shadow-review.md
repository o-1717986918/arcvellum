# W6-6C 章节计划 shadow 编译与模拟（审查）

## 结论

**状态：完成。** 本批按
`docs/architecture/reviews/w6-6c-chapter-plan-shadow-plan.md` 实现。

## 实现

- `orchestration/chapter_binding.py`：
  - `ChapterWindowPolicy`：章节/活动场景/深度窗口/horizon/每场景风险等级/
    全局分支数/rebase 策略，并提供 `as_dict`；
  - `chapter_window_policy` 从窗口与风险画像派生策略；
  - `project_chapter_candidate_parameters` 把风险等级投影到候选
    `roleplay_depth` 与 `branch_count`，并同步 `strategy.scene_inventory`
    保持 W6-5A 策略绑定不变式；无画像节点产生 warning。
- `orchestration/chapter_shadow.py`：
  - `evaluate_chapter_plan_shadow` 先投影窗口/画像，再复用
    `evaluate_shadow_candidate`（Normalize→Lint→Compile→Simulate）；
  - 返回 `ChapterPlanShadowEvaluation`（`executed=False`、耗时与 violations），
    失败事实不进入管线。
- `orchestration/__init__.py` 导出新契约。

## 证据

- 定向测试：`tests/orchestration/test_chapter_plan_shadow.py`，4 tests
  passed（候选参数投影、窗口策略身份、完整 shadow 管线深度投影、
  fail-closed）。
- Python 全量：749 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check`：passed，无新增债务。

## 边界确认

- 未创建任务、未调用 Worker、未持久化、未激活计划。
- 分支数为章节全局值，深度按场景独立投影；正式独立 AgentReview 不豁免。

## 下一批

W6-6 剩余：磁盘事实适配器（字数预算、节奏、承诺义务读取）接入
`ChapterPlanningFacts`，随后 W6-6 Exit Audit 收口 AO-5。
