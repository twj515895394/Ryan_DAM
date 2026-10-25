import { reactive } from "vue";

import { api, ApiRequestError } from "../api/client";
import type {
  AssetPage,
  ExternalSource,
  FolderEditPayload,
  FolderNode,
  ImportJob,
  Project,
  Settings,
  Tag,
  TrashItem
} from "../api/types";

export type SizeRange = "" | "small" | "medium" | "large";
export type ModifiedRange = "" | "today" | "week" | "month";

export interface AssetQueryState {
  q: string;
  assetType: "" | "image" | "video" | "audio" | "document" | "other";
  sizeRange: SizeRange;
  modifiedRange: ModifiedRange;
  tagId: number | null;
  sort: "created_at" | "name" | "size" | "updated_at";
  order: "asc" | "desc";
}

export interface LibraryState {
  loaded: boolean;
  generalTree: FolderNode[];
  projects: Project[];
  projectTrees: Record<number, FolderNode[]>;
  settings: Settings | null;
  notice: { kind: "error" | "success"; text: string } | null;
  importJob: ImportJob | null;
  assets: AssetPage | null;
  assetQuery: AssetQueryState;
  tags: Tag[];
  selectedAssetIds: number[];
  trash: TrashItem[];
  externalSources: ExternalSource[];
}

export const library = reactive<LibraryState>({
  loaded: false,
  generalTree: [],
  projects: [],
  projectTrees: {},
  settings: null,
  notice: null,
  importJob: null,
  assets: null,
  assetQuery: { q: "", assetType: "", sizeRange: "", modifiedRange: "", tagId: null, sort: "created_at", order: "desc" },
  tags: [],
  selectedAssetIds: [],
  trash: [],
  externalSources: []
});

let noticeTimer: ReturnType<typeof setTimeout> | null = null;

export function notify(kind: "error" | "success", text: string): void {
  library.notice = { kind, text };
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => {
    library.notice = null;
  }, 5000);
}

export function errText(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

export async function loadAll(): Promise<void> {
  try {
    const [generalTree, projects, settings] = await Promise.all([
      api.generalTree(),
      api.listProjects(),
      api.getSettings()
    ]);
    library.generalTree = generalTree;
    library.projects = projects;
    library.settings = settings;
    const trees = await Promise.all(projects.map((p) => api.projectTree(p.id)));
    const projectTrees: Record<number, FolderNode[]> = {};
    projects.forEach((p, index) => {
      projectTrees[p.id] = trees[index];
    });
    library.projectTrees = projectTrees;
    library.loaded = true;
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function createProject(name: string): Promise<boolean> {
  try {
    await api.createProject(name);
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function renameProject(id: number, name: string): Promise<boolean> {
  try {
    await api.renameProject(id, name);
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function deleteProject(id: number, cascade = false): Promise<boolean> {
  try {
    await api.deleteProject(id, cascade);
    await Promise.all([loadAll(), loadTrash(), loadExternalSources()]);
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function createGeneralFolder(name: string, parentId: number | null): Promise<boolean> {
  try {
    await api.createFolder({ name, scope: "general", parent_id: parentId });
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function createProjectFolder(projectId: number, name: string, parentId: number | null): Promise<boolean> {
  try {
    await api.createFolder({ name, scope: "project", project_id: projectId, parent_id: parentId });
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function ensureTopLevelFolder(
  scope: "general" | "project",
  name: string,
  projectId?: number | null
): Promise<FolderNode | null> {
  const tree =
    scope === "general"
      ? library.generalTree
      : projectId
      ? library.projectTrees[projectId] ?? []
      : [];

  const cleanName = name.trim();
  const existing = tree.find((f) => f.name.toLowerCase() === cleanName.toLowerCase());
  if (existing) return existing;

  try {
    const payload =
      scope === "general"
        ? { name: cleanName, scope: "general" as const, parent_id: null }
        : {
            name: cleanName,
            scope: "project" as const,
            project_id: projectId ?? undefined,
            parent_id: null
          };
    await api.createFolder(payload);
    await loadAll();
    const updatedTree =
      scope === "general"
        ? library.generalTree
        : projectId
        ? library.projectTrees[projectId] ?? []
        : [];
    return updatedTree.find((f) => f.name.toLowerCase() === cleanName.toLowerCase()) ?? null;
  } catch (error) {
    notify("error", errText(error));
    return null;
  }
}

export async function updateFolder(id: number, payload: FolderEditPayload): Promise<boolean> {
  try {
    await api.updateFolder(id, payload);
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function deleteFolder(id: number, cascade = false): Promise<boolean> {
  try {
    await api.deleteFolder(id, cascade);
    await Promise.all([loadAll(), loadTrash(), loadExternalSources()]);
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function updateManagedRoot(path: string): Promise<boolean> {
  try {
    library.settings = await api.updateSettings(path);
    notify("success", "默认存储位置已更新（只影响之后的导入）。");
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

const JOB_TERMINAL = new Set(["completed", "completed_with_errors", "failed", "interrupted"]);
let importPollTimer: ReturnType<typeof setInterval> | null = null;

function stopImportPolling(): void {
  if (importPollTimer) {
    clearInterval(importPollTimer);
    importPollTimer = null;
  }
}

export async function importFiles(paths: string[], folderId: number, allowDuplicates = false): Promise<boolean> {
  return startImportJob(() => api.createImport(paths, folderId, allowDuplicates));
}

export async function importFolder(sourceDir: string, folderId: number, allowDuplicates = false): Promise<boolean> {
  return startImportJob(() => api.createFolderImport(sourceDir, folderId, allowDuplicates));
}

async function startImportJob(create: () => Promise<ImportJob>): Promise<boolean> {
  try {
    const job = await create();
    library.importJob = job;
    pollImportJob(job.id);
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export function dismissImportJob(): void {
  stopImportPolling();
  library.importJob = null;
}

export function pollImportJob(jobId: number): void {
  stopImportPolling();
  importPollTimer = setInterval(async () => {
    try {
      const fresh = await api.getImport(jobId);
      library.importJob = fresh;
      if (JOB_TERMINAL.has(fresh.status)) {
        stopImportPolling();
        if (fresh.status === "completed") notify("success", "导入完成。");
        else if (fresh.status === "completed_with_errors") notify("error", "导入完成，但部分文件失败。");
        else if (fresh.status === "failed") notify("error", fresh.message ?? "导入失败。");
      }
    } catch {
      stopImportPolling();
      library.importJob = null;
      notify("error", "无法获取导入任务状态。");
    }
  }, 800);
}

export async function retryFailedImports(): Promise<boolean> {
  const job = library.importJob;
  if (!job) return false;
  try {
    const fresh = await api.retryFailed(job.id);
    library.importJob = fresh;
    notify("success", "正在重试失败项。");
    pollImportJob(fresh.id);
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function forceImportSkipped(): Promise<boolean> {
  const job = library.importJob;
  if (!job) return false;
  const groups = new Map<number, string[]>();
  for (const item of job.items) {
    if (item.status !== "skipped") continue;
    const folderId = item.target_folder_id ?? job.target_folder_id;
    if (folderId === null) continue;
    const paths = groups.get(folderId) ?? [];
    paths.push(item.source_path);
    groups.set(folderId, paths);
  }
  if (groups.size === 0) {
    notify("error", "没有可强制导入的重复项。");
    return false;
  }
  let allOk = true;
  for (const [folderId, paths] of groups) {
    const ok = await importFiles(paths, folderId, true);
    allOk = allOk && ok;
  }
  return allOk;
}

export async function fetchAssets(
  params: { scope: string; projectId?: number | null; folderId?: number | null },
  options: { page?: number; append?: boolean } = {}
): Promise<void> {
  currentAssetScope = params;
  try {
    const page = options.page ?? 1;
    const query = library.assetQuery;
    const request: Record<string, string | number | undefined> = {
      scope: params.scope,
      project_id: params.projectId ?? undefined,
      folder_id: params.folderId ?? undefined,
      page,
      page_size: 50,
      q: query.q || undefined,
      asset_type: query.assetType || undefined,
      tag_id: query.tagId ?? undefined,
      sort: query.sort,
      order: query.order
    };
    if (query.sizeRange === "small") request.size_max = 1024 * 1024;
    else if (query.sizeRange === "medium") {
      request.size_min = 1024 * 1024;
      request.size_max = 50 * 1024 * 1024;
    } else if (query.sizeRange === "large") request.size_min = 50 * 1024 * 1024;
    if (query.modifiedRange) {
      const now = new Date();
      if (query.modifiedRange === "today") now.setHours(0, 0, 0, 0);
      else if (query.modifiedRange === "week") now.setDate(now.getDate() - 7);
      else now.setDate(now.getDate() - 30);
      request.modified_after = now.toISOString();
    }
    const result = await api.listAssets(request as Parameters<typeof api.listAssets>[0]);
    if (options.append && library.assets) {
      library.assets = { ...result, items: [...library.assets.items, ...result.items] };
    } else {
      library.assets = result;
    }
  } catch (error) {
    notify("error", errText(error));
  }
}

export function clearAssetFilters(): void {
  library.assetQuery.assetType = "";
  library.assetQuery.sizeRange = "";
  library.assetQuery.modifiedRange = "";
  library.assetQuery.tagId = null;
}

export async function loadTags(): Promise<void> {
  try {
    library.tags = await api.listTags();
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function createTag(name: string): Promise<Tag | null> {
  try {
    const created = await api.createTag(name);
    await loadTags();
    return created;
  } catch (error) {
    notify("error", errText(error));
    return null;
  }
}

export async function renameTag(id: number, name: string): Promise<boolean> {
  try {
    await api.renameTag(id, name);
    await loadTags();
    await refreshCurrentAssetsQuiet();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function deleteTag(id: number): Promise<boolean> {
  try {
    await api.deleteTag(id);
    if (library.assetQuery.tagId === id) library.assetQuery.tagId = null;
    await loadTags();
    await refreshCurrentAssetsQuiet();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

async function refreshCurrentAssetsQuiet(): Promise<void> {
  if (currentAssetScope) {
    await fetchAssets(currentAssetScope);
  }
}

// 最近一次资产查询的范围参数（供标签变更后静默刷新复用）
let currentAssetScope: { scope: string; projectId?: number | null; folderId?: number | null } | null = null;

export async function updateAssetTags(assetId: number, tagIds: number[]): Promise<boolean> {
  try {
    await api.setAssetTags(assetId, tagIds);
    await loadTags();
    await refreshCurrentAssetsQuiet();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export function toggleAssetSelection(assetId: number): void {
  const index = library.selectedAssetIds.indexOf(assetId);
  if (index >= 0) library.selectedAssetIds.splice(index, 1);
  else library.selectedAssetIds.push(assetId);
}

export function clearAssetSelection(): void {
  library.selectedAssetIds = [];
}

function summarize(result: { ok_count: number; failed_count: number }): string {
  if (result.failed_count === 0) return `操作完成：成功 ${result.ok_count} 项。`;
  return `操作完成：成功 ${result.ok_count} 项，失败 ${result.failed_count} 项。`;
}

export async function bulkAddTags(tagId: number): Promise<void> {
  if (library.selectedAssetIds.length === 0) return;
  try {
    const result = await api.bulkTags({ asset_ids: library.selectedAssetIds, add_tag_ids: [tagId] });
    notify(result.failed_count ? "error" : "success", summarize(result));
    await loadTags();
    await refreshCurrentAssetsQuiet();
    clearAssetSelection();
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function bulkRemoveTags(tagId: number): Promise<void> {
  if (library.selectedAssetIds.length === 0) return;
  try {
    const result = await api.bulkTags({ asset_ids: library.selectedAssetIds, remove_tag_ids: [tagId] });
    notify(result.failed_count ? "error" : "success", summarize(result));
    await loadTags();
    await refreshCurrentAssetsQuiet();
    clearAssetSelection();
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function bulkMove(targetFolderId: number): Promise<void> {
  if (library.selectedAssetIds.length === 0) return;
  try {
    const result = await api.bulkMove({ asset_ids: library.selectedAssetIds, target_folder_id: targetFolderId });
    notify(result.failed_count ? "error" : "success", summarize(result));
    await loadAll();
    await refreshCurrentAssetsQuiet();
    clearAssetSelection();
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function renameAssetById(assetId: number, name: string): Promise<boolean> {
  try {
    await api.renameAsset(assetId, name);
    await refreshCurrentAssetsQuiet();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function moveAssetToFolder(assetId: number, folderId: number): Promise<boolean> {
  try {
    await api.moveAsset(assetId, folderId);
    await refreshCurrentAssetsQuiet();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function loadTrash(): Promise<void> {
  try {
    library.trash = (await api.listTrash()).items;
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function loadExternalSources(): Promise<void> {
  try {
    library.externalSources = await api.listExternalSources();
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function linkExternalSource(
  rootPath: string,
  target: { targetFolderId?: number | null; targetProjectId?: number | null; createMountFolder: boolean }
): Promise<boolean> {
  try {
    const result = await api.createExternalSource(rootPath, target);
    await Promise.all([loadExternalSources(), loadAll(), refreshCurrentAssetsQuiet()]);
    const scan = result.scan;
    const mount = result.source.mount_folder ? `已挂载为「${result.source.target_folder_name}」，` : "";
    notify("success", `外部目录已关联：${mount}新增 ${scan.added} 项。`);
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function rescanExternalSource(sourceId: number): Promise<void> {
  try {
    const scan = await api.scanExternalSource(sourceId);
    await Promise.all([loadExternalSources(), refreshCurrentAssetsQuiet()]);
    const parts: string[] = [];
    if (scan.added) parts.push(`新增 ${scan.added}`);
    if (scan.updated) parts.push(`变更 ${scan.updated}`);
    if (scan.missing) parts.push(`失效 ${scan.missing}`);
    if (scan.reactivated) parts.push(`恢复 ${scan.reactivated}`);
    notify("success", parts.length ? `重新扫描完成：${parts.join("，")}。` : "重新扫描完成：没有变化。");
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function unlinkExternalSource(sourceId: number): Promise<boolean> {
  try {
    const result = await api.unlinkExternalSource(sourceId);
    await Promise.all([loadExternalSources(), loadAll(), refreshCurrentAssetsQuiet()]);
    const pruned = result.mount_folder_removed ? "，挂载的空目录已清理" : "";
    notify("success", `已解除关联，移除 ${result.removed} 个外部资产索引${pruned}；源文件未受影响。`);
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function convertExternalToManaged(assetId: number): Promise<boolean> {
  try {
    await api.convertToManaged(assetId);
    await Promise.all([loadExternalSources(), refreshCurrentAssetsQuiet()]);
    notify("success", "已转为系统托管：文件已复制进托管存储，原记录就地更新，外部源文件保留。");
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

// 删除/恢复会同时影响画廊、回收站计数与外部来源计数，统一刷新
async function refreshAfterTrashChange(): Promise<void> {
  await Promise.all([loadTrash(), loadTags(), loadExternalSources(), refreshCurrentAssetsQuiet()]);
}

export async function deleteAssetToTrash(assetId: number): Promise<boolean> {
  try {
    await api.deleteAsset(assetId);
    // 选区里残留已删除的 id 会让后续批量操作整体 404
    const index = library.selectedAssetIds.indexOf(assetId);
    if (index >= 0) library.selectedAssetIds.splice(index, 1);
    await refreshAfterTrashChange();
    notify("success", "已移入回收站。");
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function bulkTrashSelected(): Promise<void> {
  if (library.selectedAssetIds.length === 0) return;
  try {
    const result = await api.bulkTrash(library.selectedAssetIds);
    notify(result.failed_count ? "error" : "success", summarize(result));
    await refreshAfterTrashChange();
    clearAssetSelection();
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function restoreFromTrash(assetId: number): Promise<boolean> {
  try {
    await api.restoreTrashItem(assetId);
    await refreshAfterTrashChange();
    notify("success", "资产已恢复到原目录。");
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function permanentlyDeleteTrashItem(assetId: number): Promise<boolean> {
  try {
    await api.permanentDeleteTrashItem(assetId);
    await refreshAfterTrashChange();
    notify("success", "已永久删除。");
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function emptyTrashAll(): Promise<boolean> {
  try {
    const result = await api.emptyTrash();
    await loadTrash();
    if (result.failed > 0) {
      notify("error", `已删除 ${result.removed} 项；${result.failed} 项文件被占用，未能删除。`);
    } else {
      notify("success", `已清空回收站（${result.removed} 项）。`);
    }
    return result.failed === 0;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export function clearAssets(): void {
  library.assets = null;
}
