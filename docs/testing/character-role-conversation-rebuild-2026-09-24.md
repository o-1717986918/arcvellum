# 场景角色持久对话重构（2026-09-24）

## 目标

每个角色在一场中使用一个无工具 Pi Agent 对话实例。第一次输入只含“你是姓名与身份、简短抽象语言特点”和用户指定的三条沉浸要求；此后可按场景需要继续发送人物处境、任务、追问和输出格式，不限定后续轮数。当前整场批量路线在初始化后发送一次场景任务，要求返回该角色整场的候选言行；这只是当前调用方式，不是会话协议的轮数上限。角色候选不直接成为正文、Canon 或正式资产；主创与既有审查、晋升链保持原权属。

旧的角色整包提示、重复的语言风格 JSON，以及实验性 relay 角色逐回合调用从活动执行链退出。首轮消息的完整内容和后续消息的先后顺序需要由测试直接断言，不能靠把文本拼成单条消息冒充同一 Agent 对话。

## Module Change Packets

### A. Engine 角色提示合同

```yaml
module_change_packet:
  objective: "拆分纯角色初始化与后续场景任务，主创分别设计简短语言特点与场景职责"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_actor_initialization_prompt, render_actor_scene_prompt, parse_performance_plan"
  variation_point: none
  inputs: ["SceneBrief", "主创 performance plan", "现有人物投影"]
  outputs: ["初始化文本", "场景任务文本", "归一化计划"]
  invariants: ["角色只交候选言行", "场景事实仍由主创与来源限定", "初始化消息不含任务/JSON"]
  allowed_dependencies: ["Engine roleplay contract", "Engine public.literary export"]
  forbidden_dependencies: ["Studio runtime", "Provider SDK", "新增 Gate"]
  tests: ["tests/test_scene_performance_agents.py"]
  rollback_unit: "Engine 角色提示合同"
  documentation: ["本记录"]
```

### B. Studio 会话接线

```yaml
module_change_packet:
  objective: "为每位角色在同一会话中先发送纯初始化，再发送任意数量的后续消息，并只接收最后一次结果"
  primary_module: "Studio runtime/role_conversation"
  public_entry: "RoleConversationGateway.run_sequence"
  variation_point: "现有 Pi Worker conversation adapter"
  inputs: ["初始化及至少一条后续消息", "scene actor role"]
  outputs: ["最终角色候选", "隔离会话记录"]
  invariants: ["一次角色调用一个进程与一个 Agent 实例", "环境/主创仍用原入口", "正式正文由主创生成"]
  allowed_dependencies: ["Studio runtimes", "Engine public.literary"]
  forbidden_dependencies: ["直接 Provider HTTP", "第二套任务生命周期"]
  tests: ["tests/test_role_conversation.py", "tests/test_scene_performance_agents.py"]
  rollback_unit: "Studio 会话接线"
  documentation: ["本记录"]
```

### C. Pi Worker 角色对话

```yaml
module_change_packet:
  objective: "让同一 Pi Agent 顺序接收纯初始化及后续消息，隐藏初始化回执，仅交付最新答案"
  primary_module: "workers/pi-worker conversation"
  public_entry: "runConversation"
  variation_point: "character-actor 专用有序消息输入；其他 conversation role 保持单消息"
  inputs: ["版本化消息 envelope，至少含初始化与一条后续消息", "模型与 thinking 配置"]
  outputs: ["最后一轮 answer", "累计用量事件"]
  invariants: ["同一 Agent 实例", "无工具、无项目写入", "DeepSeek thinking 映射继续生效"]
  allowed_dependencies: ["Pi Agent Core", "现有 Pi runtime contracts"]
  forbidden_dependencies: ["文学 Gate", "项目写入能力"]
  tests: ["workers/pi-worker/test/conversation-profile.test.ts", "npm run check", "真实角色调用"]
  rollback_unit: "Pi Worker 会话协议"
  documentation: ["本记录"]
```

## 验收

1. 角色首轮提示逐字符合用户格式，只有姓名、身份、简短语言特点及三条沉浸要求。
2. 场景、任务单、人物事实和 JSON 输出说明只在后续消息。
3. 每名参与者每场只启动一个 Pi Agent 实例；初始化后可继续多次 `agent.prompt`，最终候选来自最后一次回答。当前批量场景发出一次后续任务，但协议和测试不得把两轮写成上限。
4. 旧 relay 逐回合角色提示不可从产品配置进入活动链；旧缓存失效。
5. 定向、架构测试与一轮真实角色调用提供证据；未完成的正式晋升不得冒称通过。

## 验证记录

- Python 定向回归：`python -m unittest tests.test_role_conversation tests.test_scene_performance_agents tests.test_lean_kernel_v2_pi_runtime`，46 项通过。包含三消息会话及旧单条角色提示拒绝用例。
- Pi Worker：`npm run check`，构建通过，108 项测试通过；角色协议允许初始化后继续发送消息，不把第二条当作终点。
- 真实 DeepSeek 试跑：`build/scene-performance-e2e/actor-conversation-smoke/character-actor/runs/run-1790250200323`。依次发送初始化、场景任务、追问；事件记录有三次 provider request，同一 `arcvellum-conversation-603365e9f886bd455cd2` 会话 ID，只发出一次 session.created、一次 session.finished，无协议警告。最终回答为：“（我把书往柜台上一放，抬眼看他，顿了一下）在。抽屉最底下，压着呢——你倒记得清楚。”这验证了多消息会话接线，不代表整场正文或正式晋升已经通过。
- `compileall`、模块图检查、`git diff --check` 通过。广域 Python 回归第一次运行 1568 项，只有架构预算一项失败：字数预算函数超出既有长度与复杂度基线。把既有条件抽成等价的具名谓词后，架构审计通过；再跑架构、字数预算、长篇物化和角色场景等 76 项针对性测试，全部通过。
