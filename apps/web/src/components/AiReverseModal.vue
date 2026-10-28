<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { api } from "../api/client";
import type { AiModelProfile, AiReverseTemplate, SingleImageReverseResult } from "../api/types";
import ConfirmDialog from "./ConfirmDialog.vue";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";

const props = defineProps<{
  open: boolean;
  assetId: number;
  assetName: string;
  hasExistingPrompt: boolean;
  currentPromptText?: string | null;
  currentPromptRevision?: number;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "saved", payload: { prompt_text: string; prompt_origin: string; prompt_revision: number }): void;
}>();

const loading = ref(false);
const error = ref("");
const templates = ref<AiReverseTemplate[]>([]);
const visionModels = ref<AiModelProfile[]>([]);
const selectedTemplateId = ref<number | null>(null);
const selectedModelProfileId = ref<number | null>(null);
const selectedLanguage = ref<"zh" | "en">("zh");

const languageOptions: AppleSelectOption[] = [
  { value: "zh", label: "中文 (默认推荐)", subLabel: "输出详尽结构化中文描述", badge: "中文", badgeColor: "emerald" },
  { value: "en", label: "英文 (English)", subLabel: "输出 SD/MJ/Flux 英文提示词", badge: "英文", badgeColor: "zinc" }
];

const templateOptions = computed<AppleSelectOption[]>(() =>
  templates.value.map((tpl) => ({
    value: tpl.id,
    label: tpl.name,
    subLabel: tpl.description || undefined,
    badge: tpl.is_builtin ? "内置" : "自定义",
    badgeColor: tpl.is_builtin ? "zinc" : "accent"
  }))
);

const visionModelOptions = computed<AppleSelectOption[]>(() => [
  { value: "", label: "默认路由模型", subLabel: "使用全局默认视觉理解模型", badge: "默认", badgeColor: "emerald" },
  ...visionModels.value.map((m) => ({
    value: m.id,
    label: m.name,
    subLabel: m.model_id,
    badge: m.adapter_kind,
    badgeColor: "blue" as const
  }))
]);

// 执行反推状态
const reversing = ref(false);
const reverseResult = ref<SingleImageReverseResult | null>(null);
const draftPrompt = ref("");
const saving = ref(false);

// 覆盖确认弹窗
const showOverwriteConfirm = ref(false);

function handleClose(): void {
  emit("close");
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

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      error.value = "";
      reverseResult.value = null;
      draftPrompt.value = "";
      showOverwriteConfirm.value = false;
      selectedLanguage.value = "zh";
      await loadInitialData();
    }
  },
  { immediate: true }
);

async function loadInitialData(): Promise<void> {
  loading.value = true;
  try {
    const [tpls, models] = await Promise.all([
      api.listReverseTemplates(true),
      api.listAllModels(),
    ]);
    templates.value = tpls;
    if (tpls.length > 0 && !selectedTemplateId.value) {
      selectedTemplateId.value = tpls[0].id;
    }
    // 过滤具有 image_understand 能力的模型
    visionModels.value = models.filter((m) => m.enabled && m.capabilities?.image_understand?.supported);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载配置失败";
  } finally {
    loading.value = false;
  }
}

async function runReverse(): Promise<void> {
  reversing.value = true;
  error.value = "";
  try {
    const res = await api.reverseSingleImage(props.assetId, {
      template_id: selectedTemplateId.value,
      model_profile_id: selectedModelProfileId.value,
      language: selectedLanguage.value,
    });
    reverseResult.value = res;
    draftPrompt.value = res.reversed_prompt;
  } catch (err: any) {
    error.value = err?.message || (err instanceof Error ? err.message : "视觉反推失败");
  } finally {
    reversing.value = false;
  }
}

function handleSaveClick(): void {
  if (props.hasExistingPrompt) {
    showOverwriteConfirm.value = true;
  } else {
    void executeSave(false);
  }
}

async function executeSave(forceOverwrite: boolean): Promise<void> {
  showOverwriteConfirm.value = false;
  saving.value = true;
  error.value = "";
  try {
    const res = await api.setAssetPrompt(props.assetId, draftPrompt.value, {
      expectedRevision: forceOverwrite ? undefined : (props.currentPromptRevision || 1),
      promptOrigin: "ai_reverse",
    });
    emit("saved", {
      prompt_text: res.prompt_text ?? draftPrompt.value,
      prompt_origin: res.prompt_origin || "ai_reverse",
      prompt_revision: res.prompt_revision,
    });
    handleClose();
  } catch (err: any) {
    error.value = err?.message || (err instanceof Error ? err.message : "保存提示词失败");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      @click.self="handleClose"
    >
      <div
        class="relative flex max-h-[90vh] w-full max-w-[640px] flex-col rounded-2xl border border-line/80 bg-white shadow-2xl backdrop-blur-xl overflow-hidden"
      >
        <!-- 头部 (固定置顶) -->
        <div class="flex items-center justify-between border-b border-line px-6 py-4 shrink-0">
          <div class="flex items-center gap-2.5 min-w-0">
            <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent text-sm">👁️</span>
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-ink">AI 视觉提示词反推</h3>
              <p class="text-[11px] text-muted truncate max-w-[440px]">{{ assetName }}</p>
            </div>
          </div>
          <button
            type="button"
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-ink transition active:scale-95"
            title="关闭 (Esc)"
            aria-label="关闭"
            @click.stop="handleClose"
          >
            <svg class="h-4 w-4 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- 中间内容区域 (独立滚动，避免长内容撑爆视口) -->
        <div class="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          <!-- 错误提示 -->
          <p v-if="error" class="rounded-xl bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700 border border-rose-200">
            {{ error }}
          </p>

          <!-- 表单参数选择 (Apple HIG 统一下拉选择器) -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div>
              <label class="block font-medium text-ink mb-1.5">反推模板模式</label>
              <AppleSelect
                v-model="selectedTemplateId"
                :options="templateOptions"
                :disabled="reversing || loading"
                placeholder="请选择反推模板"
              />
            </div>
            <div>
              <label class="block font-medium text-ink mb-1.5">视觉理解模型 (Vision)</label>
              <AppleSelect
                :model-value="selectedModelProfileId ?? ''"
                :options="visionModelOptions"
                :disabled="reversing || loading"
                placeholder="默认路由模型"
                @change="(val) => { selectedModelProfileId = val ? Number(val) : null; }"
              />
            </div>
            <div>
              <label class="block font-medium text-ink mb-1.5">输出语言 (Language)</label>
              <AppleSelect
                v-model="selectedLanguage"
                :options="languageOptions"
                :disabled="reversing || loading"
                placeholder="选择语言"
              />
            </div>
          </div>

          <!-- 执行按钮区 -->
          <div class="flex items-center justify-between pt-1">
            <span class="text-[11px] text-muted max-w-[380px] leading-relaxed">
              * 反推将忠实提取画面客观视觉事实，不假定真实相机或原始 Prompt
            </span>
            <button
              type="button"
              class="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-medium text-white shadow-sm hover:bg-blue-600 transition disabled:opacity-40 shrink-0 active:scale-95"
              :disabled="reversing || loading"
              @click="runReverse"
            >
              <span v-if="reversing" class="animate-spin">⏳</span>
              <span>{{ reversing ? "正在反推中…" : (reverseResult ? "重新反推" : "开始视觉反推") }}</span>
            </button>
          </div>

          <!-- 反推结果区 -->
          <div v-if="reverseResult || draftPrompt" class="border-t border-line/80 pt-4 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-ink flex items-center gap-1.5">
                <span>反推提示词草稿</span>
                <span class="text-[10px] text-muted font-normal">
                  (来自 {{ reverseResult?.model_name || 'Vision Model' }} · {{ reverseResult?.template_name }})
                </span>
              </span>
              <span v-if="hasExistingPrompt" class="text-[10px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
                已有提示词，保存将替换
              </span>
            </div>

            <textarea
              v-model="draftPrompt"
              rows="7"
              class="w-full resize-y rounded-xl border border-line bg-white px-3.5 py-2.5 font-mono text-xs leading-6 text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent/20"
              placeholder="反推结果将展示在此处，可直接编辑修改…"
            ></textarea>
          </div>
        </div>

        <!-- 底部操作栏 (固定置底，始终清晰可点) -->
        <div class="flex items-center justify-between border-t border-line/60 bg-canvas/40 px-6 py-3.5 shrink-0">
          <span class="text-[11px] text-muted truncate max-w-[340px]">
            {{ draftPrompt.trim() ? "保存后将为当前素材写入正式 Prompt 并标记来源" : "按 Esc 或点击取消退出" }}
          </span>
          <div class="flex items-center gap-2.5">
            <button
              type="button"
              class="rounded-xl border border-line/80 bg-white px-4 py-1.5 text-xs font-medium text-ink hover:bg-canvas transition active:scale-95"
              @click.stop="handleClose"
            >
              取消
            </button>
            <button
              type="button"
              class="rounded-xl bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-600 transition disabled:opacity-40 active:scale-95"
              :disabled="saving || !draftPrompt.trim() || reversing"
              @click="handleSaveClick"
            >
              {{ saving ? "正在保存…" : "确认并保存到资产" }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 覆盖确认弹窗 -->
    <ConfirmDialog
      :open="showOverwriteConfirm"
      title="覆盖已有提示词？"
      :description="`当前素材已存在提示词。\n保存此反推结果将覆盖现有提示词（版本将递增升级）。是否确认覆盖？`"
      confirm-text="确认覆盖"
      intent="warning"
      @confirm="executeSave(true)"
      @cancel="showOverwriteConfirm = false"
    />
  </Teleport>
</template>
