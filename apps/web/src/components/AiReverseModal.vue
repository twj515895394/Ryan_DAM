<script setup lang="ts">
import { ref, watch } from "vue";
import { api } from "../api/client";
import type { AiModelProfile, AiReverseTemplate, SingleImageReverseResult } from "../api/types";
import ConfirmDialog from "./ConfirmDialog.vue";

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

// 执行反推状态
const reversing = ref(false);
const reverseResult = ref<SingleImageReverseResult | null>(null);
const draftPrompt = ref("");
const saving = ref(false);

// 覆盖确认弹窗
const showOverwriteConfirm = ref(false);

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      error.value = "";
      reverseResult.value = null;
      draftPrompt.value = "";
      showOverwriteConfirm.value = false;
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
    emit("close");
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
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm"
      @click.self="emit('close')"
    >
      <div class="w-[620px] max-w-[94vw] rounded-2xl bg-white p-6 shadow-2xl border border-line/60">
        <!-- 头部 -->
        <div class="flex items-center justify-between border-b border-line pb-3">
          <div class="flex items-center gap-2">
            <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10 text-accent text-sm">👁️</span>
            <div>
              <h3 class="text-sm font-semibold text-ink">AI 视觉提示词反推</h3>
              <p class="text-[11px] text-muted truncate max-w-[420px]">{{ assetName }}</p>
            </div>
          </div>
          <button
            class="rounded-lg p-1.5 text-muted hover:bg-canvas hover:text-ink transition"
            @click="emit('close')"
          >
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- 错误提示 -->
        <p v-if="error" class="mt-3 rounded-xl bg-rose-50 px-3.5 py-2 text-xs text-rose-700 border border-rose-200">
          {{ error }}
        </p>

        <!-- 表单参数选择 -->
        <div class="mt-4 grid grid-cols-2 gap-3 text-xs">
          <div>
            <label class="block font-medium text-ink mb-1">反推模板模式</label>
            <select
              v-model="selectedTemplateId"
              class="w-full rounded-xl border border-line bg-white px-3 py-2 text-xs text-ink outline-none focus:border-accent"
              :disabled="reversing"
            >
              <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">
                {{ tpl.name }} {{ tpl.is_builtin ? '(内置)' : '' }}
              </option>
            </select>
          </div>
          <div>
            <label class="block font-medium text-ink mb-1">视觉理解模型 (Vision)</label>
            <select
              v-model="selectedModelProfileId"
              class="w-full rounded-xl border border-line bg-white px-3 py-2 text-xs text-ink outline-none focus:border-accent"
              :disabled="reversing"
            >
              <option :value="null">默认路由模型</option>
              <option v-for="m in visionModels" :key="m.id" :value="m.id">
                {{ m.name }} ({{ m.model_id }})
              </option>
            </select>
          </div>
        </div>

        <!-- 执行按钮区 -->
        <div class="mt-3 flex items-center justify-between">
          <span class="text-[11px] text-muted">
            * 反推将忠实提取画面客观视觉事实，不假定真实相机或原始 Prompt
          </span>
          <button
            class="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-medium text-white shadow-sm hover:bg-blue-600 transition disabled:opacity-40"
            :disabled="reversing || loading"
            @click="runReverse"
          >
            <span v-if="reversing" class="animate-spin">⏳</span>
            <span>{{ reversing ? "正在反推中…" : (reverseResult ? "重新反推" : "开始视觉反推") }}</span>
          </button>
        </div>

        <!-- 反推结果区 -->
        <div v-if="reverseResult || draftPrompt" class="mt-4 border-t border-line pt-4">
          <div class="flex items-center justify-between mb-1.5">
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
            rows="8"
            class="w-full resize-y rounded-xl border border-line bg-white px-3 py-2.5 font-mono text-xs leading-6 text-ink outline-none focus:border-accent"
            placeholder="反推结果将展示在此处，可直接编辑修改…"
          ></textarea>

          <div class="mt-3 flex items-center justify-between">
            <span class="text-[11px] text-muted">
              保存后将为当前素材写入正式 Prompt 并标记来源为「AI 视觉反推」
            </span>
            <div class="flex items-center gap-2">
              <button
                class="rounded-xl border border-line px-3.5 py-1.5 text-xs text-ink hover:bg-canvas transition"
                @click="emit('close')"
              >
                取消
              </button>
              <button
                class="rounded-xl bg-accent px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-600 transition disabled:opacity-40"
                :disabled="saving || !draftPrompt.trim()"
                @click="handleSaveClick"
              >
                {{ saving ? "正在保存…" : "确认并保存到资产" }}
              </button>
            </div>
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
