# 环境 Agent 场景初始化

状态：2026-09-25，已接入 lean 场景表演路线；真实模型文风试跑待后续创作测试。

## Module Change Packet

```yaml
module_change_packet:
  objective: "每场环境 Agent 先接收主创填写的标签初始化，再在同一无工具会话接收场景资料并生成候选描写"
  primary_module: "Engine literary/scene/roleplay/performance.py"
  public_entry: "render_performance_plan_prompt / parse_performance_plan / render_environment_prompt"
  variation_point: "主创按本场需要增删改六区标签，标签数不设固定配额"
  inputs: ["SceneBrief", "Expression And Voice", "Confirmed Sources", "主创编排 JSON"]
  outputs: ["environment_initialization", "候选环境 passages"]
  invariants: ["正文仍由主创写", "环境 Agent 无工具、无项目写权", "Canon 与审查路线不变", "场景资料不混入首条初始化"]
  allowed_dependencies: ["Engine public literary facade", "Studio scene performance adapter", "Pi Worker conversation transport"]
  forbidden_dependencies: ["第二套 Gate", "环境候选直接晋升正文", "Provider 特定逻辑"]
  tests: ["环境初始化渲染与编排解析", "同一会话的首条与后续消息次序", "环境候选接入场景事务"]
  rollback_unit: "本批环境初始化相关 diff；已有工作树改动保留，不混合提交"
  documentation: ["本文及相关测试"]
```

## 行为合同

初始化首条消息只包含 `【SCENE_LOAD】`、`[COMPOSITION_MODE]`、`[SCENE_CORE]`、`[SCENE_SURFACE]`、`[LITERATURE_STYLE]`、`[NOW_TO_DO]` 六区。区内标签由主创结合本场人物视角、空间、作品风格自由填写；范例标签不是运行时门禁或逐项描写配额。`[LITERATURE_STYLE]` 可用作家、文学流派或作品的抽象英文标签。首条消息之后，同一会话再收到 SceneBrief、已确认来源、文风参考、可用情境及输出格式。

旧环境写手系统散文提示由首条初始化取代；无工具和无写权由 Worker 实际工具列表及隔离边界保证。环境输出仍只是候选素材，由主创决定取舍与正文写法。

## 实施位置与验证

- Engine 场景编排生成并解析 `environment_initialization`；六区顺序固定，区内标签由主创自由增删，未设置数量配额。
- Studio 将首条初始化与后续场景资料封装成环境会话；Pi Worker 在同一无工具 Agent 会话依次发送两条用户消息，且只把第二轮输出当作候选素材。
- 已通过完整 Python 回归 1580 项（另有 1 项跳过）；最后将输出 schema 标为 v10 后，相关 Python 测试 42 项复验通过。Pi Worker 测试 109 项及构建、架构审计、模块图检查、Prompt Registry 校验与 `git diff --check` 均通过。
- 尚未通过真实模型试跑比较环境 Agent 文风；本批验证的是初始化消息与后续场景资料的顺序、执行隔离和候选素材合同。
