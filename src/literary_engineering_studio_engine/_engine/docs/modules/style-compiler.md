# 风格编译器

输入语料，先输出风格 profile、统计指标、语料清单和评测样例，再通过 `style-prompt` 生成供 LLM 写作时直接注入的 `style_prompt.md`。

`style-prompt-eval` 使用 `style_prompt.md + LLM provider` 生成回译文本、大纲扩写文本或盲评候选，再调用 `style-eval` 审查这份提示词是否有效。

关注维度：叙事距离、句长节奏、意象密度、心理描写方式、对话比例、段落组织、主题母题。

边界：非授权作者不做精确复刻，只做高层技法抽象。统计指标不是最终产物，最终产物是可执行、可复审的 LLM 文风约束提示词。

## 正式路线门禁

从 `v0.84.4` 起，项目内 `style/{profile}/` 目录进入 `style-engineering` task loop：

```powershell
python -m literary_engineering_workbench task-next <project> --route style-engineering
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
```

正式挂载前必须满足：

1. `style-profile.md` 与 `style_metrics.json` 存在。
2. `style_prompt.agent_tasks.md` 已处理，并有 `style_prompt.agent_completion.json`。
3. 平台 Agent 写出 `style_prompt.md` 与 `style_prompt.agent.json`。
4. `style_prompt.md` 为 500-2500 中文内容 detail chars，计入汉字和中文标点，不计入 Markdown 标记、英文路径、代码围栏或空白，并包含身份/边界、核心机制、叙述距离、句法节奏、标点、意象感官、心理/行为、对白、AI 腔控制、禁止倾向和输出自检。
5. 至少一个 `evaluation_results/*/style_eval_*.json` 被接受，不能是高复制风险或低相似度。
