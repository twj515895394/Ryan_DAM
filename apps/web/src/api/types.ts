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

export interface ApiErrorBody {
  error?: { code?: string; message?: string };
}
