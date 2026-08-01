# W6-6A Rolling Horizon 与 SceneRiskProfile 确定性契约底座（审查）

## 结论

**状态：完成。** 本批按
`docs/architecture/reviews/w6-6a-rolling-horizon-risk-contracts-plan.md`
实现，未越过 AO-5 边界。

## 实现

- `orchestration/rolling_horizon.py`：
  - `RollingHorizonWindow` 不可变契约，含 `chapter_id`、`planned_scene_ids`、
    `deep_scene_ids`、`active_scene_id`、`horizon_size`、`base_project_revision`
    与 `rebase_after`；
  - `build_rolling_horizon` 确定性生成窗口：深度窗口为活动场景之后最多
    `horizon_size`（2-4）个场景；显式 `deep_scene_ids` 可覆盖默认选择；
  - `rolling_horizon_violations` 覆盖重复场景、horizon 越界、缺失 base
    revision、活动场景不在计划内、深度场景未规划/不属未来/超窗口/剩余场景
    却空窗口。
- `orchestration/risk.py`：
  - `SceneRiskFacts` 与 `SceneRiskProfile` 不可变契约；
  - `machine_minimum_risk_level` 依据机器阈值表推导最低等级；
  - `effective_risk_level` 保证 Planner 建议只能升高不能降低；
  - `build_scene_risk_profile` 保留机器最低等级并记录触发原因；
  - `scene_risk_violations` 拒绝空 `scene_id` 与负数风险特征。
- `orchestration/__init__.py` 导出全部新契约。

## 证据

- 定向测试：`tests/orchestration/test_rolling_horizon_risk.py`，24 tests
  passed（窗口选择、边界、violation 矩阵、风险阈值、只升不降）。
- Python 全量：736 tests passed，1 skipped。
- `python -m compileall -q src`：passed。
- `python scripts/architecture_audit.py`：passed，34 file debts、
  220 function debts、0 cycles，与基线持平，无新增债务。
- `git diff --check` 与 `scripts/verify_version_sync.py`：passed。

## 边界确认

- 本批未创建任务、未调用 Worker、未持久化、未激活计划，不改变正式任务顺序。
- 深度窗口语义与 AO-5 “只对未来 2-4 个场景做深度推演”一致。
- 风险等级不豁免正式独立 AgentReview。

## 下一批

W6-6B：把本章规划事实（事件库存、字数预算、节奏与承诺义务）投影为窗口输入，
并接入 shadow 管线。
