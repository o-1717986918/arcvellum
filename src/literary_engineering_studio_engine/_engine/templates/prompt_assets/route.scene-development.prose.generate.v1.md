---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.prose.generate.v1
match: route.scene-development.prose.generate.v1
version: v10
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
  - 下笔前必须把抽象文风软约束转译为本场的动力与代价、主导表现通道、叙述距离、段落/句法节奏、邻场差异和收束方式；直接按该策略生成，不等待审查阶段统一润色。
  - 已挂载参考语料时，从完整选段中选一篇最贴合本场功能的表达主参照，主动模仿其叙述距离、句群呼吸、细节进入顺序和对白或意象推进方式；不能只概括为抽象风格词。必要时辅以另一篇，仍用当前人物与情节写新正文，不搬运参考原句或专名。
  - 候选 manifest 必须把 canon_change 写为 true、false（同时给 no_canon_change_reason）或 unknown，供后续 canon-evolve 判定。
  - 中文正文统一使用全角标点、中文弯双引号“”、省略号“……”；不用 ASCII 标点或角引号，破折号原则上不用，孤例必须承担真实中断或插入功能。
  - 生硬对照一律禁用，包括“不是……而是……”“不再是……而是……”“没有再……而是……”“并非……而是……”“不是……——是……”“看似……其实……”及其标点或同义换皮；用动作、事实顺序、信息差或直接陈述完成转向。
  - 无关精确数字默认不用；先区分“一个又一个”等虚指反复与实际计数。当场问答、谈判、事实辨认、选择、因果、连续性或后文核验中的一项实际功能足以保留精度，不要求全部功能同时成立，既定事实数值必须准确。技术、灾难、悬疑、倒计时、scene 或 composition 的读数要求不自动豁免装饰性数字；普通陈设与日常动作不为显得具体而计件、计次或计秒。
  - 器官轮岗、万能占位、空泛比喻、景物强制同步和模板化身体反应合计按约 2% 叙事单元软上限控制；高潮靠准确细节，过场简写，不靠形容词堆叠撑字数。
  - 逗号较多时先检查句内层级，只有关系松散或重复才重组；不要按数量机械拆句。中等长度句承担主要叙述，短句只用于真实落点，也不要以金句、主题总结或工作流说明收尾。
style_constraints:
  - 像给朋友讲一件真实发生的事：叙述清楚、细节准确、人物因选择承担后果，不写满分作文腔。
  - 从 scene、character、reader experience、narrative rhythm 和 scene bridge 的既有字段选择本场写法，不新增风格 schema，不把所有场景写成核对、记录、隐瞒、离场或异常物件收尾的同一动作链。
  - 人物说话从已有身份、欲望、关系压力和知识边界中分化词域、句子形状、礼貌边界与回避方式；朴素不等于人人语气平直，不凭空制造方言或口头禅。
  - 正式正文不包含工作流笔记、AGENT_TASK、prompt 分析、Canon 说明或审查文本。
output_contract:
  - Write candidate Markdown, candidate manifest JSON, and completion marker only at paths in the task package.
review_requirements:
  - Candidate must pass exact-candidate AgentReview before promotion.
  - Route audit must show generation provenance, style lint, word budget, reader experience, rhythm/bridge, and new-character gates.
  - Style Lint 与 AgentReview 继续核验违禁表达、反规避变体和中文标点；它们不替代生成阶段对抽象文风软约束的落实。
forbidden_shortcuts:
  - Do not skip prompt manifest, context trace, composition, sidecar completion, or review gates.
---

# Exact Prose Generation Prompt Asset

完成当前场景的小说正文与候选 manifest。下笔前先在内部选择本场的场景动力、人物代价、主导材料、叙述距离、节奏差异和收束方式；若挂载了完整参考语料，选一篇对应选段作为表达主参照，把它的句法与叙述步幅真正带入本场初稿，而不是只引用分类名称。通过段落速度、场景功能、人物选择、信息释放和因果后果体现节奏与衔接；让背景故事只通过人物的选择、回避、误判和语气间接生效，并让人物在措辞和回避方式上可辨。交稿前逐项判断阿拉伯数字、中文数词、序数，以及时长、距离、尺寸、温度、百分比、型号、轮次和次数的语义：虚指反复不算精确计数；当场问答、辨认、选择或因果所需精度可留；无关精度则围绕动作、状态变化、可感范围或后果逐句重写，不做批量删除和机械模糊化。违禁表达、反规避与中文标点既要在生成阶段清理，也要接受后续审查；不要在正文解释合同、策略或工作流。
