# 主创全篇意图与推演观察：实施记录

状态：功能已实施，顶层 Agent 实际试跑核验中。范围：lean-v2 场景运行时与创作现场只读观察；不改变正式 Gate、Canon 或候选晋升。

## 已核实的现状

- 推演素材已存于 Studio 的场景事务缓存，但主创的 Pi 会话无项目文件读取工具。正文生成时，当前场景的角色言行和环境候选以文本块进入提示词。文件路径本身不会使模型理解文件，也不会自动节省 token。
- SceneBrief 提供本场目标、冲突、节奏、人物、章节义务与上一场交接；来源按预算截取。但全书规划里的 `premise`、`central_question`、`ending_choice` 和本章戏剧转向并未稳定进入每场主创上下文。主创能写场景，不等于拥有足以校准全书意图的视野。
- 现有 `scene.performance.interaction.turn` 事件只有轮次、角色和条目数量。缓存到表演结束才保存；现有创作现场无法逐轮显示角色实际发言，也没有跨会话的推演历史读模型。

## Module Change Packet A：主创上下文

```yaml
module_change_packet:
  objective: "每场主创以小而稳定的上下文理解全书意图，同时删去与 SceneBrief 重复的原始大文件"
  primary_module: "Studio runtimes/scene_source_evidence.py"
  public_entry: "scene_source_evidence"
  variation_point: "有 lean_project_plan 时抽取全篇主轴和本章转向；没有时保持旧来源行为"
  inputs: ["SceneBrief", "project_root", "已有来源路径", "prompt budget"]
  outputs: ["有来源标识的短全篇意图摘要", "本场仍需的事实来源"]
  invariants: ["用户与 Canon 事实优先", "不补造计划", "输入 revision 的来源绑定不变", "正式 Gate 不变"]
  allowed_dependencies: ["项目本地 JSON", "既有 prompt recipe"]
  forbidden_dependencies: ["Provider 调用", "第二份规划", "前端状态"]
  tests: ["本章意图注入", "预算与冗余抑制", "无规划兼容"]
  rollback_unit: "本批聚焦 diff；保留工作树既有改动"
  documentation: ["本文"]
```

## Module Change Packet B：逐轮事件与历史

```yaml
module_change_packet:
  objective: "正在推演时按角色完成一轮就展示，已推演场景可回看"
  primary_module: "Studio observability/scene_rehearsals.py"
  public_entry: "项目内事务 ID 授权的只读推演列表与详情"
  variation_point: "活跃场景由 SSE 追加完整公开轮次；历史从同一场景会话缓存读取"
  inputs: ["项目事务列表", "Studio data_root", "场景会话缓存", "实时事件"]
  outputs: ["推演索引", "公开发言与行为轮次", "环境候选"]
  invariants: ["不暴露私人内心、角色初始化或原始模型消息", "不跨项目读取", "不产生额外模型调用"]
  allowed_dependencies: ["场景事务 Repository", "creative-live router", "creative-live feature client"]
  forbidden_dependencies: ["正式正文写入", "通用 transport 直连组件", "UI 派生文学事实"]
  tests: ["逐轮落盘与事件", "项目隔离及历史", "前端快照与 SSE 去重"]
  rollback_unit: "本批聚焦 diff；保留工作树既有改动"
  documentation: ["本文"]
```

## 界面方向

主题是“排练中的聊天”，面向正在观察作品的作者；窗口只做一件事：看谁在什么时候说了什么、做了什么。颜色沿用现有创作现场的冷绿与纸白：`#F8FAF7` 纸面、`#263831` 墨色、`#2F705D` 主创绿、`#E6F1EB` 自己一侧的气泡、`#FFFFFF` 另一侧气泡、`#8CA79A` 辅助线。标题用现有 display 字体，正文用现有中文 UI 字体，轮次与节拍用 utility 字体。左列是场景历史，右侧是按轮次生长的对戏流；单人戏的气泡仍按角色身份呈现，环境观察是中轴上的窄卡，不冒充人物发言。独特元素是“轮次线”：每个完成的角色回合沿一条细线落下，不用打字机动画伪造 token 流。

```text
左侧入口「推演观察」 → 独立浮动窗口
┌ 场景历史 ────────┬ 选中场景 / 实时状态 ──────────┐
│ 当前 / 已完成     │ 节拍标签  ·  角色气泡            │
│ 场景 A           │       环境观察                  │
│ 场景 B           │ 角色发言 + 可见动作              │
└──────────────────┴─────────────────────────────────┘
```

## 成本判断

文件持久化用于恢复、追溯与 UI 回看；模型需要使用的文字仍要进入它实际可见的上下文。此次不增加一轮“摘要 Agent”或文件读取工具调用。全篇意图以确定性抽取构成短摘要；已经在 SceneBrief 中体现的整份节奏计划和预算原文件不再重复塞给主创。角色输出事件与历史读模型只读已有缓存，不新增创作模型调用。

## 全书结构权责与实施

顶层 Agent 负责理解用户目标、提出或更新全书方向与关键取舍；主创规划 Agent 将方向落实为叙事模式、视角、时间组织、章节转向、场景安排和详略权重。顶层 Agent 不需逐场代填微观结构，主创也不因固定六种节奏角色或统一场景负载而失去形式选择。

`lean_project_plan.json` 保存 `narrative_design`、各场 `story_time` 和相对长度权重；预算按权重重新分配，仍守住总量。未来重规划可在第一场提交前调用，也可保留已提交前缀并改写后续场景。主创每场收到全篇主轴与本章转向的短摘录。固定 `scene_load`、六个转折位置和类型比例预设已移除。

角色推演会话逐轮落盘；主创可在每轮 direction 中增加外部变化与角色当下可知信息，正文写作或修订时也可按需请求角色续演、环境补写。推演窗口从同一缓存读取历史、从 SSE 接收完整公开回合；私人内心与原始模型消息不入前端。

## 初始化标签试跑反馈

顶层 Agent 的修改前基线确实生成 `PUBLIC_SPARE_SENTENCES`、`VOICE_HALF_SENTENCE_AT_EMOTION` 这类压低人物语言能量的标签，并把雨后、电台、潮湿磁带等场景意象写入环境首条。主创提示现明确区分稳定人格、外显个性与语言气质；具体剧情责任放在 `actor_tasks` / 轮间 direction。环境首条改为抽象观察与修辞技法，场景物象由后续输入承载。保存人物标签仍供主创参考，但本场实际初始化使用主创写成的 `actor_prompts`，避免执行时被旧标签覆盖。未增设标签审查器。

## 验证与未证实

已通过相关后端单元测试、前端 252 项测试、Pi worker 109 项测试、客户端构建与架构审计。推演窗口的桌面和窄屏 Playwright 可视测试已通过。真实模型能否形成足够鲜明的人物语言仍须以修改后的顶层 Agent 正式场景试跑判断，不能由合同测试替代；该结果另记测试报告。
