---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.source-ingest.resolve-identities.v1
match: route.source-ingest.resolve-identities.v1
version: v1
route: source-ingest
task_type: platform-agent-archaeology-resolution
title: Whole-Work Identity and Conflict Resolution
required_inputs:
  - current source manifest and evidence index
  - ready deterministic archaeology aggregate
context_groups:
  - entity occurrences
  - lexical alias hypotheses
  - claim and timeline conflicts
hard_constraints:
  - Account for every entity occurrence and aggregate conflict exactly once.
  - Merge identities only when bounded source evidence supports the merge.
  - Preserve unresolved partial and same-name-distinct alternatives.
  - Do not create Canon or Archive candidates.
style_constraints:
  - Use concise rationales and evidence ids rather than source quotation.
output_contract:
  - Write the declared identity resolution JSON and human-readable report.
review_requirements:
  - Every judgment includes evidence_refs confidence rationale and unknowns.
forbidden_shortcuts:
  - Do not use majority wording lexical similarity or narrative convenience as proof of identity.
---

# Project Archaeology Identity Resolution

Resolve only what the whole-work evidence supports. An honest unresolved result is preferable to a convenient false merge.
