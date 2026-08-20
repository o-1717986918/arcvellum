# ArcVellum Prompt v3 Compile Canary

- revision: `f916859976b011532dd6`
- status: `pass`
- mode: compile-only; no model was invoked.

| case | class/runtime kind | v2 chars | v3 chars | reduction | gate | duplicate | lint | status |
|---|---|---:|---:|---:|---:|---:|---|---|
| structured-world-foundation | structured/creative | 17467 | 9732 | 44.3% | 30% | 0.0% | pass | pass |
| analysis-scene-roleplay | analysis/creative | 45028 | 12859 | 71.4% | 60% | 2.2% | pass | pass |
| prose-scene-generation | prose/prose | 173556 | 14765 | 91.5% | 80% | 0.0% | pass | pass |
| review-project-canon | review/structured | 15358 | 5959 | 61.2% | 40% | 0.0% | pass | pass |
| review-scene-candidate | review/review | 25674 | 15377 | 40.1% | 40% | 0.0% | pass | pass |
| planning-story-architecture | planning/planning | 6992 | 3767 | 46.1% | 40% | 0.0% | pass | pass |

## Live Quality Gate

- current: `pending-current-live-ab`
- historical baseline: `docs/benchmarks/prompt-v3-final-ab-gate-2026-08-11.json`
- compile pass does not authorize broad Prompt v3 enforcement.

## Limitations

- No model was invoked; quality, preflight pass rate, latency, and provider token usage remain unproven.
- A live interleaved A/B gate is still required before Prompt v3 enforcement is enabled.
