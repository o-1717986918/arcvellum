---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.prose.generate.v1
match: route.scene-development.prose.generate.v1
version: v1
route: scene-development
task_type: main-platform-agent-prose
title: Scene Prose Generation Exact Prompt Asset
required_inputs:
  - task package from task-open
  - scene yaml
  - context packet and context trace
  - composition packet
  - prompt manifest
  - mounted style skill or style profile when present
  - word budget contract
  - reader experience contract
  - narrative rhythm and scene bridge contract
context_groups:
  - canon
  - scene participants
  - hidden background stories
  - selected branch
  - mounted style skill
  - word budget
  - reader experience
  - narrative rhythm
hard_constraints:
  - Run generate-scene first; do not handwrite a formal candidate outside the CLI task package.
  - The main platform Agent must write body prose personally; subagents may only gather/check bounded evidence.
  - Apply mounted style, word budget, reader experience, narrative rhythm, scene bridge, scene function, reader question/promise-payoff, narrative distance, punctuation standard, anti-evasion, and new-character registration before drafting.
  - Candidate manifest must declare canon_change as true, false with no_canon_change_reason, or unknown for later canon-evolve.
style_constraints:
  - Do not use mechanical contrast frames or their punctuation variants.
  - Formal prose must not include workflow notes, AGENT_TASK markers, prompt analysis, canon notes, or review text.
output_contract:
  - Write candidate Markdown, candidate manifest JSON, and completion marker only at paths in the task package.
review_requirements:
  - Candidate must pass exact-candidate AgentReview before promotion.
  - Route audit must show generation provenance, style lint, word budget, reader experience, rhythm/bridge, and new-character gates.
forbidden_shortcuts:
  - Do not skip prompt manifest, context trace, composition, sidecar completion, or review gates.
---

# Exact Prose Generation Prompt Asset

Treat the CLI task package as the execution program. Write the scene body only after all required sources are read. Make rhythm and bridge visible through pacing, scene function, scene turn, reader effect, entrance pressure, outgoing hooks, narrative distance, and texture variety, not through workflow explanation.
