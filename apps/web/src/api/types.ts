export interface Project {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface FolderNode {
  id: number;
  name: string;
  scope_type: string;
  project_id: number | null;
  parent_id: number | null;
  sort_order: number;
  pinned: boolean;
  locked: boolean;
  description: string | null;
  children: FolderNode[];
}

export interface FolderOut {
  id: number;
  name: string;
  scope_type: string;
  project_id: number | null;
  parent_id: number | null;
  sort_order: number;
  pinned: boolean;
  locked: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface FolderEditPayload {
  name?: string;
  pinned?: boolean;
  locked?: boolean;
  description?: string | null;
}

export interface FolderCreatePayload {
  name: string;
  scope: "general" | "project";
  project_id?: number | null;
  parent_id?: number | null;
}

export interface FolderStats {
  folder_id: number;
  folder_name: string;
  subfolder_count: number;
  asset_count: number;
  managed_asset_count: number;
  external_asset_count: number;
}

export interface ProjectStats {
  project_id: number;
  project_name: string;
  subfolder_count: number;
  asset_count: number;
  managed_asset_count: number;
  external_asset_count: number;
}

export interface Settings {
  managed_root: string;
  managed_root_state: "ok" | "missing" | "unavailable";
}

export interface TagBrief {
  id: number;
  name: string;
  color: string | null;
}

export interface Tag extends TagBrief {
  asset_count: number;
  created_at: string;
  updated_at: string;
}

export interface AssetOut {
  id: number;
  folder_id: number | null;
  name: string;
  extension: string | null;
  asset_type: "image" | "video" | "audio" | "document" | "other";
  size_bytes: number;
  source_type: "managed" | "external";
  thumbnail_status: string;
  status: "active" | "trashed" | "missing";
  media_width: number | null;
  media_height: number | null;
  media_duration_ms: number | null;
  file_path: string;
  created_at: string;
  updated_at: string;
  tags: TagBrief[];
  has_prompt: boolean;
}

export interface AssetPage {
  total: number;
  page: number;
  page_size: number;
  items: AssetOut[];
}

export interface TrashItem {
  id: number;
  name: string;
  asset_type: "image" | "video" | "audio" | "document" | "other";
  size_bytes: number;
  source_type: "managed" | "external";
  deleted_at: string | null;
  original_folder: string;
  extension?: string | null;
  mime_type?: string | null;
  media_width?: number | null;
  media_height?: number | null;
  media_duration_ms?: number | null;
  thumbnail_status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TrashList {
  total: number;
  items: TrashItem[];
}

export interface BulkResult {
  ok_count: number;
  failed_count: number;
  items: { asset_id: number; ok: boolean; error: string | null }[];
}

export interface ExternalSource {
  id: number;
  root_path: string;
  display_name: string | null;
  target_folder_id: number;
  target_folder_name: string | null;
  last_scan_at: string | null;
  status: string;
  asset_count: number;
  missing_count: number;
}

export interface ScanResult {
  added: number;
  updated: number;
  missing: number;
  reactivated: number;
}

export interface ImportJobItem {
  id: number;
  source_path: string;
  status: "pending" | "processing" | "success" | "skipped" | "failed";
  error_message: string | null;
  asset_id: number | null;
  target_folder_id: number | null;
}

export interface ImportJob {
  id: number;
  job_type: string;
  status: "queued" | "running" | "completed" | "completed_with_errors" | "failed" | "interrupted";
  target_folder_id: number | null;
  total_count: number;
  success_count: number;
  skipped_count: number;
  failed_count: number;
  stage: string | null;
  message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  items: ImportJobItem[];
}

export interface ApiErrorBody {
  error?: { code?: string; message?: string };
}
