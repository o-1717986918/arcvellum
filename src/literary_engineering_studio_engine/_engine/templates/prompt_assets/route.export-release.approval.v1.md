---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.export-release.approval.v1
match: route.export-release.approval.v1
version: v1
route: export-and-release
task_type: human-approval-boundary
title: Export Approval Exact Prompt Asset
required_inputs:
  - export readiness report
  - clean manuscript preview
  - route and longform audits
  - release manifest
context_groups:
  - reader-facing manuscript
  - unresolved risks
  - output formats
  - publication metadata
hard_constraints:
  - Present an understandable release summary and unresolved risks before asking for approval.
  - Verify that workflow traces scene ids canon notes reviews and draft markers are absent from the manuscript.
  - The Agent cannot self-approve publication.
style_constraints:
  - Approval text is concise factual and separate from the literary work.
output_contract:
  - Record only the user's approve revise or reject decision with the matching release id.
review_requirements:
  - Approval references the exact candidate release and previewed artifacts.
forbidden_shortcuts:
  - Do not publish after silence inferred consent or an approval for another release id.
---

# Export Approval

Show the reader-facing result, format inventory, audits, and known limitations. Ask the user for a deliberate release decision; do not turn a technical gate into ceremonial confirmation.
