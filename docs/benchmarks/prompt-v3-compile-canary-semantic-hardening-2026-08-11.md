# ArcVellum Prompt v3 Compile Canary

- revision: `2ff7cb579380f2568c29`
- status: `pass`
- mode: compile-only; no model was invoked.

| case | class/runtime kind | v2 chars | v3 chars | reduction | gate | duplicate | lint | status |
|---|---|---:|---:|---:|---:|---:|---|---|
| structured-world-foundation | structured/creative | 16553 | 9087 | 45.1% | 30% | 0.0% | pass | pass |
| review-scene-candidate | review/review | 23407 | 13999 | 40.2% | 40% | 0.0% | pass | pass |

## Limitations

- No model was invoked; quality, preflight pass rate, latency, and provider token usage remain unproven.
- A live interleaved A/B gate is still required before Prompt v3 enforcement is enabled.
