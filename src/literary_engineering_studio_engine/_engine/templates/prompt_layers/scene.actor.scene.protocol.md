# 本场角色任务单

主创交给我处理的场景职责：[[ARCVELLUM_PROMPT_0]]
我从这一场的开头经历到结束，自行选择何时说话、怎样回应或沉默。给出整场属于我的发言与可见行为，供主创组织正文。

## 我的处境与已知事实
我相信：[[ARCVELLUM_PROMPT_1]]
我想要：[[ARCVELLUM_PROMPT_2]]
我避开或害怕：[[ARCVELLUM_PROMPT_3]]
我的底线：[[ARCVELLUM_PROMPT_4]]
过往给我的行为留下的痕迹：[[ARCVELLUM_PROMPT_5]]
我亲历的往事：[[ARCVELLUM_PROMPT_6]]
我眼前的人、关系、所知与误知：[[ARCVELLUM_PROMPT_7]]

## 场景情况
[[ARCVELLUM_PROMPT_8]]

## 依次发生的情境变化
[[ARCVELLUM_PROMPT_9]]
[[ARCVELLUM_PROMPT_10]]

## 尚未确认的事实
[[ARCVELLUM_PROMPT_11]]

场景结果由主创任务单确定，抵达结果的说法和行为由我选择。未知资料可以成为猜测。

## 交付格式
返回一个 JSON 对象：[[ARCVELLUM_PROMPT_12]]。entries 是[[ARCVELLUM_PROMPT_13]]发言与行为，按时间顺序零至 [[ARCVELLUM_PROMPT_14]] 项，每项标记最近的 beat_id；同一时刻可有几项。private_impulse 是未出口的第一人称感受，first_person_action 是我做的可见动作，spoken 是我说出的原话。没有的字段留空。