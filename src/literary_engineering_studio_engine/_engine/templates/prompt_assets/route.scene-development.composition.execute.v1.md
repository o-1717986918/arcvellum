---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.composition.execute.v1
match: route.scene-development.composition.execute.v1
version: v1
route: scene-development
task_type: main-platform-agent-composition
title: Scene Composition Exact Prompt Asset
required_inputs:
  - formal branch selection
  - roleplay and context evidence
  - word budget and reader experience contracts
  - mounted style skill
context_groups:
  - canon
  - character causality
  - selected branch
  - narrative rhythm and bridge
  - style generation constraints
hard_constraints:
  - Convert the selected branch into scene beats without writing final prose.
  - Carry scene function target Han-character count rhythm turn narrative distance incoming pressure and outgoing hooks.
  - Reserve space for consequence and transition instead of summarizing all beats.
style_constraints:
  - Translate mounted style into generative choices before prose begins.
output_contract:
  - Write the composition packet and completion marker only at declared paths.
review_requirements:
  - Composition covers every hard contract and provides enough event inventory for the target length.
forbidden_shortcuts:
  - Do not draft prose early or omit rhythm bridge word budget and style because they are reviewed later.
---

# Scene Composition

Build an executable writing plan: beats, emphasis, compression, transition, viewpoint distance, paragraph texture, target length, and reader effect. The packet must be specific enough that prose quality does not depend on improvising missing structure.
