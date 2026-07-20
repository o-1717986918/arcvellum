# Phase 29：Agent 场景审查

## 目标

> Current project-type skill override: `agent-review-scene` writes a platform-agent task sidecar and expected review paths. It does not call local `dry-run`, `http-chat`, or external agent services.

把单场景审查扩展为 LLM/Agent 语义审查。Agent 会读取 scene YAML、草稿、上下文包、上下文来源证明和文风提示词，输出符合 `scene_review.v1` 的结构化审查结果。`v0.86.0` 起，缺失或无效 context trace 时不得给出 clean pass。

## 新增能力

- `agent_scene_review.py`
- `agent-review-scene`
- `reviews/agent/{scene_id}_scene_review.md`
- `reviews/agent/{scene_id}_scene_review.json`

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-review-scene work/demo --scene scenes/scene_0001.yaml
```

## 审查维度

- 人物行为是否符合 BDI、背景故事、当前状态和关系。
- 场景目标是否被推进。
- 是否存在 canon 风险或未确认事实。
- 文风提示词是否在句法、叙述距离和意象调度上生效。

## 边界

Agent 场景审查与 `review-scene` 并行存在。它不能替代人工审批，也不能直接发布或写 canon。

`v0.66.0` 起，`pass_with_notes` 必须进入小修闭环：审查 JSON 的 `revision_actions` / `warnings` / `style_notes` 应给出可由 writing agent 局部执行的修改目标。下一轮场景生成会把这些 notes 注入 prompt manifest 的 `generation_standards.review_notes`，并要求 writing agent 执行或说明豁免。

`v0.71.0` 起，`scene_review.v1` 必须包含 `style_adherence`。当项目挂载 Style Skill 时，平台 Agent 需要明确审查挂载文风是否已经进入正文表达：叙述距离、句法节奏、意象/感官、心理呈现、对白语气、标点停顿和 AI 腔规避。`pass` / `pass_with_notes` 可进入后续门禁；缺失、`not_applicable` 或 `revise_required` 会被 `route-audit --route scene-development` 视为阻塞。
