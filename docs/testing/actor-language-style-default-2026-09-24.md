# 角色人格初始化默认挂载 LANGUAGE_STYLE（2026-09-24）

## Engine Module Change Packet

```yaml
module_change_packet:
  objective: "每个角色首条人格初始化默认追加用户指定的三个英文语言风格标签"
  primary_module: "literary/scene/roleplay"
  public_entry: "public.literary.render_actor_initialization_prompt"
  variation_point: "未显式提供 LANGUAGE_STYLE 区块时追加默认区块；已有区块原样保留"
  inputs: ["主创的英文大写人格块"]
  outputs: ["人格块与默认 LANGUAGE_STYLE 首条消息"]
  invariants: ["标签只影响生成", "场景任务单仍为后续消息", "不增加审查或阻断规则"]
  allowed_dependencies: ["现有 Engine roleplay 合同测试"]
  forbidden_dependencies: ["Studio Runtime", "Provider SDK", "新文学 Gate"]
  tests: ["默认挂载精确文本", "自定义区块无重复", "真实角色对戏"]
  rollback_unit: "Engine 首条提示默认区块增量"
  documentation: ["本记录"]
```

## Studio Module Change Packet

```yaml
module_change_packet:
  objective: "默认 LANGUAGE_STYLE 变化后不复用旧角色候选缓存"
  primary_module: "runtimes/scene_performance"
  public_entry: "scene_performance_materials"
  variation_point: "仅递增场景表演候选缓存版本"
  inputs: ["已有主创计划和场景上下文"]
  outputs: ["新缓存键"]
  invariants: ["正文晋升与 Canon 路线不变"]
  allowed_dependencies: ["Engine public.literary"]
  forbidden_dependencies: ["Engine internal", "新 Gate"]
  tests: ["定向 Runtime 回归", "缓存版本检查"]
  rollback_unit: "Studio 缓存版本增量"
  documentation: ["本记录"]
```

## Worker Experiment Module Change Packet

```yaml
module_change_packet:
  objective: "隔离对戏脚本与生产初始化的默认语言标签保持一致"
  primary_module: "workers/pi-worker/ 的隔离对戏试验脚本"
  public_entry: "scripts/actor-roleplay-spike.mjs --persona-load"
  variation_point: "读取主创人格块后，若缺少 LANGUAGE_STYLE 则追加同一默认区块"
  inputs: ["既有主创 actor_prompts", "新输出目录"]
  outputs: ["可复核七轮 transcript"]
  invariants: ["不修改主创源记录", "无正式写回或工具权限"]
  allowed_dependencies: ["现有试验脚本"]
  forbidden_dependencies: ["正式晋升", "额外模型调用"]
  tests: ["脚本语法", "首条消息核对", "七轮实跑"]
  rollback_unit: "试验脚本默认标签增量"
  documentation: ["本记录"]
```

## 结果

生产 `render_actor_initialization_prompt` 现对没有显式 `[LANGUAGE_STYLE]` 的人设块，在末尾追加：

```text
[LANGUAGE_STYLE]
ANTI_PLAIN
ANTI_SIMPLISTIC
ANTI_SHORT_SENTENCES
```

已有 `[LANGUAGE_STYLE]` 的主创人设块原样保留，不叠加第二份。原三个 `【...】` 人格区块和独立 `ANTI_CONCISE` 均保留；这些标签只在角色生成时起作用，不进入静态审查。候选缓存由 `performance-v29` 升至 `performance-v30`。隔离对戏脚本也按同一缺省规则追加该块。

真实模型测试使用上一轮同一份纯英文人格块，首轮场上来话与未挂载语言风格区块的试验逐字相同。七轮均有非空回复；两名角色的完整首条消息均与生产渲染函数输出逐字一致，各有且仅有一个 `[LANGUAGE_STYLE]`，标签行不含中文。原始记录见 `build/scene-performance-e2e/interactive-roleplay-english-style-default-20260924/transcript.json`，阅读版见同目录 `materials.md`。角色总回复从 5296 增至 6644 字符（周岑 2765→3652，许遥 2531→2992）。句子和环境/心理停留更舒展，但增长主要是动作、物象与流程解释；人物对白仍反复围绕核验、风险、报酬和航线展开，未自动变得鲜活。第五轮虽宣称载体接入终端并锁定，第六轮仍留有木盒在桌上的描写，显示新标签不能替代主创的情节修订。角色还补出“十七分钟”“多烧两成燃料”等未经确认的具体数据。两轮除默认区块外起始人设相同，但后续来话包含各自上轮回复，因此长度变化只是这次实验的观察，不是因果证明。

正式角色任务单窄测：用生产函数生成的许遥首条消息，加原未改动的结构化任务单，得到 `scene_0001` / `许遥` 的 9 条候选；现有 JSON 解析器及角色材料合同通过。原始记录见 `build/scene-performance-e2e/actor-persona-english-style-task-sheet-20260924/studio-data/character-actor/runs/run-1790262568913/`。所有输出都只保留为隔离候选，没有写回正文或 Canon。

验证：50 个相关 Python 测试、Pi Worker 108 个测试、脚本语法、Python 编译、架构审计、模块图、提示资产验证与 `git diff --check` 均通过。
