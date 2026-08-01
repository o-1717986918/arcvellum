# W6-7B ContextCacheKey 与 session lease 契约（计划）

## 目标

按统一实施方案 §11.9/§11.10 建立 AO-6 的缓存与会话确定性底座：

1. `ContextCacheKey`：project revision、scope、Canon digest、人物状态
   digest、文风 hash、字数预算 revision、节奏/桥契约 hash、角色与任务
   类型组成的不可变缓存身份。
2. `partition_reusable`：任一身份字段变化即失效，缓存分区不可复用。
3. `SessionLease` 与 `session_reusable`：同角色、同项目/模型/文风、Context
   Ledger 未失效、上一任务完成、token/时间/失败预算未超时才可复用；
   Writer 与 Reviewer 永不互相转换。

## 边界

- 缓存只保存可重建的 Studio 运行资料，不成为项目正式事实。
- 本批不读文件系统、不创建任务、不调用 Worker、不持久化。
- provider cache 与内容缓存的分层、throughput 投影属后续批次。

## 交付物

- `runtime/context_cache.py` 与 `runtime/session_lease.py`。
- `tests/runtime/test_context_cache_session_lease.py`。

## 验收

- fingerprint 稳定且对任一身份字段敏感；缺失字段/invalid scope 有 violation。
- 同 key 可复用，任何身份差异不可复用。
- 会话复用决策覆盖角色/项目/模型/文风/Ledger/完成态/三类预算。
- Architecture Audit 不新增债务；全量测试通过。
