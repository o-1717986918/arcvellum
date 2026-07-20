# Phase 85：文件型 Prompt Registry

版本：`v0.85.0`

## 目标

让 `prompt_asset_id` 从任务包里的字符串升级为可解析、可校验、可预览、可注入的 Prompt Asset。平台 Agent 仍然负责创作和判断；Prompt Registry 负责把任务的提示词族、上下文组、硬约束、输出契约、审查要求和禁止捷径显式交给 Agent。

## 新增文件

1. `src/literary_engineering_workbench/prompt_registry.py`
2. `schemas/prompt_asset.v1.json`
3. `templates/prompt_assets/route.scene-development.v1.md`
4. `templates/prompt_assets/route.longform-planning.v1.md`
5. `templates/prompt_assets/route.source-ingest.v1.md`
6. `templates/prompt_assets/route.style-engineering.v1.md`
7. `templates/prompt_assets/route.character-world-assets.v1.md`
8. `templates/prompt_assets/route.review-audit.v1.md`
9. `templates/prompt_assets/route.export-release.v1.md`
10. `docs/modules/prompt-registry.md`

## 新增 CLI

```powershell
python -m literary_engineering_workbench prompt-registry-list
python -m literary_engineering_workbench prompt-registry-validate
python -m literary_engineering_workbench prompt-preview route.scene-development.prose.generate.v1
```

`prompt-registry-validate` 会检查：

1. Prompt Asset 必填字段。
2. frontmatter schema 是否为 `literary-engineering-workbench/prompt-asset/v1`。
3. 列表字段是否为列表。
4. Prompt body 是否非空。
5. `task_registry.py` 中的全部 `prompt_asset_id` 是否能通过 exact 或 wildcard asset 解析。

## Task-Open 接入

`task-open` 现在会在任务 Markdown 中写入 `## Prompt Asset`：

1. requested id
2. resolved id
3. wildcard match
4. version
5. title
6. output contract
7. prompt body

这使平台 Agent 打开任务时直接收到任务提示词资产，不再只看到一个装饰性的 id。

## 当前覆盖

当前采用路由级 wildcard asset 覆盖七条正式路线：

1. `route.scene-development.*.v1`
2. `route.longform-planning.*.v1`
3. `route.source-ingest.*.v1`
4. `route.style-engineering.*.v1`
5. `route.character-world-assets.*.v1`
6. `route.review-audit.*.v1`
7. `route.export-release.*.v1`

验证时覆盖 `task_registry.py` 中的全部 prompt id。后续可以为高风险任务增加 exact asset，例如正文生成、AgentReview、revision、style prompt execute。

## 测试

新增：

- `tests/test_prompt_registry.py`

覆盖：

1. 内置 Prompt Registry 校验通过。
2. route wildcard 能解析 exact task prompt id。
3. `task-open` 任务包包含解析后的 Prompt Asset。
4. CLI 暴露 list / validate / preview。
5. validate JSON 输出为 pass。
