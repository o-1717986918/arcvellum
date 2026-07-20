# Phase 35：Demo 与回归链路

## 目标

提供一个可重复、无版权风险、可 dry-run 演示的端到端文学工程项目，用于验证 Agent schema、审查、委员会和 workflow 联动。

## 新增能力

- `demo_project.py`
- `demo-project`
- demo 自造人物、背景故事、场景、草稿、规则审查、Agent 审查、Agent canon 审查、审稿委员会和 workflow state。

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench demo-project examples/demo-work --title "文学工程 Demo"
```

## 产物

- `reviews/agent/demo_walkthrough.md`
- `reviews/agent/scene_0001_scene_review.md`
- `reviews/agent/canon_review.md`
- `reviews/agent/committee_demo-scene-0001.md`
- `workflow/runs/demo-agent-scene-loop/workflow_state.json`

## 边界

Demo 使用自造文本和 dry-run agent，不依赖真实模型 key，也不包含受版权限制语料。
