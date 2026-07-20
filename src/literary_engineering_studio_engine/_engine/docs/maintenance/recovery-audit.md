# 恢复审计报告

## 背景

在 Phase 11 打包和缓存清理过程中，曾发生一次误删普通文件的问题。随后已从旧发布包、当前源码状态和人工重建内容恢复项目，并从 `recovered-baseline-0.11.0` 起启用 Git 管理。

本报告记录当前恢复状态、验证方法和剩余风险，避免后续继续开发时遗忘这次恢复边界。

## 当前恢复状态

- Git 分支：`main`
- 基线标签：`recovered-baseline-0.11.0`
- 当前版本：`0.48.0`
- Python 源码：43 个源文件
- 文档入口：30+ 个文档文件
- 测试覆盖：34 个测试文件，113 个模块级回归用例
- 发布包：`outputs/skill-zips/literary-engineering-workbench-skill.zip`

## 已恢复范围

### 工程源码

已恢复并验证：

- CLI 入口：`cli.py`
- 项目初始化：`init_project.py`
- 记忆索引：`memory_index.py`
- 上下文包：`context_packet.py`
- 文风编译：`style_compiler.py`
- LLM 文风约束提示词：`style_prompt.py`
- 文风提示词有效性评测：`style_prompt_eval.py`
- 场景草稿：`scene_draft.py`
- 审查 CI：`review_ci.py`
- 角色推演：`roleplay_lab.py`
- 编排蓝图：`orchestration_blueprint.py`
- 章节工作台：`chapter_pipeline.py`
- 长篇审计：`longform_audit.py`
- 多格式导出：`export_package.py`
- 工作流 runner：`workflow_runner.py`
- LangGraph adapter：`langgraph_adapter.py`
- FastAPI backend：`api_server.py`
- Dify DSL：`dify_dsl.py`
- API 审批闭环：`approval.py`
- 创作模型 provider：`generation_provider.py`
- 元数据知识库：`knowledge_store.py`
- 文风评测：`style_evaluator.py`
- Canon / Plot Lint：`canon_lint.py`
- 多分支剧情推演：`branch_lab.py`
- 章节发布链路：`publish.py`
- 场景创作编排器：`scene_composer.py`
- Prompt Pack：`prompt_pack.py`
- 人物状态演化候选：`character_state_evolver.py`
- 候选稿转草稿：`candidate_promotion.py`
- 人物状态审批写回：`character_state_apply.py`
- 通用 Agent provider：`agent_provider.py`
- Agent schema 与 repair：`agent_schema.py`
- Agent 场景审查：`agent_scene_review.py`
- Agent canon 审查：`agent_canon_review.py`
- Agent JSON / patch plan：`agent_json_builder.py`
- Agent 文风提示词：`style_prompt_agent.py`
- 多 Agent 审稿委员会：`agent_committee.py`
- Demo 项目生成器：`demo_project.py`
- 全局配置层：`model_config.py`
- 本地前端控制台：`frontend/index.html`、`frontend/styles.css`、`frontend/app.js`
- Agent 设定创作层：`asset_workshop.py`
- 顶层创作总监：`director_agent.py`

### 测试规模

误删后曾只剩一个大测试文件。现已恢复为模块级测试：

- `test_initializer.py`
- `test_memory_context.py`
- `test_style_compiler.py`
- `test_style_prompt.py`
- `test_scene_review.py`
- `test_roleplay_lab.py`
- `test_orchestration_blueprint.py`
- `test_chapter_pipeline.py`
- `test_longform_audit.py`
- `test_export_package.py`
- `test_workflow_runner.py`
- `test_langgraph_adapter.py`
- `test_api_server.py`
- `test_dify_dsl.py`
- `test_approval.py`
- `test_generation_provider.py`
- `test_knowledge_store.py`
- `test_style_evaluator.py`
- `test_canon_lint.py`
- `test_branch_lab.py`
- `test_publish.py`
- `test_scene_composer.py`
- `test_character_state_evolver.py`
- `test_candidate_promotion.py`
- `test_character_state_apply.py`
- `test_agent_provider.py`
- `test_agent_schema.py`
- `test_agentic_workflows.py`
- `test_model_config.py`
- `test_asset_workshop.py`
- `test_director_agent.py`
- `test_project_integrity.py`
- `helpers.py`

当前目标不是“每一行代码都覆盖”，而是恢复误删前的回归测试规模和失败定位能力。

### 文档入口

已恢复：

- `AGENTS.md`
- `agentread.yaml`
- `README.md`
- 架构文档
- 模块文档
- Phase 1-48 实现文档
- 维护文档

## 验证命令

每轮恢复后运行：

```powershell
git status --short
python -m unittest discover -s tests -v
```

发布包验证：

```powershell
rg --files "C:\path\to\packaged-skill" | rg "__pycache__|\.pyc$|openai\.yaml$|egg-info"
```

该命令应无输出。

## 剩余风险

- 部分文档为恢复后的压缩版，不一定完全等同误删前的原始长文档。
- 发布包不包含主工程测试目录，测试主要在开发仓库中维护。
- Dify 已有 Workflow DSL starter；仍需在目标 Dify 版本中做一次真实导入验证。
- LangGraph 已支持 thread id；SQLite checkpointer 仍未作为硬依赖接入。

## 后续修复优先级

1. 用完整性测试保护 agentread / README / AGENTS 中的路径引用。
2. 补 LangGraph SQLite checkpointer 可选依赖。
3. 在真实 Dify 环境中导入 DSL 并记录版本差异。
4. 真实 Dify 环境导入验证。
5. 更多模型 provider profile 模板。
6. 真实 Dify 环境导入验证。
7. LangGraph SQLite checkpointer。
8. 增加跨章节人物弧光审计。

## 操作纪律

- 清理缓存只删除 `__pycache__/` 目录和明确生成物，不再使用宽泛 `-Include` 删除。
- 大范围复制或打包前先提交当前状态。
- 发布包重建后必须检查内部条目。
- 每次完成一个恢复批次后提交 Git。
