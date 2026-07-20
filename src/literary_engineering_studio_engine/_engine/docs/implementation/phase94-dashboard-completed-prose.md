# Phase 94：项目总控已完成正文主模块

版本：`v0.92.0`

## 目标

把“已完成正文”从作品档案的二级分类提升为项目总控页的显眼主模块。用户打开本地控制台时，应该先看到作品实际产出，而不是只看到流程状态、JSON 证据和 route 门禁。

## 实现

### 后端

`project_library.py` 新增 `completed_prose` 摘要：

1. 优先聚合 `releases/**/*_novel.md` 中的正式发布正文。
2. 其次聚合 `exports/**/*_novel.md` 中的正式导出正文。
3. 再展示 `drafts/chapters/*.md` 和 `drafts/scenes/*.md` 中的已合稿/已晋升正文。
4. 候选稿与修订候选仍留在 `sections.drafts` 中展示，但不会作为“已完成正文”优先对象。

`display_cleaner.py` 调整正文展示口径：先按最终交付正文规则过滤工程痕迹，再清理 Markdown 标题、链接、代码块、sidecar、scene id、workflow、canon notes 等前端不应直接暴露的符号。

### 前端

项目总控页新增“已完成正文”主模块，位于“当前判断”和流程指标之间：

1. 左侧展示当前正文中文内容字数。
2. 右侧展示最优先的正式正文预览。
3. 下方展示另外几份已完成正文入口。
4. “查看全部正文”跳转到“作品档案 / 正文草稿”。

该模块只读，不晋升候选稿，不创建 completion marker，不绕过审查与导出路线。

## 边界

1. 总控正文展示以用户阅读体验为主，不显示内部路径细节、原始 JSON、任务 sidecar 或状态写回候选。
2. 正文统计使用清洗后的中文内容字数。机器非空白字符仍只是诊断数据。
3. 若项目还没有发布、导出、合稿或已晋升正文，模块显示空状态并提示等待正式审查/晋升/导出。

## 测试

`tests/test_api_server.py` 覆盖：

1. `/project/library` 返回 `completed_prose`。
2. 正式导出正文优先进入完成正文摘要。
3. 完成正文展示不包含 Markdown `#`、`scene_0001` 和工作流程痕迹。
4. 前端首页包含“已完成正文”主模块。
5. 前端脚本包含 `renderDashboardProse` 和 `openLibraryDrafts`。
