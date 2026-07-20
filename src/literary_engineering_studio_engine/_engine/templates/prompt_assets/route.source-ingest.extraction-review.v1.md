---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.source-ingest.extraction-review.v1
match: route.source-ingest.extraction-review.v1
version: v1
route: source-ingest
task_type: platform-agent-extraction-review
title: Source Extraction Review Exact Prompt Asset
required_inputs:
  - source manifest and segments
  - extracted candidate files
  - provenance report
context_groups:
  - source evidence
  - extraction candidates
  - contradictions and uncertainty
hard_constraints:
  - Check claims against the exact source evidence and reject unsupported certainty.
  - Check chronology identity relationship and world-rule consistency across files.
  - Flag copied source prose that is unnecessary for factual extraction.
style_constraints:
  - Review style abstraction without rewarding phrase imitation.
output_contract:
  - Write extraction review JSON Markdown and completion marker at declared paths.
review_requirements:
  - A pass has no unsupported major fact unresolved contradiction or missing provenance.
forbidden_shortcuts:
  - Do not review summaries instead of the extracted files and source segments.
---

# Source Extraction Review

Act as a skeptical continuity editor. Test the extracted project against source evidence and keep unknowns unknown.
