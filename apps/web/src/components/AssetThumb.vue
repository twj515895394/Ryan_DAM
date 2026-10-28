<script setup lang="ts">
import { useThumbnailObjectUrl } from "../composables/useThumbnailCache";
import AssetIcon from "./AssetIcon.vue";

const props = withDefaults(
  defineProps<{
    assetId: number;
    assetType?: string;
    thumbnailStatus?: string | null;
    hoverZoom?: boolean;
  }>(),
  {
    assetType: "image",
    thumbnailStatus: undefined,
    hoverZoom: false
  }
);

const objectUrl = useThumbnailObjectUrl(
  () => props.assetId,
  () => props.assetType,
  () => props.thumbnailStatus
);
</script>

<template>
  <div class="relative flex h-full w-full items-center justify-center overflow-hidden bg-canvas">
    <img
      v-if="objectUrl"
      :src="objectUrl"
      class="h-full w-full object-cover transition duration-150"
      :class="hoverZoom ? 'group-hover:scale-105' : ''"
      alt=""
    />
    <AssetIcon v-else :type="assetType" class="h-8 w-8 text-muted/60" />
  </div>
</template>
