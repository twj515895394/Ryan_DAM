<script setup lang="ts">
import { computed, ref } from "vue";
import type { AiResult, AiTaskDetail } from "../api/types";
import { api } from "../api/client";
import { useAiResultImageDetails } from "../composables/useAiResultCache";
import { useFolderOptions } from "../composables/useFolderOptions";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";
import SidebarIcon from "./SidebarIcon.vue";
import AiResultThumb from "./AiResultThumb.vue";

const props = defineProps<{
  taskDetail: AiTaskDetail;
  modelName?: string;
}>();

const emit = defineEmits<{
  (e: "back-to-edit"): void;
  (e: "regenerate"): void;
  (e: "inspect-detail", result: AiResult, task: AiTaskDetail): void;
}>();

const results = computed(() => props.taskDetail.results || []);
const activeIndex = ref(0);

const activeResult = computed<AiResult | null>(() => {
  if (results.value.length === 0) return null;
  const idx = Math.min(activeIndex.value, results.value.length - 1);
  return results.value[idx] || null;
});

const {
  objectUrl: activeObjectUrl,
  loading: loadingImage,
  error: imageError,
  reload: reloadActiveImage
} = useAiResultImageDetails(() => activeResult.value?.id);

// 文件夹入库
const { allFolderGroups } = useFolderOptions();
const selectedFolderId = ref<number | "">("");
const importing = ref(false);
const importSuccessMap = ref<Record<string, number>>({});
const importErrorMsg = ref("");
const copyingPrompt = ref(false);

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

const currentImportedAssetId = computed(() => {
  if (!activeResult.value) return null;
  return importSuccessMap.value[activeResult.value.id] ?? activeResult.value.imported_asset_id ?? null;
});

async function handleImport(): Promise<void> {
  if (!activeResult.value || importing.value || currentImportedAssetId.value) return;
  importing.value = true;
  importErrorMsg.value = "";

  try {
    const targetFolder = typeof selectedFolderId.value === "number" && selectedFolderId.value > 0
      ? selectedFolderId.value
      : undefined;
    const res = await api.importAiResultToAsset(activeResult.value.id, {
      target_folder_id: targetFolder
    });
    importSuccessMap.value[activeResult.value.id] = res.id;
  } catch (err: any) {
    importErrorMsg.value = err.message || "入库失败，请重试";
  } finally {
    importing.value = false;
  }
}

async function handleCopyPrompt(): Promise<void> {
  const p = props.taskDetail.prompt_final || "";
  if (!p || copyingPrompt.value) return;
  copyingPrompt.value = true;
  try {
    await navigator.clipboard.writeText(p);
    setTimeout(() => {
      copyingPrompt.value = false;
    }, 1800);
  } catch {
    copyingPrompt.value = false;
  }
}

function handleDownload(): void {
  if (!activeObjectUrl.value) return;
  const a = document.createElement("a");
  a.href = activeObjectUrl.value;
  a.download = `ryan_ai_${activeResult.value?.id.slice(0, 10) || "result"}.png`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function handleInspect(): void {
  if (activeResult.value) {
    emit("inspect-detail", activeResult.value, props.taskDetail);
  }
}
</script>

<template>
  <div class="flex flex-col space-y-4 px-6 py-4 animate-scale-in">
    <!-- 顶部状态栏与面包屑 -->
    <div class="flex items-center justify-between border-b border-line/60 pb-3">
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
          @click="emit('back-to-edit')"
        >
          <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m15 18-6-6 6-6" />
          </svg>
          <span>返回修改提示词</span>
        </button>

        <span class="text-xs text-muted">/</span>
        <span class="text-xs font-semibold text-ink">生成完成</span>

        <span v-if="results.length > 1" class="rounded-full bg-accent/10 px-2 py-0.5 text-[10.5px] font-semibold text-accent">
          共生成 {{ results.length }} 张
        </span>
      </div>

      <div class="flex items-center gap-3 text-[11px] text-muted">
        <span v-if="activeResult?.width && activeResult?.height" class="font-mono">
          {{ activeResult.width }} × {{ activeResult.height }}
        </span>
        <span v-if="modelName" class="rounded bg-canvas px-1.5 py-0.5 text-ink/80">
          {{ modelName }}
        </span>
      </div>
    </div>

    <!-- 主展示画布与多图选择 -->
    <div class="flex flex-col items-center justify-center">
      <!-- 大图展示舞台 (点击放大检视) -->
      <div
        class="group relative flex max-h-[52vh] max-w-full items-center justify-center overflow-hidden rounded-2xl border border-line/80 bg-zinc-950/90 p-2 shadow-2xl transition-all"
      >
        <img
          v-if="activeObjectUrl"
          :src="activeObjectUrl"
          alt="AI 生成结果"
          class="max-h-[48vh] w-auto max-w-full rounded-xl object-contain transition duration-200 group-hover:scale-[1.01]"
        />

        <div v-else-if="imageError" class="flex h-64 w-80 flex-col items-center justify-center gap-2 text-xs text-rose-400 p-4 text-center">
          <span>{{ imageError }}</span>
          <button
            type="button"
            class="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs text-white hover:bg-white/20 transition active:scale-95"
            @click="reloadActiveImage"
          >
            重新加载图像
          </button>
        </div>

        <div v-else class="flex h-64 w-80 items-center justify-center text-xs text-muted">
          正在载入高清图像…
        </div>

        <!-- 悬浮微操作胶囊 (右上角) -->
        <div class="absolute right-4 top-4 flex items-center gap-1.5 rounded-xl border border-white/20 bg-black/60 p-1 backdrop-blur-md opacity-90 transition hover:opacity-100">
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded-lg text-white/80 transition hover:bg-white/20 hover:text-white"
            title="1:1 微距像素检视"
            @click="handleInspect"
          >
            <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
            </svg>
          </button>
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded-lg text-white/80 transition hover:bg-white/20 hover:text-white"
            title="下载原图"
            @click="handleDownload"
          >
            <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
            </svg>
          </button>
        </div>

        <!-- 点击查看全屏提示条 (底端) -->
        <div
          class="pointer-events-none absolute bottom-4 rounded-full border border-white/15 bg-black/50 px-3 py-1 text-[11px] font-medium text-white/80 opacity-0 backdrop-blur-md transition-opacity duration-200 group-hover:opacity-100"
        >
          点击右上角 🔍 可 1:1 微距查看真实细节
        </div>
      </div>

      <!-- 多图结果缩略选择条 (若生成张数 > 1) -->
      <div
        v-if="results.length > 1"
        class="mt-3 flex items-center gap-2 overflow-x-auto p-1"
      >
        <button
          v-for="(res, idx) in results"
          :key="res.id"
          type="button"
          class="relative h-14 w-14 overflow-hidden rounded-xl border transition-all"
          :class="idx === activeIndex ? 'border-accent ring-2 ring-accent/30 scale-105' : 'border-line opacity-70 hover:opacity-100'"
          @click="activeIndex = idx"
        >
          <AiResultThumb :result-id="res.id" class="h-full w-full object-cover" />
          <span class="absolute bottom-0.5 right-1 rounded bg-black/60 px-1 text-[9px] font-mono text-white">
            #{{ idx + 1 }}
          </span>
        </button>
      </div>
    </div>

    <!-- 底部决策与操作工具条 (Apple HIG 悬浮毛玻璃底栏) -->
    <div class="rounded-2xl border border-line/70 bg-canvas/60 p-3.5 backdrop-blur-md">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <!-- 左侧：快速入库区域 -->
        <div class="flex items-center gap-2">
          <div class="w-48 sm:w-56">
            <AppleSelect
              v-model="selectedFolderId"
              size="sm"
              :options="folderOptions"
              :disabled="importing || !!currentImportedAssetId"
              placeholder="选择目标文件夹…"
            />
          </div>

          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition active:scale-97 disabled:cursor-not-allowed"
            :class="currentImportedAssetId
              ? 'border border-emerald-300 bg-emerald-50 text-emerald-700'
              : 'bg-accent text-white hover:bg-blue-700 shadow-xs'"
            :disabled="importing || !!currentImportedAssetId"
            @click="handleImport"
          >
            <SidebarIcon
              v-if="currentImportedAssetId"
              name="check"
              class="h-3.5 w-3.5"
            />
            <svg
              v-else
              class="h-3.5 w-3.5"
              :class="importing ? 'animate-spin' : ''"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
              <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
            </svg>
            <span>
              {{ currentImportedAssetId ? `已入库 (#${currentImportedAssetId})` : (importing ? '正在入库…' : '📥 立即入库') }}
            </span>
          </button>

          <span v-if="importErrorMsg" class="text-xs text-rose-600">
            {{ importErrorMsg }}
          </span>
        </div>

        <!-- 右侧：调整与再次生成决策 -->
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-xl border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
            @click="handleCopyPrompt"
          >
            <svg class="h-3.5 w-3.5 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
              <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
            </svg>
            <span>{{ copyingPrompt ? "已复制！" : "复制 Prompt" }}</span>
          </button>

          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-xl border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
            @click="emit('back-to-edit')"
          >
            <SidebarIcon name="edit" class="h-3.5 w-3.5 text-muted" />
            <span>调整提示词</span>
          </button>

          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-xl border border-accent/40 bg-accent/10 px-3.5 py-1.5 text-xs font-semibold text-accent transition hover:bg-accent/20 active:scale-97"
            @click="emit('regenerate')"
          >
            <SidebarIcon name="refresh" class="h-3.5 w-3.5" />
            <span>✨ 再来一组</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.96);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.animate-scale-in {
  animation: scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
</style>
