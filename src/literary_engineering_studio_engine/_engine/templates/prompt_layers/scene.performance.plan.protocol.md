# Scene Performance Direction

## Environment Initialization Example
[[ARCVELLUM_PROMPT_0]]

beats 是至多 [[ARCVELLUM_PROMPT_1]] 个外部情境变化，从已知场地、人物和事件自然生长，使下一轮人物的关系或选择余地发生变化。opening_direction 同时决定第一轮由谁回应、使用哪个 beat 以及此人当下可感的局面；cue 写清主要对话对象、可感的起因和关系压力，让演员自己决定声音和动作。第一轮公开舞台为空，请把触发事件的前因排通：若误称来自另一人的玩笑或暗示，先让玩笑者亲自演出，使后来的角色真能听见并误解；若误称者自己挑起话头，给他可感、可信的误认依据和明确的对话对象。若 SceneBrief 已指定某人说出关键称呼或完成情节触发行为，把这个必须发生的情节事实交给该人物本人的 cue，留其余措辞、语气和反应由他创作；下一轮才让别人回应。beats 与 scene_change 承载环境、物件或已演言行的外部后果；若一人的关键言行构成另一人回应的前因，先让前者获得自己的轮次。即使大局需要多人相遇，也可以让一次玩笑、误听或好奇慢慢牵出下一人，人物各自保有不说往事的权利。若本场没有参与人物，opening_direction.finish 为 true。已确认的场景结果仍须成立；结果之间的互动路径可由演员发现。unknown_slots 记录容易误写为事实的资料空位，没有就返回空数组。你在这里设计人物声音与局面。

## SceneBrief
[[ARCVELLUM_PROMPT_2]]

## Working Literary Intent
[[ARCVELLUM_PROMPT_3]]

## Editable Literary Guidance
[[ARCVELLUM_PROMPT_4]]

## Expression And Voice
[[ARCVELLUM_PROMPT_5]]

## Confirmed Sources
[[ARCVELLUM_PROMPT_6]]

仅返回 JSON：{"scene_id":"与 SceneBrief 相同","beats":[{"beat_id":"b1","event":"已确认的外部变化"}],"opening_direction":[[ARCVELLUM_PROMPT_7]],"actor_prompts":[[ARCVELLUM_PROMPT_8]],"actor_tasks":[[ARCVELLUM_PROMPT_9]],"environment_initialization":[[ARCVELLUM_PROMPT_10]],"unknown_slots":[]}。两组人物键已经列全；人物事实以档案和来源为准。