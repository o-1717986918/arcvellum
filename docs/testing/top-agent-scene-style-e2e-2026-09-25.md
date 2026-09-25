# 顶层 Agent 正式场景：初始化与文风验证

状态：修订版试跑中。测试作品只用于验证，不修改用户既有作品。

## 证据边界

两轮测试均由 `POST /project-agent/sessions/{session_id}/turns` 启动顶层 Agent；顶层 Agent 再使用正式目标管理、规划、资产、场景创作路线。直接调用底层场景脚本的早期诊断不计作本报告的端到端成果。

### 修改前基线

- 作品：`build/top-agent-scene-e2e/one-scene-20260925`
- 顶层会话：`project-agent-303f22860d4d407c`
- 目标运行：`autopilot-168a777a8510482b`
- 场景事务：`scene-tx-fabdbba35e48453d94e5f2dda352a8a5`
- 实际完成至少六轮角色推演并生成环境候选；场景进入 `revision-needed`，未晋升。基线于 2026-09-25 12:59 左右暂停，材料保留。
- 原始初始化全文：本机数据目录 `.literary-engineering-studio/scene-transactions/scene-tx-fabdbba35e48453d94e5f2dda352a8a5/performance-interaction-session-e4badcba9f99e4b940e0.json` 的 `initializations`；环境首条见同目录 `performance-plan-e4badcba9f99e4b940e0.json` 的 `environment_initialization`。

基线角色标签中，纪蔚出现 `PUBLIC_SPARE_SENTENCES`、`VOICE_SHORT_SCREW_TURNS`、`VOICE_HALF_SENTENCE_AT_EMOTION`；梁栖出现 `VOICE_ANNOUNCER_EVENNESS`、`PUBLIC_BACK_STRAIGHT_VOICE_EVEN`。这些标签把语言压低、把具体姿态混入稳定人格，并与默认 `ANTI_SHORT_SENTENCES` 对冲。环境首条出现 `SCENE_OLD_RADIO_STATION_AFTER_TYPHOON`、`ATTR_SALT_DAMP_AND_OLD_TAPE`、`MOVEMENT_STYLE_SEASIDE_REALISM`，把本场意象和写实取向固化为常驻创作模式。环境输出随之密集复现潮湿、盐、灯光、设备细节。

动作来源审查还把 `他停了一下`、`梁栖往日志那边看了一眼` 等过渡组织判为未授权动作，触发多次完整正文修订与角色续演。该轮估计模型费用超过 0.11 美元，未换来正式正文；这是成本与风格问题的现场证据，不是修订版效果。

## 修订版验证点

- 测试作品：`build/top-agent-scene-e2e/persona-technique-20260925`
- 顶层会话：`project-agent-993d338dd399428e`
- 目标运行：`autopilot-cedec8e571b24f52`
- 角色初始化应由主创从人物性格定性，而本场任务、动作和临时信息进入后续任务／轮间提示；已存档人设用作主创依据，不再覆盖主创本场首条。
- 环境初始化只用抽象观察、修辞和节奏技法；具体天气、物件、空间与本场意象进入后续场景输入。
- 角色关键抉择和情节动作仍核对一级来源；普通走位、眼神、停顿等由主创组织，避免反复整场修订。
- 必须核对顶层发起记录、角色／环境首条、逐轮推演、主创正文、核验、审读、修订和正式提交回执，缺任一步不得称端到端通过。

## 自动化回归

相关后端测试 48 项通过；追加动作来源与 API 回归 40 项通过；前端 252 项、Pi worker 109 项通过。客户端构建、桌面／窄屏推演窗口 Playwright 视觉测试和架构审计通过。真实文学效果待修订版正文人工对读。
