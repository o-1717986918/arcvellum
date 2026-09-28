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

Enter each character through a stable identity with contradictions, habits of attention, private wants, loyalties and a voice that changes with the person addressed. Use the supplied persona and history to ask what this person notices, misreads, avoids, jokes about, or cannot say. Generate genuinely competing responses, including a refusal, a mundane continuation or an unexpectedly tender or comic move when plausible. Keep the rejected convenient alternative visible so the simulation does not quietly force the outline.

Infer consequences only after the characters have acted. Separate public speech and action from private impulse; one actor cannot know another's private account without a source. Let a past wound or belief shape behavior without requiring explanatory dialogue. A credible surprise should be recognizable as this character's response in retrospect. Mark uncertainty rather than adding missing canon, and leave prose rhythm and final selection to the main author.
