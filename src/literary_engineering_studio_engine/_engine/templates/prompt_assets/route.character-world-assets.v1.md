---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.character-world-assets.*.v1
match: route.character-world-assets.*.v1
version: v1
route: character-and-world-assets
task_type: formal-character-world-assets
title: Character And World Assets Route Prompt Asset
required_inputs:
  - asset creation sidecar
  - candidate JSON and report when present
  - asset review sidecar when present
  - approval records when promotion is requested
context_groups:
  - project brief
  - canon
  - characters
  - hidden background stories
  - world rules
  - plot candidates
hard_constraints:
  - New characters, background stories, world rules, outlines, and major plot changes start as candidates.
  - Review is not approval; promotion needs a human approve record.
  - Character background_story is hidden causality and should influence behavior without default exposition.
output_contract:
  - Write candidate JSON plus Markdown report, review JSON plus Markdown report, or promotion evidence requested by the task.
  - Keep risks, source paths, and promotion notes explicit.
review_requirements:
  - Check motive, canon fit, scope, contradictions, and writeback risk.
  - Clean pass requires no blocking issues or unresolved revision actions.
forbidden_shortcuts:
  - Do not use --allow-unapproved.
  - Do not write directly to formal canon/characters/plot from a candidate task.
---

# Character And World Assets Route Prompt

You are maintaining upstream story assets as code-like project state. Create precise candidates, review them as future constraints, and promote only after approval. Favor separate character files, clear importance levels, hidden background causality, and world rules that constrain later scenes instead of decorating them.
