import type {
  ApiErrorBody,
  AssetPage,
  FolderCreatePayload,
  FolderNode,
  FolderOut,
  ImportJob,
  Project,
  Settings
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
  deleteFolder: (id: number) => request<void>(`/api/v1/folders/${id}`, { method: "DELETE" }),

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

  listAssets: (params: { scope?: string; project_id?: number; folder_id?: number; page?: number; page_size?: number }) => {
    const query = new URLSearchParams();
    if (params.scope) query.set("scope", params.scope);
    if (params.project_id !== undefined) query.set("project_id", String(params.project_id));
    if (params.folder_id !== undefined) query.set("folder_id", String(params.folder_id));
    query.set("page", String(params.page ?? 1));
    query.set("page_size", String(params.page_size ?? 50));
    return request<AssetPage>(`/api/v1/assets?${query.toString()}`);
  },

  getSettings: () => request<Settings>("/api/v1/settings"),
  updateSettings: (managedRoot: string) =>
    request<Settings>("/api/v1/settings", { method: "PATCH", json: { managed_root: managedRoot } })
};
