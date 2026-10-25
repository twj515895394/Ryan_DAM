<script setup lang="ts">
import { ref } from "vue";
import AssetCard from "./AssetCard.vue";
import AssetIcon from "./AssetIcon.vue";
import type { AssetPage } from "../api/types";

const props = defineProps<{
  assets: AssetPage | null;
  selectedAssetIds: number[];
  loaded: boolean;
}>();

const emit = defineEmits<{
  (e: "open", assetId: number): void;
  (e: "toggle-select", asset: { id: number }, event?: MouseEvent): void;
  (e: "prompt", asset: { id: number }): void;
  (e: "load-more"): void;
}>();

const galleryScroll = ref<HTMLElement | null>(null);

defineExpose({
  getScrollTop: () => galleryScroll.value?.scrollTop ?? 0,
  setScrollTop: (val: number) => {
    if (galleryScroll.value) galleryScroll.value.scrollTop = val;
  }
});
</script>

<template>
  <main ref="galleryScroll" class="min-h-0 flex-1 overflow-y-auto px-8 pb-10 pt-6">
    <div
      v-if="assets && assets.items.length > 0"
      class="grid gap-4"
      style="grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))"
    >
      <AssetCard
        v-for="asset in assets.items"
        :key="asset.id"
        :asset="asset"
        :selected="selectedAssetIds.includes(asset.id)"
        :selection-active="selectedAssetIds.length > 0"
        @open="emit('open', asset.id)"
        @toggle-select="(selectedAsset, ev) => emit('toggle-select', selectedAsset, ev)"
        @prompt="emit('prompt', $event)"
      />
    </div>

    <!-- 加载更多按钮 -->
    <div v-if="assets && assets.items.length < assets.total" class="mt-6 flex justify-center">
      <button
        class="rounded-xl border border-line bg-white px-5 py-2.5 text-sm font-medium transition hover:bg-canvas text-ink"
        @click="emit('load-more')"
      >
        加载更多（已显示 {{ assets.items.length }} / {{ assets.total }}）
      </button>
    </div>

    <!-- 空状态提示 -->
    <div v-if="!assets || assets.items.length === 0" class="flex min-h-full items-center justify-center">
      <div class="w-full max-w-md rounded-3xl border border-line bg-white p-10 text-center shadow-sm">
        <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-canvas text-muted/70">
          <AssetIcon type="other" class="h-7 w-7" />
        </div>
        <h2 class="mt-5 text-base font-semibold text-ink">
          {{ !loaded ? "正在连接本地服务…" : assets === null ? "加载失败" : "此目录还没有资产" }}
        </h2>
        <p class="mt-2 text-sm leading-6 text-muted">
          {{ loaded
            ? "选中左侧目录后，通过顶部「导入文件」将文件复制进托管存储；支持缩略图与多端预览。"
            : "如果长时间未连接，请检查本地服务是否正常启动。" }}
        </p>
      </div>
    </div>
  </main>
</template>
