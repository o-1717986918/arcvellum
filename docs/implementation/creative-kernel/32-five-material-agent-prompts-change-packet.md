# 五类取材 Agent 文学初始化 Change Packet

```yaml
module_change_packet:
  objective: "让四类描写/叙述 Agent 各自以明确的文学创作方法响应主创委托；角色 Agent 继续只接收角色卡模板。"
  primary_module: "Engine prompting / scene.v2.material.* prompt assets"
  public_entry: "prompt_layer_spec('scene.v2.material.<kind>') and prompt snapshot used by SceneCreatorV2MaterialCoordinator"
  variation_point: "environment / character-description / event-narration / scene-description each use a different narratological lens"
  inputs:
    - "单次主创自然语言委托与可选文风"
    - "本次明确挂载的材料及其来源说明"
    - "角色的 16 区角色卡模板"
  outputs:
    - "可供主创重组的文学化原始素材"
    - "四个非角色提示词各自唯一的 {{STYLE_DIRECTION}} 文风槽"
  invariants:
    - "角色系统提示词保持现有 16 区结构，不增加前言、文风槽或共享权限文本"
    - "其他四类每类仅有一个自由文风槽，并直接作为该类系统提示词"
    - "运行时只呈现本次委托的挂载与自然语言任务"
    - "角色候选、描写素材及事件事实状态仍按现有合同归场景主创处理"
    - "旧交易提示词快照保留，v2 默认启用状态不变"
  allowed_dependencies:
    - "Engine prompting layer registry and existing natural material request contract"
    - "literary narratology / creative writing theory sources listed below"
  forbidden_dependencies:
    - "Studio runtime, Provider transport, formal archive writes, or Gate policy"
    - "shared boundary/permission boilerplate added to v2 material identities"
    - "JSON output instructions in the creative identity prompts"
  tests:
    - "each template uses its own literary focus and remains distinct from the other three"
    - "style placeholder occurs exactly once in each non-actor prompt and never in actor card"
    - "no new negative boundary boilerplate or inherited shared layer in natural invocation"
    - "prompt snapshot versions advance for every changed asset"
  rollback_unit: "five material identity assets v5"
  documentation:
    - "docs/implementation/creative-kernel/32-five-material-agent-prompts-change-packet.md"
```

## 理论转译

- **环境观察**：叙事环境同时由物质地形、社会生活、人物经验与故事时间构成；空间在被行走、使用、记忆和感知时成为有意义的地方。写作提示会把这种关系转成可触的材质、时间痕迹、行动可能和感知焦点。
- **人物肖像**：人物可通过外貌、言语、动作、思想及其对他人的影响逐渐显形；观察位置会决定细节的选择和读者的推断。提示将以观察者的目光组织肖像，让身体细节与行为、关系发生联系。
- **事件叙述**：故事事件与叙述安排可以在因果、顺序、时长和重复上形成不同结构。提示将引导叙述者选择切入点、详略、回看和揭示节奏，让制度或世界设定经由事件及其后果进入故事。
- **场面描写**：叙事空间由不断展开的空间框架构成，读者借人物移动、感知、地标与事件形成心中的空间关系。提示将把已经给出的言行组织成可阅读的站位、路线、视线和动作节拍。

参考：Rodak 与 Storey 的开放教材《Prose Fiction》[Setting 章节](https://manifold.open.umn.edu/read/c13-setting-rodak-storey/section/7786ea14-3407-4091-bc78-a15ced7641d0)、[Characterization 章节](https://manifold.open.umn.edu/read/c11-characterization-rodak-storey/section/98ad1eb6-146f-4b86-ba61-ac0e2dcdee81)；Hühn 等编《Living Handbook of Narratology》的 [Space 条目](https://www-archiv.fdm.uni-hamburg.de/lhn/node/55.html)；Ribó《Prose Fiction》的 [Plot 章节](https://www.openbookpublishers.com/books/10.11647/obp.0187/chapters/10.11647/obp.0187.02)；Rodak 与 Storey 的 [Narration 章节](https://manifold.open.umn.edu/read/c14-narration-rodak-storey/section/e8402bea-3301-465c-86fa-4cafcb4c0d37)。这些理论用于生成各自的创作视角，不作为写作术语清单塞给 Agent。

## 完成标准

- 环境写“人物如何经历地方”，人物描写写“一个人如何在观察关系中显现”，事件叙述写“事件怎样被讲述并改变当下”，场面描写写“言行怎样在连续空间中构成可读场景”。
- 四类提示都直接自然地引导文学素材交付，文风槽可自由填写；角色卡维持现有纯模板。

## 实施与验证

- 四类身份模板升为 package version 5，角色卡保持 version 3 与 16 区结构。每个非角色模板保留唯一文风槽；自然调用仍把对应模板直接作为 system prompt。
- 依据上述叙事理论重写四类身份文字，提示作者意图、当前委托和本次挂载素材如何转成各领域的文学表达。四类提示互不复用同一套身份段落。
- 25 项自然提示、角色/取材/快照兼容回归通过；prompt registry 的 59 项资产与 73 项任务绑定校验通过，架构审计与模块图检查通过。
- 旧自然交易仍按已冻结的提示快照运行；本次没有更改 v2 的默认关闭状态、候选整理、事件事实状态、正式写回或审读 Gate。
