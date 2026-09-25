# 创作现场：过程可见与正文区修订

状态：已实施并完成定向验证。目标是让作者在创作现场直接看见规划、角色推演、环境素材、主创写作、复核和晋升；修订稿与差异占用正文主画布，而非右侧窄栏。

## Module Change Packet A — 现场只读投影

```yaml
module_change_packet:
  objective: "重连后现场按真实时间呈现候选、修订与晋升，不再把正式正文显示成仍在流式生成"
  primary_module: "Studio observability/creative_live"
  public_entry: "GET /creative-live 与 /creative-live/artifacts/{id}/revisions（现有只读合同）"
  variation_point: "none"
  inputs: ["当前作品的持久事件", "当前作品的实时事件"]
  outputs: ["按时间归并的 CreativeLiveSnapshot", "按时间排序的 ArtifactRevision"]
  invariants: ["不合成文学事实", "不改变晋升/审查 Gate", "仅展示当前作品的数据", "继续遮蔽密钥和主机路径"]
  allowed_dependencies: ["api/routers/creative_live.py", "observability/creative_live/*", "既有只读存储接口"]
  forbidden_dependencies: ["文学 Engine 内部写接口", "新的 Provider 调用", "项目文件写入"]
  tests: ["tests/observability/test_creative_live_api.py", "tests/observability/test_creative_live_projection.py"]
  rollback_unit: "创作现场投影修正"
  documentation: ["本文件"]
```

## Module Change Packet B — 作者视角

```yaml
module_change_packet:
  objective: "创作过程成为正文同级主视图，修订版本和差异进入中央正文画布"
  primary_module: "Vue creative-live feature"
  public_entry: "services/creativeLiveClient.ts（保持现有 feature client）"
  variation_point: "none"
  inputs: ["CreativeLiveSnapshot", "ArtifactRevisionSummary/ArtifactRevision", "CreativeSession"]
  outputs: ["过程/正文/修订三种中央阅读模式", "可读的 Agent 过程与全文修订对照"]
  invariants: ["只读观察", "候选与正式身份清楚区分", "不展示模型私有思考", "小屏不横向溢出"]
  allowed_dependencies: ["client/src/features/creative-live/*", "client/src/styles/creativeLive.css", "现有 SafeMarkdown"]
  forbidden_dependencies: ["generic API transport 直连组件", "跨 feature concrete component", "创作路线写入"]
  tests: ["creativePresentation/projection Vitest", "client build", "桌面与窄屏可视检查"]
  rollback_unit: "创作现场中央画布布局"
  documentation: ["本文件"]
```

## 视觉与交互决策

对象是盯着长篇创作进程的作者。页面的单一任务是回答“现在谁在做什么、留下了什么、正文怎样变化”。沿用现有墨绿仪表背景与浅色工作区：深墨 `#0c1815`、工作白 `#f8faf7`、正文白 `#ffffff`、线色 `#d6dfd8`、信号绿 `#28735f`、修订删改红 `#a33f33`。标题继续使用产品显示字族，正文使用现有阅读字族，时间和技术信息使用 utility 字族。

布局以中央主画布的“过程 / 正文 / 修订”三种观察模式为主，左侧列出创作内容，右侧保留简短审查证据。过程模式把活动时间线和 Agent 可读结果放大到中央；修订模式把版本选择、完整文本、差异切换放在中央。其识别点是同一张稿纸沿时间在三种状态间切换，而不是另造装饰性看板。窄屏各区纵向排列，中央内容仍可独立滚动。

完成标准：用《屋顶上的暴雨花园》已保存的真实事务重连时，正文显示“已纳入项目”，过程模式能选到角色/环境/主创/审读会话，修订模式能读完整修订稿及前后差异；不能只剩一个正文预览。

## 验证结果

- 真实事务重连：正文身份为 `promoted`；过程投影保留 21 次 Agent 会话、40 条活动、2 条审查；推演详情有 7 轮角色演出、3 名角色与 4 段环境描写。修订历史从事务缓存恢复初稿、修订稿，再与正式晋升稿合为 3 个可读版本。缓存只按当前作品事务 ID 读取，正式稿内容还需与提交回执哈希吻合。
- 重连时按事件发生时间归并持久与实时事件，并带上实时游标；旧的流式预览不会覆盖较晚晋升的正文，也不会在 SSE 重放时再次覆盖。
- Vue 定向测试 254 项、Python 创作现场定向测试 22 项、桌面/窄屏 Playwright 2 项、前端类型检查和生产构建均通过。模块映射检查与架构审计通过，`git diff --check` 无空白错误。
- 窄屏选择“正文修订”后会自动定位中央稿纸；桌面截图确认过程、正文、修订在同一主画布，审查证据留在右侧。

## Module Change Packet C — 修订痕迹恢复

```yaml
module_change_packet:
  objective: "进入正文修订即可看见有色修改痕迹；正式晋升未改字时展示紧前一次实际修订"
  primary_module: "Vue creative-live feature"
  public_entry: "services/creativeLiveClient.ts 既有 revisions/revision 只读合同"
  variation_point: "none"
  inputs: ["按时间排序的修订摘要", "选中版本及其 diff"]
  outputs: ["中央正文区的有色修订差异", "明确的比较基准说明"]
  invariants: ["不伪称晋升再次改字", "不修改后端修订证据", "全文仍可一键查看"]
  allowed_dependencies: ["client/src/features/creative-live/*", "既有 RevisionDiff 与样式"]
  forbidden_dependencies: ["Engine Gate", "项目文件写入", "组件直接调用通用 HTTP transport"]
  tests: ["定向 Vitest", "真实事务数据核对", "桌面与窄屏 Playwright"]
  rollback_unit: "修订视图的比较选择和展示"
  documentation: ["本文件"]
```

复现：已保存事务的三版正文为初稿、主创修订稿、正式晋升稿。后两版文本同哈希；正式晋升稿的相邻版本 `diff` 为空，而修订稿相对初稿的 `diff` 有增删行。旧界面默认“全文”，因此修订页和“比较变化”页都可能看不到颜色。

修复：修订页默认进入有色比较；若正式晋升的 `diff` 为空且与前一版同哈希，前端只读加载这一段同文版本的首个修订稿差异，并明确标注“晋升未再次改字”。全文按钮保留。窄屏进入修订页后，将首条有色修改滚入可视区域。真实事务的正式稿 `diff` 长度为 0、前一修订稿 `diff` 长度为 3534，符合此路径。

验证：新增 2 项定向比较测试；前端 78 个文件共 256 项测试通过，桌面和窄屏 Playwright 2 项通过，构建、架构审计、模块映射与空白检查通过。Playwright 使用仓库内隔离测试数据，测试服务在结束后关闭，未替换用户作品数据。
