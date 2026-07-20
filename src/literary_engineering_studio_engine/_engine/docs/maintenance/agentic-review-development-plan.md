# Agent 化审查与生成开发计划

本计划承接 Phase 27，用于把“多数审查、提示词、JSON 由 AI 按规范生成，再由工程规则校验”的设想逐步落成。核心原则是：LLM 负责语义判断、文学判断和结构草案；工程层负责 schema、路径、状态、审批、回滚和不可越界规则。

截至 `v0.35.0`，Phase 28-35 已完成首轮工程实现。后续工作应围绕真实模型 provider、多厂商配置、LangGraph checkpointer、真实 Dify 导入验证和前端审稿台继续加深，而不是重新规划 Phase 28-35。

## 总体原则

- 每个 Agent 都必须有 `agent_id`、任务说明、输入 prompt、原始输出、解析输出和验证报告。
- LLM 生成 JSON 是可接受路线，但必须经过 schema 检查、修复循环和人工/规则门禁。
- Agent 审查结论不能直接写 canon、人物档案、正稿或 release。
- 所有真实模型调用统一走 provider 层，key 只通过环境变量读取。
- dry-run 必须保留，确保无 key 环境下仍能跑测试。

## Phase 27：Agent Provider 基础层

状态：已实现。

目标：建立通用 Agent 运行入口。

交付：

- `agent_provider.py`。
- `lew agent-run`。
- `agents/runs/{run_id}/input.prompt.json`。
- `agents/runs/{run_id}/raw_output.md`。
- `agents/runs/{run_id}/parsed_output.json`。
- `agents/runs/{run_id}/validation_report.md`。

验收：

- dry-run 可稳定生成机器可读 JSON。
- http-chat 缺环境变量时明确失败。
- 不泄露 API key。

## Phase 28：Agent JSON Schema 与修复循环

目标：让 Agent 输出从“能解析 JSON”升级为“符合明确 schema”。

拟交付：

- `schemas/agent_outputs/*.schema.json`。
- `agent_schema.py`。
- `lew agent-validate`：校验指定 run 的 `parsed_output.json`。
- `lew agent-repair`：将 schema 错误、原始输出和规范作为 prompt 发给修复 agent。
- `agents/runs/{run_id}/schema_validation.json`。
- `agents/runs/{run_id}/repair_attempts/`。

关键 schema：

- `scene_review.v1`：人物逻辑、canon 风险、节奏问题、修订建议。
- `canon_review.v1`：事实冲突、未确认事实、时间线风险。
- `style_prompt.v1`：文风约束、禁忌、句法策略、叙事距离。
- `json_patch_plan.v1`：可写回候选、理由、风险和审批要求。

验收：

- 不合 schema 的输出不会进入 workflow state。
- 修复循环最多有限次数，失败后保留人工处理任务。

## Phase 29：Agent 场景审查

目标：把单场景审查从规则报告扩展为 LLM 语义审查。

拟交付：

- `agent_scene_review.py`。
- `lew agent-review-scene`。
- `templates/prompts/agents/scene_review_system.md`。
- `templates/prompts/agents/scene_review_user.md`。
- `reviews/agent/{scene_id}_scene_review.md`。
- `reviews/agent/{scene_id}_scene_review.json`。

审查维度：

- 人物行为是否符合 BDI、背景故事、当前状态和关系。
- 场景目标是否被推进。
- 情节是否违反 canon 或制造未确认事实。
- 文风提示词是否被执行。
- 是否存在机械感、同质化、解释过度或戏剧张力不足。

验收：

- 规则审查与 Agent 审查并行存在。
- Agent 审查不能覆盖人工审批。

## Phase 30：Agent Canon / Continuity 审查

目标：把跨章节和跨场景连续性问题交给专门 Agent 读取上下文包、知识库结果和结构化 canon。

拟交付：

- `agent_canon_review.py`。
- `lew agent-canon-review`。
- `reviews/agent/canon_review.md`。
- `reviews/agent/canon_review.json`。
- `longform-audit` 可选读取 Agent 审查结果。

重点：

- 时间线冲突。
- 人物记忆、动机、关系状态冲突。
- 伏笔债务与回收风险。
- 已确认事实与候选事实混淆。

验收：

- Agent 报告必须引用输入来源路径。
- 不能把检索结果直接提升为 canon。

## Phase 31：Agent JSON 草案生成与受控写回

目标：允许 AI 根据规范生成候选 JSON，但由工程层决定是否可写回。

拟交付：

- `agent_json_builder.py`。
- `lew agent-build-json`。
- `lew agent-plan-patch`。
- 写回目标白名单。
- patch preview report。

适用对象：

- 人物状态候选 patch。
- 场景元数据候选。
- 分支选择摘要。
- 风格提示词 manifest。

验收：

- 所有写回都必须是 patch，不直接改原文件。
- patch 必须有来源、理由、风险和审批要求。

## Phase 32：Agent 文风提示词生成器增强

目标：把文风模块正式改成“LLM 生成供 LLM 使用的文风约束提示词，评测提示词有效性”。

拟交付：

- 将 `style-prompt` 可选迁移到底层 `agent-run`。
- 增加 `style_prompt.v1` schema。
- 增加风格约束 prompt 的自评审查。
- 增加回译/扩写失败原因归因报告。

验收：

- 输出重点是可执行 prompt，而不是风格分析文章。
- 回译和大纲扩写使用 prompt + LLM 生成候选，再评估 prompt 是否有效。

## Phase 33：多 Agent 审稿委员会

目标：将单一 Agent 扩展为多角色审查，避免一个模型单点判断。

拟交付：

- `agent_committee.py`。
- `lew agent-committee`。
- 角色：主编、人物心理审查、canon 审查、文风审查、市场可读性审查、反同质化审查。
- 汇总器 Agent。
- 分歧矩阵和最终建议。

验收：

- 每个 Agent 独立输入输出留痕。
- 汇总器必须保留少数意见和不确定项。

## Phase 34：Workflow / LangGraph / Dify 联动

目标：把 Agent 审查节点接入现有工作流。

拟交付：

- `run-workflow --agent-review`。
- LangGraph 节点：agent_scene_review、agent_canon_review、agent_repair。
- Dify DSL 中增加 HTTP Request 节点建议。
- API 增加 Agent run 查询接口。

验收：

- CLI、本地 LangGraph、Dify HTTP 三条路径使用同一底层 provider。
- Dify 不保存模型 key；模型调用仍在本地后端完成。

## Phase 35：Demo、回归集与可展示链路

目标：形成可演示的端到端文学工程链路。

拟交付：

- `examples/demo-work` 或 demo 生成脚本。
- demo 语料和 prompt 均为公版/授权或自造文本。
- 场景从 context、branch、compose、generate、agent-review、promote、state-evolve 到 publish 的演示记录。
- 回归测试覆盖 Agent schema、修复、workflow 接入。

验收：

- 无模型 key 可 dry-run 演示工程链路。
- 有模型 key 可替换为真实输出。
- 发布包不包含缓存、key、私有语料或模型服务残留命名。

## 执行顺序

1. 先完成 Phase 28，让所有 Agent 输出有 schema 门禁。
2. 再做 Phase 29 和 Phase 30，把审查能力接入场景与 canon。
3. 再做 Phase 31 和 Phase 32，把 AI 生成 JSON 与文风提示词机制工程化。
4. 最后做 Phase 33-35，把多 Agent、工作流平台和 demo 串起来。

## 后续未完成项

- 真实模型 provider 仍是通用 `http-chat`，尚未做多厂商 profile。
- `style-prompt` 仍保留独立 provider 逻辑；`agent-style-prompt` 已提供 Agent 版路径。
- Dify DSL 已加入 `agent_review` 参数，但仍需在真实 Dify 版本中导入验证。
- LangGraph adapter 尚未拥有持久化 checkpointer。
