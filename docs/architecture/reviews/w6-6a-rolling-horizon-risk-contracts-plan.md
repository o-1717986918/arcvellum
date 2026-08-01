# W6-6A Rolling Horizon 与 SceneRiskProfile 确定性契约底座（计划）

## 目标

W6-6（AO-5 章节级编排）的第一批只建立确定性契约底座，不开放任何生产行为：

1. `RollingHorizonWindow`：章节内场景顺序、当前活动场景、未来 2-4 个深度规划
   场景窗口、基础项目 revision 与 rebase 触发器的不可变契约。
2. `SceneRiskProfile`：由正式风险事实推导机器最低风险等级
   （`compact` / `standard` / `deep`），Planner 只能建议升高、不能降低。

## 边界

- 本批不创建任务、不调用 Worker、不写项目文件、不激活计划、不改变正式
  Engine lifecycle。
- 深度窗口只包含活动场景之后的未来场景（与“只对未来 2-4 个场景做深度
  推演”一致）；章节末尾剩余场景不足时窗口自然缩短，活动场景是最后一个时
  允许空窗口。
- 风险等级只影响推演、分支和审查深度；正式独立 AgentReview 永不豁免。
- 阈值是机器常量，后续配置化必须保留最低等级不可被 Planner 降低的语义。

## 交付物

- `src/literary_engineering_studio/orchestration/rolling_horizon.py`：
  `RollingHorizonWindow`、`build_rolling_horizon`、`rolling_horizon_violations`。
- `src/literary_engineering_studio/orchestration/risk.py`：
  `SceneRiskFacts`、`SceneRiskProfile`、`machine_minimum_risk_level`、
  `effective_risk_level`、`build_scene_risk_profile`、`scene_risk_violations`。
- `tests/orchestration/test_rolling_horizon_risk.py`：确定性单元测试。

## 验收

- 默认深度窗口按 `active_scene_id` 之后的位置截取且不超过 `horizon_size`。
- 重复场景、越界 horizon、非未来深度场景、深度窗口超过 horizon、仍有剩余
  场景却空窗口、空 base revision 均产生确定性 violation。
- 零风险事实为 `compact`；任一 standard 阈值触发 `standard`；任一 deep
  阈值触发 `deep`；Planner 建议不能把等级降到机器最低值以下。
- Architecture Audit 不新增 file/function/cycle 债务；全量 Python 测试通过。

## 后续批次

W6-6B 将把本章规划事实（事件库存、字数预算、节奏与承诺义务）投影为窗口输入，
并接入 shadow 管线；W6-6C 再进入章节级计划编译与模拟。
