# Phase 33：多 Agent 审稿委员会

## 目标

让关键文本和剧情决策经过多个独立审稿角色，再由汇总 Agent 输出委员会意见，避免单一 Agent 单点判断。

## 新增能力

- `agent_committee.py`
- `agent-committee`
- 独立 reviewer run：`agents/committee/{committee_id}/{reviewer_id}/`
- 汇总 run：`agents/committee/{committee_id}/summary/`
- `reviews/agent/committee_{subject}.md`
- `reviews/agent/committee_{subject}.json`

## 默认审稿角色

- `chief-editor`
- `character-psychology`
- `canon-auditor`
- `style-auditor`
- `market-readability`
- `anti-homogeneity`

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-committee work/demo --subject scene-0001 --source drafts/scenes/scene_0001.md
```

## 边界

委员会输出仍是审查证据，不是发布批准。少数意见和分歧必须保留。
