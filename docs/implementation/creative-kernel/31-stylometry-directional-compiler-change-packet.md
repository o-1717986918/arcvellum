# 计量文风方向化编译 Change Packet

```yaml
module_change_packet:
  objective: "滑块目标区间改变后，主创挂载的文学指导会随指标及相对作者样本的方向变化。"
  primary_module: "src/stylometric_prompt_lab/creator_fragment.py"
  public_entry: "compile_creator_fragment(profile, controls, title, intent, dependency_parse)"
  variation_point: "启用指标的目标范围相对来源画像四分位区间的位置"
  inputs:
    - "已校验摘要的 stylometric-profile/v1"
    - "与画像绑定的 stylometric-creator-controls/v1"
  outputs:
    - "含指标名、单位、样本范围、目标范围与对应文学方向的冻结提示词片段"
    - "递增的编译器版本和现有来源摘要"
  invariants:
    - "保留每项计量值、单位、指标来源和目标范围"
    - "把统计目标表达为整篇写作倾向，不生成逐句配额"
    - "编译输出保持正向创作引导，计量效果继续标记 not-verified"
    - "不可变已保存版本及场景交易快照不变"
  allowed_dependencies:
    - "stylometric_prompt_lab 既有画像、指标目录与依存参考函数"
    - "现有 Stylometry Service / Lab adapter 合同测试"
  forbidden_dependencies:
    - "Studio 数据库或档案写入"
    - "Provider 调用、文学 Gate 或生成效果宣称"
    - "新增测量算法或客户端自行推算统计"
  tests:
    - "目标落在样本区间内、低于样本、高于样本时分别编译出恰当指导"
    - "主轴、次级、语法词与依存目标均按指标定义给出方向"
    - "摘要、单位、范围校验及来源绑定保持"
    - "输出无逐句数值配额和反向禁令模板"
  rollback_unit: "directional creator fragment compiler v1.1"
  documentation:
    - "docs/implementation/creative-kernel/31-stylometry-directional-compiler-change-packet.md"
```

## 完成标准

- 改变同一滑块的目标方向会改变对应文学指导；目标仍落在来源四分位范围时保留观察型描述。
- 四主轴、九个次级目标、语法词频和七个依存目标都有明确的指标语义。
- 数值仍与其单位、来源画像和目标区间绑定；自动标注误差和生成效果未验证状态继续呈现。

## 实施与验证

- 提示词编译器升至 `creator-1.1`。每项启用目标同时显示来源中位数、四分位范围与用户目标；目标完全落在样本中段下方/上方时，分别切换到对应指标的文学化方向，区间重叠时沿用观察型指导。
- 四个主轴、九个次级指标、频率词和七项依存指标各有方向化描述；范围仍作为整篇分布的写作方向，逐场表达跟随人物与场景变化。
- `generation_effect` 保持 `not-verified`。23 项文风导入、服务/API、挂载、主创消费和编辑共享快照回归通过，其中包含三个新编译器合同测试；compileall、架构审计、模块图与 59 项提示词资产/73 项任务绑定校验通过。
