<script setup lang="ts">
import { computed } from "vue";

import type { AssetOut } from "../api/types";

const props = defineProps<{ asset: AssetOut }>();

const typeIcon = computed(() => {
  switch (props.asset.asset_type) {
    case "image": return "🖼️";
    case "video": return "🎬";
    case "audio": return "🎵";
    case "document": return "📄";
    default: return "📦";
  }
});

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
</script>

<template>
  <div class="group overflow-hidden rounded-2xl border border-line bg-white transition-shadow hover:shadow-soft">
    <div class="flex aspect-square items-center justify-center bg-canvas">
      <span class="text-4xl opacity-80">{{ typeIcon }}</span>
    </div>
    <div class="px-3 py-2.5">
      <p class="truncate text-sm font-medium" :title="asset.name">{{ asset.name }}</p>
      <div class="mt-1 flex items-center gap-1.5 text-xs text-muted">
        <span>{{ typeLabel }}</span>
        <span>·</span>
        <span>{{ sizeLabel }}</span>
        <span
          v-if="asset.source_type === 'external'"
          class="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700"
        >外部链接</span>
      </div>
    </div>
  </div>
</template>
