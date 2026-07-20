# 数据模型

核心对象：

- WorkProject：作品项目根目录。
- CanonFact：事实、规则、适用范围、来源和确认状态。
- CharacterProfile：目标、信念、情绪、秘密、关系、语言习惯。
- Scene：场景目标、冲突、出场人物、输入事实、输出变化。
- Draft：草稿文本和上下文来源。
- SourceImport：已有文本的 raw、chunks、manifest、平台 Agent 反推任务和候选输出清单。
- WordBudget：目标中文内容字符、卷章场景预算、叙事负载、现有库存扫描、扩纲任务、机器字符诊断映射和预算审查状态。
- ChapterObligation：章节功能、承诺兑现、设置、变化、暂不解决项、章末钩子和库存充分性。
- ReaderExperience：逐场读者问题、承诺回报、暂扣信息、兑现/延迟、张力来源、反摘要要求和读后余味。
- CandidatePromotion：模型候选转入草稿审查通道的选择记录。
- ReviewReport：审查结论、问题、修订建议。
- CharacterStatePatch：待审批的人物状态演化候选。
- CharacterStateApply：审批后人物状态写回记录。
- WorkflowRun：节点事件、状态、产物、人工确认需求。
- Release：通过 canon、章节 ready、导出和审批门禁后的发布版本。

写回原则：新事实、源作品反推结论和预算化大纲扩展先进入候选区或审查报告，人工确认后才能成为 canon 或正式 plot。
