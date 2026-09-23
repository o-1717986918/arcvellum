# 正文表现力与解释性收尾修正

## 现象与根因

当前成稿同时出现持续低音量、短句切碎、白描独占、人物声音趋同，以及动作或意象已经完成表达后又补一句解释的问题。以《他与她》现有场景为证，挂载的不可变默认文风仍是早期版本，其中以“朴素”“中等长度句承担主要叙述”“每场只取一个主机制”为中心；项目早期方向又把“句子短而完整”写入世界规则。两者共同压低了后续“文笔尽可能优美”的软要求。首轮长度补写提示只要求深化阻力与反应，没有要求继承参考样例的句群、修辞、叙述距离和收束方式，补写段落会进一步趋向动作说明。

本轮不新增文学 Gate，不提高审查门槛，不增加模型调用或持久化字段。修正集中在生成阶段：把“有起伏”落实为可执行的语言谱面、把参考样例落实为可观察的技法、允许具有气氛和审美时间的段落、限制解释性尾句，并让续写继承同一表达机制。既有机械对照、反规避和中文标点审查保持不变。

## 批次 A：默认文风生成合同

```yaml
module_change_packet:
  objective: "默认文风以场景驱动的语言起伏、修辞调度和证据后停笔替代持续朴素白描"
  primary_module: "Engine literary/style"
  public_entry: "默认 Style Skill 模板、ANTI_AI_STYLE_PROMPT、dry style prompt"
  variation_point: "不同场景按参考样例和场景转折选择不同语言谱面与收束方式"
  inputs: ["mounted style profile", "R01-R25 完整语料", "scene/character/rhythm/reader experience contracts"]
  outputs: ["可版本化挂载的默认文风", "生成期表现力与解释性收尾约束"]
  invariants: ["不改写既有不可变挂载", "不新增 Gate 或阈值", "机械对照与中文标点继续审查", "不复制参考原句或专名", "canon 与用户最新方向优先"]
  allowed_dependencies: ["literary/style 现有模板与质量报告"]
  forbidden_dependencies: ["Provider transport", "Studio API", "静默覆盖用户项目"]
  tests: ["tests/test_default_style_preset.py", "tests/test_anti_ai_style.py"]
  rollback_unit: "默认文风与反 AI 生成指导独立提交"
  documentation: ["本记录", "docs/quality/default-style-reference-catalog.md"]
```

## 批次 B：正式场景 Prompt Asset

```yaml
module_change_packet:
  objective: "正式正文任务在初稿中执行语言谱面、参考技法和无解释性尾句的收束"
  primary_module: "Engine prompting"
  public_entry: "route.scene-development.prose.generate.v1 Prompt Asset 与 platform generation sidecar"
  variation_point: "场景转折、人物注意力和所选参考样例决定局部表达强度"
  inputs: ["TaskPackage", "mounted style/profile", "scene/composition/rhythm/reader experience contracts"]
  outputs: ["版本化 prose generation prompt", "同义的主平台 Agent 生成说明"]
  invariants: ["不改 route 顺序、输出 schema 或审查 Gate", "软文风在生成阶段执行", "正文仍由主创 Agent 完成"]
  allowed_dependencies: ["prompting 现有 Prompt Asset 与 sidecar 模板"]
  forbidden_dependencies: ["Runtime Provider 参数", "新模型调用", "第二套风格状态"]
  tests: ["Prompt Asset registry", "tests/test_default_style_preset.py", "platform task contract tests"]
  rollback_unit: "正式正文提示资产独立提交"
  documentation: ["本记录"]
```

## 批次 C：lean-v2 初稿与补写

```yaml
module_change_packet:
  objective: "lean-v2 的初稿、返修和首轮长度补写共享同一表现力、人物声音与收束合同"
  primary_module: "Studio runtimes"
  public_entry: "render_scene_create_prompt()、render_scene_revision_prompt()、render_scene_length_completion_prompt()"
  variation_point: "已有正文的语言谱面和所选参考样例由本场输入决定"
  inputs: ["SceneBrief", "Relevant Sources", "已有 prose", "review evidence"]
  outputs: ["同一 JSON 合同的场景候选或可插入段落"]
  invariants: ["不改事务生命周期", "不新增 Gate、schema 或 Provider 调用", "补写不新增人物、稳定事实或核心事件", "不以华丽辞藻灌字数"]
  allowed_dependencies: ["Engine public literary DTO", "现有 RoleConversationGateway 与 PromptRecipe"]
  forbidden_dependencies: ["Engine internal import", "第二次风格改写调用", "自动语义改稿"]
  tests: ["tests/test_lean_kernel_v2_pi_runtime.py", "prompt size contract"]
  rollback_unit: "lean-v2 三类提示文案独立提交"
  documentation: ["本记录"]
```

## 批次 D：现有项目升级

```yaml
module_change_packet:
  objective: "《他与她》后续场景实际使用新版文风，并由最新用户方向取代早期短句优先口径"
  primary_module: "项目 Style Skill 与 user direction 正式接口"
  public_entry: "build/mount style profile version 与 user-direction append"
  variation_point: "只升级当前用户明确指定的项目"
  inputs: ["新版默认文风资产", "当前 active style identity", "用户本轮文风要求"]
  outputs: ["新的不可变挂载版本", "可审计的最新用户方向"]
  invariants: ["不修改已晋升正文", "不改写旧挂载目录", "不恢复暂停的自动创作", "不伪造审查或版本来源"]
  allowed_dependencies: ["现有正式 style build/mount 与 direction API"]
  forbidden_dependencies: ["直接覆盖 active mount 内容", "静默修改创作历史", "重写 canon 事实"]
  tests: ["active style integrity", "next-scene prompt source evidence", "project remains paused"]
  rollback_unit: "新挂载版本与方向记录的既有 receipt"
  documentation: ["本记录与项目 mutation receipt"]
```

## 验收标准

1. 默认文风不再把朴素、白描或中等句长当作恒定底色；关键段落可以使用自由间接引语、反讽、通感、借代、复沓、长句推进等具体手段，但不按配额堆修辞。
2. 每场从参考语料中选主参照后，须提取至少两项可观察技法并贯穿场景，而非只借题材词。
3. 动作、意象、对白或物证已经传达含义时停笔，不追加翻译潜台词、总结主题或解释“这意味着什么”的尾句；机械“不是……而是……”仍由现有硬审查阻断。
4. 补写段落继承已有正文的叙述距离、句群呼吸、意象线和人物说话方式，不把后半场补成说明文。
5. 当前项目挂载新版本并写入覆盖旧“句子短而完整”的方向；自动创作保持暂停，待验证后由用户决定是否继续。
6. 全量测试、架构审计、Prompt Registry、客户端与 Pi Worker 检查通过；版本号、构建产物和更新元数据一致后发布。
