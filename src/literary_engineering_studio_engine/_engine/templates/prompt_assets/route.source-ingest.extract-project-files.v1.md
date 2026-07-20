---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.source-ingest.extract-project-files.v1
match: route.source-ingest.extract-project-files.v1
version: v1
route: source-ingest
task_type: main-platform-agent-source-extraction
title: Source Work Extraction Exact Prompt Asset
required_inputs:
  - imported source manifest
  - source text segments
  - project schemas
context_groups:
  - explicit facts
  - inferred facts
  - chronology
  - characters and relationships
  - world and locations
hard_constraints:
  - Separate quoted or explicit facts from inference uncertainty and contradiction.
  - Preserve source provenance at artifact and segment level.
  - Generate candidates only; do not write confirmed Canon or overwrite project assets.
style_constraints:
  - Extracted style observations remain descriptive and do not copy source phrasing into new prose.
output_contract:
  - Write standardized candidate project files and provenance report at declared paths.
review_requirements:
  - Every important claim has evidence or an explicit inference label.
forbidden_shortcuts:
  - Do not fill gaps with plausible invention or flatten contradictory narrators into one truth.
---

# Source Work Extraction

Reverse-engineer a maintainable project from the supplied work. Treat ambiguity as data. Preserve conflicting accounts, temporal uncertainty, implicit relationships, and the difference between what the text states and what an editor infers.
