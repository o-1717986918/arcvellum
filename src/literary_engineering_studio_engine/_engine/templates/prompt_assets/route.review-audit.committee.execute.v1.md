---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.review-audit.committee.execute.v1
match: route.review-audit.committee.execute.v1
version: v1
route: review-and-audit
task_type: platform-agent-review-committee
title: Review Committee Exact Prompt Asset
required_inputs:
  - committee task sidecar
  - exact review targets
  - route audit canon style budget and reader evidence
context_groups:
  - continuity
  - character causality
  - prose and style
  - longform structure
  - reader experience
hard_constraints:
  - Evaluate independent lenses before synthesizing a verdict.
  - Cite exact artifacts and distinguish deterministic failures from semantic judgment.
  - Deterministic attention is evidence to consider, not an automatic defect or repair action.
  - Optional polish belongs in reviewer or minority notes; action_items contain only concrete defects that must change before export.
  - An action verification must prove a changed observable; never require that an already passing or ok status merely stays passing or ok.
  - A disagreement that the committee resolves must be explained in reviewer findings and omitted from disagreements.
  - If only non-blocking polish remains, use approve with empty action_items and disagreements; approve_with_notes creates required revision work and never behaves as pass.
  - A non-approve recommendation is a valid completed review; every repair action item or disagreement must include exact target_path action and verification.
style_constraints:
  - Be adversarial toward flattering generic feedback and unsupported praise.
output_contract:
  - Write committee JSON report Markdown and completion marker at declared paths.
  - JSON must contain schema subject final_recommendation reviewers disagreements action_items source_paths and minority_opinions; all collection fields are arrays even when empty.
  - Do not replace final_recommendation and action_items with generic verdict and findings fields.
  - reviews/ and workflow/ are read-only evidence domains, never repair targets.
review_requirements:
  - Verdict accounts for all blocking lenses and exact-source provenance.
  - A required repair target_path must name an existing text file under canon/ characters/ plot/ scenes/ or drafts/candidates/ rather than a review or workflow artifact.
forbidden_shortcuts:
  - Do not average away a blocking Canon review style lint or route gate failure.
---

# Review Committee

Run each editorial lens independently, expose disagreement, then synthesize. A minority blocking finding remains visible until explicitly resolved.

Classify before writing the verdict: a required repair changes a concrete project artifact and has a before/after verification. An advisory
attention item, preference, possible future enhancement, or already-resolved disagreement is not a required repair. Keep optional polish in
reviewer findings or minority opinions. When no required repair or unresolved disagreement remains, return `approve` with both arrays empty.

Use this exact top-level JSON shape:

```json
{
  "schema": "literary-engineering-workbench/committee-review-agent/v1",
  "subject": "project-final-audit",
  "final_recommendation": "approve",
  "reviewers": [],
  "disagreements": [],
  "action_items": [],
  "source_paths": [],
  "minority_opinions": []
}
```

Use `approve_with_notes`, `revise`, or `reject` only when a concrete defect must change before export. In that case each action item must use
`{"target_path": "<existing project artifact>", "action": "<exact repair>", "verification": "<observable before/after proof>"}` and the target
must be an existing text file under `canon/`, `characters/`, `plot/`, `scenes/`, or `drafts/candidates/`. Never target `reviews/` or `workflow/`.
