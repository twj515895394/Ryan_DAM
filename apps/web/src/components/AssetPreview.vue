<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import { api } from "../api/client";
import AssetIcon from "./AssetIcon.vue";
import AssetTagEditor from "./AssetTagEditor.vue";
import ConfirmDialog from "./ConfirmDialog.vue";
import PromptModal from "./PromptModal.vue";
import { renderMarkdown } from "../utils/markdown";
import type { AssetOut, TrashItem } from "../api/types";
import type { ConfirmIntent } from "./ConfirmDialog.vue";
import type { MoveFolderGroup } from "../composables/useFolderOptions";

const props = withDefaults(
  defineProps<{
    asset: AssetOut;
    moveOptions?: { id: number; label: string }[];
    moveGroups?: MoveFolderGroup[];
    autoOpenPrompt: boolean;
    trashMode?: boolean;
    trashMeta?: TrashItem | null;
  }>(),
  { trashMode: false, trashMeta: null }
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "prev"): void;
  (e: "next"): void;
  (e: "delete", assetId: number): void;
  (e: "rename", assetId: number): void;
  (e: "move", assetId: number, folderId: number): void;
  (e: "convert", assetId: number): void;
  (e: "prompt-opened"): void;
  (e: "restore", assetId: number): void;
  (e: "permanent-delete", assetId: number): void;
}>();

const objectUrl = ref<string | null>(null);
const contentText = ref<string | null>(null);
const loading = ref(false);
const errorMessage = ref("");
const playbackFailed = ref(false);
const fitWindow = ref(true);
let loadToken = 0;

const TEXT_PREVIEW_EXTS = new Set(["txt", "md", "json", "csv"]);
const OFFICE_EXTS = new Set(["doc", "docx", "xls", "xlsx", "ppt", "pptx"]);

const docKind = computed<"none" | "pdf" | "text" | "office" | "other">(() => {
  const ext = (props.asset.extension ?? "").toLowerCase();
  if (props.asset.asset_type !== "document") return "none";
  if (ext === "pdf") return "pdf";
  if (TEXT_PREVIEW_EXTS.has(ext)) return "text";
  if (OFFICE_EXTS.has(ext)) return "office";
  return "other";
});

const textPreview = computed(() => {
  if (contentText.value === null) return null;
  const ext = (props.asset.extension ?? "").toLowerCase();
  const raw = contentText.value;
  if (ext === "json") {
    try {
      return { kind: "json" as const, body: JSON.stringify(JSON.parse(raw), null, 2) };
    } catch {
      return { kind: "plain" as const, body: raw };
    }
  }
  if (ext === "csv") return { kind: "csv" as const, body: raw };
  if (ext === "md") return { kind: "md" as const, body: raw };
  return { kind: "plain" as const, body: raw };
});

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

/** 回收站预览：删除时间来自 TrashItem.deleted_at（UTC 无时区后缀，补 Z 再本地化）。 */
const deletedAtLabel = computed(() => {
  const raw = props.trashMeta?.deleted_at;
  if (!raw) return "—";
  const date = new Date(raw + (raw.endsWith("Z") ? "" : "Z"));
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString("zh-CN", { hour12: false });
});

interface PreviewConfirmState {
  title: string;
  description: string;
  confirmText: string;
  intent: ConfirmIntent;
  action: () => void;
}

const confirmDialog = ref<PreviewConfirmState | null>(null);

function askDelete(): void {
  const isExternal = props.asset.source_type === "external";
  if (isExternal) {
    confirmDialog.value = {
      title: "从资产库移除资产？",
      description: `确定从资产库移除「${props.asset.name}」吗？\n只删除索引记录，不会删除磁盘上的源文件。`,
      confirmText: "移除索引",
      intent: "warning",
      action: () => emit("delete", props.asset.id)
    };
  } else {
    confirmDialog.value = {
      title: "移入回收站？",
      description: `确定把「${props.asset.name}」移入回收站吗？\n之后可以在回收站中随时恢复或永久删除。`,
      confirmText: "移入回收站",
      intent: "danger",
      action: () => emit("delete", props.asset.id)
    };
  }
}

const moveTargetId = ref<number | null>(null);
watch(
  () => props.asset.id,
  () => {
    moveTargetId.value = null;
    confirmDialog.value = null;
  }
);

function confirmMove(): void {
  if (moveTargetId.value === null) return;
  emit("move", props.asset.id, moveTargetId.value);
}

function askConvert(): void {
  confirmDialog.value = {
    title: "转为系统托管存储？",
    description: `确定把「${props.asset.name}」转为系统托管吗？\n\n文件将复制到托管存储并就地更新资产记录（保留目录与标签），原外部文件不会被删除。`,
    confirmText: "转为托管",
    intent: "default",
    action: () => emit("convert", props.asset.id)
  };
}

// ── 提示词 ────────────────────────────────────────────────────
const promptModalOpen = ref(false);
const canUsePrompt = computed(() => props.asset.asset_type === "image" || props.asset.asset_type === "video");

watch(
  () => props.asset.id,
  () => {
    promptModalOpen.value = false;
  }
);

watch(
  () => props.autoOpenPrompt,
  (value) => {
    if (value && canUsePrompt.value) {
      promptModalOpen.value = true;
      emit("prompt-opened");
    }
  },
  { immediate: true }
);

function onPromptSaved(hasPrompt: boolean): void {
  props.asset.has_prompt = hasPrompt;
}

function clearContent(): void {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value);
    objectUrl.value = null;
  }
  contentText.value = null;
}

async function loadContent(): Promise<void> {
  clearContent();
  errorMessage.value = "";
  playbackFailed.value = false;
  loading.value = true;
  fitWindow.value = true;
  const token = ++loadToken;
  const wantText = docKind.value === "text";
  try {
    if (wantText) {
      const text = await api.fetchContentText(props.asset.id);
      if (token !== loadToken) return;
      // guard against multi-megabyte documents freezing the UI
      contentText.value = text.length > 2_000_000 ? text.slice(0, 2_000_000) + "\n\n…（文件过大，已截断显示）" : text;
    } else {
      const url = await api.fetchContentObjectUrl(props.asset.id);
      if (token !== loadToken) {
        URL.revokeObjectURL(url);
        return;
      }
      objectUrl.value = url;
    }
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
    if (promptModalOpen.value) {
      // Esc 只关最上层的提示词弹窗，不连预览一起关
      promptModalOpen.value = false;
      return;
    }
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
          <iframe
            v-else-if="objectUrl && docKind === 'pdf'"
            :src="objectUrl"
            class="h-full w-full rounded-xl bg-white"
            title="PDF 预览"
          />
          <div
            v-else-if="docKind === 'text' && textPreview"
            class="h-full w-full overflow-auto rounded-xl bg-white p-6"
          >
            <table v-if="textPreview.kind === 'csv'" class="w-full border-collapse text-xs">
              <tbody>
                <tr v-for="(row, ri) in textPreview.body.split(/\r?\n/).slice(0, 500)" :key="ri" class="border-b border-line">
                  <td
                    v-for="(cell, ci) in row.split(',')"
                    :key="ci"
                    class="border-r border-line px-2.5 py-1.5 align-top"
                    :class="ri === 0 ? 'font-semibold' : ''"
                  >{{ cell }}</td>
                </tr>
              </tbody>
            </table>
            <pre v-else-if="textPreview.kind === 'json'" class="whitespace-pre-wrap break-all font-mono text-xs leading-6">{{ textPreview.body }}</pre>
            <pre v-else-if="textPreview.kind === 'plain'" class="whitespace-pre-wrap break-words text-sm leading-7">{{ textPreview.body }}</pre>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div v-else class="markdown-preview text-sm leading-7" v-html="renderMarkdown(textPreview.body)" />
          </div>
          <div
            v-else-if="docKind === 'office'"
            class="flex flex-col items-center gap-4 text-white/70"
          >
            <AssetIcon type="document" class="h-16 w-16" />
            <p class="text-sm">Office 文件不做在线预览，可调用系统默认应用打开</p>
            <button
              class="rounded-xl bg-white/15 px-4 py-2 text-sm text-white transition hover:bg-white/25"
              @click="openInSystemApp"
            >在系统默认应用中打开</button>
          </div>
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
            <div v-if="asset.status === 'missing'" class="flex justify-between gap-3">
              <dt class="shrink-0 text-muted">状态</dt>
              <dd class="text-right text-rose-600">失效（源文件缺失）</dd>
            </div>
            <div class="flex justify-between gap-3"><dt class="shrink-0 text-muted">大小</dt><dd>{{ sizeLabel }}</dd></div>
            <div class="flex justify-between gap-3"><dt class="shrink-0 text-muted">尺寸</dt><dd>{{ dimensionsLabel }}</dd></div>
            <div v-if="durationLabel" class="flex justify-between gap-3"><dt class="shrink-0 text-muted">时长</dt><dd>{{ durationLabel }}</dd></div>
            <div v-if="!trashMode" class="flex justify-between gap-3"><dt class="shrink-0 text-muted">修改时间</dt><dd class="text-right">{{ updatedAtLabel }}</dd></div>
          </dl>
          <!-- 标签编辑（内联搜索 + 即时新建打标）；回收站预览不提供打标 -->
          <AssetTagEditor v-if="!trashMode" :asset="asset" />
          <div v-if="!trashMode && (asset.source_type === 'managed' || (asset.source_type === 'external' && asset.status !== 'missing'))" class="mt-4 border-t border-line pt-3">
            <p class="text-xs font-medium text-muted">管理</p>
            <template v-if="asset.source_type === 'managed'">
              <button
                class="mt-2 w-full rounded-lg border border-line px-3 py-2 text-xs font-medium text-ink transition hover:bg-canvas"
                @click="emit('rename', asset.id)"
              >重命名</button>
              <div class="mt-1.5 flex gap-1.5">
                <select
                  v-model="moveTargetId"
                  class="min-w-0 flex-1 rounded-lg border border-line bg-white px-2 py-1.5 text-xs outline-none focus:border-accent"
                >
                  <option :value="null">移动到…</option>
                  <template v-if="moveGroups && moveGroups.length > 0">
                    <optgroup
                      v-for="group in moveGroups"
                      :key="group.id"
                      :label="group.label"
                    >
                      <option
                        v-for="option in group.options"
                        :key="option.id"
                        :value="option.id"
                      >
                        {{ option.label }}
                      </option>
                    </optgroup>
                  </template>
                  <template v-else-if="moveOptions">
                    <option v-for="option in moveOptions" :key="option.id" :value="option.id">{{ option.label }}</option>
                  </template>
                </select>
                <button
                  class="shrink-0 rounded-lg bg-accent px-2.5 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:opacity-40"
                  :disabled="moveTargetId === null"
                  @click="confirmMove"
                >移动</button>
              </div>
            </template>
            <button
              v-else
              class="mt-2 w-full rounded-lg border border-amber-200 px-3 py-2 text-xs font-medium text-amber-700 transition hover:bg-amber-50"
              @click="askConvert"
            >转为系统托管</button>
          </div>
          <div v-if="canUsePrompt && !trashMode" class="mt-4 border-t border-line pt-3">
            <p class="text-xs font-medium text-muted">提示词</p>
            <button
              class="mt-2 w-full rounded-lg border border-line px-3 py-2 text-xs font-medium text-ink transition hover:bg-canvas"
              @click="promptModalOpen = true"
            >{{ asset.has_prompt ? "查看提示词" : "添加提示词" }}</button>
          </div>
          <!-- 回收站上下文：原目录与删除时间（回收站项不提供路径与常规管理） -->
          <div v-if="trashMode && trashMeta" class="mt-4 border-t border-line pt-3">
            <p class="text-xs font-medium text-muted">回收站</p>
            <dl class="mt-2 space-y-3 text-xs">
              <div class="flex justify-between gap-3">
                <dt class="shrink-0 text-muted">原目录</dt>
                <dd class="truncate text-right" :title="trashMeta.original_folder">{{ trashMeta.original_folder }}</dd>
              </div>
              <div class="flex justify-between gap-3"><dt class="shrink-0 text-muted">删除时间</dt><dd class="text-right">{{ deletedAtLabel }}</dd></div>
            </dl>
          </div>
          <div v-if="!trashMode" class="mt-4 border-t border-line pt-3">
            <p class="text-xs text-muted">路径</p>
            <p class="mt-1 break-all font-mono text-[11px] leading-5 text-muted" :title="asset.file_path">{{ asset.file_path }}</p>
          </div>
          <div class="mt-4 border-t border-line pt-3">
            <template v-if="trashMode">
              <button
                class="flex min-h-11 w-full items-center justify-center gap-1.5 rounded-xl bg-accent px-3 text-sm font-medium text-white shadow-sm transition duration-100 hover:bg-blue-700 active:scale-[0.98]"
                @click="emit('restore', asset.id)"
              >恢复到原目录</button>
              <button
                class="mt-2 flex min-h-11 w-full items-center justify-center gap-1.5 rounded-xl border border-rose-200 px-3 text-sm font-medium text-rose-600 transition duration-100 hover:bg-rose-50 active:scale-[0.98]"
                @click="emit('permanent-delete', asset.id)"
              >永久删除</button>
            </template>
            <button
              v-else
              class="w-full rounded-lg border border-rose-200 px-3 py-2 text-xs font-medium text-rose-600 transition hover:bg-rose-50"
              @click="askDelete"
            >{{ asset.source_type === "external" ? "从库中移除（不删源文件）" : "删除到回收站" }}</button>
          </div>
        </aside>
      </div>
    </div>

    <PromptModal
      :open="promptModalOpen"
      :asset-id="asset.id"
      :asset-name="asset.name"
      :has-prompt="asset.has_prompt"
      @close="promptModalOpen = false"
      @saved="onPromptSaved"
    />

    <ConfirmDialog
      :open="confirmDialog !== null"
      :title="confirmDialog?.title ?? ''"
      :description="confirmDialog?.description"
      :confirm-text="confirmDialog?.confirmText"
      :intent="confirmDialog?.intent ?? 'default'"
      @confirm="() => { const action = confirmDialog?.action; confirmDialog = null; action?.(); }"
      @cancel="confirmDialog = null"
    />
  </Teleport>
</template>
