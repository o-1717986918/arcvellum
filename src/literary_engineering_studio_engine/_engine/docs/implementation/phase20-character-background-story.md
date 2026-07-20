# Phase 20 Patch：人物背景故事

## 目标

为人物档案增加 `background_story`，让角色过去经历成为行为和剧情分支的隐性因果，而不是正文中直接交代的设定段落。

## 字段

```yaml
background_story:
  summary: ""
  formative_events: []
  behavior_influences: []
  reveal_policy: implicit_only
```

## 使用方式

- `summary`：背景故事核心摘要，供 Agent 理解人物长期动因。
- `formative_events`：塑造人物的关键事件。
- `behavior_influences`：这些经历如何影响角色选择、回避、误判、语气和关系处理。
- `reveal_policy`：默认 `implicit_only`，表示除非场景明确需要揭示，否则不能直接说明。

## 已接入链路

- `templates/character.yaml`：新增字段。
- `roleplay_lab.py`：角色推演读取背景故事，并要求只作为行为因果。
- `branch_lab.py`：分支评分和人物测试纳入背景故事。
- `context_packet.py`：上下文包提示背景故事不能覆盖 canon，也不能直接曝光。
- `scene_draft.py`：草稿工作台要求背景故事转化为动作、回避、误判、语气和潜台词。
- `generation_provider.py`：模型候选提示加入隐性使用边界。
- `canon_lint.py`：正式人物档案缺少背景故事时给出 warning。

## 边界

- 背景故事不是 canon 自动确认入口。
- 背景故事不能替代 BDI、当前信息差和场景目标。
- 背景故事不应直接出现在正文中，除非人工选择某场景承担“揭示过去”的叙事功能。
