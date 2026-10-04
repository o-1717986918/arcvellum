# 自动去 AI 味实验挂载

2026-10-04。用户授权实验挂载及启动开发版。实验以主创已完成的正文为输入，依据参考项目的十一项规则形成局部编辑建议，再由程序应用可校验的改动。原稿、改后稿和依据保留；现有审读、验证和正式写回继续运行。

## Module Change Packets

### Engine prompting

- objective: 十一项参考规则转写为正向文学编辑提示，提供单一文风栏。
- primary_module: Engine prompting。
- public_entry: public.prompting。
- variation_point: experiment.less_ai_tone.editor 版本化可编辑模板。
- inputs: 已有正文、文风、作者意图。
- outputs: 自然文字的局部改稿建议。
- invariants: 原角色卡、既有提示词 ID 和快照。
- allowed_dependencies: Engine 资源、标准库。
- forbidden_dependencies: 外部仓库运行依赖、模型客户端。
- tests: 注册、文风占位和正向提示检查。
- rollback_unit: 提示资产、来源归属独立提交。
- documentation: 本文件、模块目录。

### Scene runtime

- objective: 成稿及返修后自动清理，在审读前交付结果。
- primary_module: Studio runtimes。
- public_entry: PiSceneTransactionRuntime.create_scene / revise_scene。
- variation_point: 默认关闭的实验 mixin、冻结挂载、既有角色 gateway。
- inputs: CreativeResult、规则快照、主创文风。
- outputs: CreativeResult、原稿/改后稿/局部补丁/拒绝原因审计。
- invariants: SceneDelta、角色对话与引文、数字、人物名、已有证据；旧交易保持原挂载状态。
- allowed_dependencies: Engine public、既有 gateway、自然输出整理器。
- forbidden_dependencies: 新模型客户端、直接正式写回、整篇静默覆盖。
- tests: 自动调用、缓存、开关冻结、保护文本、重叠/重复定位、自然输出及技术整理。
- rollback_unit: runtime 独立提交。
- documentation: 本文件、模块目录。

### Application configuration / API / settings

#### Application

- objective: 用户可查询、切换并持久化实验开关。
- primary_module: application。
- public_entry: get_less_ai_tone_preferences / set_less_ai_tone_preferences。
- variation_point: 现有 save_config 与 LES_CONFIG_PATH。
- inputs: 配置、enabled 布尔设置。
- outputs: 设置及规则来源摘要。
- invariants: 正式默认关闭；保存成功后更新运行中的配置；已开始的场景挂载冻结。
- allowed_dependencies: 标准库、application.config。
- forbidden_dependencies: FastAPI、模型客户端、正式项目写入。
- tests: 布尔校验、保存失败一致性、配置往返。
- rollback_unit: application 独立提交。
- documentation: 本文件、模块目录。

#### API

- objective: 前端可通过 HTTP 查询、保存实验设置。
- primary_module: api。
- public_entry: /experiments/less-ai-tone。
- variation_point: application preferences 函数。
- inputs: 严格布尔请求。
- outputs: preferences JSON。
- invariants: HTTP 适配层不拥有配置保存逻辑。
- allowed_dependencies: FastAPI、application。
- forbidden_dependencies: 直接文件修改、模型调用。
- tests: 请求校验、持久化、新作品健康/read-model/SSE。
- rollback_unit: API、OpenAPI 合同独立提交。
- documentation: 本文件。

#### Vue settings

- objective: 在设置页查看和切换自动去 AI 味实验。
- primary_module: client/features/settings。
- public_entry: settingsClient。
- variation_point: 独立设置组件。
- inputs: preferences。
- outputs: 开关设置请求、保存或失败反馈。
- invariants: 组件只使用所属 feature client。
- allowed_dependencies: Vue、settingsClient、既有样式。
- forbidden_dependencies: generic transport、文件或模型访问。
- tests: 开关加载、保存、失败恢复、客户端请求合同及桌面/移动布局。
- rollback_unit: Vue 独立提交。
- documentation: 本文件。

### Development launcher

- objective: 使用独立实验配置启动源码 API 和 Vite。
- primary_module: scripts。
- public_entry: scripts/start_dev.ps1 的 ConfigPath 参数。
- variation_point: LES_CONFIG_PATH。
- inputs: 独立配置、可用端口。
- outputs: 开发版进程、日志及 URL。
- invariants: 既有进程、正式用户配置；所有辅助进程隐藏启动。
- allowed_dependencies: 现有 Python/Node 开发工具。
- forbidden_dependencies: 新鉴权存储、无关进程终止。
- tests: 源码导入、版本核对、健康与实际服务检查。
- rollback_unit: launcher 独立提交。
- documentation: 本文件。

## 参考归属

来源：[lieflat-less-ai-tone](https://github.com/larashero3-dotcom/lieflat-less-ai-tone)，固定提交 27d29232f10124db904ca9c0536d0b67cb3b2833，MIT，Copyright (c) 2026 shiujan。源码指南及许可证留档于 third_party/lieflat-less-ai-tone，原指南作为来源资料。运行时挂载的是本项目按用户要求编写的正向版本。

清理采用局部补丁；每处须对应原文唯一位置和规则编号。相同段落结构、引文、数字、人物名及已记录证据由程序复核。这些检查覆盖可确定的差异，文学意味与事实一致性仍由后续审读判断。

## 已实现链路

1. 场景第一次进入 create/revise 时，冻结实验开关、编辑模板、技术整理模板、作者文风；已有场景提示词快照的交易保持原链路。
2. 主创正常完成 CreativeResult 后，同一主创运行时以正向编辑模板回看原文，使用自然语言提出局部替换。技术整理器随后提取补丁，替换文字须来自主创建议原文。
3. 程序按原文位置应用可复核的补丁；重复定位、重叠、引文/数字/段落/人物名/交接证据变化记录为拒绝，原文保留。SceneDelta 保持同一份对象。
4. 改后结果继续由现有验证、审读、修订和场景写回处理；未新增 Canon 或档案写入路径。
5. 缓存目录为 data_root/scene-transactions/交易 ID/less-ai-tone。mount.json 冻结挂载，每轮目录保存 original.md、editor-answer.md、cleaned.md、report.json 和技术整理原文。

设置 → 模型连接中可查看和切换“自动去 AI 味 · 实验”。设置 → 提示词的“修订与交接”下可编辑 experiment.less_ai_tone.editor。普通默认配置关闭；开发启动使用独立配置文件启用。scene_creator_v2 的开关保持原设置，本实验同时兼容现有 v1 和 opt-in v2 成稿。

writing-dna-skill 继续作为此前文风架构的参考；本次实验消费已有作者指令及挂载文风，没有加入新的语料蒸馏流程。lieflat 原仓库的统计脚本用于研究性诊断；本次自动修改由本项目新增的主创编辑、技术整理与局部补丁链路执行。

## 实验与开发启动证据

- 真实小样：项目现有 deepseek/deepseek-v4-flash，两次模型调用，采用四处修改、拒绝零处。原稿 219 字符、改稿 196 字符。文件保存在 work/dev-runtime/sample-data/scene-transactions/live-less-ai-tone-20261004/less-ai-tone；没有正式场景写回。
- 样例仅证明调用、自然建议整理和局部改稿记录完整。第二处修改缩短了重复动作句，迟疑节奏可能减弱；文学效果仍需代表性场景与作者评审。
- 开发启动：npm run dev -- -ConfigPath work/dev-runtime/less-ai-tone-experiment.config.json。配置由原设置复制，实验 enabled=true。原默认用户配置保持原文件。
- 页面 http://127.0.0.1:5173/ui/，API http://127.0.0.1:8791；均实际返回 200。版本 0.99.12，源码导入与版本同步通过。
- 后台 supervisor 命令被自动审批以 blocked by policy 拒绝，改用上述项目标准开发入口。进程由工具执行会话持有，当前 PID/会话记录见 work/dev-runtime/launch.json。
- 浏览器确认实验开关显示开启。909 px 桌面、390 px 移动截图完成；新组件文字与选择框无重叠、无内部横向溢出；页面根宽度等于视口宽度。

## 验证结果

- runtime 定向：9 项通过，覆盖成稿、返修、缓存、旧快照、文风/版本冻结、v2 自然创作到审读、补丁保护及技术整理原文一致性；既有自然输出 4 项通过。
- application/API 定向：3 项通过，覆盖默认关闭、持久化、保存失败一致性、严格布尔 HTTP 输入、新建作品 health/projects/runtime adapters/workspace/SSE。
- Python 全量：1696 项，OK，跳过 1 项。首次全量因已有 sidecar 测试临时日志被 Windows 占用而出现清理错误；该项单独重跑通过，完整复跑 264.497 秒通过。完整日志见 work/dev-runtime/less-ai-tone-python-tests-rerun.log。
- client 全量：80 个文件、254 项通过；类型检查与生产构建通过；Pi Worker 13 个文件、121 项通过。
- doctor/CLI、prompt registry、架构审计、模块图、OpenAPI 合同同步、diff check 均通过。架构债务维持 16 文件/76 函数/0 cycle。
- 真实模型效果结论保持为“小样链路跑通”；冲突、日常、空间调度和设定揭示的文学效果仍待作者验收，v2 总开关继续采用原配置。
