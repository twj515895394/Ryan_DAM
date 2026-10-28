<script setup lang="ts">
import { ref, watch } from "vue";
import { api } from "../api/client";
import type { AiResultWithTask, AssetOut } from "../api/types";
import { loadAiResultObjectUrl } from "../composables/useAiResultCache";
import SidebarIcon from "./SidebarIcon.vue";
import AssetThumb from "./AssetThumb.vue";
import AiResultThumb from "./AiResultThumb.vue";

export interface SelectedReferenceItem {
  source_kind: "asset" | "history_result" | "local_upload";
  source_id: string;
  preview_url: string;
  name: string;
  role: string;
}

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "pick", item: SelectedReferenceItem): void;
}>();

const activeTab = ref<"local" | "library" | "history">("local");

// 本地上传状态
const localUploading = ref(false);
const localError = ref("");
const fileInputRef = ref<HTMLInputElement | null>(null);

// 资产库选择状态
const libraryLoading = ref(false);
const libraryQuery = ref("");
const libraryAssets = ref<AssetOut[]>([]);

// 历史结果状态
const historyLoading = ref(false);
const historyResults = ref<AiResultWithTask[]>([]);

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      localError.value = "";
      if (activeTab.value === "library") void loadLibraryAssets();
      else if (activeTab.value === "history") void loadHistoryResults();
    }
  },
  { immediate: true }
);

watch(activeTab, (tab) => {
  if (tab === "library" && libraryAssets.value.length === 0) {
    void loadLibraryAssets();
  } else if (tab === "history" && historyResults.value.length === 0) {
    void loadHistoryResults();
  }
});

// ── 本地上传处理 ────────────────────────────────────────────────────────
function triggerFileInput(): void {
  fileInputRef.value?.click();
}

async function handleFileChange(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement;
  const files = target.files;
  if (!files || files.length === 0) return;
  await uploadFile(files[0]);
  target.value = "";
}

async function handleDrop(event: DragEvent): Promise<void> {
  event.preventDefault();
  const files = event.dataTransfer?.files;
  if (!files || files.length === 0) return;
  await uploadFile(files[0]);
}

async function uploadFile(file: File): Promise<void> {
  if (!file.type.startsWith("image/")) {
    localError.value = "仅支持上传图片文件 (JPG, PNG, WebP)";
    return;
  }

  localUploading.value = true;
  localError.value = "";

  try {
    const base64 = await readFileAsBase64(file);
    const staged = await api.stageUploadReference({
      filename: file.name,
      content_base64: base64
    });

    emit("pick", {
      source_kind: "local_upload",
      source_id: staged.upload_id,
      preview_url: base64,
      name: file.name,
      role: "reference"
    });
    emit("close");
  } catch (err: any) {
    localError.value = err.message || "上传参考图失败";
  } finally {
    localUploading.value = false;
  }
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("读取本地文件失败"));
    reader.readAsDataURL(file);
  });
}

// ── 资产库加载 ──────────────────────────────────────────────────────────
async function loadLibraryAssets(): Promise<void> {
  libraryLoading.value = true;
  try {
    const page = await api.listAssets({
      asset_type: "image",
      q: libraryQuery.value || undefined,
      page_size: 30
    });
    libraryAssets.value = page.items;
  } catch (err) {
    console.error("加载资产库图片失败", err);
  } finally {
    libraryLoading.value = false;
  }
}

async function pickAsset(asset: AssetOut): Promise<void> {
  const url = await api.fetchThumbnailObjectUrl(asset.id).catch(() => "");
  emit("pick", {
    source_kind: "asset",
    source_id: String(asset.id),
    preview_url: url,
    name: asset.name,
    role: "reference"
  });
  emit("close");
}

// ── 历史生成结果加载 ────────────────────────────────────────────────────
async function loadHistoryResults(): Promise<void> {
  historyLoading.value = true;
  try {
    const res = await api.listAiResults({ limit: 30 });
    historyResults.value = res.items;
  } catch (err) {
    console.error("加载生成历史失败", err);
  } finally {
    historyLoading.value = false;
  }
}

async function pickHistoryResult(item: AiResultWithTask): Promise<void> {
  const url = await loadAiResultObjectUrl(item.id);
  emit("pick", {
    source_kind: "history_result",
    source_id: item.id,
    preview_url: url || "",
    name: item.task?.prompt_final?.slice(0, 20) || `AI_${item.id.slice(0, 8)}`,
    role: "reference"
  });
  emit("close");
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      leave-active-class="transition duration-100 ease-in"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-[60] flex items-center justify-center bg-black/45 p-4 backdrop-blur-md"
        @click.self="emit('close')"
      >
        <div
          class="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl border border-line/80 bg-white/95 shadow-2xl backdrop-blur-xl"
        >
          <!-- 弹窗顶栏与 Tab 切换 -->
          <div class="flex items-center justify-between border-b border-line/60 px-5 py-3.5">
            <div class="flex items-center gap-1.5 rounded-xl border border-line bg-canvas/60 p-1">
              <button
                type="button"
                class="rounded-lg px-3 py-1 text-xs font-medium transition"
                :class="
                  activeTab === 'local'
                    ? 'bg-white text-accent shadow-xs'
                    : 'text-muted hover:text-ink'
                "
                @click="activeTab = 'local'"
              >
                本地上传
              </button>
              <button
                type="button"
                class="rounded-lg px-3 py-1 text-xs font-medium transition"
                :class="
                  activeTab === 'library'
                    ? 'bg-white text-accent shadow-xs'
                    : 'text-muted hover:text-ink'
                "
                @click="activeTab = 'library'"
              >
                从主资产库选择
              </button>
              <button
                type="button"
                class="rounded-lg px-3 py-1 text-xs font-medium transition"
                :class="
                  activeTab === 'history'
                    ? 'bg-white text-accent shadow-xs'
                    : 'text-muted hover:text-ink'
                "
                @click="activeTab = 'history'"
              >
                从 AI 历史选择
              </button>
            </div>

            <button
              type="button"
              class="flex h-7 w-7 items-center justify-center rounded-lg text-muted transition hover:bg-black/5 hover:text-ink"
              @click="emit('close')"
            >
              <SidebarIcon name="close" class="h-4 w-4" />
            </button>
          </div>

          <!-- 主体内容区 -->
          <div class="flex-1 overflow-y-auto p-5">
            <!-- 1. 本地上传面板 -->
            <div v-if="activeTab === 'local'" class="space-y-3">
              <div
                class="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-line/80 bg-canvas/30 px-6 py-12 text-center transition hover:border-accent/60 hover:bg-accent/5 cursor-pointer"
                @click="triggerFileInput"
                @dragover.prevent
                @drop="handleDrop"
              >
                <input
                  ref="fileInputRef"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  class="hidden"
                  @change="handleFileChange"
                />

                <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent mb-3">
                  <SidebarIcon name="image" class="h-6 w-6" />
                </div>
                <p class="text-sm font-semibold text-ink">
                  {{ localUploading ? "正在上传与校验图片…" : "点击或拖拽参考图到此处" }}
                </p>
                <p class="mt-1 text-xs text-muted">支持 JPG, PNG, WebP 格式，单个图片最大 20MB</p>
              </div>

              <div v-if="localError" class="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                {{ localError }}
              </div>
            </div>

            <!-- 2. 主资产库选择面板 -->
            <div v-else-if="activeTab === 'library'" class="space-y-3">
              <div class="flex items-center gap-2">
                <input
                  v-model="libraryQuery"
                  type="text"
                  placeholder="搜索资产库图片…"
                  class="h-8 flex-1 rounded-xl border border-line bg-canvas/40 px-3 text-xs text-ink outline-none transition focus:border-accent focus:bg-white"
                  @keydown.enter="loadLibraryAssets"
                />
                <button
                  type="button"
                  class="rounded-xl border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink transition hover:bg-canvas"
                  @click="loadLibraryAssets"
                >
                  搜索
                </button>
              </div>

              <div v-if="libraryLoading" class="py-12 text-center text-xs text-muted">
                正在加载主库图片…
              </div>
              <div v-else-if="libraryAssets.length === 0" class="py-12 text-center text-xs text-muted">
                资产库暂无符合条件的图片
              </div>
              <div v-else class="grid grid-cols-3 gap-2.5 sm:grid-cols-4">
                <div
                  v-for="asset in libraryAssets"
                  :key="asset.id"
                  class="group relative aspect-square cursor-pointer overflow-hidden rounded-xl border border-line/60 bg-canvas/50 transition hover:border-accent hover:shadow-sm"
                  @click="pickAsset(asset)"
                >
                  <AssetThumb
                    :asset-id="asset.id"
                    :asset-type="asset.asset_type"
                    :thumbnail-status="asset.thumbnail_status"
                    hover-zoom
                  />
                  <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 to-transparent p-1.5 text-left">
                    <p class="truncate text-[10.5px] font-medium text-white">{{ asset.name }}</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- 3. AI 历史结果选择面板 -->
            <div v-else-if="activeTab === 'history'" class="space-y-3">
              <div v-if="historyLoading" class="py-12 text-center text-xs text-muted">
                正在加载 AI 生成历史…
              </div>
              <div v-else-if="historyResults.length === 0" class="py-12 text-center text-xs text-muted">
                暂无历史生成图片
              </div>
              <div v-else class="grid grid-cols-3 gap-2.5 sm:grid-cols-4">
                <div
                  v-for="item in historyResults"
                  :key="item.id"
                  class="group relative aspect-square cursor-pointer overflow-hidden rounded-xl border border-line/60 bg-canvas/50 transition hover:border-accent hover:shadow-sm"
                  @click="pickHistoryResult(item)"
                >
                  <AiResultThumb
                    :result-id="item.id"
                    hover-zoom
                    class="h-full w-full border-none rounded-none"
                  />
                  <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 to-transparent p-1.5 text-left">
                    <p class="truncate text-[10px] text-white/90">
                      {{ item.task?.prompt_final || item.id }}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
