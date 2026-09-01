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

## 1. 现象

文风工程的语义审查最后一次失败，不是因为审查者给出了错误的文学判断，而是因为审查者漏写了必填的 `evidence_limitations` 字段。审查结果进入合同校验后缺少这个字段，于是 Gate 将整份审查结果判为失败。

## 2. 建议的修复方向

1. 在 `style-review-agent-task` 的 hard constraints 中明确要求：
   - 保留审查骨架中的全部字段；
   - `evidence_limitations` 必须保持为列表；
   - 没有限制时填写 `[]`，而不是删除字段。
2. 在独立审查 prompt 资产中重复同一输出合同，避免 Agent 只从上下文中推断字段结构。
3. 不建议由 preflight 静默补齐这个字段，因为它是 Reviewer-owned evidence。自动补齐虽然能让 Gate 通过，但会削弱审查的真实性。

## 3. 为什么不是提示词质量问题

这次失败的核心不是审查者不会做文学判断，而是输出合同的约束不够显眼。审查任务需要模型同时做两件事：

1. 给出文学语义判断；
2. 严格保留机器绑定的审查骨架字段。

当第 2 项没有在 hard constraints 和 prompt 正文中同时强调时，模型容易只关注第 1 项而漏写 `evidence_limitations`。因此更适合通过合同措辞和回归测试来修复，而不是改写审查语义本身。

## 4. 验证建议

后续如果要落地代码修复，建议至少验证：

- targeted blueprint / prompt contract test；
- `python -m literary_engineering_studio_engine prompt-registry-validate --json`；
- 文风审查 loop 的定向测试；
- `python scripts/architecture_audit.py`；
- `python scripts/generate_module_map.py --check`。
