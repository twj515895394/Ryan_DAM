<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import { api } from "../api/client";
import AssetIcon from "./AssetIcon.vue";
import type { AssetOut } from "../api/types";

const props = withDefaults(
  defineProps<{
    asset: AssetOut;
    selected: boolean;
    selectionActive?: boolean;
  }>(),
  { selectionActive: false }
);

const emit = defineEmits<{
  (e: "open", asset: AssetOut): void;
  (e: "toggle-select", asset: AssetOut, event?: MouseEvent): void;
  (e: "prompt", asset: AssetOut): void;
}>();

function onCardClick(e: MouseEvent): void {
  // 当满足下列任一条件时，单击整张卡片一律触发勾选/多选，绝不打断弹出大图预览：
  // 1. 用户按住 Ctrl / Meta / Shift 修饰键（桌面端标准连续/独立多选）
  // 2. 当前已有选中的资产（处于批量选择状态）
  if (e.ctrlKey || e.metaKey || e.shiftKey || props.selectionActive) {
    emit("toggle-select", props.asset, e);
    return;
  }
  // 未在选择态时，单击打开大图预览
  emit("open", props.asset);
}

function onCardDblClick(): void {
  // 双击卡片始终打开大图预览
  emit("open", props.asset);
}

function onCheckboxClick(e: MouseEvent): void {
  emit("toggle-select", props.asset, e);
}

const canUsePrompt = computed(() => props.asset.asset_type === "image" || props.asset.asset_type === "video");

const objectUrl = ref<string | null>(null);
let loadToken = 0;

const typeLabel = computed(() => {
  switch (props.asset.asset_type) {
    case "image": return "图片";
    case "video": return "视频";
    case "audio": return "音频";
    case "document": return "文档";
    default: return "文件";
  }
});

const sizeLabel = computed(() => {
  const bytes = props.asset.size_bytes;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
});

const durationLabel = computed(() => {
  const ms = props.asset.media_duration_ms;
  if (ms === null || ms < 0) return null;
  const totalSeconds = Math.round(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const mm = String(minutes).padStart(2, "0");
  const ss = String(seconds).padStart(2, "0");
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
});

function clear(): void {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value);
    objectUrl.value = null;
  }
}

async function loadThumbnail(): Promise<void> {
  clear();
  const type = props.asset.asset_type;
  const fetchable =
    type === "image" || type === "video" || (type === "audio" && props.asset.thumbnail_status === "ready");
  if (!fetchable) return;
  const token = ++loadToken;
  try {
    const url = await api.fetchThumbnailObjectUrl(props.asset.id);
    if (token !== loadToken) {
      URL.revokeObjectURL(url); // a newer load superseded this one
      return;
    }
    objectUrl.value = url;
  } catch {
    // generation pending or failed: keep the type icon fallback
  }
}

watch(
  () => [props.asset.id, props.asset.thumbnail_status],
  () => void loadThumbnail(),
  { immediate: true }
);

onUnmounted(clear);
</script>

<template>
  <div
    class="group overflow-hidden rounded-2xl border bg-white transition-all select-none"
    :class="[
      selectionActive ? 'cursor-pointer hover:border-accent/60' : 'cursor-zoom-in hover:shadow-soft',
      selected
        ? 'border-accent ring-2 ring-accent/30 bg-accent/[0.02] shadow-xs'
        : 'border-line'
    ]"
    role="button"
    tabindex="0"
    @click="onCardClick"
    @dblclick="onCardDblClick"
    @keydown.enter="onCardClick"
    @keydown.space.prevent="emit('open', asset)"
  >
    <div class="relative flex aspect-square items-center justify-center overflow-hidden bg-canvas">
      <!-- 左上角大感应触控区（44×44px，覆盖整个左上边缘，彻底解决小靶心误触问题） -->
      <button
        type="button"
        class="group/chk absolute left-0 top-0 z-20 flex h-11 w-11 items-start justify-start p-2 text-[11px] transition"
        :title="selected ? '取消选择 (按住 Shift 可范围多选)' : '选择 (按住 Shift 可范围多选)'"
        @click.stop="onCheckboxClick"
      >
        <div
          class="flex h-5 w-5 items-center justify-center rounded border transition-all duration-150 shadow-xs"
          :class="
            selected
              ? 'border-accent bg-accent text-white scale-105'
              : 'border-line bg-white/90 text-transparent hover:border-accent group-hover/chk:border-accent group-hover/chk:text-muted/60 group-hover:text-muted/60'
          "
        >
          <svg
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="h-3.5 w-3.5 transition-opacity"
            :class="selected ? 'opacity-100 text-white' : 'opacity-0 group-hover/chk:opacity-100 group-hover:opacity-100'"
            aria-hidden="true"
          >
            <path d="M3.5 8.5 6.5 11.5 12.5 4.5" />
          </svg>
        </div>
      </button>
      <img
        v-if="objectUrl"
        :src="objectUrl"
        class="h-full w-full object-contain"
        alt=""
      />
      <AssetIcon v-else :type="asset.asset_type" class="h-12 w-12 text-muted/70" />
      <span
        v-if="durationLabel"
        class="absolute bottom-1.5 right-1.5 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[10px] leading-none text-white"
      >{{ durationLabel }}</span>
      <span
        v-if="asset.source_type === 'external'"
        class="absolute right-2 top-2 rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 shadow-xs"
      >外部链接</span>
      <span
        v-if="asset.status === 'missing'"
        class="absolute bottom-1.5 left-2 rounded bg-rose-600/90 px-1.5 py-0.5 text-[10px] font-medium text-white"
        title="源文件缺失，重新扫描外部目录可检测恢复"
      >失效</span>
      <button
        v-if="canUsePrompt"
        class="absolute bottom-1.5 left-1.5 hidden rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-medium text-accent group-hover:block"
        :title="asset.has_prompt ? '查看提示词' : '添加提示词'"
        @click.stop="emit('prompt', asset)"
      >{{ asset.has_prompt ? "查看提示词" : "+ 提示词" }}</button>
    </div>
    <div class="px-3 py-2.5">
      <p class="truncate text-sm font-medium" :title="asset.name">{{ asset.name }}</p>
      <div class="mt-1 flex items-center gap-1.5 text-xs text-muted">
        <span>{{ typeLabel }}</span>
        <span>·</span>
        <span>{{ sizeLabel }}</span>
      </div>
      <div v-if="asset.tags.length > 0" class="mt-1.5 flex flex-wrap gap-1">
        <span
          v-for="tag in asset.tags.slice(0, 2)"
          :key="tag.id"
          class="max-w-[80px] truncate rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent"
          :title="tag.name"
        >{{ tag.name }}</span>
        <span v-if="asset.tags.length > 2" class="rounded bg-canvas px-1.5 py-0.5 text-[10px] text-muted">+{{ asset.tags.length - 2 }}</span>
      </div>
    </div>
  </div>
</template>
