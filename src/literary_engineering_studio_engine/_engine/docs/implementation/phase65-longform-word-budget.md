# Phase 65：长篇字数预算与剧情库存门禁

本阶段新增 `word-budget` / `longform-budget`，用于把长篇目标字数转化为可审计的卷、章、场景和叙事负载预算，并把扩纲与创作判断交给平台 agent。

## 背景

长篇项目常出现目标字数和实际产出严重脱节：用户要求 50 万字、5 卷，但模型生成的一卷只有 2 万字。这不是单纯的“字数约束不够强”，而是大纲规划没有把目标字数映射为足够的剧情库存。解决方向是把字数预算前置为标准链路门禁。

## 已实现能力

- CLI 命令：`word-budget`
- CLI 别名：`longform-budget`
- 协议路线：`longform-planning`
- 预算输出：`plot/word_budget/word_budget.md`
- 机器可读预算：`plot/word_budget/word_budget.json`
- 平台 agent 任务：`plot/word_budget/word_budget.agent_tasks.md`
- 分章分场景库存任务：`plot/word_budget/scene_inventory_expansion.agent_tasks.md`
- 章节义务规划任务：`plot/chapter_obligations/chapter_obligations.agent_tasks.md`
- 预算化大纲候选目标：`plot/candidates/outlines/word_budget_expansion.md`
- 分场景库存候选目标：`plot/candidates/scenes/word_budget_scene_inventory.md`
- 预算审查目标：`reviews/word_budget/word_budget_review.md`
- 场景库存审查目标：`reviews/word_budget/scene_inventory_review.md`
- 章节义务审查目标：`reviews/word_budget/chapter_obligation_review.md`

## 设计边界

CLI 负责确定性计算：

- 读取 `project.yaml` 的 `target_length` / `genre` / `longform_budget.volumes`。
- 根据类型预设估算章数、场景数、平均章中文内容字符、平均场景中文内容字符。
- 按卷数分配总目标中文内容字符，保持总和严格等于目标。
- 扫描现有大纲、`scenes/*.yaml` 和已写草稿的清洗后正文，判断剧情库存、章节库存和实际中文内容字符是否明显不足。
- 生成每章目标中文内容字符、实际正文中文内容字符、机器非空白字符诊断、已有场景数、推荐场景数、缺失场景数和扩场景任务入口。
- 输出 `.agent_tasks.md`，明确平台 agent 下一步要写什么。

平台 agent 负责非确定性判断：

- 类型、时间跨度与目标字数是否匹配。
- 是否应增加人物线、地点、时间跨度、章节层级或伏笔网络。
- 预算化大纲是否有足够叙事密度，而不是机械拉长。
- 分场景库存是否能用具体事件、关系转折、线索、后果链和伏笔回收支撑每章字数。
- 是否建议缩短目标字数或调整卷数。
- 是否批准候选大纲进入正式 `plot/outline.md`。

## 类型预设

内置预设包括：

- `general`：通用长篇。
- `mystery`：悬疑、推理、惊悚。
- `speculative`：科幻、奇幻、玄幻。
- `urban`：都市、职场、现实题材。
- `literary`：严肃文学、文学性叙事。

每个预设包含平均章字数、平均场景字数、每章场景范围，以及主线推进、关系推进、世界信息、后果链和喘息段落的负载比例。

## 标准链路

```powershell
python -m literary_engineering_workbench protocol longform-planning
python -m literary_engineering_workbench word-budget "<work-dir>" --target-words 500000 --volumes 5 --genre mystery --time-span "三年"
```

然后平台 agent 读取：

```text
plot/word_budget/word_budget.agent_tasks.md
```

并写出：

```text
plot/candidates/outlines/word_budget_expansion.md
plot/candidates/scenes/word_budget_scene_inventory.md
reviews/word_budget/word_budget_review.md
reviews/word_budget/scene_inventory_review.md
reviews/word_budget/chapter_obligation_review.md
```

最后运行：

```powershell
python -m literary_engineering_workbench longform-audit "<work-dir>" --target-length 500000
```

## 与生成链路的集成

`prompt_pack.py` 会在构建场景生成 prompt 时读取 `plot/word_budget/word_budget.json`。如果文件存在，prompt manifest 的 `generation_standards` 会包含：

- `word_budget`
- `word_budget_loaded`
- `word_budget_path`

用户 prompt 中也会追加“长篇字数预算标准”。因此预算不是只在审查阶段出现，而是进入生成前硬约束。

后续增强：`v0.87.0` 起，正式通过口径为清洗后中文内容字符，计入汉字和中文标点；机器非空白字符只作为诊断映射。`v0.88.0` 起，`word-budget` 还会派发章节义务规划侧车，单章生成前需运行 `chapter-obligation --chapter-id <chapter_id>`，让平台 agent 建立 reader-experience contract，防止长篇目标被压缩成摘要。

## 与长篇审计的集成

`longform-audit` 现在会读取 `plot/word_budget/word_budget.json` 并检查：

- 目标超过中长篇规模但缺少预算。
- 预算状态为 `needs_expansion`。
- 现有场景数量远低于预算场景数。

这些风险会进入 `reviews/longform/longform_audit.md` 和 JSON。

## 完成标准

- `protocol longform-planning` 可解析。
- `word-budget` 和 `longform-budget` 可生成预算报告、JSON 和任务侧车。
- 新建项目包含 `plot/word_budget/` 和 `reviews/word_budget/`。
- 场景生成 prompt manifest 自动加载预算标准。
- `longform-audit` 会报告预算缺失和场景库存不足。
- `route-audit --route longform-planning` 会报告预算化大纲、分场景库存和 route gate 完成情况。
- 回归测试覆盖 CLI、prompt manifest 和审计联动。
