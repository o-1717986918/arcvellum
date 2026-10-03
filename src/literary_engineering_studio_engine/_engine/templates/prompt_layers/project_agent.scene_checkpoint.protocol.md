同一长期目标进入场间编辑检查点：本场刚提交，下一场尚待开始。

用户原始要求：[[ARCVELLUM_PROMPT_0]]
场间状态：[[ARCVELLUM_PROMPT_1]]
目标作品 work_id：[[ARCVELLUM_PROMPT_2]]

用 project_overview(focus="scene-checkpoint") 阅读 macro_plan、story_brief 和 latest_formal_scene 的实际正文。理解本场改变了什么、人物关系与世界状态如何发展、全篇问题与本章义务推进到哪里。结合实际阅读经验判断人声、节奏、因果和承诺的连续性。

方向成立时沿既定方向继续；需要宏观调整时，经 project_record_direction 或 project_future_replan 调整未写后续。核对资料和文风后，用该 work_id 调用 project_goal_manage(operation="recover", expected_stop_reason="scene-editorial-checkpoint") 继续原目标。用户要求暂停或存在外部阻断时，以实际情况保持暂停并说明原因。
