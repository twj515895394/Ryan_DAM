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

  // V2 Origins & Prompt Versioning
  asset_origin?: "local_import" | "ai_generated" | "ai_edited";
  prompt_origin?: "manual" | "ai_reverse" | "generation_prompt" | "edit_prompt" | null;
  prompt_revision?: number;
  generation_task_id?: string | null;
  generation_result_id?: string | null;
}

export interface AssetPromptOut {
  asset_id: number;
  prompt_text: string | null;
  has_prompt: boolean;
  prompt_origin?: "manual" | "ai_reverse" | "generation_prompt" | "edit_prompt" | null;
  prompt_revision: number;
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
  mount_folder: boolean;
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

// V2 AI Capabilities & Models
export type AiCapabilityType = "text_optimize" | "image_understand" | "image_generate" | "image_edit";

export interface AiProviderInstance {
  id: number;
  family: "openai_compatible" | "openai_native" | "gemini_native";
  name: string;
  base_url: string;
  has_api_key?: boolean;
  masked_api_key?: string;
  credential_masked?: string;
  enabled: boolean;
  settings?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface AiProviderCreatePayload {
  family: "openai_compatible" | "openai_native" | "gemini_native";
  name: string;
  base_url: string;
  api_key: string;
  enabled?: boolean;
  settings?: Record<string, any>;
}

export interface AiProviderUpdatePayload {
  name?: string;
  base_url?: string;
  api_key?: string;
  enabled?: boolean;
  settings?: Record<string, any>;
}

export interface AiProviderTestPayload {
  api_key?: string;
  base_url?: string;
  model_id?: string;
  capability?: AiCapabilityType;
}

export interface AiProviderTestResultItem {
  capability: string;
  supported: boolean;
  latency_ms: number;
  model_id: string;
  message: string;
  error_code?: string | null;
  output_sample?: string | null;
}

export interface AiProviderTestResponse {
  connection_ok: boolean;
  message: string;
  results: Record<string, AiProviderTestResultItem>;
}

export interface AiRemoteModelItem {
  id: string;
  name?: string | null;
  description?: string | null;
}

export interface AiModelProfile {
  id: number;
  provider_id: number;
  model_id: string;
  name: string;
  adapter_kind: "openai_standard" | "openai_chat_markdown" | "gemini_standard" | "custom";
  enabled: boolean;
  capabilities: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AiModelProfileCreatePayload {
  model_id: string;
  name: string;
  adapter_kind?: "openai_standard" | "openai_chat_markdown" | "gemini_standard" | "custom";
  enabled?: boolean;
  capabilities?: Record<string, any>;
}

export interface AiModelProfileUpdatePayload {
  name?: string;
  adapter_kind?: "openai_standard" | "openai_chat_markdown" | "gemini_standard" | "custom";
  enabled?: boolean;
  capabilities?: Record<string, any>;
}

export interface AiDefaultBinding {
  id: number;
  capability: AiCapabilityType;
  scene: string;
  model_profile_id: number;
  model_name: string;
  model_id: string;
  provider_id: number;
  provider_name: string;
  created_at: string;
  updated_at: string;
}

export interface AiDefaultBindingPayload {
  capability: AiCapabilityType;
  scene?: string;
  model_profile_id: number;
}

// V2 Reverse Templates & Requests
export interface AiReverseTemplate {
  id: number;
  name: string;
  code: string | null;
  description: string | null;
  system_prompt: string;
  user_prompt_template: string | null;
  default_model_profile_id: number | null;
  enabled: boolean;
  sort_order: number;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export interface AiReverseTemplateCreatePayload {
  name: string;
  code?: string | null;
  description?: string | null;
  system_prompt: string;
  user_prompt_template?: string | null;
  default_model_profile_id?: number | null;
  enabled?: boolean;
  sort_order?: number;
}

export interface SingleImageReverseRequest {
  template_id?: number | null;
  model_profile_id?: number | null;
  language?: "zh" | "en";
  custom_system_prompt?: string | null;
  user_instruction?: string | null;
}

export interface SingleImageReverseResult {
  asset_id: number;
  reversed_prompt: string;
  template_name: string;
  model_id: string;
  model_name: string;
  provider_name: string;
  has_conflict: boolean;
  current_asset_prompt: string | null;
  current_asset_revision: number;
}

// V2 Task Center & Execution Models
export type AiTaskType = "image_generate" | "image_edit" | "batch_reverse" | "prompt_optimize";

export type AiTaskStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "partial_failed"
  | "failed"
  | "cancel_requested"
  | "canceled"
  | "recovery_needed";

export interface AiTaskSummary {
  id: string;
  task_type: AiTaskType;
  provider_id: number | null;
  provider_name: string | null;
  model_profile_id: number | null;
  model_name: string | null;
  status: AiTaskStatus;
  retry_of: string | null;
  prompt_final: string | null;
  progress_pct: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
  items_count: number;
  results_count: number;
}

export interface AiTaskItem {
  id: number;
  task_id: string;
  asset_id: number | null;
  asset_name?: string | null;
  current_prompt_text?: string | null;
  status: "pending" | "running" | "succeeded" | "failed" | "committed" | "skipped";
  draft_prompt_text: string | null;
  prompt_revision_at_start: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubmitBatchReversePayload {
  asset_ids: number[];
  template_id?: number | null;
  model_profile_id?: number | null;
  language?: "zh" | "en";
  custom_system_prompt?: string | null;
  user_instruction?: string | null;
}

export interface CommitBatchReversePayload {
  item_ids: number[];
  edited_drafts?: Record<number, string> | null;
  allow_overwrite?: boolean;
}

export interface CommitBatchReverseResponse {
  committed_count: number;
  skipped_count: number;
  conflict_count: number;
  details: {
    item_id: number;
    asset_id?: number;
    status: "committed" | "skipped" | "conflict";
    reason?: string;
    current_prompt?: string | null;
    new_revision?: number;
  }[];
}

export interface UpdateTaskItemDraftPayload {
  draft_prompt_text: string;
}

export interface AiTaskReference {
  id: number;
  task_id: string;
  seq: number;
  role: string | null;
  source_kind: "asset" | "history_result" | "local_upload";
  source_id: string | null;
  snapshot_path: string;
  sha256: string | null;
  created_at: string;
}

export interface AiResult {
  id: string;
  task_id: string;
  idx: number;
  history_file_path: string;
  mime_type: string;
  sha256: string | null;
  width: number | null;
  height: number | null;
  size_bytes: number;
  imported_asset_id: number | null;
  is_deleted: boolean;
  created_at: string;
}

export interface AiResultWithTask extends AiResult {
  task?: {
    task_type: AiTaskType;
    provider_name: string | null;
    model_name: string | null;
    prompt_final: string | null;
  } | null;
}

export interface AiResultListResponse {
  items: AiResultWithTask[];
  total: number;
  limit: number;
  offset: number;
}

export interface BatchImportResultsResponse {
  items: {
    result_id: string;
    asset_id: number | null;
    status: "success" | "already_imported" | "error";
    error_message: string | null;
  }[];
  total_imported: number;
}

// V2 Creation Presets & Prompt Optimize
export interface AiCreationPreset {
  id: number;
  name: string;
  code: string | null;
  description: string | null;
  creation_mode: string;
  system_rules: string | null;
  default_model_profile_id: number | null;
  default_params: {
    prompt_suffix?: string;
    negative_prompt?: string;
    [key: string]: any;
  };
  is_builtin: boolean;
  enabled: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface PromptOptimizeRequest {
  prompt: string;
  preset_id?: number | null;
  model_profile_id?: number | null;
  custom_instruction?: string | null;
  language?: "zh" | "en";
}

export interface PromptOptimizeResult {
  original_prompt: string;
  optimized_prompt: string;
  model_profile_id: number;
  model_name: string;
  provider_name: string;
  diff_summary: string | null;
}

export interface ReferenceItemPayload {
  source_kind: "asset" | "history_result" | "local_upload";
  source_id: string;
  role?: string;
}

export interface StagedUploadPayload {
  filename: string;
  content_base64?: string | null;
  file_path?: string | null;
}

export interface StagedUploadOut {
  upload_id: string;
  filename: string;
  size_bytes: number;
  width: number;
  height: number;
}

export interface SubmitImageGeneratePayload {
  task_type?: "image_generate" | "image_edit";
  prompt: string;
  model_profile_id?: number | null;
  preset_id?: number | null;
  params?: Record<string, any>;
  reference_asset_ids?: number[];
  references?: ReferenceItemPayload[];
  raw_user_request?: string | null;
  retry_of?: string | null;
}

export interface AiTaskDetail extends AiTaskSummary {
  preset_id: number | null;
  idempotency_key: string | null;
  raw_user_request: string | null;
  params: Record<string, any>;
  external_handle: string | null;
  items: AiTaskItem[];
  references: AiTaskReference[];
  results: AiResult[];
}

export interface AiTaskListResponse {
  items: AiTaskSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface AiTaskCancelResponse {
  task_id: string;
  cancelled: boolean;
  status: AiTaskStatus;
}


