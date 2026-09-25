# 创作提示词的防错尾巴清理

## 判定

本轮检查全部创作入口：主创成稿、修订、补写、角色规划与对演、环境写手、顶层 Agent、资产初始化、文风模板与编译器、正式任务动态提示、注册 Prompt Asset 和旧模板。目标是清除同一指令里“做 A；不要做 B”的预防性尾巴。按用户补充要求，尾巴直接删除，不移到新设的“边界”段，也不换一种否定措辞重新写入。原本独立存在的禁令，以及 Canon、角色言行归属、输出结构、违禁表达、标点等硬合同，仍按其原有职责保留。

检索命中并不等于缺陷。例如“不可越过视角人物可知范围”本身就是边界；小说参考语料中的否定句是作品文本，不属于提示词。按语义逐项判断，不做字符串批量替换。

## Module Change Packets

```yaml
module_change_packet:
  objective: "直接删除默认文风与文风编译正向指令后的预防性否定尾巴"
  primary_module: "Engine literary/style"
  public_entry: "default-clear-plain/prompt.md 与 style prompt compiler"
  variation_point: none
  inputs: ["文风资料", "场景与人物", "既有硬语言规则"]
  outputs: ["默认与生成的文风提示"]
  invariants: ["R01—R25 完整语料保留", "违禁表达、标点、数字审查不变", "挂载版本不可变"]
  allowed_dependencies: ["现有 Engine 文风合同"]
  forbidden_dependencies: ["新 Gate", "Studio Runtime"]
  tests: ["default style preset", "anti AI style", "style prompt preflight"]
  rollback_unit: "文风提示尾巴清理"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "直接删除主创、角色与环境创作指令后的预防性否定尾巴"
  primary_module: "Engine literary/scene 与 Studio runtimes"
  public_entry: "scene create/revise/completion 与 roleplay prompt renderers"
  variation_point: none
  inputs: ["SceneBrief", "角色档案", "对演资料"]
  outputs: ["创作阶段提示"]
  invariants: ["一级角色言行归属不变", "主创正文责任不变", "SceneDelta 和 JSON 合同不变"]
  allowed_dependencies: ["现有提示渲染入口"]
  forbidden_dependencies: ["新解析器", "门禁扩张"]
  tests: ["lean scene runtime", "scene performance", "scene interaction"]
  rollback_unit: "场景提示尾巴清理"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "直接删除正式路由与顶层对话中正向指令后的预防性否定尾巴"
  primary_module: "Engine prompting 与 Studio project_agent"
  public_entry: "Prompt Asset / platform task text / project agent policy"
  variation_point: none
  inputs: ["正式任务合同", "用户方向", "工具状态"]
  outputs: ["任务提示与用户对话策略"]
  invariants: ["任务权限和 formal provenance 不变", "工具与写回边界不变"]
  allowed_dependencies: ["现有任务与顶层 Agent 合同"]
  forbidden_dependencies: ["新增流程限制", "审查放宽"]
  tests: ["prompt registry", "project agent prompt", "platform task"]
  rollback_unit: "正式与顶层提示尾巴清理"
  documentation: ["本文"]
```

## 验证记录

已盘点 59 个注册 Prompt Asset、10 个旧模板，以及文风编译、顶层对话、主创、角色、环境、动态任务提示。正向创作指令后的软性防错尾巴直接删除；原本独立的审查禁令、输出格式、来源与写回合同保留。清理范围内没有新门禁。资源文本版本随更改更新，相关断言改为验证正向目标与原有硬约束。

追加需求：角色 Agent 首条初始化增加 `[LITERATURE_STYLE]`，由主创填写高度概括的作者式或文学流派标签，可兼有；随后统一附上用户指定的三条角色沉浸要求。保存的人物标签开放第五区块，旧四区块档案读取时按空文学风格区块兼容。标签由主创在导演阶段确定，具体场景互动继续通过后续消息传达。

路线收敛：正式创作只使用逐轮对戏。旧配置中的 `mode: whole-scene` 不再选择整场任务单；逐轮对戏失败后也不回退到一次性整场任务单。创作缓存版本更新，以免复用旧模式素材。无可用演员素材时，现有主创候选生成行为照旧，未增加新阻断。

验证：Python 全量回归 1578 项通过、1 项跳过；最终拼写与运行路线调整后，架构、Prompt 编译、角色初始化、逐轮对戏等定向回归 99 项通过。Pi Worker 编译通过，109 项测试通过；`verify_checkout_import.py` 与 `git diff --check` 通过。运行检查只能证明提示可装载、流程未破坏；文学风格效果仍需真实场景试读。
