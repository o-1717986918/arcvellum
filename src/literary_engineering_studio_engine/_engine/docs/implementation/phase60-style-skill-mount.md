# Phase 60: Style Skill Mount

本阶段实现文风挂载。

`style-lab-mount` 会把全局文风库中的 style skill 复制到创作项目：

```text
style/mounted/{style_id}/
style/active_style_skill.json
```

同时更新 `project.yaml` 的 `style` 区块，记录：

- `active_style_skill`
- `priority: highest`
- `mount_path`
- `target_profiles`
- `blend_strategy`

挂载后，创作项目拥有明确的 active style skill，后续生成和总监状态都能读取这一约束。
