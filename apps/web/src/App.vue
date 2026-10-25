<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

import AssetPreview from "./components/AssetPreview.vue";
import AssetGallery from "./components/AssetGallery.vue";
import ImportJobPanel from "./components/ImportJobPanel.vue";
import NameDialog from "./components/NameDialog.vue";
import FolderEditDialog from "./components/FolderEditDialog.vue";
import ConfirmDialog from "./components/ConfirmDialog.vue";
import Stage0Panel from "./components/Stage0Panel.vue";
import AppSidebar from "./components/AppSidebar.vue";
import AppHeader from "./components/AppHeader.vue";
import TrashView from "./components/TrashView.vue";
import BatchActionBar from "./components/BatchActionBar.vue";
import TargetFolderDialog from "./components/TargetFolderDialog.vue";
import SettingsDialog from "./components/SettingsDialog.vue";
import { useFolderOptions } from "./composables/useFolderOptions";
import { useConfirmDialog } from "./composables/useConfirmDialog";
import { useDialogFlows } from "./composables/useDialogFlows";
import { useFolderDelete } from "./composables/useFolderDelete";
import { useProjectDelete } from "./composables/useProjectDelete";
import { useTrashPreview } from "./composables/useTrashPreview";

import type { ExternalSource, FolderEditPayload, FolderNode } from "./api/types";
import {
  bulkTrashSelected,
  clearAssetSelection,
  clearAssets,
  convertExternalToManaged,
  deleteAssetToTrash,
  deleteTag,
  emptyTrashAll,
  ensureTopLevelFolder,
  fetchAssets,
  importFiles,
  importFolder,
  library,
  linkExternalSource,
  loadAll,
  loadExternalSources,
  loadTags,
  loadTrash,
  moveAssetToFolder,
  rescanExternalSource,
  toggleAssetSelection,
  unlinkExternalSource,
  updateFolder
} from "./stores/library";

type TargetDialogRequest =
  | { kind: "external-link"; root: string }
  | { kind: "import-files" }
  | { kind: "import-folder" };

const targetDialog = ref<TargetDialogRequest | null>(null);
const showStage0 = ref(false);
const showSettingsDialog = ref(false);
const activeScope = ref<"general" | "project">("general");
const activeProjectId = ref<number | null>(null);
const activeFolderId = ref<number | null>(null);
const previewIndex = ref<number | null>(null);
const galleryRef = ref<InstanceType<typeof AssetGallery> | null>(null);
const viewMode = ref<"library" | "trash">("library");
let savedScrollTop = 0;

const { allFolderGroups, allFolderOptions, flattenFolderNodes } = useFolderOptions();

// Apple HIG 确认弹窗 / 通用输入对话框 / 目录与项目级联删除 / 回收站沉浸式预览
const { confirmDialog, ask, resolveConfirm, dismissConfirm } = useConfirmDialog();
const { dialog, dialogTitle, dialogInitial, onDialogConfirm } = useDialogFlows({
  onAssetRenamed: relocatePreview
});
const { askDeleteFolder } = useFolderDelete(ask);
const { askDeleteProject: confirmDeleteProject } = useProjectDelete(ask);
const {
  trashPreviewItem,
  trashPreviewAsset,
  openTrashPreview,
  closeTrashPreview,
  stepTrashPreview,
  restoreTrashItem,
  askPermanentDeleteTrashItem
} = useTrashPreview(ask);

function onRestoreFromTrashPreview(): void {
  if (trashPreviewItem.value) restoreTrashItem(trashPreviewItem.value);
}

function onPermanentDeleteFromTrashPreview(): void {
  if (trashPreviewItem.value) askPermanentDeleteTrashItem(trashPreviewItem.value);
}

/** 切换库/回收站视图时关闭另一视图的沉浸式预览，避免浮层跨视图残留或叠加。 */
watch(viewMode, (mode) => {
  if (mode === "trash") closePreview();
  else closeTrashPreview();
});

function selectTrash(): void {
  viewMode.value = "trash";
  void loadTrash();
}

function askEmptyTrash(): void {
  const count = library.trash.length;
  if (count === 0) return;
  ask({
    title: "清空回收站？",
    description: `确定清空回收站吗？将永久删除 ${count} 项。\n文件会从磁盘中直接删除，此操作不可恢复。`,
    confirmText: "清空回收站",
    intent: "danger",
    action: () => {
      void emptyTrashAll();
    }
  });
}

function askBulkTrash(): void {
  const count = library.selectedAssetIds.length;
  if (count === 0) return;
  ask({
    title: "删除选中的资产？",
    description: `确定删除选中的 ${count} 项吗？\n托管资产将移入回收站，可随时恢复；外部资产仅移除索引，不会删除源文件。`,
    confirmText: "删除资产",
    intent: "danger",
    action: () => {
      void bulkTrashSelected();
    }
  });
}

async function onDeleteFromPreview(assetId: number): Promise<void> {
  if (await deleteAssetToTrash(assetId)) closePreview();
}

function onRenameFromPreview(): void {
  const asset = previewAsset.value;
  if (!asset) return;
  const base = asset.name.replace(/\.[^.\\/]+$/, "");
  dialog.value = { kind: "asset-rename", assetId: asset.id, initial: base };
}

function relocatePreview(assetId: number): void {
  const assets = library.assets;
  if (!assets) {
    closePreview();
    return;
  }
  const index = assets.items.findIndex((a) => a.id === assetId);
  if (index < 0) closePreview();
  else previewIndex.value = index;
}

async function onMoveFromPreview(assetId: number, folderId: number): Promise<void> {
  if (await moveAssetToFolder(assetId, folderId)) closePreview();
}

async function onConvertFromPreview(assetId: number): Promise<void> {
  if (await convertExternalToManaged(assetId)) relocatePreview(assetId);
}

// ── 外部目录关联 ──────────────────────────────────────────────
async function startLinkExternal(): Promise<void> {
  let folder: string | null = null;
  try {
    folder = await window.ryanDam.selectFolder();
  } catch {
    return;
  }
  if (!folder) return;
  targetDialog.value = { kind: "external-link", root: folder };
}

async function onTargetDialogPick(folderId: number): Promise<void> {
  const request = targetDialog.value;
  targetDialog.value = null;
  if (!request) return;
  if (request.kind === "external-link") {
    await linkExternalSource(request.root, folderId);
    return;
  }
  if (request.kind === "import-files") await runFilesImport(folderId);
  else await runFolderImport(folderId);
}

function askUnlinkExternal(source: ExternalSource): void {
  ask({
    title: "解除外部目录关联？",
    description:
      `确定解除关联「${source.display_name ?? source.root_path}」吗？\n\n` +
      `将移除该来源下 ${source.asset_count} 个外部资产索引（含 ${source.missing_count} 个失效项）；` +
      `不会删除磁盘上的源文件；已转为托管的资产不受影响。`,
    confirmText: "解除关联",
    intent: "warning",
    action: () => {
      void unlinkExternalSource(source.id);
    }
  });
}

function findFolder(nodes: FolderNode[], id: number): FolderNode | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    const hit = findFolder(node.children, id);
    if (hit) return hit;
  }
  return null;
}

const activeFolder = computed<FolderNode | null>(() => {
  if (activeFolderId.value === null) return null;
  const nodes =
    activeScope.value === "general"
      ? library.generalTree
      : library.projectTrees[activeProjectId.value ?? -1] ?? [];
  return findFolder(nodes, activeFolderId.value);
});

const activeProject = computed(() =>
  activeProjectId.value === null
    ? null
    : library.projects.find((p) => p.id === activeProjectId.value) ?? null
);

const locationTitle = computed(() => {
  if (activeFolder.value) return activeFolder.value.name;
  if (activeScope.value === "project" && activeProject.value) return activeProject.value.name;
  return "通用资产库";
});

function askDeleteTag(id: number, name: string): void {
  ask({
    title: "删除标签？",
    description: `确定删除标签「${name}」吗？\n只有未被任何资产使用的空闲标签可以被删除。`,
    confirmText: "删除标签",
    intent: "danger",
    action: () => {
      void deleteTag(id);
    }
  });
}

function selectGeneral(): void {
  viewMode.value = "library";
  activeScope.value = "general";
  activeProjectId.value = null;
  activeFolderId.value = null;
}

function selectProject(id: number): void {
  viewMode.value = "library";
  activeScope.value = "project";
  activeProjectId.value = id;
  activeFolderId.value = null;
}

function selectFolder(node: FolderNode): void {
  viewMode.value = "library";
  activeScope.value = node.scope_type === "project" ? "project" : "general";
  activeProjectId.value = node.project_id;
  activeFolderId.value = node.id;
}

/** 项目删除统一走 useProjectDelete（统计 → 级联影响说明 → 确认）。 */
function askDeleteProject(id: number, name: string): void {
  confirmDeleteProject(id, name, (ok) => {
    if (ok && activeProjectId.value === id) selectGeneral();
  });
}

/** 目录删除统一走 useFolderDelete（统计 → 级联影响说明 → 确认）。 */
function onDeleteFolderNode(node: FolderNode): void {
  askDeleteFolder(node, (ok) => {
    if (ok && activeFolderId.value === node.id) selectGeneral();
  });
}

/** 侧栏铅笔 →「编辑文件夹」弹窗（名称 / 描述 / 锁定开关），保存成功后关闭并刷新树。 */
const folderEditNode = ref<FolderNode | null>(null);

async function onFolderEditSave(payload: FolderEditPayload): Promise<void> {
  const node = folderEditNode.value;
  if (!node) return;
  const ok = await updateFolder(node.id, payload);
  if (ok) folderEditNode.value = null;
}

async function runFilesImport(folderId: number): Promise<void> {
  let paths: string[] = [];
  try {
    paths = await window.ryanDam.selectFiles();
  } catch {
    return;
  }
  if (paths.length === 0) return;
  await importFiles(paths, folderId);
}

async function runFolderImport(folderId: number): Promise<void> {
  let folder: string | null = null;
  try {
    folder = await window.ryanDam.selectFolder();
  } catch {
    return;
  }
  if (!folder) return;
  await importFolder(folder, folderId);
}

function getFolderNameFromPath(dirPath: string): string {
  const normalized = dirPath.replace(/[/\\]+$/, "");
  const parts = normalized.split(/[/\\]/);
  return parts[parts.length - 1] || "新建文件夹";
}

function startImport(): void {
  if (activeFolderId.value !== null) {
    void runFilesImport(activeFolderId.value);
    return;
  }
  targetDialog.value = { kind: "import-files" };
}

async function startFolderImport(): Promise<void> {
  if (activeFolderId.value !== null) {
    await runFolderImport(activeFolderId.value);
    return;
  }
  let folderPath: string | null = null;
  try {
    folderPath = await window.ryanDam.selectFolder();
  } catch {
    return;
  }
  if (!folderPath) return;

  const folderName = getFolderNameFromPath(folderPath);
  const scope = activeScope.value === "project" ? "project" : "general";
  const projectId = scope === "project" ? activeProjectId.value : null;

  const targetFolder = await ensureTopLevelFolder(scope, folderName, projectId);
  if (!targetFolder) return;
  await importFolder(folderPath, targetFolder.id);
}

async function createAndPickFolder(name: string): Promise<void> {
  const scope = activeScope.value === "project" ? "project" : "general";
  const projectId = scope === "project" ? activeProjectId.value : null;

  const folder = await ensureTopLevelFolder(scope, name, projectId);
  if (!folder) return;
  await onTargetDialogPick(folder.id);
}

async function refreshCurrentAssets(append = false, page = 1): Promise<void> {
  const keepScroll = !append ? galleryRef.value?.getScrollTop() ?? 0 : null;
  await fetchAssets(
    { scope: activeScope.value, projectId: activeProjectId.value, folderId: activeFolderId.value },
    { page, append }
  );
  if (keepScroll !== null && galleryRef.value) {
    void nextTick(() => {
      galleryRef.value?.setScrollTop(keepScroll);
    });
  }
}

watch([activeScope, activeProjectId, activeFolderId], () => {
  clearAssets();
  thumbRefreshCount = 0;
  void refreshCurrentAssets();
});

let thumbRefreshTimer: ReturnType<typeof setTimeout> | null = null;
let thumbRefreshCount = 0;

function scheduleThumbnailRefresh(): void {
  const assets = library.assets;
  const generating = assets?.items.some(
    (a) => a.thumbnail_status === "pending" && ["image", "video", "audio"].includes(a.asset_type)
  );
  if (!generating) return;
  if (thumbRefreshCount >= 8 || thumbRefreshTimer) return;
  thumbRefreshTimer = setTimeout(() => {
    thumbRefreshTimer = null;
    thumbRefreshCount += 1;
    void refreshCurrentAssets().then(scheduleThumbnailRefresh);
  }, 2500);
}

watch(() => library.assets, scheduleThumbnailRefresh);

watch(
  () => library.importJob?.status,
  (status, previous) => {
    const terminal = new Set(["completed", "completed_with_errors", "failed", "interrupted"]);
    if (status && previous && terminal.has(status) && !terminal.has(previous)) {
      void loadAll();
      void refreshCurrentAssets();
    }
  }
);

function loadMoreAssets(): void {
  const assets = library.assets;
  if (!assets) return;
  void refreshCurrentAssets(true, assets.page + 1);
}

const showBatchBar = computed(() => viewMode.value === "library" && library.selectedAssetIds.length > 0);

const previewAsset = computed(() => {
  if (previewIndex.value === null || !library.assets) return null;
  return library.assets.items[previewIndex.value] ?? null;
});

const promptRequested = ref(false);
let lastSelectedAssetId: number | null = null;

function handleCardSelect(asset: { id: number }, e?: MouseEvent): void {
  const assetId = asset.id;
  if (e?.shiftKey && lastSelectedAssetId !== null && library.assets) {
    const items = library.assets.items;
    const fromIdx = items.findIndex((a) => a.id === lastSelectedAssetId);
    const toIdx = items.findIndex((a) => a.id === assetId);
    if (fromIdx !== -1 && toIdx !== -1) {
      const start = Math.min(fromIdx, toIdx);
      const end = Math.max(fromIdx, toIdx);
      const rangeSlice = items.slice(start, end + 1);
      for (const item of rangeSlice) {
        if (!library.selectedAssetIds.includes(item.id)) {
          library.selectedAssetIds.push(item.id);
        }
      }
      lastSelectedAssetId = assetId;
      return;
    }
  }

  toggleAssetSelection(assetId);
  lastSelectedAssetId = library.selectedAssetIds.includes(assetId) ? assetId : null;
}

function selectAllCurrentAssets(): void {
  if (!library.assets) return;
  library.selectedAssetIds = library.assets.items.map((a) => a.id);
}

function onCardPrompt(asset: { id: number }): void {
  if (!library.assets) return;
  const index = library.assets.items.findIndex((a) => a.id === asset.id);
  if (index < 0) return;
  savedScrollTop = galleryRef.value?.getScrollTop() ?? 0;
  previewIndex.value = index;
  promptRequested.value = true;
}

function openPreview(assetId: number): void {
  if (!library.assets) return;
  const index = library.assets.items.findIndex((a) => a.id === assetId);
  if (index < 0) return;
  savedScrollTop = galleryRef.value?.getScrollTop() ?? 0;
  previewIndex.value = index;
}

function closePreview(): void {
  previewIndex.value = null;
  void nextTick(() => {
    galleryRef.value?.setScrollTop(savedScrollTop);
  });
}

function stepPreview(delta: number): void {
  const assets = library.assets;
  if (previewIndex.value === null || !assets || assets.items.length === 0) return;
  const count = assets.items.length;
  previewIndex.value = ((previewIndex.value + delta) % count + count) % count;
}

const canImport = computed(
  () => !["queued", "running"].includes(library.importJob?.status ?? "")
);

const targetDialogOptions = computed(() => {
  if (targetDialog.value?.kind === "external-link") {
    return allFolderOptions.value;
  }
  // 导入对话框在通用/项目范围
  const out: { id: number; label: string }[] = [];
  if (activeScope.value === "general") {
    flattenFolderNodes(library.generalTree, "", out as any);
  } else if (activeProjectId.value !== null) {
    flattenFolderNodes(library.projectTrees[activeProjectId.value] ?? [], "", out as any);
  }
  return out;
});

watch(
  () => [
    library.assetQuery.q,
    library.assetQuery.tagId,
    library.assetQuery.assetType,
    library.assetQuery.sizeRange,
    library.assetQuery.modifiedRange,
    library.assetQuery.sort,
    library.assetQuery.order
  ],
  () => {
    clearAssets();
    void refreshCurrentAssets();
  }
);

function onGlobalKeyDown(e: KeyboardEvent): void {
  const target = e.target as HTMLElement | null;
  const isInputActive =
    target &&
    (target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT" ||
      target.isContentEditable);

  if ((e.ctrlKey || e.metaKey) && (e.key === "a" || e.key === "A")) {
    if (!isInputActive && viewMode.value === "library" && library.assets && library.assets.items.length > 0) {
      e.preventDefault();
      selectAllCurrentAssets();
    }
    return;
  }

  if (e.key === "Escape") {
    if (previewIndex.value !== null) {
      closePreview();
      return;
    }
    if (library.selectedAssetIds.length > 0) {
      clearAssetSelection();
    }
  }
}

onMounted(() => {
  window.addEventListener("keydown", onGlobalKeyDown);
  void loadAll().then(() => refreshCurrentAssets());
  void loadTags();
  void loadTrash();
  void loadExternalSources();
});

onUnmounted(() => {
  window.removeEventListener("keydown", onGlobalKeyDown);
});
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-canvas text-ink">
    <!-- 侧边栏子组件（含标签折叠/展开与渐进式展示） -->
    <AppSidebar
      :active-scope="activeScope"
      :active-project-id="activeProjectId"
      :active-folder-id="activeFolderId"
      :view-mode="viewMode"
      @select-general="selectGeneral"
      @select-project="selectProject"
      @select-folder="selectFolder"
      @select-trash="selectTrash"
      @create-folder="(scope, projId, parentId) => (dialog = { kind: 'folder-create', scope, projectId: projId, parentId })"
      @edit-folder="(n) => (folderEditNode = n)"
      @delete-folder="onDeleteFolderNode"
      @create-project="dialog = { kind: 'project-create' }"
      @rename-project="(id, name) => (dialog = { kind: 'project-rename', projectId: id, initial: name })"
      @delete-project="(id, name) => askDeleteProject(id, name)"
      @link-external="startLinkExternal"
      @rescan-external="rescanExternalSource"
      @unlink-external="askUnlinkExternal"
      @create-tag="dialog = { kind: 'tag-create' }"
      @rename-tag="(id, name) => (dialog = { kind: 'tag-rename', tagId: id, initial: name })"
      @delete-tag="(id, name) => askDeleteTag(id, name)"
      @open-settings="showSettingsDialog = true"
    />

    <div class="flex min-w-0 flex-1 flex-col">
      <!-- 顶栏子组件（含搜索防抖、筛选弹层、排序与导入） -->
      <AppHeader
        :view-mode="viewMode"
        :location-title="locationTitle"
        :active-scope="activeScope"
        :active-project-name="activeProject?.name ?? null"
        :active-folder-id="activeFolderId"
        :can-import="canImport"
        @empty-trash="askEmptyTrash"
        @start-import="startImport"
        @start-folder-import="startFolderImport"
      />

      <!-- 回收站视图子组件（行单击打开沉浸式预览） -->
      <TrashView
        v-if="viewMode === 'trash'"
        @preview="openTrashPreview"
        @restore="restoreTrashItem"
        @delete="askPermanentDeleteTrashItem"
        @empty="askEmptyTrash"
      />

      <!-- 主画廊资产网格视图子组件 -->
      <AssetGallery
        v-else
        ref="galleryRef"
        :assets="library.assets"
        :selected-asset-ids="library.selectedAssetIds"
        :loaded="library.loaded"
        @open="openPreview"
        @toggle-select="handleCardSelect"
        @prompt="onCardPrompt"
        @load-more="loadMoreAssets"
      />
    </div>

    <!-- 全局轻量 Toast 提示 -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150"
        enter-from-class="opacity-0 -translate-y-1"
        leave-active-class="transition duration-150"
        leave-to-class="opacity-0 -translate-y-1"
      >
        <div
          v-if="library.notice"
          class="fixed left-1/2 top-4 z-[60] -translate-x-1/2 rounded-xl border px-4 py-2.5 text-sm shadow-soft"
          :class="library.notice.kind === 'error' ? 'border-rose-100 bg-rose-50 text-rose-700' : 'border-emerald-100 bg-emerald-50 text-emerald-700'"
        >
          {{ library.notice.text }}
        </div>
      </Transition>
    </Teleport>

    <!-- 单资产沉浸式预览与详情（支持跨库/跨项目 optgroup 分组移动） -->
    <AssetPreview
      v-if="previewAsset"
      :asset="previewAsset"
      :move-groups="allFolderGroups"
      :auto-open-prompt="promptRequested"
      @close="closePreview"
      @prev="stepPreview(-1)"
      @next="stepPreview(1)"
      @delete="onDeleteFromPreview"
      @rename="onRenameFromPreview"
      @move="onMoveFromPreview"
      @convert="onConvertFromPreview"
      @prompt-opened="promptRequested = false"
    />

    <!-- 回收站沉浸式预览：复用媒体/文本/PDF 播放渲染，提供恢复到原目录 / 永久删除 -->
    <AssetPreview
      v-if="trashPreviewAsset"
      :asset="trashPreviewAsset"
      :auto-open-prompt="false"
      trash-mode
      :trash-meta="trashPreviewItem"
      @close="closeTrashPreview"
      @prev="stepTrashPreview(-1)"
      @next="stepTrashPreview(1)"
      @restore="onRestoreFromTrashPreview"
      @permanent-delete="onPermanentDeleteFromTrashPreview"
    />

    <!-- 多选批量操作浮动工具栏（支持跨项目分组移动与内联打标） -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150"
        enter-from-class="opacity-0 translate-y-2"
        leave-active-class="transition duration-150"
        leave-to-class="opacity-0 translate-y-2"
      >
        <BatchActionBar
          v-if="showBatchBar"
          :total-current-assets="library.assets?.items.length ?? 0"
          @select-all="selectAllCurrentAssets"
          @ask-trash="askBulkTrash"
        />
      </Transition>
    </Teleport>

    <!-- 导入任务进度悬浮窗 -->
    <ImportJobPanel />

    <!-- 目标目录选择对话框 -->
    <TargetFolderDialog
      :request="targetDialog"
      :options="targetDialogOptions"
      @pick="onTargetDialogPick"
      @create-and-pick="createAndPickFolder"
      @close="targetDialog = null"
    />

    <!-- 偏好设置模态框 -->
    <SettingsDialog
      :open="showSettingsDialog"
      @close="showSettingsDialog = false"
      @edit-root="dialog = { kind: 'root-edit' }"
      @open-stage0="showStage0 = true"
    />

    <!-- 通用输入对话框 -->
    <NameDialog
      :open="dialog !== null"
      :title="dialogTitle"
      :initial="dialogInitial"
      @confirm="onDialogConfirm"
      @cancel="dialog = null"
    />

    <!-- 编辑文件夹弹窗（名称 / 描述 / 锁定） -->
    <FolderEditDialog
      :open="folderEditNode !== null"
      :folder="folderEditNode"
      @save="onFolderEditSave"
      @cancel="folderEditNode = null"
    />

    <!-- Apple HIG 全局操作确认模态框 -->
    <ConfirmDialog
      :open="confirmDialog !== null"
      :title="confirmDialog?.title ?? ''"
      :description="confirmDialog?.description"
      :confirm-text="confirmDialog?.confirmText"
      :intent="confirmDialog?.intent"
      @confirm="resolveConfirm"
      @cancel="dismissConfirm"
    />

    <!-- 诊断弹窗 -->
    <Stage0Panel v-if="showStage0" @close="showStage0 = false" />
  </div>
</template>
