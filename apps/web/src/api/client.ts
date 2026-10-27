import type {
  AiDefaultBinding,
  AiDefaultBindingPayload,
  AiModelProfile,
  AiModelProfileCreatePayload,
  AiModelProfileUpdatePayload,
  AiProviderCreatePayload,
  AiProviderInstance,
  AiProviderTestPayload,
  AiProviderTestResponse,
  AiProviderUpdatePayload,
  AiReverseTemplate,
  AiReverseTemplateCreatePayload,
  SingleImageReverseRequest,
  SingleImageReverseResult,
  AiTaskCancelResponse,
  AiTaskDetail,
  AiTaskListResponse,
  AiTaskSummary,
  AiResult,
  AiResultListResponse,
  BatchImportResultsResponse,
  AiCreationPreset,
  PromptOptimizeRequest,
  PromptOptimizeResult,
  SubmitImageGeneratePayload,
  SubmitBatchReversePayload,
  CommitBatchReversePayload,
  CommitBatchReverseResponse,
  UpdateTaskItemDraftPayload,
  AiTaskItem,
  ApiErrorBody,
  AssetOut,
  AssetPage,
  AssetPromptOut,
  BulkResult,
  ExternalSource,
  FolderCreatePayload,
  FolderEditPayload,
  FolderNode,
  FolderOut,
  FolderStats,
  ImportJob,
  Project,
  ProjectStats,
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
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
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
    throw new ApiRequestError(code, message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listProjects: () => request<Project[]>("/api/v1/projects"),
  createProject: (name: string) => request<Project>("/api/v1/projects", { method: "POST", json: { name } }),
  renameProject: (id: number, name: string) =>
    request<Project>(`/api/v1/projects/${id}`, { method: "PATCH", json: { name } }),
  deleteProject: (id: number, cascade = false) =>
    request<void>(`/api/v1/projects/${id}${cascade ? "?cascade=true" : ""}`, { method: "DELETE" }),
  getProjectStats: (id: number) => request<ProjectStats>(`/api/v1/projects/${id}/stats`),

  generalTree: () => request<FolderNode[]>("/api/v1/folders/tree?scope=general"),
  projectTree: (projectId: number) =>
    request<FolderNode[]>(`/api/v1/folders/tree?scope=project&project_id=${projectId}`),
  createFolder: (payload: FolderCreatePayload) =>
    request<FolderOut>("/api/v1/folders", { method: "POST", json: payload }),
  updateFolder: (id: number, payload: FolderEditPayload) =>
    request<FolderOut>(`/api/v1/folders/${id}`, { method: "PATCH", json: payload }),
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

  getAsset: (id: number) => request<AssetOut>(`/api/v1/assets/${id}`),
  renameAsset: (id: number, name: string) =>
    request<AssetOut>(`/api/v1/assets/${id}`, { method: "PATCH", json: { name } }),
  moveAsset: (id: number, folderId: number) =>
    request<AssetOut>(`/api/v1/assets/${id}/move`, { method: "POST", json: { folder_id: folderId } }),

  listExternalSources: () => request<ExternalSource[]>("/api/v1/external-sources"),
  createExternalSource: (
    rootPath: string,
    target: { targetFolderId?: number | null; targetProjectId?: number | null; createMountFolder: boolean }
  ) =>
    request<{ source: ExternalSource; scan: ScanResult }>("/api/v1/external-sources", {
      method: "POST",
      json: {
        root_path: rootPath,
        target_folder_id: target.targetFolderId ?? null,
        target_project_id: target.targetProjectId ?? null,
        create_mount_folder: target.createMountFolder
      }
    }),
  scanExternalSource: (id: number) =>
    request<ScanResult>(`/api/v1/external-sources/${id}/scan`, { method: "POST" }),
  unlinkExternalSource: (id: number) =>
    request<{ removed: number; mount_folder_removed: boolean }>(`/api/v1/external-sources/${id}`, {
      method: "DELETE"
    }),
  convertToManaged: (id: number) =>
    request<AssetOut>(`/api/v1/assets/${id}/convert-to-managed`, { method: "POST" }),
  getAssetPrompt: (id: number) =>
    request<AssetPromptOut>(
      `/api/v1/assets/${id}/prompt`
    ),
  setAssetPrompt: (
    id: number,
    promptText: string | null,
    options?: { expectedRevision?: number; promptOrigin?: string }
  ) =>
    request<AssetPromptOut>(
      `/api/v1/assets/${id}/prompt`,
      {
        method: "PUT",
        json: {
          prompt_text: promptText,
          expected_revision: options?.expectedRevision,
          prompt_origin: options?.promptOrigin ?? "manual"
        }
      }
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
  bulkConvertToManaged: (payload: { asset_ids: number[] }) =>
    request<BulkResult>("/api/v1/assets/bulk-convert-to-managed", {
      method: "POST",
      json: payload
    }),

  deleteAsset: (id: number) => request<void>(`/api/v1/assets/${id}`, { method: "DELETE" }),
  listTrash: () => request<TrashList>("/api/v1/trash"),
  restoreTrashItem: (id: number) => request<void>(`/api/v1/trash/${id}/restore`, { method: "POST" }),
  permanentDeleteTrashItem: (id: number) => request<void>(`/api/v1/trash/${id}`, { method: "DELETE" }),
  emptyTrash: () => request<{ removed: number; failed: number }>("/api/v1/trash/empty", { method: "POST" }),
  bulkTrash: (assetIds: number[]) =>
    request<BulkResult>("/api/v1/assets/bulk-trash", { method: "POST", json: { asset_ids: assetIds } }),

  getSettings: () => request<Settings>("/api/v1/settings"),
  updateSettings: (managedRoot: string) =>
    request<Settings>("/api/v1/settings", { method: "PATCH", json: { managed_root: managedRoot } }),

  // V2 AI Provider Instances
  listAiProviders: () => request<AiProviderInstance[]>("/api/v1/ai/providers"),
  getAiProvider: (id: number) => request<AiProviderInstance>(`/api/v1/ai/providers/${id}`),
  createAiProvider: (payload: AiProviderCreatePayload) =>
    request<AiProviderInstance>("/api/v1/ai/providers", { method: "POST", json: payload }),
  updateAiProvider: (id: number, payload: AiProviderUpdatePayload) =>
    request<AiProviderInstance>(`/api/v1/ai/providers/${id}`, { method: "PATCH", json: payload }),
  deleteAiProvider: (id: number) =>
    request<void>(`/api/v1/ai/providers/${id}`, { method: "DELETE" }),
  testAiProvider: (id: number, payload: AiProviderTestPayload) =>
    request<AiProviderTestResponse>(`/api/v1/ai/providers/${id}/test`, { method: "POST", json: payload }),

  // V2 AI Model Profiles & Defaults
  listAllModels: () => request<AiModelProfile[]>("/api/v1/ai/models"),
  listProviderModels: (providerId: number) =>
    request<AiModelProfile[]>(`/api/v1/ai/providers/${providerId}/models`),
  createModelProfile: (providerId: number, payload: AiModelProfileCreatePayload) =>
    request<AiModelProfile>(`/api/v1/ai/providers/${providerId}/models`, { method: "POST", json: payload }),
  updateModelProfile: (modelId: number, payload: AiModelProfileUpdatePayload) =>
    request<AiModelProfile>(`/api/v1/ai/models/${modelId}`, { method: "PATCH", json: payload }),
  deleteModelProfile: (modelId: number) =>
    request<void>(`/api/v1/ai/models/${modelId}`, { method: "DELETE" }),

  listDefaultBindings: () => request<AiDefaultBinding[]>("/api/v1/ai/defaults"),
  setDefaultBinding: (payload: AiDefaultBindingPayload) =>
    request<AiDefaultBinding>("/api/v1/ai/defaults", { method: "POST", json: payload }),

  // V2 Reverse Templates & API
  listReverseTemplates: (enabledOnly = false) =>
    request<AiReverseTemplate[]>(`/api/v1/ai/reverse/templates${enabledOnly ? "?enabled_only=true" : ""}`),
  createReverseTemplate: (payload: AiReverseTemplateCreatePayload) =>
    request<AiReverseTemplate>("/api/v1/ai/reverse/templates", { method: "POST", json: payload }),
  updateReverseTemplate: (id: number, payload: Partial<AiReverseTemplateCreatePayload>) =>
    request<AiReverseTemplate>(`/api/v1/ai/reverse/templates/${id}`, { method: "PUT", json: payload }),
  deleteReverseTemplate: (id: number) =>
    request<void>(`/api/v1/ai/reverse/templates/${id}`, { method: "DELETE" }),
  reverseSingleImage: (assetId: number, payload: SingleImageReverseRequest) =>
    request<SingleImageReverseResult>(`/api/v1/ai/reverse/assets/${assetId}`, { method: "POST", json: payload }),

  // V2 AI Task Center
  listAiTasks: (params?: { task_type?: string; status?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.task_type) q.set("task_type", params.task_type);
    if (params?.status) q.set("status", params.status);
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    if (params?.offset !== undefined) q.set("offset", String(params.offset));
    const qs = q.toString();
    return request<AiTaskListResponse>(`/api/v1/ai/tasks${qs ? `?${qs}` : ""}`);
  },
  getAiTask: (id: string) => request<AiTaskDetail>(`/api/v1/ai/tasks/${id}`),
  cancelAiTask: (id: string) =>
    request<AiTaskCancelResponse>(`/api/v1/ai/tasks/${id}/cancel`, { method: "POST" }),
  retryAiTask: (id: string) =>
    request<AiTaskSummary>(`/api/v1/ai/tasks/${id}/retry`, { method: "POST" }),

  submitImageGenerate: (payload: SubmitImageGeneratePayload) =>
    request<AiTaskSummary>("/api/v1/ai/tasks", { method: "POST", json: payload }),
  submitBatchReverse: (payload: SubmitBatchReversePayload) =>
    request<AiTaskSummary>("/api/v1/ai/tasks/batch-reverse", { method: "POST", json: payload }),
  commitBatchReverseItems: (taskId: string, payload: CommitBatchReversePayload) =>
    request<CommitBatchReverseResponse>(`/api/v1/ai/tasks/${taskId}/commit-items`, { method: "POST", json: payload }),
  updateTaskItemDraft: (taskId: string, itemId: number, payload: UpdateTaskItemDraftPayload) =>
    request<AiTaskItem>(`/api/v1/ai/tasks/${taskId}/items/${itemId}`, { method: "PUT", json: payload }),
  stageUploadReference: (payload: { filename: string; content_base64?: string | null; file_path?: string | null }) =>
    request<{ upload_id: string; filename: string; size_bytes: number; width: number; height: number }>(
      "/api/v1/ai/tasks/staging/upload",
      { method: "POST", json: payload }
    ),

  // V2 Creation Presets & Prompt Optimize
  listCreationPresets: (creationMode = "image_generate", enabledOnly = false) => {
    const q = new URLSearchParams();
    if (creationMode) q.set("creation_mode", creationMode);
    if (enabledOnly) q.set("enabled_only", "true");
    const qs = q.toString();
    return request<AiCreationPreset[]>(`/api/v1/ai/presets${qs ? `?${qs}` : ""}`);
  },
  getCreationPreset: (id: number) => request<AiCreationPreset>(`/api/v1/ai/presets/${id}`),
  createCreationPreset: (payload: Partial<AiCreationPreset>) =>
    request<AiCreationPreset>("/api/v1/ai/presets", { method: "POST", json: payload }),
  updateCreationPreset: (id: number, payload: Partial<AiCreationPreset>) =>
    request<AiCreationPreset>(`/api/v1/ai/presets/${id}`, { method: "PUT", json: payload }),
  deleteCreationPreset: (id: number) =>
    request<void>(`/api/v1/ai/presets/${id}`, { method: "DELETE" }),
  optimizePrompt: (payload: PromptOptimizeRequest) =>
    request<PromptOptimizeResult>("/api/v1/ai/prompt/optimize", { method: "POST", json: payload }),

  // V2 AI History Results
  listAiResults: (params?: {
    task_id?: string;
    task_type?: string;
    model_profile_id?: number;
    query?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.task_id) q.set("task_id", params.task_id);
    if (params?.task_type) q.set("task_type", params.task_type);
    if (params?.model_profile_id !== undefined) q.set("model_profile_id", String(params.model_profile_id));
    if (params?.query) q.set("query", params.query);
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    if (params?.offset !== undefined) q.set("offset", String(params.offset));
    const qs = q.toString();
    return request<AiResultListResponse>(`/api/v1/ai/results${qs ? `?${qs}` : ""}`);
  },
  getAiResult: (id: string) => request<AiResult>(`/api/v1/ai/results/${id}`),
  deleteAiResult: (id: string, confirm = true) =>
    request<{ id: string; status: string }>(`/api/v1/ai/results/${id}?confirm=${confirm}`, { method: "DELETE" }),
  getAiResultContentUrl: (id: string) => `/api/v1/ai/results/${id}/content`,
  importAiResultToAsset: (id: string, payload?: { target_folder_id?: number; custom_name?: string }) =>
    request<AssetOut>(`/api/v1/ai/results/${id}/import`, { method: "POST", json: payload || {} }),
  batchImportAiResults: (payload: { result_ids: string[]; target_folder_id?: number }) =>
    request<BatchImportResultsResponse>("/api/v1/ai/results/batch-import", { method: "POST", json: payload })
};
