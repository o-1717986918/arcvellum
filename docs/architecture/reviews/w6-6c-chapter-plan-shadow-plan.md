# W6-6C 章节计划 shadow 编译与模拟（计划）

## 目标

把 W6-6A/B 的窗口与风险画像投影到章节级计划候选，并接入既有 AO-2
measure-only 管线：

1. `ChapterWindowPolicy`：窗口身份、深度场景、每场景风险等级与全局分支数。
2. `project_chapter_candidate_parameters`：把风险等级映射为
   `roleplay_depth`（compact→light、standard→targeted、deep→full）与
   分支数（2/3/5），同时同步 `strategy.scene_inventory`，保持
   W6-5A 的策略绑定不变式。
3. `evaluate_chapter_plan_shadow`：投影后复用 Normalize→Lint→Compile→
   Simulate，不执行、不持久化、不激活。

## 边界

- 本批不创建任务、不调用 Worker、不写项目事实、不改变正式 Engine lifecycle。
- 分支数为章节全局值（保证 `scene_strategy_violations` 不变式）；深度按场景
  独立投影。
- 风险画像只提高推演/分支/审查深度，正式独立 AgentReview 永不豁免。
- 非法事实或窗口投影失败时 fail closed，不进入 AO-2 管线。

## 交付物

- `orchestration/chapter_binding.py`：窗口策略与候选参数投影。
- `orchestration/chapter_shadow.py`：章节计划 shadow 评估。
- `tests/orchestration/test_chapter_plan_shadow.py`：确定性测试。

## 验收

- 深风险场景编译后 `roleplay_depth=full`、分支数按章节策略生效；
  紧凑场景保持 `light`。
- 候选 `strategy.scene_inventory` 与节点参数一致，通过现有 Plan Lint。
- shadow 评估 `executed=False`，通过既有 Normalize/Lint/Compile/Simulate。
- 非法事实不进入管线并返回机器可读 violation。
- Architecture Audit 不新增债务；全量 Python 测试通过。
