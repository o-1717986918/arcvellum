# 版本管理规则

从 `recovered-baseline-0.11.0` 起，本工程使用 Git 管理版本。

## 当前基线

- 分支：`main`
- 基线标签：`recovered-baseline-0.11.0`
- 基线含义：误删影响初步恢复后的可运行版本，包含源码、文档、模板和测试。

## 工作前检查

每次修改前先运行：

```powershell
git status --short
git log --oneline --decorate -5
```

如果存在未知改动，先判断来源，不直接覆盖。

## 提交粒度

推荐按以下粒度提交：

- `docs:` 文档恢复或设计说明。
- `test:` 测试恢复、覆盖补充。
- `feat:` 新能力。
- `fix:` bug 修复。
- `chore:` 工程配置、打包和清理。

一个提交只做一类事情，便于回滚。

## 不入库内容

`.gitignore` 已排除：

- Python 缓存：`__pycache__/`、`*.pyc`
- 构建元数据：`*.egg-info/`、`dist/`、`build/`
- 本地语料和作品工作区：`corpus/`、`work/`
- 临时文件、日志和生成 zip

如需发布 zip，先在仓库外生成，并记录路径和 SHA256。

## 恢复流程

如果再次发生误删：

```powershell
git status --short
git restore --source=HEAD -- <path>
```

如果要回到当前恢复基线：

```powershell
git switch main
git checkout recovered-baseline-0.11.0
```

注意：不要在不确认用户改动来源的情况下执行大范围还原。

## 当前恢复结论

- 源码规模已扩展到 43 个 Python 源文件。
- 文档规模已覆盖 Phase 1-48、架构、集成和维护入口。
- 测试规模已恢复并扩展到 34 个测试文件、113 个模块级回归用例。
- LangGraph / FastAPI / Dify、Agent 设定创作层和顶层创作总监入口均已保留在 Git 版本管理中。
