# 桌面星仪纵深一致性修正

```yaml
module_change_packet:
  objective: "桌面安全策略下正常启用星仪 WebGL 天幕和视差层"
  primary_module: "Vue orrery renderer"
  public_entry: "NarrativeParallaxRenderer.create"
  variation_point: "Pixi shader and uniform synchronization under CSP"
  inputs: ["既有星仪投影和布局", "桌面 CSP"]
  outputs: ["保留远中近层的 WebGL 星仪"]
  invariants: ["不放宽 CSP", "保留相机、交互和静态备用路径", "不改文学数据", "不打包或发布桌面安装包"]
  allowed_dependencies: ["Pixi 官方 CSP 兼容入口", "既有星仪渲染模块"]
  forbidden_dependencies: ["新增 unsafe-eval 权限", "后端或 Engine 逻辑修改"]
  tests: ["与桌面等效的脚本限制下浏览器修正前后对照", "星仪既有测试", "前端生产构建", "架构检查"]
  rollback_unit: "本批渲染入口与 CSP 回归夹具差异"
  documentation: ["本文", "透明 UI 设计方案及可交互候选"]
```

源码证据：桌面 CSP 的 script-src 没有 unsafe-eval；Pixi AbstractRenderer 默认 _unsafeEvalCheck 在相同环境下抛错。星仪初始化异常被 NarrativeParallaxStage 捕获后进入 staticProjection，备用界面缺少程序化天幕。Pixi 提供的 pixi.js/unsafe-eval 入口名称容易误解，实际内容是无动态代码执行的兼容实现，替换 uniform / shader 同步函数，并不增加页面权限。

透明 UI 仅制作独立设计候选，本批不把透明参数直接应用到产品界面。

## 验证记录（2026-10-18）

- CSP 回归夹具调用实际 NarrativeParallaxRenderer，禁止 unsafe-eval。修正前初始化失败，错误为 “Current environment does not allow unsafe-eval”；修正后通过。
- 修正后检查 WebGL canvas、静止背景时拖动相机造成的画面变化、CSP 违规及页面脚本错误；1440×900 与 390×844 均正常，未发现水平溢出。
- `npm run client:test`：94 个测试文件、302 项测试通过。
- `npm run client:build`：类型检查、生产构建及 166 项前端资源校验通过；只同步静态前端资源，未运行桌面安装包构建。
- 架构检查与模块映射一致性通过；现有债务为 15 个文件、68 个函数，无新增循环依赖。
- 独立透明候选完成 1440×1000 与 390×844 截图及面板边界检查；对话、档案、材质切换和收起 UI 单独验证。

边界：使用 Chromium 在等效的脚本限制下验证，未对新安装后二进制或原生 WebView 实测；本批未打包、发布或替换现有桌面程序。宿主界面检查工具无法启动，浏览器回归用于验证代码路径，不作为已安装桌面程序的实测声明。
