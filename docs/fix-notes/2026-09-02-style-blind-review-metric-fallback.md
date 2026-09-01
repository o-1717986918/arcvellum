# Style blind-review metric fallback fix

## Module Change Packet

```yaml
module_change_packet:
  objective: "内置定性 Style Profile 缺少数值目标时，blind-review 仍可用 reference 计算标点与感官匹配，避免候选被必然压成零分"
  primary_module: "literary_engineering_studio_engine.literary.style.evaluator"
  public_entry: "evaluate_style(StyleEvalOptions)"
  variation_point: "punctuation/sensory profile target selection"
  inputs: ["style_metrics.json", "reference text", "candidate text"]
  outputs: ["style_eval_current.json 分项评分", "style_eval_current.md"]
  invariants: ["不修改候选或评分文件", "不 reinterpret failed gate", "已有显式 Profile 数值目标优先于 reference fallback"]
  allowed_dependencies: ["literary/style/compiler.analyze_style"]
  forbidden_dependencies: ["model provider abstraction", "API-key storage", "direct HTTP LLM client"]
  tests: ["tests.test_style_evaluation_loop metric fallback regression", "prompt registry validation", "architecture audit"]
  rollback_unit: "one Git commit"
  documentation: ["docs/fix-notes/2026-09-02-style-blind-review-metric-fallback.md"]
```

## Change

- `punctuation_top` and `sensory_counts` now fall back to the reference-derived metrics only when the Profile has no numeric value for that dimension.
- The fallback matches the existing behavior already used by rhythm and narrative density targets, so an `arcvellum/builtin-style-metrics/v1` qualitative preset does not force both dimensions to zero.
- Explicit numeric Profile targets remain authoritative when present.

## Verification

- New regression test first failed with `punctuation = 0.0`, then passed after the fallback.
- Targeted style loop tests passed.
- Prompt registry validation, architecture audit, module-map check, and Studio doctor passed.
