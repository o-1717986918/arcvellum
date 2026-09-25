# 默认场景表演与文风回归试跑

## Module Change Packets

```yaml
module_change_packets:
  - objective: "新安装与未明确关闭的现有配置默认启用角色和环境候选创作，保留用户显式关闭的选择"
    primary_module: "Studio application/config"
    public_entry: "default_config、load_config、get_scene_performance_preferences"
    variation_point: "默认偏好；不改变调用角色数上限与用户保存的显式偏好"
    inputs: ["Studio config JSON"]
    outputs: ["有效场景表演偏好"]
    invariants: ["用户显式关闭仍生效", "角色与环境候选无正式项目写权", "容量限制与失败语义不降低"]
    allowed_dependencies: ["Studio application/scene_performance_preferences", "Studio runtimes/scene_performance", "设置 API 合同测试"]
    forbidden_dependencies: ["Engine 反向依赖 Studio", "直接 Provider 客户端", "修改用户现有作品"]
    tests: ["tests/test_scene_performance_agents.py", "设置 API 合同测试"]
    rollback_unit: "默认偏好修改"
    documentation: ["本试跑记录"]
  - objective: "恢复对破折号过密的既有阈值阻断，保留语义必要的单次破折号与用户配置例外"
    primary_module: "Engine literary/style"
    public_entry: "default_creative_quality_profile、candidate_language_gate、verify_creative_result"
    variation_point: "dash-overuse 的 profile mode 与硬/软判定；不扩展到逗号或抽象文风软约束"
    inputs: ["正文", "creative_quality_profile", "场景 scope"]
    outputs: ["阻断或提醒的可追溯语言问题"]
    invariants: ["中文排版硬错误继续阻断", "孤立且有语义功能的破折号不因出现本身阻断", "不自动批量改写正文"]
    allowed_dependencies: ["Engine literary/review/creative_quality", "Engine literary/style/punctuation", "Engine literary/scene/transaction", "Engine literary/scene/promotion", "质量规则测试"]
    forbidden_dependencies: ["Studio 再建一套标点 Gate", "脚本替 Agent 改正文"]
    tests: ["tests/test_creative_quality.py", "tests/test_lean_kernel_v2_domain.py"]
    rollback_unit: "破折号规则修改"
    documentation: ["本试跑记录"]
  - objective: "让角色、环境和主创在生成阶段处理成簇的平淡短句、破折号代转折、景物重复与解释性心理"
    primary_module: "Engine literary/scene/roleplay"
    public_entry: "render_actor_scene_prompt、render_environment_prompt、render_performance_materials"
    variation_point: "提示内容与主创交接；Studio 既有 Runtime 和 Pi conversation role 只作适配，不添加门禁"
    inputs: ["SceneBrief", "人物表达与世界事实", "选定文风参考", "一级表演素材"]
    outputs: ["角色言行候选", "环境描写候选", "主创正文与修订"]
    invariants: ["人物意图和对话回合先由角色 Agent 给出", "主创可改台词措辞但不新增回合或动作", "事实来源不被候选素材扩大", "主创是正式正文唯一作者"]
    allowed_dependencies: ["Engine literary/scene/composition", "Studio runtimes/pi_scene_transaction", "Studio runtimes/pi_scene_review_prompt", "Studio runtimes/scene_performance", "Pi Worker conversation role", "提示合同测试"]
    forbidden_dependencies: ["第二套场景状态机", "前端直接写文学规则", "人工代写测试正文"]
    tests: ["tests/test_scene_performance_agents.py", "tests/test_lean_kernel_v2_pi_runtime.py", "workers/pi-worker/test/conversation-profile.test.ts", "真实 Pi 隔离作品 E2E"]
    rollback_unit: "生成与审读提示修改"
    documentation: ["本试跑记录与原始候选链接"]
```

## 验收口径

在隔离作品中从准备场景起运行角色、环境、主创、确定性核验、主创返修、独立审读和单场景原子提交；提交后重读正文与回执。保留真实 provider 调用及候选材料，记录命中的阻断、修订次数和未解决的文风/事实来源问题。未通过不得称为晋升。旧版正式 `task-next` 路线与精简场景事务不可混称。

## 实际执行与结果

- 隔离作品：`build/scene-performance-e2e/default-performance-blocking-20260924`，只从既有文风测试素材复制项目档案与规划；没有复制旧草稿、旧事务或缓存。当前用户配置未保存表演偏好，加载后的有效值为 `enabled: true, max_actor_calls: 4`。显式关闭仍由偏好测试覆盖。
- 使用 `scripts/test_scene_style_e2e.py`、本机真实 Pi Worker/DeepSeek 调用、`LeanSceneRunCoordinator` 的 `STANDARD` 场景事务，依次经过 prepared → created → verified/revision-needed → revised → verified/revision-needed → revised → verified/reviewing → reviewed/committable → committed。事务 ID：`scene-tx-0f0b8d611a7144bcb6a62f2347de8ee6`。本脚本止于单场景提交，不声称完成旧版正式 `task-next` 或整书发布。
- 角色一级候选：周岑 8 条、许遥 9 条；环境一级候选 4 段；主创首稿与两轮修订均保留在 `studio-data/scene-transactions/<事务 ID>/`，最终正文是 `drafts/scenes/scene_0001.md`。首稿曾因无来源可见动作进入主创归属修复；审计器同时附了一条不在正文中的臆造引文。解析器现会保留有正文和同角色证据的有效发现、丢弃该臆造项；若整批无一有效发现则继续报错，不会伪装为 clean。
- 确定性核验：第一轮修订仍有生硬对照与换皮转折两条 hard issue；第二轮修订后无 hard issue，剩 5 条 warning（单次破折号、逗号句内层级、模板风险句、短句密度、逗号链）。破折号从此前同题材试跑的密集使用明显减少；本场首稿 2 处、提交稿 1 处。由于首稿未触及密集破折号的阈值，本次实际返修不是由 `dash-overuse` 触发；恢复该阻断的证据是独立的规则回归测试，不能把这一场当作它的命中演示。
- 独立审读判 `pass`，原子提交回执在 `workflow/scene_commits/scene_0001.json`，`review_decision: pass`，`prose_sha256: 60bc9272ba48a3d16784d72ff9777c15e3f811dba5f7373cb9f67f180fcf18ef`。提交稿核验记录的正文汉字数为 2935；提交流程总计 11 次 provider 调用（不包括首次进程中断前已发生的调用）。

## 提交后阅读检查

人物声音已有局部差异：周岑偏向遮掩与工序语言，许遥更直接地谈窗口、油量和承担风险；但中段仍有“带了”“拿出来”等功能性短答，尚未构成稳定鲜明的个人语言。环境 Agent 实际仍交齐 4 个节拍，成稿的广播、雨声、霓虹数次以相似方式施压；提示中的“可不覆盖每拍”并未完全转化为取舍。本场文风选择器选中 R21（`layered-signal`、`urban-noise`），可能强化了同一噪声材料的反复使用；这是基于选中技法与正文的推断，尚非受控消融证据。心理有进入正文，但“她问的是值不值得，他如果答了……”仍替读者解释人物思想；部分设备结构、转换线和操作细节来自模型扩写，后续需专门核对其事实来源与跨场承诺。独立审读的文字总结称“6 条 warning”，确定性报告实际列 5 条，应以报告为准。本场可作为通过当前流程的测试正文，不作为文风终局样本。

## 验证

- 定向 Python：`tests.test_scene_performance_agents`、`tests.test_creative_quality`、`tests.test_lean_kernel_v2_domain`、`tests.test_lean_kernel_v2_pi_runtime` 共 68 项通过；归属审计 7 项通过。
- Pi Worker：11 个测试文件、106 项通过，构建通过。
- 前端 Vitest：76 个测试文件、250 项通过。
- `git diff --check` 通过。架构审计目前仅剩开始本批前已经存在的 `literary/planning/contracts.py::scene_word_budget_contract` 预算超限（187/184 行、复杂度 45/44）；本批新引入的审计函数超限已拆分修复，没有调整基线掩盖。
- 首轮全量 Python 回归发现设置 API 用例仍断言旧的 `enabled: false` 默认值；已同步新合同，相关 76 项复测通过。最终全量复测共运行 1565 项、跳过 1 项，只有上述预存规划函数的架构预算断言失败；其余用例通过。新增的精简事务破折号阻断测试另行定向通过，因全量运行已开始，它不计入上述 1565 项。
- `python scripts/generate_module_map.py --check` 通过。
