# 自然创作与审读的单次文风注入 Change Packet

```yaml
module_change_packet:
  objective: "让自然主创和审读每次只接收一份冻结文风正文，同时保留上下文中的挂载来源与版本信息。"
  primary_module: "Studio runtimes/scene natural output"
  public_entry: "briefing_for_natural_context() used by scene creator and review context builders"
  variation_point: "自然主创、自然审读及各自的后置整理上下文"
  inputs:
    - "场景交易冻结的主创文风 brief"
    - "作者指令、正式挂载和实验计量指导的来源元数据"
  outputs:
    - "文风完整正文通过对应 system prompt 提供"
    - "创作/审读上下文保留挂载状态、版本、哈希、来源路径和组合方式"
  invariants:
    - "实际 system prompt 仍持有本交易的完整文风正文"
    - "结构化旧链路的文风上下文保持原样"
    - "作者指令、挂载文风、计量组合模式与冻结摘要不变"
    - "自然输出原文和正式审读、Gate、写回合同保持不变"
  allowed_dependencies:
    - "scene_natural_output.py"
    - "natural creator/reviewer context assembly"
    - "existing stylometry snapshot and natural extraction tests"
  forbidden_dependencies:
    - "prompt invention or alternate style source"
    - "provider-specific cost estimates"
    - "changing style measurement or literary judgment"
  tests:
    - "system prompt still receives the frozen full style"
    - "natural generation/review context omits duplicated style body but retains metadata"
    - "the source briefing is not mutated"
  rollback_unit: "natural-context style body projection"
  documentation:
    - "docs/implementation/creative-kernel/34-single-style-delivery-change-packet.md"
```

## 依据

自然创作器与审读器已分别通过 system prompt 收到 `creator_style(briefing)` 的冻结文风。原始 briefing 又以 JSON 随用户轮次发送，并进入后置整理任务，因此同一文风会在多个请求中重复出现。此次仅压缩自然链路的冗余副本，保留版本、哈希、挂载状态、来源和组合模式以便审计；结构化旧交易及其上下文不变。
