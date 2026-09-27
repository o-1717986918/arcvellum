# 改造前场景创作调用图与问题定位

本页记录实施前基线，便于逐项核对改造效果。依据 `docs/architecture/module-catalog.md` 和 `agent-interface-development-standard.md`，本次仅修改 Engine `literary/`、`prompting/` 的拥有者合同，经 `public/*` 暴露，再接 Studio runtime、application、API 与 settings feature。

```text
ProjectSceneBriefProvider -> SceneBrief + 已提交正文/SceneDelta/连续性/用户方向
  -> PiSceneTransactionRuntime.create_scene
     -> 风格/表达投射 -> scene_performance_materials [当前必先规划、环境、角色]
     -> render_scene_create_prompt -> 主创 worker
     -> [material_requests 循环] -> 角色/环境候选 -> 主创 worker
     -> complete_first_draft_length [当前不足软下限则插段]
     -> CreativeResult -> verify -> 独立 review -> [revise] -> commit
```

当前角色初始化从项目 `actor_personas` 或表演规划读取；角色有场景历史，环境每次新会话。`render_interaction_materials` 记录公开言行，但交接压缩时丢失 `cue`、`director_note`。主创模型调用本身无持久会话；跨场景由项目来源与正式 `SceneDelta` 重建。现有正式 `PromptAsset` 注册表、Studio `PromptProgram v3` 和大量内嵌运行提示并行存在。

目标调用：主创首次选择工作性文学意图与行动；可直接写，或按需取角色、环境、描写器候选。每次主创调用从有界场景记忆重载意图、取舍和未决问题，候选始终无正式写权。review 根据候选正文与意图判阅读损害，软字数仅提醒。正式跨场景事实仍由已提交正文、`SceneDelta` 和连续性投射供应。

变更风险：旧缓存内没有意图和场景记忆；旧素材块与新请求结构不同；角色私念不能漏给其他视角；提示版本必须在一次交易内固定；现有预改工作树涉及 Project Agent 与 lean planning，不应混入本次修改。
