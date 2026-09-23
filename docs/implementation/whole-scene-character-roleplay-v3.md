# 整场角色扮演与人物语言优先级

状态：2026-09-23，已实施并验证。范围仅限 opt-in 的 lean-v2 场景候选生成；主创正文、Canon、审查规则和默认开关不变。

## 问题与决定

现有 Worker 系统提示已有通用的第一人称角色要求，不能把“没有进入系统提示”当作完整病因。真正欠缺的是：稳定语言风格在动态任务里靠后、表述温和；同一人物的每个节拍分别启动一次会话，既重复消耗调用，也让语气、称呼和受压变化无法贯穿整场。上一轮真实试跑还暴露人物资产本身趋向同一套职业流程语言，因此提示词修正不保证自动产生鲜明对白。

本次把“人物声音优先于中性助手解释腔”写入白名单 `character-actor` 的静态系统提示；人物身份、知识与语言资产仍作为明确分区的角色输入，不把任意项目文本提升为系统指令。系统提示承诺如何扮演，而动态任务单提供扮演谁。每名说话人物只启动一轮，收到按剧情顺序排列的该人物全部节拍，连续扮演并一次返回各节拍的唯一台词、动作和内在冲动。主创仍负责交错编排、补足剧情义务和最终正文。

## Module Change Packets

```yaml
module_change_packet:
  objective: "同一人物在一轮会话内连续扮演整场，并把语言声音放在演员输入最显眼处"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_actor_scene_prompt、parse_actor_scene_material"
  variation_point: "ActorSceneMaterial/v3；每个 speaker 对应 1..4 个顺序节拍"
  inputs: ["SceneBrief", "已锁定的该人物节拍", "现有人物声音投射"]
  outputs: ["按 beat_id 对齐的 spoken、first_person_action、private_impulse 候选"]
  invariants: ["每节拍只交一个候选", "不替别人说话", "不改变剧情与事实", "演员没有正文/Canon 权限", "不新增文学硬门禁"]
  allowed_dependencies: ["现有场景合同和人物声音投射"]
  forbidden_dependencies: ["Studio 内部", "Provider SDK", "项目持久化"]
  tests: ["整场角色提示覆盖声音连续性", "缺失/重复/越界节拍拒绝", "单节拍兼容"]
  rollback_unit: "与 Studio/Pi 适配一起回滚的可运行提交"
  documentation: ["本记录"]
```

```yaml
module_change_packet:
  objective: "每人物一次候选调用、缓存和失败隔离"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "scene_performance_materials、scene_creative_cache_digest"
  variation_point: "从逐节拍调用改成按 speaker 分组调用"
  inputs: ["SceneBrief", "PerformancePlan", "ActorSceneMaterial/v3"]
  outputs: ["沿原按节拍形状传给唯一主创的候选块"]
  invariants: ["候选调用上限按人物调用次数计", "演员失败不阻断主创", "旧缓存失效", "只由主创写正文"]
  allowed_dependencies: ["Engine public/literary.py", "现有 RoleConversationGateway"]
  forbidden_dependencies: ["Engine 内部 import", "第二套项目写入"]
  tests: ["同人物两节拍只调用一次", "跨人物顺序", "缓存命中", "失败回退"]
  rollback_unit: "与 Engine/Pi 一起回滚的可运行提交"
  documentation: ["本记录"]
```

```yaml
module_change_packet:
  objective: "让人物语言在角色扮演系统提示中具有清晰优先级"
  primary_module: "workers/pi-worker conversation"
  public_entry: "conversationSystemPrompt(character-actor)"
  variation_point: "白名单静态演员系统提示，不开放自定义 system prompt"
  inputs: ["白名单 conversation_role", "Engine 提供的角色输入"]
  outputs: ["ActorSceneMaterial/v3 JSON 候选"]
  invariants: ["tools=[]", "单轮", "无项目写权限", "事实和行动边界优先于文风"]
  allowed_dependencies: ["现有 Pi conversation profile"]
  forbidden_dependencies: ["任意项目文本注入系统提示", "项目工具", "Provider 特判"]
  tests: ["连续扮演/风格优先级/无工具断言", "其他 profile 回归"]
  rollback_unit: "与 Engine/Studio 一起回滚的可运行提交"
  documentation: ["本记录"]
```

## 验收与风险

先运行结构、缓存、Worker 和架构测试，再以同一场景做真实模型抽样；样本需展示按人物一次调用的原始候选和主创所见的候选块。质量只作为实验观察，不以“必须有特定修辞/口癖”建立硬门禁。若人物档案本身同质化、演员自造物件或主创抹平声音，均应单独记下，不能宣称提示词已解决。

本实现中的“整场”是**本场导演已规划的该角色全部发言节拍**，而非承诺枚举整场正文中每一句对白。当前导演上限是四个关键节拍；未规划的过渡对白仍归唯一主创。`max_actor_calls` 现在按不同说话人物的会话次数计，而不是按节拍计。角色输出必须与节拍顺序一一对应；主创所见素材再按全场节拍顺序排序。版本从 `scene-performance/v2` 到 `v3`，候选和正文缓存均刷新。原 `render_actor_prompt` 作为单节拍便捷入口保留，但其输出合同也已是 v3。

## 真实模型观察

以《shoreline》测试项目旧控制室场景、从周鹤人物卡压缩摘出的身份和声音投射，对 `deepseek/deepseek-v4-flash` 做两次单人双节拍调用（非完整端到端正文，也非正式作品）。两次均在一个回答中交出 `b1`、`b3` 各一条台词、第一人称动作与冲动，解析通过。初版 `b1` 为“……等一下。刚才那句，你再往下读一行。就一行。”，但 `b3` 又滑向“稿面在，播出记录在……都有留档”的程序解释，并将未确认的留档当成事实。补上“职业词不是每句标记、职业惯例不是现场证据”的生成提示后，第二次样本变为：

> b1：“……这里。不是设备故障。”
>
> b3：“空着……也正常。台里有些临时操作，事后不一定补签。你问这个，是丢了什么吗？”

第二次结尾有针对沈照月身份误判的反问，比前一次更像人物在对方身上行动；但“临时操作事后不一定补签”仍可能暗示未经确认的工作规则。两次随机抽样不能证明提示词造成质量提升，且此人物卡本身以程序术语定义声音，后续仍需同题多样本盲评、事实核对和主创正文采用率比较。没有将这些候选晋升 Canon 或写入正式正文。

验证：最终 Python 全量复测 `1536` 项完成、`1` 项跳过；定向场景测试 `13` 项通过，Pi Worker `106` 项通过。架构审计、模块图、Prompt Registry（59 资产/73 ID）、`compileall` 及 `git diff --check` 通过。
