# AO-0 架构审查：编排命名与所有权边界

## 结论

AO-0 建立的是只读协议边界，不是新的执行框架。旧外部平台蓝图、新自适应计划域和正式
Engine lifecycle 已有清晰所有权，feature-off 路径未变化。

## 1. 模块变化

- 旧静态平台蓝图实现迁至
  `literary_engineering_studio_engine/platforms/orchestration_blueprint.py`。
- 旧根模块和 `tasking/orchestration.py` 保留兼容 facade。
- 新增 Engine `orchestration/`：Gate Catalog、Task Catalog、route macro 和默认等价检查。
- 新增 Studio `orchestration/settings.py`，只解析模式与 feature flag。

没有删除正式 route、Task Registry、AgentWorker 或 Autopilot 模块。

## 2. 依赖图变化

依赖方向为：

```text
Studio orchestration -> Engine orchestration catalogs
Engine orchestration catalogs -> Engine constants only
Engine orchestration -X-> Studio / Runtime / API
```

旧 platform blueprint 不被新运行域 import。

## 3. 公共合同变化

- 新增 `PlanNodeKind`、`GateId`、`FormalTaskCapability`、`RouteMacro`。
- 新增稳定 macro `fixed-formal-route.v1`。
- 配置新增 `orchestration.enabled/mode/strategy_preset`，默认关闭。
- 未新增数据库表、API endpoint 或运行事件。

## 4. 重复职责检查

未发现第二套 Gate 或 task lifecycle。Gate Catalog 只给计划域提供稳定 ID；实际 Gate
实现仍由 Engine route 和 preflight 拥有。

## 5. Facade

兼容 facade 仅用于旧 orchestration blueprint import。删除条件是所有外部调用方迁至
`platforms/orchestration_blueprint.py`；它不属于自适应运行时依赖。

## 6. 文件与函数预算

新增目录文件均低于 400 行软上限；无新复杂函数债务。目录按协议职责拆分，没有把目录、
设置和兼容 facade 合成单文件。

## 7. Feature-off 路径

配置未启用时 `effective_mode` 无条件为 `fixed`。测试覆盖“配置残留 full_adaptive 但
feature 关闭”的情况。

## 8. 固定路线兼容

`DEFAULT_ROUTE_ORDER` 与现有 `AutopilotService.ROUTE_ORDER` 由测试锁定。AO-0 不接
Autopilot，不改变 task-next。

## 9. 确定性审计

- Commit：`34848a1`。
- Architecture Audit：无新增 file/function debt，0 cycle。
- 编排基础、配置、Autopilot 与兼容 import 测试通过。

## 10. 后续债务

- facade 删除版本尚未确定，进入 v1.0 前应列出外部 import 使用者。
- Engine Catalog 目前只描述能力，不证明所有未来 binding 能在任意 formal state 获得；
  该责任属于 AO-2 Simulator 与后续 Scheduler。

## Reviewer

实现者复核：边界成立，无 blocker。

独立 reviewer：与 AO-1/AO-2 合并复核；feature-off、目录所有权和固定路线边界均通过，
无 P0/P1。
