# 编排平台对比

## LangGraph

适合作为核心状态机，表达循环、分支、人工确认、恢复和持久化。Phase 11 已接入 `run-langgraph`。

## Dify

适合作为审稿台和人工输入界面。通过 HTTP Request 调用 `serve-api`，通过 Human Input 收集 `approve / revise / reject`。

## LlamaIndex Workflows

适合知识库摄取、召回和检索评测子流程，不作为全局创作状态源。

## CrewAI

适合角色推演和多角色辩论实验，但结果必须经过 canon 审查。

## Temporal

适合后期长任务恢复、重试和生产调度；当前阶段暂不引入。
