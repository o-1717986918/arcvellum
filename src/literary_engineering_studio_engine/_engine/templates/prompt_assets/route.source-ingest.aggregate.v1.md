---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.source-ingest.aggregate.v1
match: route.source-ingest.aggregate.v1
version: v1
route: source-ingest
task_type: deterministic-cli
title: Deterministic Archaeology Fan-In
required_inputs:
  - source manifest and evidence index
  - every declared chunk extraction and completion receipt
context_groups:
  - chunk completion set
  - namespaced observations
  - alias hypotheses
  - claim conflicts
  - temporal conflicts
hard_constraints:
  - Run the exact core command only after every chunk task has passed.
  - Preserve every occurrence and unresolved alternative during deterministic aggregation.
  - Treat lexical alias groups as hypotheses and never as confirmed identity merges.
style_constraints:
  - none
output_contract:
  - Core writes the declared aggregate JSON and verifies exact reproducibility.
review_requirements:
  - Fan-in is ready only when every declared chunk is present valid and evidence-bound.
forbidden_shortcuts:
  - Do not hand-edit the aggregate omit failed chunks or suppress contradictory alternatives.
---

# Project Archaeology Fan-In

Execute the deterministic aggregate command. This task has no creative judgment and must not be delegated to an Agent.
