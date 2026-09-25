# 人格载入标签改为纯英文大写（2026-09-24）

> 本记录的七轮对戏尚未挂载后续新增的 `[LANGUAGE_STYLE]` 默认区块；当前缺省试验见 `actor-language-style-default-2026-09-24.md`。

## Engine Module Change Packet

```yaml
module_change_packet:
  objective: "角色首条人格载入中的标签词只用大写英文字母和下划线"
  primary_module: "literary/scene/roleplay"
  public_entry: "public.literary.render_performance_plan_prompt / render_actor_initialization_prompt"
  variation_point: "主创将中文人设意译成英文大写标签，姓名用拼音；首条提示不再把中文接在英文前缀后"
  inputs: ["人物档案和主创资料", "主创生成的 actor_prompts"]
  outputs: ["纯英文大写标签的人格载入首条消息"]
  invariants: ["三个区块和空行形式保留", "中文姓名、剧情信息仍可在第二条任务单中出现", "不增加文学审查门禁"]
  allowed_dependencies: ["现有 Engine roleplay 和合同测试"]
  forbidden_dependencies: ["Studio Runtime", "Provider SDK", "人工固定角色翻译表"]
  tests: ["首条消息合同测试", "主创提示样例没有中英混合标签", "真实主创计划输出检查"]
  rollback_unit: "Engine 角色载入文本增量"
  documentation: ["本记录"]
```

## Studio Module Change Packet

```yaml
module_change_packet:
  objective: "新英文标签提示不复用旧中文标签候选缓存"
  primary_module: "runtimes/scene_performance"
  public_entry: "scene_performance_materials"
  variation_point: "仅递增创作候选缓存版本"
  inputs: ["当前角色计划和创作上下文"]
  outputs: ["新缓存键"]
  invariants: ["角色任务单、工具权限和正文晋升路线不变"]
  allowed_dependencies: ["Engine public.literary"]
  forbidden_dependencies: ["Engine internal", "新的 Gate"]
  tests: ["相关 Runtime 合同测试", "缓存版本检查"]
  rollback_unit: "Studio 缓存版本增量"
  documentation: ["本记录"]
```

## 结果

主创提示示例及说明现明确要求：每条标签只用 `A–Z` 和 `_`，中文姓名转大写拼音，人物性情意译成英文词组；区块标题与空行形式不变，字段名称和数量仍由主创按角色设计。`render_actor_initialization_prompt` 原样传递完整块，并做轻量词法校验；不再把旧版中文短气质拼接为 `TRAIT_中文`。旧版缓存由 `performance-v28` 升为 `performance-v29`。此处校验是首条提示的输入格式，不是正文文学审查或新晋升门禁；不合格的主创计划不会被伪装成合格角色初始化。

真实模型窄测：`deepseek/deepseek-v4-flash` 为许遥、周岑生成了可解析的主创计划；两个人格块的每个标签均满足 `^[A-Z_]+$`。例如许遥是 `SELF_CLAIM_XU_YAO`、`SPECIES_CATKIN`、`TRAIT_LOYAL_BUT_GUARDED`，周岑是 `SELF_CLAIM_ZHOU_CEN`、`TRAIT_STUBBORN_UNDER_CALM`。原始记录见 `build/scene-performance-e2e/actor-persona-english-director-20260924/studio-data/worker/runs/run-1790261981977/`。

随后以这两个真实人格块作为各自持久角色会话的第一条消息，沿用此前七轮交接场景的来话模板，完整跑通七轮，两人每轮均有非空中文回复。两条初始化与主创输出逐字相同；首轮场上来话与上一轮中英混合标签试验逐字相同。完整记录见 `build/scene-performance-e2e/interactive-roleplay-english-tags-20260924/transcript.json`，阅读版见同目录 `materials.md`。两轮总回复由 4717 增至 5296 字符，但角色人格内容与后续动态来话也改变，不能把长度变化归因于标签语言。文学上并未改善：许遥第二轮列出六项交接要求，周岑第三轮逐项复述；第六轮虚构封条编号 `XC-7H-4412-09`、精确时间 `二十三点四十七分十六秒`，末轮又补出检修渠二十米、四十米等未确认参数。英文标签满足格式要求，却没有自动解决流程说明过重、角色说话不像自然对戏的问题。所有输出均为隔离候选，没有进入正文或 Canon。

验证：50 个相关 Python 测试通过；Python 编译、架构审计、模块图、提示资产验证与 `git diff --check` 通过。未改 Pi Worker 产品代码。
