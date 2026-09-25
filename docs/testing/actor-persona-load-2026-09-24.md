# 角色默认初始化改为标签式人格载入（2026-09-24）

> 历史试验记录。后续已改为纯英文大写标签，并移除中文短气质拼接回退；当前默认规则见 `actor-persona-english-tags-2026-09-24.md` 与 `actor-language-style-default-2026-09-24.md`。

## 结构解析

这是一份按空行分组的标签清单，而非带值的 JSON。`【PERSONA_LOAD】` 装载自我认同、已知偏好与语言；`【PERSONALITY_CORE】` 描述不一定直接说出口的内在倾向；`【PERSONALITY_PUBLIC】` 描述可被他人感知的气质和行为；`ANTI_CONCISE` 是鼓励充分表达的风格方向。标签名及数量随角色变化，示例里的姓名、炒饭和性格词都不是全局默认事实。孤立的 `&#x20;` 只是粘贴格式，不属于提示。

## Engine Module Change Packet

```yaml
module_change_packet:
  objective: "把角色首条初始化改为可由主创自由填写字段的四段标签结构"
  primary_module: "literary/scene/roleplay"
  public_entry: "public.literary.render_performance_plan_prompt / parse_performance_plan / render_actor_initialization_prompt"
  variation_point: "actor_prompts 文本可承载完整结构；旧版短气质仍可转换为同形默认提示"
  inputs: ["角色姓名和身份", "主创 actor_prompts 或既有短气质"]
  outputs: ["PERSONA_LOAD、PERSONALITY_CORE、PERSONALITY_PUBLIC、ANTI_CONCISE 首条消息"]
  invariants: ["场景任务单仍在第二条消息", "角色候选仍无正式正文或 Canon 写权", "不补造特定食物偏好"]
  allowed_dependencies: ["现有 Engine roleplay 合同与定向测试"]
  forbidden_dependencies: ["Studio Runtime", "Provider SDK", "新增审查门禁"]
  tests: ["结构化块原样传递", "短气质回退", "导演到角色的端到端传递"]
  rollback_unit: "Engine 角色初始化与导演提示的增量"
  documentation: ["本记录"]
```

## Studio Module Change Packet

```yaml
module_change_packet:
  objective: "新初始化不误用上一版角色候选缓存"
  primary_module: "runtimes/scene_performance"
  public_entry: "scene_performance_materials"
  variation_point: "仅递增创作候选缓存版本"
  inputs: ["现有 plan、角色档案和场景"]
  outputs: ["新缓存键"]
  invariants: ["调用顺序和晋升路线不变"]
  allowed_dependencies: ["Engine public.literary"]
  forbidden_dependencies: ["Engine internal", "新的 Gate"]
  tests: ["相关 Runtime 合同测试", "缓存版本检查"]
  rollback_unit: "Studio 缓存版本增量"
  documentation: ["本记录"]
```

## 结果

主创 `actor_prompts` 仍是每人一段文本，而非新增固定字段表；主创现在按四段标签结构填写，并可按角色调整标签、数量与内容。Engine 将结构化文本作为角色首条消息原样传递。旧版单句气质仍可转成同形结构：姓名与已有身份进入 PERSONA_LOAD，原气质进入 PERSONALITY_CORE，未有依据的 FOOD 等偏好不被补造；PERSONALITY_PUBLIC 在这种回退情况下留空。场景事实与输出格式仍只出现在第二条任务单。此前的五条编号式沉浸指令不再混入默认首条提示。

定向合同测试覆盖结构化块原样传递、任意人物字段、短气质回退以及主创提示到第一层角色 Agent 的传递。50 个相关 Python 测试、Pi Worker 108 个测试、Python 编译、架构审计、模块图、提示资产验证、`git diff --check` 均通过。Studio 候选缓存版本由 `performance-v27` 改为 `performance-v28`，使旧初始化结果不会被复用。

真实模型窄测：用 `deepseek/deepseek-v4-flash`，以许遥的独立标签式人设块作为首条消息，再发送既有未修改的原角色任务单；得到 `scene_0001` / `许遥` 的可解析 JSON，含 12 条角色候选。原始两条提示与回答见 `build/scene-performance-e2e/actor-persona-block-task-sheet-20260924/studio-data/character-actor/runs/run-1790260523573/`。这只验证新首条格式能与一次既有任务单共存，不证明文风质量或所有角色都稳定。候选没有晋升正文或写入 Canon。

随后补做主创到角色的实模链路。初版主创标签夹带“偏好未确认”的防御性占位；改为省略空字段后，第二次把标签写得过长，整份计划 JSON 截断。第三次把提示收敛为“每区只挑少数最有辨识度的标签”，主创为许遥、周岑生成可解析计划与完整人设块，且没有虚构食物偏好；记录见 `build/scene-performance-e2e/actor-persona-block-director-v3-20260924/studio-data/worker/runs/run-1790260852575/`。将该次主创生成的许遥首条消息原样发送给角色，再接未修改的原任务单，模型返回带 Markdown 代码围栏的 JSON；正式路线已有的 `_answer_payload` 解析器和角色材料合同均通过，得到 11 条候选。记录见 `build/scene-performance-e2e/actor-persona-block-director-to-actor-20260924/studio-data/character-actor/runs/run-1790260903442/`。这仍只是规划及角色素材的窄测，不是正文生成、修订或晋升路线。
