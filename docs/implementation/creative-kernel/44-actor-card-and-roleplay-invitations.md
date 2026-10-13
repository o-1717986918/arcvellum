# 角色卡与扮演委托修复 · 2026-10-10

## A：Engine 角色卡合同

primary_module：Engine literary/scene/roleplay；public_entry：parse_actor_character_card、render_actor_character_card。
objective：以作者最后的鸣人示例为准，新增十一块 v2 卡，完整支持旧十六块 v1 卡。
inputs：作者原文、版本化卡、冻结模板；outputs：完整角色系统卡及可追溯版本。
invariants：旧卡、旧交易与原文保持，预算明确报错，系统人格只由卡提供；正式正文及 Canon 不改写。
allowed_dependencies：Engine public literary 与 prompting；forbidden_dependencies：Studio、模型客户端、正式写回。
tests：十一块原文结构与渲染、旧卡回读、模板完整性；rollback_unit：角色卡合同。

## B：Engine 提示词资产

primary_module：Engine prompting；public_entry：scene.v2.material.actor、scene.v2.creator.actor-card、scene.v2.creator.delegation、新 scene.v2.actor.turn。
objective：让主创以人物身份填写卡，并以当轮来话、环境与已发生刺激邀请人物回应。
inputs：作者示例与真实失败委托；outputs：纯结构系统模板、正向填写任务、独立当轮提示。
invariants：当轮提示与人格分离，自然交付，四类领域作家各自的文风接口保留，旧提示快照保持。
tests：提示资产注册与内容合同；rollback_unit：新资产版本。

## C：Studio Runtime

primary_module：Studio runtimes；public_entry：SceneCreatorV2MaterialCoordinator、NaturalOutputProcessor。
objective：实际发送面向目标人物的情境与来话；主创文学目的留在主创记录，新交易识别旧卡需要按新模板重填。
inputs：冻结提示、主创委托、已知/参考挂载；outputs：卡独占 system、自然当轮角色回应、完整原文与后置技术记录。
invariants：旧交易按原快照运行；其他四类保持文学邀约；角色语境独立；整理逐字核对，长字段明确报错。
tests：新旧快照、旧作品卡补填、第一人称回应整理保留对白、完整实际保存记录离线核对；rollback_unit：角色当轮适配。

## D：独立角色聊天与评审前端

primary_module：Studio application/character_chat；public_entry：setup/create；inputs：新旧卡；outputs：版本明确的卡填写结构。
invariants：原独立会话初始化与历史保持，主创角色会话不受影响；tests：聊天服务及 feature 回归。
前端批次通过 characterChatClient 消费服务返回的当前卡 schema 和 sections。提示词设计台生成新版本，保留浏览器用户草稿与旧资产原文；角色当轮位可查看修改。
浏览器核验补充：关闭以 Teleport 为根节点的角色页时，RouterView 的页面过渡触发空 parentNode 错误。CharacterChatView 提供稳定的页面元素承接路由过渡，弹窗仍挂到 body；核验关闭、重新打开与移动视口，保留零模型调用断言。

本轮不调用付费模型。真实文学效果尚需余额恢复后的新交易验证。

## E：独立聊天的卡目录读取

primary_module：Studio persistence/character_chats；public_entry：FileCharacterChatRepository.cards。
浏览器复现：作品带有当前角色卡，但隔离实例的私有目录为空，界面无法列出已有卡。读取同时合并作品内已校验的当前卡与私有历史卡，按摘要去重；原文和历史保持，查询不补写私有目录。
tests：导入作品在空私有目录下仍可查看当前卡且零写入，桌面与移动加载；rollback_unit：卡目录读取适配。

## 核验与遗留

此前完整回归 1853 项（1 项跳过）；后续版本合同和卡目录的定向回归 29 项通过，前端单元 5 项通过。桌面 1440×1000 与手机 390×844 验证新十一块卡、旧十六块卡、完整系统卡、独立会话保存及关闭重新打开；零模型调用，零浏览器错误，零横向溢出。架构和模块目录检查通过。

新资产版本：系统卡 4、填卡任务 6、主创委托 9、角色当轮提示 1。评审前端保留旧资产全文和用户草稿。当前作品既有卡与旧交易保持原版本；新交易由主创按冻结的新格式补齐当前卡，真实回应效果尚待新生成核验。

成本分析见 `work/literary-style-rebuild-20261009/cost-cache-audit.json` 与当前成果报告。统计取自391个去重用量事件，没有新增付费请求。非思考整理、原文定位交付、稳定前缀和跨恢复累计预算是后续方案，本批没有将其当作已实现收益。
