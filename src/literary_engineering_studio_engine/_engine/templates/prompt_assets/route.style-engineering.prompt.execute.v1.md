---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.style-engineering.prompt.execute.v1
match: route.style-engineering.prompt.execute.v1
version: v1
route: style-engineering
task_type: platform-agent-style-prompt
title: Style Prompt Execution Exact Prompt Asset
required_inputs:
  - author style project
  - source excerpts or extracted observations
  - style prompt quality rules
context_groups:
  - style corpus
  - style observations
  - generation constraints
hard_constraints:
  - Output an LLM-facing style prompt in Chinese-content character count range 500-2500.
  - The prompt must be specific enough to mount into scene generation, not only review.
  - Preserve canon/user constraints over style imitation.
style_constraints:
  - Describe mechanisms rather than copying distinctive source text.
output_contract:
  - Write style_prompt.md and evaluation artifacts requested by the task package.
review_requirements:
  - Style prompt must satisfy the 500-2500 Chinese-content character quality contract.
  - At least one accepted style evaluation is required before formal mount.
forbidden_shortcuts:
  - Do not output a vague style label such as "literary" or "serious" without executable constraints.
---

# Exact Style Prompt Execution Asset

Create a mountable style prompt that can drive generation before review. It should specify narrative distance, syntax, paragraph rhythm, imagery routing, psychology, dialogue, punctuation, anti-AI constraints, and conflict rules.
