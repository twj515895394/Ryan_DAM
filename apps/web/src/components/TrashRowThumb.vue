<script setup lang="ts">
import { useThumbnailObjectUrl } from "../composables/useThumbnailCache";
import AssetIcon from "./AssetIcon.vue";

const props = defineProps<{
  assetId: number;
  assetType: string;
  thumbnailStatus?: string | null;
}>();

const objectUrl = useThumbnailObjectUrl(
  () => props.assetId,
  () => props.assetType,
  () => props.thumbnailStatus
);
</script>

<template>
  <div class="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-canvas ring-1 ring-line/60">
    <img v-if="objectUrl" :src="objectUrl" class="h-full w-full object-contain" alt="" />
    <AssetIcon v-else :type="assetType" class="h-5 w-5 text-muted/70" />
  </div>
</template>
