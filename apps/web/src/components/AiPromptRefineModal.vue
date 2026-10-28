<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from "vue";
import { api } from "../api/client";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";
import SidebarIcon from "./SidebarIcon.vue";

const props = defineProps<{
  open: boolean;
  basePrompt: string;
  modelName?: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "apply-prompt", refinedPrompt: string): void;
  (e: "regenerate-with-prompt", refinedPrompt: string): void;
  (e: "jump-to-form"): void;
}>();

const customInstruction = ref("");
const language = ref<"zh" | "en">("zh");
const isOptimizing = ref(false);
const errorMsg = ref("");
const refinedPrompt = ref("");
const copiedBase = ref(false);
const showBasePrompt = ref(true);

const languageOptions: AppleSelectOption[] = [
  { value: "zh", label: "中文 (Chinese)", badge: "推荐", badgeColor: "blue" },
  { value: "en", label: "英文 (English)", badge: "生图兼容佳", badgeColor: "zinc" }
];

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      customInstruction.value = "";
      errorMsg.value = "";
      refinedPrompt.value = "";
      copiedBase.value = false;
      showBasePrompt.value = true;
    }
  },
  { immediate: true }
);

async function handleOptimize(): Promise<void> {
  const instr = customInstruction.value.trim();
  if (!instr) {
    errorMsg.value = "请先填写您希望对当前画面进行的修改或优化要求。";
    return;
  }
  isOptimizing.value = true;
  errorMsg.value = "";

  try {
    const res = await api.optimizePrompt({
      prompt: props.basePrompt,
      custom_instruction: instr,
      language: language.value
    });
    refinedPrompt.value = res.optimized_prompt;
  } catch (err: any) {
    errorMsg.value = err.message || "提示词重写失败，请检查网络或模型配置";
  } finally {
    isOptimizing.value = false;
  }
}

async function handleCopyBase(): Promise<void> {
  if (!props.basePrompt || copiedBase.value) return;
  copiedBase.value = true;
  try {
    await navigator.clipboard.writeText(props.basePrompt);
    setTimeout(() => {
      copiedBase.value = false;
    }, 1500);
  } catch {
    copiedBase.value = false;
  }
}

function handleApply(): void {
  const p = refinedPrompt.value.trim() || props.basePrompt;
  emit("apply-prompt", p);
}

function handleRegenerate(): void {
  const p = refinedPrompt.value.trim() || props.basePrompt;
  emit("regenerate-with-prompt", p);
}

function handleClose(): void {
  emit("close");
}

function handleJumpToForm(): void {
  emit("jump-to-form");
}

function onKeydown(e: KeyboardEvent): void {
  if (!props.open) return;
  if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    handleClose();
  }
}

onMounted(() => {
  window.addEventListener("keydown", onKeydown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      leave-active-class="transition duration-150 ease-in"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4 backdrop-blur-md"
        @click.self="handleClose"
      >
        <div
          class="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-line/80 bg-white/95 shadow-2xl backdrop-blur-xl transition-all"
        >
          <!-- 固定头部 (Fixed Header) -->
          <div class="flex shrink-0 items-center justify-between border-b border-line/60 px-6 py-4">
            <div class="flex items-center gap-2.5">
              <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/10 text-accent">
                <SidebarIcon name="edit" class="h-4 w-4" />
              </div>
              <div>
                <h3 class="text-sm font-semibold tracking-tight text-ink">
                  基于已有提示词迭代调整
                </h3>
                <p class="text-xs text-muted">
                  在当前画面提示词基础上，输入修改或新增要求，AI 将为您智能融合重塑
                </p>
              </div>
            </div>

            <button
              type="button"
              class="flex h-7 w-7 items-center justify-center rounded-lg text-muted transition hover:bg-canvas hover:text-ink active:scale-95"
              title="关闭 (Esc)"
              @click.stop="handleClose"
            >
              <svg class="pointer-events-none h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- 独立滚动体 (Scrollable Body) -->
          <div class="flex-1 overflow-y-auto px-6 py-5 space-y-4">
            <!-- 1. 已有基础提示词卡片 -->
            <div class="rounded-xl border border-line/70 bg-canvas/60 p-3.5">
              <div class="flex items-center justify-between pb-2">
                <div class="flex items-center gap-1.5 text-xs font-semibold text-ink">
                  <svg class="h-3.5 w-3.5 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                  <span>当前画面的原始提示词</span>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 text-[11px] font-medium text-muted hover:text-ink transition"
                    @click="handleCopyBase"
                  >
                    <span>{{ copiedBase ? "已复制！" : "复制" }}</span>
                  </button>
                  <button
                    type="button"
                    class="text-[11px] font-medium text-muted hover:text-ink transition"
                    @click="showBasePrompt = !showBasePrompt"
                  >
                    {{ showBasePrompt ? "收起" : "展开" }}
                  </button>
                </div>
              </div>

              <div
                v-if="showBasePrompt"
                class="max-h-28 overflow-y-auto rounded-lg bg-white/80 p-2.5 text-xs leading-relaxed text-ink/80 border border-line/40 select-text"
              >
                {{ basePrompt || "（暂无提示词文本）" }}
              </div>
            </div>

            <!-- 2. 增量修改与优化要求输入 -->
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <label class="text-xs font-semibold text-ink flex items-center gap-1.5">
                  <span class="flex h-4 w-4 items-center justify-center rounded-full bg-accent text-[10px] font-bold text-white">2</span>
                  <span>您的修改与优化要求 (Modification Requirements)</span>
                </label>
                <span class="text-[11px] text-muted">支持自然语言描述</span>
              </div>

              <textarea
                v-model="customInstruction"
                rows="3"
                class="w-full resize-none rounded-xl border border-line bg-white px-3.5 py-2.5 text-xs leading-relaxed text-ink placeholder:text-muted/60 focus:border-accent focus:outline-hidden focus:ring-2 focus:ring-accent/20 transition"
                placeholder="例如：将人物衣服换成红色法式长裙，背景增加金色落日余晖，增加电影质感景深与胶片颗粒…"
              />

              <!-- 语言设置与重写按钮条 -->
              <div class="flex items-center justify-between pt-1">
                <div class="flex items-center gap-2">
                  <span class="text-xs text-muted">输出语言:</span>
                  <div class="w-36">
                    <AppleSelect
                      v-model="language"
                      size="sm"
                      :options="languageOptions"
                    />
                  </div>
                </div>

                <button
                  type="button"
                  class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-1.5 text-xs font-semibold text-white shadow-xs transition hover:bg-blue-700 active:scale-97 disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="isOptimizing || !customInstruction.trim()"
                  @click="handleOptimize"
                >
                  <svg
                    v-if="isOptimizing"
                    class="h-3.5 w-3.5 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <line x1="12" y1="2" x2="12" y2="6" />
                    <line x1="12" y1="18" x2="12" y2="22" />
                    <line x1="4.93" y1="4.93" x2="7.76" y2="7.76" />
                    <line x1="16.24" y1="16.24" x2="19.07" y2="19.07" />
                    <line x1="2" y1="12" x2="6" y2="12" />
                    <line x1="18" y1="12" x2="22" y2="12" />
                    <line x1="4.93" y1="19.07" x2="7.76" y2="16.24" />
                    <line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
                  </svg>
                  <SidebarIcon v-else name="star" class="h-3.5 w-3.5" />
                  <span>{{ isOptimizing ? "正在融合重塑…" : "✨ 开始智能重写" }}</span>
                </button>
              </div>

              <p v-if="errorMsg" class="text-xs text-rose-600 pt-1">
                {{ errorMsg }}
              </p>
            </div>

            <!-- 3. 重写结果预览与编辑 -->
            <div v-if="refinedPrompt" class="space-y-2 pt-2 border-t border-line/60">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-1.5">
                  <span class="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-bold text-white">✓</span>
                  <label class="text-xs font-semibold text-ink">
                    重塑后的生图提示词（可直接微调）
                  </label>
                </div>
                <span class="rounded-full bg-emerald-50 px-2 py-0.5 text-[10.5px] font-medium text-emerald-700 border border-emerald-200">
                  已融合修改要求
                </span>
              </div>

              <textarea
                v-model="refinedPrompt"
                rows="4"
                class="w-full resize-none rounded-xl border border-emerald-300 bg-white px-3.5 py-2.5 text-xs leading-relaxed text-ink focus:border-emerald-500 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 transition"
              />
            </div>
          </div>

          <!-- 固定底部 (Fixed Footer) -->
          <div class="flex shrink-0 items-center justify-between border-t border-line/60 bg-canvas/40 px-6 py-3.5">
            <button
              type="button"
              class="text-xs text-muted hover:text-ink underline transition"
              @click="handleJumpToForm"
            >
              直接返回工作台手动编辑
            </button>

            <div class="flex items-center gap-2">
              <button
                type="button"
                class="rounded-xl border border-line bg-white px-4 py-1.5 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
                @click="handleClose"
              >
                取消
              </button>

              <template v-if="refinedPrompt">
                <button
                  type="button"
                  class="rounded-xl border border-line bg-white px-4 py-1.5 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
                  @click="handleApply"
                >
                  带回工作台
                </button>

                <button
                  type="button"
                  class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-1.5 text-xs font-semibold text-white shadow-xs transition hover:bg-blue-700 active:scale-97"
                  @click="handleRegenerate"
                >
                  <SidebarIcon name="refresh" class="h-3.5 w-3.5" />
                  <span>✨ 立即重新生成</span>
                </button>
              </template>

              <template v-else>
                <button
                  type="button"
                  class="rounded-xl border border-line bg-white px-4 py-1.5 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
                  @click="handleJumpToForm"
                >
                  前往表单修改
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
