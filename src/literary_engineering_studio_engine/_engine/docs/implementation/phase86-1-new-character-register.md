# v0.86.1：新角色登记门禁

本补丁解决场景开发中的一个旁路风险：平台 Agent 在正文里临时引入新人物，但没有同步创建角色档案、候选资产、审查或 approval，导致长篇项目的人物库和正文事实逐渐漂移。

## 1. 新增文件

1. `src/literary_engineering_workbench/new_character_register.py`
2. `docs/modules/new-character-register.md`

## 2. 核心机制

新增 `new_character_register`，要求候选 manifest 和 AgentReview JSON 显式声明：

1. 本场景是否引入新角色。
2. 新角色是一次性路人还是持久角色。
3. 持久角色是否已有候选资产、审查、approval 或 promotion。
4. 未解决项是什么。

## 3. 接入模块

1. `prompt_pack.py`：生成前 prompt 注入新角色登记契约。
2. `platform_agent_tasks.py`：generation sidecar 和 AgentReview sidecar 明确要求填 register。
3. `agent_scene_review.py`：review prompt 与 dry-run payload 包含 register。
4. `candidate_promotion.py`：candidate generation gate 与 candidate review gate 检查 register。
5. `scene_readiness.py`：chapter/export readiness 继承 register gate。
6. `agent_task_status.py`：route-audit 输出显式新角色登记 gate。
7. `character_state_evolver.py`：state-evolve 要求持久新角色走候选资产路线。
8. `draft_text.py`：最终正文清洗过滤 `## 新角色候选登记`。
9. `schemas/agent_outputs/scene_review.v1.schema.json`：登记 `new_character_register` 字段。

## 4. 门禁策略

候选生成 manifest 中允许：

1. `none`
2. `existing_only`
3. `ephemeral_only`
4. `candidates_ready`
5. `resolved`

AgentReview clean pass 只允许：

1. `none`
2. `existing_only`
3. `ephemeral_only`
4. `resolved`

`needs_candidate`、`needs_review`、`needs_approval`、`unknown`、`blocked` 均为 blocking。`candidates_ready` 在 review 阶段仍会阻塞，除非已有 approval 或 promotion。

## 5. 测试

新增或更新测试覆盖：

1. prompt manifest 包含 `generation_standards.new_character_register`。
2. generation sidecar 包含 `new_character_register` 要求。
3. dry-run AgentReview 输出 clean `new_character_register`。
4. promotion 阻塞 `needs_candidate` 的新角色登记。
5. 既有正式候选 fixture 全部携带 clean register。
