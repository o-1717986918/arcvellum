# Phase 23：模型 Provider 与 Prompt Pack

## 状态

已在 `v0.23.0` 实现 `http-chat` provider、场景生成 prompt pack 和 workflow 可选候选生成节点。

## 目标

让真实 LLM 创作接入具备稳定工程边界：

- 提示词从代码字符串升级为项目内可版本化模板。
- 模型调用通过 provider 协议进入 `drafts/candidates/`。
- workflow 只有在开启模型候选或 Agent 审查节点时调用模型。
- API key 通过统一全局配置或环境变量提供，不写入项目文件、manifest 或日志。

## 新增与变更

### Prompt Pack

默认模板：

- `templates/prompts/scene_generation_system.md`
- `templates/prompts/scene_generation_user.md`

初始化作品项目时复制到：

- `prompts/scene_generation_system.md`
- `prompts/scene_generation_user.md`

每次 `generate-scene` 会生成：

```text
drafts/candidates/{scene_id}-{provider}-{timestamp}.prompt.json
```

该文件记录 system/user messages、场景、上下文包、上下文来源证明、场景创作编排包、文风 profile、`generation_standards.style`、`generation_standards.word_budget`、`generation_standards.review_notes`、`generation_standards.hard_constraints` 和来源清单，便于复盘模型输入。

`generation_standards.style` 是生成前置契约，不是审查后置清单。平台 agent 或 provider 在写正文候选前，应先把 Style Skill / style profile 转译为本场景的叙述距离、句法节奏、意象系统、心理呈现、对白密度和标点停顿策略；这些策略只用于指导写作，不应作为工作流痕迹输出到候选正文。

`v0.75.0` 起，Prompt Pack 会把“降低 AI 腔”从软提醒改成生成前的分层门禁：机械“不是……而是……”“并非……而是……”“与其说……不如说……”及“不是……——是……”等破折号/句号变体是核心禁区，不判断为合理修辞；若 Style Skill 证据中有否定纠偏或高破折号节奏，写作 agent 只能抽象其人物认知、信息反转、讽刺顿挫或叙述者纠偏功能，不能把模板句式授权给生成模型。器官轮岗、万能占位、比喻依赖、抽象总结、模板转折和景物强制同步按约 2% 叙事单元密度门禁控制。任何语义级清洗都必须逐句复核，不能用正则批量删除否定或破折号。

`v0.66.0` 起，Prompt Pack 会额外注入：

- `generation_standards.hard_constraints`：把 canon、场景编排、人物逻辑、文风、字数预算、AgentReview notes、标点和输出边界压缩成生成前执行顺序。
- `generation_standards.review_notes`：读取上一轮 `reviews/agent/{scene_id}_scene_review.json` 或静态 review；若结论为 `pass_with_notes`，要求 writing agent 执行局部小修或记录豁免理由。
- `generation_standards.word_budget`：读取 `plot/word_budget/word_budget.json`，避免长篇目标被压缩成短篇摘要。

这些都是生成前硬约束，不是候选正文的一部分。正文不得输出硬约束摘要、review notes、prompt manifest 或自检过程。

`v0.70.0` 起，正式 `generate-scene` / prompt pack 默认要求已经存在 ready composition：场景必须先完成 context、`simulate-scene --agent`、`branch-simulate --agent`、正式 `branch_selection.md` 和 `compose-scene`。缺失 composition、fallback composition、recommended-only composition 或未正式选择的 composition 都会阻塞正式生成；`--allow-missing-composition` 与 `--allow-unselected-composition` 只用于内部实验，产物不得直接晋升或发布。

`v0.71.0` 起，挂载 Style Skill 的项目还需要在生成后的正式平台场景审查中写入 `style_adherence`。这让文风从“生成前硬约束”延伸到“生成后验收门禁”：prompt pack 负责把文风压进写作任务，`scene_review.v1` 与 `route-audit` 负责检查它是否真的改变了正文表达。

`v0.86.0` 起，Prompt Pack 要求正式 context packet 必须有相邻 context trace。传入 `--context` 但缺少 `*.trace.json` 时会阻塞，prompt manifest 会写入 `context_trace`，平台 Agent 在动笔前必须先用 trace 复核实际加载来源。

### Provider

当前 provider：

- `auto`：当前默认值，配置完整时解析为 `http-chat`。
- `dry-run`：本地占位，不需要外部模型。
- `http-chat`：通过标准库 HTTP 调用 chat-completions 兼容接口。

`http-chat` 所需环境变量：

```powershell
$env:LEW_MODEL_API_BASE = "https://your-model-endpoint/v1"
$env:LEW_MODEL_NAME = "your-model-name"
$env:LEW_MODEL_API_KEY = "your-api-key"
```

可选环境变量：

```powershell
$env:LEW_MODEL_TIMEOUT = "60"
$env:LEW_MODEL_TEMPERATURE = "0.7"
$env:LEW_MODEL_MAX_TOKENS = "2500"
```

当前 `auto` 要求存在 API Key；如需离线验证链路，显式使用 `--provider dry-run`。

## 命令

默认真实模型：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench generate-scene work/demo-work --scene scenes/scene_0001.yaml --rebuild-context
```

离线 dry-run：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench generate-scene work/demo-work --scene scenes/scene_0001.yaml --provider dry-run --rebuild-context
```

workflow 可选生成候选：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench run-workflow work/demo-work --mode scene-loop --generate-candidate
```
未配置模型时，追加 `--provider dry-run` 可验证工程链路。

## 输出

`generate-scene` 输出：

- `drafts/candidates/{scene_id}-{provider}-{timestamp}.md`
- `drafts/candidates/{scene_id}-{provider}-{timestamp}.json`
- `drafts/candidates/{scene_id}-{provider}-{timestamp}.prompt.json`
- `drafts/candidates/{scene_id}-{provider}-{timestamp}.agent_tasks.md`（使用 `--agent-tasks` 时）

`run-workflow --generate-candidate` 会把以下路径写入 workflow state：

- `candidate`
- `candidate_manifest`
- `prompt_manifest`
- `candidate_agent_tasks`（使用 `--agent-tasks` 时）

## 边界

- 模型输出是候选，不是正稿。
- 候选不会覆盖 `drafts/scenes/`。
- 候选不会写入 `canon/`、`characters/` 或 `plot/`。
- prompt manifest 记录提示词内容，但不记录 API key，也不写入 `[AGENT_TASK: ...]`。
- 平台 agent 审查候选和 prompt manifest 的任务写入 sidecar `.agent_tasks.md`。
- 外部模型错误会让对应 workflow 节点失败，并要求人工处理。

## 下一步

- 针对不同模型风格增加 provider 配置 profile。
- 为 prompt pack 增加自动压缩和优先级预算。
- 将 `style-eval` 接到候选生成后的可选评测节点。
- 候选稿转草稿已由 Phase 25 的 `promote-candidate` 接管。
