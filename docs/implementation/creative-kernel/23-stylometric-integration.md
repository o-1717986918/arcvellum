# 计量文风接入与运行修复

2026-10-05。用户授权实施。保留既有未提交规划改动；去 AI 味保持独立、默认关闭的实验。

## Module Change Packet：自然交付与恢复

- objective: 主创委托来自自然原文，交付失败可恢复，新增回归进入标准测试。
- primary_module: Studio runtimes。
- public_entry: PiSceneTransactionRuntime / NaturalOutputProcessor。
- variation_point: 逐字来源校验与自然回答尝试记录。
- inputs: 冻结资料、自然回答、已有候选。
- outputs: 已校验 DTO、原文与失败记录。
- invariants: 文学正文主创独写、实际必用调用、旧交易、档案冻结、Gate 与正式写回。
- allowed_dependencies: Engine public、现有 gateway、Studio 文件缓存。
- forbidden_dependencies: 新模型客户端、修改 Canon、伪造素材或 Gate。
- tests: 委托／文风改写拒绝、有效来源、失败后新回答、角色中断恢复、标准收集。
- rollback_unit: runtime 修复独立提交；测试收集单独提交。
- documentation: 本文件。

## 实施记录

自然委托／文风逐字校验及来源范围完成；失败原文与原因保留，最多两次即时修正，外部重试使用新反馈继续；有效素材和角色卡保持复用。角色恢复测试已迁移到自然交付，移除没有真实来源的 DIRECTOR_ONLY 占位断言。31 项运行时测试通过；架构债务维持 16 文件／76 函数／0 cycle，diff 检查通过。

## Module Change Packet：标准测试收集

- objective: 新运行时合同进入既有本地命令与 CI。
- primary_module: tests。
- public_entry: unittest discover -s tests。
- variation_point: none。
- inputs: runtimes 测试包。
- outputs: 完整测试收集。
- invariants: 既有用例与历史交易兼容覆盖。
- allowed_dependencies: unittest。
- forbidden_dependencies: 生产设置与秘密。
- tests: 标准发现 1727 项，其中 runtimes 31 项；显式 31 项通过。
- rollback_unit: 测试包入口独立提交。
- documentation: 本文件。

