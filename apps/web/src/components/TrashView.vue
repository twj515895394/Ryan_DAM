<script setup lang="ts">
import AssetIcon from "./AssetIcon.vue";
import TrashRowThumb from "./TrashRowThumb.vue";
import { library } from "../stores/library";
import type { TrashItem } from "../api/types";

const emit = defineEmits<{
  (e: "preview", item: TrashItem): void;
  (e: "restore", item: TrashItem): void;
  (e: "delete", item: TrashItem): void;
  (e: "empty"): void;
}>();

const ASSET_TYPE_LABELS: Record<string, string> = {
  image: "图片",
  video: "视频",
  audio: "音频",
  document: "文档",
  other: "其他"
};

function trashTypeLabel(type: string): string {
  return ASSET_TYPE_LABELS[type] ?? type;
}

function trashSizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function trashDateLabel(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value + (value.endsWith("Z") ? "" : "Z"));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}
</script>

<template>
  <main class="min-h-0 flex-1 overflow-y-auto px-8 pb-10 pt-6">
    <div
      v-if="library.trash.length > 0"
      class="overflow-hidden rounded-2xl border border-line bg-white shadow-xs"
    >
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-line bg-canvas/60 text-left text-xs text-muted">
            <th class="px-4 py-2.5 font-medium">名称</th>
            <th class="px-4 py-2.5 font-medium">类型</th>
            <th class="px-4 py-2.5 font-medium">大小</th>
            <th class="px-4 py-2.5 font-medium">删除时间</th>
            <th class="px-4 py-2.5 font-medium">原目录</th>
            <th class="px-4 py-2.5 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in library.trash"
            :key="item.id"
            class="cursor-pointer border-b border-line transition-colors duration-100 last:border-b-0 hover:bg-canvas/60 active:bg-canvas/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/40"
            role="button"
            tabindex="0"
            title="单击打开沉浸式预览"
            @click="emit('preview', item)"
            @keydown.enter.prevent="emit('preview', item)"
          >
            <td class="max-w-[320px] px-4 py-2.5">
              <div class="flex items-center gap-3">
                <TrashRowThumb
                  :asset-id="item.id"
                  :asset-type="item.asset_type"
                  :thumbnail-status="item.thumbnail_status"
                />
                <div class="flex min-w-0 items-center gap-2">
                  <span class="truncate" :title="item.name">{{ item.name }}</span>
                  <span
                    v-if="item.source_type === 'external'"
                    class="shrink-0 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700"
                  >
                    外部
                  </span>
                </div>
              </div>
            </td>
            <td class="px-4 py-2.5 text-muted">{{ trashTypeLabel(item.asset_type) }}</td>
            <td class="px-4 py-2.5 text-muted">{{ trashSizeLabel(item.size_bytes) }}</td>
            <td class="px-4 py-2.5 text-muted">{{ trashDateLabel(item.deleted_at) }}</td>
            <td class="max-w-[180px] truncate px-4 py-2.5 text-muted" :title="item.original_folder">
              {{ item.original_folder }}
            </td>
            <td class="whitespace-nowrap px-4 py-2.5 text-right">
              <button
                type="button"
                class="min-h-9 rounded-lg px-3 py-1.5 text-xs font-medium text-accent transition duration-100 hover:bg-accent/10 active:scale-[0.97]"
                @click.stop="emit('restore', item)"
              >
                恢复
              </button>
              <button
                type="button"
                class="ml-1 min-h-9 rounded-lg px-3 py-1.5 text-xs font-medium text-rose-600 transition duration-100 hover:bg-rose-50 active:scale-[0.97]"
                @click.stop="emit('delete', item)"
              >
                永久删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="flex min-h-full items-center justify-center">
      <div class="w-full max-w-md rounded-3xl border border-line bg-white p-10 text-center shadow-sm">
        <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-canvas text-muted/70">
          <AssetIcon type="other" class="h-7 w-7" />
        </div>
        <h2 class="mt-5 text-base font-semibold text-ink">回收站是空的</h2>
        <p class="mt-2 text-sm leading-6 text-muted">
          删除的托管资产会保留在这里，可随时恢复到原目录；「永久删除」和「清空回收站」才会真正从磁盘移除文件。
        </p>
      </div>
    </div>
  </main>
</template>
