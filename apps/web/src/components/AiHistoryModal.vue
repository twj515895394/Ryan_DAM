<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "../api/client";
import type { AiModelProfile, AiResultWithTask, FolderNode } from "../api/types";
import { library, notify } from "../stores/library";
import { useFolderOptions } from "../composables/useFolderOptions";
import SidebarIcon from "./SidebarIcon.vue";
import ConfirmDialog from "./ConfirmDialog.vue";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "open-workbench"): void;
  (e: "create-variant", result: AiResultWithTask): void;
  (e: "imported", count: number): void;
}>();

// ── 目录选项 ────────────────────────────────────────────────────────────
const { allFolderGroups } = useFolderOptions();
const targetFolderId = ref<number | undefined>(undefined);

// ── 筛选与搜索状态 ───────────────────────────────────────────────────────
const queryText = ref("");
const selectedTaskType = ref<string>("");
const selectedModelId = ref<number | "">("");
const filterImported = ref<"all" | "imported" | "unimported">("all");

const taskTypeOptions: AppleSelectOption[] = [
  { value: "", label: "全部任务类型" },
  { value: "txt2img", label: "文生图 (txt2img)", badge: "生图", badgeColor: "emerald" },
  { value: "img2img", label: "图生图 (img2img)", badge: "参考", badgeColor: "blue" },
  { value: "image_edit", label: "图像扩展/编辑", badge: "编辑", badgeColor: "amber" }
];

const modelFilterOptions = computed<AppleSelectOption[]>(() => [
  { value: "", label: "全部模型 Profile" },
  ...models.value.map((m) => ({
    value: m.id,
    label: m.name,
    subLabel: m.model_id
  }))
]);

const folderSelectOptions = computed<AppleSelectOption[]>(() =>
  allFolderGroups.value.flatMap((g) =>
    g.options.map((opt) => ({
      value: opt.id,
      label: opt.label,
      badge: g.label,
      badgeColor: "zinc" as const
    }))
  )
);

const models = ref<AiModelProfile[]>([]);
const results = ref<AiResultWithTask[]>([]);
const totalCount = ref(0);
const loading = ref(false);
const limit = 40;
const offset = ref(0);

// ── 多选状态 ────────────────────────────────────────────────────────────
const selectedIds = ref<Set<string>>(new Set());

// ── 单图详情浮层 ────────────────────────────────────────────────────────
const activeDetailResult = ref<AiResultWithTask | null>(null);
const singleImporting = ref(false);
const singleImportFolderId = ref<number | undefined>(undefined);

// ── 批量操作状态 ────────────────────────────────────────────────────────
const showBatchImportDialog = ref(false);
const batchImporting = ref(false);
const showBatchDeleteConfirm = ref(false);
const batchDeleting = ref(false);

// ── 单项删除确认 ────────────────────────────────────────────────────────
const pendingDeleteId = ref<string | null>(null);
const showSingleDeleteConfirm = ref(false);

// ── 格式化辅助 ──────────────────────────────────────────────────────────
function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(isoStr: string): string {
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return isoStr;
  const pad = (n: number) => (n < 10 ? `0${n}` : `${n}`);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ── 加载模型列表 ────────────────────────────────────────────────────────
async function loadModels(): Promise<void> {
  try {
    models.value = await api.listAllModels();
  } catch {
    // 忽略加载失败
  }
}

// ── 加载结果列表 ────────────────────────────────────────────────────────
let searchDebounce: ReturnType<typeof setTimeout> | null = null;

async function fetchResults(resetOffset = false): Promise<void> {
  if (resetOffset) {
    offset.value = 0;
  }
  loading.value = true;
  try {
    const res = await api.listAiResults({
      query: queryText.value.trim() || undefined,
      task_type: selectedTaskType.value || undefined,
      model_profile_id: selectedModelId.value !== "" ? Number(selectedModelId.value) : undefined,
      limit,
      offset: offset.value
    });
    results.value = res.items;
    totalCount.value = res.total;
  } catch (err) {
    notify("error", `获取生成历史失败: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    loading.value = false;
  }
}

watch(
  [selectedTaskType, selectedModelId],
  () => {
    void fetchResults(true);
  }
);

watch(queryText, () => {
  if (searchDebounce) clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    void fetchResults(true);
  }, 300);
});

// 计算属性：前端辅助过滤入库状态
const displayedResults = computed(() => {
  if (filterImported.value === "imported") {
    return results.value.filter((r) => r.imported_asset_id !== null);
  }
  if (filterImported.value === "unimported") {
    return results.value.filter((r) => r.imported_asset_id === null);
  }
  return results.value;
});

// ── 勾选与多选 ──────────────────────────────────────────────────────────
const isAllSelected = computed(() => {
  if (displayedResults.value.length === 0) return false;
  return displayedResults.value.every((r) => selectedIds.value.has(r.id));
});

function toggleSelect(id: string, e?: Event): void {
  e?.stopPropagation();
  const next = new Set(selectedIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  selectedIds.value = next;
}

function toggleSelectAll(): void {
  if (isAllSelected.value) {
    selectedIds.value = new Set();
  } else {
    selectedIds.value = new Set(displayedResults.value.map((r) => r.id));
  }
}

// ── 单张操作 ────────────────────────────────────────────────────────────
function openDetail(item: AiResultWithTask): void {
  activeDetailResult.value = item;
  singleImportFolderId.value = targetFolderId.value || allFolderGroups.value[0]?.options[0]?.id;
}

function closeDetail(): void {
  activeDetailResult.value = null;
}

async function copyPrompt(text?: string | null): Promise<void> {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    notify("success", "提示词已复制到剪贴板");
  } catch {
    notify("error", "复制失败，请手动选取");
  }
}

async function importSingleResult(item: AiResultWithTask): Promise<void> {
  singleImporting.value = true;
  try {
    const res = await api.importAiResultToAsset(item.id, {
      target_folder_id: singleImportFolderId.value
    });
    item.imported_asset_id = res.id;
    notify("success", `已成功入库资产「${res.name}」`);
    emit("imported", 1);
  } catch (err) {
    notify("error", `入库失败: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    singleImporting.value = false;
  }
}

function requestDeleteSingle(id: string, e?: Event): void {
  e?.stopPropagation();
  pendingDeleteId.value = id;
  showSingleDeleteConfirm.value = true;
}

async function confirmDeleteSingle(): Promise<void> {
  if (!pendingDeleteId.value) return;
  const id = pendingDeleteId.value;
  try {
    await api.deleteAiResult(id, true);
    notify("success", "历史结果已彻底清理");
    results.value = results.value.filter((r) => r.id !== id);
    selectedIds.value.delete(id);
    if (activeDetailResult.value?.id === id) {
      activeDetailResult.value = null;
    }
  } catch (err) {
    notify("error", `删除失败: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    showSingleDeleteConfirm.value = false;
    pendingDeleteId.value = null;
  }
}

// ── 批量入库 ────────────────────────────────────────────────────────────
function openBatchImportDialog(): void {
  if (selectedIds.value.size === 0) return;
  targetFolderId.value = targetFolderId.value || allFolderGroups.value[0]?.options[0]?.id;
  showBatchImportDialog.value = true;
}

async function executeBatchImport(): Promise<void> {
  if (selectedIds.value.size === 0) return;
  batchImporting.value = true;
  try {
    const ids = Array.from(selectedIds.value);
    const resp = await api.batchImportAiResults({
      result_ids: ids,
      target_folder_id: targetFolderId.value
    });
    notify("success", `已成功将 ${resp.total_imported} 张生成图片入库`);
    showBatchImportDialog.value = false;
    selectedIds.value = new Set();
    emit("imported", resp.total_imported);
    void fetchResults();
  } catch (err) {
    notify("error", `批量入库失败: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    batchImporting.value = false;
  }
}

// ── 批量清理 ────────────────────────────────────────────────────────────
async function executeBatchDelete(): Promise<void> {
  if (selectedIds.value.size === 0) return;
  batchDeleting.value = true;
  let successCount = 0;
  try {
    const ids = Array.from(selectedIds.value);
    for (const id of ids) {
      try {
        await api.deleteAiResult(id, true);
        successCount++;
      } catch {
        // 单个失败继续
      }
    }
    notify("success", `已清理 ${successCount} 项生成历史`);
    selectedIds.value = new Set();
    showBatchDeleteConfirm.value = false;
    void fetchResults();
  } catch (err) {
    notify("error", `批量清理异常: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    batchDeleting.value = false;
  }
}

function handleCreateVariant(item: AiResultWithTask, e?: Event): void {
  e?.stopPropagation();
  emit("create-variant", item);
}

// ── 弹窗打开初始化 ──────────────────────────────────────────────────────
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      void loadModels();
      void fetchResults(true);
      selectedIds.value = new Set();
    }
  },
  { immediate: true }
);
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in"
    @click.self="emit('close')"
  >
    <div
      class="flex h-[90vh] w-[95vw] max-w-6xl flex-col rounded-2xl bg-white shadow-2xl border border-line/60 overflow-hidden"
    >
      <!-- 头部栏 -->
      <header class="flex h-14 shrink-0 items-center justify-between border-b border-line/60 px-6 bg-canvas/40">
        <div class="flex items-center gap-3">
          <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/10 text-accent">
            <SidebarIcon name="star" class="h-4 w-4" />
          </div>
          <div>
            <h2 class="text-sm font-semibold text-ink flex items-center gap-2">
              <span>AI 生成历史总览</span>
              <span class="rounded-full bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent">
                永久存储 ({{ totalCount }})
              </span>
            </h2>
            <p class="text-[11px] text-muted">所有生图历史均持久化隔离存储，手动入库后才进入资产主库</p>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <button
            type="button"
            class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-accent/20 bg-accent/5 hover:bg-accent/10 px-3 text-xs font-medium text-accent transition"
            @click="emit('open-workbench')"
          >
            <SidebarIcon name="star" class="h-3.5 w-3.5" />
            <span>进入 AI 创作</span>
          </button>
          <button
            type="button"
            class="rounded-lg p-1.5 text-muted hover:bg-black/5 hover:text-ink transition"
            @click="emit('close')"
          >
            <SidebarIcon name="close" class="h-4 w-4" />
          </button>
        </div>
      </header>

      <!-- 多维筛选控制条 -->
      <div class="flex flex-wrap items-center justify-between gap-3 border-b border-line/40 px-6 py-2.5 bg-canvas/20">
        <div class="flex flex-wrap items-center gap-2.5">
          <!-- 关键词搜索 -->
          <div class="relative w-56">
            <input
              v-model="queryText"
              type="text"
              placeholder="搜索提示词关键词..."
              class="h-8 w-full rounded-lg border border-line/80 bg-white pl-7 pr-7 text-xs text-ink placeholder:text-muted/60 focus:border-accent focus:outline-none"
            />
            <SidebarIcon name="filter" class="pointer-events-none absolute left-2 top-2 h-3.5 w-3.5 text-muted" />
            <button
              v-if="queryText"
              class="absolute right-2 top-2 text-muted hover:text-ink"
              @click="queryText = ''"
            >
              <SidebarIcon name="close" class="h-3 w-3" />
            </button>
          </div>

          <!-- 任务类型 (AppleSelect) -->
          <div class="w-36 shrink-0">
            <AppleSelect
              v-model="selectedTaskType"
              size="sm"
              :options="taskTypeOptions"
              placeholder="全部任务类型"
            />
          </div>

          <!-- 模型筛选 (AppleSelect) -->
          <div class="w-44 shrink-0">
            <AppleSelect
              v-model="selectedModelId"
              size="sm"
              :options="modelFilterOptions"
              placeholder="全部模型 Profile"
            />
          </div>

          <!-- 入库状态 -->
          <div class="flex rounded-lg border border-line/80 bg-canvas/60 p-0.5 text-xs">
            <button
              type="button"
              class="rounded-md px-2.5 py-1 font-medium transition"
              :class="filterImported === 'all' ? 'bg-white text-ink shadow-xs' : 'text-muted hover:text-ink'"
              @click="filterImported = 'all'"
            >
              全部
            </button>
            <button
              type="button"
              class="rounded-md px-2.5 py-1 font-medium transition"
              :class="filterImported === 'unimported' ? 'bg-white text-ink shadow-xs' : 'text-muted hover:text-ink'"
              @click="filterImported = 'unimported'"
            >
              未入库
            </button>
            <button
              type="button"
              class="rounded-md px-2.5 py-1 font-medium transition"
              :class="filterImported === 'imported' ? 'bg-white text-ink shadow-xs' : 'text-muted hover:text-ink'"
              @click="filterImported = 'imported'"
            >
              已入库
            </button>
          </div>
        </div>

        <!-- 刷新与全选控制 -->
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line/80 bg-white px-2.5 text-xs text-ink hover:bg-canvas/60 transition active:scale-97"
            @click="fetchResults()"
          >
            <SidebarIcon name="refresh" class="h-3.5 w-3.5 text-muted" :class="{ 'animate-spin': loading }" />
            <span>刷新</span>
          </button>
          <button
            type="button"
            class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line/80 bg-white px-2.5 text-xs font-medium text-ink hover:bg-canvas/60 transition"
            @click="toggleSelectAll"
          >
            <span>{{ isAllSelected ? "取消全选" : "全选当前页" }}</span>
          </button>
        </div>
      </div>

      <!-- 结果卡片网格区域 -->
      <main class="flex-1 overflow-y-auto p-6 bg-canvas/10">
        <div v-if="loading && results.length === 0" class="flex h-64 items-center justify-center">
          <div class="flex flex-col items-center gap-3 text-muted text-xs">
            <SidebarIcon name="refresh" class="h-6 w-6 animate-spin text-accent" />
            <span>正在加载历史生成结果...</span>
          </div>
        </div>

        <div v-else-if="displayedResults.length === 0" class="flex h-64 flex-col items-center justify-center text-muted">
          <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-canvas border border-line/60 mb-2">
            <SidebarIcon name="star" class="h-6 w-6 text-muted/60" />
          </div>
          <p class="text-sm font-medium text-ink/80">暂无符合条件的 AI 生成结果</p>
          <p class="text-xs text-muted/80 mt-1">尝试更换检索条件或前往 AI 创作工作台发起生成</p>
        </div>

        <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          <div
            v-for="item in displayedResults"
            :key="item.id"
            class="group relative flex flex-col rounded-xl border bg-white overflow-hidden shadow-xs hover:shadow-md transition cursor-pointer select-none"
            :class="selectedIds.has(item.id) ? 'border-accent ring-2 ring-accent/20' : 'border-line/60 hover:border-line'"
            @click="openDetail(item)"
          >
            <!-- 勾选框 (Apple HIG 44x44px 热区) -->
            <button
              type="button"
              class="absolute left-1.5 top-1.5 z-10 flex h-9 w-9 items-center justify-center rounded-lg transition"
              @click="toggleSelect(item.id, $event)"
            >
              <div
                class="flex h-4 w-4 items-center justify-center rounded border transition"
                :class="selectedIds.has(item.id) ? 'border-accent bg-accent text-white' : 'border-white/80 bg-black/30 backdrop-blur-xs text-transparent hover:border-white'"
              >
                <svg class="h-3 w-3" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M12.207 4.793a1 1 0 010 1.414l-5 5a1 1 0 01-1.414 0l-2-2a1 1 0 011.414-1.414L6.5 9.086l4.293-4.293a1 1 0 011.414 0z" />
                </svg>
              </div>
            </button>

            <!-- 已入库徽标 -->
            <div
              v-if="item.imported_asset_id !== null"
              class="absolute right-2 top-2 z-10 rounded-md bg-emerald-500/90 backdrop-blur-xs px-1.5 py-0.5 text-[10px] font-medium text-white shadow-xs"
            >
              已入库
            </div>

            <!-- 图片容器 -->
            <div class="relative aspect-square w-full bg-black/5 overflow-hidden">
              <img
                :src="api.getAiResultContentUrl(item.id)"
                :alt="item.task?.prompt_final || 'AI Result'"
                loading="lazy"
                class="h-full w-full object-cover transition duration-300 group-hover:scale-103"
              />

              <!-- 悬浮快捷操作蒙层 -->
              <div
                class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2 justify-between"
              >
                <button
                  type="button"
                  class="rounded-lg bg-white/90 p-1.5 text-ink hover:bg-white transition shadow-xs text-[11px] font-medium flex items-center gap-1"
                  title="以此图参数创作变体"
                  @click="handleCreateVariant(item, $event)"
                >
                  <SidebarIcon name="star" class="h-3 w-3 text-accent" />
                  <span>变体</span>
                </button>

                <button
                  type="button"
                  class="rounded-lg bg-white/90 p-1.5 text-danger hover:bg-white transition shadow-xs"
                  title="删除此条记录"
                  @click="requestDeleteSingle(item.id, $event)"
                >
                  <SidebarIcon name="trash" class="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <!-- 卡片信息区 -->
            <div class="p-2.5 flex flex-col gap-1">
              <div class="flex items-center justify-between text-[10px] text-muted">
                <span class="font-medium text-ink/80">{{ item.task?.model_name || "未知模型" }}</span>
                <span>{{ item.width && item.height ? `${item.width}×${item.height}` : formatBytes(item.size_bytes) }}</span>
              </div>
              <p class="text-[11px] text-ink/90 line-clamp-2 leading-relaxed" :title="item.task?.prompt_final || ''">
                {{ item.task?.prompt_final || "（无提示词）" }}
              </p>
              <div class="text-[9.5px] text-muted/70 mt-0.5">
                {{ formatDate(item.created_at) }}
              </div>
            </div>
          </div>
        </div>
      </main>

      <!-- 底部多选批量操作栏 -->
      <footer
        v-if="selectedIds.size > 0"
        class="flex h-14 shrink-0 items-center justify-between border-t border-accent/20 bg-accent/5 px-6 animate-fade-in"
      >
        <div class="flex items-center gap-3">
          <span class="text-xs font-semibold text-accent">
            已勾选 {{ selectedIds.size }} 项生成结果
          </span>
          <button
            type="button"
            class="text-xs text-muted hover:text-ink transition underline"
            @click="selectedIds = new Set()"
          >
            清空勾选
          </button>
        </div>

        <div class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-danger/30 bg-white hover:bg-danger/5 px-3 text-xs font-medium text-danger transition"
            @click="showBatchDeleteConfirm = true"
          >
            <SidebarIcon name="trash" class="h-3.5 w-3.5" />
            <span>批量清理 ({{ selectedIds.size }})</span>
          </button>

          <button
            type="button"
            class="inline-flex h-8 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-xs font-medium text-white shadow-xs hover:bg-blue-700 transition"
            @click="openBatchImportDialog"
          >
            <SidebarIcon name="folder" class="h-3.5 w-3.5" />
            <span>批量入库到资产库</span>
          </button>
        </div>
      </footer>
    </div>

    <!-- 单图大图详情抽屉/浮层 -->
    <div
      v-if="activeDetailResult"
      class="fixed inset-0 z-60 flex items-center justify-center bg-black/60 backdrop-blur-md p-6 animate-fade-in"
      @click.self="closeDetail"
    >
      <div
        class="flex max-h-[92vh] w-full max-w-4xl flex-col md:flex-row rounded-2xl bg-white shadow-2xl border border-line/60 overflow-hidden"
      >
        <!-- 大图展示区 -->
        <div class="flex-1 bg-black/95 flex items-center justify-center p-4 relative min-h-[360px]">
          <img
            :src="api.getAiResultContentUrl(activeDetailResult.id)"
            class="max-h-[80vh] max-w-full object-contain rounded-lg shadow-lg"
          />
        </div>

        <!-- 右侧元数据与操作面板 -->
        <div class="w-full md:w-80 flex flex-col justify-between border-l border-line/60 bg-white p-5">
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <span class="rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-semibold text-accent">
                {{ activeDetailResult.task?.task_type || "AI 产物" }}
              </span>
              <button
                type="button"
                class="rounded-lg p-1 text-muted hover:bg-black/5 hover:text-ink transition"
                @click="closeDetail"
              >
                <SidebarIcon name="close" class="h-4 w-4" />
              </button>
            </div>

            <!-- 模型与参数信息 -->
            <div class="rounded-xl bg-canvas/60 p-3 space-y-1.5 text-xs">
              <div class="flex justify-between">
                <span class="text-muted">模型：</span>
                <span class="font-medium text-ink">{{ activeDetailResult.task?.model_name || "未知" }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted">分辨率：</span>
                <span class="font-medium text-ink">{{ activeDetailResult.width }} × {{ activeDetailResult.height }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted">体积：</span>
                <span class="font-medium text-ink">{{ formatBytes(activeDetailResult.size_bytes) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted">时间：</span>
                <span class="text-ink">{{ formatDate(activeDetailResult.created_at) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted">入库状态：</span>
                <span
                  class="font-medium"
                  :class="activeDetailResult.imported_asset_id ? 'text-emerald-600' : 'text-amber-600'"
                >
                  {{ activeDetailResult.imported_asset_id ? `已入库 (#${activeDetailResult.imported_asset_id})` : "未入库" }}
                </span>
              </div>
            </div>

            <!-- 提示词详情 -->
            <div>
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-xs font-semibold text-ink">生成提示词</span>
                <button
                  type="button"
                  class="text-[11px] font-medium text-accent hover:underline flex items-center gap-1"
                  @click="copyPrompt(activeDetailResult.task?.prompt_final)"
                >
                  <span>复制</span>
                </button>
              </div>
              <div class="max-h-36 overflow-y-auto rounded-xl border border-line/60 bg-canvas/30 p-2.5 text-xs text-ink/90 leading-relaxed font-mono">
                {{ activeDetailResult.task?.prompt_final || "（无最终提示词）" }}
              </div>
            </div>

            <!-- 入库目标目录选择 -->
            <div v-if="!activeDetailResult.imported_asset_id" class="space-y-1.5">
              <label class="text-xs font-semibold text-ink">入库目标目录</label>
              <AppleSelect
                v-model="singleImportFolderId"
                size="sm"
                searchable
                :options="folderSelectOptions"
                placeholder="-- 请选择入库目标目录 --"
                search-placeholder="搜索目录名称…"
              />
            </div>
          </div>

          <!-- 操作按钮组 -->
          <div class="pt-4 border-t border-line/60 space-y-2">
            <button
              v-if="!activeDetailResult.imported_asset_id"
              type="button"
              class="w-full flex h-8 items-center justify-center gap-1.5 rounded-xl bg-accent px-3 text-xs font-medium text-white shadow-xs hover:bg-blue-700 transition active:scale-98 disabled:opacity-50"
              :disabled="singleImporting"
              @click="importSingleResult(activeDetailResult)"
            >
              <SidebarIcon name="folder" class="h-3.5 w-3.5" />
              <span>{{ singleImporting ? "入库中..." : "入库到资产库" }}</span>
            </button>

            <button
              type="button"
              class="w-full flex h-8 items-center justify-center gap-1.5 rounded-xl border border-accent/20 bg-accent/5 hover:bg-accent/10 px-3 text-xs font-medium text-accent transition active:scale-98"
              @click="handleCreateVariant(activeDetailResult)"
            >
              <SidebarIcon name="star" class="h-3.5 w-3.5" />
              <span>以此参数创作变体</span>
            </button>

            <button
              type="button"
              class="w-full flex h-8 items-center justify-center gap-1.5 rounded-xl border border-danger/20 text-danger hover:bg-danger/5 px-3 text-xs font-medium transition active:scale-98"
              @click="requestDeleteSingle(activeDetailResult.id)"
            >
              <SidebarIcon name="trash" class="h-3.5 w-3.5" />
              <span>删除此条记录</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 批量入库选择目录弹窗 -->
    <div
      v-if="showBatchImportDialog"
      class="fixed inset-0 z-70 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in"
      @click.self="showBatchImportDialog = false"
    >
      <div class="w-full max-w-md rounded-2xl bg-white shadow-2xl border border-line/60 p-6 space-y-4">
        <h3 class="text-sm font-semibold text-ink">批量入库目标目录</h3>
        <p class="text-xs text-muted">
          选中的 {{ selectedIds.size }} 张图片将复制进所选目录的托管存储，并作为正规资产打上「AI 生成」来源。
        </p>

        <div>
          <label class="block text-xs font-medium text-ink mb-1.5">选择目录</label>
          <AppleSelect
            v-model="targetFolderId"
            searchable
            :options="folderSelectOptions"
            placeholder="-- 请选择目标目录 --"
            search-placeholder="搜索目录名称…"
          />
        </div>

        <div class="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            class="h-8 rounded-xl border border-line px-3 text-xs font-medium text-ink hover:bg-canvas transition"
            @click="showBatchImportDialog = false"
          >
            取消
          </button>
          <button
            type="button"
            class="h-8 rounded-xl bg-accent px-4 text-xs font-medium text-white shadow-xs hover:bg-blue-700 transition disabled:opacity-50"
            :disabled="batchImporting"
            @click="executeBatchImport"
          >
            {{ batchImporting ? "正在入库..." : "确认批量入库" }}
          </button>
        </div>
      </div>
    </div>

    <!-- Apple HIG 单项删除确认弹窗 -->
    <ConfirmDialog
      :open="showSingleDeleteConfirm"
      title="彻底删除此条生成历史？"
      description="此操作将从永久存储区中移除此条图片记录并清理物理文件。若该图已入库为主库资产，已入库的资产文件将独立保留不受影响。"
      intent="danger"
      confirm-text="确认清理"
      @confirm="confirmDeleteSingle"
      @cancel="showSingleDeleteConfirm = false"
    />

    <!-- Apple HIG 批量删除确认弹窗 -->
    <ConfirmDialog
      :open="showBatchDeleteConfirm"
      :title="`确认批量清理选中的 ${selectedIds.size} 项生成记录？`"
      description="选中的生成历史记录与底层文件将被彻底删除且无法撤销。已入库到主库的正式资产不会受任何影响。"
      intent="danger"
      confirm-text="确认全部清理"
      @confirm="executeBatchDelete"
      @cancel="showBatchDeleteConfirm = false"
    />
  </div>
</template>
