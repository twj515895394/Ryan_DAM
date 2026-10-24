<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import { api } from "../api/client";
import AssetIcon from "./AssetIcon.vue";
import type { AssetOut } from "../api/types";

const props = defineProps<{ asset: AssetOut }>();

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

function clear(): void {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value);
    objectUrl.value = null;
  }
}

async function loadThumbnail(): Promise<void> {
  clear();
  if (props.asset.asset_type !== "image") return;
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
  <div class="group overflow-hidden rounded-2xl border border-line bg-white transition-shadow hover:shadow-soft">
    <div class="relative flex aspect-square items-center justify-center overflow-hidden bg-canvas">
      <img
        v-if="objectUrl"
        :src="objectUrl"
        class="h-full w-full object-contain"
        alt=""
      />
      <AssetIcon v-else :type="asset.asset_type" class="h-12 w-12 text-muted/70" />
      <span
        v-if="asset.source_type === 'external'"
        class="absolute left-2 top-2 rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-medium text-amber-700"
      >外部链接</span>
    </div>
    <div class="px-3 py-2.5">
      <p class="truncate text-sm font-medium" :title="asset.name">{{ asset.name }}</p>
      <div class="mt-1 flex items-center gap-1.5 text-xs text-muted">
        <span>{{ typeLabel }}</span>
        <span>·</span>
        <span>{{ sizeLabel }}</span>
      </div>
    </div>
  </div>
</template>
