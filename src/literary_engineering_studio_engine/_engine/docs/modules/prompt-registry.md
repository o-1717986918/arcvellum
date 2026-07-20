# Prompt Registry

Prompt Registry turns `prompt_asset_id` from a label into a file-backed execution asset.

The registry does not call an LLM and does not replace the platform Agent. It tells the platform Agent which prompt family, context groups, hard constraints, output contract, review requirements, and forbidden shortcuts apply to the current CLI-mediated task.

## Why It Exists

Before this module, task packages carried a `prompt_asset_id`, but the actual prompt guidance still lived across code, templates, and long documents. A fast host Agent could treat the id as decorative and continue from memory.

From `v0.85.0`, `task-open` resolves the id through `templates/prompt_assets/*.md` and injects the resolved Prompt Asset into the task Markdown.

## Files

Prompt assets live here:

```text
templates/prompt_assets/*.md
```

Each file uses simple frontmatter followed by Markdown body:

```markdown
---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.*.v1
match: route.scene-development.*.v1
version: v1
route: scene-development
task_type: formal-scene-development
required_inputs:
  - scene yaml
context_groups:
  - canon
hard_constraints:
  - Follow the CLI task current_state exactly.
output_contract:
  - Write only the artifact requested by the task package.
review_requirements:
  - Resolve pass_with_notes through revise-scene and re-review.
forbidden_shortcuts:
  - Do not use review bypass flags.
---

# Prompt Body

Platform Agent instructions go here.
```

The schema is:

```text
schemas/prompt_asset.v1.json
```

## Resolution

The registry supports exact and wildcard assets.

Current route-level assets use wildcard ids such as:

```text
route.scene-development.*.v1
route.export-release.*.v1
```

When `task-open` sees an exact task id such as `route.export-release.publish.v1`, it first looks for an exact asset. If none exists, it resolves the best wildcard match. This keeps all formal tasks covered while still allowing high-risk steps to gain more specific prompt assets later.

## CLI

List assets:

```powershell
python -m literary_engineering_workbench prompt-registry-list
```

Validate registry assets and every `prompt_asset_id` used by `task_registry.py`:

```powershell
python -m literary_engineering_workbench prompt-registry-validate
```

Preview the asset that will be used for a task id:

```powershell
python -m literary_engineering_workbench prompt-preview route.scene-development.prose.generate.v1
```

## Task-Open Contract

`task-open` now writes a `## Prompt Asset` section into the task package.

The section includes:

1. requested id
2. resolved id
3. match pattern
4. version
5. title
6. output contract
7. prompt body

If the asset cannot be resolved, the task package tells the Agent to run `prompt-registry-validate` before treating the route as complete.

## Extension Rule

Add exact assets when a state needs stronger guidance than the route-level default. For example:

```text
templates/prompt_assets/route.scene-development.prose.generate.v1.md
templates/prompt_assets/route.scene-development.agent-review.v1.md
templates/prompt_assets/route.style-engineering.prompt.execute.v1.md
```

Exact assets override wildcard route assets.
