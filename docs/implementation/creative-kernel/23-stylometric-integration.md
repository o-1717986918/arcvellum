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
## Module Change Packet：宿主文风用例合同

- objective: 用户可统计语料、保存参数版本并选择主创实验挂载。
- primary_module: application/style。
- public_entry: StylometryService、版本化文档 DTO、分析与存储 ports。
- variation_point: 独立 lab 计算后端及 Studio data root 存储。
- inputs: 作品、上传文本、画像、参数、可选依存原树。
- outputs: 分析结果、不可变版本、挂载快照与逐项测量。
- invariants: 正式文风版本和 Gate、默认未挂载、角色上下文、实验开关相互独立。
- allowed_dependencies: 标准库、application ports、作品标识。
- forbidden_dependencies: Lab 内部计算、FastAPI、Provider、正式作品写入。
- tests: 用例、版本切换、过期挂载、源哈希、缺测与恢复。
- rollback_unit: application 合同与用例独立提交。
- documentation: 本文件。

## Module Change Packet：固定计算包与 adapter

- objective: 安装后的宿主可脱离研究 checkout 运行统计。
- primary_module: infrastructure。
- public_entry: StylometryAnalysisPort / StylometryRepositoryPort。
- variation_point: 固定 wheel 的分析模块与文件 adapter。
- inputs: typed sources 和原始 JSON 合同。
- outputs: typed versioned documents。
- invariants: Lab 原始计算与版本／文件摘要；无模型客户端。
- allowed_dependencies: lab 安装包、标准库、application DTO。
- forbidden_dependencies: Engine internal、正式项目写回。
- tests: 计算一致、来源封装与 wheel 脱离目录运行。
- rollback_unit: 固定计算包与 adapter 独立提交。
- documentation: 本文件、third_party provenance。

## 实施记录

## Module Change Packet：主创动态消费

- objective: 项目所选计量文风经现有主创接口消费，场景交易冻结并记录输出统计。
- primary_module: runtimes。
- public_entry: PiSceneTransactionRuntime、既有 lean runtime composition。
- variation_point: typed snapshot provider 与只读 measurement provider。
- inputs: 不可变版本快照、主创交付正文。
- outputs: 文风快照、源摘要及测量文件。
- invariants: 旧交易保持关闭；五类取材和独立角色聊天沿用原委托；文风与去 AI 味独立；Gate 与写回。
- allowed_dependencies: application DTO、现有 gateway、已注入 ports。
- forbidden_dependencies: Lab 计算、模型客户端、正式档案写入。
- tests: 新旧交易、冻结与版本切换、文风组合、主创独占、输出统计。
- rollback_unit: composition 和 runtime adapter 提交。
- documentation: 本文件。

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

