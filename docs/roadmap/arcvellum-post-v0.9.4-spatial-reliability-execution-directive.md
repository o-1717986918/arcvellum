# ArcVellum post-v0.9.4 空间可靠性与创作可观测性执行指令

> 状态：已完成实施与验收。验证记录见
> `docs/releases/post-v0.9.4-spatial-reliability-verification.md`。
>
> 基线版本：`0.9.4`。
>
> 文档性质：强指导性执行文件。本文规定下一轮开发的实施顺序、禁止事项、产物、测试和退出门禁。后续 Agent 不得将本文降级为灵感清单，也不得在未满足当前批次退出门禁时提前进入后续批次。
>
> 与既有文档的关系：`arcvellum-v0.9-spatial-orrery-and-creative-observability-plan.md` 继续承担产品愿景和视觉方向说明；本文承担实际实施约束。发生冲突时，涉及实施顺序、可靠性门禁和验收证据的事项以本文为准。

## 1. 本轮必须解决的问题

本轮开发必须完整解决以下问题，不得遗漏或以纯视觉隐藏代替真实修复：

1. 星图视角移动时不得发生突兀的 Z 轴反转或控制方向翻转。
2. 视角旋转不得存在人为角度上限。
3. 必须恢复历史版本中更有节奏感的优秀主曲线，但不得恢复旧版的拥挤、折返和碰撞问题。
4. 默认观测视角和观测时间必须与主曲线解耦。
5. 已完成、当前、未完成和阻塞章节及曲线必须具有清楚的视觉差异，优先采用亮暗关系。
6. 规则窗口必须适配空间仪表尺寸，不能继续把完整规则页面直接塞入小窗口。
7. Agent 任务窗口必须显示所有真实 Agent 会话，而不是只显示一个自动创作 run。
8. 人工决策必须形成“提交、落库、消费、卡片消失、流程继续”的可验证闭环。
9. 档案正文必须安全渲染 Markdown。
10. 自动创作必须能够识别无错误但无进展的空转，并在恢复失败后主动暂停。

## 2. 已确认的代码事实

以下结论来自当前仓库，不得在实施时重新假设相反事实：

- `client/src/features/orrery/engine/parallaxProjection.ts` 仍使用受限 `yaw/pitch`，存在 `MAX_YAW` 和 `MAX_PITCH`。
- `client/src/stores/spatialProjection.ts` 只维护 `level/focus/grammar`，没有独立观测时间状态。
- `client/src/features/orrery/layout/layoutEngine.ts` 同时承担曲线公式、章节簇定位和局部布局，调整成本过高。
- `src/literary_engineering_studio/agent_observability.py` 只把整个自动创作 run 投影为一个会话。
- `client/src/features/orrery/SpatialWindowLayer.vue` 只渲染 `sessions[0]`。
- `src/literary_engineering_studio/opencode_runtime_pool.py` 已具备 `worker/advisor/steward` 三类常驻服务状态，不需要另造 runtime 管理器。
- `client/src/features/workflow/OverviewView.vue` 与 `OrreryWorkbench.vue` 分别维护人工选择状态。
- `record_human_choice()` 对重复 `choice_id` 创建带时间戳副本，不具备严格幂等性。
- `client/src/components/SafeMarkdown.vue` 已存在并执行安全净化，不需要另造 Markdown 引擎。
- `src/literary_engineering_studio/autopilot.py` 已有租约、项目互斥锁、失败次数限制和人工等待，但没有正式的无进展检测。
- 当前工作树存在与本轮开发无关的日志文件。实施过程中必须精确暂存文件，禁止使用 `git add .`。

## 3. 总体执行原则

### 3.1 必须遵守

1. MUST 先修后端事实，再修前端表现。
2. MUST 先写或更新测试，再宣布一个闭环完成。
3. MUST 让每个批次形成可独立回滚的提交。
4. MUST 使用“你好新世界”作为长篇视觉验收项目。
5. MUST 同时验证 WebGL 正式渲染和静态降级渲染。
6. MUST 保持现有 CLI 状态机、任务包、审查、晋升和写回门禁。
7. MUST 使用服务端回执判断选择是否完成。
8. MUST 使用正式状态摘要判断自动创作是否推进。
9. MUST 保留全书节点；观测时间只改变聚焦、明暗、LOD 和镜头，不得通过隐藏节点伪造清晰度。

### 3.2 严禁采用

1. MUST NOT 只删除角度 clamp 后继续使用原 Euler 角实现。
2. MUST NOT 用 CSS 隐藏仍未被后端消费的决策卡。
3. MUST NOT 直接 `git checkout` 历史版本的整个 `layoutEngine.ts`。
4. MUST NOT 让前端自行猜测一个章节是否完成。
5. MUST NOT 把自动创作 run、OpenCode 服务进程和真实 LLM 会话混为同一个概念。
6. MUST NOT 在 Agent 面板暴露隐藏推理、完整系统提示词、API Key、服务密码或敏感绝对路径。
7. MUST NOT 以“Worker 返回 complete”代替正式推进证据。
8. MUST NOT 在未完成浏览器视觉验收时打包桌面安装程序。

## 4. 唯一允许的实施顺序

```text
Batch 0  冻结基线
   ↓
Batch 1  数据契约与数据库迁移
   ↓
Batch 2  人工决策闭环
   ↓
Batch 3  自动创作防空转
   ↓
Batch 4  无限制相机数学
   ↓
Batch 5  时间观测与主曲线恢复
   ↓
Batch 6  完成状态视觉
   ↓
Batch 7  Agent / 规则 / 档案面板
   ↓
Batch 8  全量验收、构建与发布准备
```

除紧急编译修复外，不得跨批次混写。任何批次退出门禁失败时，必须停留在当前批次。

## 5. Batch 0：冻结基线

### 5.1 必做事项

1. 创建独立开发分支，例如 `feat/spatial-observability-stability`。
2. 运行 Python、Vitest 和客户端构建。
3. 保存“你好新世界”在六种空间构型、当前默认视角和三个常见分辨率下的基线截图。
4. 提取以下版本的曲线实现作为只读比较材料：
   - `8b7db62`
   - `b96be42`
   - 当前 HEAD
5. 记录当前人工选择、Agent 会话和自动创作状态的 API 样例。

### 5.2 基线命令

```powershell
python -m unittest discover -s tests -v
npm run client:test
npm run client:build
```

### 5.3 退出门禁

- 三组命令全部通过，或已有失败被明确记录为基线问题。
- 基线截图和曲线差异能够被后续 A/B 使用。
- 没有把无关日志加入 Git。

## 6. Batch 1：数据契约与数据库迁移

### 6.1 必须建立的契约

#### HumanChoiceReceipt v0.2

至少包含：

```json
{
  "receipt_id": "",
  "choice_id": "",
  "selected": "",
  "recorded": true,
  "materialized": true,
  "consumed": true,
  "effect": {},
  "state_before": {},
  "state_after": {}
}
```

#### AgentObservability v2

必须区分：

- controller：自动创作控制器；
- service：OpenCode 的 worker/advisor/steward 常驻服务；
- session：一次真实 Agent 会话；
- task：状态机当前正式任务；
- event：用户可见的运行事件。

#### AutopilotProgressState

至少包含：

- `route_index`
- `progress_fingerprint`
- `stalled_cycles`
- `last_progress_at`
- `last_recovery_at`

#### NodeCompletionState

值域固定为：

```text
completed
active
planned
blocked
```

#### SpatialViewState

至少包含：

- 无限制相机方向；
- 缩放；
- 平移；
- 观测时间游标；
- 观测窗口；
- 镜头预设。

### 6.2 数据库要求

必须在现有 `JobStore` 中完成一次向后兼容迁移：

1. 为 `autopilot_runs` 增加推进状态字段。
2. 增加 `agent_sessions` 表。
3. 提供 upsert、结束、查询当前项目会话的方法。
4. 旧数据库打开时自动补列和建表。
5. 不得要求用户删除应用数据或重新创建文学项目。

### 6.3 退出门禁

- 旧数据库迁移测试通过。
- 新旧 API 字段兼容。
- TypeScript 类型检查通过。
- 尚未改视觉时，客户端仍可正常启动。

## 7. Batch 2：人工决策闭环

### 7.1 后端实现

1. `record_human_choice()` 必须按原始 `choice_id` 幂等。
2. 相同选择重复提交必须返回原回执。
3. 同一选择提交不同选项时必须返回明确冲突，不能创建时间戳副本。
4. `build_current_human_choices()` 必须排除已被正式消费的选择。
5. `/workflow/human-choice` 必须返回 `HumanChoiceReceipt v0.2`。
6. `human.choice_recorded` 事件必须携带 `consumed` 和效果摘要。
7. 自动创作若只因该选择暂停，且授权仍有效，消费后必须重新审计并恢复。

### 7.2 前端实现

1. 新建唯一的 `humanChoices` Pinia store。
2. 删除 Overview 与 Orrery 各自独立的选择源。
3. 所有决策卡必须使用 `choice_id` 作为稳定身份。
4. 提交时进入 `submitting`。
5. 回执 `consumed=true` 后进入短暂 `resolved`，随后关闭弹窗并移除卡片。
6. `consumed=false` 时卡片不得消失，必须解释仍缺什么。
7. 所有页面必须响应 `human.choice_recorded` 事件。

### 7.3 必测闭环

```text
打开决策卡
→ 选择选项
→ 后端落库
→ 正式效果写入
→ 服务端确认消费
→ 所有决策视图移除同一卡片
→ 刷新后不复现
→ 等待该决定的自动创作继续
```

### 7.4 退出门禁

- 重复点击不会生成重复正式记录。
- 选择失败时不会误删卡片。
- 星仪和普通总控状态一致。
- 自动创作等待态能够被解除。

## 8. Batch 3：自动创作防空转

### 8.1 推进指纹

每轮 Worker 执行前后必须计算正式推进指纹，至少覆盖：

```text
current route
current task id
route-audit digest
gate state
pending choice ids
formal output digests
workflow dashboard revision
```

### 8.2 停滞规则

1. Worker 返回 `complete` 但指纹不变：不得增加已完成任务数。
2. 连续两次无变化：发布 `autopilot.progress_slow`。
3. 连续三次无变化：执行一次受控恢复。
4. 恢复后仍无变化：暂停为 `no-progress`。
5. 资产依赖路线反复 `route_ready` 但依赖仍存在：判定依赖循环。
6. `route_ready` 必须由最新 route-audit 复核。
7. 长时间无 Worker 心跳：检查 runtime，最多自动重启一次。

### 8.3 启动预检

自动创作启动前必须确认：

- 项目可读；
- 场景库存可机器读取；
- 当前路线可解析；
- runtime 与模型可用；
- 授权仍有效；
- 待决策可以被用户或授权的 Steward 处理；
- 不存在已经确定的依赖死循环。

预检失败时不得启动一个表面为 running 的 run。

### 8.4 退出门禁

- 假 `complete` 不会制造虚假进度。
- 依赖循环会被识别。
- 应用重启后仍保留路线游标和停滞计数。
- 前端能显示最后有效推进时间和停滞原因。

## 9. Batch 4：无限制相机数学

### 9.1 实现约束

1. 使用四元数、旋转矩阵或虚拟轨迹球，不再使用受限 Euler 角作为正式状态。
2. 删除视觉角度上限，仅允许为数值稳定进行周期归一化。
3. 中键拖动必须相对于屏幕空间轴计算。
4. 平移、缩放、旋转必须互不污染。
5. 旋转时当前世界枢轴必须稳定。
6. 深度排序必须连续变化。
7. WebGL 与静态降级模式必须共享同一相机核心。

### 9.2 默认视角

必须提供：

- 推荐斜向视角；
- 正视视角；
- 当前章节聚焦视角。

“复位”默认回到推荐斜向视角。推荐参数必须由“你好新世界”的实际截图验收确定，不得仅凭代码猜测。

### 9.3 数学测试

- 水平拖动方向稳定。
- 竖直拖动方向稳定。
- 连续旋转多圈无角度限制。
- 穿越原极点无控制方向突变。
- 旋转前后枢轴屏幕位置稳定。
- 极端输入无 NaN、Infinity 和节点瞬移。

### 9.4 退出门禁

- 自动数学测试通过。
- 鼠标中键实际交互通过。
- 正式渲染与降级渲染手感一致。
- 未开始调整主曲线。

## 10. Batch 5：时间观测与主曲线恢复

### 10.1 先拆责任

必须将当前布局职责拆为：

```text
NarrativeGeometry
  负责作品节点在世界中的稳定位置

ObservationWindow
  负责观测时点、强调范围和 LOD

CameraFraming
  负责镜头中心、缩放和过渡
```

### 10.2 曲线恢复方法

1. 将曲线公式从 `layoutEngine.ts` 提取到 `curveProfiles.ts`。
2. 以 `8b7db62` 的回环和舞台函数作为第一候选。
3. 保留当前时间间距、章节簇、关系锚点和碰撞松弛。
4. 不得恢复旧文件整体。
5. 开发阶段允许内部 A/B 开关比较候选。
6. 正式构建不得保留难以解释的调试入口。

### 10.3 观测时间

1. 增加独立 `timeCursor` 和 `timeWindow`。
2. 时间切换不得删除全书节点。
3. 时间切换只控制镜头、明暗、LOD 和关系权重。
4. 默认观测时点应接近当前正式创作进度。
5. 章节、场景视图仍然是全书视图，只提高相应粒度。

### 10.4 视觉比较集

必须比较：

- 3 章短项目；
- “你好新世界”；
- 20 章项目；
- 70 章以上长项目；
- 回环、舞台、脊柱、编织、层室、星簇六种构型。

### 10.5 退出门禁

- 曲线恢复后不重新引入节点碰撞。
- 默认观测时间不再造成曲线“看似过密”。
- 时间切换不改变节点世界坐标。
- 主曲线具备呼吸感，但不绕圈和折返。

## 11. Batch 6：完成状态视觉

### 11.1 状态来源

完成状态必须由后端 Narrative Projection 计算：

- 场景：根据审查、晋升、正式草稿和阻塞门禁。
- 章节：根据所属场景及章节级义务聚合。
- 当前：根据正式工作流当前目标。
- 阻塞：根据 route gate 与可操作阻塞原因。

前端不得通过“存在一个 formal 场景”猜测整章完成。

### 11.2 视觉规则

| 状态 | 节点 | 主曲线 |
|---|---|---|
| completed | 明亮稳定核心、清晰轮廓 | 高亮稳定 |
| active | 最高亮度、轻微呼吸 | 活跃信号 |
| planned | 较暗但清楚可读 | 低亮度连续线 |
| blocked | 暗底、暖色边缘 | 暖色断续提示 |

亮暗是主要编码，但必须辅以轮廓或线型，满足可访问性。

### 11.3 曲线拆分

现有单条章节主曲线必须拆为可单独着色的章节区间。人物高亮、章节聚焦和完成状态必须可以叠加，不能通过覆盖 class 互相排斥。

### 11.4 退出门禁

- 不看文字也能区分完成、当前和未来。
- 所有主题下语义一致。
- 聚焦人物或章节时，完成状态仍可辨认。
- 远景不会因暗化而丢失全部未来结构。

## 12. Batch 7：Agent、规则与档案面板

### 12.1 Agent 会话中心

必须在以下创建和结束位置登记真实会话：

- Worker OpenCode session；
- Advisor remote session；
- Steward decision session。

Agent 观测界面必须分别展示：

- 自动创作控制器状态；
- OpenCode 常驻服务健康；
- 每一个真实 Agent 会话；
- 当前正式任务；
- 用户可见事件时间线。

每张会话卡至少包含：

- 角色；
- 公开会话短 ID；
- 模型；
- 当前任务或动作；
- 状态；
- 启动时间和耗时；
- 最近活动；
- 重试次数；
- 等待或失败原因。

状态灯只允许对应真实状态：运行、排队、等待用户、空闲、失败、结束。禁止无意义常亮或装饰性闪烁。

### 12.2 规则仪表

1. 提取共享 `useQualityProfile`。
2. 新建 `RulesInstrument.vue`。
3. 不再在空间窗口中直接嵌套完整 `QualityView`。
4. 保留节奏、语言、预览、逐条规则四个紧凑标签。
5. 使用容器查询适配窗口宽度。
6. 内容区内部滚动，底部保存栏固定。
7. 必须提供加载、空数据、脏状态、保存中、成功和失败表现。

### 12.3 档案 Markdown

1. `LibraryView` 必须复用 `SafeMarkdown`。
2. 支持标题、段落、列表、引用、表格、链接和代码块。
3. 必须继续经过 DOMPurify。
4. 表格必须横向滚动。
5. 长文必须使用适合阅读的行宽、行高和段距。
6. 搜索索引使用纯文本，不使用渲染后的 HTML。

### 12.4 退出门禁

- 同时运行 Worker、Advisor、Steward 时出现三张真实会话卡。
- 结束后会话状态正确归档。
- 规则窗口缩放后不变形、不溢出。
- Markdown 恶意 HTML 测试通过。

## 13. Batch 8：全量验收与发布准备

### 13.1 自动测试

```powershell
python -m unittest discover -s tests -v
npm run client:test
npm run client:build
```

### 13.2 必做集成场景

1. 决策提交、消费、移除、刷新不复现、自动创作恢复。
2. Worker 返回假 `complete`，系统识别无进展。
3. 资产依赖循环，系统停止空转。
4. Worker、Advisor、Steward 同时活动。
5. 无限旋转、平移、缩放、聚焦和复位。
6. 时间切换后全书节点仍存在。
7. 已完成和未完成章节在所有主题下清楚可辨。
8. 规则窗口在最小和最大尺寸下可用。
9. 档案 Markdown 安全渲染。

### 13.3 视觉验收

必须使用“你好新世界”在以下视口检查：

- `1366×768`
- `1920×1080`
- `2560×1440`

每个视口必须检查：

- 默认视角；
- 六种构型；
- 章节、场景和全书粒度；
- 完成状态；
- 多窗口；
- Agent 会话面板；
- 决策卡；
- 规则窗口；
- 所有正式主题；
- `prefers-reduced-motion`。

视觉验收必须依靠实际截图和交互，不得只读 CSS 或单元测试。

### 13.4 桌面构建

只有前述门禁全部通过后才允许执行：

```powershell
npm run desktop:build
```

桌面构建完成后还必须验证：

- 安装；
- 首次启动；
- 旧数据迁移；
- 项目打开；
- OpenCode runtime；
- 自动创作；
- 更新检查；
- 卸载与重新安装。

## 14. 提交纪律

建议提交序列：

```text
contracts: add durable choice session and progress contracts
fix: close human choice loop and prevent autopilot stalls
feat: replace bounded Euler camera with unrestricted orbit
feat: restore expressive narrative curves with temporal framing
feat: add completion lighting and multi-agent observability
feat: redesign rules and archive instruments
test: complete post-v0.9.4 visual and workflow acceptance
```

每次提交前必须执行与修改范围相符的最小测试。Batch 8 再执行全量测试。禁止把数据库迁移、相机重构、曲线调整和窗口样式压进同一个不可回滚提交。

## 15. 完成定义

本轮只有在以下条件全部成立时才算完成：

- 相机可无限旋转，且没有突兀 Z 轴或控制方向反转。
- 推荐默认视角经过实际长篇项目验收。
- 历史优秀曲线恢复，但没有恢复拥挤与折返。
- 时间观测与曲线几何已经解耦。
- 完成、当前、未来和阻塞状态清楚可辨。
- 规则窗口适配空间仪表尺寸。
- 所有真实 Agent 会话均可观察。
- 决策卡形成正式后端闭环，不再持续骚扰。
- 档案支持安全 Markdown。
- 自动创作可识别空转并给出可操作诊断。
- Python、Vitest、客户端构建和桌面构建全部通过。
- “你好新世界”完成多视口、多主题、六构型实际视觉验收。

任何一项未满足时，文档状态不得改为“已完成”，也不得仅凭版本号、提交记录或安装包存在宣称交付。

## 16. 后续 Agent 开工回执

承担实施的 Agent 在开始修改前必须输出并遵守以下回执：

```text
已读取本执行指令。
当前批次：
允许修改的模块：
本批次明确不修改的模块：
预计新增或更新的测试：
退出门禁：
```

每个批次结束后必须报告：

```text
本批次完成内容：
实际修改文件：
测试结果：
尚未满足的门禁：
是否允许进入下一批次：
```

没有回执、没有测试证据或门禁未满足时，不得继续下一批次。
