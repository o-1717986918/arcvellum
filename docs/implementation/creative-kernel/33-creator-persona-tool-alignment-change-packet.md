# 主创人格提示词与工具对齐 Change Packet

```yaml
module_change_packet:
  objective: "让顶层人格生成模板所指示的读取与更新操作对应到实际注册的 Project Agent 工具。"
  primary_module: "Project Agent prompt policy / creator persona prompt asset"
  public_entry: "creator_persona_guidance() + available_read_tools() + available_action_tools()"
  variation_point: "V2 场景主创开关开启且当前作品存在时，顶层 Agent 获得人格维护指导"
  inputs:
    - "当前作品用户创作意图与档案"
    - "prompt_layer_spec('project_agent.creator_persona.v2')"
    - "Project Agent 允许的读取与动作工具名"
  outputs:
    - "可执行的主创人格初建/更新指引"
    - "按工具合同保存的版本化人格与更新理由"
  invariants:
    - "提示词中的工具标识与 Studio 注册工具名逐字一致"
    - "V2 的启用条件和人格存储语义保持"
    - "人格更新仍由用户明确改变创作意图触发"
    - "不改变场景交易中的人格快照和旧交易行为"
  allowed_dependencies:
    - "Project Agent prompt policy"
    - "Project Agent tool registry"
    - "Engine public prompt asset registry"
  forbidden_dependencies:
    - "Provider transport"
    - "自动写入作品档案或改动正式审读/写回状态"
  tests:
    - "提示词引用的读取工具存在于 READ_TOOLS"
    - "提示词引用的更新工具存在于 ACTION_TOOLS"
    - "人格工具调用及版本保存既有合同继续通过"
  rollback_unit: "project_agent.creator_persona.v2 asset v5"
  documentation:
    - "docs/implementation/creative-kernel/33-creator-persona-tool-alignment-change-packet.md"
```

## 实施

- 将人格提示词中的 `creator_persona_read` / `creator_persona_update` 更正为实际注册名 `project_creator_persona_read` / `project_creator_persona_update`。
- Prompt 资产升为 package version 5。
- 增加合同测试，令提示词提及的工具名同时与 Prompt 文案及 READ/ACTION 注册表对照。
- 人格版本化读取、更新、V2 启用条件和场景交易快照保持原行为。
