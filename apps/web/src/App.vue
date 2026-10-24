<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";

import FolderTree from "./components/FolderTree.vue";
import AssetCard from "./components/AssetCard.vue";
import AssetIcon from "./components/AssetIcon.vue";
import AssetPreview from "./components/AssetPreview.vue";
import ImportJobPanel from "./components/ImportJobPanel.vue";
import NameDialog from "./components/NameDialog.vue";
import Stage0Panel from "./components/Stage0Panel.vue";
import type { FolderNode, TrashItem } from "./api/types";
import {
  bulkAddTags,
  bulkMove,
  bulkRemoveTags,
  bulkTrashSelected,
  clearAssetFilters,
  clearAssetSelection,
  clearAssets,
  createGeneralFolder,
  createProject,
  createProjectFolder,
  createTag,
  deleteAssetToTrash,
  deleteFolder,
  deleteProject,
  deleteTag,
  emptyTrashAll,
  fetchAssets,
  importFiles,
  importFolder,
  library,
  loadAll,
  loadTags,
  loadTrash,
  permanentlyDeleteTrashItem,
  moveAssetToFolder,
  renameFolder,
  renameProject,
  renameAssetById,
  renameTag,
  restoreFromTrash,
  toggleAssetSelection,
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

const dialog = ref<DialogRequest | null>(null);
const showStage0 = ref(false);
const activeScope = ref<"general" | "project">("general");
const activeProjectId = ref<number | null>(null);
const activeFolderId = ref<number | null>(null);
const previewIndex = ref<number | null>(null);
const galleryScroll = ref<HTMLElement | null>(null);
const viewMode = ref<"library" | "trash">("library");
let savedScrollTop = 0;

function selectTrash(): void {
  viewMode.value = "trash";
  void loadTrash();
}

function askEmptyTrash(): void {
  const count = library.trash.length;
  if (count === 0) return;
  if (window.confirm(`确定清空回收站吗？将永久删除 ${count} 项，文件会从磁盘删除，此操作不可恢复。`)) {
    void emptyTrashAll();
  }
}

function askPermanentDeleteTrashItem(item: TrashItem): void {
  if (window.confirm(`确定永久删除「${item.name}」吗？文件将从磁盘删除，此操作不可恢复。`)) {
    void permanentlyDeleteTrashItem(item.id);
  }
}

function onRestoreTrashItem(item: TrashItem): void {
  void restoreFromTrash(item.id);
}

function askBulkTrash(): void {
  const count = library.selectedAssetIds.length;
  if (count === 0) return;
  if (window.confirm(`确定删除选中的 ${count} 项吗？托管资产将移入回收站，可随时恢复；外部资产仅移除索引，不删除源文件。`)) {
    void bulkTrashSelected();
  }
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
  if (window.confirm(`确定删除标签「${name}」吗？只有未被任何资产使用的标签可以删除。`)) {
    void deleteTag(id);
  }
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
  if (window.confirm(`确定删除项目「${name}」吗？仅允许删除没有任何文件夹的空项目。`)) {
    void deleteProject(id).then((ok) => {
      if (ok && activeProjectId.value === id) selectGeneral();
    });
  }
}

function askDeleteFolder(node: FolderNode): void {
  if (window.confirm(`确定删除文件夹「${node.name}」吗？只有空文件夹（无子目录、无资产）可以删除。`)) {
    void deleteFolder(node.id).then((ok) => {
      if (ok && activeFolderId.value === node.id) selectGeneral();
    });
  }
}

async function startImport(): Promise<void> {
  if (activeFolderId.value === null) return;
  let paths: string[] = [];
  try {
    paths = await window.ryanDam.selectFiles();
  } catch {
    return;
  }
  if (paths.length === 0) return;
  await importFiles(paths, activeFolderId.value);
}

async function startFolderImport(): Promise<void> {
  if (activeFolderId.value === null) return;
  let folder: string | null = null;
  try {
    folder = await window.ryanDam.selectFolder();
  } catch {
    return;
  }
  if (!folder) return;
  await importFolder(folder, activeFolderId.value);
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
      ok = await createTag(value);
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
  () => activeFolderId.value !== null && !["queued", "running"].includes(library.importJob?.status ?? "")
);

const searchDraft = ref("");
let searchTimer: ReturnType<typeof setTimeout> | null = null;

watch(searchDraft, (value) => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    library.assetQuery.q = value.trim();
  }, 300);
});

const showFilters = ref(false);
const activeFilterCount = computed(
  () =>
    (library.assetQuery.assetType ? 1 : 0) +
    (library.assetQuery.sizeRange ? 1 : 0) +
    (library.assetQuery.modifiedRange ? 1 : 0) +
    (library.assetQuery.tagId !== null ? 1 : 0)
);

watch(
  () => [library.assetQuery.assetType, library.assetQuery.sizeRange, library.assetQuery.modifiedRange, library.assetQuery.sort, library.assetQuery.order],
  () => {
    clearAssets();
    void refreshCurrentAssets();
  }
);

onMounted(() => {
  void loadAll().then(() => refreshCurrentAssets());
  void loadTags();
  void loadTrash();
});
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-canvas text-ink">
    <aside class="flex w-64 shrink-0 flex-col border-r border-line bg-white">
      <div class="flex items-center gap-2.5 px-4 py-4">
        <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-ink text-xs font-semibold text-white">R.</div>
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold">Ryan_DAM</p>
          <p class="text-[11px] text-muted">本地数字资产库</p>
        </div>
      </div>

      <nav class="flex-1 overflow-y-auto px-2.5 pb-4">
        <section>
          <div class="flex items-center justify-between pl-1.5 pr-1 pb-1 pt-2">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted">通用资产库</p>
            <button
              class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-canvas hover:text-accent"
              title="新建顶层文件夹"
              @click="dialog = { kind: 'folder-create', scope: 'general', projectId: null, parentId: null }"
            >＋</button>
          </div>
          <button
            class="flex w-full items-center gap-1.5 rounded-lg px-1.5 py-1.5 text-left text-sm transition-colors"
            :class="activeScope === 'general' && activeFolderId === null ? 'bg-accent/10 font-medium text-accent' : 'hover:bg-canvas'"
            @click="selectGeneral"
          >全部资产</button>
          <FolderTree
            :nodes="library.generalTree"
            :active-id="activeScope === 'general' ? activeFolderId : null"
            @select="selectFolder"
            @create-child="(n) => (dialog = { kind: 'folder-create', scope: 'general', projectId: null, parentId: n.id })"
            @rename="(n) => (dialog = { kind: 'folder-rename', folderId: n.id, initial: n.name })"
            @remove="askDeleteFolder"
          />
        </section>

        <section class="mt-5">
          <div class="flex items-center justify-between pl-1.5 pr-1 pb-1 pt-2">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted">标签管理</p>
            <button
              class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-canvas hover:text-accent"
              title="新建标签"
              @click="dialog = { kind: 'tag-create' }"
            >＋</button>
          </div>
          <p v-if="library.tags.length === 0" class="px-1.5 py-1 text-xs leading-5 text-muted">
            还没有标签。创建全局标签后可打在任意资产上。
          </p>
          <div v-for="tag in library.tags" :key="tag.id" class="group/tag">
            <div
              class="flex items-center gap-1 rounded-lg px-1.5 py-1.5 text-sm transition-colors"
              :class="library.assetQuery.tagId === tag.id ? 'bg-accent/10 font-medium text-accent' : 'hover:bg-canvas'"
              role="button"
              tabindex="0"
              @click="library.assetQuery.tagId = library.assetQuery.tagId === tag.id ? null : tag.id"
              @keydown.enter="library.assetQuery.tagId = library.assetQuery.tagId === tag.id ? null : tag.id"
            >
              <span class="min-w-0 flex-1 truncate">
                {{ tag.name }}
                <span class="text-[10px] text-muted">{{ tag.asset_count }}</span>
              </span>
              <span class="hidden shrink-0 items-center gap-0.5 group-hover/tag:flex">
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-ink"
                  title="重命名标签"
                  @click.stop="dialog = { kind: 'tag-rename', tagId: tag.id, initial: tag.name }"
                >✎</button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-rose-600"
                  title="删除标签（仅允许删除未被使用的标签）"
                  @click.stop="askDeleteTag(tag.id, tag.name)"
                >×</button>
              </span>
            </div>
          </div>
        </section>

        <section class="mt-5">
          <div class="flex items-center justify-between pl-1.5 pr-1 pb-1 pt-2">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted">项目资产库</p>
            <button
              class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-canvas hover:text-accent"
              title="新建项目"
              @click="dialog = { kind: 'project-create' }"
            >＋</button>
          </div>
          <p v-if="library.projects.length === 0" class="px-1.5 py-1 text-xs leading-5 text-muted">
            还没有项目。点击「＋」创建第一个项目。
          </p>
          <div v-for="project in library.projects" :key="project.id" class="group/proj">
            <div
              class="flex items-center gap-1 rounded-lg px-1.5 py-1.5 text-sm transition-colors"
              :class="activeScope === 'project' && activeProjectId === project.id && activeFolderId === null ? 'bg-accent/10 font-medium text-accent' : 'hover:bg-canvas'"
              role="button"
              tabindex="0"
              @click="selectProject(project.id)"
              @keydown.enter="selectProject(project.id)"
            >
              <span class="min-w-0 flex-1 truncate">{{ project.name }}</span>
              <span class="hidden shrink-0 items-center gap-0.5 group-hover/proj:flex">
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-accent"
                  title="在项目顶层新建文件夹"
                  @click.stop="dialog = { kind: 'folder-create', scope: 'project', projectId: project.id, parentId: null }"
                >＋</button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-ink"
                  title="重命名项目"
                  @click.stop="dialog = { kind: 'project-rename', projectId: project.id, initial: project.name }"
                >✎</button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-rose-600"
                  title="删除空项目"
                  @click.stop="askDeleteProject(project.id, project.name)"
                >×</button>
              </span>
            </div>
            <div class="ml-3 border-l border-line pl-1">
              <FolderTree
                :nodes="library.projectTrees[project.id] ?? []"
                :active-id="activeScope === 'project' && activeProjectId === project.id ? activeFolderId : null"
                @select="selectFolder"
                @create-child="(n) => (dialog = { kind: 'folder-create', scope: 'project', projectId: project.id, parentId: n.id })"
                @rename="(n) => (dialog = { kind: 'folder-rename', folderId: n.id, initial: n.name })"
                @remove="askDeleteFolder"
              />
            </div>
          </div>
        </section>
        <section class="mt-5">
          <div class="flex items-center justify-between pl-1.5 pr-1 pb-1 pt-2">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted">回收站</p>
          </div>
          <button
            class="flex w-full items-center gap-1.5 rounded-lg px-1.5 py-1.5 text-left text-sm transition-colors"
            :class="viewMode === 'trash' ? 'bg-accent/10 font-medium text-accent' : 'hover:bg-canvas'"
            @click="selectTrash"
          >
            <span class="min-w-0 flex-1">回收站</span>
            <span
              v-if="library.trash.length > 0"
              class="shrink-0 rounded-full px-1.5 text-[10px]"
              :class="viewMode === 'trash' ? 'bg-accent/15 text-accent' : 'bg-canvas text-muted'"
            >{{ library.trash.length }}</span>
          </button>
          <p v-if="viewMode === 'trash'" class="px-1.5 pt-1 text-[11px] leading-5 text-muted">
            托管资产删除后在此保留，可恢复；外部资产移除仅删索引，不进回收站。
          </p>
        </section>
      </nav>

      <div class="border-t border-line px-3.5 py-3">
        <div class="flex items-center justify-between">
          <p class="text-[11px] font-semibold uppercase tracking-wider text-muted">设置</p>
          <button
            class="rounded-lg px-2 py-1 text-xs text-accent transition hover:bg-canvas"
            @click="dialog = { kind: 'root-edit' }"
          >编辑</button>
        </div>
        <template v-if="library.settings">
          <p class="mt-1 truncate font-mono text-[11px] text-muted" :title="library.settings.managed_root">
            {{ library.settings.managed_root }}
          </p>
          <p class="mt-0.5 text-[11px]" :class="library.settings.managed_root_state === 'ok' ? 'text-emerald-700' : library.settings.managed_root_state === 'missing' ? 'text-amber-700' : 'text-rose-700'">
            {{ rootStateLabel }} · 仅影响新导入
          </p>
        </template>
        <button class="mt-2 text-xs text-muted transition hover:text-ink" @click="showStage0 = true">阶段 0 诊断…</button>
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
          <input
            v-model="searchDraft"
            type="text"
            placeholder="搜索文件名 / 文件夹…"
            class="w-56 rounded-xl border border-line bg-white px-3.5 py-2 text-sm outline-none transition placeholder:text-muted focus:border-accent"
          />
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
            title="选择文件夹，保留子目录层级导入"
            @click="startFolderImport"
          >导入文件夹</button>
          <button
            class="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="!canImport"
            :title="activeFolderId === null ? '请先在左侧选择一个目录' : '选择文件并导入到当前目录'"
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
            @open="openPreview(asset.id)"
            @toggle-select="toggleAssetSelection(asset.id)"
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
      @close="closePreview"
      @prev="stepPreview(-1)"
      @next="stepPreview(1)"
      @delete="onDeleteFromPreview"
      @rename="onRenameFromPreview"
      @move="onMoveFromPreview"
    />

    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150"
        enter-from-class="opacity-0 translate-y-2"
        leave-active-class="transition duration-150"
        leave-to-class="opacity-0 translate-y-2"
      >
        <div v-if="showBatchBar" class="fixed bottom-5 left-1/2 z-40 -translate-x-1/2">
          <div class="flex items-center gap-1.5 rounded-2xl border border-line bg-white px-4 py-2.5 shadow-soft">
            <span class="mr-1 text-sm font-medium">已选 {{ library.selectedAssetIds.length }} 项</span>
            <div class="relative">
              <button class="rounded-lg px-3 py-1.5 text-sm text-ink transition hover:bg-canvas" @click="batchPanel = batchPanel === 'add-tag' ? 'none' : 'add-tag'">加标签</button>
              <div v-if="batchPanel === 'add-tag'" class="absolute bottom-11 left-0 z-50 w-52 rounded-xl border border-line bg-white p-2 shadow-soft">
                <p v-if="library.tags.length === 0" class="px-2 py-1 text-xs text-muted">暂无标签，请先创建</p>
                <button
                  v-for="tag in library.tags"
                  :key="tag.id"
                  class="block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-sm transition hover:bg-canvas"
                  @click="bulkAddTags(tag.id); batchPanel = 'none'"
                >{{ tag.name }}</button>
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

    <NameDialog
      :open="dialog !== null"
      :title="dialogTitle"
      :initial="dialogInitial"
      :placeholder="dialog?.kind === 'root-edit' ? '例如 D:\\Ryan_DAM\\assets' : dialog?.kind === 'asset-rename' ? '输入新名称（扩展名自动保留）' : '输入名称'"
      :confirm-text="dialog?.kind === 'root-edit' ? '保存' : '确定'"
      @confirm="onDialogConfirm"
      @cancel="dialog = null"
    />

    <Stage0Panel v-if="showStage0" @close="showStage0 = false" />
  </div>
</template>
