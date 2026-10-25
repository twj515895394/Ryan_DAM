# Ryan_DAM 开发交接文档（Codex 接手入口）

> **必读：** 这是 Ryan_DAM 项目根目录 `.handoff/current.md` 的详细交接文档。接手者应先读本文件，再读 `docs/` 下的需求与设计；不要依赖聊天记录来判断实际代码状态。
>
> **最近核实时间：** 2026-10-25（ZCode 会话）  
> **交接版本：** Handoff v15（预览翻页改边缘圆形悬浮按钮；承 v14 预览同目录切换增强：跨分页遍历 + 位置指示 + ↑/↓、v13「其他」分类/迁移 0008、v12 侧栏目录置顶、v11 代码文件文本预览/缩略图 LRU 缓存）  
> **目标仓库：** https://github.com/twj515895394/Ryan_DAM  
> **主分支：** `main`  
> **当前阶段：** 阶段 0–5 全部开发票落地；多选、移动、弹窗全面升级 Apple HIG；目录与项目级联删除全面完成（`cascade_delete_folder_ids` 共享算法 + Apple HIG 影响说明确认弹窗）；**用户报告的删除项目 409 已定位为陈旧后端进程**（Electron 派生的 Python 服务无热重载，旧进程静默忽略 `?cascade=true`），代码无缺陷，**用户完全重启桌面应用后即可正常级联删除**，前端已加固为遇 404 如实提示重启；md 文档预览支持 GFM 表格；导入任务面板 5 秒自动关闭；卡片提示词入口双修复；**侧栏铅笔升级为「编辑文件夹」弹窗（名称 + 描述 + Apple HIG 琥珀锁定开关）**——迁移 0006 增 `folders.locked/description`，锁定目录拦截直接删除与目录/项目级联（409 `folder_locked` 点名锁定目录），锁只拦删除、不向下继承；typecheck + build + **131 pytest** 全绿，5173 浏览器冒烟锁定/拦截/解锁/级联全链路通过。**需完全重启桌面应用使 0006 迁移与守卫生效（前端 vite 热更新即可，后端进程必须重启）**；最新：**侧栏紧凑化 + 可拖拽宽度**（目录行 24px、缩进 13px/层、截断悬停全名；把手 1:1 跟手拖拽钳制 [220,480]、键盘/双击调节、localStorage 持久化；顺带修复无效类 `h-7.5/py-0.2` 与冒烟揪出的 STORAGE_KEY 损坏字面量），纯前端、刷新即生效；最新：**代码文件文本预览 + 缩略图缓存**——后端 `CODE_EXTS`（47 种源码/配置/日志扩展）并入文档分类（新导入/外扫的 `.py`/`.ts`/`.yml` 等注册为文档），前端沉浸预览按等宽 `font-mono` 文本渲染代码且**存量已存为「文件」的代码资产按扩展名回退同样可预览**；新增 `useThumbnailObjectUrl` 模块级 LRU 缓存（240 条）共享给资产卡与回收站行，目录切换/滚动重挂零网络请求、`failed` 负缓存防反复 404。typecheck + build + **134 pytest** 全绿，5173 冒烟（代码预览、存量回退、缓存零新增请求）全通过；最新：**侧栏目录置顶**——目录行悬停操作区新加图钉按钮（`+` 与铅笔之间），点击置顶/解除置顶，置顶目录**始终排在同层最上方**（全局排序 `pinned desc → sort_order → id`，build_tree 保序 → 任意层级生效），名称右侧常驻蓝色图钉徽标（镜像锁定徽标模式、accent 语义色区分琥珀锁定）；迁移 0007 增 `folders.pinned`，`PATCH {pinned}` 走 `update_folder_info` 哨兵，改名/锁定 PATCH 不重置置顶。**需用户完全重启桌面应用使 0007 迁移与置顶排序生效（后端进程必须重启；前端刷新即生效）**；最新：**「其他」分类**——用户反馈 `.py` 全挂在「文档」下：顶栏分类栏加「其他」chip，代码/配置/日志扩展不再并入文档（`guess_asset_type` 归 `other`），**迁移 0008 把存量误标 document 的代码资产自动改回 other**（冻结扩展名快照、幂等），卡片/预览/回收站 other 标签「文件」→「其他」；代码预览经 v11 的 other 扩展名回退通道**原样可用**。typecheck + build + **135 pytest** 全绿；迁移 E2E（0007 旧库→启动自动升 0008 改类）+ 5173 冒烟（chip 过滤/卡片标签/代码预览仍渲染且面板「类型：其他」）全通过。**同样需完全重启桌面应用使 0008 改类生效**；最新：**预览同目录上下切换增强**——沉浸预览切换早已存在（按钮 + ←/→）但只在本页 50 项内回绕：`stepPreview` 重写为分页感知，到末尾自动追加下一页再前进（**切换可遍历整个目录**），按钮间加 `n / total` 位置指示（单资产目录整组隐藏），`↑/↓` 并入切换；typecheck + build + **135 pytest** 全绿，5173 冒烟（50 边界自动追加 51/55、全量遍历、双向回绕、↑/↓、单图隐藏按钮、截图目检）全通过。**纯前端、刷新即生效**（迁移 0006–0008 的重启要求不变）；最新：**预览翻页改边缘圆形悬浮按钮**——用户反馈右上角文字按钮不顺手：移除头部「← 上一项 / 下一项 →」，改为媒体区左右边缘垂直居中的白底圆形箭头（`h-11 w-11` 44px 命中热区、`bg-white/85` 毛玻璃、原始尺寸平移时视口锚定不滚走），右上角仅留 `n / total` 指示；键盘与跨分页逻辑不变；typecheck + build + **135 pytest** 全绿，5173 冒烟（点击切换、几何、单图隐藏、截图与参考图风格一致）全通过。**纯前端、刷新即生效。**

---

## 0. Codex 启动必读与执行原则

### 0.0 最新迭代摘要（2026-10-25，ZCode 会话 · 预览翻页改边缘圆形悬浮按钮）

> **最新会话交接：** [`.handoff/handoff-20261025-200229.md`](./handoff-20261025-200229.md)——接手者务必先读它，再读本文件。上一票（预览同目录切换增强：跨分页 + 指示 + ↑/↓）交接见 [`.handoff/handoff-20261025-195603.md`](./handoff-20261025-195603.md)。

- **Git 分支 / 状态：** `main`，本地 `de42a74`（web）；连同积压 `0269505` `213e9fb` `7d78aff` `b9c71a4` 等均未推送（统一交付后再推）。
- **本会话已完成工作（纯前端，v14+v15 两票）：**
  1. **v14** 预览同目录切换增强（详见 §0.0.1 与 handoff-195603）：`stepPreview` async 分页感知（末尾自动追加下一页、遍历整目录）、`n / total` 指示、↑/↓ 键、单资产隐藏按钮组。
  2. **v15 需求**：用户：「加这种图标不是更好吗 你把上下页放右上角 操作起来没这么方便啊」+ 参考图（图片右缘白底圆钮 `>` 箭头）。
  3. **v15 交付**（`de42a74`，仅 `AssetPreview.vue`）：头部移除两个文字翻页按钮、右上角仅留 `n / total` 指示；媒体区左右边缘加白底圆形悬浮箭头（`h-11 w-11` 44px、`bg-white/85 backdrop-blur shadow-lg hover:bg-white active:scale-95`、lucide 风格描边 chevron、`aria-label`）；**关键结构**：滚动容器外包 `relative min-w-0 flex-1`、容器改 `absolute inset-0`——按钮视口锚定，原始尺寸平移图片时不随内容滚走；`total > 1` 门控、键盘与跨分页逻辑零改动。
  4. **验证与冒烟**：typecheck ✅ / build ✅ 1.95s / pytest ✅ 135（后端零改动）；5173 冒烟：按钮几何 44×44/边缘 12px/垂直居中 ✅、点 `›`→`2 / 55`、点 `‹`→`1 / 55` ✅、单图两钮+指示均不渲染 ✅、截图 `.handoff/preview-edge-buttons.png` 目检与参考图风格一致 ✅；测毕杀后端、删种子、清桥接。**构建坑**：模板加包装 div 忘补 `</div>` → `[vite:vue] Element is missing end tag` 且行号指向根节点（真实缺点在嵌套深处）——改模板嵌套后先 build 再信行号。
  5. **codereview**：0 致命（`@click.self` 根遮罩不误触、z-10 不挡视频控制条、行数 ~548 <800）。
- **待处理问题记录（下个会话继续）：**
  - **用户动作（积压）**：**完全重启桌面应用**使 0006/0007/0008 迁移生效；v14/v15 纯前端**刷新即生效**。
  - 候选（未点名不做）：预览切换动画（淡入/滑动）、触摸板手势。
  - 全部验收通过后统一 `git push`。

### 0.0.1 迭代时间线（倒序）

0. **预览翻页改边缘圆形悬浮按钮（本票，2026-10-25）**——用户：「加这种图标不是更好吗 你把上下页放右上角 操作起来没这么方便啊」+ 白圆钮参考图。头部移除「← 上一项 / 下一项 →」文字按钮（右上角仅留 `n / total` 指示），媒体区左右边缘加 44px 白底毛玻璃圆形描边箭头（`left-3 / right-3 top-1/2 z-10`、`bg-white/85 shadow-lg active:scale-95`、`aria-label`）；滚动容器外包 relative 包装 + 容器 `absolute inset-0` 实现**视口锚定**（原始尺寸平移不滚走）；`total > 1` 门控与键盘/跨分页逻辑不变。typecheck/build/135 pytest 全绿；5173 冒烟（几何 44×44/边缘 12px/垂直居中、点击切换 `2 / 55`↔`1 / 55`、单图隐藏、截图目检风格一致）全通过；codereview 0 致命。坑：模板加包装 div 忘补闭合 → `[vite:vue] missing end tag` 且行号指向根节点（改嵌套先 build）。详见 [`.handoff/handoff-20261025-200229.md`](./handoff-20261025-200229.md)。
1. **预览同目录上下切换增强：跨分页遍历 + 位置指示 + ↑/↓（上一票，2026-10-25）**——用户：「预览图片和视频的窗口，加一个同目录下可以进行上下图片切换预览的功能吧」。诊断切换早已存在（按钮 + ←/→），真实缺口：只在本页 50 项内回绕、无位置指示、缺 ↑/↓。`stepPreview` 重写为 async 分页感知（末尾自动追加下一页再前进、`steppingPreview` 锁、真边界才回绕——切换遍历整个目录）；`AssetPreview` 新 props `position`/`total` 渲染按钮间 `n / total` 指示、`total > 1` 才显示整组按钮（单图目录隐藏）、回收站同样支持；`ArrowUp/Down` 并入切换。135 pytest 全绿；5173 冒烟（50 边界自动追加 51/55、全量遍历、双向回绕、↑/↓、单图隐藏、截图目检）全通过；codereview 0 致命。坑：IAB 中文 `getByText` 不稳改 evaluate DOM click；`playwright.keyboard` 不存在用合成 KeyboardEvent；指示器正则会被面板日期误报须 `.tabular-nums` 精确定位。**纯前端刷新即生效；0006–0008 迁移的重启要求积压。**详见 [`.handoff/handoff-20261025-195603.md`](./handoff-20261025-195603.md)。
1. **「其他」分类：代码文件脱离文档类别（上一票，2026-10-25）**——用户圈顶栏分类栏：「再加一个其他。代码类的不要加到文档类别里」。`guess_asset_type` 撤销 `CODE_EXTS ⊂ DOC_EXTS`（代码/配置/日志归 other，文档回归纯文档）；迁移 0008 幂等把存量误标 document 的代码资产改回 other（迁移内冻结扩展名快照）；`AppHeader` 加「其他」chip，卡片/预览/回收站 other 标签「文件」→「其他」；代码预览经 v11 other 回退通道零改动可用。135 pytest 全绿（+1）；迁移 E2E（0007 旧库启动自动升 0008 改类 + 新导入归 other）+ 5173 冒烟（chip 过滤互斥、标签、预览「类型：其他」）全通过；codereview 0 致命。坑：列表过滤参数名是 `asset_type` 非 `type`（错名被静默忽略）；保活 5173 必须 `npm run dev:web`（根 `dev` 与 Electron 互杀）。**需完全重启桌面应用使存量改类生效。**详见 [`.handoff/handoff-20261025-194335.md`](./handoff-20261025-194335.md)。
1. **侧栏目录置顶：图钉切换 + 同层置顶排序（上一票，2026-10-25）**——迁移 0007 增 `folders.pinned`（NOT NULL default false，0006 同款 batch 模式）；`list_folders` 全局 `pinned desc → sort_order → id`，build_tree 保序 → 任意层级置顶在前；`PATCH {pinned}` 走 `update_folder_info` 哨兵，改名/锁定不重置。侧栏目录行悬停加图钉按钮（`+` 与铅笔之间，置顶态 `text-accent`、`active:scale-95`、`@click.stop`），名称右侧常驻蓝色图钉徽标（镜像锁徽标）；`FolderTree → AppSidebar → App.vue` emit 链，保存成功 `loadAll` 即时重排。134 pytest 全绿（+2），5173 冒烟（解除/再置顶即时重排、刷新持久、截图目检）全通过；codereview 0 致命。**用户需完全重启桌面应用使迁移与排序生效。**冒烟揪出长跑 vite 陈旧模块教训：`curl /src/App.vue` 返回 SPA 回退 HTML，不能作模块新鲜性判据，须 vnode 探针 + 重启 vite。详见 [`.handoff/handoff-20261025-192450.md`](./handoff-20261025-192450.md)。
1. **代码文件文本预览 + 缩略图前端 object URL LRU 缓存（上一会话，2026-10-25）**——后端 `CODE_EXTS`（47 种源码/配置/日志扩展）并入 `DOC_EXTS`，新导入/外扫的 `.py`/`.ts`/`.yml` 等注册为文档；`AssetPreview.vue` 增 `CODE_PREVIEW_EXTS`、`docKind` 对 document 与**存量 other 按扩展名回退 text**（用户现有 `.py` 无需重导入即可预览）、等宽 `font-mono [tab-size:4]` code 渲染分支。新组合式 `useThumbnailObjectUrl`：模块级 LRU（240 条）共享 object URL 给资产卡与回收站行，重挂复用零网络请求、卸载不 revoke、`failed` 负缓存；AssetCard/TrashRowThumb 加载逻辑收敛至此。132 pytest 全绿（+1），5173 冒烟：代码预览 marker、存量 other 回退、首屏 4 次 `/thumbnail` 且目录切换往返零新增请求、reload 基线复现；codereview 0 致命。前端刷新即生效，新分类需重启后端进程对新导入生效。详见 [`.handoff/handoff-20261025-184747.md`](./handoff-20261025-184747.md)。
1. **侧栏密度紧凑化 + 可拖拽调节宽度（上一会话，2026-10-25）**——目录/项目/外部/标签/回收站行统一 24px、缩进 13px/层、截断名称 `title` 悬停；修复无效类 `h-7.5/py-0.2`；新 `useSidebarResize` 组合式：把手指针 1:1 拖拽 `--sidebar-w`（每帧零重渲染）、钳制 [220,480]、键盘 ←/→/Home、双击复位、localStorage 持久化；`role=separator` 把手带悬停/聚焦高亮与 aria。冒烟揪出并修复 STORAGE_KEY 损坏字面量（U+2026）。typecheck/build/131 pytest 全绿，5173 冒烟（行高/缩进/拖拽/钳制/持久化/截图目检）全通过；codereview 0 致命。纯前端、刷新即生效。详见 [`.handoff/handoff-20261025-171829.md`](./handoff-20261025-171829.md)。
1. **文件夹编辑弹窗：锁定开关 + 描述（上一会话，2026-10-25）**——侧栏铅笔升级为「编辑文件夹」弹窗（名称 + 描述 + Apple HIG 琥珀锁定开关，一次组合 PATCH）；迁移 0006 增 `folders.locked/description`；锁定目录拦截直接删除与目录/项目级联（409 `folder_locked` 点名锁定目录），锁只拦删除、不向下继承；树行琥珀锁徽标 + × 禁用 tooltip + `useFolderDelete` 前置兜底。131 pytest 全绿（+6），5173 冒烟锁定/拦截/解锁/级联/描述持久化全链路通过；codereview 0 致命。**用户需完全重启桌面应用使迁移与守卫生效。**详见 [`.handoff/handoff-20261025-165908.md`](./handoff-20261025-165908.md)。
1. **卡片提示词入口双修复（上一会话，2026-10-25）**——①无提示词资产点卡片「+ 提示词」弹出空查看框而非添加框：`PromptModal` 的 `open` watch 缺 `immediate`，卡片入口挂载即 `open=true` 无变化可监听，`initPrompt` 永不执行；加 `{ immediate: true }` 修复，标题按意图显示添加/编辑/查看。②实心蓝徽标突兀：重设计为深色毛玻璃芯片（`bg-black/55` + `backdrop-blur-sm`，与时长角标同材质），有提示词图标常驻、无提示词悬停显现，`focus-visible` 键盘可达，失效徽标同排不重叠。125 pytest 全绿，5173 四场景冒烟通过；codereview 对比度与焦点 2 建议已落实。详见 [`.handoff/handoff-20261025-163052.md`](./handoff-20261025-163052.md)。
1. **项目删除 409 诊断 + 预览/导入优化（2026-10-25 上一会话）**——diagnosing-bugs 流程确诊 409 为陈旧后端进程（时间线取证 + worktree RED/GREEN diff loop），前端加固为 404 如实重启提示；md 预览支持 GFM 表格（对齐 + 横向滚动卡片）；导入任务面板完成 5 秒自动关闭。125 pytest 全绿，5173 三项冒烟通过。**用户需完全重启桌面应用使级联项目删除生效。**详见 [`.handoff/handoff-20261025-145000.md`](./handoff-20261025-145000.md)。
1. **项目级联删除（2026-10-25 上一会话）**——解除「仅允许删除没有任何文件夹的空项目」限制：`cascade_delete_folder_ids` 共享算法 + `GET /projects/{id}/stats` + `DELETE ?cascade` + `useProjectDelete` 影响说明确认弹窗（托管→回收站、外部→仅移除索引），125 pytest 全绿，5173 冒烟通过。详见 [`.handoff/handoff-20261025-143000.md`](./handoff-20261025-143000.md)。
1. **前端回收站沉浸式预览集成（2026-10-25 上一会话）**——回收站整行点击调出沉浸预览，trashMode 恢复/永久删除（danger 确认 + 44px 热区），App.vue 瘦身至 composables 四件套 + AssetTagEditor 抽取，`/open` 放行 trashed，123 pytest 全绿，5173 浏览器冒烟全链路通过。详见 [`.handoff/handoff-20261025-123500.md`](./handoff-20261025-123500.md)。
1. **目录级联删除与回收站媒体流放行（2026-10-25 上一会话）**——Alembic 0005 迁移解开 `folder_id` 外键约束、目录资产统计接口、级联删除与回退承接机制、受控放行回收站 content 与 thumbnail 流、前端 Apple HIG 级联删除确认弹窗。详见 [`.handoff/handoff-20261025-113000.md`](./handoff-20261025-113000.md)。
2. **顶栏交互重构与层叠遮挡修复（2026-10-25 上一会话）**——搜索框平滑扩展与 `⌘K`、连体式胶囊排序控件、毛玻璃独立筛选面板、移除浮动过滤条实现零布局抖动（Zero CLS）、Header 与浮层 z-index 提升解决卡片穿透遮挡。详见 [`.handoff/handoff-20261025-101500.md`](./handoff-20261025-101500.md)。
3. **Apple HIG 规范落地与跨库移动（2026-10-25 上一会话）**——全面废除 `window.confirm`，改用全项目统一的 Apple HIG `ConfirmDialog`；更新 `AGENTS.md` 和设计规范；解禁跨项目/跨通用库资产移动限制；新增单文件不超过 800 行的架构硬性约束。详见 [`.handoff/handoff-20261025-085144.md`](./handoff-20261025-085144.md)。
2. **票 15–20（2026-10-24）**（`194df8a` → `fd4df00`，全部仅本地提交）——回收站（删除/恢复/永久删除/清空/bulk-trash 逐项结果 + 锁定文件 409 保护）、单资产重命名/移动（扩展名保留、同目录冲突、external 只读）、外部目录关联与手动扫描（层级镜像、重扫幂等、失效标记 missing、迁移 0004）、解除关联（仅删仍为 external 的索引）、外部转托管（staging+哈希校验+就地更新）、图片/视频提示词（`GET/PUT /assets/{id}/prompt`，换行逐字保留）。UI 实测全链路通过；review 加固（托管根子树跳过、提交失败补偿、选区清理、Esc 层级）已合入。
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

### 最近一次迭代（更新日期 2026-10-25，ZCode 会话 · 预览翻页改边缘圆形悬浮按钮）

- **Git 分支 / 提交：** `main` 本地 `de42a74`（web），连同积压提交未推送。
- **开发目标：** 用户：「加这种图标不是更好吗 你把上下页放右上角 操作起来没这么方便啊」+ 图片右缘白底圆钮参考图——翻页按钮从右上角文字按钮改为媒体区两侧边缘悬浮圆形箭头。
- **实际交付：** 见 [`.handoff/handoff-20261025-200229.md`](./handoff-20261025-200229.md)。头部移除「← 上一项 / 下一项 →」（右上角仅留 `n / total`）；`AssetPreview.vue` 媒体区左右边缘加 44px 白底毛玻璃圆形描边箭头按钮（`absolute left-3 / right-3 top-1/2 z-10 bg-white/85 shadow-lg active:scale-95`、`aria-label`）；滚动容器外包 `relative min-w-0 flex-1` + 容器 `absolute inset-0` 实现视口锚定（原始尺寸平移不滚走）；`total > 1` 门控与键盘/跨分页逻辑不变。
- **修改文件：** `apps/web/src/components/AssetPreview.vue`。
- **运行验证：** typecheck ✅ / build:web ✅ 1.95s / pytest ✅ 135（后端零改动）/ 5173 冒烟（复用 55 图 + 单图隔离后端）：几何 44×44/边缘内缩 12px/垂直居中 ✅、点 `›`→`2 / 55`、点 `‹`→`1 / 55` ✅、单图两钮+指示不渲染 ✅、截图 `.handoff/preview-edge-buttons.png` 目检风格与参考图一致 ✅；测毕杀后端删种子清桥接。
- **未完成 / 已知问题：** codereview 0 致命。坑：模板加包装 div 忘补 `</div>` → `[vite:vue] Element is missing end tag`（行号指根节点，真实在嵌套深处）——改嵌套后先 build 再信行号。**用户仍积压「完全重启桌面应用」（0006/0007/0008）；本票纯前端刷新即生效。**
- **下一步第一任务（1–3 个）：** ①**用户完全重启桌面应用**后实机验收预览按钮 + 其他分类 + 置顶 + 锁定；②候选（未点名不做）：预览切换动画/触摸板手势；③全部通过后统一 `git push`。

### 上一次迭代（更新日期 2026-10-25，ZCode 会话 · 预览同目录上下切换增强：跨分页遍历 + 位置指示 + ↑/↓）

- **Git 分支 / 提交：** `main` 本地 `0269505`（web）+ 文档提交，连同积压提交未推送。
- **开发目标：** 用户：「预览图片和视频的窗口，加一个同目录下可以进行上下图片切换预览的功能吧」。诊断：切换早已存在（头部按钮 + ←/→），缺口是只在本页 50 项内回绕、无位置指示、缺 ↑/↓。
- **实际交付：** 见 [`.handoff/handoff-20261025-195603.md`](./handoff-20261025-195603.md)。`App.vue` `stepPreview` async 分页感知重写（末尾自动追加下一页再前进、`steppingPreview` 锁、真边界回绕）+ `previewPosition/previewTotal/trashPreviewPosition/trashPreviewTotal` computed 传入两处预览；`AssetPreview.vue` 新 props `position`/`total`、按钮间 `n / total` 指示、`total > 1` 才渲染按钮组（单图目录隐藏）、`ArrowUp/Down` 并入 prev/next、修正 v13 过时注释。
- **修改文件：** `apps/web/src/App.vue`、`apps/web/src/components/AssetPreview.vue`。
- **运行验证：** typecheck ✅ / build:web ✅ 2.15s / pytest ✅ **135 passed**（纯前端）/ 5173 冒烟（隔离后端 `.pnav-smoke` 种子 55 张手写 PNG + 单图目录）：P06=`50/55` → 按 → 跨页自动追加 P05=`51/55`、全量遍历 `55/55`、双向回绕、↑/↓、单图按钮与指示器不渲染（`.tabular-nums` 精确验证）、截图 `.handoff/preview-nav-indicator.png` 目检 ✅；测毕杀后端删种子；vite 5173=200。
- **未完成 / 已知问题：** codereview 0 致命 0 需修。冒烟坑：IAB 中文 `getByText` 不稳（evaluate DOM click 替代）、`playwright.keyboard` 不存在（合成 KeyboardEvent）、`tab.screenshot()` 无参（`Buffer.from` 落盘）、指示器正则被面板日期误报（用 class 精确选择）。**纯前端刷新即生效；用户仍积压「完全重启桌面应用」使 0006/0007/0008 生效。**
- **下一步第一任务（1–3 个）：** ①**用户完全重启桌面应用**后实机验收预览切换 + 其他分类 + 置顶 + 锁定；②候选（未点名不做）：预览滑动切换动画/触摸板手势；③全部通过后统一 `git push`。

### 上一次迭代（更新日期 2026-10-25，ZCode 会话 · 「其他」分类：代码文件脱离文档类别）

- **Git 分支 / 提交：** `main` 本地 `7d78aff` backend / `b9c71a4` web + 文档提交，未推送。
- **开发目标：** 用户圈顶栏分类栏（全部/图片/视频/音频/文档）：「这个分类再加一个其他。代码类的不要加到文档类别里」——`.py` 等代码文件不再归文档，顶栏加「其他」chip。
- **实际交付：** 见 [`.handoff/handoff-20261025-194335.md`](./handoff-20261025-194335.md) §2–3。后端：`guess_asset_type` 撤销 `CODE_EXTS ⊂ DOC_EXTS`（代码/配置/日志归 other）；迁移 `0008_asset_code_to_other`（幂等 `reclassify_code_documents`，迁移内冻结扩展名快照，downgrade 反向）。前端：`AppHeader` 其他 chip（`asset_type=other` 后端早已支持）；`AssetCard`/`AssetPreview`/`TrashView` other 标签「文件」→「其他」；代码预览经 v11 other 扩展名回退通道零改动可用。
- **修改文件：** `backend/app/services/import_service.py`、`backend/alembic/versions/0008_asset_code_to_other.py`（新）、`backend/tests/{test_imports_api,test_migrations}.py`；`apps/web/src/components/{AppHeader,AssetCard,AssetPreview,TrashView}.vue`。
- **运行验证：** `npm run typecheck` ✅ / `npm run build:web` ✅ 1.99s / pytest ✅ **135 passed**（+1 迁移数据测试含幂等断言）/ 迁移 E2E（脚本造 0007 旧库 + 误标 document 的 .py/.pdf → 后端启动自动升 0008：API document 只剩 pdf、other 见 legacy；`POST /imports` 新 demo.py → other）✅ / 5173 冒烟（chips 含其他、三卡片标签、文档/其他/全部过滤互斥、demo.py 等宽预览 marker + 面板「类型：其他」）✅；测毕杀后端、删 `.other-smoke`、清桥接关标签页；vite 以纯 `dev:web` 保持 5173=200。
- **未完成 / 已知问题：** codereview 0 致命 0 需修。坑 ①：资产列表过滤参数名是 **`asset_type`** 非 `type`，错名被 FastAPI 静默忽略返回全量。坑 ②：根 `npm run dev` 连 Electron 且 `-k first` 互杀，保活 5173 须 `npm run dev:web`。**用户需完全重启桌面应用使 0008 存量改类生效（连同 0007 置顶、0006 锁验一并验收）。**
- **下一步第一任务（1–3 个）：** ①**用户完全重启桌面应用**后实机验收「其他」分类 + 置顶 + 锁定链路；②候选（未点名不做）：「代码」单独 chip；③全部通过后统一 `git push`。

### 上一次迭代（更新日期 2026-10-25，ZCode 会话 · 侧栏目录置顶：图钉切换 + 同层置顶排序）

- **Git 分支 / 提交：** `main` 本地两组原子提交（backend / web）+ 文档提交，未推送。
- **开发目标：** 「加一个目录置顶的功能吧 [$design-taste-frontend] [$apple-design] 菜单边上有个置顶图标可以点击置顶以及解除置顶」——目录行悬停操作区加图钉切换，置顶目录排同层最前。
- **实际交付：** 见 [`.handoff/handoff-20261025-192450.md`](./handoff-20261025-192450.md) §2–3。后端：迁移 `0007_folder_pinned`（`folders.pinned BOOLEAN NOT NULL DEFAULT false`，0006 同款 batch 模式）、`list_folders` 排序 `pinned desc → sort_order → id`（build_tree 保序 → 任意层级生效）、`update_folder_info` pinned 哨兵、`PATCH` 组合分支、测试 +2。前端：`SidebarIcon` 新 `pin` 线性图标、`FolderTree.vue` 图钉按钮（`+`/铅笔之间，置顶态 `text-accent`、`active:scale-95`、`@click.stop`）+ 名称右侧常驻 `text-accent` 图钉徽标（镜像琥珀锁徽标）+ 递归转发、`AppSidebar` 双树转发、`App.vue onTogglePinFolder`（`updateFolder` 成功 `loadAll` 即时重排）。
- **修改文件：** `backend/alembic/versions/0007_folder_pinned.py`（新）、`backend/app/{models,schemas,services,api/v1}/folder*`、`backend/tests/{test_folders_api,test_migrations}.py`；`apps/web/src/api/types.ts`、`apps/web/src/components/{SidebarIcon,FolderTree,AppSidebar}.vue`、`apps/web/src/App.vue`。
- **运行验证：** `npm run typecheck` ✅ / `npm run build:web` ✅ 2.11s / pytest ✅ **134 passed**（+2：同层置顶排序含子层级作用域与取消还原、默认 false 且改名/锁定 PATCH 不重置）/ 5173 冒烟（隔离后端 63995 + 桥 + 种子项目/三级目录，真实数据 0 接触）✅ UI 解除置顶 PATCH 200 顺序立即还原、再置顶即时排首 + accent 蓝徽标（rgb(37,99,235)）、刷新持久、截图目检 hover `+ / 📌 / ✏️ / ×` 排布干净；测毕杀进程、删 `.pin-smoke`、清桥接关标签页；vite 掉线已重启（5173 返回 200）。
- **未完成 / 已知问题：** codereview 0 致命 0 需修；冒烟揪出长跑 vite 陈旧模块坑：UI 点击无反应＝App.vue 模块未更新（vnode 探针证实 props 缺 `onTogglePinFolder`；`touch` 不失效、`curl /src/App.vue` 返回 SPA 回退 HTML **不能**作新鲜性判据），重启 vite + 硬刷新解决。**用户需完全重启桌面应用使 0007 迁移与置顶排序生效（连同前会话 0006/代码预览分类一并验收）。**
- **下一步第一任务（1–3 个）：** ①**用户完全重启桌面应用**后实机验收置顶全链路；②候选（未点名不做）：拖拽排序与置顶合并交互、右键菜单置顶入口；③全部通过后统一 `git push`。

### 上一次迭代（更新日期 2026-10-25，ZCode 会话 · 代码文件文本预览 + 缩略图前端 object URL LRU 缓存）

- **Git 分支 / 提交：** `main` 本地两组原子提交（`d49b851` backend / `1d1c3cf` web），未推送。
- **开发目标：** ①代码类文件（用户截图 `qc_case.py`）此前落到「浏览器无法直接播放」兜底，要像文本一样预览；②回答并补齐「列表图片/视频缩略图缓存」——后端盘缓存（JPEG + size/mtime 指纹 sidecar）早已存在，缺口在前端每次挂载重新 fetch blob、无跨挂载缓存。
- **实际交付：** 见 [`.handoff/handoff-20261025-184747.md`](./handoff-20261025-184747.md) §3–4。后端：`CODE_EXTS`（47 源码/配置/日志扩展）并入 `DOC_EXTS`，`guess_asset_type` 零改动生效（import/外扫共用），测试 +1。前端：`AssetPreview.vue` `CODE_PREVIEW_EXTS` + `docKind` document/存量 other 双分支回退 text + 等宽 `font-mono [tab-size:4]` code 分支；新 `useThumbnailObjectUrl`（`useThumbnailCache.ts` 114 行）模块级 LRU 240 条共享 object URL + `failed` 负缓存，AssetCard（−45 行）/TrashRowThumb（43→23 行）收敛接入。
- **修改文件：** `backend/app/services/import_service.py`、`backend/tests/test_imports_api.py`；`apps/web/src/composables/useThumbnailCache.ts`（新）、`apps/web/src/components/{AssetPreview,AssetCard,TrashRowThumb}.vue`。
- **运行验证：** `npm run typecheck` ✅ / `npm run build:web` ✅ 5.70s / pytest ✅ **132 passed**（+1）/ 5173 冒烟（隔离后端 59073，种子 3 PNG + 1 MP4 + qc_case.py(document) + legacy_py.py(SQL 改 other 模拟存量)）✅ 代码等宽预览 marker 命中且「无法播放」消失、存量 other 回退预览、首屏 4 次 `/thumbnail`、目录切换往返 6 卡重挂网络请求仍 4（零新增）、reload 基线复现、截图目检；测毕杀进程、删 `.code-preview-smoke`、清桥接关标签页。
- **未完成 / 已知问题：** codereview 0 致命 0 需修；已知取舍：源文件替换且后端重生成缩略图后缓存显示旧图至 LRU 逐出（512px 列表场景可接受）；后端未加显式 Cache-Control（避免陈旧，前端内存缓存已消除重复请求）。**用户需重启桌面应用后端进程使新分类对新导入生效；现有 `.py` 资产前端刷新即已可预览。**

### 上一次迭代（更新日期 2026-10-25，ZCode 会话 · 侧栏密度紧凑化 + 可拖拽调节宽度）

- **Git 分支 / 提交：** `main` 本地单组原子提交（`f6c251c` web + docs），未推送。
- **开发目标：** 侧栏目录上下间距与逐层缩进过大、深层名称截断；左侧区域需支持拖拽调节宽度。附 `$apple-design` `$design-taste-frontend`（dense 产品 UI 仅采纳密度/工艺部分）。
- **实际交付：** 见 [`.handoff/handoff-20261025-171829.md`](./handoff-20261025-171829.md) §2–3。密度：全部侧栏行 24px + `space-y-px`、缩进 13px/层、目录/项目/标签名 `title` 悬停、修复无效类 `h-7.5`（×3）与 `py-0.2`。宽度：`useSidebarResize.ts`（CSS 变量 `--sidebar-w` 拖拽期零重渲染 1:1 跟手、钳制 [220,480]、松手持久化、键盘/双击复位）+ App.vue `role="separator"` 把手（8px 热区、悬停/聚焦/按下高亮条、aria/tabindex）。
- **修改文件：** `apps/web/src/composables/useSidebarResize.ts`（新 94 行）、`apps/web/src/App.vue`（761 行）、`apps/web/src/components/AppSidebar.vue`、`apps/web/src/components/FolderTree.vue`。后端 0 改动。
- **运行验证：** `npm run typecheck` ✅ / `npm run build:web` ✅ 1.93s / pytest ✅ 131 passed（回归）/ 5173 冒烟（隔离后端 62841，六层嵌套种子目录）✅ 行高 24px 实测、逐层 13px、真实指针拖拽跟手 + 上下钳制 + 双击复位 + 刷新持久化、悬停高亮实测、截图目检；测毕杀进程、删 `.sidebar-smoke`、清桥接关标签页。vite 5173 会话后保持运行。
- **未完成 / 已知问题：** codereview 0 致命 0 需修；冒烟中揪出并修复 `STORAGE_KEY` 损坏字面量（U+2026）；纯前端改动，Electron 无需重启，刷新即生效。

### 上上次迭代（更新日期 2026-10-25，ZCode 会话 · 文件夹「编辑文件夹」弹窗：锁定开关 + 描述，级联删除锁定拦截）

- **Git 分支 / 提交：** `main` 本地三组原子提交（`f611783` backend / `c234b43` web / 文档），全部未推送。
- **开发目标：** 侧栏文件夹铅笔从「重命名文件夹」升级为「编辑文件夹」弹窗，可编辑目录信息；第一功能 = 锁定开关：锁定后该目录不能被删除（含父级/项目级联），但子目录与资产仍可单独删除。grill-me 定案：级联遇锁定整次拦截 409、锁只拦删除（重命名/移动允许）、字段 = 名称 + 锁定 + 描述。
- **实际交付：** 见 [`.handoff/handoff-20261025-165908.md`](./handoff-20261025-165908.md) §1–2。后端：迁移 0006（`folders.locked` NOT NULL default false + `folders.description` ≤2000）、`update_folder_info` 哨兵语义（未提供保持 / 显式 null 空白清空 / strip / 超长 422）、`delete_folder` 锁定守卫 + `cascade_delete_folder_ids` 子树锁定单查询拦截（目录与项目级联共用）、`PATCH` 组合分支。前端：`FolderEditDialog.vue`（119 行，名称/描述/琥珀 `role="switch"` 开关，单保存一次 PATCH）、树行琥珀锁徽标 + × `disabled` + 锁定 tooltip、`useFolderDelete` 锁定 warning 兜底、store `updateFolder`。
- **修改文件：** `backend/alembic/versions/0006_folder_lock_description.py`（新）、`backend/app/{models,schemas,services,api/v1}/folder*`、`backend/tests/{test_folders_api,test_migrations}.py`；`apps/web/src/components/FolderEditDialog.vue`（新）、`FolderTree/AppSidebar/SidebarIcon.vue`、`App.vue`、`api/{types,client}.ts`、`stores/library.ts`、`composables/{useDialogFlows,useFolderDelete}.ts`。
- **运行验证：** `npm run typecheck` ✅ / `npm run build:web` ✅ 2.03s / `.venv/Scripts/python.exe -m pytest backend/tests` ✅ **131 passed**（+6）/ 5173 浏览器冒烟（隔离后端 58469 + localStorage 桥，真实数据 0 接触）✅ 锁徽标琥珀实测、× disabled、级联 409 toast 点名「内层」、解锁→徽标消失→删除成功、描述持久化、NameDialog 新建回归；测毕杀进程、删 `.folder-lock-smoke`、清桥接，5173 复测正常。
- **未完成 / 已知问题：** codereview 0 致命 0 需修；新组件 119 行合规；`{"locked": null}` 显式 null 按「不改动」处理（弹窗恒携带布尔值，无实际影响）。
- **下一步第一任务（1–3 个）：** ①**用户完全重启桌面应用**（0006 迁移与守卫需后端重启）后实机验收锁定全链路 + 前会话遗留项（项目级联、票 21/22、卡片芯片）；②编辑弹窗后续字段候选（封面/颜色/归档）待用户点名；③全部通过后统一 `git push`。

### 上一迭代（2026-10-25，ZCode 会话 · 卡片提示词入口双修复：挂载时序进编辑态 + 毛玻璃芯片重设计）

- **Git 分支 / 提交：** `main` 本地三组原子提交（`79257e8` fix / `8cd8e37` feat / 文档），全部未推送。
- **开发目标：** ①无提示词资产点卡片「+ 提示词」应进入添加提示词编辑框，实测弹出的是空白查看框；②卡片实心蓝色「+ 提示词」徽标突兀，需按 design-taste-frontend / apple-design 优化显示。
- **实际交付：** 见 [`.handoff/handoff-20261025-163052.md`](./handoff-20261025-163052.md) §1。要点：根因 = `PromptModal` 的 `open` watch 缺 `immediate`——卡片入口 `AssetPreview` setup 期同步置 `open=true`，挂载即真值无变化可监听，`initPrompt()`（`promptEditing = !hasPrompt`）永不执行；修复 = `{ immediate: true }` + 标题按状态显示「添加提示词/编辑提示词/提示词 · 名称」。徽标重设计 = 深色毛玻璃芯片（`bg-black/55 backdrop-blur-sm`、hover `/75`，与时长角标 `bg-black/60` 同材质家族），有提示词图标常驻悬停展开、无提示词悬停卡片显现「+ 提示词」，`focus-visible:opacity-100` 键盘可达，失效徽标与芯片同处左下 `bottom-1.5 left-1.5` 芯片行互不遮挡。
- **修改文件：** `apps/web/src/components/PromptModal.vue`、`apps/web/src/components/AssetCard.vue`（纯前端，后端 0 改动）。
- **运行验证：** `npm run typecheck` ✅ / `npm run build:web` ✅ 1.93s / `.venv/Scripts/python.exe -m pytest backend/tests` ✅ **125 passed** / 5173 浏览器冒烟（隔离后端 + localStorage 桥，真实数据 0 接触、用户 vite 未动）✅ 四场景：无提示词点入直达添加态（标题+聚焦确认）、保存换行逐字保留且卡片图标翻转、有提示词查看态+复制正常、悬停芯片实测 `rgba(0,0,0,0.55)`+`blur(4px)` 截图确认；测毕杀进程、删 `.prompt-smoke`、清桥接与冒烟标签页（53220 复测 000、5173 复测 200）。
- **未完成 / 已知问题：** codereview 0 致命、2 建议已落实（对比度 `/45→/55`+hover `/70→/75` 过 AA、`focus-visible` 键盘可见）；行数合规（PromptModal ≈230 / AssetCard ≈150）。
- **下一步第一任务（1–3 个）：** ①用户实机验收卡片芯片观感 + 卡片入口直达添加框（连同前会话级联删除重启验收、票 21/22）；②review 遗留小项批量小修复；③全部通过后统一 `git push`。

### 上一迭代（2026-10-25，ZCode 会话 · 项目删除 409 陈旧后端诊断与加固 + md 表格预览 + 导入面板自动关闭）

- **Git 分支 / 提交：** `main` 本地四组原子提交（前端 fix / feat ×2 / 文档），全部未推送。
- **开发目标：** ①用户报告「文件夹已级联删除后，删除项目仍提示 409 项目仍包含 1 个文件夹，实际未删除成功」，用 diagnosing-bugs 技能定位根因；②md 文档预览中 GFM 表格按原始管道符文本显示，需渲染为表格；③导入完成任务面板希望 5 秒自动关闭。
- **实际交付：** 见 [`.handoff/handoff-20261025-145000.md`](./handoff-20261025-145000.md) §1–2。要点：诊断结论为**非代码缺陷**——用户 Electron 派生后端进程（12:16:53 启动）早于级联代码提交（13:28:17），旧 FastAPI 静默忽略 `?cascade=true` 走旧 409 拦截路径；证据链 = 进程时间线取证 + `git worktree d3269d7` RED（409 文案逐字复现）/ HEAD GREEN（204）。前端加固：`ApiRequestError.status` + `useProjectDelete` 遇 stats 404 如实提示重启。`utils/markdown.ts` GFM 表格解析（表头+分隔行识别、`:---:`/`---:` 对齐、overflow-x-auto 圆角卡片表格）。`ImportJobPanel.vue` 完成态 5 秒 `dismissImportJob`、回到运行态撤销计时、卸载清理。
- **修改文件：** `apps/web/src/api/client.ts`、`apps/web/src/composables/useProjectDelete.ts`、`apps/web/src/utils/markdown.ts`、`apps/web/src/components/ImportJobPanel.vue`。
- **运行验证：** `npm run typecheck` ✅ / `npm run build:web` ✅ 1.91s / `.venv/Scripts/python.exe -m pytest backend/tests` ✅ **125 passed** / 5173 浏览器冒烟（隔离后端 + localStorage 桥，真实数据 0 接触、用户 vite 未动）✅ 三项：表格渲染为样式化表格（无 `| --- |` 残留）、面板完成 7.5s 后自动消失、级联删除成功无 409（回收站 +2），截图确认；测毕清理隔离数据/进程/worktree/浏览器桥接与冒烟标签页。
- **未完成 / 已知问题：** **用户必须完全退出并重启 Ryan_DAM 桌面应用**，项目级联删除才能生效（Electron 派生 Python 后端无热重载）；codereview 0 致命 0 建议；行数全部合规。
- **下一步第一任务（1–3 个）：** ①用户重启应用实机验证级联删除 + 票 21（拖出）/票 22（终验）；②review 遗留小项批量小修复；③全部通过后统一 `git push`。

### 上一迭代（2026-10-25，ZCode 会话 · 项目级联删除，解除空项目限制）

- **Git 分支 / 提交：** `main` 本地三组原子提交（后端 / 前端 / 文档），全部未推送。
- **开发目标：** 用户反馈「删除项目」弹窗仍限制"仅允许删除没有任何文件夹的空项目"，要求非空项目也能连同文件夹、子文件夹与文件一起删除；语义对齐既有目录级联（托管→回收站、外部→仅移除索引、源文件永不删除）。
- **实际交付：** 见 [`.handoff/handoff-20261025-143000.md`](./handoff-20261025-143000.md) §1。要点：`cascade_delete_folder_ids(db, root_ids)` 共享级联算法（多根去重）、`get_project_stats` + `ProjectStats` schema、`GET /projects/{id}/stats`、`DELETE /projects/{id}?cascade=true`（非空未 cascade 仍 409 `project_not_empty`）、前端 `useProjectDelete`（空项目轻确认 / 非空级联影响说明 + 异常回退）、`client.deleteProject(id, cascade)`、store 删除后并行刷新库/回收站/外部源。
- **修改文件：** `backend/app/services/folder_service.py`、`project_service.py`、`backend/app/schemas/project.py`、`backend/app/api/v1/projects.py`、`backend/tests/test_projects_api.py`；`apps/web/src/composables/useProjectDelete.ts`（新）、`api/client.ts`、`api/types.ts`、`stores/library.ts`、`App.vue`、`components/AppSidebar.vue`。
- **运行验证：** `npm run typecheck` ✅ / `npm run build:web` ✅ 1.97s / `.venv/Scripts/python.exe -m pytest backend/tests` ✅ **125 passed**（新增 2 项）/ 5173 浏览器冒烟（隔离后端 + localStorage 桥，真实数据 0 接触）✅：级联对话框文案与数字准确、确认后项目/目录/外部源消失且回收站 +1、空项目轻对话框、取消关闭；测毕清理隔离数据与进程。
- **未完成 / 已知问题：** codereview 0 致命 0 建议；无硬编码；关键文件全部 < 800 行（project_service 100 / folder_service 322 / useProjectDelete 78 / App.vue 715）。
- **下一步第一任务（1–3 个）：** ①用户实机验收票 21（拖出）/票 22（终验）；②review 遗留小项批量小修复；③如需 GitHub Issues 发布用 `to-issues`。

### 上一迭代（2026-10-25，ZCode 会话 · 前端回收站沉浸式预览与恢复/永久删除集成）

- **Git 分支 / 提交：** `main` 本地三组原子提交（`20d041d` 后端 / 前端 / 文档），全部未推送；本批提交同时收编了 101500（顶栏重构）与 113000（级联删除后端）两个会话遗留的未提交工作（均已在上一会话验证通过）。
- **开发目标：** 完成 113000 交接指定的唯一任务——回收站 TrashView 沉浸式预览与恢复/永久删除交互集成，并按 apple-design/codereview 规范全量审查。
- **实际交付：** 见 [`.handoff/handoff-20261025-123500.md`](./handoff-20261025-123500.md) §1。要点：行点击整行预览（三态交互）、`trashMode` 预览面板（回收站信息块 + 44px 恢复/永久删除按钮 + danger 确认）、`useConfirmDialog/useFolderDelete/useDialogFlows/useTrashPreview` 四 composables 与 `AssetTagEditor.vue` 抽取、`ConfirmIntent` 类型复用、`/open` 放行 trashed + 2 项回归测试、`SERVABLE_STATUSES` 常量、跨视图预览 watch 关闭。
- **修改文件：** `backend/app/api/v1/assets.py`、`backend/tests/test_content_api.py`；`apps/web/src/App.vue`、`components/AssetPreview.vue`、`components/TrashView.vue`、`components/TrashRowThumb.vue`、`components/AssetTagEditor.vue`、`composables/`（4 新文件）。
- **运行验证：** `npm run typecheck` ✅ / `npm run build:web` ✅ 2.29s / `.venv/Scripts/python.exe -m pytest backend/tests` ✅ **123 passed** / 5173 浏览器冒烟（隔离后端 + localStorage 桥，用户真实数据 0 接触）✅ 全链路 + 截图确认 Apple HIG 质感；测毕已杀冒烟后端进程并删除 `.ui-smoke-data` 与临时素材。
- **未完成 / 已知问题：** codereview 0 致命、3 建议已修；信息项（`out as any` 历史遗留、AssetTagEditor props 写回、2MB 截断有注释、z 层级链）不修；预览浮层遮挡侧栏导致 watch 守卫仅程序化生效（预期）。
- **下一步第一任务（1–3 个）：** ①用户实机验收票 21（拖出）/票 22（终验）；②review 遗留小项批量小修复；③如需 GitHub Issues 发布用 `to-issues`。

### 上一迭代（2026-10-24，票 15–20）

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
