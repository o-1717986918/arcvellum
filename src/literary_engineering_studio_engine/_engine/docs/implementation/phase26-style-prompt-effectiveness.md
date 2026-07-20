# Phase 26：LLM 文风约束提示词与有效性评测

## 状态

已在 `v0.26.0` 实现 `style-prompt` 和 `style-prompt-eval`。

> Current project-type skill override: formal `style-prompt` and `style-prompt-eval` write platform-agent task sidecars and expected output paths. They do not call local `dry-run`, `http-chat`, or external agent services.

## 目标

修正文风模块的产物定义：`style-profile` 和 `style_metrics.json` 只是中间资产，最终交付应是供 LLM 写作时直接注入的文风约束提示词。

## 核心链路

```text
corpus
-> style-profile
-> style-prompt
-> style-prompt-eval
-> style-eval metrics/report
-> 人工判断提示词是否有效
```

## style-prompt

命令：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench style-prompt work/demo-work/style/demo-author
```

输出：

```text
style/{profile}/style_prompt.md
style/{profile}/style_prompt.agent.json
style/{profile}/style_prompt.agent_tasks.md
```

`style_prompt.md` 是给 LLM 用的提示词，必须覆盖：

- 使用身份。
- 核心风格机制。
- 句法与节奏约束。
- 叙述距离与心理呈现。
- 意象和感官调度。
- 对白与动作约束。
- 禁止倾向。
- 输出自检。

## style-prompt-eval

命令：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench style-prompt-eval work/demo-work/style/demo-author `
  --reference eval/reference.txt `
  --input eval/english.txt `
  --mode back-translation
```

输出：

```text
style/{profile}/evaluation_results/{mode}/platform_agent_candidate.md
style/{profile}/evaluation_results/{mode}/platform_agent_candidate.prompt.json
style/{profile}/evaluation_results/{mode}/platform_agent_candidate.agent_tasks.md
style/{profile}/evaluation_results/{mode}/style_eval_{timestamp}.md
style/{profile}/evaluation_results/{mode}/style_eval_{timestamp}.json
```

这一步审查的是“提示词是否有效”，而不是只审查统计 profile。评测逻辑：

1. 用 `style_prompt.md` 作为 system prompt。
2. 用英文回译文本、大纲或盲评任务作为 user prompt。
3. 由平台 Agent 生成候选中文文本。
4. 调用 `style-eval` 比较 reference 与 candidate。
5. 输出风格相似度、结构指标和复制风险。

## 场景生成接入

`generate-scene` 的 prompt pack 现在优先读取：

1. `style/style_prompt.md`
2. `style/*/style_prompt.md`
3. `style/style-profile.md`
4. `style/*/style-profile.md`

也就是说，一旦项目生成了 `style_prompt.md`，后续场景生成会优先注入这份 LLM 文风约束提示词。

## 边界

- `style-prompt` 不训练模型，只生成提示词资产。
- `style-prompt-eval` 的正式路径不调用本地 provider；候选由平台 Agent 回填。
- 统计指标只是辅助生成提示词和审查提示词有效性的证据。
- 精确模仿仅限公版或授权语料；其他语料应抽象为高层技法提示词。
- 提示词有效不等于作品可发布，仍需 canon、人物、剧情和原创性审查。
