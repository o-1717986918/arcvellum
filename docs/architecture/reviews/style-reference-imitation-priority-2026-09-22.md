# 参考语料模仿优先级修正

## 目标与边界

用户要求提高参考语料在正文生成中的权重，使创作 Agent 更主动模仿样例的表达方法。这里的“模仿”指选择一篇与本场功能相合的参考选段，贴近其叙述距离、句群节奏、细节组织、对白或意象推进方式，用当前作品的人物与事件写新正文；不要求逐句复刻或把二十五种声音混合。用户已提供的 R01—R25 仍全部完整保留，R17—R25 仍是正向类型参考。

现状缺口：正式默认文风虽将完整语料写入挂载的 `style-profile.md`，lean-v2 的 `active_style_evidence_paths()` 只列挂载提示词和元数据，未列 `style-profile.md`；因此其即时场景调用可能看到“先读语料”的命令，却没有看到语料全文。仅加强形容词无法解决这一读取缺口。

## Module Change Packet：文风资产与来源

```yaml
module_change_packet:
  objective: "让已挂载的完整参考语料成为场景可读来源，并提高默认文风对具体样例表达方法的模仿优先级"
  primary_module: "Engine literary/style"
  public_entry: "active_style_evidence_paths() 与已挂载默认 Style Skill"
  variation_point: "不同场景选择不同参考选段；已有项目的不可变挂载不自动覆盖"
  inputs: ["active_style_skill.json", "挂载版本 prompt.md", "挂载版本 style-profile.md"]
  outputs: ["包含完整 style-profile.md 的来源路径", "更明确的默认文风生成指令"]
  invariants: ["用户语料原文与顺序不变", "R17—R25 保持正向参考", "canon、人物、情节与用户方向优先", "既有违禁表达和标点审查不变", "不新增 Gate 或状态字段"]
  allowed_dependencies: ["Engine 现有挂载完整性与安全路径解析"]
  forbidden_dependencies: ["Studio Runtime 内部", "新 Provider 调用", "自动改写既有不可变版本"]
  tests: ["tests/test_default_style_preset.py", "style mount / evidence path tests"]
  rollback_unit: "Engine 文风资产与来源路径修改"
  documentation: ["本记录", "docs/quality/default-style-reference-catalog.md"]
```

## Module Change Packet：正式生成提示

```yaml
module_change_packet:
  objective: "正式场景路线明确要求以具体参考选段为表达主参照，而非只抽象归纳语料"
  primary_module: "Engine prompting"
  public_entry: "route.scene-development.prose.generate.v1 Prompt Asset"
  variation_point: "当前场景从 R01—R25 中选择合适的主参照"
  inputs: ["TaskPackage", "mounted style profile", "scene/composition contracts"]
  outputs: ["带具体模仿指令的场景生成任务"]
  invariants: ["不改正式路线顺序和审查 Gate", "不复用参考专名与连续原句"]
  allowed_dependencies: ["现有 Prompt Asset"]
  forbidden_dependencies: ["Studio Provider 分支", "第二套风格权重字段"]
  tests: ["tests/test_default_style_preset.py", "prompt-registry-validate"]
  rollback_unit: "正式场景生成 Prompt Asset 文案"
  documentation: ["本记录"]
```

## Module Change Packet：lean-v2 即时生成

```yaml
module_change_packet:
  objective: "lean-v2 create/revision 在已内联完整语料后主动按一篇选段的表达形态写作"
  primary_module: "Studio runtimes/pi_scene_transaction"
  public_entry: "render_scene_create_prompt() 与 render_scene_revision_prompt()"
  variation_point: "同一挂载风格在不同场景的参考选段选择"
  inputs: ["SceneBrief", "source_refs 与 Relevant Sources"]
  outputs: ["有样例主参照指令的 create/revision 提示"]
  invariants: ["不新增语义审查或数字密度 Gate", "不改变输出 JSON 合同", "用户方向、canon、人物和本场义务优先"]
  allowed_dependencies: ["Engine public literary DTO", "现有 SceneBrief 来源"]
  forbidden_dependencies: ["Engine internal import", "新 Provider 分支或模型调用"]
  tests: ["tests/test_lean_kernel_v2_pi_runtime.py", "真实来源内联回归"]
  rollback_unit: "lean-v2 即时提示文案"
  documentation: ["本记录"]
```

## 验收

1. 新项目的挂载文风仍完整含二十五个单元，且 `active_style_evidence_paths()` 将同版本 `style-profile.md` 列为可读来源。
2. lean-v2 的真实 create 提示含完整语料和具体模仿指令；超过来源预算时不得谎称“已读完整语料”。
3. 正式与 lean-v2 生成都区分“模仿表达机制”和“复制内容”；不改变现有硬语言审查。
4. 提示词质量、定向测试、全量测试、架构与 prompt registry 检查通过；若未跑真实模型对照，不能把提示变化宣称为文学效果已证实。

## 实施与验证结果

- `active_style_evidence_paths()` 现在把活动不可变挂载中的 `style-profile.md` 放在 prompt 后、元数据前；保留项目内路径校验与挂载完整性检查。默认文风的原始二十五单元未改动。
- 默认文风 prompt、profile、正式场景 Prompt Asset（`v9`）及 lean-v2 create/revision 均要求选一篇最相合样例作为表达主参照，重点模仿叙述距离、句群节奏、细节进入顺序和对白或意象推进，而不是只写抽象“清简”。既有硬语言约束与审查未变。
- 以《潮痕之下》五章 35 场的真实来源列表作只读回放：35/35 个 lean-v2 create 证据文本均包含已挂载 `style-profile.md` 全文；项目已有不可变 prompt 未被改写，新的即时生成指令与来源读取会在后续场景生效。
- 默认新项目的文风测试逐段核验二十五个单元仍全部进入挂载 profile，并新增 lean 来源全文内联回归。Prompt 质量合同通过，默认提示词为 2455 个中文内容字符。
- Python 全量 1479 项通过、1 项 Windows 符号链接条件跳过；Vue 单独重跑 75 文件、245 项通过；Pi Worker 10 文件、102 项通过；生产前端构建通过。
- Prompt Registry 59 个资产、73 个任务 ID 通过；17 个确定性 Prompt Eval 案例通过；架构审计 15 文件债、76 函数债、0 导入环、0 Studio->Engine internal 违规；模块图与 `git diff --check` 通过。
- 首次并行跑 Vue 时，`router.spec.ts` 一项超过 5 秒原有超时；在其他大型测试结束后用同一命令重跑，245/245 通过。没有更改测试超时或测试内容。
- 未运行本次改动的新稿实模型盲评或四组消融；以上证明“语料完整进入当前生成调用”和“提示行为合同改变”，不能证明文学审美提升的幅度。
