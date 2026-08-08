---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.branch.selection.v1
match: route.scene-development.branch.selection.v1
version: v1
route: scene-development
task_type: main-platform-agent-decision
title: Branch Selection Exact Prompt Asset
required_inputs:
  - completed branch manifest
  - validated Agent branch proposals when declared by the manifest
  - roleplay simulation
  - scene and longform obligations
context_groups:
  - branch scores
  - canon
  - character arcs
  - reader promises
hard_constraints:
  - Select by causal strength and longform value rather than convenience or novelty alone.
  - Record rejected branches and any elements deliberately retained.
  - Human-gated decisions remain human-gated and cannot be self-approved.
style_constraints:
  - Decision rationale stays outside prose.
output_contract:
  - Write a formal branch selection with rationale retained elements and risks.
  - Put `decision: selected` and `selected_branch: <exact validated branch_id>` on separate plain-text lines; headings, tables, bold prose, and translated labels do not satisfy the CLI handoff.
review_requirements:
  - The selected branch exists in the manifest and preserves canon and character causality.
forbidden_shortcuts:
  - Do not infer selection from filenames scores alone or the intended outline ending.
---

# Branch Selection

Choose the branch that makes later writing more causally inevitable while keeping meaningful future pressure. Explain why apparently easier alternatives were rejected.

Start the file with this machine-readable handoff, replacing the placeholder with an exact `branch_id` from validated `branch_proposals.json`, or from `branch_manifest.json` only when the fallback is deliberately required:

```text
decision: selected
selected_branch: <exact branch_id>
```

Then provide the human-readable rationale, retained elements, rejected alternatives, risks, and next-scene pressure. Do not replace the two handoff lines with Markdown emphasis, a table cell, or natural-language wording.
