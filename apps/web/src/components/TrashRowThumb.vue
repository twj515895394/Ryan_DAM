<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";

import { api } from "../api/client";
import AssetIcon from "./AssetIcon.vue";

const props = defineProps<{
  assetId: number;
  assetType: string;
  thumbnailStatus?: string | null;
}>();

const objectUrl = ref<string | null>(null);
let loadToken = 0;

function clear(): void {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value);
    objectUrl.value = null;
  }
}

async function loadThumbnail(): Promise<void> {
  clear();
  const type = props.assetType;
  const fetchable =
    type === "image" || type === "video" || (type === "audio" && props.thumbnailStatus === "ready");
  if (!fetchable) return;
  const token = ++loadToken;
  try {
    const url = await api.fetchThumbnailObjectUrl(props.assetId);
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
  () => [props.assetId, props.thumbnailStatus],
  () => void loadThumbnail(),
  { immediate: true }
);

onUnmounted(clear);
</script>

<template>
  <div class="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-canvas ring-1 ring-line/60">
    <img v-if="objectUrl" :src="objectUrl" class="h-full w-full object-contain" alt="" />
    <AssetIcon v-else :type="assetType" class="h-5 w-5 text-muted/70" />
  </div>
</template>
