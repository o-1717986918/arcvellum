# Phase 42：设定创作工作流集成

本阶段扩展 `run-workflow`，加入设定创作模式。

## 新增模式

- `project-seeding`：生成世界观、角色和大纲候选，并逐一审查。
- `character-lab`：生成角色、背景故事和关系网候选。
- `worldbuilding-lab`：生成世界规则、地点和组织候选。
- `outline-lab`：生成大纲、章节计划和场景列表候选。

这些模式只生成候选与审查报告，并设置 `human_approval_required=true`。晋升仍需人工 approve。
