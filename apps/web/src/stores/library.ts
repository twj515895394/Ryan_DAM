import { reactive } from "vue";

import { api, ApiRequestError } from "../api/client";
import type { AssetPage, FolderNode, ImportJob, Project, Settings } from "../api/types";

export type SizeRange = "" | "small" | "medium" | "large";
export type ModifiedRange = "" | "today" | "week" | "month";

export interface AssetQueryState {
  q: string;
  assetType: "" | "image" | "video" | "audio" | "document" | "other";
  sizeRange: SizeRange;
  modifiedRange: ModifiedRange;
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
  assetQuery: { q: "", assetType: "", sizeRange: "", modifiedRange: "", sort: "created_at", order: "desc" }
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

export async function deleteProject(id: number): Promise<boolean> {
  try {
    await api.deleteProject(id);
    await loadAll();
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

export async function renameFolder(id: number, name: string): Promise<boolean> {
  try {
    await api.renameFolder(id, name);
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function deleteFolder(id: number): Promise<boolean> {
  try {
    await api.deleteFolder(id);
    await loadAll();
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
}

export function clearAssets(): void {
  library.assets = null;
}
