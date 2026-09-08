# ArcVellum 精简文学内核 v2 架构设计

> 文档状态：K0-K6 已实现；lean-v2 处于可选预览，默认切换等待文学盲评证据
> 决策级别：上位架构决策
> 适用范围：Literary Engineering Engine、Studio Runtime、Autopilot、Pi Worker、任务协议与创作可观察性
> 核心目标：显著减少模型往返、形式化产物、重复语义审查和故障表面，同时保留正式事实写回、安全边界、恢复能力与文学质量
> 实施约束：先建立并行 v2 路线；旧路线在迁移期保留为 `strict-v1`；未经真实作品 A/B 验证不得切换默认值

## 1. 决策摘要

ArcVellum 当前文学内核已出现明显的工程化过度：一个场景被拆成约三十个连续状态，创作、推演、审查、状态演化和连续性维护分别产生任务、sidecar、completion marker、摘要、新鲜度证明和写回证据。系统能够证明 Agent 遵守流程，却需要为一千余字正文支付多轮模型调用、巨量上下文和大量重试成本。

本设计作出以下决策：

1. **正式保护边界从“每个过程步骤”收敛到“不可逆写回边界”。**
2. **场景成为一个创作工作单元。** 默认由一次主创调用完成必要推演、取舍、编剧决策和正文；独立审查按风险触发。
3. **RP、分支、Composition、Reader Contract 继续作为创作能力存在，但不再天然对应独立 Agent 任务和正式门禁。**
4. **机器字段全部由机器负责。** Agent 不再生成 task id、路径、摘要、字数、session id、completion marker、provenance 布尔值或固定枚举包装。
5. **人物状态、Canon、连续性和正文以一个 Scene Delta 进入原子提交。** 不再为每种变化重复运行一套准备、审查、批准和应用链。
6. **跨场景质量转移到章节检查点。** 节奏、承诺、问题账本、文风漂移和连续性更适合在章节范围审查。
7. **现有自适应编排暂停扩张。** 仅复用风险画像、滚动窗口、资源冲突和检查点；Planner/Compiler/Simulator 不再成为创作前的新必经流程。
8. **不进行推倒式重写。** 新增 `scene-transaction-v2`，复用现有项目格式、Pi Worker、沙箱、预检、写回协调器、SQLite UoW、SSE 和前端投影。

本设计正式修正旧路线图中的一项原则：

> “吞吐提升不得减少任何正式 Gate”不再适用于 RP、分支、Composition、逐场 Reader Contract、多重语义 Review 等创作过程门禁。

继续不可削弱的内容只有：沙箱与权限、正式写回一致性、用户锁定事实、重大 Canon 变化、版本与恢复、发布前完整性检查。

## 2. 事实基线

### 2.1 代码事实

当前生产场景路线由 `workflow/state_scene.py::_scene_state()` 顺序组装，包含：

1. 场景人物资产；
2. Context Packet 与 Trace；
3. RP 模板与 RP Agent 任务；
4. Branch Manifest、Branch Agent 任务与选择；
5. 字数、读者体验、叙事节奏合同；
6. Composition 与 Composition Agent 任务；
7. 正文生成、sidecar、字数修订；
8. AgentReview、review sidecar、promotion、promoted draft、static review；
9. 人物状态 patch、语义审查和写回；
10. Canon 写回；
11. 连续性 ledger 准备、生成、独立审查、应用；
12. 下一场 handoff。

`routes/scene/gates.py` 又对同一路径进行正式提交验证，`workflow/audit/` 负责只读投影，Studio preflight 再做一次 sandbox 输出检查。任务状态、路由门禁、审计投影和 Worker 预检各有合理职责，但文学条件在多个层次重复表达。

长篇规划路线约有十五个状态：故事架构、独立审查、修订、字数预算、场景库存、章节义务及各自候选/审查/修订，最后才物化场景。

当前 `src/literary_engineering_studio/orchestration/` 已包含五十余个计划、编译、模拟、风险、滚动窗口、资源和 Campaign 模块。生产路线仍以 fixed 状态机为主，部分能力处于 shadow、契约或兼容模式。复杂度增长尚未换来同等的生产简化。

### 2.2 真实项目样本

对 `C:/Users/26532/Documents/ArcVellum/Works/兄弟` 的观察值：

- 72 个场景文件；
- 第一场正文尚未晋升前已产生 46 份正式任务合同；
- 历史运行目录 85 个，其中 66 个使用 Pi Worker；
- 52 次完成，约 30 次失败或 core command failed；
- 高成本任务曾携带 60 至 74 个项目 source paths；
- 已记录正式 Prompt 合计约 127 万字符；
- 已准备上下文合计约 403 万字符；
- candidate revision 是最明显的重试和上下文热点。

这些数字包含开发期故障与重复测试，不能等同于理想路径成本；它们仍准确暴露了故障放大率：一次局部失败会触发重新准备上下文、重签证据、重新运行模型和级联过期。

## 3. 问题诊断

### 3.1 四个概念被错误绑定

当前实现容易把以下概念视为一一对应：

```text
文学思考步骤 = workflow state = Agent 调用 = 落盘证据
```

这四者应当分离：

- 文学思考可以在一次创作调用内部完成；
- workflow state 只描述可恢复的业务事务阶段；
- Agent 调用只用于需要语义判断或创作的任务；
- 落盘证据只服务于恢复、正式写回、审计或用户理解。

将每次思考都落成正式产物，会提高成本，却不必然提高文本质量。

### 3.2 门禁粒度过细

当前系统对可逆的中间分析和不可逆的正式写回采用近似相同的严格程度。RP 未完成与 Canon 被错误覆盖都能阻断整条路线，但两者风险完全不同。

合理的风险分层应为：

- **内容建议**：可随时重算，不需要正式批准；
- **候选内容**：需要结构验证，不直接改变项目事实；
- **正式事实**：需要一致性检查、版本和恢复；
- **发布产物**：需要全局审计与用户确认。

### 3.3 模型承担了机器工作

当前任务要求 Agent 同时生成文学内容和大量协议字段。这会产生三类损失：

- Prompt 变长，文学目标被格式说明淹没；
- 模型可能写错摘要、枚举、路径或 session 字段；
- preflight 因机械字段失败后，必须重新调用昂贵模型。

系统已知的 ID、摘要、字数、输入路径和运行身份应在模型返回后由确定性代码注入。

### 3.4 证据新鲜度形成级联失效

内容摘要和时间新鲜度能防止旧证据被错误复用，但当前绑定范围过大。上游任意文件变化都可能使 RP、分支、Composition、Review 和 Revision 依次过期。

v2 应使用字段级或事实分区摘要：

- `creative_inputs_digest`：只覆盖影响正文语义的输入；
- `commit_base_revision`：覆盖正式写回基线；
- `policy_revision`：覆盖门禁策略；
- UI、说明文档、无关资产变化不得使正文事务失效。

### 3.5 自适应编排自身也已过度设计

现有自适应方案原计划在不减少 Gate 的前提下增加 Planner、Reviewer、Normalizer、Compiler、Simulator、Freedom Budget、Context Ledger、Resource Gate 和 Campaign。该方案能增强可审计性，却无法解决“门禁成本高于创作成本”，还可能在固定状态机上方增加第二套形式化流程。

v2 不把完整 CreativeExecutionPlan 设为每场前置条件。默认路径只需要确定性 `ScenePolicy`。复杂 Planner 仅用于整章重规划、重大分支或用户主动请求。

## 4. 文学质量风险

### 4.1 工作表化正文

连续填写角色信念、恐惧、分支评分、读者效果和节拍表，会让模型把显式分析重新讲进正文。人物行为变得可解释，文学中的含混、误读和潜台词反而减少。

### 4.2 每场同构

普通过场、关系余波、高潮和行动场被迫经历同样步骤，容易产生相似的冲突密度、转折强度和结尾钩子。叙事节奏控制因此可能演变成另一种均匀化。

### 4.3 分支最优化导致趋同

每场都生成多个方案并选择综合分最高者，会稳定偏向易解释、易审查、因果明确的路线。冒险、留白和风格化选择在评分机制中处于劣势。

### 4.4 逐场精确字数破坏章节呼吸

字数应当以章节和滚动窗口管理。场景目标适合使用软范围；章节检查点负责偿还字数偏差。只有严重低于最低内容量时才触发场景修订。

### 4.5 重复审查磨平文风

同一模型或同一标准对文本反复执行生成、Review、Revision、Static Review，会促使文本收敛到安全表达。风格 lint 应提供证据，语义编辑应判断是否真的伤害阅读；机械修订不能自动获得最高优先级。

## 5. 设计原则

1. **文学产物优先**：任何门禁都必须说明它保护了哪一种真实损失。
2. **风险决定深度**：低风险场景走短路径，高风险场景按需展开推演和审查。
3. **一次调用完成一个完整语义目的**：禁止为了留下流程痕迹拆分模型调用。
4. **机器管理协议，Agent 管理语义**。
5. **只在不可逆边界形成正式 Gate**。
6. **章节承担跨场景质量控制**。
7. **正文由一个主创 Agent 完成**；只读研究和独立审查允许并行。
8. **上下文即时获取**：Prompt 只携带高信号简报，额外资料通过受控工具按需读取。
9. **恢复以事务为单位**：失败后从最近完整事务阶段恢复，不重跑已经成功的模型调用。
10. **新内核必须减少概念数量、文件数量和状态数量**。

## 6. 目标架构

```text
Frontend / API
       |
       v
Autopilot / Manual Command
       |
       v
SceneTransactionService  <------ ChapterCheckpointService
       |
       +--> SceneBriefBuilder ------> ContextProvider
       +--> ScenePolicy ------------> RiskProfiler
       +--> CreativeRuntime --------> Pi Worker
       +--> VerificationSuite ------> deterministic checks
       +--> ReviewPolicy -----------> CriticRuntime (conditional)
       +--> SceneCommitCoordinator -> Project Repository + SQLite UoW
       +--> EventSink --------------> SSE / Observatory / Orrery
```

### 6.1 Engine 所有权

Embedded Engine 继续拥有：

- 文学领域合同；
- 场景事实读取；
- 风险计算；
- 确定性验证；
- Scene Delta 校验；
- 章节检查合同；
- 写回计划的纯函数构造；
- 兼容旧项目格式的读取适配。

Engine 不调用模型、不启动进程、不写 Studio SQLite、不依赖前端。

### 6.2 Studio 所有权

Studio 继续拥有：

- Pi Worker 和其他 Runtime Adapter；
- 沙箱、进程、取消与超时；
- 事务协调和持久化；
- Autopilot；
- SSE、创作现场与可观察性；
- 用户审批和执行模式。

### 6.3 新的核心服务

首版只新增两个应用服务：

```python
class SceneTransactionService:
    def prepare(self, project_root: Path, scene_id: str) -> PreparedScene: ...
    def create(self, transaction_id: str) -> CreativeRun: ...
    def verify(self, transaction_id: str) -> VerificationReport: ...
    def review_if_required(self, transaction_id: str) -> ReviewResult | None: ...
    def commit(self, transaction_id: str) -> SceneCommit: ...
    def resume(self, transaction_id: str) -> SceneTransaction: ...

class ChapterCheckpointService:
    def evaluate(self, project_root: Path, chapter_id: str) -> ChapterCheckpoint: ...
    def resolve(self, checkpoint_id: str) -> ChapterResolution: ...
```

不新增通用 Workflow Framework、第二套 Task Registry 或第二个 Agent Runtime SPI。

## 7. 场景事务状态机

### 7.1 正式状态

```text
READY
  -> PREPARED
  -> CREATING
  -> VERIFYING
  -> REVIEWING?        # 由策略触发
  -> REVISION_NEEDED?  # 最多一次自动定向修订
  -> COMMITTABLE
  -> COMMITTED

任何阶段均可进入 BLOCKED 或 CANCELLED。
```

界面只展示这些业务状态。Prompt 准备、沙箱复制、completion marker、摘要计算和 CLI 子命令执行属于内部操作，不形成用户可见文学阶段。

### 7.2 场景事务产物

运行期事务产物存放在 Studio 数据目录或 SQLite，不进入作品目录：

```text
<studio-data>/projects/<project-id>/scene-transactions/<transaction-id>/
  scene_brief.json
  creative_result.json
  draft.md
  verification.json
  review.json              # 仅实际调用审查时存在
  revision.md              # 仅实际修订时存在
  scene_delta.json
  commit_manifest.json
```

作品目录只接收已经提交的正文、人物状态、Canon、连续性、handoff，以及一份
`workflow/scene_commits/<scene_id>.json`。运行期草稿、Prompt、完整会话和审查过程不会污染作品目录。

禁止创建 `not_required` 占位文件。策略跳过某个步骤时，只在事务记录和最终 commit manifest
中保存理由。Task Protocol v2 继续作为 Worker 传输格式，但 v2 场景任务由 Studio 签发到沙箱和
事务仓储，不为每个内部操作写一份项目内 task 文件。

### 7.3 SceneBrief

`SceneBrief` 只包含真正影响当前创作的信息：

```json
{
  "scene_id": "scene_0001",
  "objective": "本场必须发生的可观察变化",
  "scene_function": "relationship-turn",
  "participants": ["character/protagonist", "character/mother"],
  "canon_constraints": ["稳定事实或用户锁定约束"],
  "incoming_handoff": ["上一场遗留压力"],
  "chapter_obligations": ["本章需推进的承诺或问题"],
  "rhythm": {"pace": "slow-to-fast", "detail": "selective"},
  "length": {"target_hanzi": 1600, "soft_min": 1200, "soft_max": 2100},
  "style_mount": {"id": "mounted-style", "revision": "..."},
  "risk": {"level": "standard", "reasons": ["relationship-state-change"]},
  "source_refs": ["受控上下文引用"]
}
```

SceneBrief 不复制整份项目手册、任务协议、全部 Canon、全部人物或全部规划产物。

### 7.4 CreativeResult

主创 Agent 只负责：

- 正文；
- 简短创作决策摘要；
- 建议的 `SceneDelta`；
- 新出现的持久人物候选；
- 需要升级审查的风险声明。

RP 和分支过程默认保留在主创会话内部。高风险场景可要求输出简短 `decision_trace`，但它不进入正文，也不构成独立 route。

## 8. 风险驱动门禁

### 8.1 风险等级

沿用现有 `SceneRiskProfile` 的事实来源，将等级语义调整为：

| 等级 | 典型场景 | 正式处理 |
|---|---|---|
| `low` | 过场、位置移动、轻量关系余波 | 一次生成、确定性验证、延迟到章节审查 |
| `standard` | 信息释放、关系变化、普通冲突 | 一次生成、一次独立语义审查、必要时一次修订 |
| `high` | Canon 变化、高潮、重大人物转向、时间线变化 | 显式推演、独立审查、必要的人类或 Steward 批准 |

现有 `compact/standard/deep` 可通过兼容映射过渡，避免一次修改全部存量计划。

### 8.2 风险特征

继续复用并校准：

- Canon 变化；
- 人物长期状态变化；
- 新持久资产；
- 分支歧义；
- 高潮权重；
- 连续性债务；
- 文风新颖度。

新增：

- 用户锁定事实触达；
- 时间线或叙述视角切换；
- 重要承诺兑现；
- 与前文证据冲突；
- 主创主动请求升级。

风险只能决定额外审查，不得要求低风险场景生成空洞的形式化证据。

### 8.3 门禁矩阵

| 能力 | Low | Standard | High |
|---|---:|---:|---:|
| SceneBrief | 必须 | 必须 | 必须 |
| 主创正文 | 必须 | 必须 | 必须 |
| 确定性验证 | 必须 | 必须 | 必须 |
| 独立场景 Review | 延迟到章节 | 一次 | 一次严格 Review |
| 显式 RP/Branch | 主创内部 | 按歧义触发 | 必须输出决策摘要 |
| 自动 Revision | 仅硬错误 | 最多一次 | 最多一次，之后升级 |
| 人类/Steward 审批 | 无 | 通常无 | 仅不可逆高风险变化 |
| 章节检查点 | 必须 | 必须 | 必须 |

## 9. 审查模型

### 9.1 确定性验证只检查可确定事项

- 文件和 schema；
- 中文正文字符数；
- 引号与标点规范；
- 明确禁用表达的模式证据；
- 锁定 Canon 的直接冲突；
- Scene Delta 的引用和目标存在性；
- 写入范围；
- 事务基线 revision；
- 正文非空、非摘要、无流程痕迹。

Lint 输出证据和严重度。除极少数硬错误外，不自动改写正文。

### 9.2 语义审查只检查需要判断的事项

- 人物行为可信度；
- 场景是否产生有效变化；
- 风格是否自然落实；
- 节奏与详略；
- 前后衔接；
- 读者问题和承诺是否得到合理推进；
- Canon 候选是否值得写回。

审查输出只有：`pass`、`revise`、`escalate`。`pass_with_notes` 作为展示信息存在，不阻断提交；确需修改的意见必须归入 `revise` 并指向具体片段。

### 9.3 章节检查点

章节检查点负责当前逐场门禁难以处理的问题：

- 场景功能重复；
- 全章节奏曲线；
- 视角和叙事距离变化；
- 问题与承诺拖延；
- 信息重复；
- 人物状态在多个场景间的连续性；
- 实际字数和后续库存；
- 文风漂移。

章节检查只生成一份问题清单和一个修订计划。轻微问题允许延迟到章末统一处理，避免每场反复抛光。

## 10. 原子写回

### 10.1 SceneDelta

```json
{
  "character_changes": [],
  "canon_candidates": [],
  "continuity_changes": [],
  "promise_updates": [],
  "reader_question_updates": [],
  "next_handoff": [],
  "new_asset_candidates": []
}
```

模型提出语义变化；Engine 校验引用、类型和冲突；Studio 生成正式路径、摘要和事务元数据。

### 10.2 提交协议

复用 `WritebackCoordinator` 与 `sqlite_uow.py`，新增一个场景级提交日志：

```text
PREPARED -> APPLYING -> COMMITTED
                 \-> RECOVERY_REQUIRED
```

提交步骤：

1. 获取项目写锁；
2. 验证 base revision；
3. 把所有目标文件写入事务临时目录；
4. 重新运行确定性验证；
5. 保存 before-image 和 commit manifest；
6. 用可恢复 rename 顺序替换正式文件；
7. 写 SQLite 事务记录和 outbox event；
8. 标记 COMMITTED；
9. 释放锁并投递 SSE。

启动恢复只处理未完成的 commit journal，不重新调用模型。

## 11. 上下文与 Prompt

### 11.1 稳定会话层

每个章节的主创会话持有：

- 主创角色与创作原则；
- 当前挂载文风；
- 项目核心设定摘要；
- 当前章节目标；
- 工具使用约束。

这些内容不在每个场景重复输出。会话在章节检查点后压缩或轮换。

### 11.2 场景任务层

每次仅发送：

- SceneBrief；
- 上一场结尾或 handoff；
- 当前必要人物状态；
- 输出合同；
- 与当前场景相关的审查反馈。

Agent 可通过受控读取工具请求额外 Canon、人物或前文片段。工具返回短摘要和引用，避免复制整个文件树。

### 11.3 机械元数据后置

Prompt 中移除：

- SKILL/AGENTS/CLI 手册全文；
- 全量 source path 清单；
- task lifecycle 教程；
- Agent 无法可靠计算的 hash；
- completion marker 模板；
- Studio 已知的运行信息；
- 与当前任务无关的历史 Review。

### 11.4 上下文预算目标

首轮生产目标：

- 正文生成准备上下文中位数不高于 40,000 字符；
- Review 中位数不高于 24,000 字符；
- Revision 只包含原稿、命中问题、必要约束和局部上下文；
- 同一章节稳定资料使用内容寻址缓存；
- 超预算时优先转换为按需工具引用，不静默删除硬约束。

## 12. 长篇规划收敛

### 12.1 ProjectPlanBundle

把故事架构、字数预算、场景库存和章节义务合并为一个候选包：

```text
规划 Agent 一次生成 ProjectPlanBundle
  -> 确定性预算/引用/库存验证
  -> 一次独立规划 Review
  -> 必要时一次修订
  -> 一次物化
```

内部仍保留结构化字段，以便星仪和后续场景读取；这些字段不再分别形成 Agent 生命周期。

### 12.2 滚动规划

全书只建立足以验证体量的宏观库存。细化保持 2 至 4 个场景的滚动窗口。章节检查点根据真实正文调整后续字数、节奏和事件库存。

## 13. 资产策略

### 13.1 人物

- 主要角色和跨多场景持续人物需要正式资产；
- 临时路人可先进入 SceneDelta 的 `new_asset_candidates`；
- 连续出现、获得稳定身份或影响 Canon 时再晋升；
- 不因场景 YAML 出现一个名字就阻断正文。

### 13.2 Canon

- 已确认 Canon 和用户锁定事实保持严格；
- 新推断默认进入候选；
- 低风险补充可在场景事务中自动提交为带来源候选；
- 改变既有规则、时间线或核心关系时升级审批。

### 13.3 连续性账本

连续性更新合并进 SceneDelta。独立 ledger Review 只在证据冲突、重要承诺关闭或高风险时间线变化时触发。章节检查点负责整体逾期和遗漏审计。

## 14. 执行模式

| 模式 | 行为 | 主要用途 |
|---|---|---|
| `draft` | 每场一次主创调用，章节统一 Review | 探索、快速形成完整初稿 |
| `standard` | 风险驱动场景 Review，章节检查点 | 默认模式 |
| `publication` | 高风险场景展开推演，章卷双重审查 | 定稿与发布 |
| `strict-v1` | 保留当前完整固定路线 | 兼容、审计与回退 |

模式改变审查深度，不改变项目事实保护和沙箱安全。

## 15. 并发原则

首版只允许：

- 不同未来场景的只读资料整理；
- 确定性 lint；
- 独立审查；
- 章节级统计与索引更新。

正文仍由单一主创会话按叙事顺序生成。任何正式 SceneDelta 提交串行执行。已有 Resource Gate 和 lease 可以复用，无需增加新调度器。

## 16. 可观察性

前端只展示能够帮助用户理解作品推进的事件：

- 正在准备哪一场；
- 主创正在生成或修订；
- 发现了哪些具体问题；
- 当前是否需要用户决定；
- 本场为作品增加了什么；
- 本章进度、字数、节奏和承诺变化。

沙箱复制、摘要计算、marker 写入等机械事件进入可展开技术日志，不占据创作现场主视图。

星仪仍可展示 RP、分支、审查和状态节点，但这些节点由 `SceneTransaction` 投影生成。视觉节点不再要求后台存在同数量的正式任务和 sidecar。

## 17. 现有模块处置

### 17.1 直接复用

- `literary/scene/facts.py`；
- `literary/planning/narrative_rhythm.py`；
- `literary/style/*` 的挂载、编译、标点与 lint；
- `runtime/worker.py` 与 Pi Worker Adapter；
- `runtime/sandbox*`；
- `runtime/context_*` 中已验证的预算、缓存和按需读取能力；
- `runtime/worker_writeback.py`；
- `persistence/sqlite_uow.py`；
- `automation/no_progress.py`；
- `observability/creative_live/*`；
- 现有项目文件格式与导出模块。

### 17.2 降级为按需能力

- RP Lab；
- Branch Simulation；
- Composition beat planner；
- Reader Experience 场景合同；
- Scene AgentReview；
- Canon/State/Continuity 独立语义审查。

这些模块继续提供纯函数、Prompt 片段或高风险工具，不再分别拥有默认 route state。

### 17.3 迁移期兼容

- `workflow/state_scene.py`；
- `routes/scene/blueprints.py`；
- `routes/scene/gates.py`；
- Task Protocol v2；
- 历史 sidecar 解析；
- `strict-v1` CLI 命令。

### 17.4 冻结并评估删除

对 `orchestration/` 执行消费者审计：

- 优先保留 `risk.py`、`rolling_horizon.py`、`resource_gate.py`、`checkpoint.py` 和必要 settings；
- Planner、Reviewer、Normalizer、Compiler、Simulator、Constitution、Default Plan、Shadow 管线若没有生产消费者，不接入 v2 默认路线；
- v2 稳定两个发行周期后，删除零消费者和纯 shadow 模块；
- 不把这些模块再包装一层后继续保留。

## 18. 建议代码布局

仅新增以下必要模块：

```text
src/literary_engineering_studio_engine/literary/scene/transaction/
  contracts.py       # DTO、Enum、SceneDelta、VerificationReport
  brief.py           # SceneBrief 纯构建逻辑
  policy.py          # 风险到执行策略映射
  verification.py    # 确定性文学/协议验证
  commit_plan.py     # 纯写回计划

src/literary_engineering_studio/application/
  scene_transaction.py
  chapter_checkpoint.py

src/literary_engineering_studio/persistence/
  scene_transactions.py

src/literary_engineering_studio/automation/
  scene_transaction_loop.py
```

以下能力继续通过已有模块提供，不创建 v2 副本：

- Runtime 选择；
- Prompt 编译；
- Context Budget；
- 沙箱；
- 写回协调；
- SSE；
- 资源锁；
- 资产仓储；
- 文风和导出。

## 19. 关键接口

```python
class CreativeRuntime(Protocol):
    def create_scene(self, brief: SceneBrief, context: ContextHandle) -> CreativeResult: ...

class CriticRuntime(Protocol):
    def review_scene(self, packet: ReviewPacket) -> ReviewResult: ...

class SceneTransactionRepository(Protocol):
    def load(self, transaction_id: str) -> SceneTransaction: ...
    def save(self, transaction: SceneTransaction) -> None: ...

class ProjectCommitPort(Protocol):
    def apply_scene_commit(self, commit: SceneCommitPlan) -> SceneCommitReceipt: ...

class TransactionEventSink(Protocol):
    def emit(self, event: SceneTransactionEvent) -> None: ...
```

Pi Worker 适配 `CreativeRuntime` 和 `CriticRuntime`。领域层不感知 RPC、API Key、模型厂商或进程。

## 20. 错误模型

统一分为：

- `TransientRuntimeFailure`：网络、限流、流中断，可有限重试；
- `InvalidCreativeOutput`：正文或 SceneDelta 不合格，局部 repair；
- `PolicyEscalation`：风险升高，需要额外 Review 或决定；
- `StaleTransaction`：正式事实基线变化，重新 prepare；
- `CommitFailure`：进入事务恢复，不重跑模型；
- `ConfigurationFailure`：立即停止并给出用户可操作信息；
- `InternalDefect`：禁止自动无限重试，保留诊断包。

同一错误最多经历一次同策略重试。再次发生必须改变策略或终止，防止 no-progress 空转。

## 21. 迁移策略

采用旁路替换：

### K0：冻结基线

- 固定 `strict-v1` 当前行为和关键 E2E fixture；
- 记录调用数、输入输出 Token、耗时、失败、人工干预和文学评分；
- 给现有状态与产物建立兼容读取测试；
- 暂停继续增加 fixed route Gate。

### K1：建立纯领域事务合同

- 实现 SceneBrief、ScenePolicy、CreativeResult、SceneDelta、VerificationReport；
- 复用现有 SceneFacts、Style、Rhythm 和 Word Budget；
- 全部为无 I/O 纯逻辑；
- 不接入生产 Controller。

### K2：实现事务服务与确定性假 Runtime

- 实现 prepare/create/verify/commit；
- 使用 fake CreativeRuntime 完成模型无关 E2E；
- 注入每个阶段故障，验证恢复不会重复写回或重跑已完成调用。

### K3：接入 Pi Worker

- 新增简短 scene prompt recipe；
- 让 Pi 返回正文和 SceneDelta；
- 机器后置补全元数据；
- 完成真实单场 `standard` 闭环。

### K4：章节检查点与规划合并

- 合并 ProjectPlanBundle；
- 完成一个三场景章节；
- 验证节奏、承诺、字数和连续性在章节级闭环。

### K5：双路线 A/B

- 同一模型、同一项目约束、同类场景分别运行 strict-v1 和 v2；
- 比较成本、耗时、失败率、文学质量和 Canon 回归；
- v2 未达到非劣文学质量前保持可选。

### K6：默认切换与兼容收敛

- `standard` 成为新项目默认；
- 旧项目可继续 strict-v1 或迁移；
- 星仪和创作现场切换到事务投影；
- 两个发行周期后删除零消费者 compatibility/shadow 代码。

### 21.1 分批文件变更边界

| 批次 | 新增或主要修改 | 明确禁止混入 |
|---|---|---|
| K0 | 本文、基线量测 fixture、strict-v1 characterization tests | 生产行为、Prompt、Gate 顺序 |
| K1 | `engine/literary/scene/transaction/*`、对应纯领域测试 | Studio、Worker、API、前端 |
| K2 | `application/scene_transaction.py`、`persistence/scene_transactions.py`、fake runtime E2E | 真实模型、旧 route 删除、UI |
| K3 | `runtime/worker_execution_profile.py`、`runtime/prompt_recipes.py`、Pi Worker 的结构化文学输出适配 | Autopilot 默认切换、章节规划 |
| K4 | `application/chapter_checkpoint.py`、既有 planning/rhythm/continuity 的聚合适配 | 新规划框架、自由 DAG |
| K5 | `automation/controller.py`、`automation/run_loop.py`、API read model、SSE、前端事务投影 | 旧代码删除、无关视觉重构 |
| K6 | compatibility manifest、模块目录、零消费者删除和迁移工具 | 新功能 |

每批必须先写 change packet，记录输入合同、输出合同、允许依赖、回滚点和测试；一批只改变一个
生产语义。K1 至 K4 期间，`workflow/state_scene.py` 和 `routes/scene/*` 的 strict-v1 行为冻结。

### 21.2 生产接线路径

v2 不要求 Engine Task Registry 先展开三十个工作项。Studio 创建一条场景事务后，只在需要模型时
签发粗粒度 Task Protocol v2 包：

```text
scene.create       # 必须，一次主创调用
scene.review       # 按风险，可选
scene.revise       # 按验证结果，可选且最多一次
```

确定性 prepare、verify、commit 由应用服务直接调用 Engine 纯函数，不伪装成 Agent task。
Autopilot 每轮推进一个事务状态；事务完成才移动到下一场。CLI 为调试与自动化暴露
`scene-transaction prepare/run/status/resume`，前端仍通过 Studio API 使用同一个应用服务。

## 22. 测试与首次质量策略

“首次无 bug”无法通过架构文档绝对保证。可执行目标是：让第一次生产接线在受控测试中暴露问题，而不影响现有用户项目。

### 22.1 Characterization

- strict-v1 的任务选择、提交、promotion 和恢复保持不变；
- 旧项目可读取、导出和继续运行；
- v2 不写旧 sidecar 来伪装兼容。

### 22.2 单元测试

- 风险映射表；
- SceneBrief 最小资料合同；
- 软字数范围；
- SceneDelta 引用、冲突和幂等性；
- ReviewPolicy；
- commit plan；
- stale revision；
- 错误分类和 retry budget。

### 22.3 属性与组合测试

- 任意合法 SceneDelta 重复提交不会产生第二次变化；
- 任意失败点恢复后最终状态等价于一次成功提交；
- UI/文档变化不会使 creative digest 失效；
- 机器元数据错误不能触发模型重写；
- Low 风险路径不会隐式创建 Review 占位文件；
- High 风险路径无法绕过正式事实保护。

### 22.4 E2E

1. 低风险过场一次调用完成；
2. 标准关系场经过一次审查；
3. 高风险 Canon 场升级审批；
4. Revision 一次成功；
5. Revision 二次失败后停止；
6. 模型中断后续跑；
7. Commit 中断后恢复；
8. 三场景章节检查；
9. 桌面端暂停、重启、继续；
10. 真实 Pi Worker 全自动路径。

### 22.5 文学验收

建立多题材盲评样本：过场、对话、动作、情绪、信息反转、高潮、余波。评估：

- 人物行为可信度；
- 场景功能；
- 文风辨识度；
- 含混与潜台词；
- 节奏；
- 衔接；
- 读者问题管理；
- Canon 与连续性错误。

文学质量必须至少与 strict-v1 持平；流程合规分不参与文学总分。

## 23. 量化退出门槛

以真实项目的中位数和 P95 统计：

- `standard` 每场 Agent 调用中位数不超过 2，P95 不超过 3；
- `draft` 每场调用中位数接近 1；
- 第一场正文前正式任务数量下降至少 70%；
- 每千个交付汉字的输入 Token 下降至少 60%；
- 模型首次输出通过确定性预检比例不低于 95%；
- 因机器元数据导致的模型重试为 0；
- 无进展重复任务为 0；
- Commit 恢复不重复调用模型；
- Canon/状态回归率不高于 strict-v1；
- 文学盲评达到非劣，并在自然度或节奏上至少一项提高；
- 新内核新增生产模块不超过本设计列出的范围；
- v2 上线后代码净增长必须由已删除或退役的旧代码抵消。

## 24. 明确拒绝的方案

- 在当前 fixed route 上继续增加豁免参数；
- 再建一套通用 DAG 框架；
- 把现有全部 Orchestration 模块接入每场生产路径；
- 用更多 Subagent 弥补过长流程；
- 让模型生成或修复机器元数据；
- 为跳过的步骤创建 `not_required` sidecar；
- 取消全部审查和 Canon 保护；
- 一次删除 strict-v1；
- 先改前端表现，再处理内核成本；
- 以测试数量或 Gate 数量作为文学可靠性的替代指标。

## 25. 外部实践校准

本设计借鉴原则，不引入对应框架依赖：

- Anthropic 建议从最简单可行方案开始，仅在复杂度能够证明改善结果时增加 Agent 结构；同时强调透明计划和工具接口质量：
  <https://www.anthropic.com/engineering/building-effective-agents>
- Anthropic 的 Context Engineering 建议使用即时取回，让工具返回高信号资料并鼓励高效行为：
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>
- OpenAI 的 Agent 指南建议依据风险和失败阈值触发人工介入，并可让 guardrail 与主执行并行：
  <https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/>
- LangGraph 的 durable execution 文档强调可序列化状态、幂等任务、隔离副作用和从检查点恢复；ArcVellum 复用这些原则，不因此引入 LangGraph：
  <https://docs.langchain.com/oss/python/langgraph/functional-api>
- Unit of Work 模式用于聚合一个业务事务中的变化并协调写入，支持 SceneDelta 的场景级原子提交：
  <https://martinfowler.com/eaaCatalog/unitOfWork.html>

## 26. 实施前必须回答的问题

进入 K1 前必须用代码和真实项目数据确认：

1. strict-v1 在无故障理想路径中每场真实 Agent 调用数；
2. 哪些 existing preflight 可直接作用于 CreativeResult；
3. Context Packet 中每类资料的命中率；
4. 当前 Pi Worker 是否能在一个结构化响应中稳定返回正文和 SceneDelta；
5. 哪些前端节点直接依赖历史 sidecar 文件；
6. SQLite 与项目文件提交的现有恢复能力可复用到什么程度；
7. `SceneRiskProfile` 当前阈值是否能从真实项目事实稳定推导；
8. strict-v1 的哪些用户正在依赖逐步骤人工控制；
9. 旧任务协议中哪些字段仍有真实消费者；
10. Orchestration 五十余模块各自是否存在生产调用方。

这些问题由 K0 产出机器可读基线，不通过假设回答。

## 27. 最终架构判断

ArcVellum 无需放弃文学工程，也无需放弃可靠性。需要改变的是工程约束落点：

- 创作过程允许集中、灵活和可逆；
- 正式写回保持严格、可审计和可恢复；
- 局部质量由风险驱动审查；
- 长篇质量由章节和卷级检查点承担；
- 机器协议退出模型上下文；
- 视觉投影不再决定后台任务数量。

新内核的成功形态可以概括为：

> 一次完整创作事务产生一段正文和一组可验证变化；系统把复杂度留在真正需要保护的提交边界，把模型时间留给文学。

## 28. K0-K6 实施结论

截至 2026-09-08，本设计的 K0-K6 代码路线已经完成：

- K0 固化 strict-v1 特征基线和成本量测；
- K1 建立 Engine 纯领域场景事务合同；
- K2 完成可恢复应用服务、SQLite 仓储和原子提交；
- K3 通过紧凑 Prompt 接入 Pi Worker 创作、审查与一次定向修订；
- K4 完成章节级节奏、字数、连续性与问题检查点；
- K5 接入真实项目事实、Autopilot、SSE/创作现场投影并形成结构 A/B；
- K6 完成显式迁移、回滚、CLI/API/前端兼容面和退役观察清单。

结构 A/B 已达到每场 Agent 调用 `8 -> 2`、用户可见状态 `31 -> 5`、项目内
Agent task 文件 `8 -> 0`。当前尚无合格的同模型文学盲评 scorecard，因此
`lean-v2` 保持 preview，兼容清单继续推荐 `strict-v1`。这是一项有意保留的
质量门槛，不属于实现缺口。

详细验证和已知边界见
`docs/verification/lean-kernel-v2-k0-k6-delivery-2026-09-08.md`。
