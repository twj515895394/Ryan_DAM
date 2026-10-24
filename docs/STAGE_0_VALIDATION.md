# 阶段 0：技术验证与验收清单

## 自动化检查

在 Windows 开发环境执行：

```powershell
python -m pytest backend/tests
npm run typecheck
npm run build
npm run package:win
```

Windows CI 会执行后端测试、前端类型检查与安装包构建。CI 通过不代表原生拖出已在真实桌面验证，该项必须人工验收。

## 1. Electron ↔ FastAPI 生命周期

- [ ] npm run dev 可以启动 Vite 和 Electron。
- [ ] Electron 收到 RYAN_DAM_READY 就绪消息后才显示主窗口。
- [ ] 后端绑定 127.0.0.1 的动态可用端口。
- [ ] 主界面健康状态显示“本地服务已连接”，版本为 0.1.0。
- [ ] 重新检查服务会再次调用 /health。
- [ ] 关闭应用后，后端通过 /shutdown 正常退出；超时则 Electron 清理子进程。
- [ ] 后端启动失败时显示错误提示，日志写入 %LOCALAPPDATA%\\Ryan_DAM\\logs\\desktop.log。
- [ ] 日志中不出现 API token。

## 2. 本地 API 安全边界

- [ ] 后端只绑定 127.0.0.1，不能从局域网其他机器访问。
- [ ] 缺少 X-Ryan-DAM-Token 的请求返回 401。
- [ ] 错误 Host 或不受信任 Origin 的请求被拒绝。
- [ ] Renderer 未启用 Node.js 集成。
- [ ] 不存在允许 Renderer 传入任意路径并直接拖出的 IPC 接口。

## 3. Windows 原生文件拖出 PoC

1. 在 Windows 桌面环境运行 npm run dev。
2. 点击“生成拖拽测试文件”。
3. 打开 Chrome 的文件上传页面或本地测试页。
4. 按住 sample-upload.txt 卡片，拖到 Chrome 文件上传区域。
5. 确认接收到真实文件，内容包含 “Ryan_DAM stage-0 native file drag test”。
6. 重复拖出，确认文件没有被移动或删除。
7. 重启应用，确认窗口大小、位置与最大化状态恢复。
8. 确认测试文件只在 %LOCALAPPDATA%\\Ryan_DAM\\stage0-poc\\ 下创建。

通过标准：Chrome 收到真实文件，而不是路径文本、网页 URL 或缩略图。

## 4. 独立后端与安装包

- [ ] PyInstaller 生成 backend/dist/ryan-dam-api.exe。
- [ ] NSIS 安装包输出到 release/。
- [ ] 在没有开发环境的 Windows 测试机安装后，应用不依赖系统 Python。
- [ ] 打包客户端能够启动独立后端并通过健康检查。
- [ ] 应用数据位于 %LOCALAPPDATA%\\Ryan_DAM\\，不放入安装目录。
- [ ] 覆盖安装不删除已有应用数据，卸载不自动删除用户数据。

## 阶段 0 完成定义

后端测试、前端类型检查、生产构建、Windows 安装包构建和 Windows 桌面拖出 PoC 均通过。正式资产数据库、导入、缩略图、画廊、搜索、标签和提示词管理属于后续阶段。
