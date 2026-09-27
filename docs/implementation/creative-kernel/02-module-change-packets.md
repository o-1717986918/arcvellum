# 逐批 Module Change Packet

每批先改拥有合同的模块，再迁移 adapter/调用方。每批的回滚单位是本批显式文件清单与测试；不触碰当前工作树中的 Project Agent、planning 改动。

## A 意图合同

```yaml
module_change_packet:
  objective: "主创可以形成并修订场景工作性文学意图"
  primary_module: "Engine literary.scene.transaction"
  public_entry: "public.literary.CreativeIntentV1.from_payload/to_dict"
  variation_point: none
  inputs: ["主创 JSON creative_intent 或既有意图"]
  outputs: ["版本化意图，含读者已知、误知与保留未知"]
  invariants: ["不进入 SceneDelta/Canon", "自由文字，不做审美门禁"]
  allowed_dependencies: ["transaction/contracts", "public/literary"]
  forbidden_dependencies: ["Studio", "Provider", "项目 I/O"]
  tests: ["意图解析、修订版本和界限", "public API"]
  rollback_unit: "A 合同文件及导出"
  documentation: ["本包", "03-describer-design.md"]
```

签名：`CreativeIntentV1.from_payload(payload: Mapping[str, object], *, prior: CreativeIntentV1 | None = None) -> CreativeIntentV1`。示例输入 `{"reader_experience":"让惯常沉默先显得温柔，稍后才有不安","reader_knows":"门没有锁","withheld":"谁把灯熄了"}`；输出 `{"schema":"arcvellum/creative-intent/v1","revision":1,...}`。无旧状态时版本 1；同场修订递增。旧缓存不迁移 Canon，缺失时重建工作意图。

## B 主创调用

```yaml
module_change_packet:
  objective: "首次主创决定直接写或按文学目的取材，后续成稿和审读共享意图"
  primary_module: "Studio runtimes/pi_scene_transaction"
  public_entry: "PiSceneTransactionRuntime.create_scene/review_scene/revise_scene"
  variation_point: "RoleConversationGateway 模型调用"
  inputs: ["SceneBrief", "CreativeIntentV1", "SceneCreatorMemoryV1"]
  outputs: ["CreativeResult", "ReviewResult", "交易私有意图记录"]
  invariants: ["只有主创交付正式正文", "软长度 warning 由审读判断", "缓存绑定提示摘要"]
  allowed_dependencies: ["Engine public.literary", "scene prompt renderer", "scene performance"]
  forbidden_dependencies: ["Engine internal", "直接 Canon 写入"]
  tests: ["零调用与请求循环", "软字数不插段", "审读接收意图"]
  rollback_unit: "B runtime/prompt 修改"
  documentation: ["01-current-callgraph.md", "本包"]
```

主创请求 JSON 示例：`{"creative_intent":{...},"material_requests":[{"kind":"actor","target":"阿青","purpose":"让读者先相信她并未生气","scene_moment":"晚饭后","cue":"对方刚把旧杯子递来"}]}`。旧回应若直接含 `prose` 则兼容；旧请求无 purpose 时不伪造文学目的，向模型要求修正。失败重启读取交易 sidecar。

## C 选材合同与交接

```yaml
module_change_packet:
  objective: "角色和环境成为主创可选工具，导演判断随候选交接"
  primary_module: "Engine literary.scene.roleplay"
  public_entry: "public.literary.parse_scene_material_requests/render_interaction_materials"
  variation_point: none
  inputs: ["MaterialRequestV2", "SceneBrief", "公开场景记录"]
  outputs: ["有 provenance 的候选块与 director_note/cue"]
  invariants: ["人格初始化保留", "私念受视角保护", "候选无写权"]
  allowed_dependencies: ["roleplay/performance", "roleplay/interaction"]
  forbidden_dependencies: ["Studio I/O", "正式 Canon"]
  tests: ["零/单/组合调用", "取舍信息和导演 note 交接", "视角边界"]
  rollback_unit: "C Engine 合同和 Studio scene_performance 适配"
  documentation: ["本包", "03-describer-design.md"]
```

`parse_scene_material_requests` 接受 `kind,target,purpose,scene_moment,cue`，旧 `speaker/beat_id` 可读。无预先计划的环境/描写请求可直接服务；角色首次请求时才规划和初始化。场景已有角色对演会话保持不变并可续演。现有旧测试需要按新按需语义更新，而非放宽权限。

## D 描写器

```yaml
module_change_packet:
  objective: "主创按需调用人物、事物、场面描写器，获取短候选"
  primary_module: "Engine literary.scene.roleplay"
  public_entry: "public.literary.render_describer_initialization/render_describer_turn/parse_describer_candidates"
  variation_point: "Pi Worker tool-free conversation role"
  inputs: ["kind", "视角", "已确认事实", "公开舞台", "purpose/scene_moment/cue"]
  outputs: ["0-3 个带 ID 的候选", "有界会话状态"]
  invariants: ["不捏造私念", "不代角色发起关键行动", "不写正式正文/Canon"]
  allowed_dependencies: ["roleplay contracts", "Studio RoleConversationGateway"]
  forbidden_dependencies: ["项目写权", "Provider HTTP client"]
  tests: ["合同校验", "续接历史", "Worker 白名单与无工具"]
  rollback_unit: "D 描写合同和 adapter"
  documentation: ["03-describer-design.md"]
```

## E 场景记忆

```yaml
module_change_packet:
  objective: "独立主创调用在一场内保有意图和取舍，下一场只继承正式事实"
  primary_module: "Studio runtimes scene creator session"
  public_entry: "SceneCreatorMemoryV1 load/save/render_context"
  variation_point: "交易 sidecar 存储"
  inputs: ["交易 ID", "意图", "候选 ID/取舍", "公开言行", "阶段"]
  outputs: ["有界上下文摘要", "可恢复 sidecar"]
  invariants: ["不包含其他角色私念", "不把候选写成确认事实"]
  allowed_dependencies: ["Engine public DTO", "scene_source_evidence"]
  forbidden_dependencies: ["SceneDelta 伪写入", "全量模型 transcript 注入"]
  tests: ["重启恢复", "候选/正式事实隔离", "上一场提交投射"]
  rollback_unit: "E session sidecar 和调用接线"
  documentation: ["本包"]
```

## F 提示词分层与编辑

```yaml
module_change_packet:
  objective: "所有模型可见提示可发现、按职责分层覆盖并在前端编辑文学层"
  primary_module: "Engine prompting"
  public_entry: "public.prompting catalog/resolve/assemble contracts"
  variation_point: "Studio persistence port 的全局/作品版本 adapter"
  inputs: ["layer ID", "scope", "revision", "transaction pin"]
  outputs: ["effective layer", "组装预览与摘要", "历史/回退"]
  invariants: ["协议层不可编辑", "作品>全局>随包", "既有 PromptAsset/PromptProgram v3 保留"]
  allowed_dependencies: ["Engine prompting", "Studio application ports", "settings feature client"]
  forbidden_dependencies: ["API 内写文件", "前端直连 generic transport"]
  tests: ["优先级/固定版本", "协议拒写", "API/client 回退"]
  rollback_unit: "F registry contract、persistence adapter、API、UI 分别提交"
  documentation: ["04-prompt-inventory.md", "本包"]
```
