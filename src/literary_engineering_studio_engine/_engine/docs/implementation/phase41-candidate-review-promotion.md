# Phase 41：候选审查与晋升机制

本阶段实现候选资产审查和受控晋升。

## 新增命令

- `list-candidate-assets`
- `review-candidate-asset`
- `promote-candidate-asset`
- `promote-character-candidate`
- `promote-world-candidate`
- `promote-outline-candidate`

## 晋升边界

默认必须存在 `approve` 审批记录，`run_id` 可使用候选资产的 `candidate_id`。内部实验可以使用 `--allow-unapproved`，但会写入 promotion manifest。

晋升输出：

- 角色：`characters/*.yaml`
- 背景故事：更新 `characters/{id}.yaml` 的 `background_story`
- 关系网：`plot/relationship_graph.json`
- 世界观：`canon/world_rules.yaml`
- 地点：`canon/locations.yaml`
- 组织：`canon/organizations.yaml`
- 大纲：`plot/outline.md` 和候选 `scenes/*.yaml`
