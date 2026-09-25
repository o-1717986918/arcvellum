# 人物声音链路修复记录（2026-09-24）

## 目标与现状

让主创在资产初始化时真正塑造人物语言，并在每场给角色写具有个性、同时保留角色自主性的扮演引子。当前 `speech_style` 虽在自动补全字段中，但被长清单淹没；场景导演只给情境锚点；角色提示还会丢掉档案中的 `signature_patterns`。测试项目的两张人物卡停留在初始简卡，因此实际扮演收到的是空白声音。

本轮做减法：不新增 Agent、Gate、实验模板或质量评分；必要的事实归属与 JSON 交付格式保留。

## Module Change Packets

### A. 资产初始化

```yaml
module_change_packet:
  objective: "生成有辨识度的人物语言资产，并补全现有测试项目的初始人物卡"
  primary_module: "Studio application/lean_asset_enrichment"
  public_entry: "enrich_lean_planning_assets(project_root, gateway)"
  variation_point: none
  inputs: ["lean_project_plan.json", "generated character stubs", "project directions"]
  outputs: ["characters/*.yaml 中已有 speech_style 合同"]
  invariants: ["不覆盖用户编辑的资产", "人物背景与世界规则仍由主创生成", "不改变正式审查和晋升"]
  allowed_dependencies: ["lean_assets", "RoleConversationGateway", "atomic_write_batch"]
  forbidden_dependencies: ["场景正文写入", "新的资产 schema/Gate"]
  tests: ["tests/test_lean_assets.py", "测试项目真实主创补全"]
  rollback_unit: "资产初始化改动"
  documentation: ["本记录"]
```

### B. 场景扮演合同

```yaml
module_change_packet:
  objective: "主创为每位角色设计第二人称角色特点，角色收到完整语言资产，并在首轮消息中收到第一人称沉浸要求"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_performance_plan_prompt, parse_performance_plan, render_actor_scene_prompt"
  variation_point: none
  inputs: ["SceneBrief", "character expression projection", "confirmed sources"]
  outputs: ["场景计划中的每角色扮演引子", "角色提示文本"]
  invariants: ["主创确定场景事实和结局", "演员独立生成本人的言行", "未知事实不升格为 Canon"]
  allowed_dependencies: ["现有 performance contract", "现有人物卡投影"]
  forbidden_dependencies: ["新的角色任务单模块", "审查 Gate", "正式正文"]
  tests: ["tests/test_scene_performance_agents.py"]
  rollback_unit: "角色提示合同改动"
  documentation: ["本记录"]
```

### C. 执行接线

```yaml
module_change_packet:
  objective: "把主创写的扮演引子送到每个角色调用，并缩短 Pi 角色系统提示"
  primary_module: "Studio runtimes/scene_performance adapter"
  public_entry: "scene_performance_materials"
  variation_point: "现有 Pi conversation role"
  inputs: ["normalized performance plan", "dialogue_intents"]
  outputs: ["character-actor prompt", "cache version"]
  invariants: ["角色仅返回素材", "正式正文仍由主创组织", "旧缓存不能掩盖新提示"]
  allowed_dependencies: ["Engine public.literary", "Pi worker conversation profile"]
  forbidden_dependencies: ["新执行器", "新路由", "额外审查门禁"]
  tests: ["tests/test_scene_performance_agents.py", "workers/pi-worker/test/conversation-profile.test.ts"]
  rollback_unit: "调用适配与系统提示改动"
  documentation: ["本记录"]
```

### D. 主创正文交接

```yaml
module_change_packet:
  objective: "正文主创收到素材时能发挥修订和文学渲染能力，而不被重复防错句淹没"
  primary_module: "Studio runtimes/pi_scene_transaction prompt adapter"
  public_entry: "render_scene_create_prompt"
  variation_point: none
  inputs: ["已有角色与环境候选", "SceneBrief", "文风参考"]
  outputs: ["精简的正文主创提示"]
  invariants: ["角色外显言行有一级来源", "主创仍可改台词与组织正文", "未确认细节不成为 Canon"]
  allowed_dependencies: ["现有场景提示配方", "performance material block"]
  forbidden_dependencies: ["新 Gate", "新创作角色", "自动生成无来源回合"]
  tests: ["tests/test_lean_kernel_v2_pi_runtime.py", "真实场景试跑"]
  rollback_unit: "主创交接提示改动"
  documentation: ["本记录"]
```

### E. DeepSeek 思考模式映射

```yaml
module_change_packet:
  objective: "用户选择 medium 时，DeepSeek 角色扮演仍进入厂商所述的思考模式"
  primary_module: "Pi Worker reasoning-budget"
  public_entry: "safeThinkingLevel(model, requested)"
  variation_point: "DeepSeek 模型只报告 off/high/max，官方将 medium 映射到 high"
  inputs: ["model provider and supported thinking levels", "user-selected level"]
  outputs: ["effective Pi thinking level"]
  invariants: ["off 仍是 off", "其他 provider 的降级语义不变", "不把推理文本泄漏到正文"]
  allowed_dependencies: ["Pi AI model metadata", "DeepSeek 官方思考模式文档"]
  forbidden_dependencies: ["角色提示强制输出隐藏推理", "新开关或 Gate"]
  tests: ["workers/pi-worker/test/reasoning-budget.test.ts", "真实角色调用的 reasoningCharacters"]
  rollback_unit: "DeepSeek thinking 映射改动"
  documentation: ["本记录"]
```

验证以真实角色输出和正文阅读为主；结构测试只确保声音不再丢失，不能拿句长或模板命中率代替文笔判断。
