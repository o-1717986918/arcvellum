---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.style-engineering.eval.fix.v1
match: route.style-engineering.eval.fix.v1
version: v1
route: style-engineering
task_type: platform-agent-revision
title: Style Prompt Evaluation Repair
required_inputs:
  - current style prompt and manifest
  - current evaluation candidate
  - deterministic score JSON and report
  - authorized corpus reference and neutral project direction
context_groups:
  - score dimensions
  - copy risk
  - prompt specificity
hard_constraints:
  - Revise the prompt and candidate according to concrete score evidence.
  - Keep the prompt within 500-2500 Chinese-content detail characters and retain every required block.
  - Change the candidate digest and leave score artifacts untouched so the state machine requires a fresh score.
  - Do not self-accept the revision.
style_constraints:
  - Improve mechanism fidelity without copying reference wording plot or named entities.
output_contract:
  - Write the revised style_prompt.md style_prompt.agent.json candidate manifest and completion evidence.
review_requirements:
  - A fresh deterministic style-eval must decide readiness.
forbidden_shortcuts:
  - Do not edit score JSON or lower thresholds.
  - Do not replace specific prompt rules with vague aesthetic labels.
---

# Style Prompt Evaluation Repair

Use the failed score as diagnostic evidence, revise the prompt and generated candidate, and return to deterministic scoring.
