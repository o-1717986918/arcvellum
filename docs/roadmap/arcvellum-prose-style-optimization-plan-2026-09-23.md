# ArcVellum 全面文风优化开发计划

> 状态：实施中（工程改造进行；盲评与长篇验收未完成）
> 基线：v0.99.10 / `ab8dd08`
> 日期：2026-09-23
> 范围：正文生成、文风语料、场景编排、人物声音、审读与效果验证
> 不在本计划内：增加文学门禁、用 AI 检测器作为目标、引入向量数据库、增加创作 Agent 数量、训练或微调模型

## 0. 决策摘要

本轮不再以“继续增加反 AI 词表”和“把提示词写得更长”为主要手段。当前文风问题的根因是：正确规则虽然已经存在，但生成链仍在向模型注入平均化模板、无条件感官提示和重复负向约束；参考语料没有经过场景化选择；人物语言资料在链路中发生信息损失；真实效果验证仍以字符串合同和静态 lint 为主。

目标链路调整为：

```text
完整文风语料与不可变版本
        ↓
按场景确定一篇主参考、至多一篇辅参考
        ↓
场景表达计划：只激活 1—3 个表达轴
        ↓
人物稳定声音 + 当下关系状态
        ↓
创作 Agent 完成正文初稿和一次局部自检
        ↓
硬语言审查 + 有证据的语义审读 + 最小范围返修
```

这条链路遵守五项约束：

1. 文风软目标在生成阶段落实，不转化为新的静态阻断器。
2. 用户明确禁用表达、中文标点正确性、Canon 和事实一致性继续进入正式审查。
3. 不新增 Agent，不新增正式路线，不增加每场模型调用次数。
4. 不把“更多感官、更多身体反应、更多修辞”当作通用解法。
5. 全部参考语料完整保留并进入可选集合，但单场只投射真正相关的完整选段，避免二十五种声音同时平均化。

## 1. 当前实现审计

### 1.1 已有能力应保留

当前系统并非缺少文风基础设施。以下能力已经成立，实施时应复用：

- 默认文风以不可变版本挂载，具有内容哈希、Prompt 哈希和挂载快照。
- 默认 R01—R25 语料完整保存在版本化 `style-profile.md` 中，新项目会正式挂载。
- 正式场景路线已有 reader experience、narrative rhythm、scene bridge、word budget、人物 BDI、背景故事和 AgentReview。
- lean-v2 已把人物资产、用户方向、Canon、上一场正文与文风证据放入 `SceneBrief.source_refs`。
- 数字规则已区分虚指反复、当场问答、因果数字和装饰性精确计数。
- 当前生成提示已允许长短句变化、自由间接引语、反讽、借代、通感、复沓和意象回返，并明确要求“证据之后停笔”。
- Creative Quality Profile 已支持 `blocking`、`note`、`off` 和场景级例外，不需要再造规则系统。

### 1.2 已确认的文风源头

| 源头 | 当前代码事实 | 对成稿的影响 |
| --- | --- | --- |
| 固定正文种子 | `literary/scene/composition/creative_plan.py::build_prose_seed()` 直接生成“一个不肯退让的细节”“旧习惯先一步收紧了他的判断”“更慢、更难、但仍属于他的路”等成品句 | 模型从同一种抽象文学腔起步，跨题材复制同一声音 |
| 通用感官填充 | `build_sensory_palette()` 在资料不足时自动给出低频声、脚步、温度、粗糙边缘、局部光源和阴影 | 即使场景不需要，也会诱导声光、身体和材质轮流报到 |
| 表达计划与正文混杂 | 正式 Prompt 摘要要求执行 `prose_seed`，编排审查也把它当成必需输入 | 顶层编排提前写死局部语言，创作 Agent 退化为扩写器 |
| 人物声音丢失 | 初始化后的 `speech_style` 有 vocabulary、rhythm、taboo_words、signature_patterns；`CharacterCard` 实际只读取 rhythm 或 vocabulary 中一个标量 | 人物语言策略、禁区和差异不能完整进入对白编排 |
| 缺少当下声音 | `dialogue_intents` 只有 wants、avoids、speech_strategy，缺少对话对象、地位、知识边界、隐瞒事项和当前言语动作 | 人物档案即使不同，也容易在具体场景中说成同一种平直话 |
| 语料无场景化选择 | lean-v2 按 `source_refs` 顺序读取文件并在字符预算耗尽时停止；默认文风完整语料作为一个大文件进入上下文 | 真实项目中语料可能被前序资料挤掉；即使完整进入，也要求模型自行从二十五段中找主参考，容易平均化 |
| 正式与 lean 路径不等价 | 正式 Prompt Pack 默认读取最多 6000 字符的 active prompt；lean-v2 另行顺序内联 source evidence | 同一挂载文风在不同创作路径中的实际证据和权重不同 |
| 规则重复 | `prompt.md`、`ANTI_AI_STYLE_PROMPT`、`STYLE_GENERATION_STANDARD`、正式 route asset、lean create/revise prompt 和质量档案重复表达相近规则 | 提示词变长，正向风格样本被大量警告稀释，也提高维护漂移风险 |
| 软审美被默认阻断 | `creative_quality.py` 将 comma overload、abstract summary、explanatory psychology、staccato、transition 等多项默认设为 `blocking` | 生成阶段没有解决的审美问题在审查端被机械退稿，容易触发反复返修和二次磨平 |
| 审查知道“不要什么”，较少知道“本场要什么” | 当前 lint 能发现模式词、对照结构、标点和密度，但没有场景表达计划与参考技法的精确投影 | 即使静态检查通过，也不能证明语言有起伏、人物有声音、样本真的生效 |
| 评测偏合同存在性 | 主要测试检查提示词包含某句话、语料哈希未变、挂载完整、规则能命中 | 能证明规则存在，不能证明读者更喜欢或人物更可辨 |

### 1.3 研究结论对本项目的直接含义

- StoryScope 显示 AI 小说的区别不仅是套话，还包括过度解释主题、因果过顺、单线收束、后置揭示不足，以及身体反应和感官描写过密。因此不能继续把“多写身体和感官”当成通用文学增强。[StoryScope](https://arxiv.org/abs/2604.03136)
- 职业作者编辑语料显示，泛化的“去 AI 味”提示不能稳定解决陈词滥调、冗余说明、笨拙句法和缺乏有根据的具体性；修订必须定位片段和功能。[LAMP](https://arxiv.org/pdf/2409.14509)
- 场景或题材相关的特征调整优于全篇统一人类化；一次只改少数高影响特征，能降低过度约束风险。[CraftAlign](https://arxiv.org/abs/2608.01377)
- 作者样本、写作说明和当前题目规则组合有效，但大量固定语言规则可能干扰模型从样本中学习的隐式风格。[个性化故事生成](https://aclanthology.org/2025.ijcnlp-long.82/)、[作者风格模拟](https://aclanthology.org/2024.personalize-1.6.pdf)
- 温度与新颖性的关系较弱，却更稳定地增加不连贯。温度只能做阶段化实验，不能替代场景、人物和参考机制。[温度与创造力实验](https://computationalcreativity.net/iccc24/papers/ICCC24_paper_70.pdf)

## 2. 目标与非目标

### 2.1 用户可感知目标

完成后，正文应出现以下变化：

- 同一作品的不同场景有可听见的速度、句法和叙述距离变化，不再全程中速平铺。
- 人物台词去掉姓名后仍有较高可辨识度，但不会依赖口头禅、方言标签或固定短句。
- 修辞从人物经验、世界材料和当前信息压力中生长，不再靠器官、天气、光线和材质自动补位。
- 动作、对白或物证已经成立时，段落能够停住；不再频繁补意义说明或金句式收束。
- 参考语料的技法可以从 Prompt Manifest 和盲评结果中追踪，而不是仅凭提示词声称“已经参考”。
- 章节间不重复同一种调查程序、动作链、悬念结尾和语言曲线。

### 2.2 工程目标

- 正式场景路线和 lean-v2 使用同一个 Engine 文风投射接口。
- 单场不增加模型调用；选段、上下文裁剪和兼容迁移均为确定性代码。
- 新增产物必须进入现有 style mount、composition 和 prompt manifest 的版本与哈希体系。
- 删除或废弃固定 `prose_seed` 后，旧项目仍可读取；不批量重写已晋升正文和不可变文风版本。
- Prompt 总体长度不增加；完成去重后，固定文风规则字符量应低于 v0.99.10 基线。

### 2.3 明确非目标

- 不追求让 AI 检测器判为人类。
- 不把每篇正文写成同一种“参差、口语、留白”的新模板。
- 不要求每个场景都使用华丽修辞、高温采样或高强度语域。
- 不引入 embedding、RAG 服务、向量数据库、第三方模型 API 或新 Agent。
- 不新增字数、数字密度、修辞数量、句长配额或感官数量门禁。
- 不把 R17—R25 当反例；它们继续作为类型氛围和空间定调的正向样本。

## 3. 目标设计

### 3.1 文风参考索引：完整保留，按场景投射

新增一个轻量、可版本化的 `style-reference-index/v1`。它不是检索服务，只是挂载文风版本内的声明式索引。

每个参考单元包含：

```json
{
  "unit_id": "R21",
  "source_digest": "sha256:...",
  "span": {"start": 0, "end": 0},
  "scene_functions": ["atmosphere", "threat-entry"],
  "pressure": ["low-burn", "rising"],
  "dialogue_level": "low",
  "narrative_distance": ["medium", "close"],
  "technique_axes": ["space-reveal", "sound-before-cause", "material-risk"],
  "genre_affinity": ["speculative", "disaster"]
}
```

约束：

- R01—R25 原文继续完整保留，原有总哈希测试继续生效。
- 二十五个单元必须全部进入索引，不能因常用程度删除或缩写。
- “全部完整用上”落实为：全部完整保存、全部可选择、全部有功能分类、全部通过可达性测试；不意味着每场把二十五段同时塞入创作提示。
- 默认文风的索引由项目维护者人工整理；用户自建文风可在现有文风编译任务中生成候选索引，并随文风版本一同审查、冻结。
- 不从参考文本抽取作者身份、版权说明或来源广告；只保留用户授权正文与必要的内部单元 ID。

选段规则：

1. 输入现有 scene function、reader effect、rhythm、viewpoint、对话比例、类型和最近场景选段历史。
2. 选择一篇主参考；只有第二篇能补充不同且必要的轴时才加入辅参考。
3. 主参考全文完整注入，不截取开头假装代表整篇；过长自定义单元在文风编译阶段预先拆成有边界的完整片段。
4. 对最近四场连续使用同一单元施加降权，但不能为了轮换选择明显不相关样本。
5. 选择结果写入 Prompt Manifest：单元 ID、内容哈希、选择理由、使用轴和选择器版本。
6. 选段不更改 Canon、人物、剧情和世界事实，只提供表达机制。

### 3.2 场景表达计划：替换固定正文种子

新建 `scene-expression-plan/v1`，作为 composition 的一个紧凑投影。它只描述表达决策，不提供可复制的成品句。

```json
{
  "focalization_lens": "人物首先注意到什么，又会漏掉什么",
  "information_strategy": "延迟、误导、直给、重释或并置",
  "syntax_motion": "句法如何随本场压力改变",
  "dialogue_pressure": "谁试探、谁回避、谁夺取解释权",
  "evidence_channel": "动作、对白、物证、直述、沉默或环境中的必要组合",
  "ending_residue": "场景结束后保留的动作、关系后果、空缺或问题",
  "active_axes": ["information_strategy", "dialogue_pressure", "syntax_motion"]
}
```

执行规则：

- 每场只激活 1—3 个表达轴，其他字段可以保持中性，防止把文学写作变成打卡。
- 删除新 composition 中的固定 `prose_seed`；旧 v0.1 composition 可读，但生成时只把它降为 legacy evidence，不要求复现措辞。
- `sensory_palette` 改为可为空的 `perceptual_options`。只有地点、人物经验或当前风险确有依据时才产生声音、触感、光线等选项。
- 允许直接写情绪。系统不再默认把每种情绪转成胸口、呼吸、手指、气味、天气或光影。
- `ending_residue` 只说明保留什么后果，不预先规定金句、异常物件或“停在一个动作上”的固定收尾。
- 顶层 Agent 和确定性编排只提供条件；具体语言选择仍由当前主创 Agent 完成。

### 3.3 人物声音：稳定层与当下层分开

复用现有人物 YAML，不增加第二套人物档案。场景编排时完整读取 `speech_style`，并从既有关系、BDI、知识状态和场景压力投射两层卡片。

稳定层：

- 词域与生活/职业经验；
- 句子完整度和节奏偏向；
- 礼貌边界、幽默方式、主动发问或回避方式；
- 明确禁区与少量可变句法习惯；
- 知识边界和不可能自然说出的内容。

当下层：

- 对话对象；
- 当前想从对方获得什么；
- 双方公开与实际地位；
- 正在隐瞒、误解或拒绝承认的内容；
- 本轮主要言语动作：试探、逼迫、套话、转移、取悦、安慰、拒绝、误导或夺取解释权；
- 压力升高后可能发生的语气变形。

对白要求从“句式特征”改成“言语行动”。不要求人物每句都显眼；审查只在关键对话持续混同、确实损害关系张力或人物可信度时返修。

### 3.4 Prompt 结构：减少重复，让样本靠近写作动作

统一后的单场正文 Prompt 顺序：

1. 身份、输出合同与不可变事实。
2. 当前 scene、上一场后果、人物和世界状态。
3. composition obligations、reader experience、rhythm/bridge。
4. 人物稳定声音与当下声音卡。
5. 本场 expression plan。
6. 选中的一篇主参考、可选辅参考及短技法卡。
7. 精简后的通用文风原则。
8. 最终硬语言边界与输出格式提醒。

通用文风原则只保留：

- 语言来自人物会注意、误解、回避和说出的事物；
- 修辞必须改变视角、节奏、关系或信息；
- 情绪选择当前最有因果意义的表达渠道，不轮流调用感官和器官；
- 证据已经成立后，停在后果，不替读者翻译；
- 样本优先迁移叙述距离、句法运动、信息隐匿、对白回弹和意象来源，不复制原句。

以下内容不再在五六个位置重复：2% 软密度说明、完整对照变体列表、完整数字说明、完整标点说明。它们各自保留一个权威来源，在 Prompt 编译时投射短版，在审查时使用完整版。

### 3.5 审查职责：硬规则继续审，软规则不再冒充文学真相

| 层级 | 规则 | 处理 |
| --- | --- | --- |
| 硬阻断 | 用户自定义禁用表达、当前明确禁止的机械对照及换皮、ASCII 标点、错误省略号、错误引号、连续标点、Canon/事实冲突、复制风险 | 保持正式审查和修订要求 |
| 配置型标点阻断 | 用户或项目明确规定的破折号、引号和标点风格 | 按 Creative Quality Profile 执行，不删除 |
| 软诊断 | 逗号链、连续短句、抽象总结、解释性心理、器官反应、比喻依赖、模板转折、景物同步、金句收尾 | 默认 `note`；给出片段、密度和阅读损害，不单独阻断 |
| 语义审读 | 无关精确数字、人物声音趋同、证据后解释、参考技法未落实、情节或动作程序重复 | 只有引用原文并说明实际损害时判 `revise` |
| 结构审读 | 场景没有 turn、信息释放过满、副线消失、结尾过度收束、连续场景同构 | 与句子润色分开；需要时重写场景，不用局部换词伪装修好 |

每次 AgentReview 最多提出三个高影响问题。返修必须保持有效片段，只改问题跨度；除非场景结构失败，不执行整场“更文学、更像人”的泛化重写。现有“两轮后收敛”机制继续保留。

### 3.6 温度与思考强度

- 创作 Agent 的思考强度和采样温度是两个不同参数，不能互相替代。
- 当前 Pi Worker 已开放思考强度；并非所有 Runtime 都开放温度。界面不得显示一个后端实际不支持的虚假温度滑块。
- 第一轮实施不改变全局温度。先完成表达计划、参考选段和人物声音 A/B，确认剩余问题确实来自采样保守后再实验。
- 若 Runtime 明确声明采样能力，后续可提供“稳定 / 均衡 / 活跃”三个创作预设：规划与审读保持低随机性，正文初稿适度提高，事实提取和 lint 不变。
- 不写死跨模型温度数值；每个 adapter 映射并报告实际生效值，Prompt Manifest 记录能力和设置。

## 4. 实施批次

每批只有一个主模块，独立提交、独立回滚。跨模块变化先落 Engine 公共合同，再迁移 Studio 调用方。

### Batch 0：冻结 v0.99.10 文风基线

```yaml
module_change_packet:
  objective: "建立可重复的当前文风基线，后续改动必须用同题盲评证明收益"
  primary_module: "tests / benchmarks"
  public_entry: "文风基准 fixture、运行脚本与报告模板"
  variation_point: "模型与 Runtime 能力写入运行清单"
  inputs: ["固定场景包", "v0.99.10 提示快照", "固定人物与文风挂载"]
  outputs: ["baseline candidates", "prompt manifests", "blind-review packet", "machine diagnostics"]
  invariants: ["不改生产行为", "不把 LLM 评分当真人结论", "不使用 AI 检测器"]
  allowed_dependencies: ["现有 benchmark 与 E2E helper", "公开 Engine 读取接口"]
  forbidden_dependencies: ["生产项目写回", "隐藏模型调用"]
  tests: ["fixture 可重复", "结果与 Prompt Manifest 一一对应"]
  rollback_unit: "独立基线提交"
  documentation: ["docs/quality/prose-style-baseline-2026-09.md"]
```

场景集至少覆盖：关系对话、公开冲突、动作场面、悬疑揭示、氛围过场、内省余波、类型高强度场景、多人信息差。另设四组相邻场景，专门检查动作链和收尾重复。

### Batch 1：建立文风参考索引与选择投影

```yaml
module_change_packet:
  objective: "完整语料按场景选择后进入创作提示，并留下可复现证据"
  primary_module: "Engine literary/style/"
  public_entry: "public/literary.py 的 active style reference projection"
  variation_point: "style-reference-index/v1；没有索引的旧挂载走兼容 fallback"
  inputs: ["不可变 style version", "scene/rhythm/reader-experience 摘要", "近期选段历史"]
  outputs: ["主/辅参考完整选段", "technique card", "selection digest"]
  invariants: ["全部原文完整保留", "不复制专名和连续措辞", "不改变 Canon", "不调用模型"]
  allowed_dependencies: ["现有 style version、snapshot、mount 与 public facade"]
  forbidden_dependencies: ["Studio runtime", "向量数据库", "Provider SDK"]
  tests: ["R01—R25 全覆盖与哈希", "每个单元至少对一个合成场景可达", "选择确定性", "近场重复降权"]
  rollback_unit: "独立 Engine style 提交"
  documentation: ["default style catalog", "style version contract"]
```

兼容策略：旧文风版本没有索引时，继续加载原 prompt，并生成 `selection_status=legacy-unindexed`；不伪造选段成功。默认文风发布一个新的不可变版本，不覆盖历史版本。

### Batch 2：用表达计划替换 `prose_seed` 和通用感官清单

```yaml
module_change_packet:
  objective: "场景编排提供表达条件而非现成文学句，停止自动填充声光触感"
  primary_module: "Engine literary/scene/composition/"
  public_entry: "composition v0.2 与 prose execution contract"
  variation_point: "scene-expression-plan/v1；legacy composition adapter"
  inputs: ["scene facts", "branch", "reader experience", "rhythm/bridge", "邻场摘要"]
  outputs: ["expression_plan", "可为空的 perceptual_options", "兼容投影"]
  invariants: ["场景义务与选择分支不变", "不写成品句", "不增加 Gate", "旧 v0.1 可读"]
  allowed_dependencies: ["现有 composition、rhythm、reader experience"]
  forbidden_dependencies: ["新 Agent", "模型调用", "通用感官默认值"]
  tests: ["新 composition 不含固定 prose_seed", "资料不足时感官选项为空", "表达轴最多三个", "旧 artifact 兼容"]
  rollback_unit: "独立 composition 提交"
  documentation: ["scene composition module docs", "artifact contract"]
```

同步移除 Prompt 中“必须执行 prose seed”的表述。旧 `prose_seed` 只能作为历史来源存在，不能继续成为措辞约束。

### Batch 3：完整传递人物声音并生成情境化对白卡

```yaml
module_change_packet:
  objective: "人物档案中的语言差异完整进入每场对白，并随对象和压力变化"
  primary_module: "Engine literary/scene/roleplay/"
  public_entry: "CharacterCard 与 dialogue intent projection"
  variation_point: "稳定声音字段 + scene-local voice state"
  inputs: ["现有人物 YAML", "关系", "BDI", "known facts", "scene participants 与冲突"]
  outputs: ["完整 stable_voice", "按说话者/对象生成的 voice_state"]
  invariants: ["不新造身世、方言或口头禅", "不把声音差异做静态 Gate", "背景故事只作行为因果"]
  allowed_dependencies: ["人物资产和 scene facts"]
  forbidden_dependencies: ["第二套人物档案", "Studio 数据库", "Provider 调用"]
  tests: ["speech_style 四字段无损读取", "对不同对象产生不同言语动作", "知识边界进入对白卡"]
  rollback_unit: "独立 roleplay 提交"
  documentation: ["character asset contract", "dialogue intent docs"]
```

Studio 的 lean asset enrichment 只需在下一独立 adapter 批次对齐公开合同，不在本批直接跨层 import Engine internal。

### Batch 4：统一正式路线 Prompt 投射

```yaml
module_change_packet:
  objective: "正式创作提示使用选定样本、表达计划和人物声音，并减少重复负向规则"
  primary_module: "Engine prompting/"
  public_entry: "public/prompting.py::build_scene_prompt_pack"
  variation_point: "style projection version recorded in prompt manifest"
  inputs: ["scene execution contract", "style reference projection", "voice cards", "hard language policy"]
  outputs: ["统一 Prompt Pack", "可审计 manifest"]
  invariants: ["任务输出合同不变", "Canon/事实优先", "硬审查不削弱", "Prompt 不增长"]
  allowed_dependencies: ["Engine public literary contracts", "现有 prompt registry"]
  forbidden_dependencies: ["Studio runtime", "重复业务规则", "隐藏 fallback"]
  tests: ["Prompt 顺序与来源", "只含所选完整样本", "manifest digest", "prompt registry validate"]
  rollback_unit: "独立 prompting 提交"
  documentation: ["prompt registry", "default style audit"]
```

Prompt Asset 版本递增；`STYLE_GENERATION_STANDARD` 成为通用生成规则唯一来源。Route Asset 只保留当前任务职责，不再复制完整反 AI 手册。

### Batch 5：让 lean-v2 使用同一 Engine 投射

```yaml
module_change_packet:
  objective: "lean-v2 与正式路线获得相同的文风样本、人物声音和表达计划"
  primary_module: "Studio runtimes/"
  public_entry: "PiSceneTransactionRuntime prompt rendering"
  variation_point: "通过 Engine public API 消费 style/expression projection"
  inputs: ["SceneBrief", "Engine 投射", "现有 source refs"]
  outputs: ["create/revise/review prompts", "一致的 selection provenance"]
  invariants: ["不直接 import Engine internal", "不增加模型调用", "不越过 Worker 写回", "缓存键纳入新 digest"]
  allowed_dependencies: ["Engine public/literary.py 与 public/prompting.py", "现有 Pi gateway"]
  forbidden_dependencies: ["顺序拼接完整语料作为主算法", "Provider 特判", "第二套选择器"]
  tests: ["formal/lean 同场选择一致", "真实 source refs 不挤掉样本", "缓存随选择摘要失效"]
  rollback_unit: "独立 Studio runtime adapter 提交"
  documentation: ["runtime prompt recipe", "lean-v2 quality note"]
```

`_source_evidence()` 继续承载 Canon 和人物资料，但不再负责文风语料选择。选中的文风片段走独立、有界、不可被普通 refs 顺序截断的区块。

### Batch 6：重整 lint 默认级别和语义审读

```yaml
module_change_packet:
  objective: "保留违禁词与标点审查，同时让软审美回到生成和证据化语义审读"
  primary_module: "Engine literary/review/"
  public_entry: "Creative Quality Profile 与 candidate style review"
  variation_point: "新默认 profile；既有保存 profile 不静默迁移"
  inputs: ["候选正文", "expression plan", "voice cards", "style selection", "用户 profile"]
  outputs: ["硬阻断", "软诊断", "最多三个语义修订项"]
  invariants: ["用户禁词不删除", "标点正确性不削弱", "数字不做正则门禁", "不自动改正文"]
  allowed_dependencies: ["现有 anti_ai、punctuation、review contracts"]
  forbidden_dependencies: ["新 Gate", "AI 检测器", "全篇泛化润色"]
  tests: ["硬规则继续 blocking", "软规则默认 notes", "有范围例外时行为稳定", "返修收敛"]
  rollback_unit: "独立 review policy 提交"
  documentation: ["creative quality migration guide", "lint audit"]
```

已有项目的 `creative_quality_profile.json` 保持不变。Style Atelier 提供迁移预览，列出哪些规则会从 blocking 降为 note，由用户确认后产生新 revision；新项目直接采用新默认。

### Batch 7：可观察性与用户控制

```yaml
module_change_packet:
  objective: "用户能看见本场采用了哪些参考和表达策略，并能调整创作随机性能力"
  primary_module: "Studio observability/creative_live/"
  public_entry: "现有 Creative Live artifact projection"
  variation_point: "只读 style provenance；Runtime capability-based sampling controls"
  inputs: ["prompt manifest", "runtime capability", "style selection digest"]
  outputs: ["参考单元、技法轴、文风版本、实际采样能力的只读展示"]
  invariants: ["不展示隐藏思维", "不允许 UI 改写正式产物", "不伪装不支持的温度"]
  allowed_dependencies: ["现有 observability read model 与 feature client"]
  forbidden_dependencies: ["新业务 Gate", "前端直读项目文件", "通用 transport 直连"]
  tests: ["read model contract", "feature client contract", "桌面与移动布局"]
  rollback_unit: "独立 observability/UI 提交"
  documentation: ["用户文风验证说明"]
```

本批不新建页面。优先在现有 Creative Live / 文风工作台中展示；温度预设只有 Runtime 明确报告支持时才出现。

### Batch 8：盲评、长篇回归与发布

```yaml
module_change_packet:
  objective: "用真实创作证明文风改善且无长篇、Canon、预算和桌面回归"
  primary_module: "benchmarks / release verification"
  public_entry: "固定 A/B 测试、五章长篇 E2E、release checklist"
  variation_point: "不同 Runtime 单独报告，不混合统计"
  inputs: ["v0.99.10 baseline", "候选版本", "固定项目与场景"]
  outputs: ["盲评报告", "回归证据", "发布候选与回滚说明"]
  invariants: ["不在结果揭盲前改 rubric", "不把格式通过称为文风通过"]
  allowed_dependencies: ["现有 E2E、route audit、desktop acceptance"]
  forbidden_dependencies: ["只用 LLM judge 放行", "只跑短样例", "带病发布"]
  tests: ["定向、全量、桌面、100k/5 章长篇"]
  rollback_unit: "发布提交与标签"
  documentation: ["最终质量报告", "CHANGELOG", "release notes"]
```

## 5. 验证设计

### 5.1 消融组

同一批场景固定人物、Canon、事件和模型：

- A：v0.99.10 基线。
- B：去除固定 `prose_seed` 和通用感官默认值，只加入 expression plan。
- C：B + 场景化参考选段。
- D：C + 稳定/当下双层人物声音。
- E：D + 新审读策略，用于确认返修没有再次磨平语言。

不得只比较 A 与最终版本，否则无法判断收益来自哪一部分，也无法在副作用出现时局部回滚。

### 5.2 真人盲评

每个候选隐藏版本、Prompt 和模型信息。至少三名读者独立评价：

1. 总体愿意继续读哪一版。
2. 语言是否随场景压力真正变化。
3. 人物台词是否可辨、是否符合关系位置。
4. 修辞是否准确且来自人物/世界，而非通用装饰。
5. 是否在读者已经明白后继续解释。
6. 场景结尾是否重复使用同一种悬念或意义总结。
7. 参考语料的技法是否可辨，同时是否存在近似复写。

角色声音另做去名测试：移除台词前的说话人标签，让读者判断人物归属并说明依据。

### 5.3 自动指标的用途边界

自动指标只负责发现退化，不负责宣布文学质量：

- 硬 lint、Canon、时间线、数字事实和标点必须通过。
- 记录句长、段厚、对白占比和标点分布，但不设统一“人类区间”。
- 检查跨场重复 n-gram、固定动作链、相同结尾结构和参考文本连续措辞相似度。
- 统计解释性尾句、身体反应、无依据感官和显式主题总结的人工确认命中率。
- 校验每场 Prompt Manifest 中的 style version、reference IDs、technique axes、expression plan digest 和 voice digest。
- LLM judge 只能给审读线索；最终放行依赖真人盲评和正式 route audit。

### 5.4 发布验收线

候选版本同时满足以下条件才进入发布：

- 所有硬语言规则、Canon、正式路线和桌面回归无退化。
- D/E 相对 A 在有效盲评中获得至少 60% 总体偏好，且任何场景家族不得低于 50%。
- 去名角色辨认率相对 A 有明确提升，主要人物之间不得出现系统性混同。
- “证据后解释”“通用感官填充”“固定收尾”人工标注率均低于基线。
- 参考技法能被评审指出，但相似度检查不出现连续措辞复制风险。
- Prompt 固定规则字符量不高于基线，单场模型调用次数不增加。
- 至少完成一个五章、约十万字项目的端到端验证，重点检查跨章声音漂移、场景模板复发、参考单元过度复用和后半程解释增多。

若总体偏好达标但某一题材家族退化，不以平均分掩盖；回到该场景家族的选段标签、表达轴或人物声音投射单独修复。

## 6. 兼容、迁移与版本策略

### 6.1 不可变文风版本

- 不修改已挂载的历史文风版本。
- 默认文风以新 version 发布，内容哈希纳入 `reference-index.json`。
- 新项目挂载新版本；旧项目在文风工作台看到差异预览后主动升级。
- Prompt Manifest 记录 selector/version，使同一候选可解释和复现。

### 6.2 Composition 兼容

- 新生成的 composition 使用 v0.2 和 `expression_plan`。
- v0.1 继续可读；旧 `prose_seed` 不再作为必须复现的硬约束。
- 已晋升正文、已完成 route event 和 Canon 不因升级而自动重写。
- 需要继续创作的旧项目只在下一场景重建 composition，不批量迁移全部历史文件。

### 6.3 Quality Profile 迁移

- 新默认把抽象总结、解释性心理、逗号链、碎句、比喻依赖、模板转折和金句收尾设为 `note`。
- 用户禁用表达、当前核心机械对照、项目标点规范和自定义 hard rules 保持 `blocking`。
- 旧 profile 不静默变化；迁移生成新 revision，可随时回退到上一 revision。

## 7. 风险与控制

| 风险 | 触发方式 | 控制 |
| --- | --- | --- |
| 参考样本导致仿写或串味 | 选段过多、长期固定一个单元 | 每场一主一辅、近场降权、相似度检查、记录哈希 |
| 场景选择器过于机械 | 标签不足或错误 | 默认文风人工索引；未知时使用中性 prompt，不伪造精准匹配 |
| 文风规则继续膨胀 | 每次发现坏句就加一条全局禁令 | 新软规则必须先有跨场复发证据；优先改表达计划、样本或人物材料 |
| 人物声音变成标签表演 | 强制口头禅、方言、固定句长 | 以言语行动和对象关系为主，静态习惯只作边界 |
| 审读返修把文本重新磨平 | Reviewer 逐句清理所有风险 | 最多三个高影响问题、片段级修改、保护有效语言和样本技法 |
| 旧项目行为突变 | 自动迁移 style/profile/composition | 新版本显式挂载、迁移预览、旧产物兼容、不批量回写 |
| Prompt 仍被截断 | 风格材料排在普通 source refs 后 | 文风投射独立预算和区块；完整性写入 manifest 并测试 |
| 温度设置名存实亡 | Runtime 不支持采样参数 | capability 检测，不支持即不展示，不用思考强度冒充温度 |
| 只优化短场景 | 微型样例好看，长篇后半程复发 | 相邻场景组、章节组和五章十万字 E2E 分层验收 |

## 8. 实施顺序与停止条件

```text
Batch 0 基线
   ↓
Batch 1 参考索引 ──┐
Batch 2 表达计划 ──┼─→ Batch 4 正式 Prompt
Batch 3 人物声音 ──┘          ↓
                         Batch 5 lean-v2 对齐
                                  ↓
                         Batch 6 审查职责重整
                                  ↓
                         Batch 7 可观察性
                                  ↓
                         Batch 8 盲评与发布
```

出现以下任一情况时停止扩展，先回到最近批次修复：

- 为解决一个坏句准备新增新的全局硬门禁；
- 单场模型调用次数开始增加；
- Prompt 长度增加但盲评没有改善；
- 参考选择无法从 Manifest 复现；
- 人物声音依赖口头禅或方言才能辨认；
- lint 通过率提高但真人偏好下降；
- 文风收益只能在一个题材成立；
- 旧项目必须批量改写才能继续使用。

## 9. 完成定义

本计划不以“提示词已经修改”作为完成。只有以下事实同时成立，才能宣布文风优化完成：

1. 固定 `prose_seed` 和无依据感官默认值不再进入新场景正文生成。
2. 正式路线与 lean-v2 使用同一份、可复现的场景化文风投射。
3. R01—R25 全部完整保存、全部进入索引、全部可达，单场只使用相关完整选段。
4. 人物 `speech_style` 不再丢字段，并形成与对话对象和当下压力相关的声音卡。
5. 抽象软文风问题主要在生成阶段解决；审查继续保留违禁词和标点规则，但不靠新增门禁塑造文学性。
6. Prompt Manifest 能证明具体用了哪些样本、技法、表达轴和人物声音来源。
7. 消融盲评显示收益来自可定位的设计，而不是模型随机波动。
8. 五章长篇回归没有出现后半程文风塌缩、人物声音合流、情节动作链重复或解释性收尾复发。
9. 全量 Python、前端、Pi Worker、架构审计、模块图、Prompt Registry、桌面开发版和安装包验证全部通过。

达到以上条件后，才进入版本号更新、CHANGELOG、安装包签名与发布流程。
