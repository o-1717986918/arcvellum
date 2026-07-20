---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.style-engineering.*.v1
match: route.style-engineering.*.v1
version: v1
route: style-engineering
task_type: formal-style-engineering
title: Style Engineering Route Prompt Asset
required_inputs:
  - style profile
  - style metrics
  - style prompt sidecar
  - evaluation reports when present
context_groups:
  - narrative distance
  - syntax rhythm
  - punctuation
  - imagery and sensory routing
  - psychology and behavior
  - dialogue tone
hard_constraints:
  - The final style_prompt.md is for an LLM to use during generation, not a literary essay.
  - The prompt must be detailed but executable, 500-2500 Chinese-content characters after stripping Markdown scaffolding.
  - Exact imitation is allowed only for public-domain or authorized corpora; otherwise abstract higher-level craft.
output_contract:
  - Write style_prompt.md and style_prompt.agent.json when requested.
  - Include identity, priority, mechanism, syntax, punctuation, imagery, psychology, dialogue, forbidden tendencies, and self-check blocks.
review_requirements:
  - Require at least one accepted evaluation before formal mount.
  - Reject high copy risk and low similarity.
forbidden_shortcuts:
  - Do not mount a short, vague, unreviewed, or unevaluated style prompt.
  - Do not let style override canon, character facts, or explicit user constraints.
---

# Style Engineering Route Prompt

You are turning style evidence into a reusable writing constraint. Produce a prompt that changes generation behavior before the draft exists. Prefer concrete rules, priority order, and self-checks over praise of the style. Make the result mountable and auditable.
