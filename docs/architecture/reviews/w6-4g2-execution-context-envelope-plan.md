# W6-4G2 唯一执行信封与四级资料契约计划

## 目标

在不改变 fixed route、正式任务顺序、文学 Gate、Agent 角色隔离和写回事务的前提下，
把当前分散在 `AGENT_TASK.md`、`TASK_CONTEXT.json`、Task Package、Prepared Context
与 Context Ledger 中的模型执行上下文收敛为一个版本化
`ExecutionContextEnvelope`。

本批只建立可验证合同和 shadow 运行证据，不直接启用较低的 bounded 上限。

## 权威边界

- Task lifecycle 继续由 Engine task package 和 `task-next/task-open/task-submit/task-complete`
  所有。
- Studio Runtime 只负责从同一个正式 Task Package 编译执行信封。
- Prompt、机器上下文、Run Manifest 和 Context Ledger 必须引用同一个 envelope digest。
- Context Ledger 记录模型实际可见层级，不保存隐藏推理或完整正文副本。
- Sandbox 仍只暴露许可资料和 expected outputs；信封不能扩大文件权限。
- 任一资料只允许属于一个有效层级：
  - `must_inline`
  - `exact_on_demand`
  - `summary_reference`
  - `excluded`

## 实施步骤

1. 在 `runtime/execution_context.py` 新增不可变信封、层级枚举、摘要引用和解析校验。
2. 扩展 `runtime/context_selection.py`：
   - 保留现有 curated source/reference 行为；
   - 明确记录被 task dependency 或 operating manual 排除的路径；
   - 不用目录启发式猜测 mandatory literary context。
3. Prepared Context 完成后，根据真实内联、可按需读取、摘要引用和排除结果编译信封；
   四组路径必须互斥，digest 必须绑定任务、Prompt asset、预算和路径内容身份。
4. `task_program.py` 只从信封投影模型可见的资料层级；不再同时重复展开完整 source、
   reference 和相同输出合同。
5. `TASK_CONTEXT.json` 保留向后兼容字段，但增加同一份
   `execution_context`，并明确它是恢复/审计投影，不是额外阅读任务。
6. Context Ledger 为每个条目记录 `visibility_tier`，并把 envelope digest 纳入运行身份；
   旧 ledger 继续可解析。
7. Run Manifest 和 `sandbox.context_ready` 公开 envelope schema、digest、层级计数和预算，
   不公开 Prompt、正文、绝对路径或凭证。

## 失败关闭

- 四级路径发生重叠时拒绝编译。
- `must_inline` 未实际进入首轮完整快照时拒绝编译。
- `exact_on_demand` 不在 Agent workspace 时拒绝编译。
- `summary_reference` 缺少 source digest 或摘要 digest 时拒绝编译。
- bounded 模式仍要求正式 task 显式声明 mandatory 路径；本批不降低该门槛。

## 验收

- 纯合同测试：序列化、digest 稳定、层级互斥、旧 ledger 兼容。
- Sandbox 集成：Prompt、Task Context、Run Manifest、Context Ledger 使用同一 digest。
- 权限测试：excluded 文件不进入 Agent workspace，Prompt 不提示 Agent 去读取它。
- fixed-route 回归：现有 expected outputs、preflight、writeback、task completion 不变。
- 全量 Python、Client、Prompt Registry、Architecture Audit、compileall、生产前端构建与
  `git diff --check` 通过。

## 明确不做

- 不引入语义向量检索。
- 不生成无法追溯的 LLM 摘要。
- 不启用跨任务 session reuse。
- 不实现 ContextCacheKey 或 Execution Bundle。
- 不开启正式并发。
- 不把 `shadow` 报告冒充真实 Token 节省。
- 不在没有真实同模型 A/B 的情况下宣称 W6-4G 完成。
