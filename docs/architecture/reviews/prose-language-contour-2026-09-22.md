# 正文生成语言起伏调整

## 批次 A：文风基础层

```yaml
module_change_packet:
  objective: "默认文风在保持清晰与事实约束时，允许有来由的句法、语域、意象和人物声音起伏"
  primary_module: "literary/style/"
  public_entry: "默认 Style Skill 模板及 ANTI_AI_STYLE_PROMPT"
  variation_point: "none"
  inputs: ["用户挂载的风格版本", "默认风格模板", "场景与人物事实"]
  outputs: ["新项目的版本化默认风格", "生成期反 AI 腔提示词"]
  invariants: ["不修改用户已挂载的不可变风格版本", "违禁表达与标点审查规则不放松", "不复制参考语料原句", "不改 Canon、Gate 或 task lifecycle"]
  allowed_dependencies: ["Style Skill 模板", "文风生成提示词", "默认风格合同测试"]
  forbidden_dependencies: ["Provider 传输", "Studio API", "用户项目文件的静默改写"]
  tests: ["默认风格模板与版本装载测试", "反 AI 腔硬规则回归"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本执行记录"]
```

## 批次 B：正式正文提示词

```yaml
module_change_packet:
  objective: "正式正文任务在生成阶段明确执行场景化语言曲线，而非反复要求统一朴素表达"
  primary_module: "prompting/"
  public_entry: "scene prose Prompt Asset、build_scene_prompt_pack()、platform generation sidecar"
  variation_point: "none"
  inputs: ["TaskPackage", "场景与编排", "挂载 Style Skill 与完整参考选段", "读者体验与节奏合同"]
  outputs: ["版本化正文 Prompt Asset", "prompt manifest", "正式创作 sidecar"]
  invariants: ["保留语料完整性与风格挂载优先级", "不改字数、审查、标点或数字 Gate", "正文只由主创 Agent 写入候选"]
  allowed_dependencies: ["Engine prompting 模块及模板", "正式场景任务合同测试"]
  forbidden_dependencies: ["Pi Worker 模型参数", "HTTP Provider", "绕过任务状态机"]
  tests: ["Prompt Asset 校验", "prompt pack/sidecar 合同测试", "场景生成相关回归"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本执行记录"]
```

定位：默认 Style Skill、生成包与正式侧栏多次要求“朴素”“给朋友讲事”“日记”，同时把短句、比喻、感官与抒情主要写成风险，容易把模型推向持续中速、解释性动作报告。改动聚焦正向生成：依场景转折安排语言的蓄势、加速与回落，按人物经验变换语域和对白，允许具有叙事效力的意象、幽默与抒情。禁止把“起伏”机械理解为随机长短句或通篇华丽。

温度判断：当前正式 Worker 通过 Pi SDK 调用模型，未显式传入 temperature；DeepSeek 官方文档说明较高温度会增加随机性，但在思考模式下无效。故本批不修改全局模型参数，也不把温度视为文风质量保证。

验证：新增 Prompt Asset v11 与生成模板合同测试；默认风格模板、反 AI 腔硬规则及场景命令定向测试通过。Prompt Registry 59 个资产与 73 个任务 ID 校验通过，架构审计和模块图检查通过；Python 全量 1497 项通过、1 项因 Windows 符号链接不可用而跳过，前端 248 项和 Pi Worker 103 项通过，前端构建成功。未调用真实模型，文学效果须在后续同场景创作中比较，不能由静态测试直接证明。

兼容边界：新项目会生成新版默认 Style Skill；既有项目的不可变挂载不会静默改写。其后新签发的正式正文任务会使用本次更新的 Prompt Asset 与生成标准；已冻结的旧任务包与旧候选不会追溯改动。
