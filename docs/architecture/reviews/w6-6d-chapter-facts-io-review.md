# W6-6D 磁盘事实适配器与项目级 shadow 入口（审查）

## 结论

**状态：完成。** 本批按
`docs/architecture/reviews/w6-6d-chapter-facts-io-plan.md` 实现。

## 实现

- `orchestration/chapter_facts_io.py`：
  - `load_chapter_planning_facts` 读取 `scenes/*.yaml`（timeline 排序）、
    `plot/rhythm_plan.json`、`plot/word_budget/word_budget.json` 与
    `plot/chapter_obligations/{chapter_id}.json`；
  - 显式风险字段读取（负数钳制为 0），`climax_weight` 按 tension_curve
    peak 确定性推导；
  - 可选文件缺失返回空默认值；整章无场景抛 `FileNotFoundError`；
    YAML 非法抛 `ValueError`。
- `orchestration/chapter_shadow.py`：
  `evaluate_chapter_plan_shadow_from_project` 加载事实后进入 W6-6C
  shadow 评估，`executed=False`。
- `orchestration/__init__.py` 导出新入口。

## 证据

- 定向测试：`tests/orchestration/test_chapter_facts_io.py`，7 tests
  passed（timeline 排序、预算/义务/节奏/风险映射、缺省回退、错误路径、
  项目级 shadow 集成）。
- Python 全量：756 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check`：passed，无新增债务。

## 边界确认

- 只读正式项目文件；未创建任务、未调用 Worker、未持久化、未激活计划。
- 正式 Engine 任务顺序与 Gate 未改变。

## 下一步

W6-6 Exit Audit 收口 AO-5（见
`docs/architecture/reviews/w6-6-exit-audit.md`）。
