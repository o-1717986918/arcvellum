# Phase 58: Author Style Projects

本阶段新增 `style_lab.py`，把文风学习从单次 profile 工具升级为作家中心的工程项目。

结构：

```text
style-library/
  authors/{author_id}/
    author.json
    works/{work_id}/
      work.json
      sources/raw/
      sources/normalized/
      sources/chunks/
    profiles/
    style_skills/
```

一个作家是一个文风项目，一部作品是一个子项目。作品文本导入后同时保留 raw、normalized 和 chunks，便于后续统计、LLM 分析和可追踪审计。
