<script setup lang="ts">
import { ref, watch } from "vue";
import { api } from "../api/client";

const props = defineProps<{
  open: boolean;
  assetId: number;
  assetName: string;
  hasPrompt: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "saved", hasPrompt: boolean): void;
}>();

const promptLoading = ref(false);
const promptSaving = ref(false);
const promptEditing = ref(false);
const promptError = ref("");
const promptText = ref<string | null>(null);
const promptDraft = ref("");
const promptCopied = ref(false);
let promptCopyTimer: ReturnType<typeof setTimeout> | null = null;

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      void initPrompt();
    } else {
      promptEditing.value = false;
      promptError.value = "";
      promptText.value = null;
    }
  }
);

async function initPrompt(): Promise<void> {
  promptError.value = "";
  promptEditing.value = !props.hasPrompt;
  promptDraft.value = "";
  promptText.value = null;
  if (!props.hasPrompt) return;

  promptLoading.value = true;
  try {
    const result = await api.getAssetPrompt(props.assetId);
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
    const result = await api.setAssetPrompt(props.assetId, promptDraft.value || null);
    promptText.value = result.prompt_text;
    emit("saved", result.has_prompt);
    promptEditing.value = false;
    if (!result.has_prompt) emit("close");
  } catch (error) {
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
          <h3 class="truncate text-sm font-semibold text-ink">提示词 · {{ assetName }}</h3>
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
              @click="savePrompt"
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
