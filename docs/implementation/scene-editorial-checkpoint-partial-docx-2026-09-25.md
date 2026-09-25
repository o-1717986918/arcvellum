# 场后宏观复核与未完稿 DOCX 快照

## 核查结论

《文学少女》已提交的第五场有八轮角色推演。正文保留了七濑的警告、远子的入场与不代答、七濑读过旧作的悬念、心叶选择“门槛”等八轮核心言行，且把心叶“从未真正看过七濑”的认识写成了场尾的新行动意图。环境素材也进入了走廊、门槛和活动室的感官组织。问题不是“采用太少”；相反，部分台词和感官句接近推演原文。主创完成了局部心理和衔接，但本场宏观位移主要已由场景计划和推演预置。需要检查跨场、跨章的兑现情况，不能用素材引用率代替剧情推进判断。

当前长期目标只在后台任务终止后恢复顶层 Agent。场景提交后下一场可以立即开始，没有场间宏观复核。现有正式全书发布器要求交付路线审计通过；交付中心按钮也要求作品完整，故未完稿即使已有正式正文，也不能随时取得合订 DOCX。

## Module Change Packet E：顶层 Agent 场后复核

```yaml
module_change_packet:
  objective: 顶层 Agent 管理的持续创作每提交一场后暂停在场间，核对宏观方向并视证据调整未写后缀
  primary_module: project_agent/ 与 automation/
  public_entry: project_goal_manage 的持久策略、lean scene commit checkpoint、delegated goal followup
  variation_point: managed lean-v2 goal 的场间复核策略
  inputs: [正式场景提交回执, 当前故事概览, 全书规划, 用户原目标]
  outputs: [场后复核事件, 保持或修正方向, 恢复原长期目标]
  invariants: [仅在正式提交后触发, 不回写已晋升正文, 无偏差不强制重排, 用户手动暂停不被自动恢复]
  allowed_dependencies: [既有 goal observer, overview/story brief, project_future_replan, project_record_direction]
  forbidden_dependencies: [第二套场景状态机, 未提交草稿作正式成果, 新文学硬门禁]
  tests: [policy normalization, commit checkpoint, delegated followup]
  rollback_unit: 场间复核策略及 followup
  documentation: [本文件]
```

## Module Change Packet F：未完稿 DOCX

```yaml
module_change_packet:
  objective: 作品未完成时随时从已提交正式场景创建可下载的当前稿 DOCX
  primary_module: projections/partial_delivery.py
  public_entry: POST /project/delivery/snapshot 与交付中心按钮
  variation_point: 当前稿快照，与全书正式发布并行而不替代
  inputs: [项目正式场景提交回执, 章节顺序, 项目标题]
  outputs: [DOCX, Markdown, 快照 manifest]
  invariants: [只取正式提交且正文哈希吻合的场景, 标明未完稿快照, 不声称通过全书发布审计]
  allowed_dependencies: [现有 DOCX 导出器, 正文清理投影, 交付下载路径]
  forbidden_dependencies: [改动正式 release manifest, 吸收候选稿, 绕过场景晋升]
  tests: [部分章节、缺失回执、正文哈希、API、前端按钮]
  rollback_unit: 快照服务和交付入口
  documentation: [本文件]
```

## 实施与验证

- 顶层 Agent 发起的 lean-v2 长期目标默认开启 `editorial_scene_checkpoint`；每场正式提交后，后台目标在下一场之前停在场间检查点。顶层 Agent 读取全书规划、故事状态和本场正式正文，决定保持方向或仅重排未写后缀，再恢复同一目标。超长场景的检查视图保留开头与结尾。
- 自动恢复必须带 `expected_stop_reason=scene-editorial-checkpoint`。若用户随后改为手动暂停，恢复不会覆盖该状态。控制器恢复前等待上一场的租约与线程退出，防止显示已恢复却没有工作线程。
- 交付中心新增“导出当前稿 DOCX”。快照只包含有提交回执且正文摘要匹配的正式场景；既有全书正式发布按钮与审计保持原样。输出位于作品的 `exports/snapshots/`，清单标为 `partial_snapshot`。
- 自动化验证：后端 72 项、Project Agent 54 项、Pi worker 110 项、全量前端 257 项通过；Vue 类型检查、API 合约生成、架构审计与 `git diff --check` 通过。DOCX 测试以真实导出器生成文件并检查 OOXML 内容和未提交场景排除。当前环境没有 LibreOffice，无法进行视觉分页检查；尚未进行消耗模型额度的在线整场测试，也未启动桌面窗口人工点击。

## 《文学少女》实绩与提示成本审计

第五场正式正文与八轮演员素材对照：八轮主要言行均进入了正文，部分接近原句；四段环境候选的空间和感官内容也被采用。主创增加了心叶的误读、自责、认识转变和下一步行动意图。因此“推演采用过少”不成立。更真实的风险是把角色素材过于直译成正文、让单场关系变化淹没在按轮次编排之中。跨场规划另有应当在新场前检查的接续点：第四场的缺页线索尚未明确解决，第五场已转入第二天；后续章节计划仍把部分已经发生的帮忙决定或三词写作当作首次节点。这可能是延迟兑现，也可能是重复，必须依据新场正文核对，而不能仅凭计划字段定罪。

本场角色标签的真相分两层：作品的 `characters/_actor_personas.json` 不存在，因此顶层 Agent 报告“没有项目级专属标签”是准确的；但第五场导演生成了三份独立初始化标签，分别含心叶的 `TRAIT_GUARDED_SELF_PUNISHER`、七濑的 `TRAIT_TSUN_SHAME`、远子的 `TRAIT_WHIMSICAL_APPETITE_FOR_STORIES`，三者还各有不同的 `VOICE_*`、`WRITER_LIKE_*` 与默认语言标签。`performance-interaction-session` 中记录的实际角色初始化与这些标签一致。该场创建早于新情绪标签开发，故记录里没有专门的 `EMOTION_*`；新逻辑只对之后重建的场景生效。项目级标签当前是导演参考输入，最终送给演员的是导演生成的场景初始化，二者不是一条直接强制挂载链。

第五场主创真实输入见 `.literary-engineering-studio/pi-conversations/worker/runs/run-1790345939947/conversation.prompt.md`，共 29,297 个字符。约 10,681 字符是 Relevant Sources，约 9,728 字符是完整角色与环境候选；另有完整 SceneBrief、文风参考、引用白名单、字数要求、文学渲染和 JSON/SceneDelta 格式说明。这一轮模型记录的输入为 17,085 tokens，输出为 17,930 tokens（其中推理 13,472）。主创仍须把素材组织成连续小说、补心理和世界状态、提取正式变化，因此不能简单删掉主创创作；但每轮重送原始推演、冗长来源和大量格式说明，确实有明显成本。修订调用又会重送正文与压缩后的素材。

机械感主要不是一句“文风要平淡”造成的。实际主创系统提示仅要求遵循角色契约、无工具、返回 payload；用户提示开头先强调姓名日期数量精确，接着是一大段 canon JSON 与资料。创作要求和结构化状态抽取、精确 ref 校验、请求素材协议共享同一输出，容易把注意力转向安全编排和字段填写；素材按轮次详列也鼓励逐轮改写。本场当时的文学渲染段已允许情绪、心理和变调，但尚无之后加入的显式 `EMOTION_ARC` 等标签；位置靠后，前面的大量资料有稀释效应。文风挂载 ID 中的 `clear-plain` 也不可单看命名：实际挂载文本已允许起伏；本场选入的部分示例语感仍偏泛化。

后续成本优化应优先把推演压成“因果转折 + 可引用的原创台词/动作 + 必要环境意象 + 素材出处”的简报，去掉重复节拍说明和非视角私念，再让主创按文学判断增删；相关 canon/source 做场景定向裁剪，修订优先传变化部分。保留主创对场景和全书的最终叙事责任，不能把小说降成素材拼接。此项是审计建议，本次没有贸然改变已有创作协议。
