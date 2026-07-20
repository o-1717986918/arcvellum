# Phase 59: Style Skill Package

本阶段新增可挂载的 `Style Skill` 包。

`style-lab-compile` 会复用现有 `style-profile` 和 `style-prompt` 链路，从作家作品语料生成 profile、metrics 和 LLM-facing style prompt。

`style-lab-build-skill` 会输出：

- `style_skill.json`
- `STYLE.md`
- `prompt.md`
- `style-profile.md`
- `style_metrics.json`
- `corpus_manifest.yaml`

`Style Skill` 是项目内的文风模块协议，不等同于 Codex 安装型 `SKILL.md`。它的目标是被创作项目挂载，并在生成、审查和总监决策中作为最高优先级表达约束。
