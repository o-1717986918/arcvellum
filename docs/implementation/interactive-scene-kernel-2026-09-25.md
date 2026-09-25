# 逐轮对演进入场景创作内核

## Module Change Packets

```yaml
module_change_packet:
  objective: "主创按当前公开舞台逐轮选择角色和场景变化，角色只贡献自己的可见言行"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_interaction_direction_prompt / parse_interaction_direction / render_actor_interaction_prompt / render_interaction_materials"
  variation_point: none
  inputs: ["SceneBrief", "主创场景计划", "公开言行", "已确认来源"]
  outputs: ["导演下一轮建议", "角色提示", "可选择的时序候选素材"]
  invariants: ["角色不写正文或 Canon", "主创保留设定展开、宏观情节、世界演化、心理和文学表达", "不新增审查门禁"]
  allowed_dependencies: ["Engine 现有 SceneBrief 与角色素材合同"]
  forbidden_dependencies: ["Studio I/O", "Provider SDK", "正式晋升写入"]
  tests: ["单人及多人导演/演员合同", "主创素材交接"]
  rollback_unit: "Engine 逐轮合同"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "同一场每名角色延续自己的已生成回答，而非重跑历史"
  primary_module: "Pi Worker conversation"
  public_entry: "actor-conversation/v2 transcript envelope"
  variation_point: none
  inputs: ["角色初始化", "既有问答历史", "本轮提示"]
  outputs: ["本轮角色答案", "首次初始化答案"]
  invariants: ["无工具和项目写权", "既有 v1 顺序会话保持兼容"]
  allowed_dependencies: ["pi-agent-core transcript state", "Studio role conversation gateway"]
  forbidden_dependencies: ["项目文件修改", "顶层 Agent 工具"]
  tests: ["v1/v2 对话合同", "Python gateway adapter"]
  rollback_unit: "Pi Worker 会话续接"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "正式 lean 场景默认使用单人至多人逐轮对演并交付主创可取舍资料"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "scene_performance_materials"
  variation_point: "原整场独立素材作为显式兼容选项"
  inputs: ["主创计划", "演员会话续接", "环境候选"]
  outputs: ["带时序与来源 ID 的候选素材块", "场景事件"]
  invariants: ["主创独占正文生成/修订", "正式审查晋升路线不变", "单人不伪造第二角色"]
  allowed_dependencies: ["Engine public.literary", "Studio role conversation gateway"]
  forbidden_dependencies: ["直接写 Canon", "二套场景晋升流程"]
  tests: ["一人、二人、三人场景", "缓存与主创交接", "正式场景 E2E"]
  rollback_unit: "Studio 对演编排"
  documentation: ["本文"]
```

## 完成标准

1. 主创设计角色初始标签与场景任务，逐轮决定下一位角色、局面变化与何时收束；角色保留即时表达与动作自主性。
2. 每个角色只收到自己的初始化、既有问答历史及可见舞台；其他人的私念不进入其会话。
3. 单人由场景事件、空间变化或自身选择继续；三人及以上不按固定顺序轮转。
4. 交给主创的是按时序列出的候选言行、环境候选与未决问题。主创仍负责设定展开、宏观剧情、世界状态提案、心理与正文修辞；角色台词可取舍改写。
5. 一场测试作品由顶层 Agent 发起，经过原审查与晋升路线，记录正式结果与模型运行证据；若外部模型或余额阻断，明确记录而不伪称完成。

## 实施与试跑记录

- 已接入正式 `create_scene`：主创先给出人物首条初始化与当前场计划；环境写手给出候选；主创逐轮选下一位人物及可进入的局面；每名角色按独立问答历史续演；时序资料再交给主创成稿、审查与修订。原整场素材模式仅作显式兼容及失败回退。
- 已验证单人面对场景变化、三人不按固定次序轮转、角色私念隔离、逐轮历史续接、正式运行时将 `actor_entries`、`director_turns` 和 `environment_candidates` 交给主创。场景相关 Python 测试 58 项、顶层 Agent 测试 46 项、Pi Worker 测试 109 项通过；架构审计通过。
- 顶层 Agent 在独立测试作品《熄灯前的母带》启动正式一场景目标。首次被 DeepSeek 402 余额不足阻断于人物/世界资产阶段；余额恢复后继续至场景生成。
- 真实模型首轮给出一个有效的当前节拍条目和一个提前标为下一节拍的条目，旧解析将整轮判无效并回退整场模式。已改为只让当前节拍的有效条目入场，未来节拍不成为已发生的公开舞台；提示词也明确同轮两条使用同一 `beat_id`。缓存版本升至 v33 以避免重用旧回退资料，补了该案例的回归测试。
- v33 试跑形成三名角色的逐轮素材，且主创曾让同一角色连续回应，证实不是固定双人轮转。随后主创的所有权修订提示因重复附上完整导演计划、逐轮提示、候选正文和来源而越过原有长度上限。现改为：首次创作仍收完整推演；审读与修订只收原始角色言行、环境候选以及精简的导演变化，省去已执行过的初始化和逐轮提示。正式存档与动作来源核对仍用完整原件，避免靠提高长度上限掩盖重复上下文。
- 修正后顶层 Agent 在原目标 `autopilot-67aa4460133346ef` 推进同一测试作品，第 1 场正式晋升：6 轮导演选择、11 条一级角色言行、4 段环境候选；主创创作并完成所有权修订，确定性硬问题从 2 降为 0，独立文学审查 `pass`，正式回执 `scene-tx-1b0a748121af406c860b7c3be0b39baa`，最终 3556 汉字与标点，1 次场景级修订，目标停在 `goal-scope-complete`。详见 `docs/testing/interactive-scene-e2e-2026-09-25.md`。
- 顶层 Agent 的终结说明曾根据最近会话列表误判“没有独立角色会话”，且修订次数显示 0；持久事件与素材缓存均反证该说法。已让长期目标摘要从已提交事务的逐轮事件聚合对演轮次、人物、条目和环境，并按正确的 `worker.scene.revised` 事件计算修订次数，附单测。
