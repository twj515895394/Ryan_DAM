<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import type { AiResult, AiResultWithTask, AiTaskDetail, AiTaskSummary } from "../api/types";
import { api } from "../api/client";
import { useAiResultImageDetails } from "../composables/useAiResultCache";
import { useFolderOptions } from "../composables/useFolderOptions";
import SidebarIcon from "./SidebarIcon.vue";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";

const props = defineProps<{
  open: boolean;
  result: (AiResult | AiResultWithTask) | null;
  task?: (AiTaskDetail | AiTaskSummary) | null;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "imported", resultId: string, assetId: number): void;
  (e: "continue-edit", result: AiResult | AiResultWithTask, task?: AiTaskDetail | AiTaskSummary | null): void;
}>();

const {
  objectUrl,
  loading: loadingImage,
  error: imageError,
  reload: reloadImage
} = useAiResultImageDetails(() => props.result?.id);

// 缩放模式：'contain' (自适应窗口) 或 'actual' (1:1 原画比例)
const zoomMode = ref<"contain" | "actual">("contain");
const copyingPrompt = ref(false);
const importing = ref(false);
const importSuccessMsg = ref("");
const importErrorMsg = ref("");
const selectedFolderId = ref<number | "">("");

const { allFolderGroups } = useFolderOptions();

const taskType = computed(() => {
  if (props.task?.task_type) return props.task.task_type;
  if (props.result && "task" in props.result && (props.result as AiResultWithTask)?.task?.task_type) {
    return (props.result as AiResultWithTask).task!.task_type;
  }
  return "image_generate";
});

const taskTypeLabel = computed(() => {
  switch (taskType.value) {
    case "image_generate":
      return "文生图";
    case "image_edit":
      return "图像编辑";
    case "prompt_optimize":
      return "提示词润色";
    case "batch_reverse":
      return "批量反推";
    default:
      return "AI 产物";
  }
});

const modelName = computed(() => {
  if (props.task?.model_name) return props.task.model_name;
  if (props.result && "task" in props.result && (props.result as AiResultWithTask)?.task?.model_name) {
    return (props.result as AiResultWithTask).task!.model_name;
  }
  return props.task?.provider_name || "未知模型";
});

const promptFinal = computed(() => {
  if (props.task?.prompt_final) return props.task.prompt_final;
  if (props.result && "task" in props.result && (props.result as AiResultWithTask)?.task?.prompt_final) {
    return (props.result as AiResultWithTask).task!.prompt_final;
  }
  return "";
});

const importedAssetId = computed(() => {
  return props.result?.imported_asset_id ?? null;
});

const sizeLabel = computed(() => {
  const bytes = props.result?.size_bytes;
  if (!bytes) return "未知大小";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
});

const dimensionLabel = computed(() => {
  if (!props.result?.width || !props.result?.height) return "未知规格";
  return `${props.result.width} × ${props.result.height}`;
});

const aspectRatioLabel = computed(() => {
  if (!props.result?.width || !props.result?.height) return "";
  const r = props.result.width / props.result.height;
  if (Math.abs(r - 1) < 0.05) return "1:1 正方形";
  if (Math.abs(r - 16 / 9) < 0.08) return "16:9 宽屏横向";
  if (Math.abs(r - 9 / 16) < 0.08) return "9:16 长屏纵向";
  if (Math.abs(r - 4 / 3) < 0.08) return "4:3 经典横幅";
  if (Math.abs(r - 3 / 4) < 0.08) return "3:4 肖像纵幅";
  return `${props.result.width}:${props.result.height}`;
});

const folderOptions = computed<AppleSelectOption[]>(() => [
  { value: "", label: "资产库根目录", subLabel: "未归档" },
  ...allFolderGroups.value.flatMap((g) =>
    g.options.map((opt) => ({
      value: opt.id,
      label: opt.label,
      badge: g.label,
      badgeColor: "zinc" as const
    }))
  )
]);

async function handleCopyPrompt(): Promise<void> {
  if (!promptFinal.value || copyingPrompt.value) return;
  copyingPrompt.value = true;
  try {
    await navigator.clipboard.writeText(promptFinal.value);
    setTimeout(() => {
      copyingPrompt.value = false;
    }, 1800);
  } catch {
    copyingPrompt.value = false;
  }
}

async function handleImport(): Promise<void> {
  if (!props.result || importing.value || importedAssetId.value) return;
  importing.value = true;
  importErrorMsg.value = "";
  importSuccessMsg.value = "";

  try {
    const targetFolder = typeof selectedFolderId.value === "number" && selectedFolderId.value > 0
      ? selectedFolderId.value
      : undefined;
    const res = await api.importAiResultToAsset(props.result.id, {
      target_folder_id: targetFolder
    });
    importSuccessMsg.value = `已成功入库为资产 #${res.id}`;
    emit("imported", props.result.id, res.id);
  } catch (err: any) {
    importErrorMsg.value = err.message || "入库失败，请重试";
  } finally {
    importing.value = false;
  }
}

function handleContinueEdit(): void {
  if (!props.result) return;
  emit("continue-edit", props.result, props.task);
  emit("close");
}

function handleKeyDown(e: KeyboardEvent): void {
  if (!props.open) return;
  if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    emit("close");
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      zoomMode.value = "contain";
      importSuccessMsg.value = "";
      importErrorMsg.value = "";
      selectedFolderId.value = "";
    }
  },
  { immediate: true }
);

onMounted(() => {
  window.addEventListener("keydown", handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeyDown);
});
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open && result"
        class="fixed inset-0 z-[65] flex items-center justify-center p-3 md:p-6 bg-black/80 backdrop-blur-xl animate-fade-in select-none"
        @click.self="emit('close')"
      >
        <div
          class="flex flex-col md:flex-row w-full max-w-5xl h-[88vh] max-h-[88vh] rounded-2xl md:rounded-3xl bg-white shadow-2xl border border-white/20 overflow-hidden"
        >
          <!-- 左侧：图像主展示与交互视口 -->
          <div
            class="relative flex-1 min-w-0 min-h-0 bg-zinc-950 flex flex-col items-center justify-center overflow-hidden h-[46vh] shrink-0 md:h-full md:shrink"
          >
            <!-- 顶部悬浮控制栏 -->
            <div class="absolute top-3 left-3 right-3 z-10 flex items-center justify-between pointer-events-none">
              <!-- 规格指示徽标 -->
              <div class="pointer-events-auto flex items-center gap-2 rounded-full bg-black/60 backdrop-blur-md px-3 py-1 text-xs text-white/90 border border-white/10 shadow-sm">
                <span class="font-medium">{{ dimensionLabel }}</span>
                <span v-if="aspectRatioLabel" class="text-white/50 text-[10px]">· {{ aspectRatioLabel }}</span>
              </div>

              <!-- 缩放与保存工具 -->
              <div class="pointer-events-auto flex items-center gap-1.5 rounded-full bg-black/60 backdrop-blur-md p-1 border border-white/10 shadow-sm">
                <button
                  type="button"
                  class="rounded-full px-2.5 py-1 text-xs font-medium transition"
                  :class="zoomMode === 'contain' ? 'bg-white/20 text-white' : 'text-white/70 hover:text-white'"
                  title="适应窗口完整展示"
                  @click="zoomMode = 'contain'"
                >
                  适应
                </button>
                <button
                  type="button"
                  class="rounded-full px-2.5 py-1 text-xs font-medium transition"
                  :class="zoomMode === 'actual' ? 'bg-white/20 text-white' : 'text-white/70 hover:text-white'"
                  title="1:1 原画实际像素"
                  @click="zoomMode = 'actual'"
                >
                  1:1 原画
                </button>
                <a
                  v-if="objectUrl"
                  :href="objectUrl"
                  :download="`AI_${result.id}.png`"
                  class="rounded-full p-1.5 text-white/70 hover:bg-white/15 hover:text-white transition flex items-center justify-center"
                  title="下载原图文件"
                >
                  <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                </a>
              </div>
            </div>

            <!-- 主图像展示 -->
            <div class="h-full w-full flex items-center justify-center p-4 overflow-auto">
              <img
                v-if="objectUrl"
                :src="objectUrl"
                :alt="promptFinal || 'AI 生成产物'"
                class="transition-all duration-200 select-none"
                :class="[
                  zoomMode === 'contain'
                    ? 'max-h-full max-w-full object-contain rounded-lg shadow-2xl'
                    : 'max-none cursor-grab'
                ]"
              />
              <div v-else-if="imageError" class="flex flex-col items-center gap-3 text-white/70 p-6 text-center">
                <SidebarIcon name="close" class="h-8 w-8 text-rose-400" />
                <span class="text-xs text-rose-300">{{ imageError }}</span>
                <button
                  type="button"
                  class="mt-1 rounded-full border border-white/20 bg-white/10 px-3.5 py-1 text-xs text-white hover:bg-white/20 transition active:scale-95"
                  @click="reloadImage"
                >
                  重新加载图像
                </button>
              </div>
              <div v-else class="flex flex-col items-center gap-3 text-white/50">
                <SidebarIcon name="star" class="h-8 w-8 animate-spin opacity-40 text-accent" />
                <span class="text-xs">正在从本地安全缓存加载高清大图…</span>
              </div>
            </div>
          </div>

          <!-- 右侧：结构化元数据与入库操作面板 -->
          <div
            class="w-full md:w-[360px] lg:w-[380px] shrink-0 flex flex-col border-t md:border-t-0 md:border-l border-line/60 bg-white overflow-hidden min-h-0 flex-1 md:flex-initial"
          >
            <!-- 头部：产物身份与关闭按钮 -->
            <div class="flex items-center justify-between border-b border-line/60 px-5 py-4 shrink-0 bg-canvas/30">
              <div class="flex items-center gap-2 min-w-0">
                <span class="rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-semibold text-accent shrink-0">
                  {{ taskTypeLabel }}
                </span>
                <span class="text-xs font-mono font-medium text-ink truncate" :title="result.id">
                  #{{ result.id.slice(-8) }}
                </span>
              </div>

              <button
                type="button"
                class="rounded-xl p-1.5 text-muted hover:bg-canvas hover:text-ink transition active:scale-95"
                title="关闭预览 (Esc)"
                @click="emit('close')"
              >
                <SidebarIcon name="close" class="h-4 w-4" />
              </button>
            </div>

            <!-- 中部：滚动详情区域 -->
            <div class="flex-1 overflow-y-auto p-5 space-y-4">
              <!-- 模型与硬件规格 -->
              <div class="rounded-2xl border border-line/60 bg-canvas/40 p-3.5 space-y-2 text-xs">
                <div class="flex items-center justify-between">
                  <span class="text-muted">执行模型</span>
                  <span class="font-medium text-ink text-right truncate max-w-[180px]" :title="modelName || ''">{{ modelName }}</span>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-muted">图像分辨率</span>
                  <span class="font-medium text-ink">{{ dimensionLabel }}</span>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-muted">文件体积</span>
                  <span class="font-medium text-ink">{{ sizeLabel }}</span>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-muted">入库状态</span>
                  <span
                    class="font-medium inline-flex items-center gap-1"
                    :class="importedAssetId ? 'text-emerald-600' : 'text-amber-600'"
                  >
                    <span>{{ importedAssetId ? `已入库 (#${importedAssetId})` : "未入库 (临时历史)" }}</span>
                  </span>
                </div>
              </div>

              <!-- 提示词快照 -->
              <div class="space-y-1.5">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-semibold text-ink">生成提示词</span>
                  <button
                    type="button"
                    class="text-[11px] font-medium text-accent hover:underline flex items-center gap-1"
                    :disabled="!promptFinal"
                    @click="handleCopyPrompt"
                  >
                    <SidebarIcon v-if="copyingPrompt" name="check" class="h-3 w-3 text-emerald-600" />
                    <svg v-else class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                    <span>{{ copyingPrompt ? "已复制" : "复制提示词" }}</span>
                  </button>
                </div>
                <div
                  class="max-h-36 overflow-y-auto rounded-xl border border-line/60 bg-canvas/30 p-3 text-xs text-ink/90 leading-relaxed font-mono select-text"
                >
                  {{ promptFinal || "（无提示词）" }}
                </div>
              </div>

              <!-- 入库目标目录选择（未入库时展示） -->
              <div v-if="!importedAssetId" class="space-y-1.5 pt-1">
                <label class="block text-xs font-semibold text-ink">入库目标目录 (可选)</label>
                <AppleSelect
                  v-model="selectedFolderId"
                  size="sm"
                  searchable
                  :options="folderOptions"
                  placeholder="-- 入库到根目录 --"
                  search-placeholder="搜索目标目录…"
                />
                <p class="text-[11px] text-muted">
                  入库后将正式纳管进 DAM 主媒体库，支持标星、标签分类及全格式检索。
                </p>
              </div>

              <!-- 成功/错误反馈横幅 -->
              <div v-if="importSuccessMsg" class="rounded-xl bg-emerald-50 border border-emerald-200 p-2.5 text-xs text-emerald-800 flex items-center gap-1.5">
                <SidebarIcon name="check" class="h-4 w-4 text-emerald-600 shrink-0" />
                <span>{{ importSuccessMsg }}</span>
              </div>
              <div v-if="importErrorMsg" class="rounded-xl bg-danger/10 border border-danger/20 p-2.5 text-xs text-danger flex items-center gap-1.5">
                <SidebarIcon name="close" class="h-4 w-4 text-danger shrink-0" />
                <span>{{ importErrorMsg }}</span>
              </div>
            </div>

            <!-- 底部：固定操作栏 -->
            <div class="border-t border-line/60 bg-canvas/30 p-4 space-y-2 shrink-0">
              <!-- 入库主按钮 -->
              <button
                v-if="!importedAssetId"
                type="button"
                class="w-full flex h-9 items-center justify-center gap-2 rounded-xl bg-accent px-4 text-xs font-medium text-white shadow-xs hover:bg-blue-700 transition active:scale-98 disabled:opacity-50"
                :disabled="importing"
                @click="handleImport"
              >
                <SidebarIcon name="folder" class="h-3.5 w-3.5" :class="importing ? 'animate-spin' : ''" />
                <span>{{ importing ? "正在入库中…" : "入库到 DAM 资产库" }}</span>
              </button>
              <div
                v-else
                class="w-full flex h-9 items-center justify-center gap-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs font-medium text-emerald-700"
              >
                <SidebarIcon name="check" class="h-4 w-4 text-emerald-600" />
                <span>该产物已入库 (资产 #{{ importedAssetId }})</span>
              </div>

              <!-- 二度编辑/变体按钮 -->
              <button
                type="button"
                class="w-full flex h-9 items-center justify-center gap-2 rounded-xl border border-line bg-white px-4 text-xs font-medium text-ink shadow-2xs hover:bg-canvas transition active:scale-98"
                title="以该图作为参考图唤起 AI 生图工作台"
                @click="handleContinueEdit"
              >
                <SidebarIcon name="star" class="h-3.5 w-3.5 text-accent" />
                <span>作为参考图继续编辑</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
