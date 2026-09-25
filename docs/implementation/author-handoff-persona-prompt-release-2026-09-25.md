# 主创素材交接、角色标签与提示词修订

状态：2026-09-25，实施记录。范围仅限 lean-v2 场景创作；正式 Gate、角色一级创作归属和资产晋升不变。

## Module Change Packet A：主创素材交接

```yaml
module_change_packet:
  objective: "主创看到按时间排列的关键角色言行、场景变化和环境候选，省去整份推演计划的重复输入"
  primary_module: "Studio runtimes/scene_performance_ownership.py"
  public_entry: "author_handoff_materials；原始 render_interaction_materials 保留在场景缓存与来源审查"
  variation_point: "初稿交接保留场景变化和视角私念；修订沿用紧凑来源"
  inputs: ["原始推演记录", "SceneBrief.viewpoint"]
  outputs: ["紧凑但可追溯的写作素材"]
  invariants: ["角色原话和可见动作不丢失", "场景因果顺序不改变", "Gate 和素材请求不变"]
  allowed_dependencies: ["Studio 场景事务", "Engine public literary"]
  forbidden_dependencies: ["Provider SDK", "修改正式正文", "新审查门槛"]
  tests: ["交接内容与缩减率", "主创初稿提示", "场景事务回归"]
  rollback_unit: "本批独立提交"
  documentation: ["本文"]
```

## Module Change Packet B：作品级角色标签

```yaml
module_change_packet:
  objective: "已保存的专属角色标签真正成为新场景角色会话的初始化"
  primary_module: "Studio runtimes/scene_interaction.py"
  public_entry: "new_scene_session"
  variation_point: "有作品级标签时优先使用；无标签时使用主创本场创作的标签"
  inputs: ["表达快照 actor_personas", "本场导演计划"]
  outputs: ["持久角色会话首条消息"]
  invariants: ["已开始事务的标签快照保持稳定", "具体任务与情节仍在后续轮次", "角色一级生成"]
  allowed_dependencies: ["Engine public literary", "Studio 场景事务"]
  forbidden_dependencies: ["擅自改写角色档案", "把任务单塞入初始化"]
  tests: ["保存标签覆盖临时标签", "无保存标签回退", "文学少女三个角色的作品级读回"]
  rollback_unit: "本批独立提交"
  documentation: ["本文"]
```

## Module Change Packet C：主创提示

```yaml
module_change_packet:
  objective: "让小说创作意图、人物情绪与叙事选择先于工程字段进入主创注意力"
  primary_module: "Studio runtimes/pi_scene_author_prompt.py"
  public_entry: "render_scene_create_prompt；render_scene_revision_prompt"
  variation_point: "初稿和修订各自保留必要 JSON/SceneDelta 合同"
  inputs: ["SceneBrief", "精简来源", "角色环境候选", "核验与审查意见"]
  outputs: ["主创模型提示"]
  invariants: ["精确事实和既有引用合同不变", "角色素材可选择和改写", "输出结构不变"]
  allowed_dependencies: ["Engine public literary", "Studio prompt recipe"]
  forbidden_dependencies: ["新模型调用", "新 Gate", "自动修改作品事实"]
  tests: ["提示合同与长度", "文学引导措辞", "现有 prompt 和场景回归"]
  rollback_unit: "本批独立提交"
  documentation: ["本文"]
```

已定位根因：原始推演含完整节拍、导演轮次和逐条素材，初稿主创重复读了大量已由 SceneBrief 覆盖的结构；来源按文件顺序占满预算，后面的角色资料容易被挤掉；作品级标签只出现在导演可见的表达快照，初始化仍取本场导演标签。提示词先强调精确数字与 JSON，再给小说体验和叙事选择，强化了机械感。修复后的效果须通过结构化回归验证；文风优劣仍需真实模型与读者检验，不能用测试替身宣称已经解决。

## Module Change Packet D：已挂载默认文风的实际生效

```yaml
module_change_packet:
  objective: "最高优先级文风真正进入 lean-v2 主创提示，且通用默认文风不误压情绪和场景停留"
  primary_module: "Studio runtimes/pi_scene_transaction.py"
  public_entry: "Engine public literary.active_style_prompt_text；Engine public literary.refresh_default_style_mount"
  variation_point: "仅主创初稿与修订叠加当前已验证挂载；环境和角色仍使用各自提示"
  inputs: ["验证过的项目文风版本", "场景参考选段"]
  outputs: ["含项目文风与场景选段的主创提示", "可追溯的新默认文风版本"]
  invariants: ["文风不覆盖事实和输出 JSON 合同", "旧版本不可变", "已有自选文风不被默认刷新覆盖"]
  allowed_dependencies: ["Engine public literary", "Studio 主创事务", "默认文风模板"]
  forbidden_dependencies: ["直接修改已挂载不可变版本", "更改禁词或标点审查", "自动覆盖用户自选文风"]
  tests: ["默认挂载刷新", "主创提示包含挂载内容与参考选段", "版本完整性", "场景事务回归"]
  rollback_unit: "本批独立提交；用户作品可用旧版本重新挂载"
  documentation: ["本文", "v0.99.11 发布说明和验证记录"]
```

审查结论：`arcvellum-clear-plain-prose` 是旧稳定 ID；当前展示名和正文早已是“弹性叙事”，并不要求全程朴素。真正断点是 lean-v2 只送入场景参考选段，未送入被标记为 `highest` 的挂载 `prompt.md`。现将验证过的挂载提示作为 prose 表达约束放到主创初稿和修订，同时让 JSON 交付合同继续由场景任务定义。默认模板的“过场压缩”“证据之后停笔”已改为按人物关系与情绪需要停留、只删除同一层意思的重复解释；“通读全部 R01—R25”改为利用当前任务实际提供的主参考选段。《文学少女》生成了新不可变版本 `v1-267cfd0f62c35e8264fd` 并完成挂载，旧版本保留。
