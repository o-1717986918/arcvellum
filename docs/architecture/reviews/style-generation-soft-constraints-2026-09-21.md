# 文风生成软约束修正记录

## Lean-v2 即时提示修正包

```yaml
module_change_packet:
  objective: "让 lean-v2 场景事务在正文交付前执行伪精确数字的五项语义判定，并让 AgentReview 复核明显残留。"
  primary_module: "Studio runtimes/pi_scene_transaction"
  public_entry: "render_scene_create_prompt()、render_scene_revision_prompt()、render_scene_review_prompt()"
  variation_point: "create、revision 与 review 对同一量化细节规则承担生成、返修与语义复核职责"
  inputs:
    - "SceneBrief"
    - "Relevant Sources 与 mounted style"
    - "候选 prose、VerificationReport 与 ReviewResult"
  outputs:
    - "置于 lean create/revision 提示末端的 Final Prose Pass"
    - "置于 lean review 提示末端的 Quantitative Detail Review"
  invariants:
    - "不新增数字密度 Gate、阈值、正则扫描器、schema 或模型调用"
    - "canon 或用户已经确定的精确事实继续逐字保留"
    - "量化细节只做逐句语义重写，不做批量删除或机械模糊化"
    - "现有场景事务、审查结论和写回生命周期不变"
  allowed_dependencies:
    - "Engine public literary DTO"
    - "既有 lean scene PromptRecipe 与 RoleConversationGateway"
  forbidden_dependencies:
    - "新 Gate、新 persistence 字段、新 Provider 分支"
    - "把文学判断下沉为数字计数或密度评分"
  tests:
    - "tests/test_lean_kernel_v2_pi_runtime.py"
    - "真实 lean-v2 新项目创作回归"
  rollback_unit: "lean scene 三类即时提示中的量化细节末端复核与定向断言"
  documentation:
    - "docs/quality/creative-test-rain-port-2026-09-21.md"
    - "本记录"
```

## 伪精确数字修正包

```yaml
module_change_packet:
  objective: "让正文生成默认舍弃与人物选择、情节因果和后续兑现无关的精确数字，减少仪表盘式伪真实感。"
  primary_module: "Engine literary/style"
  public_entry: "已挂载 style prompt 与 route.scene-development.prose.generate.v1 Prompt Asset"
  variation_point: "题材可以保留真正参与资源换算、行动阈值、时间连续性或后续兑现的数值，其余精度在生成阶段改写"
  inputs:
    - "mounted style prompt"
    - "scene/composition contracts"
    - "用户创作方向与 canon 事实"
  outputs:
    - "默认不写、例外举证的量化细节生成约束"
    - "生成结束前对阿拉伯数字、中文数字、序数、时长、距离、尺寸、百分比、型号和轮次的静默语义复核"
  invariants:
    - "不新增数字密度 Gate、评分器、阈值或持久化字段"
    - "不把所有数字列为违禁词，不误伤年龄、日期、规则编号和必要资源换算"
    - "不得用正则、批处理或简单模糊词替换正文中的数字"
    - "完整规则在生成阶段执行，现有 AgentReview 只核验是否残留明显无因果精度"
  allowed_dependencies:
    - "Engine literary/style 既有 prompt 与默认预设资产"
    - "Engine prompting 已有 scene generation Prompt Asset"
  forbidden_dependencies:
    - "新 schema、新 Gate、新 Provider 分支"
    - "Studio runtime 或前端特判"
    - "数字计数预算与自动语义改写"
  tests:
    - "tests/test_default_style_preset.py"
    - "prompt registry validation"
    - "雨港离航数字表达回归样例"
    - "git diff --check"
  rollback_unit: "伪精确数字生成约束、审读复核说明与定向测试"
  documentation:
    - "docs/quality/creative-test-rain-port-2026-09-21.md"
    - "本记录"
```

实施后验证：默认策展文风提示词为 2469 个中文内容字符，动态 dry-run 文风提示词为 1821 个，均保持在现有质量合同内；相关单元、创作质量、提示词评估和运行时资源测试共 27 项通过，lean-v2 运行时测试 8 项通过，Prompt Registry 的 59 个资产与 73 个任务映射全部通过。架构审计不再报告本次曾造成的 `build_scene_draft` 或 `pi_scene_transaction.py` 行数增长；剩余三项为本轮前已经存在的 `anti_ai.py` 文件/函数与 `punctuation.py` 函数预算债务，本轮只替换提示文案，没有新增数字规则 Gate 或扩大这些函数的复杂度。

## Module Change Packet

```yaml
module_change_packet:
  objective: "让抽象文风要求在正文生成前被转译为本场写法，同时保留违禁词、反规避和中文标点的生成约束与审查核验。"
  primary_module: "Engine literary/style"
  public_entry: "已挂载 style prompt 与 route.scene-development.prose.generate.v1 Prompt Asset"
  variation_point: "不同场景根据既有 scene、character、reader experience、narrative rhythm 和 scene bridge 合同选择不同表达策略"
  inputs:
    - "mounted style prompt"
    - "scene/composition contracts"
    - "creative quality profile"
  outputs:
    - "生成阶段可直接执行的场景化文风策略"
    - "保持原有硬约束的候选正文"
  invariants:
    - "不删除或放宽违禁词、反规避、中文标点与 Style Lint 审查"
    - "不新增文学 Gate、状态字段或第二套审查真相"
    - "不改变 canon、人物、TaskPackage、promotion 和 review 生命周期"
    - "抽象软约束在生成阶段落实，审查仅核验结果并指出残留偏差"
  allowed_dependencies:
    - "Engine prompting 已有 TaskPackage 文本"
    - "Engine literary/style 既有 prompt 与预设资产"
    - "Engine literary/planning 已有节奏和桥接合同"
  forbidden_dependencies:
    - "Studio runtime/provider 特判"
    - "新模型调用或 Provider 抽象"
    - "新增门禁、阈值或状态机分支"
  tests:
    - "tests/test_default_style_preset.py"
    - "prompt registry validation"
    - "targeted platform task generation regression"
    - "git diff --check"
  rollback_unit: "本批文风生成提示词与策展样例修改"
  documentation:
    - "docs/quality/default-style-system-audit.md"
    - "docs/quality/default-style-reference-catalog.md"
    - "本记录"
```

## 用户参考语料接入补充包

```yaml
module_change_packet:
  objective: "将用户提供的 25 个文本单元完整、分类地纳入默认文风生成上下文，不让来源与权利说明污染模型参考文本。"
  primary_module: "Engine literary/style"
  public_entry: "ensure_default_style_mount() 产生的 mounted style-profile.md"
  variation_point: "按场景功能选择中低强度叙事机制、高强度候选机制或类型氛围机制"
  inputs:
    - "用户提供并声明为公版或原创的 examp.txt"
    - "现有默认文风 prompt/profile 合同"
  outputs:
    - "不删节的 25 单元训练语料"
    - "含分类索引和完整语料的 mounted style-profile.md"
    - "不进入生成上下文的来源声明侧车"
  invariants:
    - "不新增或加强 Gate，不修改审查阈值"
    - "违禁表达、反规避和中文标点仍由生成约束与审查共同覆盖"
    - "语料中的专名、标志句、连续措辞和标点异常不成为复制许可"
    - "留出集与生成参考集继续隔离"
  allowed_dependencies:
    - "Engine literary/style 现有默认预设物化逻辑"
    - "Engine prompting 已有 style-profile source path"
  forbidden_dependencies:
    - "新 schema、新 Gate、新 Provider 分支"
    - "将来源、版权或 URL 段落注入模型面向的参考语料"
  tests:
    - "tests/test_default_style_preset.py"
    - "25 单元完整性与摇散校验"
    - "prompt registry validation"
    - "git diff --check"
  rollback_unit: "用户参考语料、分类索引、默认文风物化与定向测试"
  documentation:
    - "docs/quality/default-style-reference-catalog.md"
    - "docs/quality/default-style-system-audit.md"
    - "本记录"
```

## 问题来源

默认文风同时存在两类约束，但过去没有清楚区分它们的职责：

1. 违禁表达、反规避和中文标点属于可确定核验的边界，应在生成时明确，并继续由 Style Lint 与 AgentReview 检查。
2. 叙述距离、人物声音、段落节奏、感官通道、详略和收束方式属于场景相关的软约束。它们若只在审查阶段以偏差形式出现，初稿已经形成模板，修订往往只能做表面替换。

旧默认样例共享“安静职业场景、异常物件、克制观察、悬念物件收尾”的叙事骨架，容易把“清简”误教成固定的悬疑短篇腔。本批改用用户提供的完整参考集，并把中低强度叙事机制、有条件的高强度语域与类型氛围机制分组，避免将二十五个单元混成统一腔调。

## 修正原则

- 生成前先从已有合同提炼本场的动力、人物代价、主导表现通道、与邻场差异和收束方式；这些判断仅指导正文，不增加持久化 schema。
- 抽象软约束改写为正向生成动作，不用大规模禁词表代替文学选择。
- 硬约束保持双重覆盖：生成提示词先约束，Style Lint 与 AgentReview 后核验。
- 完整语料按 R01—R25 编号：R01—R07 作中低强度叙事机制，R08—R16 作高强度候选机制，R17—R25 作类型氛围与空间定调机制。
- 模型面向的语料不夹带版权、URL 和长篇来源说明；简短的用户授权声明留在不参与生成的 session 侧车中。
- 不增加 Gate，不更改现有质量阈值，不以字数或检测器分数代表文风质量。

## 验收重点

- Prompt Asset 明确要求在生成前形成场景化文风策略。
- 默认文风 prompt 明确区分硬语言边界与场景软策略。
- 机械对照禁区、中文全角标点、引号、省略号和破折号规则仍在生成资产中。
- 既有审查与 Style Lint 规则未被删除或放宽。
- 二十五个用户单元全部保存，原始正文的顺序和规范化摘要不变。
- 场景生成任务可通过现有 style-profile 路径读取完整语料，不只读抽象摘要。

## 验证记录

- `tests.test_default_style_preset`、`tests.test_project_schema_migration`、`tests.test_style_machine_metadata`、`tests.test_anti_ai_style`、`tests.test_task_contract_transport`：共 56 项通过。
- 用户参考集完整性：规范化后为 25 个单元，SHA-256 为 `35c5ecf515618fa59677c063d778572f53cd653f7fc302e75cc10ec55b26a03e`；定向测试逐单元确认已进入 mounted `style-profile.md`。
- 生成参考纯净性：训练语料与 mounted profile 不包含 `https://`、“作者：”或“版权”元数据；授权声明仅在 session 侧车。
- `python -m literary_engineering_studio_engine prompt-registry-validate --json`：通过，59 个 Prompt Asset、73 个任务 Prompt ID 无错误和警告。
- 内置评测候选分别运行 `lint_ai_style()` 与 `lint_punctuation()`：均无问题。
- `python -m compileall -q src`：通过。
- `python scripts/generate_module_map.py --check`：通过。
- `git diff --check`：通过；仓库中既有 OpenAPI 文件产生 CRLF 提示，不属于本批修改。
- `python scripts/architecture_audit.py`：仍被本批开始前已经存在的 `anti_ai.py` 与 `punctuation.py` 行数/复杂度超基线阻塞。本批仅同步 `anti_ai.py` 中已有提示常量的文案，没有增加行数或函数逻辑，也没有通过改 baseline 隐藏问题。
