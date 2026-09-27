# 提示词完整迁移：代码级变更包

2026-09-27。目标是使工作台登记的提示词与实际模型输入一致；每个可编辑版本都有运行时消费点、版本摘要和回退途径。场景角色的人格化初始化保留。

## F1 注册契约与默认文本

- 模块：Engine `prompting.layers`、`public.prompting`；Studio `application.prompt_workbench`、`persistence.prompt_layers`。
- 输入：层 ID、全局或作品范围、版本；输出：默认文本、有效文本、来源、摘要、用途和编辑权限。
- 迁移：把文学默认文本移入随包资源；程序只保存 ID、职责和是否可编辑。固定协议也作为只读资源登记。现有历史 JSON 不迁移，ID 不变。
- 失败：未知 ID、损坏历史、空白或超长文本拒绝；不会静默换回随包默认。
- 测试：优先级、历史回退、资源完整性、只读协议。回滚单位：注册资源与解析器。

## F2 场景主创与候选 agent

- 模块：Studio `runtimes.pi_scene_author_prompt`、`pi_scene_review_prompt`、`scene_performance`；Engine `literary.scene.roleplay.performance`、`interaction`、`describers`。
- 输入：事务开始固定的层文本与带来源的动态资料；输出：模型请求与相同摘要的缓存。
- 迁移：文学指引只来自注册层；事实/JSON/权限文字以只读协议模板渲染。每个运行时层必须有被消费的测试。角色人格标签和作品人设保持主导地位。
- 失败：渲染所需占位符缺失或超出长度直接报错；候选失效仍走现有不晋升回退。
- 回滚单位：主创、审读、候选 agent 可分别回滚。

## F3 项目总编与顾问

- 模块：Studio `project_agent.prompt_policy/service`、`advisor.prompt/service`、应用容器。
- 输入：人格、对话、工具权能、项目范围的有效提示层；输出：分层组装的模型输入。
- 迁移：安全/工具权限与输出协议固定；文学职责、表达方式和阶段判断可编辑。全局与作品版本由同一仓储解析。人格资产继续由原编辑器持有。
- 失败：无仓储配置使用随包版本；修订文本不能修改工具白名单或动作权限。
- 测试：实际服务调用的输入包含覆盖文本，固定约束在覆盖后仍在。回滚单位：总编和顾问分别回滚。

## F4 正式任务资产

- 模块：Engine `prompting.registry`；Studio 正式任务上下文解析、`runtime.prompt_compiler` 与工作台。
- 输入：既有 PromptAsset ID，资产元数据与 body；输出：PromptProgram v3 沿用结构，body 按作品→全局→随包解析。
- 迁移：保留 59 项资产原文件及任务合同；只允许编辑 body，不允许通过工作台改 route、hard constraints、output contract、review requirements。有效 body 的版本与摘要进入编译身份/缓存。
- 失败：未知或不匹配资产拒绝；旧任务按保存时快照继续。
- 测试：正式编译确实使用覆盖 body，元数据/约束不变，历史任务可重放。回滚单位：资产覆盖适配。

## F5 API、前端与审计

- 模块：`api.routers.prompts`、`client/src/features/settings`；文档目录。
- 输入：统一目录、层 ID、范围、文本与版本；输出：搜索/筛选、默认差异、最终组装预览、保存、激活/回退。
- 迁移：旧 API 保持兼容，目录增加 owner、active/inactive 状态及每层来源；作品表达显示归属编辑入口。
- 测试：API、feature client、桌面与移动端；扫描活动调用点与注册消费关系。回滚单位：API/UI 独立。

验收：不能仅以目录条目数宣称完成。每项标记为 `editable/runtime`、`fixed/runtime`、`dynamic/runtime` 或 `inactive`，并以对应运行时测试证明有效文本进入模型输入。

## F6 旧项目模板的显式归属

- 模块：Engine `prompting.layers` 登记 `templates/prompts/*.md`；Studio `application.prompt_workbench` 查阅旧项目 `prompts/*.md`。
- 输入：随包旧模板、作品根目录；输出：目录中的实际作品文本及来源。旧场景生成的 system/user 模板由 Engine `prompting.pack._load_template` 读取作品文件。
- 迁移：旧 Engine CLI/HTTP 模板标记为旧路径。对仍由旧作品使用的 `scene_generation_{system,user}.md` 提供作品范围版本化编辑，激活后写回其原始拥有位置；其余旧直连模板只读登记，避免工作台宣称版本会进入不能受 Studio 控制的直连 Provider。
- 失败：全局范围拒绝编辑旧项目模板；缺失或无效项目、超长文本、损坏历史拒绝；外部文件变更以文件为准并入历史后再保存。旧项目正式产物不自动重写。
- 测试：旧模板目录与随包资源一一对应、作品文件优先、工作台保存/回退后 Engine `build_scene_prompt_pack` 读取同一模板。回滚单位：旧模板适配层。

## F7 正式任务补救与完成片段

- 模块：Studio `runtime.repair_rendering`、`runtime.task_completion`；Engine `prompting.layers` 与只读资源。
- 输入：确定性 issue、目标文件、字数预算、回归防线及任务完成合同；输出：与原有逻辑相同的模型可见固定句式。仅运行数据留在 Studio 的格式化计算中。
- 迁移：把语义合同、停滞、字数增减、回归防线、推理预算、阅读清单、完成清单及停止条件的固定语句登记为协议资源；不改变条件分支与数值计算。
- 失败：资源占位数量不符即拒绝渲染，不静默回落到代码常量；既有任务的合同字段保持原样。
- 测试：现有 repair/context 与 PromptProgram 合同测试，加资源完整性、代表性增减和审查结论断言。回滚单位：这两个运行模块及其资源。

## F8 顾问内置人格与正式任务附加规则

- 模块：Studio `advisor.advisor_personas`、`advisor.service`、Project Agent 组合及 Advisor API 组合；Studio `runtime.context_access_policy`、`runtime.prompt_compiler`；Engine `prompting.layers`。
- 输入：选中内置人格、作用域、正式任务保护文件分类与正文字数合同；输出：运行时消费的有效人格文本及只读执行规则。内置人格 ID、名称、选择存储不变。
- 迁移：五个内置顾问人格默认文本迁入身份资源，可从工作台按全局／作品覆盖；自定义人格仍由既有编辑器持有。受保护文件访问与正文预算附加语句迁入固定协议资源。API 人格目录展示与实际模型输入使用相同解析结果。
- 失败：缺仓储时使用资源默认；不允许人格文本扩大顾问的只读权限；正式规则槽位不匹配立即拒绝。测试覆盖内置人格覆盖、目录/服务一致、执行规则同义，以及原有合同回归。回滚单位：人格与正式规则各自独立。

## F9 活动路径末端句段核对

- 模块：Studio `runtimes.pi_scene_author_prompt`、`scene_performance`、`advisor.advisor_snapshot`；Engine `prompting.layers`。
- 输入：首次无意图的场景请求、角色调用上限和顾问快照目录；输出：相同事实边界、运行状态和只读资料说明。
- 迁移：将固定的默认意图提醒、调用上限原因、快照阅读约束登记为协议资源；文件路径和场景资料仍由原模块投影。
- 测试：场景主创、角色按需取材和顾问快照既有断言，加注册资源完整性。回滚单位：三个模块分别回滚。

## F10 身份初始化组装预览

- 模块：Studio `application.prompt_workbench`；Engine 已有身份与协议资源。
- 输入：选中的角色、环境或内置顾问人格层及其有效作用域；输出：以占位符代替作品人设、导演计划和动态资料的组装预览，同时列出参与摘要的固定层。
- 迁移：角色预览拼接人格资产、角色沉浸协议及有效身份层；环境预览拼接导演生成的六区块初始化与有效环境层；内置顾问人格放入顾问对话协议的第三层，并同时展示第二层有效顾问身份指引。
- 失败：无当前作品时使用显式占位符，不能伪装成真实运行输入；固定资源或必要层缺失时拒绝预览。测试：有效覆盖出现在相应组装位置、权限协议仍在。回滚单位：预览映射，不影响模型运行。
