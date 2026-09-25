# 创作提示词全链路盘点与精简

这轮把提示词当成给写作者的交接纸：事实、归属和交稿格式要说清，表达选择不必在每张纸上重复规定。已精简默认文风、主创成稿/修订/补写、反 AI 生成提示和正式路线的文风说明；角色初始化格式、环境写手的自由描述、审查硬规则与完整参考语料保留。

## 范围与判断

盘点运行时主创成稿、修订、补写、角色、环境、顶层 Agent、资产初始化、默认文风、文风编译、正式任务动态提示，以及注册的 59 份 route prompt asset 和 10 份旧模板。按实际创作链路区分：正文生成的软表达提示可精简；Canon、人物事实、候选归属、输出结构、中文标点与违禁表达属于合同或硬语言边界，不因“去工程化”而删。

主要发现：

1. 默认文风、主创成稿与补写三处重复要求句法变调、心理展开、修辞选单和证据之后停笔。重复的抽象清单会让模型把文学选择当成逐项交作业，正文因此容易平均用力。
2. 补写提示同时要求固定插入位置、目标字数和若干修辞类型，容易把本应自然生长的段落写成填空；保留篇幅与事实合同，但把表达选择交回主创。
3. 默认反 AI 提示中的“同一件事说一遍即可”容易把情绪递进误判为重复，应区分无信息增量的复述与有变化的回环。
4. `route.scene-development.revision.v1` 仍要求精确数值通过“五项必要性测试的每一项”，与当前语义规则的一项实际功能足够相冲突，必须改正。
5. 顶层 Agent 与资产初始化提示虽长，主要承载权限、项目事实及结构输出；注册的多数正式任务资产正文简短。没有证据表明删去这些合同会改善文风，本批不进行无差别压缩。
6. 文风编译器要求每一节都写“做什么、为什么、何时例外、如何自检”，会把给写作者的提示写成逐项说明书；其干跑预设还把心理优先引向动作。已让它保留原有板块和硬边界，但每节只留下会改变创作选择的内容。

角色初始化的英文标签和默认 `[LANGUAGE_STYLE]` 是此前明确指定的格式；逐轮对演、单人场景、环境候选已有自主空间。环境候选每段 600 字及角色 entries 数量是解析合同，不是单纯文风叮嘱，本轮不借“精简提示词”暗改这些数据结构。

## Module Change Packets

```yaml
module_change_packet:
  objective: "默认文风和反 AI 生成提示不再重复劝说清简与修辞清单"
  primary_module: "Engine literary/style"
  public_entry: "default-clear-plain/prompt.md 与 ANTI_AI_STYLE_PROMPT"
  variation_point: none
  inputs: ["场景事实", "文风挂载", "项目语言规则"]
  outputs: ["正文生成阶段文风提示"]
  invariants: ["违禁表达与标点仍进入审查", "数值语义合同不变", "不新增软门禁"]
  allowed_dependencies: ["现有 Style Skill 与语言规则"]
  forbidden_dependencies: ["Studio Worker", "审查规则重写"]
  tests: ["默认文风预设", "AI 文风提示合同", "Prompt registry"]
  rollback_unit: "默认文风生成提示精简"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "主创成稿与续写提示只表达一次软文学方向，保留场景事实和输出合同"
  primary_module: "Studio runtimes/pi_scene_transaction"
  public_entry: "render_scene_create_prompt / render_scene_revision_prompt / render_scene_length_completion_prompt"
  variation_point: none
  inputs: ["SceneBrief", "来源", "角色环境候选", "正文及审读证据"]
  outputs: ["成稿、修订与续写提示"]
  invariants: ["主创独占正式正文", "角色外显言行来源不变", "SceneDelta 与长度合同不变"]
  allowed_dependencies: ["Engine public.literary", "现有 prompt recipe"]
  forbidden_dependencies: ["新 Gate", "项目事实直接写入"]
  tests: ["test_lean_kernel_v2_pi_runtime", "test_scene_interaction"]
  rollback_unit: "lean 主创提示精简"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "正式修订 prompt asset 的数字语义与当前规则一致"
  primary_module: "Engine prompting"
  public_entry: "route.scene-development.revision.v1"
  variation_point: none
  inputs: ["正式候选", "审读意见", "已确认数值"]
  outputs: ["正式修订任务提示"]
  invariants: ["精确候选审读与晋升路线不变", "有意义的精度保留", "无意义实写可修订"]
  allowed_dependencies: ["现有 prompt asset registry"]
  forbidden_dependencies: ["Studio Runtime", "数字 Gate 放宽或绕过"]
  tests: ["prompt-registry-validate", "正式资产版本测试"]
  rollback_unit: "正式修订数字规则纠偏"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "文风编译时不再生成逐节四栏说明书或动作优先的心理提示"
  primary_module: "Engine literary/style"
  public_entry: "style prompt compiler 与 dry-run preset"
  variation_point: none
  inputs: ["style profile", "metrics", "corpus manifest"]
  outputs: ["可挂载文风提示词"]
  invariants: ["原有板块与长度合同不变", "违禁表达和标点审查不变"]
  allowed_dependencies: ["现有 Style Skill"]
  forbidden_dependencies: ["新 Gate", "语料改写"]
  tests: ["style prompt preflight", "default style preset", "prompt compiler"]
  rollback_unit: "文风编译指令精简"
  documentation: ["本文"]
```

## 验证边界

默认文风模板从约 2700 个字符缩到约 1600 个字符。定向合同测试 108 项通过；完整 Python 测试 1582 项通过、1 项跳过。59 份提示资产注册校验、架构检查、模块地图检查和编译均通过。正式修订提示不再要求数值同时通过五项测试，改为一项真实语境功能即可保留。没有新增门禁，也没有改动违禁表达、标点和数字的审查代码。

这些检查只能证明新文本能装载、合同仍在，不能证明小说语感已经改善。效果还需用新场景对照人物声音、句群呼吸、解释性复述和事实准确性。旧场景和已挂载的不可变文风版本不会被静默改写。
