import type {
  ApiErrorBody,
  AssetOut,
  AssetPage,
  BulkResult,
  ExternalSource,
  FolderCreatePayload,
  FolderNode,
  FolderOut,
  FolderStats,
  ImportJob,
  Project,
  ScanResult,
  Settings,
  Tag,
  TrashList
} from "./types";

interface BackendInfo {
  baseUrl: string;
  token: string;
  version: string;
}

let infoPromise: Promise<BackendInfo> | null = null;

function hasNativeBridge(): boolean {
  return typeof window !== "undefined" && typeof window.ryanDam?.getBackendInfo === "function";
}

async function getBackendInfo(): Promise<BackendInfo> {
  if (hasNativeBridge()) {
    if (!infoPromise) {
      infoPromise = window.ryanDam.getBackendInfo().catch((error) => {
        infoPromise = null; // allow retry after a failed bridge call
        throw error;
      });
    }
    return infoPromise;
  }
  // Dev-only affordance: develop/test the UI in a plain browser against a
  // locally started backend. Packaged builds always have the native bridge.
  if (import.meta.env.DEV) {
    const raw = localStorage.getItem("ryan-dam-dev-backend");
    if (raw) {
      const parsed = JSON.parse(raw) as BackendInfo | null;
      if (parsed?.baseUrl && parsed?.token) return parsed;
    }
    throw new Error(
      "开发模式浏览器预览：请先设置 localStorage['ryan-dam-dev-backend'] = JSON.stringify({ baseUrl, token, version })，或改用桌面客户端。"
    );
  }
  throw new Error("请在 Ryan_DAM 桌面客户端中使用（缺少本地服务桥接）。");
}

export class ApiRequestError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const info = await getBackendInfo();
  const headers: Record<string, string> = {
    "X-Ryan-DAM-Token": info.token,
    ...(init.headers as Record<string, string> | undefined)
  };
  let body = init.body;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const response = await fetch(`${info.baseUrl}${path}`, { ...init, headers, body });
  if (!response.ok) {
    let code = "unknown_error";
    let message = `本地服务返回 HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as ApiErrorBody;
      if (payload?.error?.code) code = payload.error.code;
      if (payload?.error?.message) message = payload.error.message;
    } catch {
      // keep the HTTP status fallback
    }
    throw new ApiRequestError(code, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listProjects: () => request<Project[]>("/api/v1/projects"),
  createProject: (name: string) => request<Project>("/api/v1/projects", { method: "POST", json: { name } }),
  renameProject: (id: number, name: string) =>
    request<Project>(`/api/v1/projects/${id}`, { method: "PATCH", json: { name } }),
  deleteProject: (id: number) => request<void>(`/api/v1/projects/${id}`, { method: "DELETE" }),

  generalTree: () => request<FolderNode[]>("/api/v1/folders/tree?scope=general"),
  projectTree: (projectId: number) =>
    request<FolderNode[]>(`/api/v1/folders/tree?scope=project&project_id=${projectId}`),
  createFolder: (payload: FolderCreatePayload) =>
    request<FolderOut>("/api/v1/folders", { method: "POST", json: payload }),
  renameFolder: (id: number, name: string) =>
    request<FolderOut>(`/api/v1/folders/${id}`, { method: "PATCH", json: { name } }),
  getFolderStats: (id: number) => request<FolderStats>(`/api/v1/folders/${id}/stats`),
  deleteFolder: (id: number, cascade = false) =>
    request<void>(`/api/v1/folders/${id}${cascade ? "?cascade=true" : ""}`, { method: "DELETE" }),

  createImport: (paths: string[], folderId: number, allowDuplicates = false) =>
    request<ImportJob>("/api/v1/imports", {
      method: "POST",
      json: { paths, folder_id: folderId, allow_duplicates: allowDuplicates }
    }),
  createFolderImport: (sourceDir: string, folderId: number, allowDuplicates = false) =>
    request<ImportJob>("/api/v1/imports/folder", {
      method: "POST",
      json: { source_dir: sourceDir, folder_id: folderId, allow_duplicates: allowDuplicates }
    }),
  getImport: (id: number) => request<ImportJob>(`/api/v1/imports/${id}`),
  retryFailed: (id: number) => request<ImportJob>(`/api/v1/imports/${id}/retry-failed`, { method: "POST" }),

  listAssets: (params: {
    scope?: string;
    project_id?: number;
    folder_id?: number;
    q?: string;
    asset_type?: string;
    size_min?: number;
    size_max?: number;
    modified_after?: string;
    modified_before?: string;
    sort?: string;
    order?: string;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") query.set(key, String(value));
    }
    return request<AssetPage>(`/api/v1/assets?${query.toString()}`);
  },

  fetchThumbnailObjectUrl: async (assetId: number): Promise<string> => {
    const info = await getBackendInfo();
    const response = await fetch(`${info.baseUrl}/api/v1/assets/${assetId}/thumbnail`, {
      headers: { "X-Ryan-DAM-Token": info.token }
    });
    if (!response.ok) throw new Error(`thumbnail HTTP ${response.status}`);
    return URL.createObjectURL(await response.blob());
  },

  fetchContentObjectUrl: async (assetId: number): Promise<string> => {
    const info = await getBackendInfo();
    const response = await fetch(`${info.baseUrl}/api/v1/assets/${assetId}/content`, {
      headers: { "X-Ryan-DAM-Token": info.token }
    });
    if (!response.ok) throw new Error(`content HTTP ${response.status}`);
    return URL.createObjectURL(await response.blob());
  },

  fetchContentText: async (assetId: number): Promise<string> => {
    const info = await getBackendInfo();
    const response = await fetch(`${info.baseUrl}/api/v1/assets/${assetId}/content`, {
      headers: { "X-Ryan-DAM-Token": info.token }
    });
    if (!response.ok) throw new Error(`content HTTP ${response.status}`);
    return response.text();
  },

  openExternal: (assetId: number) => request<void>(`/api/v1/assets/${assetId}/open`, { method: "POST" }),

  renameAsset: (id: number, name: string) =>
    request<AssetOut>(`/api/v1/assets/${id}`, { method: "PATCH", json: { name } }),
  moveAsset: (id: number, folderId: number) =>
    request<AssetOut>(`/api/v1/assets/${id}/move`, { method: "POST", json: { folder_id: folderId } }),

  listExternalSources: () => request<ExternalSource[]>("/api/v1/external-sources"),
  createExternalSource: (rootPath: string, targetFolderId: number) =>
    request<{ source: ExternalSource; scan: ScanResult }>("/api/v1/external-sources", {
      method: "POST",
      json: { root_path: rootPath, target_folder_id: targetFolderId }
    }),
  scanExternalSource: (id: number) =>
    request<ScanResult>(`/api/v1/external-sources/${id}/scan`, { method: "POST" }),
  unlinkExternalSource: (id: number) =>
    request<{ removed: number }>(`/api/v1/external-sources/${id}`, { method: "DELETE" }),
  convertToManaged: (id: number) =>
    request<AssetOut>(`/api/v1/assets/${id}/convert-to-managed`, { method: "POST" }),
  getAssetPrompt: (id: number) =>
    request<{ asset_id: number; prompt_text: string | null; has_prompt: boolean }>(
      `/api/v1/assets/${id}/prompt`
    ),
  setAssetPrompt: (id: number, promptText: string | null) =>
    request<{ asset_id: number; prompt_text: string | null; has_prompt: boolean }>(
      `/api/v1/assets/${id}/prompt`,
      { method: "PUT", json: { prompt_text: promptText } }
    ),

  listTags: () => request<Tag[]>("/api/v1/tags"),
  createTag: (name: string) => request<Tag>("/api/v1/tags", { method: "POST", json: { name } }),
  renameTag: (id: number, name: string) =>
    request<Tag>(`/api/v1/tags/${id}`, { method: "PATCH", json: { name } }),
  deleteTag: (id: number) => request<void>(`/api/v1/tags/${id}`, { method: "DELETE" }),
  setAssetTags: (assetId: number, tagIds: number[]) =>
    request<Tag[]>(`/api/v1/assets/${assetId}/tags`, { method: "PUT", json: { tag_ids: tagIds } }),
  bulkTags: (payload: { asset_ids: number[]; add_tag_ids?: number[]; remove_tag_ids?: number[] }) =>
    request<{ ok_count: number; failed_count: number; items: { asset_id: number; ok: boolean; error: string | null }[] }>(
      "/api/v1/assets/bulk-tags",
      { method: "POST", json: payload }
    ),
  bulkMove: (payload: { asset_ids: number[]; target_folder_id: number }) =>
    request<BulkResult>(
      "/api/v1/assets/bulk-move",
      { method: "POST", json: payload }
    ),

  deleteAsset: (id: number) => request<void>(`/api/v1/assets/${id}`, { method: "DELETE" }),
  listTrash: () => request<TrashList>("/api/v1/trash"),
  restoreTrashItem: (id: number) => request<void>(`/api/v1/trash/${id}/restore`, { method: "POST" }),
  permanentDeleteTrashItem: (id: number) => request<void>(`/api/v1/trash/${id}`, { method: "DELETE" }),
  emptyTrash: () => request<{ removed: number; failed: number }>("/api/v1/trash/empty", { method: "POST" }),
  bulkTrash: (assetIds: number[]) =>
    request<BulkResult>("/api/v1/assets/bulk-trash", { method: "POST", json: { asset_ids: assetIds } }),

  getSettings: () => request<Settings>("/api/v1/settings"),
  updateSettings: (managedRoot: string) =>
    request<Settings>("/api/v1/settings", { method: "PATCH", json: { managed_root: managedRoot } })
};
