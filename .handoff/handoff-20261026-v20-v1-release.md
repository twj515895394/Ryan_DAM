# Handoff v20 · 第一版 V1 完结交付与正式资产原生拖拽落地

> **核实时间：** 2026-10-26（ZCode 会话）  
> **交接版本：** Handoff v20（第一版 V1 完结交付）  
> **承前版本：** Handoff v19（RD 品牌图标全套接线）  
> **目标仓库：** https://github.com/twj515895394/Ryan_DAM  
> **主分支：** `main`

---

## 1. 本次迭代交付内容

### 1.1 票 21：正式资产卡片与沉浸预览原生文件拖出（`drag:start-asset`）
- **安全受控 IPC**：
  - 在 `apps/desktop/main.cjs` 中新增受控 IPC `drag:start-asset` 与 `drag:prepare-asset`。
  - 渲染进程仅允许传入数字型 `assetId`，严禁接收任意文件路径。
  - 主进程通过内部 loopback 端口携带每次启动动态生成的随机 Token，请求后端 `GET /api/v1/assets/${assetId}` 获取权威 `file_path`，并校验磁盘物理文件真实存在。
  - 引入 `assetPathCache` 预热缓存机制：前端在指针移入（`pointerenter`）卡片或预览手柄时静默预热，拖动（`dragstart`）时立即触发 `event.sender.startDrag({ file: filePath, icon })`，确保 Windows OLE 拖拽同步响应，无任何卡顿延迟。
  - 拖拽图标复用 v19 产出的专用 64px RD 品牌高品质图标 `apps/desktop/assets/drag-icon.png`。
- **卡片交互集成（`AssetCard.vue`）**：
  - 媒体容器区支持 `draggable="true"`，并绑定 `@pointerenter="onPrepareDrag"` 与 `@dragstart="onDragStart"`。
  - 完美兼容已有手势：单击打开沉浸预览、双击全屏、左上角 44×44px 独立大触控区点击多选、按住 Ctrl/Shift 快捷键选区操作；仅在纯按住媒体区拖动时触发原生文件拖出。
- **沉浸预览交互集成（`AssetPreview.vue`）**：
  - 预览头部控制栏增加直观毛玻璃「拖出文件」手柄（带可拖动指针、向上箭头图标与提示），让用户在预览任何格式文件时均能按住直接拖出到外部软件（如 Chrome、剪映、微信、飞书或本地文件夹）。
  - 大图预览区域 `<img>` 同样支持直接按住拖拽出真实原始文件。

### 1.2 架构治理：`App.vue` 瘦身至 690 行（消除超 800 行上限）
- **单一职责原则重构**：
  - 抽取 `apps/web/src/composables/useImportFlow.ts`（158 行），专门管理外部目录关联流程、文件与文件夹导入流程、目标逻辑目录选择器弹窗状态（`targetDialog` / `targetDialogRoots`）以及 `canImport` 计算状态。
  - `App.vue` 代码行数从 819 行大幅瘦身至 **690 行**，彻底解除超过 800 行红线警告，代码架构清晰模块化。

---

## 2. 第一版 V1 全功能完结总览（22 票全部就绪）

| 阶段 / 票号 | 核心能力 | 状态 | 成果与技术要点 |
|---|---|---|---|
| **阶段 0**（票 1） | 骨架与生命周期 | ✅ 完成 | Electron + FastAPI loopback 随机端口 + Token 鉴权 + 退出清理 |
| **阶段 1**（基础设施） | 数据层与目录树 | ✅ 完成 | SQLite + WAL + Alembic 0001–0009 迁移 + 13px 紧凑侧栏树 + 置顶 + 锁定 + 双击逐层展开 |
| **阶段 2**（票 2–6） | 托管导入与任务 | ✅ 完成 | 预检空间 + staging 校验 + 原子落盘 + 失败清理 + SHA-256 去重与强制导入 + 任务抽屉 |
| **阶段 3**（票 7–8） | 缩略图与媒体探测 | ✅ 完成 | Pillow 缩略图后台管线 + 前端 LRU 缓存 + FFmpeg 时长与代表帧抽取（卡片时长角标） |
| **阶段 4**（票 9–16） | 画廊、预览与管理 | ✅ 完成 | 50 项分页画廊 + 沉浸预览（边缘悬浮白圆翻页钮 + 遍历整目录）+ 文档/代码文本等宽预览 + 搜索筛选 + 全局标签 + 批量操作 + 回收站 + 重命名与移动 |
| **阶段 5**（票 17–20）| 外部目录与提示词 | ✅ 完成 | 同名挂载目录 + 只读镜像 + 全部刷新汇总 + 丢失失效标记 + 解除关联清理空树 + 外部原记录就地转托管 + 图像/视频多行完整提示词 |
| **阶段 6**（票 21–22）| 原生拖出与打包发布 | ✅ 完成 | **票 21 正式落地**：卡片与预览原生真实文件拖出；RD 品牌图标全套嵌入；PyInstaller + NSIS 安装包打包流水线就绪 |

---

## 3. 验证与质量保证

1. **语法与类型检查**：
   - `node --check apps/desktop/main.cjs` ✅
   - `node --check apps/desktop/preload.cjs` ✅
   - `npm run typecheck` ✅
2. **生产构建**：
   - `npm run build:web` ✅ （4.17s 零警告，dist 包含 index.html/css/js 及 favicon）
3. **后端测试**：
   - `.venv/Scripts/python.exe -m pytest backend/tests` ✅ **143 passed**（100% 绿灯，覆盖所有 20 个测试套件）
4. **代码规模规范**：
   - 全仓库所有 `.vue`、`.ts`、`.py` 源码文件均严格控制在 700 行以内（最大 `library.ts` 697 行、`App.vue` 690 行），无上帝组件。
