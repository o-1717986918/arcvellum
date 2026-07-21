---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.style-engineering.eval.execute.v1
match: route.style-engineering.eval.execute.v1
version: v1
route: style-engineering
task_type: platform-agent-evaluation
title: Formal Style Evaluation Candidate
required_inputs:
  - style prompt and style metrics
  - authorized corpus reference
  - neutral project direction input
  - evaluation sidecar
context_groups:
  - style prompt effectiveness
  - originality boundary
hard_constraints:
  - Generate from the neutral input under style_prompt.md; do not transform or copy the reference text.
  - Write only the declared candidate manifest and completion outputs.
  - The manifest must record mode style_prompt reference input candidate source_paths and generation boundary.
  - Do not assign a score or accepted verdict; deterministic style-eval owns the measurement.
style_constraints:
  - Reproduce high-level mechanisms while avoiding phrase-level copying and plot borrowing.
output_contract:
  - Write platform_agent_candidate.md platform_agent_candidate.prompt.json and completion evidence.
review_requirements:
  - The next deterministic task must score the exact candidate digest.
forbidden_shortcuts:
  - Do not quote the reference to inflate similarity.
  - Do not fabricate deterministic scores.
---

# Formal Style Evaluation Candidate

Execute the sidecar as a blind style-prompt effectiveness test. The candidate is evidence, not an accepted style result.
