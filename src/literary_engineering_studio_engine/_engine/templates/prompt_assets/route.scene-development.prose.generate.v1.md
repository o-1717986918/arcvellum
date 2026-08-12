---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.prose.generate.v1
match: route.scene-development.prose.generate.v1
version: v5
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
  - 把当前场景的文风、汉字预算、读者体验、叙事节奏、场景桥接、叙事距离、标点、反规避和新角色登记合同落实到正文与 manifest。
  - 候选 manifest 必须把 canon_change 写为 true、false（同时给 no_canon_change_reason）或 unknown，供后续 canon-evolve 判定。
  - 中文正文统一使用全角标点、中文弯双引号“”、省略号“……”；不用 ASCII 标点或角引号，破折号原则上不用，孤例必须承担真实中断或插入功能。
  - 生硬对照一律禁用，包括“不是……而是……”“并非……而是……”“不是……——是……”“看似……其实……”及其标点或同义换皮；用动作、事实顺序、信息差或直接陈述完成转向。
  - 器官轮岗、万能占位、空泛比喻、景物强制同步和模板化身体反应合计按约 2% 叙事单元软上限控制；高潮靠准确细节，过场简写，不靠形容词堆叠撑字数。
  - 一句话超过三个逗号通常应拆句或重写；不要把连续动作切成均匀短句，也不要以金句、主题总结或工作流说明收尾。
style_constraints:
  - 像给朋友讲一件真实发生的事：叙述清楚、细节准确、人物因选择承担后果，不写满分作文腔。
  - 正式正文不包含工作流笔记、AGENT_TASK、prompt 分析、Canon 说明或审查文本。
output_contract:
  - Write candidate Markdown, candidate manifest JSON, and completion marker only at paths in the task package.
review_requirements:
  - Candidate must pass exact-candidate AgentReview before promotion.
  - Route audit must show generation provenance, style lint, word budget, reader experience, rhythm/bridge, and new-character gates.
forbidden_shortcuts:
  - Do not skip prompt manifest, context trace, composition, sidecar completion, or review gates.
---

# Exact Prose Generation Prompt Asset

完成当前场景的小说正文与候选 manifest。通过段落速度、场景功能、人物选择、信息释放和因果后果体现节奏与衔接；让背景故事只通过人物的选择、回避、误判和语气间接生效，不在正文解释合同或工作流。
