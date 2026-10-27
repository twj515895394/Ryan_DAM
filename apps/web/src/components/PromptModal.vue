<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api } from "../api/client";

const props = defineProps<{
  open: boolean;
  assetId: number;
  assetName: string;
  hasPrompt: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "saved", hasPrompt: boolean, info?: { prompt_origin?: string | null; prompt_revision?: number }): void;
}>();

const promptLoading = ref(false);
const promptSaving = ref(false);
const promptEditing = ref(false);
const promptError = ref("");
const promptText = ref<string | null>(null);
const promptDraft = ref("");
const promptOrigin = ref<string | null>(null);
const promptRevision = ref<number>(1);
const promptCopied = ref(false);
let promptCopyTimer: ReturnType<typeof setTimeout> | null = null;

// CAS 冲突状态
const hasConflict = ref(false);

const originLabel = computed(() => {
  switch (promptOrigin.value) {
    case "manual": return "手动录入";
    case "ai_reverse": return "AI 视觉反推";
    case "generation_prompt": return "生图提示词";
    case "edit_prompt": return "编辑提示词";
    default: return "未标注";
  }
});

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      hasConflict.value = false;
      void initPrompt();
    } else {
      promptEditing.value = false;
      promptError.value = "";
      promptText.value = null;
      hasConflict.value = false;
    }
  },
  { immediate: true }
);

async function initPrompt(): Promise<void> {
  promptError.value = "";
  promptEditing.value = !props.hasPrompt;
  promptDraft.value = "";
  promptText.value = null;
  promptOrigin.value = null;
  promptRevision.value = 1;
  hasConflict.value = false;

  if (!props.hasPrompt) return;

  promptLoading.value = true;
  try {
    const result = await api.getAssetPrompt(props.assetId);
    promptText.value = result.prompt_text ?? "";
    promptOrigin.value = result.prompt_origin ?? null;
    promptRevision.value = result.prompt_revision || 1;
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
  hasConflict.value = false;
}

async function savePrompt(forceOverwrite = false): Promise<void> {
  promptSaving.value = true;
  promptError.value = "";
  hasConflict.value = false;
  try {
    const result = await api.setAssetPrompt(props.assetId, promptDraft.value || null, {
      expectedRevision: forceOverwrite ? undefined : promptRevision.value,
      promptOrigin: promptOrigin.value || "manual"
    });
    promptText.value = result.prompt_text;
    promptOrigin.value = result.prompt_origin ?? null;
    promptRevision.value = result.prompt_revision;
    emit("saved", result.has_prompt, {
      prompt_origin: result.prompt_origin,
      prompt_revision: result.prompt_revision
    });
    promptEditing.value = false;
    if (!result.has_prompt) emit("close");
  } catch (err: any) {
    if (err?.code === "prompt_conflict") {
      hasConflict.value = true;
      promptError.value = err.message || "提示词已被修改，出现并发冲突";
    } else {
      promptError.value = err instanceof Error ? err.message : "保存失败";
    }
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
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[55] flex items-center justify-center bg-black/40 backdrop-blur-xs"
      @click.self="emit('close')"
    >
      <div class="w-[560px] max-w-[92vw] rounded-2xl bg-white p-5 shadow-soft">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <h3 class="truncate text-sm font-semibold text-ink">
              {{ promptEditing ? (hasPrompt ? "编辑提示词" : "添加提示词") : "提示词" }} · {{ assetName }}
            </h3>
            <span
              v-if="hasPrompt && !promptEditing"
              class="rounded-md bg-canvas px-1.5 py-0.5 text-[10px] text-muted border border-line/60"
            >
              {{ originLabel }} · v{{ promptRevision }}
            </span>
          </div>
          <button
            class="rounded-lg px-2 py-1 text-xs text-muted transition hover:bg-canvas hover:text-ink"
            @click="emit('close')"
          >
            关闭
          </button>
        </div>

        <p v-if="promptError" class="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {{ promptError }}
        </p>

        <template v-if="promptEditing">
          <textarea
            v-model="promptDraft"
            rows="12"
            placeholder="粘贴完整的图片/视频提示词…"
            class="mt-3 w-full resize-y rounded-xl border border-line bg-white px-3 py-2.5 font-mono text-xs leading-6 text-ink outline-none focus:border-accent"
          ></textarea>
          <p class="mt-1.5 text-[11px] text-muted">完整多行提示词，保留原始换行与特殊字符，不拆分正负提示词。</p>

          <!-- 冲突确认提示条 -->
          <div v-if="hasConflict" class="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-800 flex items-center justify-between">
            <span>提示词已被修改，是否放弃冲突检查直接覆盖？</span>
            <button
              type="button"
              class="rounded-md bg-amber-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-amber-700 transition"
              @click="savePrompt(true)"
            >
              强制覆盖保存
            </button>
          </div>

          <div class="mt-3 flex justify-end gap-2">
            <button
              v-if="hasPrompt"
              class="rounded-lg px-3 py-1.5 text-sm text-muted transition hover:bg-canvas"
              @click="promptEditing = false"
            >
              取消
            </button>
            <button
              class="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-40"
              :disabled="promptSaving"
              @click="savePrompt(false)"
            >
              {{ promptSaving ? "保存中…" : "保存" }}
            </button>
          </div>
        </template>

        <template v-else>
          <pre
            class="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-canvas px-3 py-2.5 font-mono text-xs leading-6 text-ink"
          >{{ promptLoading ? "正在加载…" : promptText }}</pre>
          <div class="mt-3 flex items-center justify-between">
            <button
              class="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink transition hover:bg-canvas"
              @click="copyPrompt"
            >
              {{ promptCopied ? "已复制 ✓" : "复制全文" }}
            </button>
            <div class="flex gap-2">
              <button
                class="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink transition hover:bg-canvas"
                @click="startPromptEdit"
              >
                编辑
              </button>
              <button
                class="rounded-lg px-3 py-1.5 text-xs text-muted transition hover:bg-canvas hover:text-ink"
                @click="emit('close')"
              >
                关闭
              </button>
            </div>
          </div>
        </template>
      </div>
    </div>
  </Teleport>
</template>
