# Phase 40：Agent 大纲与剧情骨架创作

本阶段新增大纲候选生成命令。

## 新增命令

- `agent-create-outline`
- `agent-create-chapter-plan`
- `agent-create-scene-list`

这些命令都生成 `plot_outline.v1` 结构，写入 `plot/candidates/outlines/`。正式晋升前不会覆盖 `plot/outline.md` 或 `scenes/*.yaml`。

## 输出字段

- `premise`
- `central_conflict`
- `acts`
- `chapters`
- `scene_list`
- `character_arcs`
- `foreshadowing`
- `risks`
