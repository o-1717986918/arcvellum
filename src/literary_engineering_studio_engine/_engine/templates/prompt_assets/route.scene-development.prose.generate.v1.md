---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.prose.generate.v1
match: route.scene-development.prose.generate.v1
version: v15
route: scene-development
task_type: main-platform-agent-prose
title: Scene Prose Generation Exact Prompt Asset
required_inputs:
  - task package from task-open
  - scene yaml
  - context packet and context trace
  - composition packet
  - prompt manifest
  - mounted style skill or style profile when present
  - word budget contract
  - reader experience contract
  - narrative rhythm and scene bridge contract
context_groups:
  - canon
  - scene participants
  - hidden background stories
  - selected branch
  - mounted style skill
  - word budget
  - reader experience
  - narrative rhythm
hard_constraints:
  - Canon、用户方向、人物事实和本场 scene turn 优先。
  - 执行已选择的 composition 分支、人物声音、expression plan、读者体验、节奏与字数合同。旧 prose_seed 仅为历史证据。
  - 项目禁用表达、机械对照及换皮、中文标点与新角色登记按现有合同审查。
  - 候选 manifest 必须把 canon_change 写为 true、false（附 no_canon_change_reason）或 unknown，供后续 canon-evolve 判定。
style_constraints:
  - 从本场选中的完整参考迁移叙述距离、句法运动、信息顺序或对白回弹。
  - 人物稳定词域与当下关系共同决定言语行动；修辞和感官从当前因果、世界材料与视角经验中生长。
  - 让语言随场景压力变调；动作、对白或物证已经传意后停在后果。
output_contract:
  - Write candidate Markdown, candidate manifest JSON, and completion marker only at paths in the task package.
review_requirements:
  - Candidate must pass exact-candidate AgentReview before promotion.
  - Route audit must show generation provenance, style lint, word budget, reader experience, rhythm/bridge, and new-character gates.
  - Style Lint 与 AgentReview 继续核验违禁表达、机械对照和中文标点；有证据的文学损害才要求语义返修。
forbidden_shortcuts:
  - Do not skip prompt manifest, context trace, composition, sidecar completion, or review gates.
---

# Scene Prose Generation

完成当前场景小说正文与候选 manifest。先读任务包中的事实、人物、上一场后果、composition、表达计划和本场选段。文风样本提供表达机制。句法、叙述距离、对白与意象要随本场行动、信息差和关系压力变化；白描与局部强度均可使用。

正文的情节选择和语义变化须可追溯。提交前复核 Canon、数字语义、项目禁用表达、中文标点与新角色登记；只写任务包规定的产物。
