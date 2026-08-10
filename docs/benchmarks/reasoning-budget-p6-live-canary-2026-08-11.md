# ReasoningBudget P6 Live Canary

- Date: `2026-08-11`
- Runtime: `pi-worker`
- Model: `deepseek/deepseek-v4-flash`
- Product default changed: `false`
- Prompt v3 promoted: `false`
- Content policy: metrics and digests only; no prompt, prose, reasoning text, credentials, or absolute paths

## Finding And Fix

DeepSeek V4 advertises `off`, `high`, and `max`; `low` is not supported. Generic Pi level clamping selected the next higher supported level, so ArcVellum's requested `low` silently became `high`. The first structured run therefore used 13,352 reasoning tokens against a 2,048-token task target.

The specialized Worker now applies a safe floor: an unsupported requested level may resolve only to the same or a lower supported level. If no safe lower level exists, execution fails before the Provider request. The requested and effective levels are both recorded.

## Same-Task Structured Comparison

| Metric | Before safe floor | After safe floor |
| --- | ---: | ---: |
| Result | waiting writeback | waiting writeback |
| Effective reasoning | implicit high | off |
| Reasoning tokens | 13,352 | 0 |
| Provider requests | 1 | 4 |
| Total time | 136.8 s | 57.3 s |
| Cost | $0.005760 | $0.003378 |
| Repairs | 0 | 0 |

Both runs produced locally valid outputs and reached Studio's writeback approval boundary. The safe-floor run reduced elapsed time by about 58% and cost by about 41%, while preserving the deterministic preflight outcome.

## Review Probe

The review canary also resolved `low` to `off`, reported 0 reasoning tokens, completed in 97.2 seconds at about $0.006101, and reached writeback approval with no repair. It used all 4 allowed Provider requests.

## Gate Decision

- Safe level control: pass.
- Provider request cap: pass.
- Receipt identity and effective-level observability: pass.
- Structured/review preflight: pass for these probes.
- Exact per-request reasoning token control on DeepSeek: unsupported/partial.
- Repeated-run variance and literary blind quality: not proven.
- Prompt v3 live A/B: not run; formal prompts remained v2 with v3 shadow metrics.

P6 may remain an opt-in technical canary. Product defaults and P7 creative/planning/prose expansion remain blocked until P3-P4 live v3 A/B and quality gates pass.
