# Material Context Contract Change Packet

```yaml
module_change_packet:
  objective: "让每次素材委托可携带主创写下的当前语境，并逐次选择此前产出的候选或片段。"
  primary_module: "Engine literary scene roleplay contracts"
  public_entry: "literary_engineering_studio_engine.public.literary.SceneMaterialRequestV4 / parse_scene_material_requests_v4"
  variation_point: "V3 委托只支持作品档案引用；新 V4 增加工作语境与场景内候选引用。"
  inputs:
    - "现有 V3 kind/target/purpose/scene_moment/cue/author_prompt/archive_attachments/card/style"
    - "V4 working_context 文本与 material_attachments 候选 ID、半开字符区间"
  outputs:
    - "不可变 V4 委托 DTO；JSON transport 保留 V3 字段并显式带 V4 字段"
  invariants:
    - "保留 V3 parser 与序列化语义，未迁移交易仍按冻结合同解释"
    - "候选挂载只引用交易内候选；来源状态由素材本身保留，不能提升为 Canon"
    - "档案挂载路径与角色知识分区继续使用现有合同"
    - "不改变正式 Gate、SceneDelta、Canon 或正文写回语义"
  allowed_dependencies:
    - "Engine roleplay DTO 与 actor-card parser"
    - "Engine public literary facade"
    - "合同测试"
  forbidden_dependencies:
    - "Studio runtime、文件系统、模型或 Provider"
    - "直接 import Engine internal from Studio"
    - "修改已有用户工作区改动"
  tests:
    - "V4 round-trip、片段范围与输入限制合同"
    - "V3 parser/DTO 兼容回归"
    - "Engine public API re-export contract"
  rollback_unit: "独立合同提交"
  documentation:
    - "docs/implementation/creative-kernel/27-material-context-contract.md"
```
