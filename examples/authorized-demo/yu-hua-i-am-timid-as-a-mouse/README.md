# 《我胆小如鼠》单篇授权演示输入

此目录只提供合同示例，不包含原文或授权凭据。生产演示范围固定为余华《我胆小如鼠》单篇，不接收同名作品集中的其他作品，也不以生成内容补足字数。

仅在本机进行私人研究时，可使用 `manifest.private-research.example.json`：该模式不要求授权凭据，只校验用户提供的源文件和自证声明，但不能生成桌面演示包或 GitHub Release 资产。可分发版本继续使用 `manifest.example.json` 并提供相应凭据。

## 本地材料结构

在仓库外建立一个受控目录，例如：

```text
authorized-i-am-timid-as-a-mouse/
├── manifest.json
├── source/
│   └── primary.docx
└── rights/
    └── authorization.pdf
```

1. 将 `manifest.example.json` 复制为本地 `manifest.json`。
2. 填写准确版本、权利方、被授权主体、授权摘要和分发范围。
3. 计算原文与凭据的 SHA-256 和字节数，替换全部占位值。
4. `source_files` 只能声明《我胆小如鼠》单篇的一个合并后主文件。
5. 只有授权明确包含公开 Release 时，才增加 `github_release_asset` scope。

## 构建命令

先准备一个持久 workspace，让正式 source-ingest、资产提取、审查和晋升任务在其中留下可验证凭据：

```powershell
python scripts/build_authorized_demo_bundle.py `
  --source-root D:\secure\authorized-i-am-timid-as-a-mouse `
  --manifest D:\secure\authorized-i-am-timid-as-a-mouse\manifest.json `
  --workspace D:\ArcVellumBuild\yu-hua-i-am-timid-as-a-mouse `
  --version 1.0.0
```

第一次运行会创建来源项目；在 ArcVellum 中完成该 workspace 的人物、世界、情节、场景、文风、节奏和账本任务后，重新运行同一命令。只有完整性审计通过时，脚本才会生成可安装的 `.arcvellum-demo`。

若目标包含 GitHub Release，追加 `--github-release`。脚本会要求 manifest 同时声明对应授权 scope；技术校验不会替代法律审查。

## 保密边界

- 不把 `source/`、`rights/` 或本地 `manifest.json` 提交到 Git。
- 授权凭据原件不会进入演示包。
- 演示母本只读；用户需要续写或改写时必须先“复制为可编辑作品”。
