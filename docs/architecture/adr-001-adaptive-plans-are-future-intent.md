# ADR-001: 自适应计划属于 Future Intent

状态：Accepted

日期：2026-07-26

## 决策

ArcVellum 的 `CreativeExecutionPlan` 属于 **Future Intent**，不是 Canon、人物当前
状态、历史正文或任务完成事实。

Studio 可以让 Agent 提议创作目标、任务依赖、推演深度、分支数量、修订策略和回退
路径；机器负责归一化、注入不可删除的 Gate、编译为现有正式任务、检查资源冲突并
记录版本。Agent 不能通过计划直接写入正式项目事实。

## 不变量

1. Engine 的 `task-next -> task-open -> task-submit -> task-complete` 仍是唯一正式任务
   生命周期。
2. Studio `orchestration/` 不建立第二套任务完成状态，也不直接调用 route 实现。
3. 计划节点只映射到 Engine 的只读 task/gate catalog，不包含任意命令或任意文件路径。
4. Canon、人物状态、正式正文、promotion、export 和 release 继续由原 Gate 与事务拥有。
5. 自适应功能默认关闭；`fixed` 模式与当前 Autopilot route 顺序完全等价。
6. 计划变更形成新 revision 和 provenance，不能改写历史计划。
7. 计划、分析和模拟不计为作品正式进度。

## 模块边界

- Engine `orchestration/`：只读 task catalog、gate catalog、route macro 和兼容性验证。
- Studio `orchestration/`：计划候选、宪法、Lint、Compiler、Simulator、Scheduler 和安全
  投影。
- Studio `automation/`：继续拥有 Autopilot 运行、授权、恢复与 no-progress。
- Studio `runtime/`：继续拥有 Worker、sandbox、Capability Broker、ResourceClaim 和
  writeback。
- Project files：保存可移植计划审计；SQLite 保存运行索引、事件、租约和恢复状态。

## 迁移策略

旧 `tasking/orchestration.py` 实际生成外部平台静态蓝图，迁入
`platforms/orchestration_blueprint.py`。旧 import 保留一个兼容周期，但新编排代码不得
依赖该 facade。

AO-0 到 AO-2 只运行 `fixed` 或 `shadow`，不得改变任务领取顺序。默认计划等价性、
Plan Lint、Compiler 和 Simulator 未通过前，不开放 assisted/adaptive 模式。

## 后果

这项决策牺牲了“让 Agent 任意安排所有操作”的表面自由，换取计划可解释、可回滚、
可验证和不污染作品事实。创意策略可以自适应，正式写入权仍受文学工程宪法约束。
