# 角色卡结构与旧稿全文入口（2026-10-03）

## Packet A：角色卡只保留结构

~~~yaml
module_change_packet:
  objective: "按用户要求移除角色卡前的说明，模板只保留 16 个区块及占位符"
  primary_module: "Engine prompting"
  public_entry: "public.prompting: scene.v2.material.actor"
  variation_point: "角色卡模板文字"
  inputs: ["当前角色卡模板", "用户明确删除的前言"]
  outputs: ["版本 3 的纯结构模板"]
  invariants: ["16 个占位符各一次", "角色卡数据合同与渲染保留", "已开始交易保持原快照"]
  allowed_dependencies: ["Engine public prompting/literary"]
  forbidden_dependencies: ["Runtime 权限变更", "档案写回", "自动启用 v2"]
  tests: ["角色卡与运行时合同回归", "提示词注册表"]
  rollback_unit: "纯结构角色卡模板"
  documentation: ["本记录"]
~~~

## Packet B：旧提示词全文直接可见

~~~yaml
module_change_packet:
  objective: "旧稿全文默认展示，有明确切换按钮与可点击的旧提示词入口"
  primary_module: "tools/prompt-design-desk"
  public_entry: "离线 HTML 与 prompt-design-submission/v2"
  variation_point: "新旧稿显示和角色模板版本迁移"
  inputs: ["注册内置稿", "历史角色卡 v2 原文", "浏览器现有稿"]
  outputs: ["全文可见的旧稿入口", "保留用户文字的角色卡前言精确移除"]
  invariants: ["旧稿原文保真", "用户其他填写保留", "改动已通过正文取消通过", "不修改运行配置"]
  allowed_dependencies: ["只读 Engine public prompting", "浏览器存储"]
  forbidden_dependencies: ["联网", "正式档案 mutation"]
  tests: ["旧稿默认全文", "新旧切换", "点击旧 ID", "精确迁移保留区块及备注"]
  rollback_unit: "旧稿可见性与卡模板迁移"
  documentation: ["本记录", "评审台 README"]
~~~

## 实施与验证

- 角色卡模板版本 3 从 PERSONA_LOAD 开始，只含 16 个区块与占位符；角色卡数据 schema 与填卡任务保留。
- 页面左侧默认展示关联旧稿全文。新增“查看旧提示词”“查看 v2 初稿”按钮；关联旧 ID 可直接点击查看全文。来源合计 64 个，包含历史 v2 角色卡。
- 浏览器保存稿及导入稿中的已删除前言仅作精确移除；区块内的用户修改和备注保留，正文变动取消通过。
- 历史卡摘要与旧 stylized 评审 ZIP 一致。模板、当前填写页和渲染示例已重新生成。
- Python 全量 1685 项，1 项跳过，0 失败；角色卡／v2／注册层定向 21 项通过。
- DOM 验证覆盖默认旧稿全文、新旧切换、旧 ID 点击、旧稿采用，以及带用户修改的保存稿／导入稿前言移除。快照 Python 测试 2 项通过。
- client:test、client:build 与 pi-worker:check 通过，Worker 121 项通过；架构、模块图、注册表、compileall、diff check 通过。
- Engine 模板独立提交 3bb6ae8；其余为独立工具与产物更新。

运行开关未更改。浏览器本地页面访问此前被工具策略拒绝，实际桌面／移动截图和渲染检查仍未完成；DOM 验证仅记录操作行为。
