# 角色初始化：人设气质与统一语言引导（2026-09-24）

## Engine Module Change Packet

```yaml
module_change_packet:
  objective: "保留主创给每名角色的人设气质输入，按用户指定结构生成首条角色扮演提示"
  primary_module: "literary/scene/roleplay"
  public_entry: "public.literary.render_actor_initialization_prompt / render_performance_plan_prompt"
  variation_point: "actor_prompts 改为简短人设气质短语；通用语言引导固定于身份句后"
  inputs: ["角色姓名", "角色身份与处境", "主创填写的人设气质"]
  outputs: ["身份句、统一语言引导、空行、原角色沉浸要求"]
  invariants: ["actor_prompts 和 actor_tasks 继续由主创分别填写", "任务单留在后续消息", "不改角色输出或晋升门禁"]
  allowed_dependencies: ["Engine 公共文学入口", "现有场景表演合同"]
  forbidden_dependencies: ["Studio runtime", "Provider SDK", "项目正式写回"]
  tests: ["通用提示精确文本测试", "主创人设气质字段合同测试"]
  rollback_unit: "Engine 角色初始化提示变更"
  documentation: ["本记录"]
```

## Studio Adapter Module Change Packet

```yaml
module_change_packet:
  objective: "让正式场景与隔离试验实际采用新提示，而非复用旧缓存或旧试验文字"
  primary_module: "runtimes/scene_performance 与 pi-worker 隔离实验入口"
  public_entry: "scene_performance_materials / actor-roleplay-spike.mjs --directed-cute-catgirl"
  variation_point: "缓存版本更新；实验入口按同一结构初始化两名角色"
  inputs: ["Engine 的 actor_prompts", "现有角色与七轮导演来话"]
  outputs: ["新缓存键", "可核对的真实模型 transcript"]
  invariants: ["不更改七轮剧情要求", "旧试验输出保留", "角色会话无工具、无正式写权"]
  allowed_dependencies: ["Engine public.literary", "现有 Pi Agent Core 实验脚本"]
  forbidden_dependencies: ["正式项目正文写回", "新增审查门禁"]
  tests: ["缓存版本检查", "角色初始化精确差异核对", "定向单元测试", "真实模型试跑", "架构审计"]
  rollback_unit: "Studio 缓存版本与隔离脚本更新"
  documentation: ["本记录"]
```

## 结果

**通用初始化已改为“人设气质 + 角色身份 + 统一语言引导”，并保留主创对每个人设气质的输入。** 这像先给演员一句能认出自己的介绍，再让同一条宽松的语言引导发挥作用。主创仍填写 `actor_prompts`，但它现在被明确说明为简短的人设气质短语，可同时含身份与性情；`actor_tasks` 仍留在第二条场景任务消息。许遥的试验输入为“可爱的猫娘”，没有再叠加“御姐、泼辣”等另一组气质词。

许遥本轮实际收到的第一句为：“你是许遥，可爱的猫娘，走私飞行员，天亮前执最后一班离港，去留未定但风险明确。语言风格高度符合人设，表达饱满、松弛，愿意把情绪和想法说充分。”随后恰有一个空行，再进入原有的【角色沉浸要求】三条；这一点由通用函数精确文本测试和真实试跑的逐字记录共同核对。实验脚本中的角色系统提示为空，初始化作为首条会话输入。

**改动没有触碰角色候选的正式边界。** 七轮隔离试跑完成，两名角色各复用自己的无工具会话，七段原文逐字写入候选清单；周岑在这次样本中亲手接入了载体。但模型也自造了记忆债规则、设备细节和燃料比例，因此这只是验证提示结构确实送达，不证明正文文风或情节可靠性已经解决。没有调用正式主创修订、审查、晋升或 Canon 写回。

运行时的场景创作缓存版本由 v25 更新到 v26，使已有作品下次生成不会复用旧结构产出的候选。定向 Python 测试 49 项、Pi Worker 测试 108 项、脚本语法、源码编译、架构审计、模块图、提示词注册表和 `git diff --check` 均通过。真实模型验证仅覆盖隔离试验入口，尚未运行正式项目的完整主创路线。

## 依据

- 通用模板与导演人设输入：`src/literary_engineering_studio_engine/literary/scene/roleplay/performance.py`；缓存版本与角色调用：`src/literary_engineering_studio/runtimes/scene_performance.py`。
- 实跑初始化、逐轮原文和会话：`build/scene-performance-e2e/interactive-roleplay-directed-cute-catgirl-template-20260924/transcript.json`；可读候选清单在同目录 `materials.md`。
