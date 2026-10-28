<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "../api/client";
import type {
  AiCreationPreset,
  AiModelProfile,
  AiTaskSummary,
  PromptOptimizeResult,
  SubmitImageGeneratePayload
} from "../api/types";
import AiReferencePickerModal, { type SelectedReferenceItem } from "./AiReferencePickerModal.vue";
import SidebarIcon from "./SidebarIcon.vue";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";

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

// 基础状态
const creationMode = ref<"image_generate" | "image_edit">("image_generate");
const loadingModels = ref(false);
const loadingPresets = ref(false);
const submitting = ref(false);
const errorMessage = ref("");

const models = ref<AiModelProfile[]>([]);
const selectedModelId = ref<number | null>(null);
const presets = ref<AiCreationPreset[]>([]);
const selectedPresetId = ref<number | null>(null);

// 表单字段
const prompt = ref("");
const negativePrompt = ref("");
const selectedAspectRatio = ref("1:1");
const selectedSize = ref("1024x1024");
const selectedQuality = ref("standard");
const selectedStyle = ref("");
const denoisingStrength = ref<number | null>(0.7);
const generateCount = ref(1);
const seed = ref<number | null>(null);
const showAdvanced = ref(false);

// 参考图与智能润色
const showRefPicker = ref(false);
const references = ref<SelectedReferenceItem[]>([]);
const optimizing = ref(false);
const lastOptimizedResult = ref<PromptOptimizeResult | null>(null);
const originalPromptBeforeOpt = ref<string | null>(null);
const optimizeError = ref("");

// ── 计算属性 ──────────────────────────────────────────────────────────
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

const activeModelCapabilities = computed(() => {
  if (!activeModel.value) return null;
  const caps = activeModel.value.capabilities as Record<string, any> | undefined;
  if (!caps) return null;
  return caps[creationMode.value] || caps.image_generate || caps.image_edit || null;
});

const supportedQualities = computed(() => {
  const caps = activeModelCapabilities.value;
  if (caps?.supported_qualities && Array.isArray(caps.supported_qualities)) {
    return caps.supported_qualities as string[];
  }
  return [];
});

const supportedStyles = computed(() => {
  const caps = activeModelCapabilities.value;
  if (caps?.supported_styles && Array.isArray(caps.supported_styles)) {
    return caps.supported_styles as string[];
  }
  return [];
});

const supportedAspectRatios = computed(() => {
  const caps = activeModelCapabilities.value;
  if (caps?.supported_aspect_ratios && caps.supported_aspect_ratios.length > 0) {
    return caps.supported_aspect_ratios as string[];
  }
  return ["1:1", "16:9", "9:16", "4:3", "3:4"];
});

const supportedSizes = computed(() => {
  const caps = activeModelCapabilities.value;
  if (caps?.supported_sizes && caps.supported_sizes.length > 0) {
    return caps.supported_sizes as string[];
  }
  return ["1024x1024", "1024x768", "768x1024", "1280x720", "720x1280"];
});

const sizeOptions = computed<AppleSelectOption[]>(() =>
  supportedSizes.value.map((sz) => ({ value: sz, label: sz }))
);
const qualityOptions = computed<AppleSelectOption[]>(() =>
  supportedQualities.value.map((q) => ({
    value: q,
    label: q === "hd" ? "超清 (HD)" : q === "standard" ? "标准 (Standard)" : q,
    badge: q === "hd" ? "高质量" : "标准",
    badgeColor: q === "hd" ? "accent" : "zinc"
  }))
);
const styleOptions = computed<AppleSelectOption[]>(() => [
  { value: "", label: "默认风格", badge: "默认", badgeColor: "zinc" },
  ...supportedStyles.value.map((st) => ({
    value: st,
    label: st === "vivid" ? "生动鲜明 (Vivid)" : st === "natural" ? "自然写实 (Natural)" : st,
    badge: st === "vivid" ? "色彩浓郁" : "自然真实",
    badgeColor: (st === "vivid" ? "amber" : "emerald") as "amber" | "emerald"
  }))
]);

const refRoleOptions: AppleSelectOption[] = [
  { value: "reference", label: "综合参考", badge: "综合", badgeColor: "zinc" },
  { value: "style", label: "风格参考", badge: "风格", badgeColor: "accent" },
  { value: "character", label: "角色主体", badge: "主体", badgeColor: "blue" },
  { value: "composition", label: "构图布局", badge: "构图", badgeColor: "amber" }
];
const activePreset = computed(() => presets.value.find((p) => p.id === selectedPresetId.value) || null);

// ── 生命周期与初始化 ──────────────────────────────────────────────────
watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      errorMessage.value = "";
      optimizeError.value = "";
      lastOptimizedResult.value = null;
      originalPromptBeforeOpt.value = null;

      if (props.initialMode) {
        creationMode.value = props.initialMode;
      } else if (props.initialReferenceAssetIds && props.initialReferenceAssetIds.length > 0) {
        creationMode.value = "image_edit";
      } else {
        creationMode.value = "image_generate";
      }

      if (props.initialPrompt !== undefined) prompt.value = props.initialPrompt;
      if (props.initialPresetId !== undefined) selectedPresetId.value = props.initialPresetId;
      if (props.initialModelId !== undefined) selectedModelId.value = props.initialModelId;
      if (props.initialParams) {
        if (props.initialParams.size) selectedSize.value = props.initialParams.size;
        if (props.initialParams.aspect_ratio) selectedAspectRatio.value = props.initialParams.aspect_ratio;
        if (props.initialParams.quality) selectedQuality.value = props.initialParams.quality;
        if (props.initialParams.style) selectedStyle.value = props.initialParams.style;
        if (props.initialParams.denoising_strength !== undefined) denoisingStrength.value = props.initialParams.denoising_strength;
        if (props.initialParams.seed !== undefined) {
          seed.value = props.initialParams.seed;
          showAdvanced.value = true;
        }
        if (props.initialParams.negative_prompt) {
          negativePrompt.value = props.initialParams.negative_prompt;
          showAdvanced.value = true;
        }
      }
      if (props.initialReferences?.length) {
        references.value = [...props.initialReferences];
      }
      if (props.initialReferenceAssetIds?.length) {
        for (const aid of props.initialReferenceAssetIds) {
          if (!references.value.some((r) => r.source_kind === "asset" && r.source_id === String(aid))) {
            references.value.push({
              source_kind: "asset",
              source_id: String(aid),
              preview_url: `/api/v1/assets/${aid}/thumbnail`,
              name: `资产 #${aid}`,
              role: "reference"
            });
          }
        }
      }

      await Promise.all([loadModels(), loadPresets()]);
    }
  },
  { immediate: true }
);

async function loadModels(): Promise<void> {
  loadingModels.value = true;
  try {
    const list = await api.listAllModels();
    // 过滤支持 image_generate 或 image_edit 且已启用的模型
    const genModels = list.filter(
      (m) =>
        m.enabled &&
        (m.capabilities?.image_generate?.supported !== false || m.capabilities?.image_edit?.supported !== false)
    );
    models.value = genModels;

    if (!selectedModelId.value && genModels.length > 0) {
      // 检查是否有全局默认 image_generate 绑定
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

const filteredPresets = computed(() => {
  return presets.value.filter(
    (p) => !p.creation_mode || p.creation_mode === creationMode.value
  );
});

watch(creationMode, () => {
  if (selectedPresetId.value) {
    const cur = presets.value.find((p) => p.id === selectedPresetId.value);
    if (cur && cur.creation_mode && cur.creation_mode !== creationMode.value) {
      selectedPresetId.value = null;
    }
  }
});

async function loadPresets(): Promise<void> {
  loadingPresets.value = true;
  try {
    const list = await api.listCreationPresets(undefined as any, true);
    presets.value = list;

    // 如果未选预设且存在写实预设，默认推荐或保持 null
    if (selectedPresetId.value) {
      applyPresetDefaults(selectedPresetId.value);
    }
  } catch (err: any) {
    console.error("加载创作预设失败", err);
  } finally {
    loadingPresets.value = false;
  }
}

function selectPreset(id: number | null): void {
  if (selectedPresetId.value === id) {
    selectedPresetId.value = null;
    return;
  }
  selectedPresetId.value = id;
  if (id) applyPresetDefaults(id);
}

function applyPresetDefaults(presetId: number): void {
  const p = presets.value.find((item) => item.id === presetId);
  if (!p) return;
  // 若预设包含 negative_prompt 且当前为空，则自动补齐
  if (p.default_params?.negative_prompt && !negativePrompt.value) {
    negativePrompt.value = p.default_params.negative_prompt;
  }
  // 若预设指定了专属模型且当前模型可用
  if (p.default_model_profile_id && models.value.some((m) => m.id === p.default_model_profile_id)) {
    selectedModelId.value = p.default_model_profile_id;
  }
}

// ── 提示词智能润色 (V2-11) ──────────────────────────────────────────────
async function handleOptimizePrompt(): Promise<void> {
  if (!prompt.value.trim() || optimizing.value) return;
  optimizing.value = true;
  optimizeError.value = "";
  originalPromptBeforeOpt.value = prompt.value;

  try {
    const res = await api.optimizePrompt({
      prompt: prompt.value,
      preset_id: selectedPresetId.value,
      model_profile_id: undefined // 让后端自动解析 text_optimize 默认绑定
    });
    lastOptimizedResult.value = res;
    prompt.value = res.optimized_prompt;
  } catch (err: any) {
    optimizeError.value = err.message || "提示词润色失败，请确认已配置 text_optimize 默认模型";
  } finally {
    optimizing.value = false;
  }
}

function revertOptimization(): void {
  if (originalPromptBeforeOpt.value !== null) {
    prompt.value = originalPromptBeforeOpt.value;
    lastOptimizedResult.value = null;
    originalPromptBeforeOpt.value = null;
  }
}

// ── 多源参考图管理 (V2-12) ──────────────────────────────────────────────
function handleAddReference(item: SelectedReferenceItem): void {
  if (!references.value.some((r) => r.source_kind === item.source_kind && r.source_id === item.source_id)) {
    references.value.push(item);
  }
  showRefPicker.value = false;
}

function removeReference(index: number): void {
  references.value.splice(index, 1);
}

// ── 任务提交 ──────────────────────────────────────────────────────────
async function handleSubmit(): Promise<void> {
  const trimmed = prompt.value.trim();
  if (!trimmed) {
    errorMessage.value = "请输入创作提示词";
    return;
  }
  if (!selectedModelId.value) {
    errorMessage.value = "请先选择生图 AI 模型";
    return;
  }
  if (creationMode.value === "image_edit" && references.value.length === 0) {
    errorMessage.value = "图像编辑模式下请至少添加一张参考图像";
    return;
  }

  submitting.value = true;
  errorMessage.value = "";

  const payload: SubmitImageGeneratePayload = {
    task_type: creationMode.value,
    prompt: trimmed,
    model_profile_id: selectedModelId.value,
    preset_id: selectedPresetId.value,
    params: {
      size: selectedSize.value,
      aspect_ratio: selectedAspectRatio.value,
      n: generateCount.value,
      ...(selectedQuality.value ? { quality: selectedQuality.value } : {}),
      ...(selectedStyle.value ? { style: selectedStyle.value } : {}),
      ...(creationMode.value === "image_edit" && denoisingStrength.value !== null
        ? { denoising_strength: denoisingStrength.value }
        : {}),
      ...(negativePrompt.value.trim() ? { negative_prompt: negativePrompt.value.trim() } : {}),
      ...(seed.value !== null ? { seed: seed.value } : {})
    },
    reference_asset_ids: references.value.filter((r) => r.source_kind === "asset").map((r) => Number(r.source_id)),
    references: references.value.map((r) => ({
      source_kind: r.source_kind,
      source_id: r.source_id,
      role: r.role || "reference"
    })),
    raw_user_request: originalPromptBeforeOpt.value || trimmed,
    retry_of: props.initialRetryOf || null
  };

  try {
    const taskSummary = await api.submitImageGenerate(payload);
    emit("task-created", taskSummary);
    emit("close");
  } catch (err: any) {
    errorMessage.value = err.message || "提交生图任务失败";
  } finally {
    submitting.value = false;
  }
}
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
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-md"
        @click.self="emit('close')"
      >
        <div
          class="relative flex max-h-[92vh] w-full max-w-3xl flex-col rounded-2xl border border-line/80 bg-white/95 shadow-2xl backdrop-blur-xl transition-all"
        >
          <!-- 顶部标题栏 -->
          <div class="flex items-center justify-between border-b border-line/60 px-6 py-4">
            <div class="flex items-center gap-2.5">
              <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/10 text-accent">
                <SidebarIcon name="star" class="h-4 w-4" />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <h2 class="text-base font-semibold tracking-tight text-ink">AI 图像创作工作台</h2>
                  <span
                    v-if="initialRetryOf"
                    class="rounded-full bg-amber-100/80 px-2 py-0.5 text-[10.5px] font-medium text-amber-800 border border-amber-200/50"
                  >
                    衍生变体自 #{{ initialRetryOf.slice(-6) }}
                  </span>
                </div>
                <p class="text-[11px] text-muted">基于大语言模型润色与高精度生成模型创作视觉作品</p>
              </div>
            </div>

            <!-- 右侧模型选择器与关闭 -->
            <div class="flex items-center gap-3">
              <div class="flex items-center gap-2">
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

              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-lg text-muted transition hover:bg-black/5 hover:text-ink"
                @click="emit('close')"
              >
                <SidebarIcon name="close" class="h-4 w-4" />
              </button>
            </div>
          </div>

          <!-- 主体滚动表单内容 -->
          <div class="flex-1 space-y-5 overflow-y-auto px-6 py-5">
            <!-- 错误通知条 -->
            <div
              v-if="errorMessage"
              class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs text-rose-700"
            >
              {{ errorMessage }}
            </div>

            <!-- 模式切换：文生图 / 图生图与编辑 (V2-13) -->
            <div class="flex items-center gap-1.5 rounded-xl bg-canvas/60 p-1 border border-line/60">
              <button
                type="button"
                class="flex-1 flex items-center justify-center gap-2 rounded-lg py-1.5 text-xs font-medium transition"
                :class="creationMode === 'image_generate' ? 'bg-white text-ink shadow-sm font-semibold' : 'text-muted hover:text-ink'"
                @click="creationMode = 'image_generate'"
              >
                <span>🎨 文生图 (Text to Image)</span>
              </button>
              <button
                type="button"
                class="flex-1 flex items-center justify-center gap-2 rounded-lg py-1.5 text-xs font-medium transition"
                :class="creationMode === 'image_edit' ? 'bg-white text-ink shadow-sm font-semibold' : 'text-muted hover:text-ink'"
                @click="creationMode = 'image_edit'"
              >
                <span>🖼️ 图生图与编辑 (Image Edit)</span>
              </button>
            </div>

            <!-- 1. 创作风格预设选择器 (V2-11) -->
            <div>
              <div class="flex items-center justify-between pb-2">
                <label class="text-xs font-semibold text-ink">创作预设与风格</label>
                <span class="text-[11px] text-muted">
                  {{ activePreset ? activePreset.description : "选择预设将自动注入专业提示词与负向词" }}
                </span>
              </div>

              <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <button
                  type="button"
                  class="flex flex-col items-start gap-1 rounded-xl border p-2.5 text-left transition active:scale-98"
                  :class="
                    selectedPresetId === null
                      ? 'border-accent bg-accent/5 ring-1 ring-accent'
                      : 'border-line/80 bg-canvas/30 hover:bg-canvas/80 text-ink'
                  "
                  @click="selectPreset(null)"
                >
                  <span class="text-xs font-semibold">自由创作</span>
                  <span class="text-[10px] text-muted line-clamp-1">完全遵循原始输入</span>
                </button>

                <button
                  v-for="p in filteredPresets"
                  :key="p.id"
                  type="button"
                  class="flex flex-col items-start gap-1 rounded-xl border p-2.5 text-left transition active:scale-98"
                  :class="
                    selectedPresetId === p.id
                      ? 'border-accent bg-accent/5 ring-1 ring-accent'
                      : 'border-line/80 bg-canvas/30 hover:bg-canvas/80 text-ink'
                  "
                  @click="selectPreset(p.id)"
                >
                  <span class="text-xs font-semibold truncate w-full">{{ p.name }}</span>
                  <span class="text-[10px] text-muted line-clamp-1">{{ p.description || "专业调优预设" }}</span>
                </button>
              </div>
            </div>

            <!-- 2. 提示词输入区与一键润色 (V2-11) -->
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <label class="text-xs font-semibold text-ink">创作提示词 (Prompt)</label>
                  <span v-if="lastOptimizedResult" class="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                    已由 {{ lastOptimizedResult.model_name }} 润色
                  </span>
                </div>

                <!-- 润色与撤销按钮 -->
                <div class="flex items-center gap-2">
                  <button
                    v-if="originalPromptBeforeOpt"
                    type="button"
                    class="text-[11px] text-muted hover:text-ink transition"
                    @click="revertOptimization"
                  >
                    撤销润色
                  </button>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent transition hover:bg-accent/20 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="optimizing || !prompt.trim()"
                    @click="handleOptimizePrompt"
                  >
                    <SidebarIcon name="star" class="h-3 w-3" :class="optimizing ? 'animate-spin' : ''" />
                    <span>{{ optimizing ? "AI 润色中…" : "✨ 智能润色" }}</span>
                  </button>
                </div>
              </div>

              <div class="relative">
                <textarea
                  v-model="prompt"
                  rows="4"
                  placeholder="用中文或英文描述画面主体、光影氛围、镜头角度、细节质感等，例如：清晨云雾缭绕的高山茶园，露珠在阳光下闪烁，微距特写…"
                  class="w-full rounded-xl border border-line bg-canvas/20 p-3 text-xs leading-relaxed text-ink outline-none transition placeholder:text-muted/60 focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/10"
                />
              </div>

              <div v-if="optimizeError" class="text-[11px] text-rose-600">
                {{ optimizeError }}
              </div>
            </div>

            <!-- 3. 参考图与角色标注 (V2-12) -->
            <div class="border-t border-line/60 pt-3">
              <div class="flex items-center justify-between pb-2">
                <div class="flex items-center gap-1.5">
                  <label class="text-xs font-semibold text-ink">参考图与角色标注</label>
                  <span class="text-[11px] text-muted">({{ references.length }} 张)</span>
                </div>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink transition hover:border-accent hover:text-accent active:scale-95"
                  @click="showRefPicker = true"
                >
                  <SidebarIcon name="plus" class="h-3 w-3" />
                  <span>添加参考图</span>
                </button>
              </div>

              <!-- 参考图列表 -->
              <div v-if="references.length > 0" class="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div
                  v-for="(refItem, idx) in references"
                  :key="`${refItem.source_kind}_${refItem.source_id}`"
                  class="flex items-center gap-2.5 rounded-xl border border-line/80 bg-canvas/30 p-2 transition hover:bg-white"
                >
                  <div class="relative h-12 w-12 flex-shrink-0 overflow-hidden rounded-lg border border-line/60 bg-canvas">
                    <img :src="refItem.preview_url" :alt="refItem.name" class="h-full w-full object-cover" />
                  </div>

                  <div class="min-w-0 flex-1">
                    <div class="truncate text-xs font-medium text-ink" :title="refItem.name">{{ refItem.name }}</div>
                    <div class="mt-1 flex items-center gap-1.5">
                      <span
                        class="rounded px-1.5 py-0.5 text-[10px] font-medium"
                        :class="{
                          'bg-blue-50 text-blue-600': refItem.source_kind === 'asset',
                          'bg-purple-50 text-purple-600': refItem.source_kind === 'history_result',
                          'bg-emerald-50 text-emerald-600': refItem.source_kind === 'local_upload'
                        }"
                      >
                        {{ refItem.source_kind === 'asset' ? '主库' : refItem.source_kind === 'history_result' ? '历史' : '本地' }}
                      </span>

                      <div class="w-28">
                        <AppleSelect
                          v-model="refItem.role"
                          size="sm"
                          :options="refRoleOptions"
                        />
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    class="rounded p-1 text-muted transition hover:bg-rose-50 hover:text-rose-600 active:scale-90"
                    title="移除参考图"
                    @click="removeReference(idx)"
                  >
                    <SidebarIcon name="close" class="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <!-- 4. 画幅比例与生成规格 (V2-13 动态参数适配) -->
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label class="block text-xs font-semibold text-ink pb-1.5">画面画幅比例</label>
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="ar in supportedAspectRatios"
                    :key="ar"
                    type="button"
                    class="rounded-lg border px-3 py-1.5 text-xs font-medium transition active:scale-95"
                    :class="
                      selectedAspectRatio === ar
                        ? 'border-accent bg-accent/10 text-accent font-semibold'
                        : 'border-line bg-white hover:bg-canvas/50 text-ink'
                    "
                    @click="selectedAspectRatio = ar"
                  >
                    {{ ar }}
                  </button>
                </div>
              </div>

              <div>
                <label class="block text-xs font-semibold text-ink pb-1.5">分辨率规格</label>
                <AppleSelect
                  v-model="selectedSize"
                  size="sm"
                  :options="sizeOptions"
                />
              </div>

              <!-- 动态参数：画质选项（如 DALL-E 3 standard/hd） -->
              <div v-if="supportedQualities.length > 0">
                <label class="block text-xs font-semibold text-ink pb-1.5">生成画质</label>
                <AppleSelect
                  v-model="selectedQuality"
                  size="sm"
                  :options="qualityOptions"
                />
              </div>

              <!-- 动态参数：风格倾向（如 DALL-E 3 vivid/natural） -->
              <div v-if="supportedStyles.length > 0">
                <label class="block text-xs font-semibold text-ink pb-1.5">风格偏好</label>
                <AppleSelect
                  v-model="selectedStyle"
                  size="sm"
                  :options="styleOptions"
                />
              </div>
            </div>

            <!-- 5. 高级参数抽屉（负向词、生成批次、重绘强度、随机种子） -->
            <div class="border-t border-line/60 pt-3">
              <button
                type="button"
                class="flex items-center gap-1.5 text-xs font-medium text-muted hover:text-ink transition"
                @click="showAdvanced = !showAdvanced"
              >
                <SidebarIcon
                  name="chevron-right"
                  class="h-3.5 w-3.5 transition-transform"
                  :class="showAdvanced ? 'rotate-90' : ''"
                />
                <span>高级生成选项 (负向词、数量、重绘强度、种子)</span>
              </button>

              <div v-show="showAdvanced" class="mt-3 space-y-3 pl-4">
                <div v-if="creationMode === 'image_edit'">
                  <label class="block text-xs font-medium text-muted pb-1">
                    重绘/参考强度 (Denoising Strength): {{ denoisingStrength }}
                  </label>
                  <input
                    v-model.number="denoisingStrength"
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    class="h-2 w-full cursor-pointer accent-accent"
                  />
                  <div class="flex justify-between text-[10px] text-muted">
                    <span>0.1 (微弱重绘，严格保留原图)</span>
                    <span>1.0 (大幅重绘，仅参考构图)</span>
                  </div>
                </div>

                <div>
                  <label class="block text-xs font-medium text-muted pb-1">负向提示词 (Negative Prompt)</label>
                  <input
                    v-model="negativePrompt"
                    type="text"
                    placeholder="不希望出现在画面中的元素，如：blurry, low quality, bad anatomy, distorted…"
                    class="w-full rounded-xl border border-line bg-canvas/20 px-3 py-2 text-xs text-ink outline-none transition placeholder:text-muted/50 focus:border-accent focus:bg-white"
                  />
                </div>

                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-xs font-medium text-muted pb-1">生成张数</label>
                    <div class="flex gap-1.5">
                      <button
                        v-for="n in [1, 2, 4]"
                        :key="n"
                        type="button"
                        class="flex-1 rounded-lg border py-1 text-xs font-medium transition"
                        :class="generateCount === n ? 'border-accent bg-accent/10 text-accent' : 'border-line bg-white text-ink'"
                        @click="generateCount = n"
                      >
                        {{ n }} 张
                      </button>
                    </div>
                  </div>

                  <div>
                    <label class="block text-xs font-medium text-muted pb-1">随机种子 (可选)</label>
                    <input
                      v-model.number="seed"
                      type="number"
                      placeholder="默认留空随机"
                      class="h-8 w-full rounded-lg border border-line bg-canvas/20 px-2.5 text-xs text-ink outline-none transition focus:border-accent focus:bg-white"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 底部提交操作栏 -->
          <div class="flex items-center justify-between border-t border-line/60 bg-canvas/30 px-6 py-4">
            <div class="text-[11px] text-muted">
              <span v-if="activeModel">将由 <span class="font-medium text-ink">{{ activeModel.name }}</span> 执行</span>
              <span v-else class="text-amber-600">未选择可用生图模型</span>
            </div>

            <div class="flex items-center gap-2.5">
              <button
                type="button"
                class="rounded-xl border border-line bg-white px-4 py-2 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
                @click="emit('close')"
              >
                取消
              </button>

              <button
                type="button"
                class="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2 text-xs font-medium text-white shadow-sm transition hover:bg-blue-700 active:scale-97 disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="submitting || !prompt.trim() || !selectedModelId"
                @click="handleSubmit"
              >
                <SidebarIcon name="star" class="h-3.5 w-3.5" :class="submitting ? 'animate-spin' : ''" />
                <span>{{ submitting ? "提交任务中…" : "开始生成" }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <AiReferencePickerModal
      :open="showRefPicker"
      @close="showRefPicker = false"
      @pick="handleAddReference"
    />
  </Teleport>
</template>
