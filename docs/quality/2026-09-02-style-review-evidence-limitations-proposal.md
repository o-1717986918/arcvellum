# 文风语义审查：`evidence_limitations` 合同缺口建议

> 状态：建议 / review note  
> 日期：2026-09-02  
> 影响模块：`literary_engineering_studio_engine.literary.style.review` 与 `routes/style` 审查蓝图  
> 本文档只提出问题与建议，不包含代码修复。

## Module Change Packet

```yaml
module_change_packet:
  objective: "文风语义审查任务显式要求审查结果保留 evidence_limitations 字段，避免审查者漏写导致语义 Gate 反复失败"
  primary_module: "literary_engineering_studio_engine.literary.style.review / routes.style review blueprints"
  public_entry: "style-engineering build_task_payload + prompt registry resolved asset"
  variation_point: "style semantic review Agent contract wording"
  inputs: ["digest-bound style_semantic_review.json skeleton", "route.style-engineering.review.execute.v1 prompt asset"]
  outputs: ["style_semantic_review.json with all skeleton fields and evidence_limitations list"]
  invariants: ["route-audit remains final", "preflight must not silently invent model-owned review fields", "Reviewer cannot change machine-owned digests"]
  allowed_dependencies: ["existing style review gate", "prompt registry"]
  forbidden_dependencies: ["model provider abstraction", "API-key storage", "direct HTTP LLM client"]
  tests: ["targeted blueprint/prompt contract test", "prompt registry validation", "style evaluation loop"]
  rollback_unit: "one documentation-only Git commit"
  documentation: ["docs/quality/2026-09-02-style-review-evidence-limitations-proposal.md"]
```

## 1. Bug 的具体表现

《全频阻塞》的文风工程流程走到 `style-review-agent-task` 时，Reviewer 已经写出了有效的语义结论：`verdict=revise`，并且有 `summary`、`findings`、`required_changes`、`effectiveness_assessment`、`copy_risk_assessment`。这些内容说明审查者完成了文学判断。

问题出在 `style_semantic_review.json` 的结构：Reviewer 把 `evidence_limitations` 字段删掉了，而不是保留为空列表：

```json
{
  "verdict": "revise",
  "summary": "...",
  "findings": [],
  "required_changes": [],
  "effectiveness_assessment": "...",
  "copy_risk_assessment": "...",
  "evidence_limitations": []
}
```

失败时的实际结构缺少最后一行 `evidence_limitations`。但合同校验不会把“字段缺失”和“没有限制”视为等价，因为 `_review_content_errors()` 对以下三个字段都要求必须是 list：

- `findings`
- `required_changes`
- `evidence_limitations`

于是缺失字段会产生：

```text
style semantic review evidence_limitations must be a list
```

随后 `inspect_style_semantic_review()` 返回：

```text
stage = revision
message = style review contract is invalid
errors = ["style semantic review evidence_limitations must be a list"]
```

## 2. 对流程的影响

这个失败会被状态机解释为审查合同无效，然后进入 `style-review-revision`。也就是说，即使 Reviewer 的文学判断本身是可读、有证据、有 `required_changes` 的，流程仍会把它当成“审查结果不合格”处理。

更麻烦的是，这类失败不是一次性的：

- Reviewer 每轮都可能重新填写 `style_semantic_review.json`；
- prompt 原来只强调文学审查、证据、verdict 和不读 holdout，没有把“保留骨架全部字段”作为硬约束重复到 prompt 正文；
- 因此下一轮 Reviewer 仍可能继续漏写同一个字段；
- 状态机就继续回到 revision，形成“语义判断看起来已经完成，但 Gate 一直卡住”的循环。

## 3. 精确根因

这不是提示词不知道“没有限制该怎么表达”，而是输出合同的保留要求太弱。

`skeleton` 已经给过默认值：

```json
"evidence_limitations": []
```

但任务契约和 prompt 没有同时强调：

1. 骨架字段不能删除；
2. `evidence_limitations` 是必填 list；
3. 没有限制时必须写 `[]`。

所以 Reviewer 很容易把注意力放在文学判断上，误以为没有限制就可以省略该字段。

## 4. 建议

后续修复应做三件事：

1. **在 `style-review-agent-task` 的 hard constraints 中显式写明**  
   要求保留 `style_semantic_review.json` 骨架中的全部字段；`evidence_limitations` 必须保持为 list；没有限制时填 `[]`。

2. **在 `route.style-engineering.review.execute.v1` prompt 正文中重复同一要求**  
   不只放在蓝图里。Reviewer 实际读取的是完整任务说明，字段保留要求必须在 prompt 正文再次出现，而不是只依赖 schema 或上下文推断。

3. **不要让 preflight 静默补齐该字段**  
   `evidence_limitations` 是 Reviewer-owned evidence。如果 preflight 自动补 `[]`，Gate 虽然会通过，但等于替审查者声明“没有证据限制”，这会削弱审查语义。正确方向是让 Reviewer 明确写出这个字段，并在合同测试中验证任务契约和 prompt 都包含该要求。

## 5. 建议验证

- targeted blueprint / prompt contract test；
- `PYTHONPATH=src python -m literary_engineering_studio_engine prompt-registry-validate --json`；
- 文风审查 loop 定向测试；
- `PYTHONPATH=src python scripts/architecture_audit.py`；
- `PYTHONPATH=src python scripts/generate_module_map.py --check`。
