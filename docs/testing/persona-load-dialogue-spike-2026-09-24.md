# 标签式人格初始化：逐轮对戏试验（2026-09-24）

> 历史基线：本轮使用中英混合标签，尚未挂载后续 `[LANGUAGE_STYLE]`。当前格式和对戏结果见 `actor-persona-english-tags-2026-09-24.md`、`actor-language-style-default-2026-09-24.md`。

## Module Change Packet

```yaml
module_change_packet:
  objective: "用主创实模生成的人格载入块运行双角色逐轮对戏，并留下可复核原文"
  primary_module: "workers/pi-worker/ 的隔离对戏试验脚本"
  public_entry: "scripts/actor-roleplay-spike.mjs --persona-load <director-run-events>"
  variation_point: "角色首条消息读取指定主创运行的 actor_prompts；对戏来话、模型和回合数保持原试验"
  inputs: ["已存在的主创运行事件文件", "新输出目录"]
  outputs: ["transcript.json", "materials.md", "阅读性结论"]
  invariants: ["无项目工具和正式写权", "不改正文、Canon 或人物资产", "对戏原文不人工润色"]
  allowed_dependencies: ["现有 Pi Agent Core 试验入口和运行事件"]
  forbidden_dependencies: ["正式 TaskPackage/晋升", "新模型调用抽象", "新审查门禁"]
  tests: ["脚本语法", "完整七轮实跑", "首条提示与源计划逐字相符", "与旧版同来话对照"]
  rollback_unit: "试验脚本新增模式"
  documentation: ["本记录"]
```

## 结果

使用 `deepseek/deepseek-v4-flash`、`medium` 思考、无工具的两条持久 Agent 会话，对同一雨夜记忆载体交接场景跑完七轮。角色首条消息逐字取自前一轮主创实模计划 `build/scene-performance-e2e/actor-persona-block-director-v3-20260924/studio-data/worker/runs/run-1790260852575/runtime.events.jsonl` 的 `actor_prompts`；核对周岑和许遥均完全相同。旧版 `directed-cute-catgirl-immersive5` 的第一轮场上来话与本轮相同；后续来话使用同一模板，但嵌入的上一轮回复自然不同。两角色七轮都有非空原始回复。完整首条提示、各轮来话、原始回复与会话 ID 见 `build/scene-performance-e2e/interactive-roleplay-persona-load-20260924/transcript.json`，阅读版见同目录 `materials.md`。试验只生成隔离候选，没有改写作品正文、人物资产或 Canon。

与旧版七轮对戏相比，原始回复总长度由 2935 增至 4717 字符（约 +61%）；周岑由 1421 增至 3015，许遥由 1514 增至 1702。数字只描述这一对样本，不构成新初始化单独造成改进的因果证明：人格内容也改变了，两轮的后续来话并非逐字相同。

文学观察：许遥会回击周岑的“排异级别”术语，在第四轮否定他给出的两条路并主动提出直连，有明确的互动自主性和比周岑更俏皮的语气。周岑则持续以程序、权属、复检和风险清单说话，两人的声音能区分，但两人都常用“第一、第二”“代价你听清楚”式技术说明。长度增长主要变成流程阐释和动作铺排，未同步转化为情绪层次或更生动的语言。周岑第五轮已交代锁定、复检关闭、索引不可见，第七轮又大段复述；末轮还没有真正接住许遥第六轮“我去跟巡逻说，你从检修门走”的行动提议，而是再次让她走、自己出面。角色反复临场确定未经来源确认的事实，例如排异/船籍链细则、离港窗口“不到四十分钟”、落点“三号民用坪”。这些都只能是待主创筛选的候选，不能误当已定世界规则。猫耳、尾巴动作亦高频出现，偶有装饰化倾向。

结论：标签式初始化足以维持七轮对戏，也明显缓解了周岑的“惜字如金”；它尚未解决技术化复述、情绪渲染不足与临场补造世界事实。后续若要优化，应先观察主创如何取舍演员素材，而不能仅凭这一轮字符数增加判断文风成功。验证：`node --check`、Pi Worker `npm run check`（11 组、108 测试）、架构审计和 `git diff --check` 均通过。
