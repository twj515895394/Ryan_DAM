# Ryan_DAM 开发交接文档（Codex 接手入口）

> **必读：** 这是 Ryan_DAM 项目根目录 `.handoff/current.md` 的详细交接文档。接手者应先读本文件，再读 `docs/` 下的需求与设计；不要依赖聊天记录来判断实际代码状态。
>
> **最近核实时间：** 2026-10-24（ZCode 会话）  
> **交接版本：** Handoff v2（阶段 0 复核 + 阶段 1 数据层与目录树已交付）  
> **目标仓库：** https://github.com/twj515895394/Ryan_DAM  
> **主分支：** `main`  
> **本次交接前已核对的 main 基线：** `87c1ecf`（stage 1 数据层 + 目录树 UI 两个提交，详见文末迭代记录）  
> **当前阶段：** 阶段 0 自动化核对全部通过、GUI 实机项仍待人工验收；阶段 1（SQLite 数据层 + 目录 API + 目录树 UI）代码已落地并有测试；下一步按票推进阶段 2  
> **最新已核对 CI：** [Stage 0 Windows verification #40077429948](https://github.com/twj515895394/Ryan_DAM/actions/runs/40077429948) — `success`（commit `1d70a69`）；阶段 1 提交后的 CI 结果见迭代记录。  
> **不要误读：** GitHub Actions 构建成功 ≠ 实际用户电脑上所有桌面交互已验收；代码存在 ≠ 功能通过用户场景验收。

---

## 0. Codex 启动必读与执行原则

### 0.0 最新迭代摘要（2026-10-24，ZCode 会话 · 阶段 5 全部开发票完成，未 push）

> **上一会话交接：** [`.handoff/handoff-20261024-213000.md`](./handoff-20261024-213000.md)（票 9–14 详情）。本会话完成票 15–20 后，**ISSUES_BACKLOG 中全部 19 张开发票（票 2–20）已交付**，剩余票 1/21/22 为 HITL 实机验收票。

- **Git 分支 / 提交：** `main` **本地**最新 `fd4df00`（review 加固）；远端 origin/main 停在 `d3ea899`，本地领先 17 个提交，待用户确认后一次性 push。
- **当前状态一句话：** 阶段 0–4 完成；阶段 5 完成（票 15 回收站、16 重命名/移动、17 外部关联与扫描、18 解除关联、19 转托管、20 提示词）；**全部开发票完成**，统一自测 + 全库 review 已做，剩 HITL 票（GUI 实机验收 / 正式拖出 / 终验）。
- **运行验证（最新）：** pytest **120/120**；vue-tsc / build / `node --check` 通过；e2e **21/21**；浏览器 UI 实测（回收站删除/恢复/清空、批量删除 managed+external 分流、提示词新增/复制/保存失败保留、外部转托管就地更新）全部通过；真实 `D:\Ryan_DAM\assets` 保持 0 条目。
- **本会话实测发现并修复的问题：** ①CORS 白名单缺 `PUT`（票 20 提示词保存全部失败，UI 实测抓到）；②删除/恢复后外部来源计数不刷新；③review 发现的模型约束与迁移 0004 不同步、外部扫描未排除托管根子树、删除后选区残留、trash 提交失败无补偿（均已修复并补测试，见 `fd4df00`）。
- **review 遗留（不阻塞，记录在案）：** 加载更多无 in-flight 防抖（快速连点可能重复追加）；搜索 `ilike` 未转义 `%`/`_`；列表 has_prompt 拉全量 prompt_text（可用 exists 优化）；解除关联后镜像出的空目录保留在树上；扫描仅按 size 判变更。
- **下一步第一任务：** 用户实机验收（票 1 GUI 启动/拖出 PoC、票 21 正式资产拖出、票 22 终验），随后按需发布 GitHub Issues 并推送。

### 0.0.1 迭代时间线（倒序）

0. **票 15–20（本会话，2026-10-24）**（`194df8a` → `fd4df00`，全部仅本地提交）——回收站（删除/恢复/永久删除/清空/bulk-trash 逐项结果 + 锁定文件 409 保护）、单资产重命名/移动（扩展名保留、同目录冲突、external 只读）、外部目录关联与手动扫描（层级镜像、重扫幂等、失效标记 missing、迁移 0004）、解除关联（仅删仍为 external 的索引）、外部转托管（staging+哈希校验+就地更新）、图片/视频提示词（`GET/PUT /assets/{id}/prompt`，换行逐字保留）。UI 实测全链路通过；review 加固（托管根子树跳过、提交失败补偿、选区清理、Esc 层级）已合入。
1. **票 9–14（2026-10-24 上一会话）**（`9921a82` → `d98db52`，全部仅本地提交）——沉浸式预览与内容端点、Range 播放与系统打开、五类文档预览、搜索/筛选/排序、全局标签、批量操作。详情与逐项验证记录见 `.handoff/handoff-20261024-213000.md`。
1. **票 8：音视频元数据与代表帧（FFmpeg 打包）**（`70116d3`）——`media_service` 受控定位器（`RYAN_DAM_FFMPEG_DIR` 环境变量 → PyInstaller 包内 `_MEIPASS/ffmpeg` → 仓库 `ffmpeg-bin/` → PATH，校验 PE 头拒绝构建期占位符）；ffprobe 提取时长/宽高、ffmpeg 提取视频代表帧（512px contain、1s 起帧回退）与音频内嵌封面；缩略图管线扩展到视频/音频；卡片新增时长角标（mm:ss）；`scripts/prepare-ffmpeg.mjs` 装载真实二进制或占位符、PyInstaller `--add-binary` 捆绑、CI 下载 BtbN win64 构建并导出环境变量；`docs/THIRD_PARTY_NOTICES.md` 记录 FFmpeg GPL v3 来源；测试 +7（66/66，无 ffmpeg 环境自动跳过）。CI 首轮失败：定位器测试依赖仓库状态（CI 在测试前已把真实 ffmpeg 放入 ffmpeg-bin/），已改为注入候选列表隔离（`3023b3b` 修复）。
   - **本地打包验证**：PyInstaller 产物 129MB（含 FFmpeg），冻结版 exe 端到端通过——视频时长 3000ms 精确、320x240、代表帧 JPEG 200；音频时长 2038ms。
2. **票 7：图片缩略图管线**（`0e6d909`）——Pillow 后台 worker + 磁盘缓存（`RYAN_DAM_CACHE_DIR`，默认 `<data>/cache/thumbnails`），源文件指纹（大小+mtime）侧车：命中直接返回、源变化自动重生成、重复失败标记 `failed` 不再重试；`GET /api/v1/assets/{id}/thumbnail` 未命中入队并返回 404（`thumbnail_unavailable`）；导入完成自动为图片入队；前端卡片 blob 带 token 加载、`object-contain` 不裁切、失败回退类型图标、画廊有 pending 时 2.5s 自动刷新（上限 8 次）；e2e +2（21 项）；测试 +6（59/59）。
2. **自测 + Code Review 轮**（`5a54f47`）——修复：①资产行提交失败时 objects/ 孤儿文件补偿（含回归测试）；②导入类测试曾污染 `D:\Ryan_DAM\assets`（新增 `iso_client` 夹具隔离并清理残留）；③票 5 UI 遗漏——任务面板新增「仍要导入重复项」；④目录路径误入文件导入 422、NameDialog 防双击、删除后选区复位、启动加载全部资产；⑤UI：中文菜单替换英文默认菜单、SVG 线性图标替换 emoji（AssetIcon）、`RYAN_DAM_USER_DATA` 隔离、DEV 浏览器预览桥。
   - **真实应用 UI 实测通过**（Electron + 隔离数据，computer-use 驱动）：新建项目/文件夹对话框、目录选中联动导入按钮、原生对话框多选导入、任务面板、重复跳过→强制导入、重启持久化、阶段 0 诊断弹窗、退出干净。
3. **票 5 + 票 6**（`e1cb958`）——`POST /api/v1/imports/{id}/retry-failed`（仅重跑失败项、进行中 409、无可重试 409、retry_count 计数）；任务面板「重试失败项目」。
4. **票 4**（`fa9e02f`）——`POST /api/v1/imports/folder` 层级镜像（item 级 target_folder_id，迁移 `0003`）；`dialog:select-folder` IPC。
5. **票 3**（`c2f247d`）——`GET /api/v1/assets` 分页画廊 v1（scope/folder 过滤、卡片网格、加载更多、导入后自动刷新）。
6. **票 2**（`52ee8a2`）——单文件托管导入全链路（空间预检同步拒绝 → staging+SHA-256 → 原子落盘 → 事务落库 → 失败清理；重复跳过/强制；迁移 `0002`；`dialog:select-files` IPC；任务面板轮询）。
7. **阶段 1**（`8f083d4` + `87c1ecf`）——SQLAlchemy 2.1/Alembic 1.20/SQLite（WAL+外键，启动程序化迁移）9 张表；`/api/v1` 项目与目录 CRUD（循环/跨作用域/非空删除拦截）、托管根目录设置；目录树 UI；`package-lock.json` + CI 改 `npm ci` + venv 固定；PyInstaller 打包 Alembic。
8. **阶段 0 复核**——自动化全过（pytest/node --check/typecheck/build/后端冒烟/CI `40077429948`）；**GUI 实机项（安装版启动、拖入 Chrome、多屏窗口恢复）仍未人工验收**，`docs/STAGE_0_VALIDATION.md` 保持未勾选。
9. **拆票**（`46687d5`）——22 票垂直切片写入 `docs/ISSUES_BACKLOG.md`；用户确认本地保存、暂不发布 GitHub Issues。

### 0.1 推荐接手顺序

1. 在仓库根目录执行 `git status`、`git log -5 --oneline`，确认本地代码与远端 `main` 的差异；**不要覆盖用户本地未提交的修改**。
2. 完整阅读 `.handoff/current.md`。
3. 阅读 `docs/Ryan_DAM_Product_Spec_v1.md`（**已确认需求的唯一事实基线**）。
4. 阅读 `docs/TECHNICAL_ARCHITECTURE_V1.md`、`docs/UI_UX_DESIGN_V1.md`、`docs/IMPLEMENTATION_PLAN_V1.md` 和 `docs/STAGE_0_VALIDATION.md`。
5. 对照现有代码验证文档描述，不要假定技术架构文档中写过的组件已真实落地。
6. 优先完成阶段 0 尚未人工验证的核心场景，随后按 `IMPLEMENTATION_PLAN_V1.md` 推进阶段 1。
7. 每次完成一个可验证的开发增量：执行检查、写明实际结果、提交代码，并**同步更新此交接文件**，方便下一次 Codex 接手。

### 0.2 用户偏好 / 工作方式

- 项目面向**个人自用**，第一版优先简单、好用、可靠，不是企业级 DAM 平台。
- 已经过约 40 项产品决策的深入讨论，**核心需求收敛**；不要重新发起零碎的需求脑暴或无限追问。
- 正常工程实现细节请直接做合理取舍并落实代码与测试；只有确实改变产品边界、存在不可逆的数据安全风险或与已有决策冲突时才向用户请示。
- 若需要提出问题，遵守项目「Grill Me 脑暴」约定：**每次只问一个问题，并给出你推荐的答案**。但开发阶段应首先尝试从 Spec 推导答案。
- 后续工作重点是**实际开发与验收**，而不只是补更多设计文档。
- 用户明确要求可以由 Codex 接手持续开发。本交接文件应成为后续迭代的最新状态入口。

---

## 1. 产品定位与不可破坏的核心决策

**产品名：** Ryan_DAM（本地数字资产管理工具）。

**目标人群：** 自媒体创作者、AI 图片 / AI 视频生成用户。管理角色图、场景图、道具图、视频、音频、参考资料、提示词等素材；优先提供高效浏览、预览、搜索、整理与实际文件复用的能力。

### 1.1 已确认的 V1 产品范围（简明版）

| 范围 | 已确认规则 |
|---|---|
| 运行形态 | Windows 首发，Electron 桌面客户端，用户单机本地使用 |
| 资产内容 | 图片、视频、音频、PDF / TXT / MD / JSON / CSV 和其他普通文件 |
| 资产组织 | 「通用资产库」「项目资产库」两个独立入口；项目有自己的多层文件夹 |
| 资产关系 | **不建立跨项目资产引用/使用关系**；不跟踪哪个项目使用了通用资产 |
| 导入 | 文件多选、文件夹导入并保留层级、拖拽导入；默认系统托管 |
| 外部目录 | 用户选定资产库中的目标文件夹，索引磁盘上已有素材；默认只读，不复制或删除原文件 |
| 导航 | 外部资产和托管资产在**相同目录树**里展示；仅用来源标识区分，不做独立外部资产顶层分类 |
| 外部转托管 | **复制原文件到托管目录后，原资产记录就地更新** `source_type`、`file_path` 等；保留 ID、目录、标签和提示词；**绝不平白新增第二张资产卡片**；原外部文件不删 |
| 解除外部来源 | 只清理该来源下**仍是 external** 的索引记录；不删除源文件；之前转为 managed 的资产继续保留 |
| 存储 | 默认托管素材目录 `D:\Ryan_DAM\assets`（用户明确不希望默认放 C 盘）；首次可自选；后续修改默认位置只影响新导入，**不自动迁移旧文件** |
| 数据 | SQLite 管理元数据，每个资产必须存储实际文件路径，不可仅依赖当前默认根目录 |
| 去重 | 以完整内容 SHA-256 检测重复；默认提示并跳过，可选择强制仍导入；不自动合并/删除 |
| UI | Apple 风格浅色极简；左侧目录 + 顶部搜索工具 + 中央缩略图画廊 |
| 预览 | 沉浸式预览 + 侧边属性；关闭后恢复之前目录/滚动位置 |
| 文档预览 | PDF、TXT、Markdown、JSON、CSV 内置预览；Office 第一版不做内置预览 |
| 标签 | 全局标签，可打到通用和任意项目资产；支持批量操作 |
| 提示词 | 图片/视频各一个完整多行 prompt 字段，可添加/查看/复制/编辑；保留原始换行，不拆正负提示词 |
| 拖出 | **必须能从 Electron 卡片和预览把真实文件拖入 Chrome 上传区域**；不是拖 URL、缩略图或文件路径文本 |
| 删除 | managed 进入应用回收站，恢复/彻底删除；external 只移除索引，不删磁盘原文件 |
| 性能 | 大文件复制、哈希、缩略图、扫描均后台化；大列表分页/懒加载 |
| 磁盘不足 | 托管导入前检查空间；不足时可更换位置或取消；中途失败清理半文件，已成功资产保留 |
| 更新 | V1 不做自动更新，使用手动下载安装包；升级/卸载不应静默删除用户素材与数据库 |

**更完整的细则以 `docs/Ryan_DAM_Product_Spec_v1.md` 中 1–40 项已确认决策为准，以上是压缩摘要，不能用它替代 Spec。**

### 1.2 第一版明确不做

- AI 自动打标签、AI 反推图/视频提示词、任何强制依赖大模型的处理。
- 文档全文检索、向量数据库、AI 语义搜索。
- Office 在线预览、PSD/AI 源文件深度解析。
- 动态视频缩略图、多帧挑选、音频波形编辑。
- 外部目录实时监控或周期自动扫描（只需手动刷新）。
- 跨项目资产关系图、自动复用跟踪、完整创作工作流。
- 多用户、登录/权限中心、云同步、微服务。
- Redis、Kafka、Celery 等基础设施（除非后来出现经过验证的实际必要性）。
- 自动更新系统、复杂任务调度器、批量重命名。

---

## 2. 技术选型：区分“需求确定”与“当前已经安装”

### 2.1 已确定的目标技术栈

| 层 | 确定方案 | 2026-10-24 实际代码状态 |
|---|---|---|
| 客户端 | Electron | **已搭骨架**，可打包 |
| Renderer | Vue 3 + TypeScript + Vite | **已搭骨架**；阶段 1 目录树 UI 已落地 |
| UI 样式 | Tailwind CSS + shadcn-vue | Tailwind **已接入**；`shadcn-vue` **尚未配置**（阶段 4 前按需引入） |
| 后端 API | Python + FastAPI + Pydantic | FastAPI **已运行**；阶段 1 已有 `/api/v1` 业务路由与 Pydantic schema |
| ORM | SQLAlchemy | **已落地**（2.1.6，9 张表模型 + 约束/索引） |
| 数据库迁移 | Alembic | **已落地**（1.20.1，初始迁移 `0001`，启动时程序化执行） |
| 数据库 | SQLite | **已接入**（WAL + 外键，userData/data 下） |
| 后台任务 | 进程内有限 worker + SQLite 持久化任务 | 表模型已建；**执行器未实现**（阶段 2 导入任务） |
| 缩略图/媒体探测 | 图片处理 + FFmpeg/ffprobe | **未实现**，属于阶段 3 |
| Windows 包 | PyInstaller + electron-builder/NSIS | **CI 已成功构建安装包**（含 Alembic 打包）；尚缺实际用户桌面安装运行验收 |

### 2.2 目标架构（已确认方向）

```text
Windows
  Electron Main                 -> 进程管理 / 窗口 / 原生文件拖出
    Preload（受控 API）          -> 仅暴露必要 IPC
      Vue 3 Renderer            -> 画廊、预览、目录、标签、提示词 UI
          HTTP /api/v1          -> 127.0.0.1 + 每次启动令牌
            FastAPI             -> 路由 + Service + Pydantic
              SQLAlchemy        -> SQLite 元数据
              有界后台任务        -> 复制、哈希、扫描、缩略图
              File System       -> 托管原文件 / 外部原文件 / 缓存
```

注意架构图中的 ORM、完整 API、worker 目前大部分还是目标设计，**不能当作阶段 0 的已完成代码**。

### 2.3 数据路径约束

- **原始托管素材默认根目录：** `D:\Ryan_DAM\assets`，首次设置可更改；不可因为 D 盘不存在就静默把大媒体文件写到 C 盘。
- **应用小数据与日志：** `%LOCALAPPDATA%\Ryan_DAM\`（当前 Electron 已设置 userData；数据库阶段建议也放这里）。
- **实际用户文件路径：** 每条资产有自己的 `file_path`，用户更改新资产默认存储位置时旧资产不会自动搬迁。
- **安装目录与数据分离：** 覆盖安装/卸载不静默删除素材和数据库。
- **阶段 0 测试文件：** `%LOCALAPPDATA%\Ryan_DAM\stage0-poc\sample-upload.txt`。
- **建议的托管物理目录：** `assets/objects/<asset-id>/<filename>`、`assets/.staging/<job-id>/`、`assets/.trash/<asset-id>/`。这在技术架构文档中是**实现建议**，尚未通过阶段 1 代码落地。

---

## 3. 当前仓库结构与入口

2026-10-24 的 main 代码结构：

```text
Ryan_DAM/
├─ .github/
│  └─ workflows/
│     └─ stage0-windows.yml       # Windows CI / 安装包 Artifact
├─ .handoff/
│  └─ current.md                  # 本交接文件；未来始终保持最新
├─ apps/
│  ├─ desktop/
│  │  ├─ main.cjs                 # Electron 生命周期、后端启动、窗口、原生拖出 PoC
│  │  └─ preload.cjs              # 最小 IPC 暴露
│  └─ web/
│     └─ src/
│        ├─ App.vue               # 阶段 0 状态页与测试卡片
│        ├─ main.ts               # Vue 挂载
│        ├─ style.css             # Tailwind/全局样式
│        └─ env.d.ts              # Window.ryanDam API 类型
├─ backend/
│  ├─ __init__.py
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py                  # FastAPI、健康检查、关闭、令牌与 Host/Origin 限制、DB 装配
│  │  ├─ api/v1/                  # /api/v1 路由：projects、folders、settings
│  │  ├─ core/                    # ApiError 与统一错误处理
│  │  ├─ db/                      # Base、session（WAL/外键）、程序化 Alembic 迁移
│  │  ├─ models/                  # 9 张表 ORM 模型
│  │  ├─ schemas/                 # Pydantic 请求/响应
│  │  └─ services/                # project/folder/settings 业务规则
│  ├─ alembic/                    # 迁移环境与 versions/0001_initial_schema.py
│  ├─ launcher.py                 # PyInstaller 后端入口
│  ├─ alembic.ini
│  ├─ requirements.txt           # FastAPI、Uvicorn、SQLAlchemy、Alembic
│  ├─ requirements-dev.txt       # pytest、httpx、PyInstaller
│  └─ tests/                     # 31 项测试（安全、迁移、项目、目录、设置）
├─ scripts/
│  └─ e2e_smoke.py               # 真实 HTTP 端到端冒烟（15 项，含重启持久化）
├─ docs/
│  ├─ Ryan_DAM_Product_Spec_v1.md
│  ├─ TECHNICAL_ARCHITECTURE_V1.md
│  ├─ UI_UX_DESIGN_V1.md
│  ├─ IMPLEMENTATION_PLAN_V1.md
│  ├─ STAGE_0_VALIDATION.md
│  └─ README.md
├─ index.html                    # Vue/Vite 入口与初步 CSP
├─ package.json                  # npm 命令 + electron-builder 配置
├─ vite.config.ts
├─ tsconfig.json
├─ tailwind.config.cjs
├─ postcss.config.cjs
├─ .gitignore
└─ README.md
```

**现状特别提醒：** `package-lock.json` 已于 2026-10-24 生成并提交，CI 已改用 `npm ci`。Alembic 目录、ORM 模型与正式业务路由均已落地；`shadcn-vue` 仍未引入。如果本地有其他未提交文件，以实际 `git status` 为准，不能擅自清理。

---

## 4. 阶段 0：已写代码及真实验证状态

### 4.1 实际已经提交的能力

**Electron / Windows：**
- 主进程窗口默认约 1440×900；读取 / 保存上一次尺寸、位置与最大化状态，恢复时限制在屏幕可用区域。
- 进程启动生成随机 `RYAN_DAM_API_TOKEN`，启动后端子进程；后端监听随机 loopback 端口，向标准输出发送 `RYAN_DAM_READY` JSON。
- Electron 接收就绪消息，将当前 API 地址和令牌通过 `backend:get-info` 暴露给本客户端 Renderer。
- 正常关闭时调用 `POST /shutdown`，超时后尝试终止子进程。
- 启动失败或后端意外退出时显示错误；将 Electron 日志写到应用数据目录。
- 提供 `drag:create-sample` 和 `drag:start-sample` 测试 IPC。前者只在受控的 PoC 目录内生成测试文件，后者调用 Electron `webContents.startDrag` 发送实际文件路径，不接受 Renderer 任意路径参数。

**Vue 测试页面：**
- 浅色状态页展示 Electron / FastAPI 基础运行状态与版本。
- 可重复请求 `GET /health`。
- 点击按钮生成 `sample-upload.txt`，随后将文件卡片拖出。
- 该页是**阶段 0 技术验证页**，不是正式的 DAM 左侧导航 / 画廊 UI。

**FastAPI：**
- `GET /health`：返回 `{"status":"ok","version":"0.1.0"}`。
- `POST /shutdown`：指示本地服务器关闭。
- 只监听 `127.0.0.1`；每次启动单独生成令牌。
- 基础 token 校验与 Host/Origin 限制；不开放 Swagger / OpenAPI 页面。
- 只完成最小服务层入口；无业务 API。

**构建 / CI：**
- npm 脚本用于开发、类型检查、前端构建、Python 后端打包、Windows NSIS 安装包。
- Python pytest 覆盖健康接口、缺少 token、非法 Host / Origin、开发 CORS preflight、关闭行为。
- GitHub Actions 在 Windows runner 安装 Node/Python 依赖并执行检查与构建，上传安装包 Artifact（最新流程）。

### 4.2 已验证通过（证据）

最新核对的运行：
- CI Workflow：`Stage 0 Windows verification`
- Run：`40077429948`
- URL：https://github.com/twj515895394/Ryan_DAM/actions/runs/40077429948
- 运行提交：`1d70a6950e932f4f5933868255515854afc1fa34`
- 结果：`completed / success`

该次 CI 下列步骤全部成功：
1. Windows runner checkout、Node 22、Python 3.12 环境准备。
2. npm 依赖安装、Python 依赖安装。
3. Electron Main / Preload 入口的 `node --check` 语法检查。
4. Python `pytest`（阶段 0 共 6 项测试）。
5. Vue/TypeScript `npm run typecheck`。
6. `npm run package:win`：PyInstaller Python 独立后端 + Vue 生产构建 + NSIS。
7. 检查 `release/` 中的 `.exe` 安装包。
8. 上传安装包 Artifact。

**CI 构建产物：**
- Artifact 名称：`Ryan_DAM-Windows-Installer`
- 所在运行：https://github.com/twj515895394/Ryan_DAM/actions/runs/40077429948
- 实际构建文件名称：`Ryan_DAM-0.1.0-x64.exe`
- GitHub Artifact ID：`12553547619`
- CI 配置保留期：14 天；到期后可重新触发工作流构建。
- 在该 Run 的 **Artifacts** 区域下载；这是 CI 构建产物，**不是经过真实 Windows GUI 验收的最终发行版**。

### 4.3 明确尚未验证 / 尚未完成

| 项目 | 状态 | 如何验收 |
|---|---|---|
| Windows 上真实启动安装后的 Electron 客户端 | **未人工验收** | Windows 10/11 x64 实机安装启动，无需 Python 开发环境 |
| 已打包客户端与 bundled Python 的实际生命周期 | **未人工验收** | 安装后显示“本地服务已连接”；退出后无残留 API 进程 |
| Electron → Chrome 原生拖出真实文件 | **未人工验收，高优先级** | `sample-upload.txt` 拖入 Chrome 上传区，确认是真实文件而非 URL / 文本 |
| 窗口上次状态在不同屏幕配置下恢复 | **未人工验收** | 正常窗口 / 最大化 / 断开副屏 |
| 复杂失效路径（崩溃、强杀、端口与令牌异常） | **未充分验证** | 定向手工 / 自动化验证 |
| 阶段 1 数据层 / 目录 API / 目录树 UI | **代码与测试已落地（31 pytest + 15 项 HTTP e2e）** | 待真实桌面人工过一遍目录树交互；Alembic 从空库迁移已自动化验证 |
| 画廊、标签、导入等正式业务 UI | **未实现** | 阶段 2 及后续（按拆票顺序） |
| shadcn-vue 组件配置 | **未实现** | UI 开发时按需引入 |

请坚持：**代码存在 ≠ 功能通过用户场景验收。**

---

## 5. 本地开发、测试、构建命令（Windows）

在仓库根目录运行 PowerShell；先安装 Node.js 22、Python 3.12。

### 5.1 首次环境准备

```powershell
git clone https://github.com/twj515895394/Ryan_DAM.git
cd Ryan_DAM

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt

npm install
```

开发模式 Python 默认调用 `python -m backend.app.main`；如果激活虚拟环境不方便，可显式设置：
```powershell
$env:RYAN_DAM_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
```

### 5.2 启动

```powershell
npm run dev
```

预期：
- Vite 开发服务监听 `127.0.0.1:5173`。
- Electron 启动 FastAPI 子进程，选择本地随机端口。
- Electron 显示阶段 0 状态页，提示本地 API 已连接。
- 普通浏览器直接打开 Vite 页面不等价于完整桌面客户端：`window.ryanDam` 来自 Electron Preload，普通浏览器没有这个对象。

### 5.3 静态检查、后端测试与生产构建

```powershell
node --check apps/desktop/main.cjs
node --check apps/desktop/preload.cjs
python -m pytest backend/tests
npm run typecheck
npm run build
```

### 5.4 Windows 安装包

```powershell
npm run package:win
```

预期：
- `backend/dist/ryan-dam-api.exe`
- `apps/web/dist/`
- `release/Ryan_DAM-0.1.0-x64.exe`

**限制：** `npm run package:win` 是 Windows 构建步骤，尽量在 Windows runner 或用户 Windows 环境验证；CI 已成功构建，不表示其他操作系统同样适用。

### 5.5 实机文件拖出验收步骤（必须补）

1. Windows 桌面启动开发版或已安装版 Ryan_DAM。
2. 确认本地服务在线。
3. 点击「生成拖拽测试文件」。
4. 打开 Chrome 中一个实际支持拖入上传文件的区域。
5. 按住 `sample-upload.txt` 卡片拖到 Chrome 上传区域并放开。
6. 验证对方接收 **真实本地文件**、文件名正确、内容包含 `Ryan_DAM stage-0 native file drag test`。
7. 再次执行拖出，检查源文件仍存在且内容未变。
8. 关闭客户端，检查 `ryan-dam-api.exe` / Python 进程是否残留；重启检查窗口状态。
9. 实测失败时先修正 IPC / Electron `startDrag` / 拖拽事件、图标与 Chromium 兼容性；**不得以 HTML5 下载 URL 或把文件路径复制到剪贴板代替核心拖出能力**。
10. 把实测环境、结果、复现步骤和修复提交写入本文件，再勾选 `docs/STAGE_0_VALIDATION.md` 对应项。

---

## 6. 代码重点位置、协议与未来扩展点

### 6.1 Electron 主进程：`apps/desktop/main.cjs`

关键职责与入口：
- `getBackendCommand()`：开发模式调用系统 / 虚拟环境 Python，打包模式查找 bundled `ryan-dam-api.exe`。
- `startBackend()`：生成令牌、spawn、读取 `RYAN_DAM_READY` 标记并保存端口，失败超时提示。
- `stopBackend()`：HTTP `POST /shutdown` + 后端超时清理。
- `readWindowState()` / `persistWindowState()`：窗口记忆与限制屏幕范围。
- `createWindow()`：创建带隔离设置的 BrowserWindow，加载 Vite 或打包后的 index.html。
- `ipcMain.handle("backend:get-info")`：让 Renderer 获取本次会话 API 地址与令牌。
- `ipcMain.handle("drag:create-sample")`：在 PoC 固定路径生成测试文件。
- `ipcMain.on("drag:start-sample")`：通过 `event.sender.startDrag({file,icon})` 原生拖出。

后续阶段新增文件/文件夹选择 IPC 应严格限制参数与来源，不能直接暴露任意文件系统接口给渲染器。正式资产拖出应按可信资产 ID 查路径并校验来源，而非盲目信任 Renderer 传入的本地路径。

### 6.2 Preload：`apps/desktop/preload.cjs`

只暴露 `window.ryanDam` 的三个方法：
- `getBackendInfo()`
- `createSampleFile()`
- `startSampleDrag()`

阶段 1 扩展 IPC 需要同步更新 `apps/web/src/env.d.ts`。仍必须维持 `contextIsolation: true`、`nodeIntegration: false`，避免把通用 Node API 暴露到页面。

### 6.3 API：`backend/app/main.py`

- `create_app(api_token)` 为测试与运行创建 FastAPI app。
- `run_server()` 使用标准库 socket 分配本地随机端口，然后将该 socket 交给 Uvicorn。
- 服务启动协议：标准输出行以 `RYAN_DAM_READY ` 开头，随后 JSON 至少含 `port`、`version`。
- `RYAN_DAM_API_TOKEN` 必填，无 token 直接退出，不允许意外成为无鉴权服务。
- API 请求带 `X-Ryan-DAM-Token`；预检 OPTIONS 特别处理。
- 健康接口 `GET /health`；结束接口 `POST /shutdown`。
- 开发 CORS 允许 `http://127.0.0.1:5173`；打包 file 页面使用 `Origin: null` 兼容逻辑。

**注意：** 目前 `RYAN_DAM_READY` 是 socket 绑定/服务即将启动的信号，不是已完成一次真正 `/health` 请求的证明。可以在阶段 0 余项中将 Electron「准备就绪」定义为成功执行令牌化 `/health` 后才正式展示业务主界面。

### 6.4 需留意的工程风险（不代表已经发现故障）

1. **file:// 与本地 token 边界**：Renderer 持有 token、服务允许 `Origin: null`；对 V1 个人本地应用可作为起点，但引入用户提供的 Markdown、网页内容或其他不可信渲染内容前，必须复核 CSP、文件预览消毒、导航拦截及请求边界。
2. **Electron 原生拖出**：目前仅是可交互的 PoC 实现，尚未 Windows 实机确认。`nativeImage` 的拖拽图标若为空或平台表现异常，需要测试并修正，不要依赖理论推断。
3. **进程生命周期**：要验证 Python 进程异常退出、应用退出、安装运行时的清理；CI 构建并未覆盖桌面进程行为。
4. **缺少锁文件**：当前没有 `package-lock.json`；为了构建可复现性，应在真实工程环境执行 `npm install` 后提交生成的锁文件，并将 CI 改为 `npm ci`（前提是锁文件可正常维护）。
5. **Windows 默认盘符**：D 盘可能不存在。首次配置必须明确提示/允许选择，不要静默把媒体写入 C 盘。
6. **数据库迁移安全**：未来模型变更必须有 Alembic 迁移；保护已有用户数据，不允许“删库重建”成为升级策略。
7. **单机 ≠ 可以忽略数据一致性**：文件系统和 SQLite 不能天然同事务，导入、转托管、回收站需要阶段化写入与失败补偿。

---

## 7. Codex 下一步建议：严格按优先级实施

### P0：补齐阶段 0 的真实用户场景验收（仅剩 GUI 项）

1. 核对阶段 1 提交后的最新 CI run（`.handoff` 文末迭代记录里的链接）为 `success`。
2. 在 Windows 环境**人工验证**：安装版/开发版启动、退出后无残留进程、`sample-upload.txt` 拖入 Chrome 上传区为真实文件、窗口状态恢复。步骤见 §5.5。
3. 只有真实人工完成的项目才能勾选 `docs/STAGE_0_VALIDATION.md`，并把环境/结果写回本文件。
4. 若本会话或下一位开发者没有 Windows GUI 操作能力：保持未勾选，明确报告，不虚构通过。

### P1：阶段 2——系统托管导入、任务面板与磁盘安全（按票推进）

**阶段目标：** 从「目录树可用」推进到「可以真实导入文件并保留层级、去重、断点可诊断」。

**1. 文件/文件夹选择与导入任务骨架**
- Electron 侧新增受控 IPC：`dialog:select-files`、`dialog:select-folder`（只返回用户选中的路径，不接受 Renderer 任意路径）。
- 后端 `POST /api/v1/imports` 创建 `import_jobs` + `import_job_items`；进程内有限并发 worker 执行。
- 前端导入按钮接入；任务面板（抽屉）轮询 `GET /api/v1/imports/{id}`。

**2. 导入安全顺序（严格按技术架构 §4.3）**
- 预扫描数量/总大小 → 检查目标盘空间（`app_settings.managed_root`）→ staging 复制 → 校验 → 原子落盘到 `objects/<asset-id>/<filename>` → 事务写 assets 记录 → 失败补偿清理半文件。
- SHA-256 后台分块计算；默认重复跳过，允许强制导入；同名不同内容自动加后缀。
- 文件夹导入保留子目录层级，映射到逻辑目录树。

**3. 验收**
- UI 导入期间不冻结；重复导入默认跳过；失败可重试且不重复处理成功项；空间不足/中断不留半成品；每条资产 file_path 真实可访问。

### P2：阶段 3–6 排期参考（**按拆票顺序做，不要一次性都做**）

- **阶段 3**：图片/视频/音频缩略图与媒体属性，FFmpeg 打包及缓存。
- **阶段 4**：网格/列表、搜索筛选、沉浸式预览、批量操作、标签、回收站；接入 shadcn-vue。
- **阶段 5**：外部目录关联与手动扫描、解除关联、原记录就地转托管、图片/视频提示词。
- **阶段 6**：正式资产卡片原生拖出、Windows 安装包、安装升级安全及全面验收。

实施计划已拆成 GitHub Issues（见文末迭代记录）；每完成一票：跑测试 → 更新本文件 → 提交。

---

## 8. 严禁违反的业务不变量（写代码时请反复自检）

1. **外部资产绝对不因索引移除、目录解除关联而删除用户磁盘上的源文件。**
2. **外部转托管是复制 + 校验 + 更新原记录，而不是新增另一条记录；保留旧资产 ID 与元数据。**
3. 更改默认存储路径不能迁移、损坏或丢失旧资产；必须依赖每条资产自己的真实路径。
4. UI 中通用库和项目库区分，但不建立“项目使用了某个通用素材”的关系模型。
5. 文件内容相同 ≠ 系统允许自动合并/删除用户已经管理的资产；重复默认跳过，用户可强制仍导入。
6. 删除托管资产优先回收站；真正永久删除必须显式操作。
7. 不能因为空间不足或复制异常就损坏已成功入库的文件；新写入文件先 staging，再校验，失败清理。
8. 未来正式资产拖出传的是**真实文件**，不能退化为 URL、缩略图或路径文本。
9. 第一版没有 AI 运行时要求，不要把 AI 依赖变成必装条件。
10. 不添加云账户、复杂权限或微服务；不要重新造一个通用工作流平台。
11. 普通操作不要求用户确认一大堆选项；更危险的删除、覆盖、解除外部关联才重点提供明确确认与说明。
12. 切勿将用户文件、SQLite、日志放在会被安装或卸载步骤直接清空的程序目录。

---

## 9. 已知文档小问题与处理原则

1. `docs/Ryan_DAM_Product_Spec_v1.md` 的决策章节标题有旧字样「第 1–33 项」，但其表格**实际已记录 1–40 项**。应以表格的内容和顶部状态为准，后续可顺手修正文案；不要因此重新讨论已确认的事项。
2. Spec 中个别实施状态类说明（如默认目录「仍待确认」）属于旧文案残留；用户已经确认默认 `D:\Ryan_DAM\assets`，磁盘空间处理规则也已确认。实现时按明确的决策记录处理。
3. 技术架构 `TECHNICAL_ARCHITECTURE_V1.md` 和 UI `UI_UX_DESIGN_V1.md` 同时包含**设计建议**和**未来目标**；不是代码完成证明。
4. 本文件中的阶段 1 方案属于**推荐开发计划**，不是用户已确认的额外产品功能。工程细节可依据简单可靠原则调整，任何触及核心业务不变量的调整必须回到 Spec 核对。
5. V1 的主要交付端是 Windows Electron，不要因为 Vue 技术栈存在就误判成需要单独部署的 Web SaaS。

---

## 10. 后续 Codex 的交接文档维护约定

### 10.1 每次开发完成必须更新

继续复用**同一个** `.handoff/current.md`，不用每完成一个小任务就创建一批交接文件。更新时务必写明：

1. **最后核实时间、分支和 commit SHA**。
2. **这次实际修改的文件 / 功能 / 重要设计取舍**。
3. **实际运行的命令与结果**：例如 6/6 pytest、TypeScript 检查、CI Run 链接、Windows 实测反馈；未运行要直说。
4. **已知问题**：错误日志 / 复现步骤 / 影响范围 / 优先级。
5. **尚未验证的交互**，尤其是 Electron 原生文件拖出、安装版与后端生命周期。
6. **下一位开发者立刻可执行的 1–3 个任务**（含验收标准）。
7. 如产品决策改变，先更新 `docs/Ryan_DAM_Product_Spec_v1.md`，再更新受影响的技术/UI/实施文档和本交接文件。
8. 交接文件必须随同对应代码提交或在该任务末尾提交到同一分支，不可在聊天里说已交接但仓库里没有文件。

### 10.2 建议的迭代结束摘要格式

```markdown
## 最近一次迭代（更新日期 YYYY-MM-DD）
- Git 分支 / 提交：
- 开发目标：
- 实际交付：
- 修改文件：
- 运行验证：
- 未完成 / 已知问题：
- 下一步第一任务：
```

### 10.3 交接优先级

**可信度排序：** 真实代码与成功测试 / CI / Windows 实测记录 ＞ Spec 中已确认的产品事实 ＞ 技术设计建议 ＞ 未验证的口头进度说明。

如果实际代码、Spec、CI、聊天说法之间出现不一致，先定位差异并记录，不要悄悄改写已确认的产品规则来迎合现有代码。

---

## 12. 迭代记录

### 最近一次迭代（更新日期 2026-10-24，ZCode 会话 · 票 15–20）

- **Git 分支 / 提交：** `main` 本地 `194df8a` → `fd4df00`（8 个提交，全部仅本地）：
  - `194df8a` feat: ticket 15 trash with restore, permanent delete and bulk trash
  - `2db0208` feat: ticket 16 single asset rename and move
  - `f986183` feat: ticket 17 external directory linking with manual scan
  - `2e3b367` feat: ticket 18 unlink external source keeping converted assets
  - `7cd0e60` feat: ticket 19 convert external asset to managed in place
  - `49d4377` feat: ticket 20 image and video prompt management
  - `b03c9f0` fix: allow PUT in CORS methods and refresh external counts after trash changes
  - `fd4df00` fix: review hardening for trash, external scan and selection cleanup
- **开发目标：** 完成阶段 5 全部开发票（15–20），统一自测 + 全库 code review 后交付。
- **实际交付：**
  - **票 15 回收站**：`DELETE /assets/{id}`（managed→trash / external 仅删索引）、`GET /trash`、`POST /trash/{id}/restore`、`DELETE /trash/{id}`（锁定文件 409 保留记录）、`POST /trash/empty`（逐项容错返回 removed/failed）、`POST /assets/bulk-trash`（逐项结果）；前端侧栏回收站入口 + 列表视图（名称/类型/大小/删除时间/原目录/恢复/永久删除）+ 预览删除按钮 + 批量删除。
  - **票 16 重命名/移动**：`PATCH /assets/{id}`、`POST /assets/{id}/move`；扩展名自动保留、修改扩展名 422、同目录同名 409、external 只读 400、移动仅改 folder_id；预览信息面板「管理」区（重命名对话框 + 同 scope 目录下拉）。
  - **票 17 外部关联**：迁移 `0004`（status 加 missing）、`GET/POST /external-sources`、`POST /external-sources/{id}/scan`；扫描只读源文件、层级镜像到目标目录、重扫幂等（added/updated/missing/reactivated）、失效标 missing 且列表可见；前端侧栏外部目录区（关联流程 = 原生选目录 → 选库内目标目录弹层、重扫按钮、失效计数）、卡片「失效」角标、预览「状态：失效」。
  - **票 18 解除关联**：`DELETE /external-sources/{id}` 仅删仍为 external 的索引（转托管记录保留），确认弹窗显示影响数量与「不删除源文件」提示。
  - **票 19 转托管**：`POST /assets/{id}/convert-to-managed`，按导入安全顺序（空间预检 → staging 复制 → SHA-256+大小校验 → 原子落盘 → 就地更新 source_type/file_path/sha256，失败补偿清理）；源文件永不删除，重扫不触碰已转换记录；预览外部资产「转为系统托管」按钮。
  - **票 20 提示词**：`GET/PUT /assets/{id}/prompt`（仅 image/video，换行与特殊字符逐字保留，空串清空）；卡片悬停「+ 提示词/查看提示词」入口（自动打开预览弹窗）、预览面板提示词区（查看/编辑/复制全文，保存失败保留草稿）。
- **修改文件：** `backend/app/**`（api: trash/external/assets、services: trash/external/asset_edit/fs_ops、schemas、models/asset.py、main.py CORS）、`backend/alembic/versions/0004_*`、`apps/web/src/**`（App.vue、stores/library.ts、api/client.ts、api/types.ts、AssetPreview/AssetCard）、`backend/tests/`（+5 个测试文件，120 项）。
- **运行验证（本机 Windows 10，venv Python 3.12，Node 24）：**
  - `.venv/Scripts/python.exe -m pytest backend/tests` → **120 passed**
  - `npm run typecheck` / `npm run build` / `node --check`（桌面入口）→ 通过
  - `scripts/e2e_smoke.py` → **21 passed**
  - **浏览器 UI 实测**（隔离后端 49489 + vite 5173 + localStorage 桥）：侧栏新分区渲染、4 资产画廊（外部角标/镜像子目录）、提示词添加→查看→复制→入口翻转、删除→回收站列表→恢复回画廊、批量删除（managed 进回收站、external 仅删索引、逐项 toast）、清空回收站、外部转托管就地更新（卡片不变、路径切到 objects/、管理操作切换、外部计数归零）、磁盘核对（源文件字节未动、托管副本存在、.trash 清空）。
  - 真实 `D:\Ryan_DAM\assets` 全程 0 条目。
- **未完成 / 已知问题：**
  - review 建议项未全部采纳（不阻塞）：加载更多无防抖、搜索 ilike 未转义、has_prompt 拉全量文本、解除关联后镜像空目录保留、扫描仅按 size 判变更——已在 §0.0 记录。
  - HITL 票 1/21/22 未开始（需用户实机）。
- **下一步第一任务（1–3 个）：**
  1. 用户实机验收：安装版/开发版启动、回收站与外部目录真实操作、正式资产拖出（票 21）、终验（票 22）。
  2. 如需发布 GitHub Issues：用 `to-issues` 把 `docs/ISSUES_BACKLOG.md` 发到仓库（需 gh/token）。
  3. 处理 review 遗留建议项（可作为下一批小修复）。

### 上一迭代（2026-10-24，票 9–14）

见 `.handoff/handoff-20261024-213000.md` 与 git 历史（`9921a82` → `d98db52`）。

---

## 11. 给下一位 Codex 的直接执行指令

> 你正在接手 GitHub 项目 `twj515895394/Ryan_DAM`。请先读 `.handoff/current.md` 和 `docs/Ryan_DAM_Product_Spec_v1.md`、技术架构、UI、实施计划与阶段 0 验收清单。检查最新 `main` 与本地未提交改动，勿覆盖用户数据和修改。
>
> 当前阶段 0 的工程骨架已经提交，Windows CI `40077429948` 通过，PyInstaller + Electron NSIS 安装包已构建并上传 Artifact；**真实 Windows GUI 的应用安装运行、原生文件拖入 Chrome 仍没有人工验收**。
>
> 请优先复核阶段 0 验收与已知工程风险，能在当前环境完成的测试直接执行；若无 Windows GUI 能力，明确报告未测部分，不虚构通过。然后进入阶段 1，优先做 SQLAlchemy + Alembic + SQLite 的可迁移数据基础、通用与项目目录 API、默认托管路径设置、基本目录树 UI，每个增量都要附测试。
>
> 第一版严格遵循已确认的 40 项产品决策：本地自用、托管优先、外部目录只读、外部转托管更新原记录且不生成重复资产、默认 D 盘、浅色 Apple 风格、不做 AI/云/复杂系统。
>
> **实际提交代码和测试优先，不要仅写更多设计文档。** 完成后更新 `.handoff/current.md`（提交、验证、遗留问题、下一步）并保持它为下一次交接的最新入口。
