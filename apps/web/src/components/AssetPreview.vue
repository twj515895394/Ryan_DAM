<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import { api } from "../api/client";
import AssetIcon from "./AssetIcon.vue";
import type { AssetOut } from "../api/types";

const props = defineProps<{ asset: AssetOut }>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "prev"): void;
  (e: "next"): void;
}>();

const objectUrl = ref<string | null>(null);
const loading = ref(false);
const errorMessage = ref("");
const playbackFailed = ref(false);
const fitWindow = ref(true);
let loadToken = 0;

async function openInSystemApp(): Promise<void> {
  try {
    await api.openExternal(props.asset.id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "调用系统应用失败";
  }
}

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

const dimensionsLabel = computed(() =>
  props.asset.media_width && props.asset.media_height
    ? `${props.asset.media_width} × ${props.asset.media_height}`
    : "—"
);

const durationLabel = computed(() => {
  const ms = props.asset.media_duration_ms;
  if (ms === null || ms < 0) return null;
  const total = Math.round(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return h > 0 ? `${h}:${m}:${s}` : `${m}:${s}`;
});

const updatedAtLabel = computed(() => {
  if (!props.asset.updated_at) return "—";
  const date = new Date(props.asset.updated_at + (props.asset.updated_at.endsWith("Z") ? "" : "Z"));
  if (Number.isNaN(date.getTime())) return props.asset.updated_at;
  return date.toLocaleString("zh-CN", { hour12: false });
});

function clearContent(): void {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value);
    objectUrl.value = null;
  }
}

async function loadContent(): Promise<void> {
  clearContent();
  errorMessage.value = "";
  playbackFailed.value = false;
  loading.value = true;
  fitWindow.value = true;
  const token = ++loadToken;
  try {
    const url = await api.fetchContentObjectUrl(props.asset.id);
    if (token !== loadToken) {
      URL.revokeObjectURL(url);
      return;
    }
    objectUrl.value = url;
  } catch (error) {
    if (token === loadToken) {
      errorMessage.value = error instanceof Error ? error.message : "内容加载失败";
    }
  } finally {
    if (token === loadToken) loading.value = false;
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    emit("close");
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    emit("prev");
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    emit("next");
  }
}

window.addEventListener("keydown", onKeydown);
watch(() => props.asset.id, loadContent, { immediate: true });
onUnmounted(() => {
  window.removeEventListener("keydown", onKeydown);
  clearContent();
});
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-40 flex flex-col bg-[#16161a]/95 backdrop-blur-sm" @click.self="emit('close')">
      <header class="flex h-14 shrink-0 items-center justify-between px-5 text-white">
        <div class="flex min-w-0 items-center gap-3">
          <button
            class="rounded-lg bg-white/10 px-3 py-1.5 text-sm transition hover:bg-white/20"
            @click="emit('close')"
          >关闭 (Esc)</button>
          <p class="truncate text-sm font-medium" :title="asset.name">{{ asset.name }}</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            v-if="asset.asset_type === 'image'"
            class="rounded-lg bg-white/10 px-3 py-1.5 text-sm transition hover:bg-white/20"
            @click="fitWindow = !fitWindow"
          >{{ fitWindow ? "原始尺寸" : "适应窗口" }}</button>
          <button
            class="rounded-lg bg-white/10 px-3 py-1.5 text-sm transition hover:bg-white/20"
            @click="emit('prev')"
          >← 上一项</button>
          <button
            class="rounded-lg bg-white/10 px-3 py-1.5 text-sm transition hover:bg-white/20"
            @click="emit('next')"
          >下一项 →</button>
        </div>
      </header>

      <div class="flex min-h-0 flex-1 gap-0 px-5 pb-5">
        <div class="relative flex min-w-0 flex-1 items-center justify-center overflow-auto rounded-2xl bg-black/40">
          <p v-if="loading" class="text-sm text-white/70">正在加载…</p>
          <p v-else-if="errorMessage" class="rounded-xl bg-rose-500/20 px-4 py-2.5 text-sm text-rose-100">
            {{ errorMessage }}
          </p>
          <img
            v-else-if="objectUrl && asset.asset_type === 'image'"
            :src="objectUrl"
            :class="fitWindow ? 'max-h-full max-w-full object-contain' : 'max-w-none'"
            class="select-none"
            alt=""
          />
          <video
            v-else-if="objectUrl && asset.asset_type === 'video' && !playbackFailed"
            :src="objectUrl"
            class="max-h-full max-w-full"
            controls
            @error="playbackFailed = true"
          />
          <div
            v-else-if="objectUrl && asset.asset_type === 'audio' && !playbackFailed"
            class="flex w-full max-w-md flex-col items-center gap-6 px-6"
          >
            <AssetIcon type="audio" class="h-24 w-24 text-white/60" />
            <audio :src="objectUrl" class="w-full" controls @error="playbackFailed = true" />
          </div>
          <div v-else-if="objectUrl" class="flex flex-col items-center gap-4 text-white/70">
            <span class="text-4xl">⚠️</span>
            <p class="text-sm">浏览器无法直接播放该格式</p>
            <button
              class="rounded-xl bg-white/15 px-4 py-2 text-sm text-white transition hover:bg-white/25"
              @click="openInSystemApp"
            >在系统默认应用中打开</button>
          </div>
          <div v-else class="flex flex-col items-center gap-3 text-white/70">
            <span class="text-4xl">{{ asset.asset_type === 'audio' ? '🎵' : asset.asset_type === 'video' ? '🎬' : '📄' }}</span>
            <p class="text-sm">该类型预览将在后续阶段接入</p>
          </div>
        </div>

        <aside class="ml-4 flex w-72 shrink-0 flex-col overflow-y-auto rounded-2xl bg-white p-5">
          <p class="break-all text-sm font-semibold leading-6">{{ asset.name }}</p>
          <dl class="mt-4 space-y-3 text-xs">
            <div class="flex justify-between gap-3"><dt class="shrink-0 text-muted">类型</dt><dd>{{ typeLabel }}</dd></div>
            <div class="flex justify-between gap-3"><dt class="shrink-0 text-muted">来源</dt>
              <dd :class="asset.source_type === 'external' ? 'text-amber-700' : ''">
                {{ asset.source_type === 'external' ? '外部链接' : '系统托管' }}
              </dd>
            </div>
            <div class="flex justify-between gap-3"><dt class="shrink-0 text-muted">大小</dt><dd>{{ sizeLabel }}</dd></div>
            <div class="flex justify-between gap-3"><dt class="shrink-0 text-muted">尺寸</dt><dd>{{ dimensionsLabel }}</dd></div>
            <div v-if="durationLabel" class="flex justify-between gap-3"><dt class="shrink-0 text-muted">时长</dt><dd>{{ durationLabel }}</dd></div>
            <div class="flex justify-between gap-3"><dt class="shrink-0 text-muted">修改时间</dt><dd class="text-right">{{ updatedAtLabel }}</dd></div>
          </dl>
          <div class="mt-4 border-t border-line pt-3">
            <p class="text-xs text-muted">路径</p>
            <p class="mt-1 break-all font-mono text-[11px] leading-5 text-muted" :title="asset.file_path">{{ asset.file_path }}</p>
          </div>
        </aside>
      </div>
    </div>
  </Teleport>
</template>
