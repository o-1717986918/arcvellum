# 空白场景模板误判导致规划阻断

2026-09-28。`吵架` 项目的自动创作于 18:39 在 `longform-planning` 阶段阻断，技术详情为 `existing authored scene scene_0001 identity or chapter differs`。当时 `scenes/scene_0001.yaml` 与随包 `templates/scene.yaml` 的 SHA-256 完全一致，`scene_id`、`chapter_id` 均为空；它是项目初始化模板，不是作者已定场景。`LeanLongformPlanningService._check_existing_first_window` 却把所有 `scene_*.yaml` 都当成已创作档案。规划修复调用再次遇到同一条件，导致自动创作阻断。Engine 物化器已有 `is_blank_scene_scaffold` 判断，能安全覆盖此模板，两个入口的判断不一致。

```yaml
module_change_packet:
  objective: "新作品的空白场景模板不阻断首次规划，已填写的场景仍受保护"
  primary_module: "Studio application/lean_longform_planning"
  public_entry: "LeanLongformPlanningService.ensure_initial"
  variation_point: "Engine public.literary 导出既有 is_blank_scene_scaffold 判定"
  inputs: ["project.yaml", "scenes/scene_*.yaml", "规划 first_window"]
  outputs: ["有效规划及物化场景", "已写场景冲突时的明确错误"]
  invariants: ["空白模板不进入模型的已填场景资料", "已写场景的章节、参与人物和容量仍须核对", "不删除或静默覆盖作者写入"]
  allowed_dependencies: ["Engine public.literary", "Studio planning service"]
  forbidden_dependencies: ["Studio 直接导入 Engine 内部 materializer", "放宽已写场景冲突检查"]
  tests: ["新项目空白模板首次规划", "已有作者场景冲突", "Engine public API", "架构审计"]
  rollback_unit: "空白场景模板识别的一次独立提交"
  documentation: ["本文件"]
```

现场运行状态与代码修复分开：项目 Agent 已在 18:53 自行重新准备规划并使自动创作进入 `character-and-world-assets`。修复代码不要求重启正在运行的开发版 API；待该会话结束后再更新服务。

## 修复与验证

Studio 首次规划的模型资料和既有场景检查现共用 Engine 物化器已有的 `is_blank_scene_scaffold` 判定；该函数经 `public.literary` 导出。空白模板不再误称为“作者已填场景”，有正文或正式输出的场景仍按既有边界核对。回归测试用项目初始化的空白场景验证一次规划成功和模板被物化，也保留原有作者场景冲突测试。相关 26 项测试及架构审计通过，模块地图已更新。
