---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.scene-inventory.execute.v1
match: route.longform-planning.scene-inventory.execute.v1
version: v3
route: longform-planning
task_type: main-platform-agent-scene-inventory
title: Scene Inventory Expansion Exact Prompt Asset
required_inputs:
  - approved outline
  - budget review
  - canon and character arcs
context_groups:
  - volume obligations
  - chapter obligations
  - reader questions and promises
  - tension curve
hard_constraints:
  - Add causally necessary scenes until inventory supports the approved scale.
  - Treat totals.scene_count totals.target_chinese_chars and every chapter_budgets scene_count and target_words value as exact; user-specified target_scenes cannot change without an explicit replan.
  - Repair an existing inventory by replacing invalid rows and deleting duplicate or surplus rows never by appending a second corrected table.
  - Give each scene a function target Han-character count rhythm role bridge and obligation.
  - Balance setup escalation payoff aftermath and transition scenes.
  - Write the inventory as the exact chapter-heading plus 11-column scene table contract required for deterministic materialization.
  - The participants column contains only durable human or character roles that should own formal character assets.
  - Every participants item is a bare stable identity label or role token. Never append parentheses, action notes, reveal timing, aliases, or descriptive clauses to an identity.
  - Never put a location vehicle signal object organization camera subject or unnamed crowd in participants.
style_constraints:
  - Scene summaries must describe events and choices not prose decoration.
output_contract:
  - Write budgeted scene inventory artifacts only at declared paths.
review_requirements:
  - Inventory totals reconcile and no scene exists only to fill length.
forbidden_shortcuts:
  - Do not multiply near-duplicate conversations or split one beat cosmetically.
---

# Scene Inventory Expansion

Expand the story's causal surface, not its sentence count. Every added scene must change knowledge, choice, relationship, risk, obligation, or payoff timing.

## Required Machine-Readable Inventory Shape

Write `plot/candidates/scenes/word_budget_scene_inventory.md` in this exact repeated shape. Do not replace it with per-scene cards, bullet lists, or prose explanations.

```md
### Ch 0001 — Chapter title |

| scene_id | name | target_chars | function | participants | conflict | information_release | consequence | setup_payoff_role | rhythm_role | obligation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SC-001 | Scene title | 1400 | mainline_action | Person A、Person B | concrete conflict | released fact | concrete consequence | setup or payoff | escalation | reader-facing obligation |
```

Use one unique `SC-###` row for every planned scene. `target_chars` must be a positive integer. The 11 data columns are mandatory, and the total row count must reconcile with `word_budget.json`.

Before finishing the candidate, reconcile the total row count, contiguous `SC-001..SC-N` sequence, each chapter's row count, each chapter's `target_chars` sum, and the whole-book sum with `word_budget.json`. Do not write a verdict; a separate Reviewer will parse and judge the finished candidate.

`participants` is a character contract, not a list of every noun present in the scene. Use `主角` for the foundational protagonist until a canonical name is fixed. List another participant only when the story intends that person or durable character role to receive a reusable formal character asset before roleplay and prose. Each item must be a bare identity such as `幸存者` or `调度员`; `幸存者（以信号点名身份现身）` is invalid because the parenthetical belongs in information release. Put stations, ships, signals, interfaces, organizations, objects, anonymous crowds, scenery, actions, aliases, and reveal notes into the conflict, information-release, consequence, or setting wording instead.
