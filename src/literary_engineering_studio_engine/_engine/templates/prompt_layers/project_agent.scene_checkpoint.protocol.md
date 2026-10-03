这是同一长期目标的场间编辑检查点，不是新用户指令。正式场景刚提交，下一场尚未开始。

用户原始要求：[[ARCVELLUM_PROMPT_0]]
场间状态：[[ARCVELLUM_PROMPT_1]]
目标作品 work_id：[[ARCVELLUM_PROMPT_2]]

请以该 work_id 调用 project_overview(focus="scene-checkpoint")，用 macro_plan、story_brief 和 latest_formal_scene 的真实正文核对：本场实际改变了什么，人物关系与世界状态怎样变化，全书问题或本章义务推进了多少，推演中的关键选择是否转化成正文。依据实际正文判断，不用台词重合率代替文学判断。若宏观方向一致，保持既定方向；若确有跨场重复、重要承诺落空、节奏或因果偏离，用 project_record_direction 或 project_future_replan 只修正未写的后续，不回改已提交正文。必要时可核查档案与文风挂载。完成检查后以该 work_id 调用 project_goal_manage(operation="recover", expected_stop_reason="scene-editorial-checkpoint") 继续同一长期目标；若遇到真实外部阻断或用户已经要求暂停，说明原因并保持暂停。检查点无需向用户逐场汇报。