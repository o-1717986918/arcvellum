# AO-3D Planner/Reviewer Shadow Service 架构评审

> 评审日期：2026-07-26  
> 范围：W6-4D，只评审只读 Planner/Reviewer Shadow 链，不包含 AO-4 激活和生产执行。

## 1. 结论

AO-3D 达到退出条件：

- Planner 与 Reviewer 使用独立的真实 Runtime session；
- 两种角色均通过只读 OpenCode profile 运行，工作区限定在 orchestration run audit；
- Agent 只提交结构化候选或判断，机器负责事件封装、归一化、Lint、Compile、Simulation、
  Review Receipt 和持久化；
- Shadow 计划始终执行 fixed route，持久化 revision 被机器标记为不可激活；
- feature-off、Planner/Reviewer/连接异常、候选无效、Lint/Simulation 失败、同会话审查、
  stale context 和审计写入故障均安全回退 fixed route；
- 没有新增依赖环、超线大文件或函数债务。

## 2. 边界

### 2.1 Agent Runtime

`RuntimeOrchestrationAgentTransport` 当前只接受 OpenCode。原因不是供应商偏好，而是 AO-3
只允许经过验证的 Planner/Reviewer 角色隔离 profile。Claude Code、Codex CLI 或其他
Runtime 在实现同等只读 capability 前不得进入此链路。

Planner 和 Reviewer：

- 不读取正式项目根目录；
- 只读取机器装配的 bounded context；
- 只在 `workflow/orchestration/runs/<operation>/` 下留下 runtime 输出；
- 不拥有正式写回、计划激活、任意 Shell 或候选修改权。

### 2.2 事件边界

`plan.candidate.delta` 只存在于 Runtime 响应的瞬时展示流，不进入 durable
`events.jsonl`。持久链从机器封装的 `plan.candidate.completed` 开始，只有该事件可以
进入 normalize、Lint、Compile 和 Simulation。

Reviewer 获取完整候选、归一化计划、Lint、Compiled Graph 和 Simulation。证据禁止静默
截断；精确上下文超过上限时回退 fixed route。

### 2.3 持久化与激活

Shadow revision 的 review 索引固定包含：

```text
activation_eligible = false
lifecycle = shadow_observation
```

既有 activation API 对缺失或 false 的标志 fail closed。即使 Reviewer 返回 clean
`pass`，AO-3 revision 也不能被后续公共入口激活；AO-4 必须通过独立审批合同产生新的
可激活证据。

Review Receipt 在持久化前逐项绑定：

- plan ID 与 revision；
- Reviewer context ledger digest；
- candidate digest；
- normalized plan digest；
- graph digest；
- simulation digest；
- 独立 Planner/Reviewer session。

重新读取 portable revision 时会再次校验主要语义链，避免跨计划 Receipt 被当作通过。

## 3. Fixed Route 对照

每个成功或失败的 Shadow run 都记录：

- fixed route step 数；
- 候选节点数；
- 机器注入 Gate 数；
- Lint、Simulation、Review 状态；
- Planner、Reviewer 和确定性阶段耗时；
- fallback 原因；
- `fixed_route_unchanged=true`。

Shadow Service 不调用 Autopilot，不创建 active plan，不修改正式任务状态，也不触碰
Canon、正文或资产。

## 4. 独立审阅闭环

第一轮独立审阅发现 4 个 P1 和 3 个 P2：

1. Shadow revision 可被既有 activation API 误激活；
2. Review Receipt 未与当前证据链绑定；
3. 普通运行异常不能始终回退 fixed route；
4. 非 OpenCode Runtime 可能缺少只读保证；
5. Reviewer 后存在 stale 窗口；
6. display delta 被写入 durable ledger；
7. `pass_with_notes` 与 clean activation 语义不一致。

修复后复核结果为零 P0、零 P1。最后一个 stale P2 通过在 evaluation 写盘后、紧贴
`persist_shadow_revision()` 前再次比较项目 fingerprint 收口。`pass_with_notes` 继续
遵循 ArcVellum 全局纪律：它不是 clean pass，不能进入激活。

## 5. 验证

- AO-3D 聚焦及攻击型测试：30 passed；
- Python 全量回归：628 passed，1 skipped；
- Prompt Registry：54 assets、89 task prompt IDs，0 error、0 warning；
- Architecture Audit：35 个既有 file debt、224 个既有 function debt、0 cycle；
- `python -m compileall -q src tests`：passed；
- `git diff --check`：passed。

## 6. 残余风险与后续边界

- Receipt 是机器所有权合同和摘要绑定，不是针对进程内恶意代码的密码学签名；
- Reviewer context ledger 的完整副本保存在 run audit，portable plan revision 保存其
  digest；AO-4 若允许长期独立迁移 revision，应再决定是否复制 ledger 附件；
- 真实 OpenCode 双会话需要在具备有效登录和模型连接的环境中做发布前 smoke test；
- `service.py` 已接近协调器合理上限。AO-4 activation、Autopilot 接入、UI projection 和
  Campaign 不得继续塞入该模块。

## 7. 下一步

AO-3D 完成后不立即把自适应计划接入生产 Autopilot。先修复星仪 W1 审计中不能延期的
焦点和关系可见性缺口，再进入 AO-4 场景级审批、激活和确定性执行适配。
