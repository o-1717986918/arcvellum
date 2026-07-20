---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.source-ingest.*.v1
match: route.source-ingest.*.v1
version: v1
route: source-ingest
task_type: formal-source-ingest
title: Source Ingest Route Prompt Asset
required_inputs:
  - source manifest
  - source chunks
  - extract_project_files.agent_tasks.md
context_groups:
  - source evidence
  - candidate project brief
  - extracted characters
  - extracted world rules
  - extracted outline and timeline
  - extracted style notes
hard_constraints:
  - Source-derived material is evidence, not canon.
  - Every extracted claim needs evidence refs, confidence, unknowns, and contradiction notes when applicable.
  - Keep all reverse-extracted files in candidate/review locations until approval.
output_contract:
  - Write the candidate files named by source_manifest.json.
  - Write a clean extraction review only after checking coverage and uncertainty.
review_requirements:
  - Review whether the extracted project files are useful for continuation, rewrite, or adaptation.
  - Mark contradictions and unknowns instead of inventing certainty.
forbidden_shortcuts:
  - Do not overwrite canon, characters, plot, style, drafts, exports, or releases directly from source text.
  - Do not summarize the source without writing standardized candidate project files.
---

# Source Ingest Route Prompt

You are reverse-engineering an existing text into a maintainable literary project. Extract reusable project state with evidence. Do not pretend uncertain claims are facts. The goal is a candidate project basis for continuation, rewrite, or adaptation, not an immediate rewrite.
