---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.story-architecture.execute.v1
match: route.longform-planning.story-architecture.execute.v1
version: v1
route: longform-planning
task_type: main-platform-agent-story-architecture
title: Story Architecture Candidate Contract
required_inputs:
  - project.yaml
  - plot/outline.md
  - plot/story_architecture.candidate.json
context_groups:
  - premise and target scale
  - central dramatic question
  - character change and counterforce
  - volume obligations and non-negotiable payoffs
hard_constraints:
  - Build a causal longform spine before word-budget expansion.
  - Do not use word counts or decorative themes as substitutes for an endgame choice.
  - The main platform Agent writes the candidate; subagents may only prepare evidence.
output_contract:
  - Write only the declared story architecture candidate and completion evidence.
  - Candidate status must be complete and identify its writer session.
review_requirements:
  - Each volume must have an irreversible obligation linked to the ending state.
  - The change vector must connect the initial misbelief to a pressured final choice.
forbidden_shortcuts:
  - Do not fill required fields with generic placeholders.
  - Do not write formal outline or scenes in this candidate task.
---

# Story Architecture Candidate

Create the smallest truthful structure that proves this project can sustain a long work: a protagonist under counterforce, a meaningful transformation, a midpoint that cannot be undone, and an ending that requires a real choice. The next route stages may expand inventory, but they must not invent this spine after the fact.
