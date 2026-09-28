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

Create a truthful longform architecture that the characters can inhabit. Identify what the protagonist believes, desires, fears losing, and cannot yet understand; show how the counterforce makes those commitments costly. Keep the required transformation, irreversible midpoint and final choice, but explain their effect on the reader's changing interpretation as well as on events.

Give the work room for ordinary life, recurring relationships, humor, silence, and motifs that change meaning when they return. A quiet chapter can deepen attachment or make an earlier fact newly legible; it still needs a place in the larger design. Mark the knowledge the reader may hold before the characters, the false inference that could fairly arise from available clues, and the question deliberately left open. Do not turn these possibilities into an obligatory twist schedule. Later inventory stages may expand the architecture without inventing its causal spine after the fact.
