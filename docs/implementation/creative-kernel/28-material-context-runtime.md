# Material Context Runtime Change Packet

```yaml
module_change_packet:
  objective: "将 V4 工作语境和逐次候选挂载冻结为真实调用内容，并让 Agent 看到可读的自然委托。"
  primary_module: "Studio runtimes/scene creator v2"
  public_entry: "SceneCreatorV2MaterialCoordinator.execute / MaterialInvocationV2"
  variation_point: "每次调用选中的档案、场景候选、片段和创作语境"
  inputs:
    - "Engine public SceneMaterialRequestV4"
    - "已落盘的本交易候选库与现有只读档案工作区"
    - "冻结的五类 Agent 初始化提示词"
  outputs:
    - "带来源状态、区间及摘要的候选冻结附件"
    - "逐次调用自然语言委托及可追溯材料清单"
  invariants:
    - "候选引用只从当前场景交易解析；重试读取已冻结副本"
    - "创作者札记仍是作者原文，超过合并上下文预算时明确要求缩小选择"
    - "角色已知与参考档案分区保留；其他四类只接收本次附件"
    - "非角色创作者不继承上次调用的对话附件；角色只延续自身先前呈现的言行"
    - "创作候选不晋升为 Canon，正式成稿和 Gate 语义不变"
    - "旧冻结交易的 V3 JSON 调用与记录可恢复"
  allowed_dependencies:
    - "Engine public literary contracts"
    - "SceneCreatorWorkspace 与当前交易素材文件"
    - "已有素材调用和自然输出测试"
  forbidden_dependencies:
    - "Engine internal import"
    - "Provider SDK / direct model client"
    - "正式档案写入或 Gate 副本"
  tests:
    - "候选完整挂载与字符片段冻结/摘要"
    - "缺失候选、越界范围、合并上下文超预算"
    - "自然邀请含实际选中内容并保留角色知识分区"
    - "历史 V3 交易兼容"
  rollback_unit: "Studio 场景取材 V4 runtime adapter"
  documentation:
    - "docs/implementation/creative-kernel/28-material-context-runtime.md"
```

## 实施与验证

- Engine V4 DTO 通过 `public.literary` 暴露，V3 DTO 和旧 JSON 交易继续沿用原解析合同。
- Studio 解析创作者原文札记，冻结本交易候选及半开字符片段，记录来源状态、编号、片段范围和内容 SHA-256。
- 角色卡仍作为角色初始化；角色可知与主创参考档案分开排布。其余取材者收到本次显式档案与前序素材。
- 非角色调用不携带前一次对话记录；角色的历史上下文只含此前呈现的言行，不复送上次委托和档案正文。
- 新自然邀请以可读文本呈现对象、读者效果、时刻、线索、主创札记和已选素材。旧冻结 JSON 路径保留。
- 已通过 53 项定向回归，覆盖 V3/V4、候选片段、失败后冻结重试、逐次档案隔离、自然取材接力、角色卡与旧交易恢复；提示词注册检查 59 个素材、73 个任务 ID 全部通过。
