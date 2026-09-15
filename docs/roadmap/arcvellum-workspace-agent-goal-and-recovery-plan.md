# ArcVellum 作品库级顶层 Agent、长期目标与主动恢复计划

> 状态：D9-A 至 D9-E 已完成，真实创作与同轮长任务恢复验证通过
>
> 日期：2026-09-14
>
> 主模块：`src/literary_engineering_studio/project_agent/`

## 1. 目标

把 Project Agent 从绑定单部作品的对话助手提升为作品库级总控 Agent。用户可以在同一自然语言入口中查看、创建和管理任意已登记作品，交付一个会持续运行的长期创作目标，并在任务阻断时要求 Agent 诊断、采取受控恢复动作并验证恢复结果。

这次扩权不授予任意 Shell、任意路径读写、文学 Gate 豁免或直接正文写入。Agent 的权限来自少量领域工具；所有正式事实继续由现有 Application Service、Lean Kernel、Worker 写回和交付门禁决定。

## 2. Module Change Packet

```yaml
module_change_packet:
  objective: "顶层 Agent 可跨作品管理、执行长期目标，并对可恢复阻断主动诊断和恢复"
  primary_module: "Studio project_agent"
  public_entry: "ProjectAgentService + ProjectAgentDependencies + ProjectAgentActionDependencies"
  variation_point: "当前回合所针对的已登记作品，以及长期目标的执行状态"
  inputs:
    - "稳定 work_id，不接受模型提供的原始路径"
    - "用户自然语言目标"
    - "现有作品库、dashboard、Autopilot 和领域服务投影"
  outputs:
    - "有界工具结果"
    - "长期目标与 Autopilot run receipt"
    - "诊断和恢复 receipt"
    - "durable Project Agent job/event/message"
  invariants:
    - "正文只能由正式主创 Worker 生成"
    - "Agent 不能绕过 review、promotion、canon、state 和 delivery Gate"
    - "只可操作作品注册表中存在的 work_id"
    - "长期执行复用 Autopilot 的线程、租约、重试和防空转"
    - "Agent 工具调用失败后必须重新读取状态并验证，不能伪报成功"
  allowed_dependencies:
    - "application/project_manager"
    - "project read models"
    - "automation/AutopilotService"
    - "既有 quality/rhythm/style/archive/delivery 服务"
    - "Pi Project Agent bridge"
  forbidden_dependencies:
    - "任意 Shell"
    - "任意文件路径"
    - "第二套任务状态机"
    - "第二套长期运行线程池"
    - "直接 Provider HTTP 调用"
  tests:
    - "project_agent contracts/read models/actions/service/API"
    - "Pi project-agent protocol"
    - "Project Agent 前端 feature tests"
    - "一条作品创建到长期运行启动的 API 集成路径"
  rollback_unit: "独立 Project Agent 扩权提交"
  documentation:
    - "本计划"
    - "Agent Desktop 与顶层 Agent 设计方案 D9 状态"
```

## 3. Autopilot 的最终定位

Autopilot 保留，但退出用户心智模型。

```text
用户长期目标
  -> Project Agent 理解并记录目标
  -> Project Agent 选择作品与执行策略
  -> Autopilot 作为后台执行泵持续领取正式任务
  -> Lean Kernel / Worker / Gate 产生事实
  -> Project Agent 查询结果、诊断阻断并触发受控恢复
```

Project Agent 与 Autopilot 不再是两个平级总控：

- Project Agent 拥有意图解释、跨作品选择、策略组合、错误诊断和恢复决策。
- Autopilot 拥有长时间循环、进程与租约管理、重试、防空转、正式任务推进。
- Lean Kernel 拥有文学事实、任务顺序和 Gate。
- Pi Worker 拥有被签发任务中的创作、审查和结构化输出。

删除 Autopilot 会迫使 Project Agent 重建线程、锁、恢复、幂等和任务循环，成本高且会降低可靠性。保留其内部服务，收起独立用户操作面，收益更高。

## 4. 工具面

### 4.1 新工具

1. `workspace_catalog`
   - 列出已登记作品和当前作品。
   - 只返回稳定 `work_id`、标题、类型、状态和简要目标，不把本机路径交给模型。

2. `project_create`
   - 通过现有项目初始化服务创建作品。
   - 返回新作品的 `work_id` 和摘要。

3. `project_diagnose`
   - 聚合 dashboard、当前 run、Agent activity、route audit 和待决策事项。
   - 输出确定性问题分类、是否可自动恢复及下一工具建议。

4. `project_goal_manage`
   - `start`：记录长期目标，把执行策略设为 `lean-v2/full_auto`，启动后台创作。
   - `pause`：暂停长期目标。
   - `resume`：恢复已有目标。
   - `recover`：对无待决策的暂停或阻断执行幂等恢复；无 run 时按给定目标启动。

### 4.2 跨作品作用域

所有项目级工具增加可选 `work_id`。Dispatcher 在调用领域服务前，通过实时作品注册表解析 `work_id`；模型提供的路径字段无效。未传 `work_id` 时使用会话锚定作品；作品库会话则使用注册表中的当前作品。

### 4.3 兼容工具

`creation_control` 暂时保留协议兼容，但不再默认暴露给 Project Agent。长期工作统一使用 `project_goal_manage`，减少工具重叠和错误选择。

## 5. 主动修正协议

Agent 的恢复循环固定为：

```text
project_diagnose
  -> 判断 pending decision / runtime failure / paused / no run / complete
  -> 调用精确领域工具或 project_goal_manage(recover)
  -> project_diagnose 复核
  -> 只有证据变化后才报告恢复成功
```

以下情况不会被“自动修复”掩盖：

- 模型未配置或认证失败；
- 作品文件损坏；
- 正式 Gate 拒绝；
- 候选审查未通过；
- 需要选择的文学分支缺少足够依据。

Agent 可以读取证据、调整可控配置或重新启动执行，但不能篡改产物伪造通过。

## 6. 长期目标语义

长期目标不会让单个模型进程长时间空转。`project_goal_manage(start)` 产生持久方向记录和 Autopilot run；Project Agent 的首次推理结束后，原对话 Job 进入轻量观察状态，持续接收 Autopilot 的有效进度。目标到达完成、暂停、阻断或失败终态时，同一轮对话自动启动一次短推理，核验项目证据、尝试受控恢复或向用户汇报交付结果。

等待阶段不占用 Provider 会话，也不建立第二套创作状态机。对话 Job 只保存 `run_id`、`work_id` 和非敏感进度摘要，并定时续约自身租约；用户停止当前回答时只结束观察，不会暗中取消仍可独立完成的创作目标。

运行中的普通协作任务不会被静默解释为长期目标。目标模式需要 `full_auto + lean-v2 + delegated release` 三项一致；策略不一致时，`AutopilotService.start_managed_goal()` 先停止旧控制器并等待线程退出，再建立新的持久运行，避免两个控制器同时写同一作品。

第一版长期目标不增加新的数据库表。方向记录是目标文本的正式来源，Autopilot run 是执行状态来源，Job/Event 是过程证据。只有实际使用证明需要多目标排队时，才评估独立 Goal Repository。

## 7. 分批实施

### D9-A：作品库作用域与合同

- 增加稳定 `work_id` 和注册表解析。
- 增加 `workspace_catalog`。
- 现有工具支持可选 `work_id`。
- 作品库外路径 fail closed。

### D9-B：长期目标与主动恢复

- 增加 `project_create`、`project_diagnose`、`project_goal_manage`。
- 长期目标启动强制 `lean-v2/full_auto/delegated release`。
- 恢复前检查待决策，恢复后返回 receipt。
- 更新系统提示词，要求“诊断、动作、复核”。

### D9-C：API、Pi Worker 与前端

- Project Agent 会话允许在尚未选择作品时建立作品库会话。
- Pi 工具 schema 使用 `work_id`，不暴露路径。
- 前端允许无作品时与 Agent 对话创建作品。
- 创建作品工具完成后刷新作品列表，同时保留当前作品与 Agent 会话。
- 增加停止当前 Agent 回合，后续再评估运行中消息队列。

### D9-D：验证与收敛

- 运行 Project Agent Python、Pi Worker 和前端定向测试。
- 通过 API 合同测试验证作品库会话与停止；通过领域动作测试验证列作品、创建作品、启动长期目标、诊断、暂停和恢复。
- 执行 architecture audit，确保不新增依赖倒置、超长函数或第二状态机。
- 更新 D9 状态和剩余缺口。

### D9-E：同轮长任务续接

- `project_goal_manage` 回执携带可观察的 Autopilot run 身份与状态。
- Project Agent 释放首次 Pi 推理进程，以持久 Job 观察长期目标。
- SSE 只在进度变化时发送路线、任务数与终态，不用高频文本制造推进假象。
- 终态到达后自动启动收尾推理；阻断时先诊断并可在同轮恢复，完成时复核交付证据。
- 前端把等待、推进、终态和复核显示为同一条回答的连续阶段。

完成记录：Project Agent Python 测试覆盖跨作品解析、无作品会话、作品创建、目标启动/恢复、待决策保护、取消竞态和同轮长任务续接；Autopilot 测试覆盖持久目标控制器切换、恢复和防空转；API 测试覆盖会话与 SSE；Pi Worker 测试覆盖新工具协议；客户端测试覆盖长任务等待、进度、终态、自动复核、作品库刷新与停止。Project Agent 运行时主循环已拆分为协议读取、工具桥接和进程收尾步骤，长期观察进一步独立为无模型占用的适配模块。

## 8. 完成标准

- 用户可以在未选择作品时让 Agent 创建作品。
- Agent 可以列出并按 `work_id` 操作任意已登记作品。
- “完成这部作品”会形成持久长期目标，并在同一聊天回合持续显示进度、自动复核终态。
- 可恢复阻断能由 Agent 完成诊断、恢复和复核。
- 所有正式文学 Gate 仍有效，正文仍由主创 Worker 生成。
- Autopilot 不再作为用户必须理解的第二个总控系统。
- 工具总量不超过既定 18 个预算，默认单回合可见工具保持有界。

## 9. 实施结论

顶层 Agent 已拥有作品库级只读与受控写权限，可以在未选择作品时建立会话和作品，并按稳定 `work_id` 管理任意已登记作品。长期目标由 Project Agent 解释、记录和启动，由 Autopilot 在后台持久执行；可恢复失败继续使用现有 checkpoint、重试、防空转和决策委托机制。确定性恢复由执行泵立即处理，待决策事项由顶层 Agent 使用 `project_decision_resolve` 处理后恢复目标；只有需要重新理解用户目标时才产生新的顶层 Agent 模型回合。

Autopilot 在实现层仍然必要，在产品层不再与 Project Agent 并列。用户只需要表达目标、查看作品和在必要时要求暂停；线程、租约、任务领取和恢复属于内部执行细节。
