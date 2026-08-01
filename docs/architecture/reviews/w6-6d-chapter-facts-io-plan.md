# W6-6D 磁盘事实适配器与项目级 shadow 入口（计划）

## 目标

把 W6-6B 的纯事实契约接到正式项目磁盘：

1. `load_chapter_planning_facts`：从场景 YAML、节奏计划、字数预算与章节义务
   文件加载 `ChapterPlanningFacts`。
2. `evaluate_chapter_plan_shadow_from_project`：加载项目事实后直接进入
   W6-6C shadow 评估。

## 读取映射（确定性）

- 场景顺序：`scenes/*.yaml` 中 `chapter_id` 匹配，按 `time.timeline_order`
   （缺省按文件名）排序。
- 字数目标：场景 YAML `word_count_target` → 节奏条目 → 章节预算
   `avg_scene_words`。
- 风险信号：场景 YAML 显式 `canon_change` 等七个字段（负数钳制为 0）；
   `climax_weight` 缺省按 `narrative_rhythm.tension_curve.peak`
   （≥5 → 4，=4 → 2，否则 0）。
- 功能/节奏：节奏计划条目 `scene_function` / `pace`。
- 承诺义务：章节义务 JSON `obligation_ids` / `promise_ids` /
   `contract.obligations`（支持 `{id}` 与字符串）。
- 节奏 hash：`plot/rhythm_plan.json` 的 `digest`。

## 边界

- 只读正式文件；不创建任务、不写项目事实、不激活计划。
- 可选文件缺失时使用空默认值；整章无场景抛 `FileNotFoundError`；
   YAML 非法抛 `ValueError`。

## 验收

- 两场景项目按 timeline 排序加载，字数/节奏/义务/风险信号正确。
- 缺 plot 目录时事实仍有效且无 violation。
- 项目级 shadow 入口通过既有 Normalize→Lint→Compile→Simulate。
- Architecture Audit 不新增债务；全量 Python 测试通过。
