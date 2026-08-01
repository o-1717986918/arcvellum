# W6-6 Exit Audit：AO-5 章节级编排收口

## 范围

W6-6（AO-5 章节级编排）按批次 A/B/C/D 完成：

- W6-6A：`RollingHorizonWindow`、`SceneRiskProfile` 与机器最低风险等级。
- W6-6B：`ChapterPlanningFacts` / `ScenePlanningFact` 与 measure-only
  shadow 投影。
- W6-6C：`ChapterWindowPolicy`、候选参数投影与完整 shadow
  编译/模拟。
- W6-6D：磁盘事实适配器与项目级 shadow 入口。

## 需求对照

| W6-6 要求 | 证据 |
| --- | --- |
| Rolling Horizon（章节级 2-4 深度窗口） | W6-6A/B/C：窗口生成、校验与候选投影；定向测试覆盖默认窗口、章节末尾收缩、空窗口与 violation 矩阵 |
| SceneRiskProfile（机器最低等级，Planner 只升不降） | W6-6A：阈值表 + `effective_risk_level`；W6-6C 编译后 `roleplay_depth` 断言 |
| 事件库存（场景顺序） | W6-6B 事实契约；W6-6D 按 `timeline_order` 确定性加载 |
| 字数/节奏/承诺义务投影 | W6-6B 事实字段；W6-6D 从字数预算、节奏计划与章节义务文件映射 |
| shadow 验证（measure-only） | W6-6C/D：`executed=False`，复用 Normalize→Lint→Compile→Simulate，失败 fail closed |

## 边界确认

- 未创建任务、未调用 Worker、未持久化、未激活计划。
- 未改变正式 Engine 任务顺序、Gate、promotion、state 或 canon 写回。
- 风险等级只影响推演/分支/审查深度；正式独立 AgentReview 永不豁免。
- 生产默认仍为 fixed 路线；AO-5 仅提供确定性契约与 shadow 投影。

## 证据汇总

- 定向测试：W6-6A 24 + W6-6B 9 + W6-6C 4 + W6-6D 7 = 44 tests passed。
- Python 全量：756 tests passed，1 skipped。
- `compileall`、Architecture Audit（34 file / 220 function debt、0 cycle）、
  `git diff --check` 全部通过，无新增架构债务。
- 分支/PR：W6-6A `feat/v097-rolling-horizon-risk`（PR #5）、
  W6-6B `feat/v097-chapter-horizon-shadow`（PR #6）、
  W6-6C `feat/v097-chapter-plan-shadow`（PR #7）、
  W6-6D `feat/v097-chapter-facts-io`（PR #8），均待审批合入。

## 结论

AO-5 确定性底座与 shadow 验证已满足本批退出门禁。W6-6 不声称
production activation：Scheduler、Execution Bundle、并发与 Campaign
仍属于 W6-7 及之后批次。
