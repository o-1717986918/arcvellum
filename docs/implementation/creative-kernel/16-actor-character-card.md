# 主创填写角色卡与角色系统模板

## Packet A：角色卡合同与模板

~~~yaml
module_change_packet:
  objective: "主创按用户示例填写角色卡，作为角色 Agent 的系统人格"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "public.literary 的 ActorCharacterCardV1"
  variation_point: "人物、关系、知识和当前阶段"
  inputs: ["场景参与者", "角色卡 sections", "来源引用", "角色系统模板"]
  outputs: ["验证后的角色卡", "填充后的系统提示词"]
  invariants: ["角色卡不写 Canon", "主创独写正文", "未知参考资料不能成为角色知识"]
  allowed_dependencies: ["Engine literary", "Engine prompting"]
  forbidden_dependencies: ["Studio 文件系统", "Provider SDK", "正式 Gate 副本"]
  tests: ["角色卡完整性", "目标一致性", "模板占位符", "请求兼容"]
  rollback_unit: "角色卡合同与提示词资产"
  documentation: ["本记录"]
~~~

## Packet B：场景角色卡冻结

~~~yaml
module_change_packet:
  objective: "首轮角色调用使用主创填好的角色卡，后续调用沿用卡和经历"
  primary_module: "Studio runtimes"
  public_entry: "SceneCreatorV2MaterialCoordinator"
  variation_point: "每个参与者的场景角色卡"
  inputs: ["SceneMaterialRequestV3", "事务提示词快照", "冻结附件"]
  outputs: ["角色系统提示词", "角色卡摘要与调用记录"]
  invariants: ["同场角色卡冻结", "无第二个规划 Agent", "不自动继承旧标签提示词", "v1 兼容"]
  allowed_dependencies: ["Engine public literary/prompting", "Studio 场景缓存"]
  forbidden_dependencies: ["正式作品写入", "直接 Provider 调用"]
  tests: ["首轮卡必填", "后续复用", "变更拒绝", "中断恢复", "v1 回归"]
  rollback_unit: "v2 角色初始化 adapter"
  documentation: ["本记录"]
~~~

## 模板来源与整理

本次依据用户提供的五份文本。file_260929_140759_78965.txt 包含庄方宜的多个版本和李织烟示例，并有重复段落、粘连标题；四份 code_20260930*.txt 分别为奶糖、春日步、御坂美琴、鸣人示例。

保留共同的身份、自称、四层人格、行为模式、动作库、台词例句、饮食偏好和真实行为结构；同时保留部分示例的核心／公开／私下／矛盾／摘要五个补充区块。每个区块只出现一次，标签后必须有可读中文说明。

独处、告白、绝对服从、语言口癖及具体动作均是示例角色的值，不能成为所有人物的默认值。私下状态由场景和关系触发；没有档案支持时填写资料不足或不适用。来源引用、设计备注留给主创与系统，不注入角色知识。

## 装配与范围

- scene.v2.material.actor：带 16 个区块占位符的角色系统模板。
- scene.v2.creator.actor-card：主创填写角色卡的任务提示，新增独立可编辑位。
- actor 请求可携带 character_card。首轮必须提供；之后可以省略以复用同场冻结卡。
- 固定权限协议、填好的角色卡、候选输出协议按顺序装配到角色 system prompt。旧的稳定标签作为主创参考输入，不额外拼成第二个人格。
- 角色卡和摘要保存在场景事务目录，不自动成为人物档案或 Canon。角色卡变更应进入新的场景事务。
- 新增位后设计台为 20 位；其余占位未设计，因此 v2 整体继续未激活。

## 配套设计台与交付

现有独立设计台增加填写角色卡这一位，仍使用原导出 schema。旧 19 位文件可以导入，新位保持空白；不会自动覆盖浏览器草稿。两份提示词作为 draft 提供可导入 JSON，等待用户继续设计。

v2 pending_request 批次预算为 160000 字符，以保存完整角色卡并支持中断恢复；超出明确报错。v1 保留 8000 字符默认预算。本次定向验证发现原 test_prompt_layers 将已存在的 scene.creator.identity v3 误写为 v2，已只修正测试期望，旧版提示词未改变。

## 验证事实

- 68 项角色卡、v2 委托、提示词注册、公开接口、主创意图及旧场景执行测试通过。
- 102 项沙盒、预检、Worker 执行与恢复、正式状态写回、作品初始化和项目 adapter 测试通过。
- 顶层 Project Agent 73 项测试通过；Pi Worker 编译及 121 项测试通过。
- compileall、architecture_audit、prompt-registry-validate、generate_module_map --check 和 diff --check 通过；未修改架构 baseline。
- 独立设计台脚本语法检查通过，20 个提示词位与 Engine 注册表相符；春日步示例卡经公开合同解析并完整填充系统模板。
- 未运行真实模型文学效果对照。浏览器对本地页面访问的限制使设计台视觉检查未完成；无替代访问绕过。

合同与模板提交：45dd7d3；顶层人格初始化提交：e0bc0eb。主创运行 adapter 独立提交，用户已有规划模块修改未纳入以上提交。
