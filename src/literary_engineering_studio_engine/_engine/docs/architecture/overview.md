# 架构总览

文学工程工作台把长篇虚构创作拆成可维护工程：

当前发布形态是项目型 Skill：Codex、Claude 等工具层 agent 是项目总监、创作总监、真实 LLM provider 和子 agent 编排者；本仓库提供规则、模板、schema、文风机制、artifact contract 和可选本地 CLI/API 工具箱。旧的本地 `director-chat`、FastAPI、LangGraph 和 Dify 路线保留为可选集成，不再是主交互入口。

- `canon/`：世界观、事实、规则和不可违背约束。
- `characters/`：人物档案、BDI、语言习惯、关系和成长弧。
- `plot/`：章节、场景、伏笔、时间线和轻量图谱。
- `style/`：公版或授权语料形成的风格 profile。
- `sources/`：已有文本、旧稿、完整作品和剧本材料的导入、分块和反推任务。
- `memory/`：轻量索引和上下文包。
- `drafts/`：草稿工作台。
- `reviews/`：审查报告和质量闸门。
- `workflow/`：运行状态、日志和人工确认记录。

系统先以 CLI 和文件产物稳定节点契约，再接 LangGraph、Dify 和知识库。
