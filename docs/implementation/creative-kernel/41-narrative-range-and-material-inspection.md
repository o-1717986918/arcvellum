# 41. 宏观叙述、取材完整展示与文风选择调整

目标：基于星光咖啡馆 scene-tx-a4d11128fed4457a8ec52e53f380f8fa 的真实证据，释放章节表达方式与详略选择，展示每次取材返回的完整素材和取舍。

## 已确认依据

五类均被调用，七项委托产出十七条候选。主创把事件叙述限为微量人物认知，把其他领域集中为物件、触觉、局部动作。R02 因“关系”与喜剧 R07 同分而成为主参考。规划落盘统一 summary: low；人物初始化必填 hidden_wound；真实章级义务未形成对应资产。旧链路当前启用；新链路默认状态沿用现有配置，已有交易保留冻结合同。

## 分批 Module Change Packets

每批唯一主模块，按合同、实现、调用方顺序推进。

| 批次 | primary_module / public_entry | 输入 → 输出 | tests |
| --- | --- | --- | --- |
| A | Engine literary/planning，public.literary.normalize_initial_plan / materialize_lean_window | 自由叙事设计、章级文学任务、可选参与人物与冲突 → 保留表达选择的场景档案及章级义务 | planning normalization/materialization、legacy compatibility |
| B | Studio application/lean_longform_planning 与 lean_asset_enrichment | 用户方向与预算 → 章节文学任务、叙述者选择、非强制创伤的人物档案 | application planning/enrichment integration |
| C | Engine prompting，public.prompting.prompt_layer_spec | 作者意图、自由详略、领域任务 → 正向引导的主创和四类取材及审读模板 | prompt layers/registry、v1/v2 frozen snapshots |
| D | Engine literary/style，public.literary.select_active_style_references | 项目审美、当前文学任务及语料 → 可追溯、同分不过度偏好低编号的表达参考 | reference selection regression、real case replay |
| E | Studio observability/creative_live，现有 projection service | 保存的委托、素材、角色历史、取舍 → 完整素材只读投影 | projection/API contracts、real saved tx |
| F | client/features/creative-live，creativeLiveClient | E 的稳定投影 → 原始素材阅读、类别/调用筛选、取舍与来源展示 | feature/component tests、desktop/mobile screenshots/overflow |
| G | workers/pi-worker/scene-material-tool，read_scene_material | 多个明确候选 ID → 一次读取完整候选；旧单条读取兼容 | batch read/unknown ID/budget tests |
| H | Engine prompting，public.prompting.prompt_layer_scope；Studio scene_prompt_snapshot adapter | 交易冻结文本 → 线程内模板渲染，退出恢复；来源选样沿用交易快照 | nested scope/frozen style/old transaction regression |
| I | Studio runtimes/scene_performance，fulfill_scene_material_requests | 新版初始化的主创委托 → 直接分派取材，使用结构承载位置；旧快照继续原规划合同 | direct delegation/no extra planning call、legacy continuation |

额外真实失败修正：旧素材正文容量 600/700 字已改为 12000 字上下文容量；事件来源札记由 240 改为 4000 字，保留完整来源。取材回应在校验前保存 received 记录，校验失败可离线重处理，重复恢复沿用已收到的原文。

统一 variation_point：文学表达与取材目的由 Agent 自由判断；保存、读取、版本与事实状态由确定性合同承载。
统一 invariants：角色卡原文作为唯一人格初始化；素材不直接成为正式正文或 Canon；正式写回和审读 Gate 不降级；既有交易和正文保留；无新增模型客户端；前端只调用所属 feature client；已保存素材全文显示且不以预览伪装全文。
allowed_dependencies：Engine public surfaces、现有 RoleConversationGateway/ApplicationContainer、creative-live projectors与feature client。
forbidden_dependencies：Engine->Studio、Studio->Engine internal、API/组件拥有文学规则、绕过正式任务或 Gate。
rollback_unit：各批可独立审阅的文件差异；保留此前未提交工作。
documentation：本记录、模块目录/生成模块图（新增文件时）、提示词版本。

## 验收目标

1. 世界介绍、跨时段概述、风俗/群体叙述能表达章级文学任务，不依赖杜撰人物冲突；已有场景计划仍可恢复。
2. 每类取材器可按任务提供不同尺度的素材；主创在成稿前选择叙述方式，细节围绕整体阅读效果伸缩。
3. 当前案例重放选样时不会仅因“关系”压过作品审美；缺少相应语料明确呈现。
4. 前端能阅读所有已保存候选，包括舍弃/未选和完整长文本，并看到委托与事实状态；角色私人素材有明确栏目。
5. 涉及模块回归、完整验证矩阵、架构与前端桌面/手机验收；真实生成在独立数据目录进行，鉴权/余额失败保留证据并停止重复调用。

## 本轮结果

A–I 已实现。真实宏观开场交易通过确定性检查、独立审读与隔离写回，原作五类素材全部展示。真实失败推动修正来源裁剪、混合来源状态、JSON 围栏识别、原始交付保存和固定模板冻结；最后的专项回归通过。完整 Python 1829 项（1 项按配置跳过）、前端 274 项、Worker 125 项与桌面/手机 4 项验收通过；详细证据、文学分歧、费用缺测与适用范围见 [42-narrative-range-acceptance.md](42-narrative-range-acceptance.md)。
