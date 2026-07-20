# Phase 19：Canon / Plot Lint

## 目标

提供项目级一致性检查器，在正式导出、章节发布或大规模扩写前检查 canon、人物、场景、章节状态和伏笔状态。

## 新增命令

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench canon-lint work/demo-work
```

输出：

```text
reviews/canon_lint.md
reviews/canon_lint.json
```

## 检查范围

- 必需项目文件是否存在。
- `canon/facts.json` 是否可解析，是否存在 conflicts / candidates。
- 正式人物档案是否缺少 `character_id`、`name`、`role` 或 BDI。
- 场景是否缺少 `scene_id`、`chapter_id`、`location`、`participants`。
- 场景参与者是否能匹配人物档案中的 `character_id` 或 `name`。
- 时间线是否为空。
- 伏笔表是否为空、状态是否有效、setup scene 是否匹配。
- 章节状态 JSON 是否可解析，章节内是否存在非 ready 场景。
- 草稿写回候选是否仍未确认。

## 状态

- `pass`：无问题。
- `pass_with_warnings`：存在 warning / info，但无 blocking。
- `blocked`：存在 blocking，正式导出或发布前必须处理。

## 边界

- `canon-lint` 只检查和报告，不自动修改 canon。
- 初始规划项目出现 warnings 是正常的。
- Blocking 用于阻断正式交付，而不是阻止早期探索。
- 写回候选仍需人工确认，不能由 lint 自动确认为 canon。
