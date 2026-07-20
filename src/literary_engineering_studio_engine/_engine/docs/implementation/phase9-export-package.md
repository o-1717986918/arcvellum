# Phase 9：视频提示词与多格式导出

命令：`export-package`

输出小说章节、剧本工作稿、长视频提示词包和 `export_manifest.json`。默认只导出 `ready` 场景。

`v0.67.0` 起，最终交付文件使用统一的“清洗后正文”口径：

- 小说、剧本、长视频提示词包不再把 `scene_0001`、`chapter_0001` 这类工程编号暴露为正文标题。
- 正文清洗会移除误混入正文区的 scene 编号、场景文件路径、上下文包、canon 说明、prompt manifest、`[AGENT_TASK: ...]`、状态变化候选、`世界状态变化` 和写回候选。
- `export_manifest.json` 仍保留 `scene_id`、草稿路径和审查路径，用于工程追溯；manifest 不是最终正稿。
- `draft_chars` 统计为清洗后可交付正文的去空白字符数，不把工作流程、审查说明或写回候选算作正文字数。

`v0.73.0` 起，`export-package` 在正式打包前默认重建章节工作台，并阻塞任何非 ready 场景：

- `ready` 必须满足 context、RP 读取回执、branch manifest、正式 branch selection、ready composition、静态 review clean `pass`、平台 AgentReview clean `pass` 且引用当前草稿。
- `pass_with_notes`、warnings、revision_actions、style_notes、style_adherence 偏差、旧章节 JSON 或缺失门禁都会阻塞正式导出。
- `--include-blocked` 只用于内部预览，不能作为最终交付或发布路径。

新增 DOCX 交付能力：

```powershell
python -m literary_engineering_workbench export-package work/demo-work --chapter-id chapter_0001 --formats md,docx
python -m literary_engineering_workbench export-docx work/demo-work/exports/chapter_0001/chapter_0001_novel.md --kind novel
```

- `--formats md,docx` 会在保留 Markdown 源导出的同时生成 `{chapter_id}_novel.docx`、`{chapter_id}_screenplay.docx` 和 `{chapter_id}_video_prompt_pack.docx`。
- DOCX 是最终交付文件，不是 canon；正式写回仍以章节工作台、审查和审批记录为准。
- DOCX 生成使用标准库打包 WordprocessingML，不增加第三方运行依赖。
