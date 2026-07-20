# Phase 37：设定候选数据模型

本阶段新增 Agent 设定创作层的候选资产 schema。目标是让角色、背景故事、世界观、地点、组织、关系网和大纲都以结构化 JSON 候选进入项目，而不是直接写入正式 canon。

## 新增 schema

- `schemas/agent_outputs/character_profile.v1.schema.json`
- `schemas/agent_outputs/background_story.v1.schema.json`
- `schemas/agent_outputs/world_rules.v1.schema.json`
- `schemas/agent_outputs/location.v1.schema.json`
- `schemas/agent_outputs/organization.v1.schema.json`
- `schemas/agent_outputs/plot_outline.v1.schema.json`
- `schemas/agent_outputs/relationship_graph.v1.schema.json`

## 候选目录

- `characters/candidates/`
- `characters/candidates/background_stories/`
- `canon/candidates/world_rules/`
- `canon/candidates/locations/`
- `canon/candidates/organizations/`
- `plot/candidates/outlines/`
- `plot/candidates/relationships/`

所有候选必须带 `candidate_id`、`risks`、`source_paths` 和 schema 值。
