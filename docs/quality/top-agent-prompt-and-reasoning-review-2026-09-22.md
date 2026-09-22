# 顶层 Agent 提示词与思考强度审查（2026-09-22）

## Module Change Packet

```yaml
module_change_packet:
  objective: "顶层 Agent 按用户意图自然答复，并在当前模型允许时使用最高思考强度"
  primary_module: "Studio project_agent/"
  public_entry: "project_agent.prompt_policy.system_prompt/delegated_goal_followup_prompt；project_agent.factory.build_project_agent_runtime"
  variation_point: "顶层 Agent 独立的 project_agent_thinking 配置，不影响创作 Worker"
  inputs: ["用户消息与会话", "只读作品证据与长期目标终态", "agent_runners.pi-worker 设置"]
  outputs: ["顶层 Agent 提示词", "Pi Worker --thinking 参数", "面向作者的答复"]
  invariants: ["不改变工具权限或文学门禁", "不把任务数冒充正文进度", "不把预设盲评冒充成稿盲评", "不推断未证实人物与情节"]
  allowed_dependencies: ["application/config.py 默认设置", "Pi Worker 已有思考等级能力", "project_agent 现有合同测试"]
  forbidden_dependencies: ["Engine 门禁", "创作 Worker 的思考配置", "前端状态卡"]
  tests: ["顶层提示词合同测试", "独立思考强度与旧配置兼容测试", "完整回归与架构检查"]
  rollback_unit: "本批独立 Git 提交"
  documentation: ["本审查记录"]
```

## 发现

1. `prompt_policy.py` 的工具、证据和权限边界总体合理。问题是同一长段把事实义务、失败恢复、对话口吻、固定信息顺序混写，且终态回执再次要求按“故事变化—人物—线索—下一步—运行状态”逐项汇报。即使用户只问一个窄问题，也容易产生固定简报腔。应保留事实义务，取消逐项模板和无条件信息铺陈。
2. 默认“严谨总编”人格强调结构判断，本身没有固定答复格式；但当前提示词没说明人格只调节观察角度，容易把操作交接也写成编辑审稿。应让用户问题决定回答方式。
3. 开发板中大量“状态已更新／已完成”来自前端活动状态卡，不是顶层模型生成的文字。本批不把这些卡片问题归因于提示词，也不修改前端。
4. 当前本机配置的共用 `thinking` 为 `low`，顶层 Agent 复用此值。所用 DeepSeek V4 Flash 的本地 Pi 模型目录仅映射 `high` 和 `max`，`low` 会经 `safeThinkingLevel` 降到 `off`。因此顶层 Agent 实际未获得预期的推理强度。应设独立默认 `max`；运行时继续按模型能力安全降级。

## 修正边界与验证

只改顶层 Agent 的提示词及启动参数。里程碑回执先给用户真正关心的成果，人物、线索、风险和下一步按相关性选取，不设统一标题或固定顺序。继续要求工具核实正式事实、区分完成与运行中、说明审读证据边界。独立 `project_agent_thinking=max` 不改变创作 Worker 的 `thinking=low`。本批静态测试可证明配置传递和提示词约束；真实文风收益仍需后续多轮作者对话盲评。

## 本批验证结果

- 本地 Pi 模型目录确认 DeepSeek V4 Flash 的思考等级映射为 `high`、`max`，`low` 不受支持；现有 `safeThinkingLevel` 会将不受支持的 `low` 回退为 `off`，将 `max` 保持为 `max`。
- 顶层 Agent、旧配置兼容与提示词定向测试：25 项通过。
- Python 全量测试：1,483 项通过，1 项跳过；Pi Worker：102 项通过；前端：245 项通过，构建通过。
- 架构审计、模块映射检查、提示词注册表验证、CLI doctor/help 均通过；未改变任何文学门禁。
- 未运行真实模型的多轮对话 A/B 测试，因此“回复是否明显更自然”尚不能作为已实证结论。配置改动需重启开发板服务后才会作用于新回合。
