# 独立场景创作与自由文风实验记录

## Module Change Packet

```yaml
module_change_packet:
  objective: "让真实角色/环境素材参与一场测试场景，并使生成提示由清简偏向有节奏、有情绪空间的自由表达"
  primary_module: "Engine literary/scene/roleplay performance prompts"
  public_entry: "literary_engineering_studio_engine.public.literary 中的 render_actor_scene_prompt、render_environment_prompt、render_performance_materials"
  variation_point: "调整角色/环境/主创及长度续写的生成提示；允许主创改写已有角色台词的措辞，但保留原角色发言意图与回合来源；移除缺失 speech_style 时的通用清简默认语；测试副本挂载已有弹性默认文风，不改调用模型的 Runtime SPI"
  inputs: ["SceneBrief", "expression/dialogue_intents", "selected style references", "confirmed sources"]
  outputs: ["角色整场 entries", "环境 passages", "主创整合的 CreativeResult"]
  invariants: ["角色素材无项目写权", "主创是正文唯一作者", "人物发言意图/回合与可见动作归属一级角色，具体台词可由主创改写", "Canon 与已知事实不扩大", "违禁词和标点仍在审查"]
  allowed_dependencies: ["Engine literary/scene/composition", "Engine literary/scene/roleplay", "Engine public/literary", "Studio runtimes/scene_performance", "Studio runtimes/scene_performance_ownership", "Studio runtimes/pi_scene_transaction", "Studio runtimes/scene_length_completion", "Studio runtimes/pi_scene_review_prompt", "定向合同测试"]
  forbidden_dependencies: ["Engine 反向依赖 Studio", "新 Provider 客户端", "第二套 Gate", "在测试中改全局用户配置"]
  tests: ["tests/test_scene_performance_agents.py", "tests/test_lean_kernel_v2_pi_runtime.py", "真实 Pi 模型隔离场景 E2E"]
  rollback_unit: "本批独立 Git 提交"
  documentation: ["本实验记录", "可核对的角色、环境、主创三层原始产物"]
```

## 测试边界

测试复用“雨港离航”源场景与人物资产，在隔离项目和隔离 Pi cache 中运行。只在内存配置启用 `scene_performance_agents`，不改用户当前应用配置、不覆盖原项目正式正文。先保留原挂载风格作为真实基线；看到角色素材、环境素材与整合稿后，再修改提示，重跑一个不同 transaction id，最后做同场对照。失败需记录真实 provider/协议错误，不用假素材代替真实调用。

## 实际试跑与晋升

本轮使用 Pi Worker 的 `deepseek/deepseek-v4-flash`。三次隔离试跑均由真实的角色、环境和主创调用生成；未由开发者写正文。最初的 `independent-performance-20260924` 使用原“清简”挂载，主创约 2990 字，环境与对白多为功能性片段。切换到现有默认“弹性叙事”挂载后的 `independent-free-style-20260924` 得到约 3275 字的整合稿，但新增无来源技术细节，且一次主创修订陷入旧逐字台词归属规则的四轮回修。针对该阻断，已让主创可改写角色已有台词，并取消逐字比对；新对话回合与动作仍需一级来源。

`independent-free-style-rerun-20260924` 在新提示下重跑独立素材：4 个场景锚点、周岑 9 条与许遥 7 条角色 entries、环境 4 段，主创首稿约 2760 个中文正文字符。周岑这次在自己的 `first_person_action` 中完成直连，不再把关键操作留给主创补做。原首稿的机械对照句、标点及文风问题触发返修。主创的第二轮实时修订把角色原台词“不是吓你，是……”改写为“这东西没在你那边校准过……”，没有新增问答回合，证明改台词权限已被实际使用。它没有显著重组全场：最终正文 2525 个中文正文字符，仍低于 2700 的软建议下限。

最终稿按项目 `creative_quality_profile` 完成确定性核验：`can_commit=true`，软字数与句法/标点节奏仅为 warning；独立文学审读为 `pass`。标准风险的场景无需额外 steward 批准，原子晋升写入隔离项目的 `drafts/scenes/scene_0001.md`、`workflow/scene_deltas/scene_0001.json`、`workflow/continuity/current.json`、`canon/facts.json`、`canon/timeline.yaml` 与 `workflow/scene_commits/scene_0001.json`。晋升后的正文与模型输出除末尾换行外相同。此处的“晋升”指精简场景事务的正式提交，不冒称旧版 `task-next` 路由的 `route-audit` 已通过；旧路由的不同候选不能用作本稿的晋升证据。
提交回执的正文哈希已与落盘文本（忽略交付末尾换行）核对一致。整书审计尚不能通过：测试副本没有 `chapter_0001` checkpoint，属于未完成章级路线，不影响本次单场景事务提交的真实性。

角色/环境素材形成于改写权限落地之前。为验证**同一批真实素材**上的主创修订，本地实验调用复用其原 transaction 缓存，没有重新调用角色与环境；主创修订、动作来源核对和最终审读都是真实 Pi Worker 调用。产品缓存版本已经提升，后续新事务不会错误命中这些旧提示结果。

## 晋升后人工检查：审查通过不等于文学目标达成

- 改写能力生效，但改写范围很窄。周岑与许遥仍大量用短句互相讲解技术流程，如“你的终端。直连。”“接上了。别动——它在写。”以及连续两次“取不出来了”。两人的身份与关切不同，声音却时常落在同样的任务问答和结论复述上。主创修订提示虽然允许全场重组，实际只做局部止损。
- 环境素材提供了较完整的声光层次，但四个锚点各交一段，主创也几乎按顺序植入。雨、霓虹、广播、巡逻声多次完成相似的压力提示，读感有堆叠；语言的长短变化主要来自长环境段与短功能对白的交替，而非人物内在运动。
- `SceneBrief` 确认的是直连、载体锁定、无法取出、航线余量重算等结果；“短接缆”“退载键”“航线余量投影”“未校准会碎得更彻底”等更细的设备结构和规则没有明确的原始来源。角色候选先行提出这些细节，主创沿用，独立审读仍判通过。这是素材非权威原则与实际审读之间的缺口，不能把本稿当作世界设定可靠的样本。
- 文中“他不想承认自己在拖”“他想骗自己说这是流程的一部分”直接解释心理，结尾又以“他也还能当这件事没结束”说明已由物件和沉默传达的意思。比原稿有心理内容，但仍非充分的、随关系变化展开的视角经验。

因此，本轮工程结论是“主创改台词和完整事务晋升可用”，不是“去 AI 味与人物语言多样化已解决”。下一轮应重点检验主创收到**具体文学损害反馈**时能否真正重排对白、视角与素材，而不是继续增加审查门禁。保留本次成稿作为可复现的失败/部分成功对照样本，不覆盖原项目正文。

## 工程验证状态

相关定向测试 92 项通过；模块映射 `--check` 与提示词注册校验通过，`git diff --check` 通过。全套 `run_tests.ps1 -q` 执行 1563 项，失败 1 项：`test_architecture_audit` 指向 `literary/planning/contracts.py::scene_word_budget_contract` 超出既有函数预算（187/184 行、复杂度 45/44）。该文件及对应字数预算测试在本轮开始前已有未提交改动，与角色/环境/主创提示和台词权限修改不重叠；本轮未擅自覆盖。独立运行架构审计得到同一项失败。此状态不能报告为“全套测试通过”。
