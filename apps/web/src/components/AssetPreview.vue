<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import { api } from "../api/client";
import AssetIcon from "./AssetIcon.vue";
import { library } from "../stores/library";
import type { AssetOut } from "../api/types";

const props = defineProps<{ asset: AssetOut; moveOptions: { id: number; label: string }[]; autoOpenPrompt: boolean }>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "prev"): void;
  (e: "next"): void;
  (e: "delete", assetId: number): void;
  (e: "rename", assetId: number): void;
  (e: "move", assetId: number, folderId: number): void;
  (e: "convert", assetId: number): void;
  (e: "prompt-opened"): void;
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

const selectedTagId = ref<number | null>(null);

const availableTags = computed(() =>
  library.tags.filter((tag) => !props.asset.tags.some((t) => t.id === tag.id))
);

async function addTag(): Promise<void> {
  if (selectedTagId.value === null) return;
  const next = props.asset.tags.map((t) => t.id);
  next.push(selectedTagId.value);
  if (await libraryUpdateTags(next)) selectedTagId.value = null;
}

async function removeTag(tagId: number): Promise<void> {
  await libraryUpdateTags(props.asset.tags.filter((t) => t.id !== tagId).map((t) => t.id));
}

async function libraryUpdateTags(tagIds: number[]): Promise<boolean> {
  try {
    await api.setAssetTags(props.asset.id, tagIds);
    // reflect locally; the gallery refresh happens via store on tag ops
    props.asset.tags = tagIds
      .map((id) => library.tags.find((t) => t.id === id))
      .filter((t): t is NonNullable<typeof t> => Boolean(t))
      .map((t) => ({ id: t.id, name: t.name, color: t.color }));
    return true;
  } catch {
    return false;
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

function askDelete(): void {
  const isExternal = props.asset.source_type === "external";
  const message = isExternal
    ? `确定从资产库移除「${props.asset.name}」吗？只删除索引记录，不会删除磁盘上的源文件。`
    : `确定把「${props.asset.name}」移入回收站吗？之后可以在回收站中恢复或永久删除。`;
  if (window.confirm(message)) emit("delete", props.asset.id);
}

const moveTargetId = ref<number | null>(null);
watch(
  () => props.asset.id,
  () => {
    moveTargetId.value = null;
  }
);

function confirmMove(): void {
  if (moveTargetId.value === null) return;
  emit("move", props.asset.id, moveTargetId.value);
}

function askConvert(): void {
  const message =
    `确定把「${props.asset.name}」转为系统托管吗？\n\n` +
    `文件将复制到托管存储并就地更新这条资产记录（保留目录与标签），外部源文件不会被删除。`;
  if (window.confirm(message)) emit("convert", props.asset.id);
}

// ── 提示词（票 20）────────────────────────────────────────────

const promptModalOpen = ref(false);
const promptLoading = ref(false);
const promptSaving = ref(false);
const promptEditing = ref(false);
const promptError = ref("");
const promptText = ref<string | null>(null);
const promptDraft = ref("");
const promptCopied = ref(false);
let promptCopyTimer: ReturnType<typeof setTimeout> | null = null;

const canUsePrompt = computed(() => props.asset.asset_type === "image" || props.asset.asset_type === "video");

watch(
  () => props.asset.id,
  () => {
    promptModalOpen.value = false;
    promptEditing.value = false;
    promptError.value = "";
    promptText.value = null;
  }
);

watch(
  () => props.autoOpenPrompt,
  (value) => {
    if (value && canUsePrompt.value) {
      void openPromptModal();
      emit("prompt-opened");
    }
  },
  { immediate: true }
);

async function openPromptModal(): Promise<void> {
  promptModalOpen.value = true;
  promptError.value = "";
  promptEditing.value = !props.asset.has_prompt;
  promptDraft.value = "";
  promptText.value = null;
  if (!props.asset.has_prompt) return;
  promptLoading.value = true;
  try {
    const result = await api.getAssetPrompt(props.asset.id);
    promptText.value = result.prompt_text ?? "";
  } catch (error) {
    promptError.value = error instanceof Error ? error.message : "提示词加载失败";
  } finally {
    promptLoading.value = false;
  }
}

function startPromptEdit(): void {
  promptDraft.value = promptText.value ?? "";
  promptEditing.value = true;
  promptError.value = "";
}

async function savePrompt(): Promise<void> {
  promptSaving.value = true;
  promptError.value = "";
  try {
    const result = await api.setAssetPrompt(props.asset.id, promptDraft.value || null);
    promptText.value = result.prompt_text;
    props.asset.has_prompt = result.has_prompt;
    promptEditing.value = false;
    if (!result.has_prompt) promptModalOpen.value = false;
  } catch (error) {
    // keep the draft and stay in edit mode so nothing the user typed is lost
    promptError.value = error instanceof Error ? error.message : "保存失败";
  } finally {
    promptSaving.value = false;
  }
}

async function copyPrompt(): Promise<void> {
  const text = promptText.value ?? "";
  try {
    await navigator.clipboard.writeText(text);
    promptCopied.value = true;
    if (promptCopyTimer) clearTimeout(promptCopyTimer);
    promptCopyTimer = setTimeout(() => {
      promptCopied.value = false;
    }, 2000);
  } catch {
    promptError.value = "复制失败，请手动选择文本复制。";
  }
}

function clearContent(): void {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value);
    objectUrl.value = null;
  }
  contentText.value = null;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarkdownInline(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, '<code class="rounded bg-canvas px-1 py-0.5 font-mono text-xs">$1</code>');
}

// Safe subset renderer: the whole source is HTML-escaped FIRST, so no markup
// can inject tags; links intentionally stay plain text (no remote loads).
function renderMarkdown(source: string): string {
  const escaped = escapeHtml(source);
  const out: string[] = [];
  let inCode = false;
  for (const line of escaped.split(/\r?\n/)) {
    if (line.trim().startsWith("```")) {
      out.push(inCode ? "</code></pre>" : '<pre class="overflow-x-auto rounded-xl bg-canvas p-3"><code>');
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      out.push(line);
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length + 1;
      out.push(`<h${level} class="mt-4 mb-2 font-semibold">` + renderMarkdownInline(heading[2]) + `</h${level}>`);
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      out.push('<li class="ml-5 list-disc">' + renderMarkdownInline(line.replace(/^\s*[-*]\s+/, "")) + "</li>");
      continue;
    }
    if (/^\s*&gt;\s?/.test(line)) {
      out.push('<blockquote class="border-l-2 border-line pl-3 text-muted">' + renderMarkdownInline(line.replace(/^\s*&gt;\s?/, "")) + "</blockquote>");
      continue;
    }
    if (!line.trim()) {
      out.push("<br>");
      continue;
    }
    out.push("<p>" + renderMarkdownInline(line) + "</p>");
  }
  if (inCode) out.push("</code></pre>");
  return out.join("\n");
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
            <div class="flex justify-between gap-3"><dt class="shrink-0 text-muted">修改时间</dt><dd class="text-right">{{ updatedAtLabel }}</dd></div>
          </dl>
          <div class="mt-4 border-t border-line pt-3">
            <p class="text-xs font-medium text-muted">标签</p>
            <div v-if="asset.tags.length > 0" class="mt-1.5 flex flex-wrap gap-1">
              <span
                v-for="tag in asset.tags"
                :key="tag.id"
                class="flex items-center gap-1 rounded bg-accent/10 px-2 py-0.5 text-xs text-accent"
              >
                {{ tag.name }}
                <button class="text-accent/60 hover:text-rose-600" title="移除标签" @click="removeTag(tag.id)">×</button>
              </span>
            </div>
            <p v-else class="mt-1 text-xs text-muted">暂无标签</p>
            <div class="mt-2 flex gap-1.5">
              <select
                v-model="selectedTagId"
                class="min-w-0 flex-1 rounded-lg border border-line bg-white px-2 py-1.5 text-xs outline-none focus:border-accent"
              >
                <option :value="null">添加标签…</option>
                <option v-for="tag in availableTags" :key="tag.id" :value="tag.id">{{ tag.name }}</option>
              </select>
              <button
                class="shrink-0 rounded-lg bg-accent px-2.5 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:opacity-40"
                :disabled="selectedTagId === null"
                @click="addTag"
              >添加</button>
            </div>
          </div>
          <div v-if="asset.source_type === 'managed' || (asset.source_type === 'external' && asset.status !== 'missing')" class="mt-4 border-t border-line pt-3">
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
                  <option v-for="option in moveOptions" :key="option.id" :value="option.id">{{ option.label }}</option>
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
          <div v-if="canUsePrompt" class="mt-4 border-t border-line pt-3">
            <p class="text-xs font-medium text-muted">提示词</p>
            <button
              class="mt-2 w-full rounded-lg border border-line px-3 py-2 text-xs font-medium text-ink transition hover:bg-canvas"
              @click="openPromptModal"
            >{{ asset.has_prompt ? "查看提示词" : "添加提示词" }}</button>
          </div>
          <div class="mt-4 border-t border-line pt-3">
            <p class="text-xs text-muted">路径</p>
            <p class="mt-1 break-all font-mono text-[11px] leading-5 text-muted" :title="asset.file_path">{{ asset.file_path }}</p>
          </div>
          <div class="mt-4 border-t border-line pt-3">
            <button
              class="w-full rounded-lg border border-rose-200 px-3 py-2 text-xs font-medium text-rose-600 transition hover:bg-rose-50"
              @click="askDelete"
            >{{ asset.source_type === "external" ? "从库中移除（不删源文件）" : "删除到回收站" }}</button>
          </div>
        </aside>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="promptModalOpen"
        class="fixed inset-0 z-[55] flex items-center justify-center bg-black/40"
        @click.self="promptModalOpen = false"
      >
        <div class="w-[560px] max-w-[92vw] rounded-2xl bg-white p-5 shadow-soft">
          <div class="flex items-center justify-between">
            <h3 class="truncate text-sm font-semibold">提示词 · {{ asset.name }}</h3>
            <button class="rounded-lg px-2 py-1 text-xs text-muted transition hover:bg-canvas" @click="promptModalOpen = false">关闭</button>
          </div>
          <p v-if="promptError" class="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{{ promptError }}</p>

          <template v-if="promptEditing">
            <textarea
              v-model="promptDraft"
              rows="12"
              placeholder="粘贴完整的图片/视频提示词…"
              class="mt-3 w-full resize-y rounded-xl border border-line bg-white px-3 py-2.5 font-mono text-xs leading-6 outline-none focus:border-accent"
            ></textarea>
            <p class="mt-1.5 text-[11px] text-muted">完整多行提示词，保留原始换行与特殊字符，不拆分正负提示词。</p>
            <div class="mt-3 flex justify-end gap-2">
              <button
                v-if="asset.has_prompt"
                class="rounded-lg px-3 py-1.5 text-sm text-muted transition hover:bg-canvas"
                @click="promptEditing = false"
              >取消</button>
              <button
                class="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-40"
                :disabled="promptSaving"
                @click="savePrompt"
              >{{ promptSaving ? "保存中…" : "保存" }}</button>
            </div>
          </template>

          <template v-else>
            <pre
              class="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-canvas px-3 py-2.5 font-mono text-xs leading-6"
            >{{ promptLoading ? "正在加载…" : promptText }}</pre>
            <div class="mt-3 flex items-center justify-between">
              <button
                class="rounded-lg border border-line px-3 py-1.5 text-xs font-medium transition hover:bg-canvas"
                @click="copyPrompt"
              >{{ promptCopied ? "已复制 ✓" : "复制全文" }}</button>
              <div class="flex gap-2">
                <button class="rounded-lg border border-line px-3 py-1.5 text-xs font-medium transition hover:bg-canvas" @click="startPromptEdit">编辑</button>
                <button class="rounded-lg px-3 py-1.5 text-xs text-muted transition hover:bg-canvas" @click="promptModalOpen = false">关闭</button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </Teleport>
  </Teleport>
</template>
