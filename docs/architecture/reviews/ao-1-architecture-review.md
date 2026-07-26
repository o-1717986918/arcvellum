# AO-1 架构审查：计划合同与默认等价

## 结论

AO-1 把 Agent 候选与机器正式计划分离，并以空节点 fixed macro 保留现有动态 Task
Registry。合同没有复制 route logic，也没有赋予计划正式写回权。

## 1. 模块变化

- 新增 `contracts.py`、`candidate.py`、`constitution.py`、`defaults.py`。
- 新增 candidate/formal plan JSON Schema 与 constitution YAML。
- 没有接入 Runtime、Worker、API、SQLite 或项目文件。

## 2. 依赖图变化

Studio 合同只依赖 Engine `PlanNodeKind`；DefaultPlanFactory 只读取 Engine route macro。
Engine 不反向依赖 Studio DTO。

## 3. 公共合同变化

- Candidate 与正式 plan 两套 schema。
- scope、RP 深度、revision policy、replan trigger、Freedom Budget、Progress Contract。
- 11 条 machine-owned orchestration constitution。
- 默认计划 factory 和 deterministic plan ID。

## 4. 重复职责检查

DefaultPlanFactory 使用空 `task_nodes`，没有静态复制当前 task-next 步骤。Future Intent、
Canon、当前人物状态、历史正文和 task lifecycle 继续分区。

## 5. Facade

AO-1 未增加 facade。

## 6. 文件与函数预算

合同按 candidate parsing、constitution、default factory 分离；均低于架构软上限。
枚举使用 Python 3.10 兼容的 `str, Enum`。

## 7. Feature-off 路径

合同存在不会触发编排。feature 关闭仍只由 fixed Autopilot 路线推进。

## 8. 固定路线兼容

默认计划 route sequence 与 Engine macro/Autopilot 顺序相同；Freedom Budget 禁止新增任务
和重规划，分支上限与策略分支数均为 1。

## 9. 确定性审计

- Commit：`95437ce`。
- Candidate 伪造机器字段会被剥离并留下 warning。
- 任意顶层 command/path 字段被拒绝。
- Schema、enum、constitution ID 和默认等价测试通过。
- Architecture Audit：无新增债务或循环依赖。

## 10. 后续债务

- 参数内部的命令/path 侧信道需由 AO-2 parameter schema 再次封闭。
- 正式计划只有在 Lint、Compiler、Simulator、review 和 activation 后才可执行。
- Plan Patch 与重规划合同属于 AO-5。

## Reviewer

实现者复核：合同所有权单一，无 blocker。

独立 reviewer：与 AO-0/AO-2 合并复核；跨项目 plan identity 问题已修复，合同所有权与
默认等价边界通过，无剩余 P0/P1。
