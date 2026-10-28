<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type {
  AiCreationPreset,
  AiModelProfile,
  SubmitImageGeneratePayload
} from "../api/types";
import AiReferencePickerModal, { type SelectedReferenceItem } from "./AiReferencePickerModal.vue";
import AiWorkbenchAdvancedDrawer from "./AiWorkbenchAdvancedDrawer.vue";
import SidebarIcon from "./SidebarIcon.vue";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";
import { usePromptOptimize } from "../composables/usePromptOptimize";
import {
  findBestRatioForSize,
  getAspectRatioHint,
  getAspectRatioLabel,
  matchSizeRatio,
  STANDARD_ASPECT_RATIOS
} from "../utils/aiDimensions";
import { api } from "../api/client";

const props = defineProps<{
  models: AiModelProfile[];
  presets: AiCreationPreset[];
  selectedModelId: number | null;
  loadingModels?: boolean;
  initialPrompt?: string;
  initialPresetId?: number;
  initialReferenceAssetIds?: number[];
  initialMode?: "image_generate" | "image_edit";
  initialParams?: Record<string, any>;
  initialReferences?: SelectedReferenceItem[];
  initialRetryOf?: string;
  submitting?: boolean;
}>();

const emit = defineEmits<{
  (e: "update:selectedModelId", id: number | null): void;
  (e: "submit", payload: SubmitImageGeneratePayload): void;
  (e: "cancel"): void;
}>();

// 基础模式与表单字段
const creationMode = ref<"image_generate" | "image_edit">("image_generate");
const selectedPresetId = ref<number | null>(null);
const prompt = ref("");
const negativePrompt = ref("");
const selectedAspectRatio = ref("1:1");
const selectedSize = ref("1024x1024");
const selectedQuality = ref("standard");
const selectedStyle = ref("");
const denoisingStrength = ref<number | null>(0.7);
const generateCount = ref(1);
const seed = ref<number | null>(null);
const errorMessage = ref("");

// 参考图与智能润色
const showRefPicker = ref(false);
const references = ref<SelectedReferenceItem[]>([]);
const optimizeLanguage = ref<"zh" | "en">("zh");
const {
  optimizing,
  optimizeError,
  lastOptimizedResult,
  originalPromptBeforeOpt,
  optimizePrompt: doOptimizePrompt,
  revertOptimization: doRevertOptimization,
  resetOptimizeState
} = usePromptOptimize();

// ── 计算属性 ──────────────────────────────────────────────────────────
const activeModel = computed(() => {
  return props.models.find((m) => m.id === props.selectedModelId) || null;
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

const supportedSizes = computed(() => {
  const caps = activeModelCapabilities.value;
  if (caps?.supported_sizes && caps.supported_sizes.length > 0) {
    return caps.supported_sizes as string[];
  }
  return ["1024x1024", "1024x768", "768x1024", "1280x720", "720x1280"];
});

const supportedAspectRatios = computed(() => {
  const caps = activeModelCapabilities.value;
  if (caps?.supported_aspect_ratios && caps.supported_aspect_ratios.length > 0) {
    return caps.supported_aspect_ratios as string[];
  }
  if (supportedSizes.value.length > 0) {
    const derived = new Set<string>();
    for (const sz of supportedSizes.value) {
      const r = findBestRatioForSize(sz, [...STANDARD_ASPECT_RATIOS]);
      if (r) derived.add(r);
    }
    if (derived.size > 0) {
      return STANDARD_ASPECT_RATIOS.filter((c) => derived.has(c));
    }
  }
  return [...STANDARD_ASPECT_RATIOS];
});

const filteredSizes = computed(() => {
  const list = supportedSizes.value.filter((sz) =>
    matchSizeRatio(sz, selectedAspectRatio.value)
  );
  return list.length > 0 ? list : supportedSizes.value;
});

const sizeOptions = computed<AppleSelectOption[]>(() =>
  filteredSizes.value.map((sz) => {
    const r = findBestRatioForSize(sz, supportedAspectRatios.value);
    const badgeColor: "blue" | "rose" | "emerald" | "amber" | "zinc" =
      r === "16:9" ? "blue" : r === "9:16" ? "rose" : r === "1:1" ? "emerald" : r === "4:3" ? "amber" : "zinc";
    return {
      value: sz,
      label: sz,
      subLabel: r ? `${getAspectRatioLabel(r)} (${r})` : undefined,
      badge: r || undefined,
      badgeColor
    };
  })
);

function selectAspectRatio(ar: string): void {
  selectedAspectRatio.value = ar;
  const matched = supportedSizes.value.filter((sz) => matchSizeRatio(sz, ar));
  if (matched.length > 0 && !matchSizeRatio(selectedSize.value, ar)) {
    selectedSize.value = matched[0];
  }
}

watch(selectedSize, (newSize) => {
  if (!newSize) return;
  const best = findBestRatioForSize(newSize, supportedAspectRatios.value);
  if (best && best !== selectedAspectRatio.value) {
    selectedAspectRatio.value = best;
  }
});

const qualityOptions = computed<AppleSelectOption[]>(() =>
  supportedQualities.value.map((q) => ({
    value: q,
    label: q === "hd" ? "高精超清 (HD)" : q === "standard" ? "标准画质 (Standard)" : q,
    badge: q.toUpperCase(),
    badgeColor: (q === "hd" ? "blue" : "zinc") as "blue" | "zinc"
  }))
);

const styleOptions = computed<AppleSelectOption[]>(() =>
  supportedStyles.value.map((st) => ({
    value: st,
    label: st === "vivid" ? "生动鲜明 (Vivid)" : st === "natural" ? "真实自然 (Natural)" : st,
    badge: st,
    badgeColor: (st === "vivid" ? "amber" : "emerald") as "amber" | "emerald"
  }))
);

const refRoleOptions: AppleSelectOption[] = [
  { value: "reference", label: "综合参考", badge: "综合", badgeColor: "zinc" },
  { value: "style", label: "风格参考", badge: "风格", badgeColor: "accent" },
  { value: "character", label: "角色主体", badge: "主体", badgeColor: "blue" },
  { value: "composition", label: "构图布局", badge: "构图", badgeColor: "amber" }
];

const filteredPresets = computed(() => {
  return props.presets.filter(
    (p) => !p.creation_mode || p.creation_mode === creationMode.value
  );
});

const activePreset = computed(() => props.presets.find((p) => p.id === selectedPresetId.value) || null);

// 初始化参数监听
watch(
  () => [props.initialPrompt, props.initialPresetId, props.initialMode, props.initialParams, props.initialReferences],
  async () => {
    resetOptimizeState();
    errorMessage.value = "";

    if (props.initialMode) {
      creationMode.value = props.initialMode;
    } else if (props.initialReferenceAssetIds && props.initialReferenceAssetIds.length > 0) {
      creationMode.value = "image_edit";
    }

    if (props.initialPrompt !== undefined) prompt.value = props.initialPrompt;
    if (props.initialPresetId !== undefined) selectedPresetId.value = props.initialPresetId;
    if (props.initialParams) {
      if (props.initialParams.size) selectedSize.value = props.initialParams.size;
      if (props.initialParams.aspect_ratio) selectedAspectRatio.value = props.initialParams.aspect_ratio;
      if (props.initialParams.quality) selectedQuality.value = props.initialParams.quality;
      if (props.initialParams.style) selectedStyle.value = props.initialParams.style;
      if (props.initialParams.denoising_strength !== undefined) denoisingStrength.value = props.initialParams.denoising_strength;
      if (props.initialParams.seed !== undefined) seed.value = props.initialParams.seed;
      if (props.initialParams.negative_prompt) negativePrompt.value = props.initialParams.negative_prompt;
    }
    if (props.initialReferences?.length) {
      references.value = [...props.initialReferences];
    }
    if (props.initialReferenceAssetIds?.length) {
      for (const aid of props.initialReferenceAssetIds) {
        if (!references.value.some((r) => r.source_kind === "asset" && r.source_id === String(aid))) {
          const url = await api.fetchThumbnailObjectUrl(aid).catch(() => "");
          references.value.push({
            source_kind: "asset",
            source_id: String(aid),
            preview_url: url,
            name: `资产 #${aid}`,
            role: "reference"
          });
        }
      }
    }
  },
  { immediate: true }
);

function applyPresetDefaults(presetId: number): void {
  const p = props.presets.find((item) => item.id === presetId);
  if (!p) return;
  if (p.default_params) {
    if (p.default_params.negative_prompt && !negativePrompt.value) {
      negativePrompt.value = p.default_params.negative_prompt;
    }
    if (p.default_params.aspect_ratio) selectedAspectRatio.value = p.default_params.aspect_ratio;
    if (p.default_params.size) selectedSize.value = p.default_params.size;
    if (p.default_params.quality) selectedQuality.value = p.default_params.quality;
    if (p.default_params.style) selectedStyle.value = p.default_params.style;
    if (p.default_params.denoising_strength !== undefined) denoisingStrength.value = p.default_params.denoising_strength;
  }
  if (p.default_model_profile_id && props.models.some((m) => m.id === p.default_model_profile_id)) {
    emit("update:selectedModelId", p.default_model_profile_id);
  }
}

async function handleOptimizePrompt(): Promise<void> {
  const optimized = await doOptimizePrompt(prompt.value, selectedPresetId.value, optimizeLanguage.value);
  if (optimized) {
    prompt.value = optimized;
  }
}

function revertOptimization(): void {
  const orig = doRevertOptimization();
  if (orig !== null) {
    prompt.value = orig;
  }
}

function handleAddReference(item: SelectedReferenceItem): void {
  if (!references.value.some((r) => r.source_kind === item.source_kind && r.source_id === item.source_id)) {
    references.value.push(item);
  }
  showRefPicker.value = false;
}

function removeReference(index: number): void {
  references.value.splice(index, 1);
}

function handleFormSubmit(): void {
  const trimmed = prompt.value.trim();
  if (!trimmed) {
    errorMessage.value = "请输入创作提示词";
    return;
  }
  if (!props.selectedModelId) {
    errorMessage.value = "请先选择生图 AI 模型";
    return;
  }
  if (creationMode.value === "image_edit" && references.value.length === 0) {
    errorMessage.value = "图像编辑模式下请至少添加一张参考图像";
    return;
  }

  errorMessage.value = "";
  const payload: SubmitImageGeneratePayload = {
    task_type: creationMode.value,
    prompt: trimmed,
    model_profile_id: props.selectedModelId,
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

  emit("submit", payload);
}
</script>

<template>
  <div class="flex flex-1 flex-col overflow-hidden">
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
          <span>🖼️ 参考图编辑 / 图生图</span>
        </button>
      </div>

      <!-- 2. 创作预设选择器 (V2-10) -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <label class="text-xs font-semibold text-ink">风格预设模板</label>
          <span v-if="activePreset" class="text-[11px] text-accent">
            已应用：{{ activePreset.name }}
          </span>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <button
            type="button"
            class="flex flex-col items-start rounded-xl border p-2.5 text-left transition active:scale-97"
            :class="selectedPresetId === null ? 'border-accent bg-accent/5 ring-1 ring-accent' : 'border-line/70 bg-white hover:border-line'"
            @click="selectedPresetId = null"
          >
            <span class="text-xs font-medium text-ink">自由发挥</span>
            <span class="mt-0.5 text-[10.5px] text-muted line-clamp-1">不附加特定预设风格</span>
          </button>

          <button
            v-for="p in filteredPresets"
            :key="p.id"
            type="button"
            class="group relative flex flex-col items-start rounded-xl border p-2.5 text-left transition active:scale-97"
            :class="selectedPresetId === p.id ? 'border-accent bg-accent/5 ring-1 ring-accent' : 'border-line/70 bg-white hover:border-line'"
            @click="selectedPresetId = p.id; applyPresetDefaults(p.id)"
          >
            <div class="flex w-full items-center justify-between">
              <span class="text-xs font-medium text-ink group-hover:text-accent transition">{{ p.name }}</span>
              <span v-if="p.is_builtin" class="rounded bg-canvas px-1 py-0.2 text-[9.5px] text-muted">内置</span>
            </div>
            <span class="mt-0.5 text-[10.5px] text-muted line-clamp-1">{{ p.description }}</span>
          </button>
        </div>
      </div>

      <!-- 3. 提示词输入与智能润色 (V2-11) -->
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

            <!-- 润色语言版本切换 (中文默认 / 英文) -->
            <div class="inline-flex items-center rounded-lg border border-line bg-canvas/60 p-0.5 text-[11px]">
              <button
                type="button"
                class="rounded-md px-1.5 py-0.5 font-medium transition"
                :class="optimizeLanguage === 'zh' ? 'bg-white text-ink shadow-xs' : 'text-muted hover:text-ink'"
                :disabled="optimizing"
                title="输出专业中文提示词"
                @click="optimizeLanguage = 'zh'"
              >
                中文
              </button>
              <button
                type="button"
                class="rounded-md px-1.5 py-0.5 font-medium transition"
                :class="optimizeLanguage === 'en' ? 'bg-white text-ink shadow-xs' : 'text-muted hover:text-ink'"
                :disabled="optimizing"
                title="输出英文生图提示词"
                @click="optimizeLanguage = 'en'"
              >
                EN
              </button>
            </div>

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

      <!-- 4. 参考图与角色标注 (V2-12) -->
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

        <div v-if="references.length === 0" class="rounded-xl border border-dashed border-line/80 py-4 text-center">
          <p class="text-xs text-muted">暂未添加参考图像（文生图可留空；图生图与编辑需至少添加一张）</p>
        </div>

        <div v-else class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <div
            v-for="(refItem, idx) in references"
            :key="`${refItem.source_kind}-${refItem.source_id}-${idx}`"
            class="group relative flex flex-col overflow-hidden rounded-xl border border-line/80 bg-white shadow-xs"
          >
            <div class="relative aspect-video w-full overflow-hidden bg-canvas">
              <img
                v-if="refItem.preview_url"
                :src="refItem.preview_url"
                :alt="refItem.name || '参考图'"
                class="h-full w-full object-cover transition duration-200 group-hover:scale-105"
              />
              <div v-else class="flex h-full w-full items-center justify-center text-[10px] text-muted">
                无缩略图
              </div>

              <button
                type="button"
                class="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white opacity-0 transition group-hover:opacity-100 hover:bg-rose-600"
                @click="removeReference(idx)"
              >
                <SidebarIcon name="close" class="h-3 w-3" />
              </button>
            </div>

            <div class="p-2 space-y-1">
              <div class="text-[11px] font-medium text-ink truncate">{{ refItem.name || `参考 #${refItem.source_id}` }}</div>
              <div class="w-full">
                <AppleSelect
                  v-model="refItem.role"
                  size="sm"
                  :options="refRoleOptions"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 5. 画面规格与动态参数配置 -->
      <div class="border-t border-line/60 pt-3 space-y-3">
        <!-- 比例胶囊选择器 -->
        <div>
          <div class="flex items-center justify-between pb-1.5">
            <label class="text-xs font-semibold text-ink">画面宽高比例 (Aspect Ratio)</label>
            <span class="text-[11px] text-muted font-mono">
              {{ selectedAspectRatio }} · {{ getAspectRatioHint(selectedAspectRatio) }}
            </span>
          </div>
          <div class="grid grid-cols-4 sm:grid-cols-7 gap-1.5">
            <button
              v-for="ar in supportedAspectRatios"
              :key="ar"
              type="button"
              class="flex flex-col items-center justify-center rounded-xl border py-1.5 px-1 text-center transition active:scale-95"
              :class="selectedAspectRatio === ar ? 'border-accent bg-accent/10 font-semibold text-accent ring-1 ring-accent' : 'border-line/70 bg-white text-ink/80 hover:border-line'"
              @click="selectAspectRatio(ar)"
            >
              <span class="font-mono text-xs">{{ ar }}</span>
              <span class="text-[9.5px] text-muted mt-0.5">{{ getAspectRatioLabel(ar) }}</span>
            </button>
          </div>
        </div>

        <!-- 尺寸规格与画质风格 -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <div class="flex items-center justify-between pb-1.5">
              <label class="text-xs font-semibold text-ink">分辨率规格</label>
              <span class="text-[11px] text-muted font-mono">联动 {{ selectedAspectRatio }}</span>
            </div>
            <AppleSelect v-model="selectedSize" size="sm" :options="sizeOptions" />
          </div>

          <div v-if="supportedQualities.length > 0">
            <label class="block text-xs font-semibold text-ink pb-1.5">生成画质</label>
            <AppleSelect v-model="selectedQuality" size="sm" :options="qualityOptions" />
          </div>

          <div v-if="supportedStyles.length > 0">
            <label class="block text-xs font-semibold text-ink pb-1.5">风格偏好</label>
            <AppleSelect v-model="selectedStyle" size="sm" :options="styleOptions" />
          </div>
        </div>
      </div>

      <!-- 6. 高级参数抽屉（负向词、生成批次、重绘强度、随机种子） -->
      <AiWorkbenchAdvancedDrawer
        :creation-mode="creationMode"
        v-model:denoising-strength="denoisingStrength"
        v-model:negative-prompt="negativePrompt"
        v-model:generate-count="generateCount"
        v-model:seed="seed"
      />
    </div>

    <!-- 底部固定提交操作栏 -->
    <div class="flex items-center justify-between border-t border-line/60 bg-canvas/30 px-6 py-4">
      <div class="text-[11px] text-muted">
        <span v-if="activeModel">将由 <span class="font-medium text-ink">{{ activeModel.name }}</span> 执行</span>
        <span v-else class="text-amber-600">未选择可用生图模型</span>
      </div>

      <div class="flex items-center gap-2.5">
        <button
          type="button"
          class="rounded-xl border border-line bg-white px-4 py-2 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
          @click="emit('cancel')"
        >
          取消
        </button>

        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2 text-xs font-medium text-white shadow-sm transition hover:bg-blue-700 active:scale-97 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="submitting || !prompt.trim() || !selectedModelId"
          @click="handleFormSubmit"
        >
          <SidebarIcon name="star" class="h-3.5 w-3.5" :class="submitting ? 'animate-spin' : ''" />
          <span>{{ submitting ? "提交任务中…" : "开始生成" }}</span>
        </button>
      </div>
    </div>

    <!-- 挂载参考图选择器 -->
    <AiReferencePickerModal
      :open="showRefPicker"
      @close="showRefPicker = false"
      @pick="handleAddReference"
    />
  </div>
</template>
