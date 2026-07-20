# ArcVellum 发布手册

## 发布前提

Windows 安装包与 Tauri 更新包由同一提交构建。GitHub 仓库需要配置两个 Actions Secret：

- `TAURI_SIGNING_PRIVATE_KEY`：Tauri updater 私钥正文。
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`：私钥密码。

私钥不得进入仓库、构建日志、诊断包或发行附件。`desktop/src-tauri/tauri.conf.json` 只保留对应公钥。商业分发所需的 Windows Authenticode 证书是另一套机制，不应与 updater 签名混淆。

## 版本同步

版本必须同时出现在：

- `pyproject.toml`
- `src/literary_engineering_studio/__init__.py`
- `package.json` 与 `package-lock.json`
- `desktop/src-tauri/Cargo.toml` 与 `Cargo.lock`
- `desktop/src-tauri/tauri.conf.json`
- `docs/releases/vX.Y.Z.md`

本地可运行：

```powershell
python -c "from literary_engineering_studio import __version__; print(__version__)"
npm run client:build
```

## 本地候选构建

```powershell
python -m pip install -e ".[api,test]"
python -m pip install "pyinstaller==6.21.0"
npm ci
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/build_desktop.ps1 -SkipPythonInstall -SkipNodeInstall
```

构建会生成 NSIS 安装程序、Tauri updater 签名、`latest.json` 和 `SHA256SUMS.txt`，统一复制到 `dist/release/`。当前 Tauri v2 Windows 更新清单直接引用签名后的 NSIS `setup.exe`；脚本仍兼容旧版 `.nsis.zip` 产物，但不会把陈旧安装包混入当前版本。

## 正式发布

1. 完成 `docs/releases/vX.Y.Z.md`。
2. 确认工作树干净并已推送 `main`。
3. 创建并推送与 Python 版本一致的 tag：`vX.Y.Z`。
4. GitHub Actions 执行全量 Python、Prompt、Vue、Rust、sidecar、NSIS 与 updater 构建。
5. 工作流上传发行附件并创建 GitHub Release。
6. 在干净的 Windows 10/11 虚拟机验证首次安装、覆盖升级、离线启动、中文路径和卸载。
7. 用已安装旧版本检查应用内更新，确认签名、下载、安装与重启均通过。

## 回滚

更新失败时 Tauri 保留当前安装。若正式版本存在严重问题，停止发布新的 `latest.json`，保留旧附件，修复后发布更高版本；不要用同一版本号覆盖不同二进制。
