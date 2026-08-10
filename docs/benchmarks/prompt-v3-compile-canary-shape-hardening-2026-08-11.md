# ArcVellum Prompt v3 Compile Canary

- revision: `1d180885897866f7c260`
- status: `pass`
- mode: compile-only; no model was invoked.

| case | class/runtime kind | v2 chars | v3 chars | reduction | gate | duplicate | lint | status |
|---|---|---:|---:|---:|---:|---:|---|---|
| structured-world-foundation | structured/creative | 16553 | 8987 | 45.7% | 30% | 0.0% | pass | pass |
| review-scene-candidate | review/review | 23883 | 14317 | 40.1% | 40% | 0.0% | pass | pass |

## Limitations

- No model was invoked; quality, preflight pass rate, latency, and provider token usage remain unproven.
- A live interleaved A/B gate is still required before Prompt v3 enforcement is enabled.
