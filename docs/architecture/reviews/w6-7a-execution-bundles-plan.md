# W6-7A Execution Bundle 契约与白名单编译器（计划）

## 目标

按统一实施方案 §11.6 建立 AO-6 的 Execution Bundle 确定性底座：

1. `ExecutionBundle` 不可变契约（bundle/plan/template/scope/step 节点/角色/
   产物/base revision/上下文快照/原子写回组/stop 边界）。
2. `BundleTemplate` 白名单目录（chapter-planning、scene-analysis、
   scene-authoring、scene-quality、scene-state-extraction）。
3. `compile_bundles`：从 `CompiledTaskGraph` 按模板与 scope 确定性编译，
   每 Bundle 只含白名单节点且单一 Agent 角色。

## 边界

- Bundle 是编译节点上的受控优化，不是第二套 task lifecycle。
- 本批不创建任务、不调用 Worker、不持久化、不激活计划。
- Writer（main-creative-agent）与 Reviewer（main-review-agent）永不混入
  同一 Bundle；scene-authoring 只含主创正文节点。
- stop 边界是机器元数据；执行期遇到人类决策/版本变化/写回/高风险 Gate
  仍必须切断（后续执行器负责）。

## 交付物

- `orchestration/bundles.py`：模板目录、编译器与 violation。
- `tests/orchestration/test_execution_bundles.py`：确定性测试。

## 验收

- scene-analysis 合并 RP 与分支节点；scene-authoring 只含正文节点；
  scene-quality 只含审查节点；scene-state-extraction 只含状态候选节点。
- Bundle ID 稳定；结构 violation 覆盖空节点/缺角色/缺 revision/缺写回组/
  缺 stop 边界。
- 未授权模板拒绝；Architecture Audit 不新增债务；全量测试通过。
