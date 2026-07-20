---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.roleplay.execute.v1
match: route.scene-development.roleplay.execute.v1
version: v1
route: scene-development
task_type: platform-agent-roleplay
title: Roleplay Simulation Exact Prompt Asset
required_inputs:
  - roleplay task sidecar
  - scene yaml
  - context packet and context trace
  - canon and relevant character files
context_groups:
  - canon
  - scene participants
  - hidden background stories
  - current character state
hard_constraints:
  - Simulate each character from belief desire intention fear secret moral line and background causality.
  - Do not choose actions merely because they make the intended plot convenient.
  - Separate character proposals world consequences branch candidates director scoring and canon audit.
  - Background stories affect choice avoidance misjudgment and voice without becoming direct exposition.
style_constraints:
  - Keep simulation analysis outside reader-facing prose.
output_contract:
  - Complete only the roleplay simulation and its completion marker at task-package paths.
review_requirements:
  - Every participating character has a causal proposal and a rejected convenient alternative.
  - Canon conflicts and next-scene costs are explicit.
forbidden_shortcuts:
  - Do not replace roleplay with a plot summary or a single predetermined branch.
---

# Roleplay Simulation

Treat characters as constrained decision makers. Generate competing actions first, then infer world consequences. Preserve disagreement and inconvenient choices when they follow character logic. Mark uncertainty instead of inventing missing canon.
