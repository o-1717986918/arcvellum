# v0.99.15 Token、缓存与顶层创作链路

基线：已发布 v0.99.14；日期：2026-10-28。每批只修改对应所有者。

## 批次 A：自然交付传输

```yaml
module_change_packet:
  objective: 降低整理索引的输入开销，保持原文逐字恢复和版本绑定
  primary_module: Studio runtimes natural transport
  public_entry: NaturalOutputProcessor.process / decode_reference_delivery
  variation_point: 模型可见索引的紧凑表示
  inputs: [已保存原文, Engine 公共 source index, 既有交付合同]
  outputs: [更小的整理请求, 同一语义的已验证交付]
  invariants: [不改正文, 不补造文学判断, 保留摘要绑定和逐字校验, 兼容旧记录]
  allowed_dependencies: [Engine public literary, 既有 natural reference adapters]
  forbidden_dependencies: [新增模型客户端, 放宽 Gate, 修改正式项目事实]
  tests: [原文引用合同, 错误引用与重复文本, 缓存恢复, 隔离顶层创作验收]
  rollback_unit: 自然交付索引独立提交
  documentation: [本文, 同版本发布说明]
```

## 批次 B：私有会话预算

```yaml
module_change_packet:
  objective: 在明确的 token 预算下复用授权会话，避免字节数混用
  primary_module: Pi Worker conversation replay
  public_entry: ConversationReplay.open
  variation_point: 预算估算及剩余上下文
  inputs: [授权历史, 当前提示, 模型上下文与输出预算]
  outputs: [可复用会话或有记录的新一代会话]
  invariants: [不跨权限复用, 不恢复未完成代次, 保留原始消息, 不截断授权正文]
  allowed_dependencies: [Pi SDK, 既有 replay store]
  forbidden_dependencies: [正式项目写入, 新 Provider 调用]
  tests: [中文与 ASCII 预算, 系统与工具开销, 变更和撤回, 完整会话恢复]
  rollback_unit: 会话预算独立提交
  documentation: [本文]
```

## 批次 C：顶层读取

```yaml
module_change_packet:
  objective: 减少顶层 Agent 重复读取状态的输入，保持细查入口
  primary_module: Studio project_agent
  public_entry: ProjectAgentDependencies / existing project tools
  variation_point: 状态摘要和按需展开
  inputs: [既有只读投影, 工具参数, 稳定提示词策略]
  outputs: [轻量状态入口, 完整按需查询]
  invariants: [保留所有展示与操作功能, 不缓存过期事实, 不绕过生命周期或写回]
  allowed_dependencies: [既有 read models / application ports]
  forbidden_dependencies: [直接改 Engine, 静默丢弃必要合同]
  tests: [工具合同, 长期目标与恢复, API/SSE, 真实创作链路]
  rollback_unit: 顶层读取独立提交
  documentation: [本文]
```

## 发布条件

- 单元、集成、架构、模块映射、提示词及版本同步通过。
- 隔离作品从顶层 Agent 发起，验证创作、审查、必要修订、正式写回及继续推进。
- 生产前端与 Pi Worker 构建、打包来源核验通过。
- 签名 Windows 安装程序、更新清单与 macOS 预览包完成发布并核对资产。
- 不把模拟链路、未运行或外部阻断写成真实模型通过。
