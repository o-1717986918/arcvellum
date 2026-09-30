# 强风格化角色卡与 v2 待设计清单

## Module Change Packet

~~~yaml
module_change_packet:
  objective: "主创按示例向极度风格化、特色化方向填写角色卡"
  primary_module: "Engine prompting"
  public_entry: "scene.v2.creator.actor-card / public.prompting"
  variation_point: "作品类型、作者意图、人物自身的表达逻辑"
  inputs: ["用户示例", "人物档案", "作品主创人格", "SceneBrief"]
  outputs: ["主创填卡任务 v2", "对应审阅与导入文件", "v2 待设计提示词清单"]
  invariants: ["保留 16 区块合同", "同场角色卡冻结", "事实与知识边界", "v2 未激活"]
  allowed_dependencies: ["Engine public prompting", "Engine public literary", "独立提示词设计台元数据"]
  forbidden_dependencies: ["正式档案写入", "新增模型调用", "修改文学 Gate"]
  tests: ["现有角色卡及提示词合同测试", "注册表校验", "设计台导出一致性"]
  rollback_unit: "强风格化填卡任务的独立提交"
  documentation: ["本记录", "outputs 中的 v2 待设计清单"]
~~~

## 实施意图

用户要求将风格化和个人辨识度作为填卡的首要设计目标。主创从示例学习强度、组织方式和跨区块呼应，主动设计少数贯穿人物的鲜明主轴，细化声线、选择性注意、身体节奏、关系反应和反差。身份与经历继续由档案约束；语言和行为的演绎设计可以充分发挥，记录于 design_notes。

角色卡仍有 16 个固定区块。此次修改任务文案及其资产版本，不增加合同字段或模型调用。角色系统模板沿用原卡结构，v2 的其他 18 位仍占位。

## Packet B：角色卡来源校验的复杂度修正

~~~yaml
module_change_packet:
  objective: "修复完整架构检查发现的角色卡解析复杂度超限"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "public.literary.parse_actor_character_card"
  variation_point: "none"
  inputs: ["原角色卡 JSON 合同"]
  outputs: ["同一验证后的 ActorCharacterCardV1"]
  invariants: ["来源引用数量和长度限制不变", "错误语义不变", "角色卡预算不变"]
  allowed_dependencies: ["Engine 文学合同"]
  forbidden_dependencies: ["Studio", "Provider", "架构 baseline 修改"]
  tests: ["现有角色卡合同及 runtime 回归", "完整 architecture_audit"]
  rollback_unit: "来源引用校验函数拆分"
  documentation: ["本记录"]
~~~

上一轮新文件进入 Git 后，架构扫描纳入该解析函数并识别复杂度 16 超过 15 的预算。将来源引用校验单独组织为纯函数，保留原限制。模块地图同步补记此前新增的已入库文件数量。

## 验证与剩余工作

22 项既有提示词、角色卡和 v2 runtime 测试通过；compileall、完整 architecture_audit、注册表校验、模块地图一致性和 diff --check 通过。设计台脚本语法及 20 个 ID 一致性检查通过。

默认注册资产中 2 位为草稿、18 位为占位。完整清单和导入 JSON 已同步到审阅包。原有顶层六位继续有内容，但需在 v2 启用前复审人格初始化和职责交接。真实模型文学效果对照仍未运行，v2 保持未激活。
