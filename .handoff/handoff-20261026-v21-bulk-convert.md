# Handoff v21: 批量转为系统托管功能落地

> **提交记录：** 2026-10-26，ZCode 会话
> **分支：** `main`
> **涉及改动：** 前端 4 文件 + 后端 4 文件（共 8 文件）

---

## 1. 需求背景

用户反馈：在资产画廊进行批量选择时，当选中的素材包含外部链接素材时，希望在现有的底部批量操作浮动栏（已选 X 项、全选、加标签、移除标签、移动到…、删除、取消）中增加一个批量操作项：「转为系统托管」。

---

## 2. 核心架构与落地细节

### 2.1 后端批量转托管端点与服务（原子性与单项容错）

1. **Schema (`backend/app/schemas/bulk.py`)**：
   - 增加 `BulkConvertPayload`，包含 `asset_ids: list[int] = Field(min_length=1, max_length=200)`。
2. **Service (`backend/app/services/bulk_service.py`)**：
   - 实现 `bulk_convert_to_managed(db: Session, asset_ids: list[int]) -> list[ItemResult]`；
   - 载入资产并进行有效性校验；
   - 若资产已为 `managed`，标记 `ok=False` 并提示「该资产已经是系统托管，无需转换」；
   - 对外部资产调用 `external_service.convert_to_managed(db, asset_id)`，执行复制、哈希校验、原子落盘与就地更新（保留 ID、目录、标签和提示词，源文件保留）；
   - 捕获异常，单个资产故障不阻断其余资产，以 `ItemResult` 形式逐项汇报。
3. **API (`backend/app/api/v1/bulk.py`)**：
   - 暴露 `POST /api/v1/assets/bulk-convert-to-managed`，输出统一格式的 `BulkResult(ok_count, failed_count, items)`。
4. **测试 (`backend/tests/test_bulk_api.py`)**：
   - 编写 `test_bulk_convert_to_managed`，全链路测试外部资产批量转托管、混合已托管资产的容错、源文件保留及元数据状态。全部 144 项 pytest 绿灯通过。

### 2.2 前端浮动操作栏与确认弹窗（Apple HIG 规范）

1. **API Client (`apps/web/src/api/client.ts`)**：
   - 暴露 `api.bulkConvertToManaged(payload)`。
2. **Store (`apps/web/src/stores/library.ts`)**：
   - 暴露 `bulkConvertToManagedSelected(targetAssetIds?)`，转换完成后自动调用 `loadExternalSources()`、`loadAll()`、`refreshCurrentAssetsQuiet()` 并清空选择，给出操作完成 Toast。
3. **组件 (`apps/web/src/components/BatchActionBar.vue`)**：
   - 增加 `hasExternalSelected` 计算属性，实时监测当前选中的资产列表中是否含有 `source_type === 'external'` 的素材；
   - 若有，在「移动到…」之后且在「删除」之前渲染「转为系统托管」按钮，点击时关闭已展开面板并 emit `ask-convert`。
4. **主界面 (`apps/web/src/App.vue`)**：
   - 实现 `askBulkConvertToManaged`，遵循 Apple HIG 规范调用 `ask(...)` 弹出 `ConfirmDialog`（`intent: "default"`）；
   - 弹窗清晰告知将要转换的外部素材数量，说明「文件将复制到托管存储并就地更新资产记录（保留目录与标签），原外部文件不会被删除」；
   - 用户确认后执行批量转换；
   - `App.vue` 当前代码行数 714 行，完全符合 800 行上限规范。

---

## 3. 验证结果

1. **类型检查**：`npm run typecheck` 0 error，完全通过。
2. **Web 生产构建**：`npm run build:web` 3.72s 成功，产物正常。
3. **后端单元测试**：`.venv/Scripts/python.exe -m pytest backend/tests` 144 个测试用例全部通过（100% passed）。
