# 第三方组件与许可声明（Third-Party Notices）

Ryan_DAM V1 在安装包中捆绑了以下第三方运行时组件。本文件记录其来源与许可信息；捆绑的均为未修改的官方构建。

## FFmpeg / ffprobe（Windows 打包内含）

- **用途：** 视频代表帧提取、音视频时长/尺寸探测、音频内嵌封面提取。
- **来源：** [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases) 的 `ffmpeg-master-latest-win64-gpl.zip`（构建时自动获取当时的最新 master 构建）。
- **许可：** **GPL v3**（该构建启用了 libx264 等 GPL 组件）。FFmpeg 本体源码：https://ffmpeg.org/download.html 。
- **说明：** 按GPL v3 要求，随应用分发 FFmpeg 二进制时需同时提供对应源码获取方式（上述官方链接即可满足）。应用安装包不含对 FFmpeg 的修改。
- **回退：** 若打包时未找到 FFmpeg（或运行时二进制不可用），视频/音频的元数据与代表帧功能自动降级为类型图标展示，不影响资产的导入与管理。

## Python 侧依赖（PyInstaller 打包内含）

| 组件 | 许可 | 用途 |
|---|---|---|
| FastAPI / Starlette | MIT | 本地 REST API |
| Uvicorn | BSD-3-Clause | ASGI 服务器 |
| SQLAlchemy | MIT | ORM |
| Alembic | MIT | 数据库迁移 |
| Pydantic | MIT | 请求/响应校验 |
| Pillow | MIT-CMU（HPND） | 图片缩略图生成 |

## 前端 / 桌面依赖（electron-builder 打包内含）

| 组件 | 许可 | 用途 |
|---|---|---|
| Electron | MIT | 桌面容器 |
| Vue 3 | MIT | 渲染层框架 |
| Vite / TypeScript / Tailwind CSS | MIT | 构建与样式 |

以上前端组件不修改源码、按其许可原样分发。完整依赖清单见 `package.json` 与 `backend/requirements.txt`。
