# Ryan_DAM V1 功能回归快照与验证基线（V2-01）

- **核实日期**：2026-10-27
- **基线分支**：`feat/phase2-ai-workbench`
- **关联任务**：`IMPLEMENTATION_PLAN_V2.md` 之 `V2-01 基线检查与 V1 回归快照`

---

## 1. V1 数据层与数据库迁移基线（Alembic 0001–0009）

当前系统的数据库迁移版本完整覆盖 V1 全部功能，演进历史如下：

| 版本号 | 迁移脚本 | 变更核心内容 |
|---|---|---|
| `0001` | `0001_initial_schema.py` | 初始全量模型（9张核心表）：`projects`, `folders`, `assets`, `tags`, `asset_tags`, `app_settings`, `import_jobs`, `import_job_items`, `external_sources` |
| `0002` | `0002_import_job_target_folder.py` | 导入任务关联目标文件夹 `import_jobs.target_folder_id` |
| `0003` | `0003_import_item_target_folder.py` | 文件夹导入时 item 级目标文件夹 `import_job_items.target_folder_id`（支持层级镜像） |
| `0004` | `0004_asset_status_missing.py` | 外部资产失效标记 `assets.status = 'missing'` 及约束更新 |
| `0005` | `0005_asset_folder_nullable.py` | 目录级联删除解绑：`assets.folder_id` 允许为 NULL |
| `0006` | `0006_folder_lock_description.py` | 目录编辑增强：新增 `folders.locked`（删除防护锁）与 `folders.description` |
| `0007` | `0007_folder_pinned.py` | 目录置顶排序：新增 `folders.pinned`，按 `pinned DESC, sort_order ASC, id ASC` 排序 |
| `0008` | `0008_asset_code_to_other.py` | 分类修正：代码类文件脱离文档分类，归入 `other`（其他）分类 |
| `0009` | `0009_external_mount_folder.py` | 外部目录同名挂载：新增 `external_sources.mount_folder_id` |

### 核心不变量与模型约束：
1. **`Asset` 表（`backend/app/models/asset.py`）**：
   - `prompt_text`: `Text`, nullable=True（每张资产严格只有一份完整多行提示词，保留原始换行）。
   - `source_type`: `String(16)`, CHECK IN ('managed', 'external')（仅表示物理文件存储模式，绝不混淆为 AI 创作来源）。
   - `status`: `String(16)`, CHECK IN ('active', 'trashed', 'missing')。
   - `file_path`: `Text`, not nullable（每个资产必须保存绝对磁盘物理路径）。
   - V2 扩展要求：在后续迁移 `0010` 中新增 `asset_origin`, `prompt_origin`, `generation_task_id`, `generation_result_id`, `prompt_revision`，保持 V1 字段原貌不变。

---

## 2. 后端核心服务模型与边界

1. **`ImportWorker`（`backend/app/services/import_service.py`）**：
   - 专属于文件与文件夹导入任务的单线程有界队列执行器（线程名 `ryan-dam-import-worker`）。
   - 服务启动时由 `recover_stale_jobs` 自动将未完成的 `queued/running` 状态标记为 `interrupted`。
   - **V2 约束**：AI 创作、模型推理与反推必须使用独立的 `TaskScheduler` 与持久化执行器，受控并发，严禁直接混入 `ImportWorker` 避免相互阻塞。

2. **存储与文件安全规范**：
   - 托管资产默认存放在 `app_settings.managed_root`（默认 `D:\Ryan_DAM\assets`）。
   - 导入落盘顺序：空间预检 → staging 写入 → SHA-256 校验 → 原子落盘到 `objects/<asset-id>/<filename>` → 事务落库 → 失败补偿清理。
   - 外部资产绝对只读，移除索引或解除关联不删除用户磁盘源文件；转托管就地更新原资产记录，保留 ID、标签、提示词且源文件不删。

---

## 3. 前端交互与架构基线

1. **架构与代码规范**：
   - 全项目严格遵守单文件 800 行上限（`App.vue` 当前 714 行，核心模块已抽离 `useImportFlow.ts`, `useSidebarResize.ts`, `useThumbnailCache.ts` 等）。
   - 严禁使用浏览器原生 `alert` / `confirm` / `prompt`，全站统一复用 Apple HIG 风格的 `ConfirmDialog.vue` 与 `NameDialog.vue`。
   - 桌面端受控 IPC：主进程严格校验路径，渲染进程仅传递 `assetId` 进行原生文件拖拽（`drag:start-asset`）。

2. **快捷键与交互状态**：
   - <kbd>Ctrl+A</kbd> / <kbd>Cmd+A</kbd> 全选，<kbd>Shift + Click</kbd> 区间连选，<kbd>Esc</kbd> 退出预览或取消选择。
   - 浏览模式（直接大图预览）与多选模式（点选卡片或勾选框）无缝区分。

---

## 4. 自动化回归冒烟清单与执行标准

每次提交前必须确保以下三项自动化门禁全部 100% 绿灯：
1. **类型检查**：`npm run typecheck`（Vue 3 + TypeScript 严格无报错）
2. **生产构建**：`npm run build:web`（Vite 生产打包通过，资源无缺失）
3. **单元与集成测试**：`./.venv/Scripts/python.exe -m pytest backend/tests`（144 项全通过）
4. **真实独立服务 HTTP 冒烟**：`./.venv/Scripts/python.exe scripts/e2e_smoke.py`（21 项全通过，含服务健康、目录树、设置持久化、文件导入、缩略图生成与重启数据恢复）
