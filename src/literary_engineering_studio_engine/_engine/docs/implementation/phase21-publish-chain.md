# Phase 21：发布链路

## 目标

建立章节级正式发布门禁。发布不是简单复制导出文件，而是把 canon 检查、章节 ready 状态、多格式导出和人工审批记录组合成可审计 release。

## 新增命令

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench publish-chapter work/demo-work --chapter-id chapter_0001 --approval-run-id run-ok
```

常用参数：

- `--release-id`：指定 release id，默认 UTC 时间戳。
- `--approval-run-id`：要求匹配指定 workflow run 的 approve 审批记录。
- `--allow-unapproved`：生成内部候选发布，不作为正式发布默认路径。
- `--rebuild-chapter`：发布前重建章节工作台和审查。
- `--rebuild-export`：发布前重建导出包。
- `--out-dir`：自定义 release 目录。
- `--overwrite`：允许覆盖已有 release 目录。
- `--export-formats`：指定发布导出格式，例如 `md,docx`。

## 默认门禁

`publish-chapter` 默认要求：

- `canon-lint` 无 blocking。
- `chapter-workspace` 中所有场景均为 `ready`。
- `export-package` 没有 skipped scenes。
- `workflow/approvals/index.jsonl` 中存在 `approve` 记录。

## 输出

默认输出到：

```text
releases/{chapter_id}/{release_id}/
```

包含：

- `publish_manifest.json`：发布 manifest、门禁结果、来源产物、发布产物和上一版指针。
- `release_notes.md`：发布说明。
- `rollback.md`：回滚说明。
- `{chapter_id}_novel.md`
- `{chapter_id}_screenplay.md`
- `{chapter_id}_video_prompt_pack.md`
- 当 `--export-formats md,docx` 时，包含对应 `.docx` 成品文件。
- `source_export_manifest.json`

同时更新：

```text
releases/{chapter_id}/latest.json
```

## 边界

- 发布不会自动确认 canon 写回候选。
- 发布不会删除旧版本。
- 回滚建议只更新 `latest.json` 指针，保留所有 release 目录用于审计。
- `--allow-unapproved` 只适合内部候选发布。
