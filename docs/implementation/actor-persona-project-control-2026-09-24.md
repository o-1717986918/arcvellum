# 角色人格标签的项目级控制与对演扩展

## 2026-09-25 人格与语言标签生成修正

```yaml
module_change_packet:
  objective: "主创生成更鲜明的人格及个人语言气质，三个默认语言标签稳定进入 LANGUAGE_STYLE"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_performance_plan_prompt / render_actor_initialization_prompt"
  variation_point: none
  inputs: ["SceneBrief", "人物表达资料", "主创生成或项目保存的人格区块"]
  outputs: ["角色计划提示", "最终角色初始化首条消息"]
  invariants: ["项目自定义标签保留", "角色初始化不带场景任务", "不新增审查门禁或正文写权"]
  allowed_dependencies: ["Engine 既有角色人格标签合同"]
  forbidden_dependencies: ["Studio I/O", "Provider SDK", "正式晋升流程"]
  tests: ["test_scene_performance_agents", "test_actor_personas"]
  rollback_unit: "本次人格提示词及默认标签合并"
  documentation: ["本文"]
```

问题来自两处：主创示例把 `ANTI_CONCISE` 放在区块外，未要求生成鲜明的个性化语言标签；最终初始化只在整个 `[LANGUAGE_STYLE]` 区块缺席时追加默认值，项目自定义区块存在但缺项时，默认标签就会丢失。本次只改生成提示与初始化合并：主创为各人选择源于身份、欲望和关系的显著性情及抽象语言气质；简洁性不再充当默认语言特色；三个默认标签在 `[LANGUAGE_STYLE]` 下补齐，自定义标签仍原样保留。旧场景事务保留原快照，新事务使用新提示。

原实现只在未指定 `[LANGUAGE_STYLE]` 时附加 `ANTI_PLAIN / POLISHED / ANTI_SHORT_SENTENCES`；本次修正后，即使已有自定义语言标签，缺少的默认项也会补在同一区块。`ANTI_SIMPLISTIC` 与 `ANTI_CONCISE` 均不属于默认生成示例。顶层 Agent 的两个工具分别列出作品内已建档人物及其全部标签、替换某个人物四个区块的全部标签。项目级设置优先于主创逐场拟写的初始化标签，但主创仍负责场景任务和最终正文。修改只影响之后开始的场景事务；已开始的场景保留原表达投影快照。

## Module Change Packets

```yaml
module_change_packet:
  objective: "角色初始化默认采用 POLISHED，项目可保存并读取每名已建档角色的全部人格标签"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "list_actor_personas / save_actor_persona / actor_personas_for_participants"
  variation_point: none
  inputs: ["正式人物档案", "四个区块的英文大写标签"]
  outputs: ["characters/_actor_personas.json", "场景角色初始化资料"]
  invariants: ["不改正文、Canon 或人物事实", "未设置项目标签时仍由主创设计", "语言默认标签只在未指定 LANGUAGE_STYLE 时补入"]
  allowed_dependencies: ["Engine 人物档案读取", "Engine 角色初始化提示"]
  forbidden_dependencies: ["Studio API 路由", "Pi Provider", "项目 Agent 直接写文件"]
  tests: ["角色标签读写及校验", "场景提示与默认标签测试"]
  rollback_unit: "本项 Engine 变更"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "顶层 Agent 能查看和完整修改角色的四个标签区块"
  primary_module: "Studio project_agent"
  public_entry: "project_actor_personas / project_actor_persona_update"
  variation_point: none
  inputs: ["注册作品 work_id", "已建档角色 character_id", "四区块标签"]
  outputs: ["已保存的人格标签及操作回执"]
  invariants: ["经注册作品解析与 Engine 公共服务操作", "不直接写人物 YAML 或正式正文"]
  allowed_dependencies: ["Engine public.literary", "Project Agent bridge"]
  forbidden_dependencies: ["任意路径写入", "绕过审查或晋升"]
  tests: ["Project Agent 工具与适配测试", "Pi Worker 工具合同测试"]
  rollback_unit: "本项 Project Agent 变更"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "保存的人格标签在下一场角色初始化生效，场景事务期间保持同一份快照"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "scene_performance_materials / scene_creative_cache_digest"
  variation_point: none
  inputs: ["场景表达投影中的角色标签"]
  outputs: ["演员首条初始化消息", "一致的场景素材缓存键"]
  invariants: ["角色只产候选素材", "主创拥有正文", "既有场景审查与晋升路线不变"]
  allowed_dependencies: ["Engine public.literary", "Pi 场景事务"]
  forbidden_dependencies: ["直接写 Canon", "新增门禁"]
  tests: ["角色覆盖优先级", "事务缓存复用"]
  rollback_unit: "本项 Runtime 变更"
  documentation: ["本文"]
```

## 对演拓展判断

当前正式执行方式是每名角色各自生成整场素材，再由主创交错整理；它已经能处理一至四名参与者，但并非真正逐轮对戏。实验脚本的逐轮对戏只覆盖双人。因此“双角色限制”属于互动实验路线，不属于整场素材路线。当前 `_relay_materials` 能按参与者循环，却每轮单独调用模型，并没有持久保存每个角色的会话；直接把其“下一位对手”轮转规则用于三人戏，会让无关人物机械地轮流插嘴。

建议下一阶段只在互动调度层增加一个共享的“公开舞台”，不复制两两会话。主创给出开场局面与必要情节方向；调度器选择当前有理由说话或行动的人，把公开言行和外部事件送进该角色自己的持久会话。角色保有发言、沉默和临场动作的自由；其内部想法只回到主创，不向其他角色广播。每次角色输出后更新公开舞台，再让主创选择是否推进事件、邀请另一人回应或结束对戏。三人以上的轮次由局面驱动，不按固定 A→B→C；若多人同时抢话，调度器只决定可见顺序，不替他们写台词。会话数量随角色数线性增长，而不是按角色对数增长。

单人场景需要的是压力来源，并不需要伪造第二个人。外部事件、器物的阻力、空间变化、消息或角色自身的决定都可成为下一轮输入。环境 Agent 仍只写可感知的环境候选，并可提供变化后的空间素材；它不扮演有意图的“场景角色”，不替人物产生新事实。主创可把已确认的场景变化送入角色会话，再依据角色反应和环境素材写心理与叙述。若是纯独处、无外部变化，角色也可以只作一次整场输出，避免为了机制而制造对话。

先做 1 人与 3 人的小场试验，比较角色声音、回应因果、连续性及调用成本，再决定是否把逐轮机制接入正式默认路线。工程落点是现有 `scene_performance` 编排与 Pi 的会话续接；Engine 只需拥有公开舞台记录、角色可知视图及候选素材的合同，不应另建一套文学 Gate、人物资产或正文晋升机制。
