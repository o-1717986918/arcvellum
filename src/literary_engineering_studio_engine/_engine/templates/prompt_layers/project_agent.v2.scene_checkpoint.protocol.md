同一长期目标进入场间编辑检查点：本场刚提交，下一场尚待开始。

用户原始要求：[[ARCVELLUM_PROMPT_0]]
场间状态：[[ARCVELLUM_PROMPT_1]]
目标作品 work_id：[[ARCVELLUM_PROMPT_2]]

用 project_overview(focus="scene-checkpoint") 阅读 macro_plan、story_brief 和 latest_formal_scene 的实际正文。完整阅读本场后段与结尾，理解当前最终状态、时间、世界认识、人物经历和阅读余味；结合全篇阶段与章节任务判断后续值得展开的经验。审美意图、编辑判断与连续性校正各记录自己的来源。

方向成立时沿既定方向继续；需要宏观调整时，经 project_record_direction 或 project_future_replan 调整未写后续。核对资料和文风后，用该 work_id 调用 project_goal_manage(operation="recover", expected_stop_reason="scene-editorial-checkpoint") 继续原目标。用户要求暂停或存在外部阻断时，以实际情况保持暂停并说明原因。
