# Ryan_DAM

本项目是面向个人创作者的本地资产管理工具。产品需求见 docs/Ryan_DAM_Product_Spec_v1.md。

## 阶段 0 已实现的工程骨架

- Electron + Vue 3 + TypeScript + Vite 桌面客户端。
- Electron 启动本地 FastAPI 子进程；后端动态绑定 127.0.0.1 的可用端口并输出就绪消息。
- 每次启动生成随机 API token，校验请求令牌、Host 和 Origin。
- 窗口尺寸、位置与最大化状态持久化，恢复时进行屏幕边界保护。
- 原生文件拖出 PoC：生成专用测试文件，验证 Windows 桌面应用拖入 Chrome 上传区域。
- 后端单元测试、Windows CI 与安装包构建脚本。

注意：这只是阶段 0 骨架，尚未实现正式资产数据库、导入、画廊、预览、标签等业务功能。PoC 只拖出测试文件，不允许 Renderer 传入任意路径。

## 环境

建议 Windows 10/11 x64、Node.js 22、Python 3.12。

PowerShell 安装依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
npm install
```

启动客户端：

```powershell
npm run dev
```

运行检查：

```powershell
python -m pytest backend/tests
npm run typecheck
npm run build
```

构建 Windows 安装包：

```powershell
npm run package:win
```

安装包输出到 release/。构建会先用 PyInstaller 打包 Python 后端，再构建前端并生成 NSIS 安装包。

## 数据位置

- 应用数据与日志：%LOCALAPPDATA%\\Ryan_DAM\\
- 后续默认托管素材目录：D:\\Ryan_DAM\\assets
- 阶段 0 测试文件：%LOCALAPPDATA%\\Ryan_DAM\\stage0-poc\\sample-upload.txt

卸载不得静默删除用户数据。

## 文档

- [开发者与 Agent 规范指南](AGENTS.md)
- [产品规格说明书](docs/Ryan_DAM_Product_Spec_v1.md)
- [技术架构](docs/TECHNICAL_ARCHITECTURE_V1.md)
- [UI/UX 规范](docs/UI_UX_DESIGN_V1.md)
- [实施计划](docs/IMPLEMENTATION_PLAN_V1.md)
- [阶段 0 验收清单](docs/STAGE_0_VALIDATION.md)
