# 场景主创记忆与跨场景交接

## 场内状态

`SceneCreatorMemoryV1` 是交易私有 sidecar，位置为 `scene-transactions/<transaction_id>/scene_creator_memory.json`。它保存工作意图及版本、意图来源、候选 ID、采用／改写／舍弃理由、未决问题、公开舞台、阶段、提示摘要和待处理素材请求。渲染给主创的摘要限制在 5000 字符；角色私念不进入公开舞台。模型调用保持独立，下一次调用由 Studio 重新装入摘要，不依赖提供商隐含会话。

请求素材前先落盘意图与待处理批次。每项请求用提示摘要和批内序号记录完成标记；候选与角色／环境历史在同一会话文件中保存。恢复时先处理尚未完成的项，已完成的项不再调用。素材块写入缓存后才将记忆标为 `material-ready`，再交给主创。这避免单批中断时重复演出，但进程在模型返回与首次文件写入之间中断时，远端调用仍可能重复；本地没有外部提供商幂等键。

`CreativeIntentV1` 只携带读者体验、可选的读者已知／误知与刻意保留的未知。模型修订主句时，未重写的可选字段继承原值。意图侧写不进入 `SceneDelta` 或 Canon；旧答复缺失意图时，Studio 用 `scene_function` 建兼容工作意图并标记 `brief-compatibility`，新提示则要求首次显式陈述。

## 跨场景状态

`ProjectSceneBriefProvider` 将上一场已提交正文排在前，随后读取已提交 `SceneDelta` 和连续性投射，再读 Canon、用户方向、人物档案等。`scene_source_evidence` 给正文标明“已提交叙述”，给 Delta 与连续性标明“提议仍待确认”。`next_handoff` 进入下一场 `SceneBrief.incoming_handoff`；`reader_question_updates` 和 `promise_updates` 在带来源的投射中保留。上一场候选、主创误导意图与角色私念不自动成为下一场世界事实。

## 接口与迁移

| 接口／文件 | 输入 → 输出 | 故障与迁移 |
| --- | --- | --- |
| `SceneCreatorMemoryV1.load/save/render_context` | 交易 ID、场景 ID → 有界 sidecar／摘要 | scene ID 或 schema 不符即拒绝；没有旧 sidecar 时建空记忆 |
| `PiSceneTransactionRuntime._ask_creator_with_materials` | 意图、素材请求、候选缓存 → `CreativeResult` | 待处理批次重启续接；16 轮仍未成稿则阻断并保留状态 |
| `fulfill_scene_material_requests` | `MaterialRequestV2`、会话、固定层文本 → 候选块 | 无模型或无权限即报错；没有值得添加的描写可返回空候选 |
| `ProjectSceneBriefProvider.prepare` | 已提交文件与正式项目状态 → `SceneBrief` | 来源摘要进入输入修订哈希；来源改变时提交拒绝 |

回滚单位：A 的 Engine 意图合同、B/E 的 Studio 记忆与调用、C/D 的候选会话、F 的提示层快照互相独立；旧正式正文、Delta 和 Canon 不需要迁移。旧的自动补长函数保留但新创建路径不调用。
