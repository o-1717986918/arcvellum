# 角色沉浸要求追加条目（2026-09-24）

## Engine Module Change Packet

```yaml
module_change_packet:
  objective: "在所有角色首条初始化提示中追加用户指定的第 4、5 条沉浸要求"
  primary_module: "literary/scene/roleplay"
  public_entry: "public.literary.render_actor_initialization_prompt"
  variation_point: "仅扩展沉浸要求的编号条目，不改变人设气质、身份句和后续任务单"
  inputs: ["姓名", "主创人设气质", "身份与处境"]
  outputs: ["原前三条 + 新第 4、5 条的角色初始化提示"]
  invariants: ["身份句后的空行保留", "角色气质输入保留", "候选不得直接晋升正文或 Canon"]
  allowed_dependencies: ["Engine 当前角色初始化函数与合同测试"]
  forbidden_dependencies: ["Provider SDK", "Studio runtime", "新增审查门禁"]
  tests: ["完整初始化提示精确文本测试", "任务单仍在后续消息"]
  rollback_unit: "Engine 沉浸提示两条增量"
  documentation: ["本记录"]
```

## Studio Experiment Module Change Packet

```yaml
module_change_packet:
  objective: "让实验与正式模板一致，并使已有作品不复用旧提示生成的缓存"
  primary_module: "runtimes/scene_performance 与 pi-worker 隔离实验入口"
  public_entry: "scene_performance_materials / actor-roleplay-spike.mjs --directed-cute-catgirl"
  variation_point: "实验首条消息增加同样条目；创作缓存版本递增"
  inputs: ["原七轮对戏场景", "同一角色初始化身份与气质"]
  outputs: ["新版本候选缓存键", "逐轮真实模型记录"]
  invariants: ["旧试验记录保留", "导演七轮来话不改", "角色会话无工具、无正式写权"]
  allowed_dependencies: ["现有 Pi Agent Core 实验脚本", "Engine public.literary"]
  forbidden_dependencies: ["正式正文写回", "新增阻断规则"]
  tests: ["脚本语法", "真实模型试跑", "缓存版本与原文核对", "架构审计"]
  rollback_unit: "Studio 缓存与试验脚本增量"
  documentation: ["本记录"]
```

## 结果

角色首条消息现保留姓名、主创提供的气质、身份处境、语言风格引导及其后的空行；在原第 1–3 条之后，原样追加所请求的第 4、5 条。第 4 条与第 3 条重复，这是本轮明确指定的文本，未擅自合并。用户粘贴内容尾部的孤立引号与 `&#x20;` 是格式残留，未进入实际提示。

两条调用路线分别实测：

- **逐轮对戏**：`deepseek/deepseek-v4-flash`，周岑和许遥各一条持久角色会话，共 7 轮；每轮均有非空回复，没有中断。完整首条提示、来话及原始回复见 `build/scene-performance-e2e/interactive-roleplay-directed-cute-catgirl-immersive5-20260924/transcript.json`，便于阅读的整理见同目录 `materials.md`。观察到角色延续了彼此的回应，但也虚构了精确时间、耗油比例、设备细节及若干尚未确定的情节事实。这说明条目追加不破坏对话，却不能单独保证世界事实一致或文风质量。
- **原正式任务单复测**：从既有许遥运行记录读取第二条任务单，保持其文本不变；第一条替换为新通用初始化，在新数据目录中调用角色会话。返回可解析 JSON，`scene_id=scene_0001`、`speaker=许遥`、`entries=11`，原始 prompt、运行事件与回答见 `build/scene-performance-e2e/actor-immersive5-task-sheet-20260924/studio-data/character-actor/runs/run-1790259305531/`。这验证了“和其他角色对话”的首条要求没有立即打断该次结构化候选输出；并非证明所有任务单或正式正文晋升路线均通过。

回归检查：49 个相关 Python 测试通过；Pi Worker `npm run check` 通过（11 组、108 测试）；脚本语法、Python 编译、架构审计、模块图、提示资产验证和 `git diff --check` 均通过。Studio 创作缓存版本从 `performance-v26` 升为 `performance-v27`，避免旧初始化的角色候选被当成新提示结果。角色会话的隐式思考是否真的全程保持第一人称，无法仅凭最终输出证明；本轮只确认提示已发送且最终回复可用。
