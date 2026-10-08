# Project Agent 主创人格初始化服务流 Change Packet

```yaml
module_change_packet:
  objective: "以无模型服务级验收连通主创人格提示、真实工具目录、版本存储与读取回执。"
  primary_module: "Studio Project Agent service / creator persona tools"
  public_entry: "ProjectAgentService.run_turn()"
  variation_point: "scene_creator_v2.enabled 且当前会话绑定正式作品"
  inputs:
    - "用户创作方向"
    - "project_agent.creator_persona.v2"
    - "CreatorPersonaStore"
  outputs:
    - "带人格初始化模板的 Project Agent system prompt"
    - "读到的空状态、由 Project Agent 工具保存的 v1 人格及版本记录"
  invariants:
    - "顶层只使用已注册的 project_creator_persona_read/update 工具名"
    - "人格仍绑定作品方向摘要并以版本方式保存"
    - "场景交易只读取已保存版本；本测试不启动场景、不调用模型"
    - "V2 的配置开关、旧人格、Canon、审读和写回语义保持"
  allowed_dependencies:
    - "ProjectAgentService"
    - "ProjectAgentToolDispatcher 与实际读/写工具注册表"
    - "CreatorPersonaStore"
    - "Engine public prompt layer registry"
  forbidden_dependencies:
    - "Provider 或模型调用"
    - "作品档案写入、正式正文和 SceneDelta 写回"
  tests:
    - "system prompt 带入人格初始化任务，用户方向进入该轮输入"
    - "allowed_tools 同时公开已注册的人格读取和更新工具"
    - "空状态被读取，更新结果可由同一 store 读回"
    - "人格保存仍通过来源摘要和理由合同"
  rollback_unit: "Project Agent persona service integration test"
  documentation:
    - "docs/implementation/creative-kernel/35-project-agent-persona-flow-change-packet.md"
```

## 实施与范围

新增一条 fake-runtime 服务级验收，将现有提示词解析、Project Agent 工具编排和 CreatorPersonaStore 串起来。它只证明工程路径可以闭合；人格是否充分反映作者意图以及文学效果仍须真实交互和人工阅读判断。
