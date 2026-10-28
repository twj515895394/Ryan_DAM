<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { api } from "../api/client";
import type {
  AiCreationPreset,
  AiModelProfile,
  AiResult,
  AiTaskDetail,
  AiTaskSummary,
  SubmitImageGeneratePayload
} from "../api/types";
import type { SelectedReferenceItem } from "./AiReferencePickerModal.vue";
import AiWorkbenchFormView from "./AiWorkbenchFormView.vue";
import AiWorkbenchProgressView from "./AiWorkbenchProgressView.vue";
import AiWorkbenchResultView from "./AiWorkbenchResultView.vue";
import AiResultPreviewModal from "./AiResultPreviewModal.vue";
import SidebarIcon from "./SidebarIcon.vue";
import AppleSelect from "./AppleSelect.vue";

const props = defineProps<{
  open: boolean;
  initialPrompt?: string;
  initialPresetId?: number;
  initialReferenceAssetIds?: number[];
  initialMode?: "image_generate" | "image_edit";
  initialModelId?: number;
  initialParams?: Record<string, any>;
  initialReferences?: SelectedReferenceItem[];
  initialRetryOf?: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "task-created", task: AiTaskSummary): void;
}>();

// 阶段状态机：'form' 编辑态 | 'generating' 生成中过渡态 | 'result' 结果展示态 | 'failed' 失败态
type WorkbenchPhase = "form" | "generating" | "result" | "failed";
const currentPhase = ref<WorkbenchPhase>("form");
const activeTaskId = ref<string | null>(null);
const activeTaskDetail = ref<AiTaskDetail | null>(null);
const cancellingTask = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;

// 1:1 微距原画检视弹窗
const inspectingResult = ref<AiResult | null>(null);
const showInspectModal = ref(false);

// 模型与预设数据
const models = ref<AiModelProfile[]>([]);
const selectedModelId = ref<number | null>(null);
const presets = ref<AiCreationPreset[]>([]);
const loadingModels = ref(false);
const loadingPresets = ref(false);
const submitting = ref(false);
const errorMessage = ref("");
const lastSubmittedPayload = ref<SubmitImageGeneratePayload | null>(null);
const currentFormPrompt = ref(props.initialPrompt || "");

watch(
  () => props.initialPrompt,
  (val) => {
    if (val !== undefined) {
      currentFormPrompt.value = val;
    }
  },
  { immediate: true }
);

const activeModel = computed(() => {
  return models.value.find((m) => m.id === selectedModelId.value) || null;
});

const modelOptions = computed(() => {
  return models.value.map((m) => ({
    value: m.id,
    label: m.name,
    subLabel: m.model_id,
    badge: m.adapter_kind === "openai_standard" ? "OpenAI" : m.adapter_kind === "gemini_standard" ? "Gemini" : m.adapter_kind,
    badgeColor: "zinc" as const
  }));
});

// ── 生命周期与初始化 ──────────────────────────────────────────────────
watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      errorMessage.value = "";
      if (currentPhase.value !== "generating") {
        currentPhase.value = "form";
        activeTaskId.value = null;
        activeTaskDetail.value = null;
      }
      if (props.initialModelId !== undefined) {
        selectedModelId.value = props.initialModelId;
      }
      await Promise.all([loadModels(), loadPresets()]);
    } else {
      stopTaskPolling();
    }
  },
  { immediate: true }
);

async function loadModels(): Promise<void> {
  loadingModels.value = true;
  try {
    const list = await api.listAllModels();
    const genModels = list.filter(
      (m) =>
        m.enabled &&
        (m.capabilities?.image_generate?.supported !== false || m.capabilities?.image_edit?.supported !== false)
    );
    models.value = genModels;

    if (!selectedModelId.value && genModels.length > 0) {
      try {
        const bindings = await api.listDefaultBindings();
        const genBinding = bindings.find((b) => b.capability === "image_generate");
        selectedModelId.value = (genBinding && genModels.some((m) => m.id === genBinding.model_profile_id))
          ? genBinding.model_profile_id
          : genModels[0].id;
      } catch {
        selectedModelId.value = genModels[0].id;
      }
    }
  } catch (err: any) {
    errorMessage.value = err.message || "加载 AI 模型列表失败";
  } finally {
    loadingModels.value = false;
  }
}

async function loadPresets(): Promise<void> {
  loadingPresets.value = true;
  try {
    const list = await api.listCreationPresets();
    presets.value = list.filter((p) => p.enabled);
  } catch (err: any) {
    console.error("加载创作预设失败:", err);
  } finally {
    loadingPresets.value = false;
  }
}

// ── 任务提交与轮询管理 ────────────────────────────────────────────────
async function handleSubmit(payload: SubmitImageGeneratePayload): Promise<void> {
  submitting.value = true;
  errorMessage.value = "";
  lastSubmittedPayload.value = payload;

  try {
    const taskSummary = await api.submitImageGenerate(payload);
    emit("task-created", taskSummary);
    // 切换至生成中过渡态并开始平滑轮询，不自动关闭工作台
    currentPhase.value = "generating";
    activeTaskId.value = taskSummary.id;
    startTaskPolling(taskSummary.id);
  } catch (err: any) {
    errorMessage.value = err.message || "提交生图任务失败";
  } finally {
    submitting.value = false;
  }
}

function startTaskPolling(taskId: string): void {
  stopTaskPolling();
  activeTaskId.value = taskId;
  pollTimer = setInterval(async () => {
    try {
      const detail = await api.getAiTask(taskId);
      activeTaskDetail.value = detail;
      if (detail.status === "succeeded") {
        stopTaskPolling();
        currentPhase.value = "result";
      } else if (detail.status === "failed" || detail.status === "canceled") {
        stopTaskPolling();
        currentPhase.value = "failed";
        errorMessage.value = detail.error_message || "任务生成未成功";
      }
    } catch (err: any) {
      console.error("轮询 AI 任务状态失败:", err);
    }
  }, 1500);
}

function stopTaskPolling(): void {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function handleCancelCurrentTask(): Promise<void> {
  if (!activeTaskId.value || cancellingTask.value) return;
  cancellingTask.value = true;
  try {
    await api.cancelAiTask(activeTaskId.value);
    stopTaskPolling();
    currentPhase.value = "form";
  } catch (err: any) {
    errorMessage.value = err.message || "取消任务失败";
  } finally {
    cancellingTask.value = false;
  }
}

function handleCloseModal(): void {
  stopTaskPolling();
  emit("close");
}

function handleBackToEdit(newPrompt?: string | unknown): void {
  stopTaskPolling();
  if (typeof newPrompt === "string" && newPrompt.trim()) {
    currentFormPrompt.value = newPrompt.trim();
  }
  currentPhase.value = "form";
}

function handleRegenerate(newPrompt?: string | unknown): void {
  if (typeof newPrompt === "string" && newPrompt.trim()) {
    currentFormPrompt.value = newPrompt.trim();
    if (lastSubmittedPayload.value) {
      handleSubmit({
        ...lastSubmittedPayload.value,
        prompt: newPrompt.trim()
      });
      return;
    }
  }
  if (lastSubmittedPayload.value) {
    handleSubmit(lastSubmittedPayload.value);
  } else {
    currentPhase.value = "form";
  }
}

function handleInspectDetail(res: AiResult): void {
  inspectingResult.value = res;
  showInspectModal.value = true;
}

function onKeydown(e: KeyboardEvent): void {
  if (!props.open) return;
  if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    if (showInspectModal.value) {
      showInspectModal.value = false;
      return;
    }
    handleCloseModal();
  }
}

onMounted(() => {
  window.addEventListener("keydown", onKeydown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKeydown);
  stopTaskPolling();
});
</script>

<template>
  <Teleport to="body">
    <Transition enter-active-class="transition duration-200 ease-out" enter-from-class="opacity-0" leave-active-class="transition duration-150 ease-in" leave-to-class="opacity-0">
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-md" @click.self="handleCloseModal">
        <div class="relative flex max-h-[92vh] w-full max-w-3xl flex-col rounded-2xl border border-line/80 bg-white/95 shadow-2xl backdrop-blur-xl transition-all">
          <!-- 顶部标题栏 -->
          <div class="flex items-center justify-between border-b border-line/60 px-6 py-4">
            <div class="flex items-center gap-2.5">
              <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/10 text-accent">
                <SidebarIcon name="star" class="h-4 w-4" />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <h2 class="text-base font-semibold tracking-tight text-ink">
                    {{ currentPhase === "generating" ? "AI 正在创作视觉作品" : (currentPhase === "result" ? "AI 创作成果就绪" : (currentPhase === "failed" ? "AI 创作未能完成" : "AI 图像创作工作台")) }}
                  </h2>
                  <span
                    v-if="initialRetryOf && currentPhase === 'form'"
                    class="rounded-full bg-amber-100/80 px-2 py-0.5 text-[10.5px] font-medium text-amber-800 border border-amber-200/50"
                  >
                    衍生变体自 #{{ initialRetryOf.slice(-6) }}
                  </span>
                </div>
                <p class="text-[11px] text-muted">
                  {{ currentPhase === "generating" ? "高精推理渲染中，可留守等待或按 Esc 放入后台运行" : (currentPhase === "result" ? "作品已渲染完成，可一键入库、微距检视或调整迭代" : (currentPhase === "failed" ? "任务执行异常，请查看详情并调整参数重试" : "基于大语言模型润色与高精度生成模型创作视觉作品")) }}
                </p>
              </div>
            </div>

            <!-- 右侧模型选择器与关闭 -->
            <div class="flex items-center gap-3">
              <div v-if="currentPhase === 'form'" class="flex items-center gap-2">
                <span class="text-xs font-medium text-muted">生成模型</span>
                <div class="w-56 sm:w-72">
                  <AppleSelect
                    v-model="selectedModelId"
                    size="sm"
                    :options="modelOptions"
                    :disabled="loadingModels || models.length === 0"
                    placeholder="暂无可用的生图模型"
                    search-placeholder="搜索可用模型…"
                  />
                </div>
              </div>

              <div v-else-if="activeModel" class="rounded-lg border border-line bg-canvas/80 px-2.5 py-1 text-xs font-medium text-ink/80">
                {{ activeModel.name }}
              </div>

              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-lg text-muted transition hover:bg-black/5 hover:text-ink"
                :title="currentPhase === 'generating' ? '放入后台运行 (Esc)' : '关闭 (Esc)'"
                @click="handleCloseModal"
              >
                <SidebarIcon name="close" class="h-4 w-4" />
              </button>
            </div>
          </div>

          <!-- 1. 表单编辑态 (currentPhase === 'form') -->
          <AiWorkbenchFormView
            v-if="currentPhase === 'form'"
            v-model:selected-model-id="selectedModelId"
            :models="models"
            :presets="presets"
            :loading-models="loadingModels"
            :initial-prompt="currentFormPrompt"
            :initial-preset-id="initialPresetId"
            :initial-reference-asset-ids="initialReferenceAssetIds"
            :initial-mode="initialMode"
            :initial-params="initialParams"
            :initial-references="initialReferences"
            :initial-retry-of="initialRetryOf"
            :submitting="submitting"
            @submit="handleSubmit"
            @cancel="handleCloseModal"
          />

          <!-- 2. 生成中过渡态 (currentPhase === 'generating') -->
          <div v-else-if="currentPhase === 'generating'" class="flex-1 overflow-y-auto">
            <AiWorkbenchProgressView
              :prompt="lastSubmittedPayload?.prompt || ''"
              :model-name="activeModel?.name"
              :aspect-ratio="lastSubmittedPayload?.params?.aspect_ratio"
              :size="lastSubmittedPayload?.params?.size"
              :cancelling="cancellingTask"
              @cancel="handleCancelCurrentTask"
              @background-run="handleCloseModal"
            />
          </div>

          <!-- 3. 结果成果展示态 (currentPhase === 'result' && activeTaskDetail) -->
          <div v-else-if="currentPhase === 'result' && activeTaskDetail" class="flex-1 overflow-y-auto">
            <AiWorkbenchResultView
              :task-detail="activeTaskDetail"
              :model-name="activeModel?.name"
              @back-to-edit="handleBackToEdit"
              @regenerate="handleRegenerate"
              @inspect-detail="handleInspectDetail"
            />
          </div>

          <!-- 4. 任务执行失败态 (currentPhase === 'failed') -->
          <div v-else-if="currentPhase === 'failed'" class="flex flex-1 flex-col items-center justify-center p-8 text-center">
            <div class="flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-rose-600 shadow-sm">
              <SidebarIcon name="close" class="h-6 w-6" />
            </div>
            <h3 class="mt-3 text-sm font-semibold text-ink">生成未成功</h3>
            <p class="mt-1.5 max-w-md text-xs text-rose-600/90 leading-relaxed">
              {{ errorMessage || "任务未能顺利完成，请检查生图模型连接或 API 配额配置。" }}
            </p>
            <div class="mt-6 flex items-center gap-3">
              <button
                type="button"
                class="rounded-xl border border-line bg-white px-4 py-2 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
                @click="() => handleBackToEdit()"
              >
                返回修改提示词
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700 active:scale-97"
                @click="() => handleRegenerate()"
              >
                <SidebarIcon name="refresh" class="h-3.5 w-3.5" />
                <span>重试生成</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 1:1 显微级原画微距检视弹窗 -->
    <AiResultPreviewModal
      :open="showInspectModal"
      :result="inspectingResult"
      :task="activeTaskDetail"
      @close="showInspectModal = false"
    />
  </Teleport>
</template>
