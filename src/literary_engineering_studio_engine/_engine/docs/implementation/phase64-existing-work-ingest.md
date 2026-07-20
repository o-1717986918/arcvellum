# Phase 64：已有作品反推与源文本导入

本阶段实现 `source-ingest` / `extract-existing-work`。

目标：让用户输入已有文本、完整作品、旧稿、剧本或伪记录材料时，项目可以先把源材料工程化保存，再由平台 Agent 反推出标准项目文件候选，用作续写、改写、改编或分析基础。

## 架构决策

- CLI 只做确定性准备：读源文本、写 raw、分块、写 manifest/report、写 `.agent_tasks.md`。
- 平台 Agent 做文学判断：人物、背景故事、世界观、剧情、时间线、伏笔和文风说明的提取都由装载 Skill 的 Codex/Claude 完成。
- 反推结果写入候选区，不直接覆盖正式 canon、角色文件、plot、style、draft、export 或 release。
- 每条重要结论应带证据引用、置信度、未知项和矛盾说明。

## 新增模块

- `src/literary_engineering_workbench/source_ingest.py`
- CLI 命令：`source-ingest`
- CLI 别名：`extract-existing-work`
- 协议路线：`source-ingest`
- 测试：`tests/test_source_ingest.py`

## 文件结构

导入产物：

```text
sources/imports/{work_id}/raw/*.txt
sources/imports/{work_id}/chunks/chunk_0001.md
sources/imports/{work_id}/source_manifest.json
sources/imports/{work_id}/source_ingest.md
sources/imports/{work_id}/extract_project_files.agent_tasks.md
```

平台 Agent 预期写入：

```text
sources/imports/{work_id}/extracted/project_brief.md
characters/candidates/extracted/{work_id}_characters.md
canon/candidates/extracted/{work_id}_world.md
plot/candidates/extracted/{work_id}_outline.md
plot/candidates/extracted/{work_id}_timeline.md
plot/candidates/extracted/{work_id}_foreshadowing.md
style/candidates/{work_id}_style_generation_notes.md
reviews/source_ingest/{work_id}_extraction_review.md
```

## 使用示例

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench protocol source-ingest
python -m literary_engineering_workbench source-ingest "work/demo" --source "old-draft.md" --title "旧稿" --work-id old-draft --mode continuation
```

然后平台 Agent 读取：

```text
sources/imports/old-draft/extract_project_files.agent_tasks.md
```

并按任务写候选文件和审查报告。

## 完成门禁

- `source_manifest.json`、chunk 文件和 `.agent_tasks.md` 存在。
- 平台 Agent 已写入候选文件，或在最终报告中明确列为待处理。
- 反推结论带证据引用和置信度。
- 未经审查与用户批准，不晋升任何源作品提取内容。

## 测试覆盖

- 导入源文件并生成 manifest、chunks、report 和任务侧车。
- CLI `source-ingest` 支持 inline text。
- `protocol source-ingest` 可解析并出现在 help 中。
