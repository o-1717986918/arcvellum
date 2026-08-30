# ArcVellum 默认文风系统审计

## 结论

当前文风系统的正式主链已经完整：语料导入、训练/留出集隔离、风格档案、LLM 提示词、确定性评测、独立语义审查、不可变版本、内容哈希、挂载预览、项目级最高优先级挂载、生成快照、修订复核与 AgentReview 门禁均已存在。

本轮发现的主要缺口不在门禁，而在默认体验：新项目只有空白 `style/style-profile.md`，没有通过正式挂载器激活的可用基础文风。因此，正文可能在用户完成文风学习前以模型默认语气起步。

## 已实现的修正

- 新增内置文风预设 `clear-plain-zh`，显示名为“清简叙事”。
- 预设不模仿特定作者，训练样例、留出样例、评测候选和提示词均为项目原创。
- 提示词正文按现有计算规则为 2405 个中文内容字符，处于 500 至 2500 的正式范围内，并覆盖全部 11 个结构门禁。
- 提示词采用稳定身份与优先级前缀、正向风格机制、场景类型适配和三遍静默复核；对应机器配置记录在预设的 `prompt_contract` 中。
- Studio 新建项目时先生成正式不可变文风版本，再调用现有 `mount_style_profile_version()` 挂载。
- 不修改、不放宽任何文风版本、完整性、生成、修订或审查门禁。
- 现有项目和已有 active style 不被自动替换。
- 精确版本、内容哈希和挂载路径记录在 `style/default_style.json` 与 `style/active_style_skill.json`。

## 文学理论转译

默认文风不是“少用形容词”这一条粗糙规则，而是以下生成机制：

1. 具体主语和准确动词承担叙述骨架，抽象解释退居次要位置。
2. 细节必须改变读者对人物、空间、关系或风险的理解，否则删去。
3. 句长变化服务意义、视角与强调，避免连续碎句和连续等重长句。
4. 叙述距离随场景功能伸缩，心理优先通过选择、误判、回避和代价显露。
5. 过场压缩，关键选择、冲突转向和余波展开。
6. 标点先表达语义停顿和结构关系，再承担节奏，不以标点频率冒充文风。
7. 文学性来自准确、节奏和余味，不来自器官轮岗、万能占位、装饰性比喻或机械对照。

依据包括：

- 国家标准 `GB/T 15834-2011`，把标点定义为表示停顿、语气和成分性质的书面语组成部分，并规定现代汉语标点形式与用法。
- Purdue OWL 关于句式变化的材料，强调短句、复句和复杂句应按表达目的组织，连续同构会造成碎裂或拖沓。
- Purdue OWL 的清晰写作原则，强调具体主语、准确动作动词、尽快到达主干动词以及控制句子蔓延。
- UW-Madison Writing Center 的清晰简洁写作材料，强调把动作放在动词中、减少含混名词和不必要膨胀。
- Ursula K. Le Guin 关于叙事技艺的讨论，强调语言的声音、停顿、句法骨架和随内容与视角变化的句子节奏。

## 提示词工程转译

默认文风遵循“详细但不重复”的产品契约，而不是把所有全局门禁再次抄入风格文件：

1. 关键身份、优先级、成功标准和输出边界放在稳定前缀中，场景动态资料由正式链路另行注入。
2. 优先正向描述可执行的写法，再用少量禁区约束已测得的高频退化模式。
3. 把“优美”“朴素”“有余味”等模糊形容词拆成主语、动词、细节功能、叙述距离、句法节奏和信息释放等可判断机制。
4. 用过场、冲突、关系、揭示、余波五类适配规则允许模型随任务变调，避免固定腔调覆盖所有场景。
5. 将检查拆成事实因果、叙事节奏、语言惯性三遍，先保护语义，再处理风格，防止同义词替换式伪修订。
6. 每项规则只在一个权威位置出现；Style Lint、项目 canon、人物状态和字数门禁继续由各自模块负责。

提示词结构参考了 OpenAI 关于精简重复指令、明确目标与成功条件的模型指导，Google Gemini 关于清晰具体、结构一致、正向样例和复杂任务拆分的提示设计建议，以及 Anthropic 关于清晰直接指令和结构化分区的实践。文学风格不能靠通用提示词范式自动获得，因此这些范式只负责提高约束可执行性，具体审美仍由文学机制、留出评测和语义审查承担。

参考资料：

- [GB/T 15834-2011 标点符号用法](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=22EA6D162E4110E752259661E1A0D0A8&refer=outter)
- [Purdue OWL: Sentence Structure and Variety](https://owl.purdue.edu/owl/graduate_writing/introduction_to_writing/documents/revising-and-editing/sentence-structure-activity.pdf)
- [UW-Madison Writing Center: Writing Style](https://writing.wisc.edu/handbook/style/)
- [Ursula K. Le Guin on Steering the Craft](https://www.vogue.com/article/ursula-le-guin-steering-the-craft)
- [OpenAI: Model guidance and prompting best practices](https://developers.openai.com/api/docs/guides/latest-model)
- [Google Gemini API: Prompt design strategies](https://ai.google.dev/gemini-api/docs/prompting-strategies)
- [Anthropic: Prompting best practices](https://platform.claude.com/docs/zh-CN/build-with-claude/prompt-engineering/claude-prompting-best-practices)

## 仍需承认的边界

- 默认文风是通用基础层，不替代题材化、作者化或项目专属文风。
- 当前确定性评测可以验证提示词结构、摘要绑定、复制风险和基本质量，但文学审美仍必须由独立 AgentReview 与用户选择共同承担。
- 文风融合仍以单一正式版本为主；复杂多风格分层若要开放，应先设计冲突优先级和场景级适用范围，不能直接拼接提示词。
- 既有项目不应被静默改写。若需要“恢复默认文风”，应由文风工作台明确发起正式版本挂载。

## 验收条件

- 新项目存在 `style/active_style_skill.json`。
- active style 的完整性状态为 `pass`。
- `scope=project`，`priority=highest`。
- director、composition、generation、revision、review 全部为 `required`。
- 生成上下文读取 mounted version 的 `prompt.md`，而非空白模板。
- 用户挂载其他正式文风后，默认文风不再拥有活动优先级。
