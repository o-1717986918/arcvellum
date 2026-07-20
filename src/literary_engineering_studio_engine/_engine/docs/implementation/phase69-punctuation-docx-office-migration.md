# Phase 69：引号统一与 DOCX 版式规划补强

本阶段处理两个问题：横排中文正文中「」/『』等角引号与“”混用，导致章节标点风格不统一；以及 DOCX 能力只完成基础生成，尚未充分吸收 `office-academic-skill` 中有价值的版式规划和文件质量检查思想。

## 已实现能力

- 标点规范明确：横排文学正文直接引语统一使用“”，内层引语使用‘’。
- `lint_punctuation()` 新增 `corner-quotes-in-horizontal-prose`，会在 review 中提示「」『』、﹁﹂﹃﹄、｢｣等竖排/角引号混入。
- 最终导出读取正文时会做安全的引号归一化，把角引号转换为“”/‘’，防止章节合并后交付稿风格散乱。
- `export-docx` 现在为每个 DOCX 生成 companion layout plan：`{stem}.layout.json`。
- `export-docx` 现在为每个 DOCX 生成 companion inspection report：`{stem}.inspection.json`。
- DOCX inspector 会记录段落数、表格数、样式、编号、东亚字体、页面尺寸、页边距和潜在警告。
- Markdown 简单表格会转换为原生 Word 表格，而不是保留 pipe 文本。
- `export-package --formats md,docx` 会把 DOCX、layout plan、inspection report 路径写入 `export_manifest.json`。

## Office Academic Skill 差距结论

已参考 `zLanqing/codex-claude-academic-skills` 中 `office-academic-skill` 的 Office/DOCX 思路。当前文学 skill 已吸收以下共通能力：

- 可编辑 DOCX 生成；
- 结构化标题与 Word 样式；
- 中文/英文分字体；
- 真实 Word 列表；
- 基础 Markdown 表格到原生 Word 表格；
- OOXML 包结构检查；
- 版式规划与生成后检查留痕。

未迁移且暂不应迁移的内容：

- 学术论文证据链、图表/公式/引用抽取；
- PPT 模板匹配、PowerPoint COM、幻灯片溢出检查；
- DOCX tracked changes、comments/replies、复杂图片/公式/引用插入；
- 完整 XSD 级 OOXML schema validation。

这些能力属于学术 Office 工作流。文学工程主线只需要最终作品、剧本工作稿、视频提示词包和项目报告的稳定可编辑交付，因此迁移范围应保持在文学交付需要的 DOCX 版式、检查和打包能力上。

## 完成标准

- 场景审查能发现角引号混入。
- 最终 Markdown/DOCX 导出统一横排中文引号。
- 单文件 DOCX 和 export package 都生成 layout/inspection 伴随文件。
- DOCX inspection 能识别基本 OOXML 结构、字体、样式、编号、页面设置和表格。
- 回归测试覆盖标点、导出归一化、DOCX 表格、layout plan 和 inspection report。
