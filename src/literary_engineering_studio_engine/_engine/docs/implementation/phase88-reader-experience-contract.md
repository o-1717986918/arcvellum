# Phase 88: Reader Experience Contract

状态：completed in v0.88.0

## 目标

Phase 88 将长篇“字数预算”继续推进到“章节义务与读者体验契约”。此前 `word-budget` 已能拆目标字数和场景库存，但正文生成仍可能只按事件摘要写，导致 50 万字目标被压缩成几万字。新机制要求平台 Agent 在正文生成前先明确每章和每场的读者推进义务。

## 新增模块

- `src/literary_engineering_workbench/reader_experience.py`
- `schemas/chapter_obligation_contract.v1.json`
- `schemas/reader_experience_contract.v1.json`
- `docs/modules/reader-experience-contract.md`
- `tests/test_reader_experience.py`

`reader_experience.py` 提供：

- `build_chapter_obligation_tasks()`
- `chapter_obligation_contract()`
- `reader_experience_contract()`
- `ensure_reader_experience_ready()`
- `render_reader_experience_contract()`
- `reader_experience_adherence_for_body()`

## CLI 接入

新增命令：

```powershell
python -m literary_engineering_workbench chapter-obligation <project> --chapter-id chapter_0001
```

该命令生成：

- `plot/chapter_obligations/{chapter_id}.json`
- `plot/chapter_obligations/{chapter_id}.md`
- `plot/chapter_obligations/{chapter_id}.agent_tasks.md`

它只创建脚手架。平台 Agent 必须填写章节功能、承诺兑现、设置、变化、暂不解决事项、继承钩子、章末钩子和逐场 reader-experience 字段，并创建相邻 `.agent_completion.json`。

`word-budget` / `longform-budget` 现在还会创建：

- `plot/chapter_obligations/chapter_obligations.agent_tasks.md`

这份通用侧车要求平台 Agent 做全局章节义务规划，并写出：

- `reviews/word_budget/chapter_obligation_review.md`

## 状态机接入

`longform-planning` route 在 `scene-inventory-review` 后新增：

```text
chapter-obligation-agent-task
-> chapter-obligation-review
-> ready
```

`scene-development` route 在 `scene-word-budget-contract` 后新增：

```text
reader-experience-contract
-> candidate-generation-provenance
```

也就是说，长篇场景必须先完成章节义务和读者体验契约，再进入正文候选生成。

## 生成链路接入

`prompt_pack.py` 现在会在生成前调用 `ensure_reader_experience_ready()`。如果契约缺失、字段未填、sidecar 未完成或状态不是 pass/ready，正式生成会直接阻塞。

prompt manifest 新增：

```json
{
  "generation_standards": {
    "reader_experience_contract": {},
    "reader_experience_loaded": true
  }
}
```

生成 `.agent_tasks.md` 也会要求主平台 Agent 读取并执行 reader contract，避免只写事件摘要。

## Review / Promotion / Export 接入

`agent-review-scene` 现在把 `reader_experience_adherence` 注入审查 prompt 和 JSON 输出。它要求平台 Agent 判断正文是否实际满足读者问题、承诺回报、兑现/延迟、张力来源、反摘要要求和读后余味。

`candidate_promotion.py`、`scene_readiness.py`、`chapter_pipeline.py`、`longform_audit.py`、`agent_task_status.py` 均已读取 reader gate：

- 契约缺失时，长篇候选不能生成。
- AgentReview 未写 `reader_experience_adherence` 时，长篇候选不能晋升。
- `reader_promise_satisfied=false` 时，章节 ready 和正式导出阻塞。
- route-audit 会把 reader-experience contract 作为 scene gate。

## 计数口径同步

Phase 88 延续 v0.87.0 的计数规则：

- 文风提示词长度以中文内容字符计算，计入汉字和中文标点。
- 长篇目标、章节目标、场景 `word_count_target/min/max` 以清洗后中文正文字符计算。
- 机器非空白字符只作诊断映射，不作为 pass/fail 基准。

`text_counts.chinese_machine_count_mapping()` 现在会记录机器数和中文数的差值，并在机器数明显膨胀时给出诊断警告，帮助发现正文是否混入工作流痕迹、英文路径或 JSON/Markdown 残留。

## 回归测试

新增和更新的重点测试：

- `tests/test_reader_experience.py`
- `tests/test_word_budget.py`
- `tests/test_task_registry.py`
- `tests/test_generation_provider.py`
- `tests/test_chapter_pipeline.py`
- `tests/test_agent_task_status.py`
- `tests/test_candidate_promotion.py`
- `tests/test_export_package.py`

本阶段防止以下历史问题复发：

- `word_budget.json` 生成了但没人读。
- 长篇规划到 scene inventory 就误判 ready。
- 场景正文生成时没有章节义务和读者体验硬属性。
- AgentReview 忽略 reader promise/payoff。
- 字数统计把 workflow、canon、路径或状态变化当正文。
