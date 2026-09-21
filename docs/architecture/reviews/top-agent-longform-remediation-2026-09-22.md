# 顶层 Agent 长篇验收问题修正方案（2026-09-22）

## 目标与边界

本轮修正来自《潮痕之下》五章长篇端到端验收。目标是修复已经被成稿、事件流和发布产物共同证明的问题，不以增加门禁或追逐字数为主要手段：

- 场景规划不再把章节级承诺机械复制为每场必须发生的事件，避免相邻场景抢戏与重复。
- 无关精确数字、模板句法、人物声音同质等软约束在规划与生成阶段落实；违禁词和标点仍由既有确定性审查执行。
- lean-v2 对已挂载品质档案的严重级别保持一致，不再维护第二张硬编码规则表。
- 正式提交后把场景增量投影为连续性事实，支持人物别名和跨场状态追踪。
- 每章检查点只产生一次作者摘要，运行投影正确累计返修并刷新正式字数预算。
- 导出标题不重复章号；顶层回执明确区分流程完成、正文规模和文风预设评估。

本轮不新增“数字密度门禁”，不提高达标字数阈值，也不以放宽或删除既有审查规则换取通过。

## Batch A：场景规划与生成合同

```yaml
module_change_packet:
  objective: "场景只承担本场分配的事件，生成时默认不用与情节无关的精确数字"
  primary_module: "Engine literary/planning"
  public_entry: "literary_engineering_studio_engine.public.literary 的长篇规划与物化入口"
  variation_point: "不同章节、场景职责与作品题材"
  inputs: ["story architecture", "chapter plan", "scene inventory", "mounted style prompt"]
  outputs: ["scene contract", "prose generation context"]
  invariants: ["用户硬约束保留", "章节承诺仍在章级兑现", "不新增数字审查门禁"]
  allowed_dependencies: ["Engine planning contracts", "Engine prompting/style public contracts"]
  forbidden_dependencies: ["Studio automation", "Provider SDK", "Vue"]
  tests: ["test_lean_longform_plan.py", "test_longform_materializer.py", "test_story_architecture_contract.py"]
  rollback_unit: "planning-contract-remediation"
  documentation: ["本修正方案", "v0.99.8 release notes"]
```

完成标准：局部场景合同不会因复制章级 payoff 而引入合同参与者之外的人物；生成提示明确要求数字具有叙事必要性，并要求相邻场景事件唯一、人物声音可区分。

## Batch B：场景验证与连续性写回

```yaml
module_change_packet:
  objective: "正式场景按同一品质档案验证，并在提交后留下可追溯连续性事实"
  primary_module: "Engine literary/scene transaction"
  public_entry: "Engine public literary scene verification/commit-plan API"
  variation_point: "挂载的 creative quality profile 与 scene delta"
  inputs: ["candidate body", "quality profile", "previous formal scene", "scene delta"]
  outputs: ["verification result", "commit plan continuity mutations"]
  invariants: ["违禁词与标点继续审查", "既有 profile severity 是唯一严重级别来源", "正式写回原子化"]
  allowed_dependencies: ["Engine style/review", "Engine assets/continuity", "Engine foundation"]
  forbidden_dependencies: ["Studio persistence", "Runtime provider", "UI"]
  tests: ["test_creative_quality.py", "test_lean_kernel_v2_pi_runtime.py", "test_lean_kernel_v2_project_adapter.py", "test_lean_book_flow.py"]
  rollback_unit: "scene-verification-continuity-remediation"
  documentation: ["本修正方案", "v0.99.8 verification"]
```

完成标准：lean 事务不再硬编码八个标点规则；相邻正式正文进入生成/复核上下文；提交的 delta 能更新 canon facts/timeline 或明确记录冲突候选，身份称谓可被后续场景读取。

## Batch C：自动推进与运行事实投影

```yaml
module_change_packet:
  objective: "长篇运行只在章真正完成时发一次章节摘要，并准确报告返修与正文规模"
  primary_module: "Studio automation"
  public_entry: "automation controller/run loop/chapter checkpoint services"
  variation_point: "章节边界、返修次数、正式场景计数"
  inputs: ["durable task events", "formal scene receipts", "word budget"]
  outputs: ["chapter checkpoint event", "run progress projection", "refreshed budget facts"]
  invariants: ["不复制 Engine task lifecycle", "事件可恢复且幂等", "不把流程进度冒充字数进度"]
  allowed_dependencies: ["application ports", "Engine public projections/workflow"]
  forbidden_dependencies: ["Engine internal modules", "Vue component state", "Provider-specific payload"]
  tests: ["test_autopilot.py", "test_lean_kernel_v2_autopilot_loop.py", "test_lean_autopilot_release.py"]
  rollback_unit: "automation-projection-remediation"
  documentation: ["本修正方案", "v0.99.8 release notes"]
```

完成标准：五章运行最多产生五个带 chapter_id 的完成检查点；总返修数和最高返修场景可从事件恢复；word_budget 的实际计数与正式场景同步。

## Batch D：作者可见顶层反馈与导出

```yaml
module_change_packet:
  objective: "作者在运行中看到章节、人物与线索变化，交付文本与证据范围表述准确"
  primary_module: "Studio project_agent"
  public_entry: "project_agent story brief/read model contracts"
  variation_point: "章节完成事实和发布审计结果"
  inputs: ["chapter checkpoint", "formal manuscript projection", "style evaluation metadata"]
  outputs: ["author-facing story update", "final receipt wording", "progress labels"]
  invariants: ["不直接写项目文件", "不生成正文", "不把预设盲评宣称为成稿盲评"]
  allowed_dependencies: ["Studio application services", "Engine public projections"]
  forbidden_dependencies: ["Engine internals", "raw provider transcript", "hidden mutation"]
  tests: ["tests/project_agent/test_read_models.py", "tests/project_agent/test_service.py", "workers/pi-worker/test/project-agent-protocol.test.ts", "frontend component tests"]
  rollback_unit: "project-agent-author-feedback-remediation"
  documentation: ["本修正方案", "v0.99.8 release notes"]
```

完成标准：章节摘要包含不可逆变化、主要人物立场、已兑现/开放线索和下一章压力；流程进度与正文完成度分名显示；整书标题只有一个章号；终局回执把“文风预设评估”与“成稿审读”分开。

## Batch E：版本与发布

```yaml
module_change_packet:
  objective: "形成可追溯、可安装、验证结果真实的 v0.99.8 发布"
  primary_module: "packaging/release"
  public_entry: "version sync scripts and release workflow"
  variation_point: "platform artifact availability"
  inputs: ["tested source tree", "version metadata", "release notes"]
  outputs: ["v0.99.8 metadata", "release artifacts", "verification record"]
  invariants: ["版本号全树一致", "未运行的测试不写通过", "制品哈希可复核"]
  allowed_dependencies: ["build scripts", "desktop config", "CI release workflow"]
  forbidden_dependencies: ["用户作品内容", "开发机秘密", "伪造外部发布成功"]
  tests: ["version sync", "Python tests", "Vitest/build", "Pi Worker checks", "architecture audit", "artifact verification"]
  rollback_unit: "release-v0.99.8"
  documentation: ["docs/releases/v0.99.8.md", "docs/releases/v0.99.8-verification.md", "README.md"]
```

发布标准：只有完成版本同步、定向回归、全量可运行矩阵和制品验证后才创建发布标签；平台或签名未完成时必须标注为候选制品而非已发布。
