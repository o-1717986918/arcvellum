# Phase 67：最终正文口径、字数统计与 RP 门禁

本阶段修复两个容易影响正式生产的问题：

1. 最终交付文件不应暴露 `scene_0001`、`chapter_0001`、场景文件路径、上下文包路径等工程编号。
2. 草稿字数统计不应把状态变化、写回候选、canon 说明、prompt manifest 或 `[AGENT_TASK: ...]` 算作正文。

## 最终正文清洗

新增 `draft_text.py`，提供统一入口：

- `final_body_from_draft_text()`：先提取 `## 正文草稿`，再清洗最终可交付正文。
- `final_body_from_draft_path()`：从草稿文件读取并清洗。
- `clean_final_body()`：删除正文中误混入的内部痕迹。
- `count_delivery_chars()`：统计清洗后正文的去空白字符数。

清洗内容包括：

- `scene_0001` / `scene-0001` 等场景编号；
- `scene_id:`、`场景编号：`、`场景文件：`、`上下文包：` 等内部元数据行；
- `canon`、`prompt manifest`、`AGENT_TASK`、写回候选、状态变化候选、审查说明；
- Markdown 内部工作台标题，如“状态变化候选”“新增事实候选”“人物状态变化”等。

## 统计口径

以下模块统一改用清洗后正文口径：

- `chapter-workspace` 的 `draft_chars` 和 summary；
- `longform-audit` 的场景矩阵、summary 和规模进度判断；
- `export-package` 的 `export_manifest.json` 中 `draft_chars`。

字段名保持 `draft_chars` 以兼容已有 JSON 消费方，但语义更新为“清洗后可交付正文字符数，不含空白”。

## 交付导出

`export-package` 不再主动把内部 scene id 写入小说稿、剧本稿或长视频提示词包：

- 小说导出使用公开章节标题，如“第1章”。
- 剧本导出使用“第1场”等公开序号，不暴露 `scene_0001`。
- 视频提示词包使用“镜头组 1”等公开标签。
- `export_manifest.json` 仍保留 scene id 和路径，作为工程追溯文件，不属于最终正文。

## RP Agent 门禁

`simulate-scene --agent` 增加“平台 Agent 执行门禁”：

- 先读取 scene、context packet、正式人物档案、canon/world_rules.yaml、canon/forbidden_changes.yaml、plot/outline.md、plot/foreshadowing.csv。
- 在“读取回执”列出已读文件、缺失文件、不可突破硬约束和写回边界。
- 缺少关键资料时可以继续生成候选推演，但必须标注依据不足。
- RP 文件只保存推演与候选，不直接写入 canon、characters、scenes 或 drafts。

## 回归覆盖

新增或强化测试：

- `test_export_package.py`：最终小说、剧本、视频提示词包不得出现 `scene_0001`。
- `test_chapter_pipeline.py`：章节 `draft_chars` 只统计清洗后正文。
- `test_longform_audit.py`：长篇审计 `draft_chars` 只统计清洗后正文。
- `test_roleplay_lab.py`：`--agent` 模式必须包含执行门禁、读取回执和写回边界。
