# 新角色登记门禁

`v0.86.1` 起，正式场景开发必须处理正文中新出现的人物。核心原则：

> 新角色可以被创作出来，但不能从正文旁路进入正式项目资产。

## 1. 分类

场景开发中出现的人物分三类：

1. **已登记角色**：存在于 `characters/*.yaml`，或在 scene.yaml 的 `participants` / `referenced_characters` / `character_refs` 中明确引用。
2. **一次性路人**：没有名字或只有功能性称谓，不复用、不改变关系网、不掌握关键线索、不影响后续剧情。
3. **持久新角色**：有名字、会再出现、掌握线索、推动关系、改变世界状态、承担主线功能或影响后续场景。

## 2. 处理规则

已登记角色按正常 scene-development 链路处理。

一次性路人可以留在本场景中，但 AgentReview 必须在 `new_character_register` 中写 `status=ephemeral_only`，并提供 `waiver_reason`。例如“码头搬运工只用于场面调度，不再复用，不产生状态债务”。

持久新角色必须进入正式资产链路：

1. 运行 `agent-create-character` 或 `asset-create --asset-type character`。
2. 平台 Agent 写 `characters/candidates/<id>.json` 与候选报告。
3. 运行 `review-candidate-asset` 并由平台 Agent 写 clean review。
4. 取得用户 approval。
5. 运行 `promote-candidate-asset` 晋升到 `characters/*.yaml`。

未完成这些步骤时，场景 review 不得 clean pass，promotion / chapter readiness / export readiness 也不得放行。

## 3. new_character_register

候选 manifest 与 AgentReview JSON 都应包含：

```json
{
  "schema": "literary-engineering-workbench/new-character-register/v0.1",
  "status": "none | existing_only | ephemeral_only | candidates_ready | resolved | needs_candidate | needs_review | needs_approval",
  "introduced": [
    {
      "name": "",
      "character_id": "",
      "scene_function": "",
      "persistence": "ephemeral | recurring | major | plot",
      "already_in_characters": false,
      "formal_character_path": "",
      "candidate_path": "characters/candidates/<id>.json",
      "review_path": "reviews/assets/<id>_review.json",
      "approval_run_id": "",
      "promotion_manifest": "",
      "waiver_reason": ""
    }
  ],
  "ephemeral_waivers": [],
  "blocking_issues": []
}
```

Clean statuses:

1. `none`
2. `existing_only`
3. `ephemeral_only`，需要豁免理由
4. `resolved`，持久新角色已完成 approval 或 promotion

Blocking statuses:

1. `needs_candidate`
2. `needs_review`
3. `needs_approval`
4. `unknown`
5. `blocked`

`candidates_ready` 可以出现在候选生成 manifest 中，表示候选角色资产已准备好；但在 AgentReview clean pass 前仍必须完成 approval 或 promotion。

## 4. 接入点

1. `generate-scene` 的 prompt manifest 注入新角色登记契约。
2. 生成 sidecar 要求候选 Markdown 包含 `## 新角色候选登记`，候选 manifest 包含 `new_character_register`。
3. `agent-review-scene` prompt 要求输出 `new_character_register`。
4. `candidate_generation_gate` 阻塞缺失或未解决的生成 manifest register。
5. `candidate_review_gate`、`scene_readiness`、`route-audit` 阻塞未解决的 AgentReview register。
6. `state-evolve` 要求把持久新角色列为 unresolved，并建议走角色候选资产路线。
7. 最终正文清洗会过滤 `## 新角色候选登记`，避免工程段落进入交付作品或字数统计。

## 5. 推荐实践

不要为了避开门禁把角色写成“某人”“那人”但又让他承担后续线索功能。功能上是持久角色，就应登记。

不要把新角色直接追加到 `characters/*.yaml`。先进入 `characters/candidates/`，再 review、approval、promotion。

不要让 subagent 创作正式正文里的新角色。subagent 可以整理候选档案、证据和审查意见；正文中的角色引入仍由主平台 Agent 负责。
