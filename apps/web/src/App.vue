<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

import FolderTree from "./components/FolderTree.vue";
import AssetCard from "./components/AssetCard.vue";
import AssetIcon from "./components/AssetIcon.vue";
import AssetPreview from "./components/AssetPreview.vue";
import SidebarIcon from "./components/SidebarIcon.vue";
import ImportJobPanel from "./components/ImportJobPanel.vue";
import NameDialog from "./components/NameDialog.vue";
import ConfirmDialog, { type ConfirmIntent } from "./components/ConfirmDialog.vue";
import Stage0Panel from "./components/Stage0Panel.vue";
import type { ExternalSource, FolderNode, TrashItem } from "./api/types";
import {
  bulkAddTags,
  bulkMove,
  bulkRemoveTags,
  bulkTrashSelected,
  clearAssetFilters,
  clearAssetSelection,
  clearAssets,
  convertExternalToManaged,
  createGeneralFolder,
  createProject,
  createProjectFolder,
  createTag,
  deleteAssetToTrash,
  deleteFolder,
  deleteProject,
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
  permanentlyDeleteTrashItem,
  moveAssetToFolder,
  renameFolder,
  renameProject,
  renameAssetById,
  renameTag,
  restoreFromTrash,
  rescanExternalSource,
  toggleAssetSelection,
  unlinkExternalSource,
  updateManagedRoot
} from "./stores/library";

type DialogRequest =
  | { kind: "project-create" }
  | { kind: "project-rename"; projectId: number; initial: string }
  | { kind: "folder-create"; scope: "general" | "project"; projectId: number | null; parentId: number | null }
  | { kind: "folder-rename"; folderId: number; initial: string }
  | { kind: "tag-create" }
  | { kind: "tag-rename"; tagId: number; initial: string }
  | { kind: "asset-rename"; assetId: number; initial: string }
  | { kind: "root-edit" };

// 需要先选定库内目标目录的操作：外部目录关联、根视图下发起导入
type TargetDialogRequest =
  | { kind: "external-link"; root: string }
  | { kind: "import-files" }
  | { kind: "import-folder" };

const targetDialog = ref<TargetDialogRequest | null>(null);

const dialog = ref<DialogRequest | null>(null);
const showStage0 = ref(false);
const showSettingsDialog = ref(false);
const activeScope = ref<"general" | "project">("general");
const activeProjectId = ref<number | null>(null);
const activeFolderId = ref<number | null>(null);
const previewIndex = ref<number | null>(null);
const galleryScroll = ref<HTMLElement | null>(null);
const viewMode = ref<"library" | "trash">("library");
let savedScrollTop = 0;

interface GlobalConfirmState {
  title: string;
  description: string;
  confirmText: string;
  intent: ConfirmIntent;
  action: () => void;
}

const confirmDialog = ref<GlobalConfirmState | null>(null);

function selectTrash(): void {
  viewMode.value = "trash";
  void loadTrash();
}

function askEmptyTrash(): void {
  const count = library.trash.length;
  if (count === 0) return;
  confirmDialog.value = {
    title: "清空回收站？",
    description: `确定清空回收站吗？将永久删除 ${count} 项。\n文件会从磁盘中直接删除，此操作不可恢复。`,
    confirmText: "清空回收站",
    intent: "danger",
    action: () => {
      void emptyTrashAll();
    }
  };
}

function askPermanentDeleteTrashItem(item: TrashItem): void {
  confirmDialog.value = {
    title: "永久删除该资产？",
    description: `确定永久删除「${item.name}」吗？\n文件将从磁盘中彻底删除，此操作不可恢复。`,
    confirmText: "永久删除",
    intent: "danger",
    action: () => {
      void permanentlyDeleteTrashItem(item.id);
    }
  };
}

function onRestoreTrashItem(item: TrashItem): void {
  void restoreFromTrash(item.id);
}

function askBulkTrash(): void {
  const count = library.selectedAssetIds.length;
  if (count === 0) return;
  confirmDialog.value = {
    title: "删除选中的资产？",
    description: `确定删除选中的 ${count} 项吗？\n托管资产将移入回收站，可随时恢复；外部资产仅移除索引，不会删除源文件。`,
    confirmText: "删除资产",
    intent: "danger",
    action: () => {
      void bulkTrashSelected();
    }
  };
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

const previewMoveOptions = computed<{ id: number; label: string }[]>(() => {
  const asset = previewAsset.value;
  if (!asset) return [];
  const out: { id: number; label: string }[] = [];
  // 移动只能在同一 scope 内，先判断资产所在树
  if (findFolder(library.generalTree, asset.folder_id) !== null) {
    flattenFolders(library.generalTree, "", out);
    return out;
  }
  for (const nodes of Object.values(library.projectTrees)) {
    if (findFolder(nodes, asset.folder_id) !== null) {
      flattenFolders(nodes, "", out);
      return out;
    }
  }
  flattenFolders(library.generalTree, "", out);
  return out;
});

// ── 外部目录关联（票 17）────────────────────────────────────────

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

const allFolderOptions = computed<{ id: number; label: string }[]>(() => {
  const out: { id: number; label: string }[] = [];
  flattenFolders(library.generalTree, "", out);
  for (const project of library.projects) {
    const scoped: { id: number; label: string }[] = [];
    flattenFolders(library.projectTrees[project.id] ?? [], "", scoped);
    scoped.forEach((option) => out.push({ id: option.id, label: `${project.name} / ${option.label}` }));
  }
  return out;
});

async function onTargetDialogPick(folderId: number): Promise<void> {
  const request = targetDialog.value;
  targetDialog.value = null;
  newFolderDraft.value = "";
  if (!request) return;
  if (request.kind === "external-link") {
    await linkExternalSource(request.root, folderId);
    return;
  }
  if (request.kind === "import-files") await runFilesImport(folderId);
  else await runFolderImport(folderId);
}

function askUnlinkExternal(source: ExternalSource): void {
  confirmDialog.value = {
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
  };
}

const ASSET_TYPE_LABELS: Record<string, string> = {
  image: "图片",
  video: "视频",
  audio: "音频",
  document: "文档",
  other: "文件"
};

function trashTypeLabel(type: string): string {
  return ASSET_TYPE_LABELS[type] ?? type;
}

function trashSizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function trashDateLabel(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value + (value.endsWith("Z") ? "" : "Z"));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
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
  const nodes = activeScope.value === "general"
    ? library.generalTree
    : library.projectTrees[activeProjectId.value ?? -1] ?? [];
  return findFolder(nodes, activeFolderId.value);
});

const activeProject = computed(() =>
  activeProjectId.value === null ? null : library.projects.find((p) => p.id === activeProjectId.value) ?? null
);

const locationTitle = computed(() => {
  if (activeFolder.value) return activeFolder.value.name;
  if (activeScope.value === "project" && activeProject.value) return activeProject.value.name;
  return "通用资产库";
});

const dialogTitle = computed(() => {
  const d = dialog.value;
  if (!d) return "";
  switch (d.kind) {
    case "project-create": return "新建项目";
    case "project-rename": return "重命名项目";
    case "folder-create": return d.parentId === null ? "新建顶层文件夹" : "新建子文件夹";
    case "folder-rename": return "重命名文件夹";
    case "tag-create": return "新建标签";
    case "tag-rename": return "重命名标签";
    case "asset-rename": return "重命名资产";
    case "root-edit": return "修改默认托管存储位置";
  }
});

const dialogInitial = computed(() => {
  const d = dialog.value;
  if (d?.kind === "project-rename" || d?.kind === "folder-rename" || d?.kind === "tag-rename" || d?.kind === "asset-rename") return d.initial;
  if (d?.kind === "root-edit") return library.settings?.managed_root ?? "";
  return "";
});

function askDeleteTag(id: number, name: string): void {
  confirmDialog.value = {
    title: "删除标签？",
    description: `确定删除标签「${name}」吗？\n只有未被任何资产使用的空闲标签可以被删除。`,
    confirmText: "删除标签",
    intent: "danger",
    action: () => {
      void deleteTag(id);
    }
  };
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

function askDeleteProject(id: number, name: string): void {
  confirmDialog.value = {
    title: "删除项目？",
    description: `确定删除项目「${name}」吗？\n注意：仅允许删除没有任何文件夹的空项目。`,
    confirmText: "删除项目",
    intent: "danger",
    action: () => {
      void deleteProject(id).then((ok) => {
        if (ok && activeProjectId.value === id) selectGeneral();
      });
    }
  };
}

function askDeleteFolder(node: FolderNode): void {
  confirmDialog.value = {
    title: "删除文件夹？",
    description: `确定删除文件夹「${node.name}」吗？\n注意：只有空文件夹（无子目录、无资产）可以被删除。`,
    confirmText: "删除文件夹",
    intent: "danger",
    action: () => {
      void deleteFolder(node.id).then((ok) => {
        if (ok && activeFolderId.value === node.id) selectGeneral();
      });
    }
  };
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

const newFolderDraft = ref("");

function startImport(): void {
  // 非一级菜单目录：直接选择文件导入到当前选中的目录
  if (activeFolderId.value !== null) {
    void runFilesImport(activeFolderId.value);
    return;
  }
  // 一级菜单目录：弹出目标目录选择或快速新建目录对话框
  newFolderDraft.value = "";
  targetDialog.value = { kind: "import-files" };
}

async function startFolderImport(): Promise<void> {
  // 1. 如果不是一级菜单目录（选中了具体子目录），直接将文件夹导入到该目录
  if (activeFolderId.value !== null) {
    await runFolderImport(activeFolderId.value);
    return;
  }

  // 2. 如果在一级菜单目录（针对项目目录，或通用资产库「全部资产」）：
  // 允许一级菜单选中直接导入文件夹：自动以所选本地文件夹名称在顶层创建（或复用）目录并导入！
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

async function createAndPickFolder(): Promise<void> {
  const name = newFolderDraft.value.trim();
  if (!name) return;
  const scope = activeScope.value === "project" ? "project" : "general";
  const projectId = scope === "project" ? activeProjectId.value : null;

  const folder = await ensureTopLevelFolder(scope, name, projectId);
  if (!folder) return;
  newFolderDraft.value = "";
  await onTargetDialogPick(folder.id);
}

async function refreshCurrentAssets(append = false, page = 1): Promise<void> {
  const scrollEl = galleryScroll.value;
  const keepScroll = !append ? scrollEl?.scrollTop ?? 0 : null;
  await fetchAssets(
    { scope: activeScope.value, projectId: activeProjectId.value, folderId: activeFolderId.value },
    { page, append }
  );
  if (keepScroll !== null && galleryScroll.value) {
    void nextTick(() => {
      if (galleryScroll.value) galleryScroll.value.scrollTop = keepScroll;
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
const batchPanel = ref<"none" | "add-tag" | "remove-tag" | "move">("none");

const batchTagQuery = ref("");
const isBatchTagSubmitting = ref(false);

const trimmedBatchTagQuery = computed(() => batchTagQuery.value.trim());

const matchedExactBatchTag = computed(() => {
  if (!trimmedBatchTagQuery.value) return null;
  const q = trimmedBatchTagQuery.value.toLowerCase();
  return library.tags.find((t) => t.name.toLowerCase() === q) ?? null;
});

const isNewBatchTagCandidate = computed(() => {
  return trimmedBatchTagQuery.value.length > 0 && matchedExactBatchTag.value === null;
});

const filteredBatchTags = computed(() => {
  const q = trimmedBatchTagQuery.value.toLowerCase();
  if (!q) return library.tags;
  return library.tags.filter((t) => t.name.toLowerCase().includes(q));
});

watch(batchPanel, (panel) => {
  if (panel === "add-tag") {
    batchTagQuery.value = "";
  }
});

async function handleBatchAddTagSubmit(): Promise<void> {
  const name = trimmedBatchTagQuery.value;
  if (!name || isBatchTagSubmitting.value) return;

  isBatchTagSubmitting.value = true;
  try {
    let targetTagId: number | null = null;
    if (matchedExactBatchTag.value) {
      targetTagId = matchedExactBatchTag.value.id;
    } else {
      const created = await createTag(name);
      if (!created) return;
      targetTagId = created.id;
    }
    if (targetTagId !== null) {
      await bulkAddTags(targetTagId);
      batchTagQuery.value = "";
      batchPanel.value = "none";
    }
  } finally {
    isBatchTagSubmitting.value = false;
  }
}

async function handleBatchSelectTag(tagId: number): Promise<void> {
  if (isBatchTagSubmitting.value) return;
  isBatchTagSubmitting.value = true;
  try {
    await bulkAddTags(tagId);
    batchTagQuery.value = "";
    batchPanel.value = "none";
  } finally {
    isBatchTagSubmitting.value = false;
  }
}

function flattenFolders(nodes: FolderNode[], prefix: string, out: { id: number; label: string }[]): void {
  for (const node of nodes) {
    const label = prefix ? `${prefix} / ${node.name}` : node.name;
    out.push({ id: node.id, label });
    flattenFolders(node.children, label, out);
  }
}

const moveTargetOptions = computed(() => {
  const out: { id: number; label: string }[] = [];
  if (activeScope.value === "general") flattenFolders(library.generalTree, "", out);
  else if (activeProjectId.value !== null) flattenFolders(library.projectTrees[activeProjectId.value] ?? [], "", out);
  return out;
});

const previewAsset = computed(() => {
  if (previewIndex.value === null || !library.assets) return null;
  return library.assets.items[previewIndex.value] ?? null;
});

const promptRequested = ref(false);

let lastSelectedAssetId: number | null = null;

function handleCardSelect(asset: { id: number }, e?: MouseEvent): void {
  const assetId = asset.id;
  // 支持桌面标准 Shift 范围连续选择
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
  savedScrollTop = galleryScroll.value?.scrollTop ?? 0;
  previewIndex.value = index;
  promptRequested.value = true;
}

function openPreview(assetId: number): void {
  if (!library.assets) return;
  const index = library.assets.items.findIndex((a) => a.id === assetId);
  if (index < 0) return;
  savedScrollTop = galleryScroll.value?.scrollTop ?? 0;
  previewIndex.value = index;
}

function closePreview(): void {
  previewIndex.value = null;
  void nextTick(() => {
    if (galleryScroll.value) galleryScroll.value.scrollTop = savedScrollTop;
  });
}

function stepPreview(delta: number): void {
  const assets = library.assets;
  if (previewIndex.value === null || !assets || assets.items.length === 0) return;
  const count = assets.items.length;
  previewIndex.value = ((previewIndex.value + delta) % count + count) % count;
}

async function onDialogConfirm(value: string): Promise<void> {
  const d = dialog.value;
  if (!d) return;
  let ok = false;
  switch (d.kind) {
    case "project-create":
      ok = await createProject(value);
      break;
    case "project-rename":
      ok = await renameProject(d.projectId, value);
      break;
    case "folder-create":
      ok = d.scope === "general"
        ? await createGeneralFolder(value, d.parentId)
        : await createProjectFolder(d.projectId ?? -1, value, d.parentId);
      break;
    case "folder-rename":
      ok = await renameFolder(d.folderId, value);
      break;
    case "tag-create":
      ok = Boolean(await createTag(value));
      break;
    case "tag-rename":
      ok = await renameTag(d.tagId, value);
      break;
    case "asset-rename":
      ok = await renameAssetById(d.assetId, value);
      if (ok) relocatePreview(d.assetId);
      break;
    case "root-edit":
      ok = await updateManagedRoot(value);
      break;
  }
  if (ok) dialog.value = null;
}

const rootStateLabel = computed(() => {
  switch (library.settings?.managed_root_state) {
    case "ok": return "可用";
    case "missing": return "目录未创建";
    case "unavailable": return "磁盘不可用";
    default: return "未知";
  }
});

const canImport = computed(
  () => !["queued", "running"].includes(library.importJob?.status ?? "")
);

const targetDialogTitle = computed(() => {
  switch (targetDialog.value?.kind) {
    case "external-link": return "选择库内目标目录";
    case "import-files": return "选择导入目标目录";
    case "import-folder": return "选择导入目标目录";
    default: return "";
  }
});

const targetDialogHint = computed(() => {
  const request = targetDialog.value;
  if (!request) return "";
  if (request.kind === "external-link") {
    return `${request.root} 中的文件将索引到所选目录（保留子目录层级）；只读索引，源文件不会被修改或删除。`;
  }
  if (request.kind === "import-files") return "选择的文件将复制进所选目录的托管存储。";
  return "所选文件夹的子目录层级将镜像到目标目录下，文件复制进托管存储。";
});

// 外部目录关联可选任意 scope 的目录；导入只能落在当前 scope 的目录树内
const targetDialogOptions = computed<{ id: number; label: string }[]>(() =>
  targetDialog.value?.kind === "external-link" ? allFolderOptions.value : moveTargetOptions.value
);

const searchDraft = ref("");
let searchTimer: ReturnType<typeof setTimeout> | null = null;

watch(searchDraft, (value) => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    library.assetQuery.q = value.trim();
  }, 300);
});

function commitSearchImmediately(): void {
  if (searchTimer) clearTimeout(searchTimer);
  library.assetQuery.q = searchDraft.value.trim();
}

function clearSearch(): void {
  if (searchTimer) clearTimeout(searchTimer);
  searchDraft.value = "";
  library.assetQuery.q = "";
}

const showFilters = ref(false);
const activeFilterCount = computed(
  () =>
    (library.assetQuery.assetType ? 1 : 0) +
    (library.assetQuery.sizeRange ? 1 : 0) +
    (library.assetQuery.modifiedRange ? 1 : 0) +
    (library.assetQuery.tagId !== null ? 1 : 0)
);

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

  // Ctrl+A / Cmd+A: 全选当前视图资产
  if ((e.ctrlKey || e.metaKey) && (e.key === "a" || e.key === "A")) {
    if (!isInputActive && viewMode.value === "library" && library.assets && library.assets.items.length > 0) {
      e.preventDefault();
      selectAllCurrentAssets();
    }
    return;
  }

  // Escape: 优先关闭预览，其次清空选择
  if (e.key === "Escape") {
    if (previewIndex.value !== null) {
      closePreview();
      return;
    }
    if (library.selectedAssetIds.length > 0) {
      clearAssetSelection();
      batchPanel.value = "none";
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
    <aside class="flex w-60 shrink-0 flex-col border-r border-line/80 bg-[#FAFAFA]">
      <!-- 顶部精简品牌区 -->
      <div class="flex items-center gap-2.5 px-3.5 py-3">
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-ink to-neutral-700 text-xs font-bold text-white shadow-xs">
          R
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <span class="truncate text-[13px] font-semibold text-ink">Ryan_DAM</span>
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" title="本地服务已连接" />
          </div>
          <p class="truncate text-[10.5px] text-muted">本地数字资产库</p>
        </div>
      </div>

      <nav class="flex-1 overflow-y-auto px-2.5 pb-4">
        <!-- 通用资产库 -->
        <section class="space-y-0.5">
          <div class="flex items-center justify-between px-2 pb-1 pt-1.5">
            <span class="text-[11px] font-semibold tracking-wider text-muted/70 uppercase">通用资产库</span>
            <button
              class="flex h-5 w-5 items-center justify-center rounded text-muted transition-colors hover:bg-black/5 hover:text-accent"
              title="新建顶层文件夹"
              @click="dialog = { kind: 'folder-create', scope: 'general', projectId: null, parentId: null }"
            >
              <SidebarIcon name="plus" class="h-3 w-3" />
            </button>
          </div>
          <button
            class="group flex h-7.5 w-full items-center gap-2 rounded-md px-2 text-left text-[13px] transition-colors duration-100"
            :class="activeScope === 'general' && activeFolderId === null && viewMode === 'library'
              ? 'bg-accent/10 font-medium text-accent'
              : 'text-ink/90 hover:bg-black/5'"
            @click="selectGeneral"
          >
            <SidebarIcon
              name="grid"
              class="h-3.5 w-3.5 text-muted group-hover:text-ink/80"
              :class="activeScope === 'general' && activeFolderId === null && viewMode === 'library' ? 'text-accent' : ''"
            />
            <span class="min-w-0 flex-1 truncate">全部资产</span>
            <span v-if="library.assets && activeScope === 'general' && activeFolderId === null && viewMode === 'library'" class="text-[11px] text-muted">
              {{ library.assets.total }}
            </span>
          </button>
          <div class="pt-0.5">
            <FolderTree
              :nodes="library.generalTree"
              :active-id="activeScope === 'general' && viewMode === 'library' ? activeFolderId : null"
              @select="selectFolder"
              @create-child="(n) => (dialog = { kind: 'folder-create', scope: 'general', projectId: null, parentId: n.id })"
              @rename="(n) => (dialog = { kind: 'folder-rename', folderId: n.id, initial: n.name })"
              @remove="askDeleteFolder"
            />
          </div>
        </section>

        <!-- 项目资产库 -->
        <section class="mt-4 space-y-0.5">
          <div class="flex items-center justify-between px-2 pb-1 pt-1">
            <span class="text-[11px] font-semibold tracking-wider text-muted/70 uppercase">项目</span>
            <button
              class="flex h-5 w-5 items-center justify-center rounded text-muted transition-colors hover:bg-black/5 hover:text-accent"
              title="新建项目"
              @click="dialog = { kind: 'project-create' }"
            >
              <SidebarIcon name="plus" class="h-3 w-3" />
            </button>
          </div>
          <div v-if="library.projects.length === 0" class="px-2 py-0.5 text-[11px] text-muted/60">
            暂无项目
          </div>
          <div v-for="project in library.projects" :key="project.id" class="group/proj">
            <div
              class="flex h-7.5 items-center gap-2 rounded-md px-2 text-[13px] transition-colors duration-100"
              :class="activeScope === 'project' && activeProjectId === project.id && activeFolderId === null && viewMode === 'library'
                ? 'bg-accent/10 font-medium text-accent'
                : 'text-ink/90 hover:bg-black/5'"
              role="button"
              tabindex="0"
              @click="selectProject(project.id)"
              @keydown.enter="selectProject(project.id)"
            >
              <SidebarIcon
                name="project"
                class="h-3.5 w-3.5 text-muted group-hover/proj:text-ink/80"
                :class="activeScope === 'project' && activeProjectId === project.id && activeFolderId === null && viewMode === 'library' ? 'text-accent' : ''"
              />
              <span class="min-w-0 flex-1 truncate">{{ project.name }}</span>
              <span class="hidden shrink-0 items-center gap-0.5 group-hover/proj:flex">
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-accent hover:shadow-xs"
                  title="新建子文件夹"
                  @click.stop="dialog = { kind: 'folder-create', scope: 'project', projectId: project.id, parentId: null }"
                >
                  <SidebarIcon name="plus" class="h-3 w-3" />
                </button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-ink hover:shadow-xs"
                  title="重命名项目"
                  @click.stop="dialog = { kind: 'project-rename', projectId: project.id, initial: project.name }"
                >
                  <SidebarIcon name="edit" class="h-3 w-3" />
                </button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-rose-600 hover:shadow-xs"
                  title="删除空项目"
                  @click.stop="askDeleteProject(project.id, project.name)"
                >
                  <SidebarIcon name="close" class="h-3 w-3" />
                </button>
              </span>
            </div>
            <div class="ml-3.5 border-l border-line/70 pl-1.5">
              <FolderTree
                :nodes="library.projectTrees[project.id] ?? []"
                :active-id="activeScope === 'project' && activeProjectId === project.id && viewMode === 'library' ? activeFolderId : null"
                @select="selectFolder"
                @create-child="(n) => (dialog = { kind: 'folder-create', scope: 'project', projectId: project.id, parentId: n.id })"
                @rename="(n) => (dialog = { kind: 'folder-rename', folderId: n.id, initial: n.name })"
                @remove="askDeleteFolder"
              />
            </div>
          </div>
        </section>

        <!-- 外部目录 -->
        <section class="mt-4 space-y-0.5">
          <div class="flex items-center justify-between px-2 pb-1 pt-1">
            <span class="text-[11px] font-semibold tracking-wider text-muted/70 uppercase">外部目录</span>
            <button
              class="flex h-5 w-5 items-center justify-center rounded text-muted transition-colors hover:bg-black/5 hover:text-accent"
              title="关联外部目录（只读索引，不修改源文件）"
              @click="startLinkExternal"
            >
              <SidebarIcon name="plus" class="h-3 w-3" />
            </button>
          </div>
          <div v-if="library.externalSources.length === 0" class="px-2 py-0.5 text-[11px] text-muted/60">
            未关联外部目录
          </div>
          <div v-for="source in library.externalSources" :key="source.id" class="group/src">
            <div class="flex h-7.5 items-center gap-2 rounded-md px-2 text-[13px] transition-colors duration-100 hover:bg-black/5">
              <SidebarIcon name="external" class="h-3.5 w-3.5 text-muted group-hover/src:text-ink/80" />
              <span class="min-w-0 flex-1 truncate" :title="source.root_path">
                {{ source.display_name ?? source.root_path }}
              </span>
              <span class="text-[11px] text-muted">{{ source.asset_count }}</span>
              <span class="hidden shrink-0 items-center gap-0.5 group-hover/src:flex">
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-accent hover:shadow-xs"
                  title="重新扫描（检测新增/变更/失效）"
                  @click.stop="rescanExternalSource(source.id)"
                >
                  <SidebarIcon name="refresh" class="h-3 w-3" />
                </button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-rose-600 hover:shadow-xs"
                  title="解除关联（只移除索引，不删除源文件）"
                  @click.stop="askUnlinkExternal(source)"
                >
                  <SidebarIcon name="close" class="h-3 w-3" />
                </button>
              </span>
            </div>
            <p v-if="source.missing_count > 0" class="px-2 text-[10.5px] leading-4 text-amber-700">
              {{ source.missing_count }} 项源文件失效
            </p>
          </div>
        </section>

        <!-- 标签管理 -->
        <section class="mt-4 space-y-0.5">
          <div class="flex items-center justify-between px-2 pb-1 pt-1">
            <span class="text-[11px] font-semibold tracking-wider text-muted/70 uppercase">标签</span>
            <button
              class="flex h-5 w-5 items-center justify-center rounded text-muted transition-colors hover:bg-black/5 hover:text-accent"
              title="新建标签"
              @click="dialog = { kind: 'tag-create' }"
            >
              <SidebarIcon name="plus" class="h-3 w-3" />
            </button>
          </div>
          <div v-if="library.tags.length === 0" class="px-2 py-0.5 text-[11px] text-muted/60">
            暂无标签
          </div>
          <div v-for="tag in library.tags" :key="tag.id" class="group/tag">
            <div
              class="flex h-7 items-center gap-2 rounded-md px-2 text-[12.5px] transition-colors duration-100"
              :class="library.assetQuery.tagId === tag.id ? 'bg-accent/10 font-medium text-accent' : 'text-ink/90 hover:bg-black/5'"
              role="button"
              tabindex="0"
              @click="library.assetQuery.tagId = library.assetQuery.tagId === tag.id ? null : tag.id"
              @keydown.enter="library.assetQuery.tagId = library.assetQuery.tagId === tag.id ? null : tag.id"
            >
              <SidebarIcon
                name="tag"
                class="h-3 w-3 text-muted group-hover/tag:text-ink/80"
                :class="library.assetQuery.tagId === tag.id ? 'text-accent' : ''"
              />
              <span class="min-w-0 flex-1 truncate">{{ tag.name }}</span>
              <span class="text-[11px] text-muted">{{ tag.asset_count }}</span>
              <span class="hidden shrink-0 items-center gap-0.5 group-hover/tag:flex">
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-ink hover:shadow-xs"
                  title="重命名标签"
                  @click.stop="dialog = { kind: 'tag-rename', tagId: tag.id, initial: tag.name }"
                >
                  <SidebarIcon name="edit" class="h-3 w-3" />
                </button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-rose-600 hover:shadow-xs"
                  title="删除标签"
                  @click.stop="askDeleteTag(tag.id, tag.name)"
                >
                  <SidebarIcon name="close" class="h-3 w-3" />
                </button>
              </span>
            </div>
          </div>
        </section>

        <!-- 回收站：不再作为重复的分类标题，而是独立且清晰的系统项 -->
        <section class="mt-4 border-t border-line/60 pt-2 space-y-0.5">
          <button
            class="group flex h-7.5 w-full items-center gap-2 rounded-md px-2 text-left text-[13px] transition-colors duration-100"
            :class="viewMode === 'trash' ? 'bg-accent/10 font-medium text-accent' : 'text-ink/90 hover:bg-black/5'"
            @click="selectTrash"
          >
            <SidebarIcon
              name="trash"
              class="h-3.5 w-3.5 text-muted group-hover:text-ink/80"
              :class="viewMode === 'trash' ? 'text-accent' : ''"
            />
            <span class="min-w-0 flex-1 truncate">回收站</span>
            <span
              v-if="library.trash.length > 0"
              class="shrink-0 rounded-full px-1.5 py-0.2 text-[10.5px] font-medium"
              :class="viewMode === 'trash' ? 'bg-accent/15 text-accent' : 'bg-black/5 text-muted'"
            >{{ library.trash.length }}</span>
          </button>
        </section>
      </nav>

      <!-- 底部整洁单行设置入口（移走繁杂路径，回归桌面级纯净） -->
      <div class="border-t border-line/60 p-2">
        <button
          class="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[12.5px] text-ink/80 transition-colors duration-100 hover:bg-black/5"
          @click="showSettingsDialog = true"
        >
          <SidebarIcon name="settings" class="h-3.5 w-3.5 text-muted" />
          <span class="flex-1 text-left font-medium">偏好设置与存储</span>
          <span
            class="h-2 w-2 rounded-full"
            :class="library.settings?.managed_root_state === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'"
            :title="`存储状态：${rootStateLabel}`"
          />
        </button>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex h-14 shrink-0 items-center justify-between border-b border-line bg-white/80 px-6">
        <div class="min-w-0">
          <h1 class="truncate text-base font-semibold">{{ viewMode === "trash" ? "回收站" : locationTitle }}</h1>
          <p class="text-[11px] text-muted">
            <template v-if="viewMode === 'trash'">已删除的资产 · {{ library.trash.length }} 项</template>
            <template v-else>
              {{ activeScope === "general" ? "通用资产库" : activeProject?.name ?? "项目资产库" }}
              <template v-if="library.assets">· {{ library.assets.total }} 项</template>
            </template>
          </p>
        </div>
        <div v-if="viewMode === 'trash'" class="flex items-center gap-2">
          <button
            class="rounded-xl border border-rose-200 bg-white px-4 py-2 text-sm font-medium text-rose-600 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="library.trash.length === 0"
            @click="askEmptyTrash"
          >清空回收站</button>
        </div>
        <div v-else class="flex items-center gap-2">
          <div class="relative w-60">
            <SidebarIcon
              name="search"
              class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted/60"
            />
            <input
              v-model="searchDraft"
              type="text"
              placeholder="搜索文件名 / 文件夹…"
              class="w-full rounded-xl border border-line bg-white pl-8 pr-7 py-2 text-sm outline-none transition placeholder:text-muted focus:border-accent"
              @keydown.enter="commitSearchImmediately"
              @keydown.esc="clearSearch"
            />
            <button
              v-if="searchDraft"
              type="button"
              class="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-muted/60 transition hover:text-ink"
              title="清空搜索"
              @click="clearSearch"
            >
              <SidebarIcon name="close" class="h-3 w-3" />
            </button>
          </div>
          <div class="relative">
            <button
              class="rounded-xl border px-3.5 py-2 text-sm font-medium transition"
              :class="activeFilterCount > 0 ? 'border-accent bg-accent/10 text-accent' : 'border-line bg-white hover:bg-canvas'"
              @click="showFilters = !showFilters"
            >筛选{{ activeFilterCount > 0 ? ` · ${activeFilterCount}` : "" }}</button>
            <div
              v-if="showFilters"
              class="absolute right-0 top-11 z-30 w-72 rounded-2xl border border-line bg-white p-4 shadow-soft"
            >
              <label class="block text-xs font-medium text-muted">类型</label>
              <select
                v-model="library.assetQuery.assetType"
                class="mt-1 w-full rounded-lg border border-line bg-white px-2.5 py-2 text-sm outline-none focus:border-accent"
              >
                <option value="">全部类型</option>
                <option value="image">图片</option>
                <option value="video">视频</option>
                <option value="audio">音频</option>
                <option value="document">文档</option>
                <option value="other">其他</option>
              </select>
              <label class="mt-3 block text-xs font-medium text-muted">大小</label>
              <select
                v-model="library.assetQuery.sizeRange"
                class="mt-1 w-full rounded-lg border border-line bg-white px-2.5 py-2 text-sm outline-none focus:border-accent"
              >
                <option value="">不限</option>
                <option value="small">≤ 1 MB</option>
                <option value="medium">1 MB – 50 MB</option>
                <option value="large">≥ 50 MB</option>
              </select>
              <label class="mt-3 block text-xs font-medium text-muted">修改时间</label>
              <select
                v-model="library.assetQuery.modifiedRange"
                class="mt-1 w-full rounded-lg border border-line bg-white px-2.5 py-2 text-sm outline-none focus:border-accent"
              >
                <option value="">不限</option>
                <option value="today">今天</option>
                <option value="week">最近 7 天</option>
                <option value="month">最近 30 天</option>
              </select>
              <label class="mt-3 block text-xs font-medium text-muted">标签</label>
              <select
                v-model="library.assetQuery.tagId"
                class="mt-1 w-full rounded-lg border border-line bg-white px-2.5 py-2 text-sm outline-none focus:border-accent"
              >
                <option :value="null">全部标签</option>
                <option v-for="tag in library.tags" :key="tag.id" :value="tag.id">{{ tag.name }}（{{ tag.asset_count }}）</option>
              </select>
              <div class="mt-4 flex justify-end">
                <button class="rounded-lg px-3 py-1.5 text-xs text-accent transition hover:bg-canvas" @click="clearAssetFilters">清除筛选</button>
              </div>
            </div>
          </div>
          <select
            v-model="library.assetQuery.sort"
            class="rounded-xl border border-line bg-white px-3 py-2 text-sm outline-none focus:border-accent"
            title="排序方式"
          >
            <option value="created_at">最新导入</option>
            <option value="name">按名称</option>
            <option value="size">按大小</option>
            <option value="updated_at">最近修改</option>
          </select>
          <button
            class="rounded-xl border border-line bg-white px-3 py-2 text-sm font-medium transition hover:bg-canvas"
            :title="library.assetQuery.order === 'desc' ? '当前：降序' : '当前：升序'"
            @click="library.assetQuery.order = library.assetQuery.order === 'desc' ? 'asc' : 'desc'"
          >{{ library.assetQuery.order === "desc" ? "↓" : "↑" }}</button>
          <button
            class="rounded-xl border border-line bg-white px-4 py-2 text-sm font-medium transition hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="!canImport"
            :title="activeFolderId === null ? (activeScope === 'project' ? '选择本地文件夹，直接作为当前项目目录导入' : '选择本地文件夹，作为顶层目录导入') : '选择本地文件夹，导入到当前目录'"
            @click="startFolderImport"
          >导入文件夹</button>
          <button
            class="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="!canImport"
            :title="activeFolderId === null ? '选择文件导入（可指定或新建目录）' : '选择文件并导入到当前目录'"
            @click="startImport"
          >导入文件</button>
        </div>
      </header>

      <main v-if="viewMode === 'trash'" class="min-h-0 flex-1 overflow-y-auto px-8 pb-10 pt-6">
        <div
          v-if="library.trash.length > 0"
          class="overflow-hidden rounded-2xl border border-line bg-white"
        >
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-line bg-canvas/60 text-left text-xs text-muted">
                <th class="px-4 py-2.5 font-medium">名称</th>
                <th class="px-4 py-2.5 font-medium">类型</th>
                <th class="px-4 py-2.5 font-medium">大小</th>
                <th class="px-4 py-2.5 font-medium">删除时间</th>
                <th class="px-4 py-2.5 font-medium">原目录</th>
                <th class="px-4 py-2.5 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in library.trash" :key="item.id" class="border-b border-line last:border-b-0">
                <td class="max-w-[280px] px-4 py-2.5">
                  <div class="flex items-center gap-2">
                    <AssetIcon :type="item.asset_type" class="h-4 w-4 shrink-0 text-muted" />
                    <span class="truncate" :title="item.name">{{ item.name }}</span>
                    <span
                      v-if="item.source_type === 'external'"
                      class="shrink-0 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700"
                    >外部</span>
                  </div>
                </td>
                <td class="px-4 py-2.5 text-muted">{{ trashTypeLabel(item.asset_type) }}</td>
                <td class="px-4 py-2.5 text-muted">{{ trashSizeLabel(item.size_bytes) }}</td>
                <td class="px-4 py-2.5 text-muted">{{ trashDateLabel(item.deleted_at) }}</td>
                <td class="max-w-[180px] truncate px-4 py-2.5 text-muted" :title="item.original_folder">{{ item.original_folder }}</td>
                <td class="whitespace-nowrap px-4 py-2.5 text-right">
                  <button
                    class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-accent transition hover:bg-accent/10"
                    @click="onRestoreTrashItem(item)"
                  >恢复</button>
                  <button
                    class="ml-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-rose-600 transition hover:bg-rose-50"
                    @click="askPermanentDeleteTrashItem(item)"
                  >永久删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-else class="flex min-h-full items-center justify-center">
          <div class="w-full max-w-md rounded-3xl border border-line bg-white p-10 text-center shadow-sm">
            <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-canvas text-muted/70">
              <AssetIcon type="other" class="h-7 w-7" />
            </div>
            <h2 class="mt-5 text-base font-semibold">回收站是空的</h2>
            <p class="mt-2 text-sm leading-6 text-muted">
              删除的托管资产会保留在这里，可随时恢复到原目录；「永久删除」和「清空回收站」才会真正从磁盘移除文件。
            </p>
          </div>
        </div>
      </main>

      <main v-else ref="galleryScroll" class="min-h-0 flex-1 overflow-y-auto px-8 pb-10 pt-6">
        <div
          v-if="library.assets && library.assets.items.length > 0"
          class="grid gap-4"
          style="grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))"
        >
          <AssetCard
            v-for="asset in library.assets.items"
            :key="asset.id"
            :asset="asset"
            :selected="library.selectedAssetIds.includes(asset.id)"
            :selection-active="library.selectedAssetIds.length > 0"
            @open="openPreview(asset.id)"
            @toggle-select="handleCardSelect"
            @prompt="onCardPrompt"
          />
        </div>

        <div v-if="library.assets && library.assets.items.length < library.assets.total" class="mt-6 flex justify-center">
          <button
            class="rounded-xl border border-line bg-white px-5 py-2.5 text-sm font-medium transition hover:bg-canvas"
            @click="loadMoreAssets"
          >加载更多（已显示 {{ library.assets.items.length }} / {{ library.assets.total }}）</button>
        </div>

        <div v-if="!library.assets || library.assets.items.length === 0" class="flex min-h-full items-center justify-center">
          <div class="w-full max-w-md rounded-3xl border border-line bg-white p-10 text-center shadow-sm">
            <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-canvas text-muted/70">
            <AssetIcon type="other" class="h-7 w-7" />
          </div>
            <h2 class="mt-5 text-base font-semibold">
              {{ !library.loaded ? "正在连接本地服务…" : library.assets === null ? "加载失败" : "此目录还没有资产" }}
            </h2>
            <p class="mt-2 text-sm leading-6 text-muted">
              {{ library.loaded
                ? "选中左侧目录后，通过顶部「导入文件」将文件复制进托管存储；缩略图与预览将在后续阶段接入。"
                : "如果长时间未连接，请打开左下角的「阶段 0 诊断」检查本地服务。" }}
            </p>
          </div>
        </div>
      </main>
    </div>

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

    <AssetPreview
      v-if="previewAsset"
      :asset="previewAsset"
      :move-options="previewMoveOptions"
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

    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150"
        enter-from-class="opacity-0 translate-y-2"
        leave-active-class="transition duration-150"
        leave-to-class="opacity-0 translate-y-2"
      >
        <div v-if="showBatchBar" class="fixed bottom-5 left-1/2 z-40 -translate-x-1/2">
          <div class="flex items-center gap-2 rounded-2xl border border-line bg-white px-4 py-2.5 shadow-soft">
            <div class="flex items-center gap-1.5 mr-1">
              <span class="text-sm font-medium">已选 {{ library.selectedAssetIds.length }} 项</span>
              <button
                v-if="library.assets && library.selectedAssetIds.length < library.assets.items.length"
                type="button"
                class="rounded-md px-1.5 py-0.5 text-xs font-medium text-accent transition hover:bg-accent/10"
                title="全选当前列表所有资产 (Ctrl+A)"
                @click="selectAllCurrentAssets"
              >全选</button>
              <button
                v-else
                type="button"
                class="rounded-md px-1.5 py-0.5 text-xs font-medium text-muted transition hover:bg-canvas"
                title="清空当前所有选中 (Esc)"
                @click="clearAssetSelection"
              >全不选</button>
            </div>
            <div class="relative">
              <button
                class="rounded-lg px-3 py-1.5 text-sm transition"
                :class="batchPanel === 'add-tag' ? 'bg-accent/10 font-medium text-accent' : 'text-ink hover:bg-canvas'"
                @click="batchPanel = batchPanel === 'add-tag' ? 'none' : 'add-tag'"
              >加标签</button>

              <div
                v-if="batchPanel === 'add-tag'"
                class="absolute bottom-11 left-0 z-50 w-64 rounded-xl border border-line bg-white p-2 shadow-soft"
              >
                <!-- 搜索与输入框 -->
                <div class="relative">
                  <input
                    v-model="batchTagQuery"
                    type="text"
                    placeholder="搜索标签，或输入新标签…"
                    class="w-full rounded-lg border border-line bg-white px-2.5 py-1.5 pr-7 text-xs text-ink outline-none transition placeholder:text-muted/60 focus:border-accent focus:ring-1 focus:ring-accent/20"
                    @keydown.enter.prevent="handleBatchAddTagSubmit"
                    @keydown.esc="batchPanel = 'none'"
                  />
                  <button
                    v-if="batchTagQuery"
                    type="button"
                    class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 text-muted/60 hover:text-ink"
                    title="清空"
                    @click="batchTagQuery = ''"
                  >
                    <SidebarIcon name="close" class="h-3 w-3" />
                  </button>
                </div>

                <!-- 新建并批量打标快捷入口 -->
                <div
                  v-if="isNewBatchTagCandidate"
                  class="mt-1.5 rounded-lg border border-emerald-200 bg-emerald-50/70 p-1"
                >
                  <button
                    type="button"
                    class="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs font-medium text-emerald-800 transition hover:bg-emerald-100/70"
                    :disabled="isBatchTagSubmitting"
                    @click="handleBatchAddTagSubmit"
                  >
                    <span class="flex items-center gap-1.5 truncate">
                      <SidebarIcon name="plus" class="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                      <span class="truncate">新建并打标 “<span class="font-bold">{{ trimmedBatchTagQuery }}</span>”</span>
                    </span>
                    <span class="shrink-0 rounded bg-emerald-200/80 px-1 py-0.5 text-[10px] text-emerald-800">
                      {{ isBatchTagSubmitting ? "打标中…" : "回车" }}
                    </span>
                  </button>
                </div>

                <!-- 匹配已有标签列表 -->
                <div v-if="filteredBatchTags.length > 0" class="mt-1.5 max-h-48 overflow-y-auto">
                  <div class="px-2 py-1 text-[10px] font-semibold tracking-wider text-muted/70 uppercase">
                    {{ trimmedBatchTagQuery ? "匹配已有标签" : "选择已有标签" }}
                  </div>
                  <button
                    v-for="tag in filteredBatchTags"
                    :key="tag.id"
                    type="button"
                    class="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs text-ink transition hover:bg-canvas hover:text-accent"
                    :disabled="isBatchTagSubmitting"
                    @click="handleBatchSelectTag(tag.id)"
                  >
                    <span class="flex items-center gap-1.5 truncate">
                      <SidebarIcon name="tag" class="h-3 w-3 shrink-0 text-muted" />
                      <span class="truncate">{{ tag.name }}</span>
                    </span>
                    <span class="shrink-0 text-[10px] text-muted/60">点击打标</span>
                  </button>
                </div>

                <!-- 空状态提示 -->
                <div
                  v-else-if="!isNewBatchTagCandidate"
                  class="px-3 py-3 text-center text-xs text-muted"
                >
                  {{ trimmedBatchTagQuery ? "无匹配标签，回车可新建" : "暂无标签，输入名称即可新建" }}
                </div>
              </div>
            </div>
            <div class="relative">
              <button class="rounded-lg px-3 py-1.5 text-sm text-ink transition hover:bg-canvas" @click="batchPanel = batchPanel === 'remove-tag' ? 'none' : 'remove-tag'">移除标签</button>
              <div v-if="batchPanel === 'remove-tag'" class="absolute bottom-11 left-0 z-50 w-52 rounded-xl border border-line bg-white p-2 shadow-soft">
                <p v-if="library.tags.length === 0" class="px-2 py-1 text-xs text-muted">暂无标签</p>
                <button
                  v-for="tag in library.tags"
                  :key="tag.id"
                  class="block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-sm transition hover:bg-canvas"
                  @click="bulkRemoveTags(tag.id); batchPanel = 'none'"
                >{{ tag.name }}</button>
              </div>
            </div>
            <div class="relative">
              <button class="rounded-lg px-3 py-1.5 text-sm text-ink transition hover:bg-canvas" @click="batchPanel = batchPanel === 'move' ? 'none' : 'move'">移动到…</button>
              <div v-if="batchPanel === 'move'" class="absolute bottom-11 left-0 z-50 max-h-64 w-64 overflow-y-auto rounded-xl border border-line bg-white p-2 shadow-soft">
                <p v-if="moveTargetOptions.length === 0" class="px-2 py-1 text-xs text-muted">当前范围没有可选目录</p>
                <button
                  v-for="option in moveTargetOptions"
                  :key="option.id"
                  class="block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-sm transition hover:bg-canvas"
                  :title="option.label"
                  @click="bulkMove(option.id); batchPanel = 'none'"
                >{{ option.label }}</button>
              </div>
            </div>
            <button
              class="rounded-lg px-3 py-1.5 text-sm text-rose-600 transition hover:bg-rose-50"
              @click="askBulkTrash"
            >删除</button>
            <button class="rounded-lg px-3 py-1.5 text-sm text-muted transition hover:bg-canvas" @click="clearAssetSelection(); batchPanel = 'none'">取消</button>
          </div>
        </div>
      </Transition>
    </Teleport>

    <ImportJobPanel />

    <Teleport to="body">
      <div
        v-if="targetDialog !== null"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="targetDialog = null"
      >
        <div class="w-[460px] rounded-2xl border border-line bg-white p-5 shadow-soft">
          <h3 class="text-sm font-semibold">{{ targetDialogTitle }}</h3>
          <p class="mt-1.5 break-all text-xs leading-5 text-muted">
            {{ targetDialogHint }}
          </p>

          <div class="mt-3.5 space-y-3">
            <!-- 已有目录选择列表 -->
            <div
              v-if="targetDialogOptions.length > 0"
              class="max-h-52 overflow-y-auto rounded-xl border border-line p-1.5"
            >
              <button
                v-for="option in targetDialogOptions"
                :key="option.id"
                class="block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-sm transition hover:bg-canvas"
                :title="option.label"
                @click="onTargetDialogPick(option.id)"
              >{{ option.label }}</button>
            </div>

            <!-- 内联快捷新建目录导入区（消除无目录死胡同） -->
            <div class="rounded-xl border border-line/80 bg-canvas/40 p-3">
              <label class="block text-xs font-medium text-ink/80 mb-2">
                {{ targetDialogOptions.length === 0 ? `当前${activeScope === 'project' ? '项目' : '资产库'}还没有目录，直接新建一个：` : "或者新建一个目录并导入：" }}
              </label>
              <div class="flex gap-2">
                <input
                  v-model="newFolderDraft"
                  type="text"
                  placeholder="输入新目录名称，例如：默认素材"
                  class="min-w-0 flex-1 rounded-lg border border-line bg-white px-3 py-1.5 text-xs text-ink outline-none transition focus:border-accent focus:ring-1 focus:ring-accent/20"
                  @keydown.enter.prevent="createAndPickFolder"
                />
                <button
                  type="button"
                  class="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:opacity-40"
                  :disabled="!newFolderDraft.trim()"
                  @click="createAndPickFolder"
                >创建并导入</button>
              </div>
            </div>
          </div>

          <div class="mt-4 flex justify-end">
            <button
              class="rounded-lg px-3 py-1.5 text-sm text-muted transition hover:bg-canvas"
              @click="targetDialog = null; newFolderDraft = ''"
            >取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showSettingsDialog"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/35 backdrop-blur-xs"
        @click.self="showSettingsDialog = false"
      >
        <div class="w-[460px] rounded-2xl border border-line bg-white p-6 shadow-soft">
          <div class="flex items-center justify-between pb-3 border-b border-line/70">
            <div class="flex items-center gap-2">
              <SidebarIcon name="settings" class="h-4 w-4 text-muted" />
              <h3 class="text-sm font-semibold text-ink">偏好设置与存储</h3>
            </div>
            <button
              class="flex h-6 w-6 items-center justify-center rounded-md text-muted hover:bg-canvas hover:text-ink transition-colors"
              @click="showSettingsDialog = false"
            >
              <SidebarIcon name="close" class="h-3.5 w-3.5" />
            </button>
          </div>

          <div class="mt-4 space-y-4">
            <!-- 存储位置 -->
            <div class="rounded-xl border border-line/80 bg-canvas/40 p-3.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-ink/80">默认托管存储目录</span>
                <span
                  class="rounded-full px-2 py-0.5 text-[10.5px] font-medium"
                  :class="library.settings?.managed_root_state === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'"
                >
                  {{ rootStateLabel }}
                </span>
              </div>
              <p
                class="mt-2 truncate rounded-lg bg-white px-2.5 py-1.5 font-mono text-xs text-muted border border-line/60"
                :title="library.settings?.managed_root"
              >
                {{ library.settings?.managed_root ?? "未设置" }}
              </p>
              <div class="mt-2.5 flex items-center justify-between text-[11px] text-muted">
                <span>修改后仅影响后续新导入的文件</span>
                <button
                  class="rounded-md border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink transition hover:bg-canvas"
                  @click="dialog = { kind: 'root-edit' }"
                >
                  修改位置…
                </button>
              </div>
            </div>

            <!-- 系统诊断与关于 -->
            <div class="rounded-xl border border-line/80 bg-canvas/40 p-3.5">
              <div class="flex items-center justify-between">
                <div>
                  <h4 class="text-xs font-semibold text-ink/80">系统诊断与环境检查</h4>
                  <p class="mt-0.5 text-[11px] text-muted">检查本地 API 服务、SQLite 数据库与 FFmpeg 环境</p>
                </div>
                <button
                  class="rounded-md border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink transition hover:bg-canvas"
                  @click="showStage0 = true; showSettingsDialog = false"
                >
                  打开诊断…
                </button>
              </div>
            </div>
          </div>

          <div class="mt-5 flex justify-end">
            <button
              class="rounded-xl bg-ink px-4 py-1.5 text-xs font-medium text-white transition hover:bg-neutral-800"
              @click="showSettingsDialog = false"
            >
              完成
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <NameDialog
      :open="dialog !== null"
      :title="dialogTitle"
      :initial="dialogInitial"
      :placeholder="dialog?.kind === 'root-edit' ? '例如 D:\\Ryan_DAM\\assets' : dialog?.kind === 'asset-rename' ? '输入新名称（扩展名自动保留）' : '输入名称'"
      :confirm-text="dialog?.kind === 'root-edit' ? '保存' : '确定'"
      @confirm="onDialogConfirm"
      @cancel="dialog = null"
    />

    <ConfirmDialog
      :open="confirmDialog !== null"
      :title="confirmDialog?.title ?? ''"
      :description="confirmDialog?.description"
      :confirm-text="confirmDialog?.confirmText"
      :intent="confirmDialog?.intent ?? 'default'"
      @confirm="() => { const action = confirmDialog?.action; confirmDialog = null; action?.(); }"
      @cancel="confirmDialog = null"
    />

    <Stage0Panel v-if="showStage0" @close="showStage0 = false" />
  </div>
</template>
