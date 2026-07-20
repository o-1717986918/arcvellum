# 精确维护执行计划

本计划用于把 Literary Engineering Workbench 从 MVP 骨架推进到可长期维护的工程级创作系统。每个阶段都必须满足：

- 有独立版本号、Git 提交和必要时的 tag。
- 有实现文档和测试。
- 不破坏既有 CLI 参数和作品项目目录协议。
- 新能力默认保守启用，危险能力必须显式开关。
- 生成内容不得自动写入 canon，除非有人工批准记录。

## Phase 13：API 安全边界

目标：让 Dify、前端或外部 Agent 调用 `serve-api` 时具备最小鉴权能力。

交付：

- `serve-api --api-token`。
- 环境变量 `LEW_API_TOKEN`。
- `Authorization: Bearer <token>` 和 `X-LEW-API-Token` 支持。
- `/health` 返回 `auth_required`。
- API 测试覆盖未授权、Bearer 授权和 Header 授权。

验收：

- 不配置 token 时保持本地旧行为。
- 配置 token 后，`/workflow/run`、`/workflow/runs/{run_id}`、`/workflow/artifact`、`/workflow/approve` 均需授权。
- 不在日志、状态文件和 Dify DSL 中写入 token 明文。

## Phase 14：工作流持久化与恢复

目标：让长流程具备可恢复、可追踪、可重复运行的基础。

交付：

- `run-workflow --run-id` 或 `--resume-run-id` 的可控运行目录。
- `workflow/runs/index.jsonl` 运行索引。
- `run-langgraph --thread-id` 和可选 SQLite checkpointer。
- 失败节点记录和恢复策略说明。

验收：

- 同一 run 能被查找、读取和恢复。
- 失败不会覆盖旧运行记录。
- 不要求所有节点自动重入，但必须明确哪些节点可安全重跑。

## Phase 15：审批闭环

目标：让人工审批结果不只是 JSONL，而能驱动下一步任务。

交付：

- `approval-summary` 命令。
- `workflow/approvals/index.jsonl`。
- `revise/reject` 自动生成修订任务草案。
- `approve` 只标记可进入发布候选，不直接写 canon。

验收：

- 审批记录可按 run、chapter、scene 查询。
- Dify 只需要调用 `/workflow/approve`，后端负责落盘和任务生成。

## Phase 16：创作模型适配层

目标：把草稿工作台从“提示词工作区”推进到“可插拔生成执行器”。

交付：

- Provider 抽象接口。
- 本地 dry-run provider。
- prompt 模板目录和上下文包注入。
- 输出解析、失败重试和安全边界。

验收：

- 无模型 key 时仍可 dry-run。
- 有 provider 时能生成正文候选。
- 模型输出只能进入 draft/candidates，不自动写 canon。

## Phase 17：知识库后端抽象

目标：从轻量索引升级到可替换检索后端。

交付：

- `knowledge_store` 接口。
- 标准库 JSON 后端。
- 后续 Qdrant/LlamaIndex 接入说明和可选适配器边界。
- 元数据：来源、类型、章节、角色、确认状态。

验收：

- 检索结果必须带来源。
- 检索结果必须带 canon 状态。
- 知识库召回不得自动改写结构化 canon。

## Phase 18：文风评测增强

目标：实现公版/授权文风工程的回译评测和大纲复原评测。

交付：

- `style-eval` 命令。
- 回译评测模板。
- 大纲复原评测模板。
- 风格 profile 迭代建议报告。

验收：

- 所有样本保留来源和授权说明。
- 评测结果区分语言表层、叙事策略、意象系统和句法节奏。

## Phase 19：Canon / Plot Lint

目标：提供项目级一致性检查器。

交付：

- `canon-lint` 命令。
- 检查人物、地点、时间线、伏笔、章节状态和未确认事实。
- CI 风格报告。

验收：

- 能在完整工作流前后运行。
- 输出明确 blocking / warning / info。

## Phase 20：多分支剧情推演

状态：已在 `v0.20.0` 实现 `branch-simulate`。

目标：让角色推演从单工作台升级为多分支候选。

交付：

- branch schema。
- 分支评分：人物逻辑、canon 安全、戏剧张力、长期伏笔收益、文学潜力。
- 人工选择记录。

验收：

- 角色推演结果仍不是 canon。
- 分支选择可追溯到输入上下文和评分理由。

## Phase 21：发布与示例作品

状态：已在 `v0.21.0` 实现 `publish-chapter`，demo 作品仍待补。

目标：建立正式稿发布链路和可展示 demo。

交付：

- `publish-chapter` 命令。
- 发布 manifest、版本号、变更摘要和回滚记录。
- `examples/demo-work` 或生成 demo 的脚本。

验收：

- 只有通过审查且审批通过的内容能进入发布候选。
- demo 可跑通 init/index/context/simulate/draft/review/chapter/export/workflow。

## Phase 22：场景创作编排器

状态：已在 `v0.22.0` 实现 `compose-scene`。

目标：优先增强创作能力核心，把上下文、人物 BDI、背景故事、分支选择和场景目标收束成可写正文的工程化编排。

交付：

- `compose-scene` 命令。
- `drafts/compositions/{scene_id}_composition.md`。
- `drafts/compositions/{scene_id}_composition.json`。
- 节拍、潜台词、对白意图、感官意象、正文种子和写回候选。

验收：

- 可读取 `branch_manifest.json` 和 `branch_selection.md`。
- 无分支 manifest 时能 fallback，并提示先运行 `branch-simulate`。
- `background_story` 只进入隐性行为因果，不成为正文解释段。
- 输出能作为后续 provider、人工扩写和审查流程的稳定输入。

## Phase 23：模型 Provider 与 Prompt Pack

状态：已在 `v0.23.0` 实现 `http-chat`、prompt pack 和 workflow 可选生成节点。

目标：让真实 LLM 创作接入具备稳定提示词、可复盘输入和可选外部调用边界。

交付：

- `http-chat` provider。
- `prompt_pack.py`。
- `templates/prompts/scene_generation_system.md`。
- `templates/prompts/scene_generation_user.md`。
- `drafts/candidates/*.prompt.json`。
- `run-workflow --generate-candidate --provider ...`。

验收：

- 无模型 key 时 `dry-run` 完整可测。
- `http-chat` 只通过 `LEW_MODEL_*` 环境变量读取配置，不把 key 写入文件。
- prompt manifest 记录 system/user messages 和来源清单。
- workflow 默认不调用模型，显式开启后生成候选和 prompt manifest。

## Phase 24：人物状态演化候选 Patch

状态：已在 `v0.24.0` 实现 `state-evolve`。

目标：把场景产物中的人物状态变化整理为可审查 patch，避免模型或草稿直接改写人物档案。

交付：

- `state-evolve` 命令。
- `character_state_evolver.py`。
- `characters/state_patches/{scene_id}_state_patch.md`。
- `characters/state_patches/{scene_id}_state_patch.json`。
- `run-workflow --mode scene-loop` 自动生成 state patch。

验收：

- 可从草稿或候选产物提取人物状态变化和关系变化。
- 能匹配人物姓名或 `character_id`，未匹配项进入 `unresolved_changes`。
- 不修改 `characters/*.yaml`。
- workflow state 记录 `state_patch` 和 `state_patch_json`。

## Phase 25：候选转正与人物状态审批写回

状态：已在 `v0.25.0` 实现 `promote-candidate` 与 `state-apply`。

目标：把模型候选接入草稿审查通道，并把人物状态 patch 的审批后写回从“待实现”推进为可审计命令。

交付：

- `promote-candidate` 命令。
- `candidate_promotion.py`。
- `drafts/promotions/{scene_id}_promotion.md`。
- `drafts/promotions/{scene_id}_promotion.json`。
- `state-apply` 命令。
- `character_state_apply.py`。
- `characters/state_patches/{scene_id}_state_apply.md`。
- `characters/state_patches/{scene_id}_state_apply.json`。
- `run-workflow --promote-candidate` 可选节点。

验收：

- 模型候选可转成包含标准审查区块的 `drafts/scenes/{scene_id}.md`。
- 已存在草稿时默认拒绝覆盖，显式 `--overwrite` 才替换。
- `state-apply` 默认要求 approve 审批记录。
- `state-apply` 不写 canon，只更新人物档案中允许的状态、弧光、关系和 memory_refs 字段。
- workflow state 记录 promotion manifest/report。

## Phase 26：LLM 文风约束提示词与有效性评测

状态：已在 `v0.26.0` 实现 `style-prompt` 与 `style-prompt-eval`。

目标：把文风学习模块从“统计报告”修正为“生成供 LLM 使用的文风约束提示词，并用 LLM 回译/扩写检验提示词有效性”。

交付：

- `style-prompt` 命令。
- `style_prompt.py`。
- `style/{profile}/style_prompt.md`。
- `style/{profile}/style_prompt.prompt.json`。
- `style-prompt-eval` 命令。
- `style_prompt_eval.py`。
- `style/{profile}/evaluation_results/{mode}/style_prompt_candidate_{timestamp}.txt`。
- `style/{profile}/evaluation_results/{mode}/style_prompt_candidate_{timestamp}.prompt.json`。
- `generate-scene` prompt pack 优先注入 `style_prompt.md`。

验收：

- `style_prompt.md` 是 LLM-facing prompt，不是分析报告。
- `style-prompt-eval` 使用 `style_prompt.md` 生成候选，再调用 `style-eval` 审查效果。
- `http-chat` 只通过 `LEW_MODEL_*` 读取配置，不写 key。
- 没有真实模型 key 时，`dry-run` 仍可测试完整链路。

## Phase 27：Agent Provider 基础层

状态：已在 `v0.27.0` 实现 `agent-run` 与 `agent_provider.py`。

目标：把“审查交给 Agent/LLM 完成、JSON 和提示词由 AI 按规范生成”的方向先落成统一可审计执行层。

交付：

- `agent-run` 命令。
- `agent_provider.py`。
- `agents/runs/{run_id}/input.prompt.json`。
- `agents/runs/{run_id}/raw_output.md`。
- `agents/runs/{run_id}/parsed_output.json`。
- `agents/runs/{run_id}/validation_report.md`。
- `docs/maintenance/agentic-review-development-plan.md`。

验收：

- dry-run 可稳定输出 JSON。
- `http-chat` 使用 `LEW_MODEL_*` 环境变量，不写 key。
- `parsed_output.json` 可供后续 schema 校验读取。
- Agent 输出不自动写 canon、正稿、人物档案或发布目录。

后续 Phase 28-35 详见 `docs/maintenance/agentic-review-development-plan.md`。

## Phase 28-35：Agent 化审查、工作流联动与 Demo

状态：已在 `v0.35.0` 连续实现 Phase 28-35。

交付：

- Phase 28：`agent-validate`、`agent-repair`、`schemas/agent_outputs/*.schema.json`。
- Phase 29：`agent-review-scene`。
- Phase 30：`agent-canon-review`。
- Phase 31：`agent-build-json`、`agent-plan-patch`。
- Phase 32：`agent-style-prompt`。
- Phase 33：`agent-committee`。
- Phase 34：`run-workflow --agent-review`、`run-langgraph --agent-review`、API `/agent/run`、Dify DSL `agent_review`。
- Phase 35：`demo-project` 与端到端 demo walkthrough。

验收：

- Agent 输出必须能写出 run 产物、schema validation 或 repair 产物。
- Agent 审查不直接写 canon、人物档案或发布目录。
- Patch plan 只生成候选计划，不直接应用。
- Workflow agent review 节点进入 workflow state。
- Demo 使用自造文本，dry-run 无 key 可执行。

## 自动推进纪律

1. 每次推进最多跨一个主阶段，除非阶段之间只涉及文档同步。
2. 每个阶段先补测试，再提交。
3. 每次提交后检查：

```powershell
git status --short
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```

4. 打包 skill 时必须验证：

```powershell
rg --files "<packaged-skill>" | rg "__pycache__|\.pyc$|openai\.yaml$|egg-info"
```

5. 任何部署项单独规划，不混入核心工程功能提交。
