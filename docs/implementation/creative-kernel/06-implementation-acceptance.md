# 创作内核 A–F 分批验收记录

本页记录代码级落点与程序验收；文学效果另见 `07-literary-evaluation.md`。实施前的调用图、Module Change Packet 和提示词清单分别在 01、02、04 文档。

| 批次 | 已接入的主入口 | 可观察行为与失败回退 | 验收证据 |
| --- | --- | --- | --- |
| A 意图 | Engine `CreativeIntentV1.from_payload/to_dict`，`public.literary` | 工作意图自由文字并可递增版本；不写 Canon。旧答复无意图时建立带来源的兼容值 | `test_creative_intent`、公开 API 快照 |
| B 主创 | Studio `PiSceneTransactionRuntime.create_scene/revise_scene/review_scene` | 首次主创可直接成稿；短场不自动插段，软下限警告交审读；修订与审读接同一意图。创作失败保留 sidecar | `test_scene_creator_intent_flow`、`test_lean_kernel_v2_transaction_service` |
| C 取材 | Engine `parse_scene_material_requests/render_interaction_materials`，Studio `fulfill_scene_material_requests` | 主创按文学目的请求 0／1／多类候选；导演 `cue`、`director_note` 随候选交接；非视角私念遮蔽。角色续演达到配置上限时将未执行原因交回主创。候选无正式写权 | `test_scene_interaction`、`test_scene_performance_agents` |
| D 描写器 | Engine `render_describer_initialization/render_describer_turn/parse_describer_candidates`，Pi Worker `role-conversation/v1` | 人物、事物、场面三类 0–3 条短候选；纯描写不先规划角色；后续角色可接上。环境和描写器续接有界历史 | `test_scene_describers`、`test_scene_interaction`、Pi Worker check |
| E 记忆 | Studio `SceneCreatorMemoryV1`、正式 `ProjectSceneBriefProvider` | 待处理批次与完成标记支持重启；下一场读已提交正文、Delta、连续性与交接，候选标明待确认 | `test_scene_creator_intent_flow`、`test_lean_kernel_v2_project_adapter` |
| F 提示词 | Engine `prompting.layers`／`public.prompting`；Studio `PromptWorkbenchService`、文件端口、API；Settings `PromptWorkbench.vue` | 作品→全局→随包版本；协议拒写；历史激活、撤销覆盖、固定快照、组装预览。正式 PromptAsset 正文也可按作品／全局版本覆盖并进入原 PromptProgram v2/v3；项目 Agent、顾问、Steward 与 Worker 实际路径接入注册层。旧作品场景模板写回原文件 | `test_prompt_layers`、`test_prompt_workbench`、`test_prompt_program_v3`、前端客户端与浏览器验收 |

程序验证（2026-09-27 至 28 日）：迁移中期 Python 全量 **运行 1677 项，1 项跳过，其余通过**。身份预览补改前的全量运行 **1678 项，1 项跳过、1 项性能门槛失败**：大文件读模型测试第一次耗时 5.147 秒，门槛为 5 秒；单独复跑为 1.532 秒并通过。另一次并行全量运行的 API 启动等待超时也已单独复跑通过。身份预览补改后，提示词、顾问人格和身份预览定向测试通过；架构审计及模块映射检查通过；正式提示资产 **59 项、73 个 task ID** 校验通过；前端全量单元测试 **261 项通过**，Pi Worker **114 项通过**，前端生产构建通过。OpenAPI 合同检查通过，类型已重新生成。设置页在 1440px 桌面与 390px 手机视口通过工作台水平溢出与字段叠压检查，截图位于 `build/creative-kernel/screenshots/`；浏览器用例在当前 API 进程下复验通过。

边界：工作台登记 129 个静态层及 59 个正式资产正文，控制当前 Studio 场景、项目 Agent、顾问、Steward、正式任务与 Worker 的活动提示路径；旧 Engine 直连 Provider 的无调用文风和评测孤岛已清理，仍存的兼容入口维持只读历史层。作品人设、文风、动态 SceneBrief 与任务资料仍保留各自事实拥有者，工作台提供入口与组装占位预览。完整单场最终 prompt 需要运行时资料；程序测试不能替代真实模型文学盲评。
