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
  children: FolderNode[];
}

export interface FolderOut {
  id: number;
  name: string;
  scope_type: string;
  project_id: number | null;
  parent_id: number | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface FolderCreatePayload {
  name: string;
  scope: "general" | "project";
  project_id?: number | null;
  parent_id?: number | null;
}

export interface Settings {
  managed_root: string;
  managed_root_state: "ok" | "missing" | "unavailable";
}

export interface AssetOut {
  id: number;
  folder_id: number;
  name: string;
  extension: string | null;
  asset_type: "image" | "video" | "audio" | "document" | "other";
  size_bytes: number;
  source_type: "managed" | "external";
  thumbnail_status: string;
  created_at: string;
}

export interface AssetPage {
  total: number;
  page: number;
  page_size: number;
  items: AssetOut[];
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
