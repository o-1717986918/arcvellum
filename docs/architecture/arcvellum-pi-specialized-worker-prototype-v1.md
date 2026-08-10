# ArcVellum Pi 专用 Worker 原型架构 v1

> 状态：实验性原型已实现并完成 structured/review 同模型探针。本文不改变 ArcVellum 默认 Runtime，也不授权把 Pi Worker 打入正式安装包。
>
> 基线：Studio `220116e` 之后的 P0-P5 实现；Pi fork `936aff00918de1187f085f123c2812d8f2d67745`，`@earendil-works/pi-agent-core` / `@earendil-works/pi-ai` 0.84.1。

## 1. 为什么仍然做这个原型

同 Provider、同模型复测已经证明：直接包装完整 Pi coding-agent CLI 没有通过 P6 晋升门禁。review 样本耗时增加 39.8%、费用增加 24.3%；structured 样本耗时增加 112.6%、费用增加 65.0%。一次 review 还产生了至少 34,528 条 reasoning delta 事件。

这否定的是“复用完整 coding-agent 外壳”，没有否定 Pi Agent Core。当前原型只验证一个更窄的问题：

> 去掉编码系统提示、Shell、任意文件工具、Skill、扩展和通用会话层后，Pi Agent Core 能否成为一个更便宜、更稳定的 ArcVellum 文学任务执行内核。

## 2. 权威边界

Studio 永远拥有：

- TaskPackage、路线状态机和任务领取；
- `TASK_CONTEXT.json` 与 Worker Program 编译；
- 上下文选择、预算、digest 和权限声明；
- 沙箱创建、基线、越界变更检查；
- 确定性 preflight、repair 决策、事务写回；
- task-submit、task-complete、route-audit 和正式 Gate；
- 用户审批、Canon/正文晋升和发布。

Pi Worker 只拥有：

- 在单个已创建沙箱中执行当前任务；
- 读取 `TASK_CONTEXT.json` 的受控投影；
- 按 `execution_context.exact_on_demand` 读取精确资料；
- 写入 Agent-owned expected outputs；
- 做本地格式自检并显式声明完成或阻断；
- 发出有界、无凭证的运行事件。

Pi Worker 不知道正式项目路径，不领取下一任务，也不执行任何 CLI 命令。

## 3. 运行拓扑

```text
Studio Worker
  -> 打开正式 TaskPackage
  -> 执行任务自带的确定性前置命令
  -> 创建 control workspace 与 bounded agent workspace
  -> 编译 AGENT_TASK.md + TASK_CONTEXT.json
  -> 启动 PiAgentRuntime（短生命周期）
       -> arcvellum-worker
          -> Pi AI Provider
          -> Pi Agent Core
          -> 7 个 ArcVellum 白名单工具
  -> Worker 显式 complete_task / report_blocker
  -> Studio deterministic preflight
  -> approval / writeback / task-complete / route-audit
```

原型保持“一任务一进程”。只有 benchmark 证明进程启动占比显著，才考虑复用进程；即使复用进程，也不默认复用跨任务对话历史。

## 4. 仓库与模块归属

### 4.1 Pi fork

在 `arcvellum-pi-agent/packages/arcvellum-worker/` 新增 workspace package：

```text
src/
  main.ts                 # 一次性进程入口、参数与退出语义
  contracts.ts            # TaskContext、结果和事件的窄类型
  task-context.ts         # 合同读取、任务类别门禁、Agent-owned outputs
  path-policy.ts          # 相对路径、越级、符号链接和读写集校验
  credential-store.ts     # 只读 Pi auth.json CredentialStore
  tools.ts                # 7 个白名单工具
  event-adapter.ts        # Pi events -> ArcVellum runtime events，节流聚合
  worker.ts               # Agent 构建、模型选择、回合与完成策略
test/
```

该包只依赖 Pi Agent Core、Pi AI、TypeBox 和 Node 标准库。不得依赖 Pi coding-agent、TUI、server、Skill/extension loader 或 ArcVellum Python 业务模块。

### 4.2 Studio

新增：

```text
src/literary_engineering_studio/runtimes/pi_worker.py
tests/test_pi_worker.py
```

只扩展 Runtime Registry 和 Runtime kwargs 投影。`worker.py`、`sandbox.py`、`worker_writeback.py` 不为 Pi 复制分支逻辑。

## 5. 输入合同

Worker 的唯一正式输入是 Studio 已物化的：

- 当前工作目录；
- `AGENT_TASK.md`；
- `TASK_CONTEXT.json` v0.2；
- `_task/task.json` 与 `_task/execution_contract.json`，仅供 Worker 启动时核验身份，不暴露为自由读取入口；
- 公开 model id、thinking level、turn/tool budget 和只读认证文件位置。

启动时必须核验：

1. task id、route、state 在三个合同间一致；
2. execution policy 为 `agent-required`；
3. 原型任务属于允许的 structured/review state；
4. expected outputs 与 completion contract 一致；
5. writable paths 不扩大 expected outputs；
6. exact-on-demand 路径属于 readable paths；
7. completion-evidence 不属于 Agent-owned outputs。

任一项失败均在调用模型前 fail closed。

## 6. 白名单工具

第一版固定七个工具，不提供动态工具发现：

1. `read_task_context`
   - 返回任务身份、Agent-owned outputs、格式、语义条件、约束、字数和当前预算；
   - 删除 workspace dependencies、正式路径和凭证信息。

2. `read_authorized_source`
   - 只允许读取 `execution_context.exact_on_demand`；
   - must-inline 已在首轮 prompt 中，不允许重复读取；
   - excluded 和未声明路径一律拒绝。

3. `write_expected_output`
   - 只允许 Agent-owned expected outputs，支持单文件和有界批量提交；
   - 原子写入；拒绝绝对路径、`..`、符号链接和超限内容；
   - 不允许写 completion evidence、`_task/`、`AGENT_TASK.md`、`TASK_CONTEXT.json`。

4. `validate_output`
   - 检查一个或全部 Agent-owned outputs 是否存在、非空且机器格式可解析；
   - 这只是本地快速反馈，不冒充 Studio 正式 preflight。

5. `complete_task`
   - 重新验证全部 Agent-owned outputs；
   - 验证通过才设置进程内 completion latch，并终止 Agent loop；
   - 不生成 completion receipt，不执行 task-complete。

6. `request_repair`
   - 在同一任务内登记一次局部修复意图并返回当前失败项；
   - 不重新发送完整上下文，不增加文件权限；
   - 原型默认最多一次。

7. `report_blocker`
   - 记录结构化阻断原因并终止；
   - Studio 将其视为 runtime failure，而不是伪造任务完成。

## 7. Agent 与停止策略

系统提示只描述 ArcVellum Worker 身份、白名单工具和完成纪律，不包含编码 Agent 的仓库探索、Shell、Git、Skill、subagent 或通用修改策略。

`beforeToolCall`：

- 再次校验工具名、路径、调用预算和 completion 状态；
- 未知工具、超预算、已完成后的调用立即阻断；
- 写工具和完成工具强制顺序执行。

`afterToolCall`：

- 对返回模型的文本做长度上限；
- 登记读写、验证结果和 progress digest；
- `complete_task` / `report_blocker` 返回 terminate hint。

`shouldStopAfterTurn`：

- completion latch 或 blocker latch 已设置；
- 达到最大回合；
- 连续两轮 progress digest 不变；
- 预算或取消信号触发。

模型自然停止但未调用 `complete_task` 不是成功。Worker 返回 `incomplete`，Studio 不进入写回。

## 8. 模型与认证

- 原型使用 Pi AI 的 built-in provider catalog；
- model id 使用 `provider/model`，缺失或不存在时 fail closed；
- 认证通过只读 `CredentialStore` 读取 Pi 自己的 `auth.json`；
- Studio 不读取、复制、显示或迁移密钥；
- 日志只记录 provider、公开 model id、认证状态，不记录凭证值；
- 后续正式产品应由 Runner 自己提供配置界面或安全认证流程，本原型不增加第二套 Provider 平台。

## 9. 可观测性与性能

Worker 输出 JSONL 事件，并映射到 Studio 既有事件名：

- `runner.process.started/completed`
- `runner.session.created/finished`
- `runner.provider.request.started`
- `runner.reasoning.started/activity/completed`
- `agent.message.delta/completed`
- `tool.execution.started/completed`
- `usage.updated`

reasoning delta 不逐 token 落盘。Worker 只累计字符数，并按时间/字符阈值发 activity；Studio 继续应用现有高频事件策略。每条事件一次写入，不在 Node 和 Python 两侧重复保存原始增量。

用量按 assistant message 的累计 usage 汇总，保留 input/output/reasoning/cache/cost。若 Provider 不报告 reasoning，字段必须标为 unavailable 或保持缺失，不能伪造 0。

## 10. 原型门禁

只测试：

- `structured-world-foundation`；
- `review-scene-candidate`。

不测试 analysis、planning、prose，不接入 Autopilot，不在前端显示为普通用户选项。

继续条件：

1. 两类任务都能在首轮或一次局部修复内通过 Studio 正式 preflight；
2. 无越界读写、无 completion evidence 伪造；
3. reasoning 持久事件数量相对 full Pi RPC 至少下降 95%；
4. 同模型至少一类任务在时延或费用上改善 20%，另一类不得显著恶化；
5. 输出文学/语义质量不低于 OpenCode 对照；
6. 取消后进程与子进程均被回收。

未达到继续条件时，保留实验代码和报告，但不进入安装包、默认 Runtime 或 P7/P8 产品开发。

## 11. 批次与回滚

1. 文档与合同审查；
2. Pi fork 内 Worker 包和无模型测试；
3. Studio Runtime 适配与 fixture 测试；
4. 同模型 structured/review live benchmark；
5. 写结论，分别提交 Pi fork 和 Studio。

每批单独提交。任何阶段都可删除 `pi-worker` Registry 项和 Pi fork 的新 package，Studio 默认 OpenCode 链路不受影响。

## 12. 实际结论

原型已完成，并修复了多输出工具预算、批量写入、验证状态进度指纹、显式完成回合、Worker 终止诊断、事件时序回填和 Windows 深路径诊断。

两类任务均通过 Studio 正式 preflight。相对完整 Pi RPC，structured/review 分别提速约 40.7%/30.3%；reasoning 持久事件在 review 样本下降约 99.3%。但相对 OpenCode，structured 更慢、review 更贵，未达到默认替代门禁。

因此原型证明“从 Pi Agent Core 底层构建专用文学 Worker”有架构价值，但不进入安装包、Autopilot 或默认 Runtime。完整数据见 `docs/benchmarks/runtime-p6-specialized-pi-worker-prototype-2026-08-10.md`。
