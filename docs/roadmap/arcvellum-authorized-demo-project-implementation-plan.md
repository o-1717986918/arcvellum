# ArcVellum 授权文学演示项目实施方案

## 1. 目标与范围

为 ArcVellum 桌面安装版提供一份可直接打开、阅读和观察完整文学工程设施的默认演示项目。当前指定作品为余华的中篇小说《我胆小如鼠》单篇，不包含同名作品集中的其他作品。

本工程必须同时满足：

- 正文来自用户提供的、经授权的确定版本，不从网络抓取或拼接；
- 作品实际字数就是演示项目字数，不为满足“十万字级”旧目标而扩写、重复或混入其他作品；
- 正文来源、版本、文件哈希和授权范围可追溯；
- 不把既有作品伪装成 Agent 生成稿，不伪造 RP、分支、审查或晋升历史；
- 人物、世界、情节、文风、场景、承诺、时间线等分析产物必须绑定原文证据；
- 安装、恢复和升级不能覆盖用户编辑过的副本；
- 公开仓库不提交授权正文或授权凭据原件，生产构建从受控本地输入生成版本化演示包。

## 2. 当前阻断与处理原则

当前已收到用户提供的本地文本 `C:/Users/26532/Downloads/我胆小如鼠.txt`。该文件实际是合集文本；构建输入已按可复核的行范围只提取《我胆小如鼠》单篇，保留原始文件哈希、派生文件哈希和提取规则。当前没有可供公开分发校验的授权凭据文件，因此：

- 可以在用户本机完成真实作品的分析工作区、来源投影和文学资产反推；
- 不得把该私人研究工作区声称为可随安装包或 GitHub Release 公开分发的演示包；
- 生产演示包构建必须在原文或授权凭据缺失、哈希不符、分发范围不足时失败；
- 用户需要提供原文文件，并提供可引用的授权凭据文件或编号；若授权只允许本地演示而不允许随安装包或 GitHub Release 分发，构建器必须采用对应范围，不能扩大解释。

私人研究例外：`user_attested_private_research` 允许用户自行导入本机文本，只要求源文件哈希和“仅限本地、不得再分发”的自证声明，不强制凭据文件。该模式只能声明 `local_analysis`，不得进入桌面默认演示、安装资源或 GitHub Release。

## 3. 架构边界

### 3.1 Engine：授权事实与文学工程真实性

归属：`src/literary_engineering_studio_engine/literary/ingest/authorized/`

职责：

- `AuthorizedWorkManifest`：作品、版本、语言和源文件清单；
- `AuthorizationGrant`：权利依据、权利方、被授权方、授权声明、凭据引用和允许的分发范围；
- `AuthorizedSourceFile`：项目相对文件名、媒体类型、字节数和 SHA-256；
- 确定性校验：安全相对路径、哈希、文件大小、凭据存在、授权范围；
- 生成稳定 manifest digest，供演示包、项目和桌面资源相互核对。

Engine 不负责：

- 判断授权文件的法律效力；
- 下载作品；
- 桌面安装位置和首次启动策略；
- 前端展示。

### 3.2 Engine Projects：授权正文形式化

归属：`src/literary_engineering_studio_engine/projects/authorized_demo.py`

职责：

- 从已校验 manifest 和本地源文件初始化项目；
- 复用 `source-ingest/v2` 保存不可变来源与分段证据；
- 将原文按实际章节/段落映射为只读的正式阅读正文；
- 为每个正式正文片段保存 `origin=authorized_source`、源范围、内容哈希和 manifest digest；
- 生成证据绑定的分析任务，不伪造 Agent 已完成痕迹；
- 生成可重复构建的项目快照。

该流程与“续写/改写项目”的创作路线分离。用户复制演示项目后，新增内容才进入正常 scene-development 门禁。

### 3.3 Studio：演示包生命周期

归属：`src/literary_engineering_studio/application/demo_distribution/`

职责：

- 演示包目录与版本清单；
- 首次启动原子安装；
- 只读演示项目与可编辑副本的区分；
- “复制为可编辑作品”和“恢复演示项目”；
- 升级时保留旧版本与用户副本，不静默覆盖；
- 安装失败回滚和状态说明。

### 3.4 Desktop：携带资源，不拥有业务规则

归属：`desktop/src-tauri/` 与 `packaging/`

职责：

- 将版本化演示包作为桌面资源携带；
- 在首次启动时调用 Studio 演示包服务；
- 构建前执行授权清单与演示包完整性验证。

桌面端不得自行解释授权范围，也不得直接解压覆盖作品目录。

### 3.5 Frontend：面向普通用户的演示入口

职责：

- 首次进入时显示“打开演示作品”；
- 清楚标记“授权演示，只读原作”和当前版本；
- 提供“复制为可编辑作品”，不允许直接改写演示母本；
- 展示原文阅读、人物、世界、情节、场景、文风和证据来源；
- 资料未生成时显示真实状态，不展示伪造的完成度；
- 提供恢复、重新安装和授权信息入口。

## 4. 数据合同

授权作品清单至少包含：

```json
{
  "schema": "arcvellum/authorized-literary-source/v1",
  "work_id": "yu-hua-i-am-timid-as-a-mouse",
  "title": "我胆小如鼠",
  "author": "余华",
  "edition": "由授权原文确定",
  "language": "zh-CN",
  "work_type": "novella",
  "source_files": [
    {
      "source_id": "primary-text",
      "filename": "source/primary.docx",
      "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "sha256": "<64 位小写十六进制>",
      "byte_size": 0
    }
  ],
  "authorization": {
    "basis": "author_permission",
    "rights_holder": "余华或实际权利方",
    "licensee": "实际被授权主体",
    "declaration": "授权范围的准确摘要",
    "evidence_ref": "rights/authorization.pdf",
    "evidence_sha256": "<64 位小写十六进制>",
    "scopes": ["local_analysis", "desktop_demo_bundle", "github_release_asset"]
  }
}
```

生产构建只校验文件、哈希与声明范围是否齐全，不自动声称法律审查通过。

## 5. 文学工程设施

演示项目应具备：

- 项目元数据与原作说明；
- 不可变来源、原文抽取文本、段落/章节范围和证据索引；
- 正式阅读正文及来源映射；
- 人物档案、主要/次要角色分类、角色背景故事和状态；
- 世界规则、地点、组织、时间线和禁改项；
- 情节结构、场景清单、章节义务、承诺/兑现账本和读者问题；
- 叙事节奏、详略、叙事距离和场景衔接分析；
- 500-2500 汉字的可挂载文风约束，并保存原文证据；
- 文学与逻辑审查报告；
- 原作分析产物与后续续写候选严格分区；
- Library、Reader、Orrery、Archive 和 Delivery 可读取的投影。

所有分析内容由正式任务生成并通过 schema / evidence gate；构建器只能创建待执行任务和确定性骨架，不能伪造完成记录。

## 6. 构建与安装流程

```text
受控本地原文 + 授权凭据
  -> authorized manifest verify
  -> source-ingest/v2
  -> 授权正文形式化
  -> 文学资产提取与逐项审查
  -> 项目完整性与证据审计
  -> 生成版本化 .arcvellum-demo
  -> 桌面生产构建校验
  -> 首次启动原子安装
  -> 用户只读体验 / 复制为可编辑作品
```

## 7. 实施阶段

截至当前代码状态：D1、D2、D4 的通用基础设施和 D5 的项目入口已经实现。真实单篇文本已进入本地 `local_analysis` 构建，D3 正在执行；D6 的本地验证可以继续，但桌面生产演示包和 GitHub Release 仍须等待覆盖对应分发范围的凭据。分析工作区在文学资产完成前保持可编辑，只有完整性审计通过后才能封存为只读母本。

### D1：授权与来源合同

- 新增授权合同、校验与文件核验；
- 支持本地分析、桌面演示包、GitHub Release 等独立范围；
- 测试路径越界、占位凭据、哈希错误、范围不足和成功样例。

### D2：单篇作品构建器

- 复用项目初始化和 `source-ingest/v2`；
- 新增授权正文 origin/provenance；
- 支持 DOCX、TXT、Markdown 等既有 reader；
- 正文实际字数写入项目目标和阅读投影；
- 对《我胆小如鼠》采用单一作品域，不引入合集子域。

### D3：文学资产完整化

- 发出证据绑定的反推任务；
- 完成人物、世界、情节、文风、时间线、承诺、节奏和审查；
- 用 route audit 验证，没有任务就不宣称完成。

### D4：演示包与桌面安装

- 生成稳定 ZIP 容器和 bundle manifest；
- 首次安装、恢复、升级、克隆和防覆盖；
- Tauri 资源与打包脚本接入；
- 公开仓库只保存工具、示例清单和测试小样，不保存授权正文。

### D5：前端体验

- 项目页增加演示卡；
- Reader 自动拼接授权正式正文；
- Archive 和 Orrery 展示真实分析设施；
- 授权状态、只读状态、克隆与恢复操作可见且亲用户。

### D6：交付验证

- 使用非版权短测试文本跑完整自动化；
- 使用用户提供的授权原文在本地运行真实构建；
- 校验 installer、首次启动、阅读、克隆、升级和恢复；
- 生成不含本机绝对路径、密钥、源凭据原件的审计报告。

## 8. 验收门禁

以下任一条件不满足，不得生成可公开分发的演示包：

- 授权原文缺失或哈希不符；
- 授权凭据缺失、为占位内容或哈希不符；
- 授权范围未明确包含目标发布渠道；
- 原文与正式阅读正文不能逐段追溯；
- 正文被标记为 Agent 生成；
- 分析产物缺少原文证据；
- 包内包含绝对路径、密钥或构建机私有路径；
- 安装或升级会覆盖用户修改；
- 前端把未完成分析展示为已完成。

## 9. 需要用户提供的输入

完成可公开分发的《我胆小如鼠》演示包仍需：

1. 当前用户文本对应的版本/出版信息；
2. 授权凭据文件或可核验编号；
3. 被授权主体名称；
4. 明确范围：可随桌面安装包分发、可作为 GitHub Release 资产分发；
5. 是否允许用户复制后续写、改写或仅可阅读和分析。

这些信息不应通过猜测补全。

## 10. 本批 Module Change Packet

```yaml
module_change_packet:
  objective: "让用户提供的单篇文本先成为可执行文学反推任务的分析工作区，审计通过后再封存为只读演示母本"
  primary_module: "Engine projects/authorized_demo"
  public_entry: "literary_engineering_studio_engine.public.projects"
  variation_point: "analysis workspace 与 sealed reference 的生命周期状态"
  inputs: ["AuthorizedWorkManifest", "已校验本地单篇源文件", "DistributionScope"]
  outputs: ["analysis workspace", "authorized source provenance", "sealed demo identity"]
  invariants:
    - "不得把原作伪装成 Agent 生成或晋升正文"
    - "不得扩大授权范围"
    - "文学资产未完成时不得只读封存"
    - "未封存项目不得进入 demo bundle"
  allowed_dependencies: ["Engine public projects/literary contracts", "Studio demo_distribution"]
  forbidden_dependencies: ["Provider HTTP", "前端业务判断", "公开分发私人研究文本"]
  tests: ["test_authorized_source_contract", "test_engine_public_api", "test_project_manager", "architecture_audit"]
  rollback_unit: "authorized demo analysis/seal lifecycle commit"
  documentation: ["本实施方案", "module-catalog.md"]
```
