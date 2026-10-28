<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";
import type {
  AiCapabilityType,
  AiDefaultBinding,
  AiModelProfile,
  AiModelProfileCreatePayload,
  AiProviderInstance,
  AiRemoteModelItem
} from "../api/types";
import SidebarIcon from "./SidebarIcon.vue";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";
import type { ConfirmRequest } from "../composables/useConfirmDialog";
import { notify } from "../stores/library";

const props = defineProps<{
  providers: AiProviderInstance[];
  onAskConfirm?: (request: ConfirmRequest) => void;
}>();

const models = ref<AiModelProfile[]>([]);
const defaults = ref<AiDefaultBinding[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

// 添加模型弹层
const showAddModel = ref(false);
const selectedProviderId = ref<number | null>(null);
const remoteModels = ref<AiRemoteModelItem[]>([]);
const fetchingRemoteModels = ref(false);
const remoteModelsError = ref<string | null>(null);
const manualInputMode = ref(false);

const modelForm = ref<AiModelProfileCreatePayload>({
  model_id: "",
  name: "",
  adapter_kind: "openai_standard",
  enabled: true,
  capabilities: {
    text_optimize: { supported: false },
    image_understand: { supported: false },
    image_generate: { supported: false },
    image_edit: { supported: false }
  }
});
const saving = ref(false);
const saveError = ref<string | null>(null);

async function loadData(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [mList, dList] = await Promise.all([
      api.listAllModels(),
      api.listDefaultBindings()
    ]);
    models.value = mList;
    defaults.value = dList;
  } catch (err: any) {
    error.value = err.message || "加载模型及默认策略失败";
  } finally {
    loading.value = false;
  }
}

async function fetchRemoteModels(providerId: number | null): Promise<void> {
  if (!providerId) {
    remoteModels.value = [];
    return;
  }
  fetchingRemoteModels.value = true;
  remoteModelsError.value = null;
  try {
    const list = await api.getProviderRemoteModels(providerId);
    remoteModels.value = list;
    if (list.length === 0) {
      manualInputMode.value = true;
    } else {
      manualInputMode.value = false;
    }
  } catch (err: any) {
    remoteModels.value = [];
    remoteModelsError.value = err.message || "无法自动获取远程模型列表";
    manualInputMode.value = true;
  } finally {
    fetchingRemoteModels.value = false;
  }
}

function formatDisplayName(modelId: string): string {
  const clean = modelId.trim();
  const lower = clean.toLowerCase();

  if (lower === "dall-e-3") return "DALL-E 3 高清生图";
  if (lower === "dall-e-2") return "DALL-E 2 生图/编辑";
  if (lower === "gpt-4o") return "GPT-4o 旗舰多模态";
  if (lower === "gpt-4o-mini") return "GPT-4o mini 智能优化";
  if (lower === "gpt-4-turbo") return "GPT-4 Turbo";
  if (lower.startsWith("gemini-1.5-pro")) return "Gemini 1.5 Pro 多模态";
  if (lower.startsWith("gemini-1.5-flash")) return "Gemini 1.5 Flash 极速推理";
  if (lower.startsWith("imagen-3")) return "Google Imagen 3 原生生图";
  if (lower.includes("flux-schnell")) return "FLUX Schnell 极速生图";
  if (lower.includes("flux-dev")) return "FLUX.1 Dev 高质量生图";
  if (lower.includes("claude-3-5-sonnet")) return "Claude 3.5 Sonnet";
  if (lower.includes("deepseek-chat") || lower.includes("deepseek-v3")) return "DeepSeek V3 智能思考";
  if (lower.includes("deepseek-reasoner") || lower.includes("deepseek-r1")) return "DeepSeek R1 深度推理";

  // 默认美化分词
  const parts = clean.split(/[-_]/);
  if (parts.length > 1) {
    return parts.map((seg) => (seg ? seg.charAt(0).toUpperCase() + seg.slice(1) : "")).join(" ");
  }
  return clean;
}

function autoDetectCapabilities(modelId: string): void {
  const lower = modelId.toLowerCase();
  const provider = props.providers.find((p) => p.id === selectedProviderId.value);

  // 1. 适配器协议推断
  if (provider?.family === "gemini_native") {
    modelForm.value.adapter_kind = "gemini_standard";
  } else if (
    lower.includes("dall-e") ||
    lower.includes("flux") ||
    lower.includes("imagen") ||
    lower.includes("stable-diffusion") ||
    lower.includes("midjourney")
  ) {
    modelForm.value.adapter_kind = "openai_standard";
  } else if (lower.includes("gemini") && provider?.family === "openai_compatible") {
    if (lower.includes("image") || lower.includes("draw")) {
      modelForm.value.adapter_kind = "openai_chat_markdown";
    }
  }

  // 2. 能力声明推断
  const caps = modelForm.value.capabilities!;
  caps.text_optimize.supported = false;
  caps.image_understand.supported = false;
  caps.image_generate.supported = false;
  caps.image_edit.supported = false;

  const isImageGen =
    lower.includes("dall-e") ||
    lower.includes("imagen") ||
    lower.includes("flux") ||
    lower.includes("stable-diffusion") ||
    lower.includes("midjourney") ||
    lower.includes("sdxl") ||
    lower.includes("cogview") ||
    lower.includes("recraft") ||
    lower.includes("kolors") ||
    lower.includes("image") ||
    lower.includes("draw");

  if (isImageGen) {
    caps.image_generate.supported = true;
    if (lower === "dall-e-2" || lower.includes("edit") || lower.includes("inpaint")) {
      caps.image_edit.supported = true;
    }
  }

  const isVision =
    lower.includes("gpt-4o") ||
    lower.includes("vision") ||
    lower.includes("vl") ||
    lower.includes("gemini-1.5") ||
    lower.includes("gemini-2") ||
    lower.includes("claude-3") ||
    lower.includes("qwen-vl") ||
    lower.includes("minicpm") ||
    lower.includes("omni");

  if (isVision) {
    caps.image_understand.supported = true;
  }

  const isChatLlm =
    lower.includes("gpt") ||
    lower.includes("claude") ||
    lower.includes("gemini") ||
    lower.includes("deepseek") ||
    lower.includes("qwen") ||
    lower.includes("glm") ||
    lower.includes("chat") ||
    lower.includes("instruct") ||
    lower.includes("llama") ||
    lower.includes("mistral");

  if (isChatLlm) {
    caps.text_optimize.supported = true;
  }

  // 兜底保障
  if (
    !caps.text_optimize.supported &&
    !caps.image_understand.supported &&
    !caps.image_generate.supported &&
    !caps.image_edit.supported
  ) {
    caps.image_generate.supported = true;
  }
}

const providerOptions = computed<AppleSelectOption[]>(() => {
  return props.providers.map((p) => ({
    value: p.id,
    label: p.name,
    subLabel: p.base_url,
    badge: p.enabled ? "已启用" : "已停用",
    badgeColor: p.enabled ? "emerald" : "zinc"
  }));
});

const remoteModelOptions = computed<AppleSelectOption[]>(() => {
  return remoteModels.value.map((rm) => {
    const lower = rm.id.toLowerCase();
    let badge = "文本LLM";
    let badgeColor: "emerald" | "blue" | "accent" | "zinc" = "zinc";
    if (lower.includes("image") || lower.includes("dall-e") || lower.includes("flux") || lower.includes("draw")) {
      badge = "图片生成";
      badgeColor = "emerald";
    } else if (
      lower.includes("vision") ||
      lower.includes("vl") ||
      lower.includes("gemini") ||
      lower.includes("4o") ||
      lower.includes("minicpm")
    ) {
      badge = "多模态视觉";
      badgeColor = "blue";
    }

    return {
      value: rm.id,
      label: rm.id,
      subLabel: rm.name && rm.name !== rm.id ? rm.name : undefined,
      badge,
      badgeColor
    };
  });
});

const adapterOptions: AppleSelectOption[] = [
  {
    value: "openai_standard",
    label: "OpenAI 标准协议 (通用对话 + /images/generations)",
    subLabel: "对话与反推走 /chat/completions，生图走标准 /images/generations",
    badge: "通用推荐",
    badgeColor: "emerald"
  },
  {
    value: "openai_chat_markdown",
    label: "Chat 嵌入图协议 (Markdown 图片链接提取)",
    subLabel: "适用于通过 /chat/completions 对话并在回复中提取图片链接的模型",
    badge: "Chat出图",
    badgeColor: "blue"
  },
  {
    value: "gemini_standard",
    label: "Gemini 原生协议 (Google 原生 Imagen/Vision)",
    subLabel: "调用 Google Gemini 原生 REST 端点",
    badge: "原生",
    badgeColor: "amber"
  },
  {
    value: "custom",
    label: "通用自定义适配器",
    subLabel: "用于扩展其它非标接口",
    badge: "扩展",
    badgeColor: "zinc"
  }
];

function getDefaultModelOptions(capKey: string): AppleSelectOption[] {
  return models.value
    .filter((item) => item.capabilities[capKey]?.supported)
    .map((m) => ({
      value: m.id,
      label: m.name,
      subLabel: m.model_id,
      badge: m.adapter_kind,
      badgeColor: "zinc"
    }));
}

function onSelectRemoteModel(modelId: string | number): void {
  if (!modelId) return;
  const strId = String(modelId);
  modelForm.value.model_id = strId;
  const found = remoteModels.value.find((m) => m.id === strId);

  // 1. 自动填充显示名称
  if (found && found.name && found.name !== strId) {
    modelForm.value.name = found.name;
  } else {
    modelForm.value.name = formatDisplayName(strId);
  }

  // 2. 自动检测并推导适配器与能力
  autoDetectCapabilities(strId);
}

function onManualInputModelId(): void {
  if (!modelForm.value.name.trim() && modelForm.value.model_id.trim()) {
    modelForm.value.name = formatDisplayName(modelForm.value.model_id);
    autoDetectCapabilities(modelForm.value.model_id);
  }
}

function openAddModel(providerId?: number): void {
  saveError.value = null;
  const pId = providerId || props.providers[0]?.id || null;
  selectedProviderId.value = pId;
  manualInputMode.value = false;
  modelForm.value = {
    model_id: "",
    name: "",
    adapter_kind: "openai_standard",
    enabled: true,
    capabilities: {
      text_optimize: { supported: false },
      image_understand: { supported: false },
      image_generate: { supported: true },
      image_edit: { supported: false }
    }
  };
  showAddModel.value = true;
  if (pId) {
    void fetchRemoteModels(pId);
  }
}

async function handleSaveModel(): Promise<void> {
  if (!selectedProviderId.value) {
    saveError.value = "请选择所属 Provider 连接";
    return;
  }
  if (!modelForm.value.model_id.trim()) {
    saveError.value = "请填写 Model ID（例如：gpt-4o-mini 或 dall-e-3）";
    return;
  }
  if (!modelForm.value.name.trim()) {
    saveError.value = "请填写模型显示名称";
    return;
  }

  saving.value = true;
  saveError.value = null;
  try {
    await api.createModelProfile(selectedProviderId.value, modelForm.value);
    showAddModel.value = false;
    await loadData();
  } catch (err: any) {
    saveError.value = err.message || "保存模型配置失败";
  } finally {
    saving.value = false;
  }
}

function handleDeleteModel(model: AiModelProfile): void {
  const doDelete = async () => {
    try {
      await api.deleteModelProfile(model.id);
      await loadData();
      notify("success", "模型配置已删除");
    } catch (err: any) {
      notify("error", err.message || "删除模型失败");
    }
  };

  if (props.onAskConfirm) {
    props.onAskConfirm({
      title: "删除模型配置",
      description: `确定要删除模型「${model.name} (${model.model_id})」吗？已配置的默认路由将解除绑定。`,
      intent: "danger",
      confirmText: "删除模型",
      action: () => {
        void doDelete();
      }
    });
  } else {
    void doDelete();
  }
}

async function handleSetDefault(capability: AiCapabilityType, modelProfileId: number): Promise<void> {
  try {
    await api.setDefaultBinding({
      capability,
      scene: "global",
      model_profile_id: modelProfileId
    });
    await loadData();
    notify("success", "默认模型策略已更新");
  } catch (err: any) {
    notify("error", err.message || "设置默认模型失败");
  }
}

function getDefaultModelId(capability: AiCapabilityType): number | null {
  const found = defaults.value.find((d) => d.capability === capability && d.scene === "global");
  return found ? found.model_profile_id : null;
}

const capabilityLabels: Record<AiCapabilityType, string> = {
  text_optimize: "Prompt 优化 LLM",
  image_understand: "单图/批量视觉反推",
  image_generate: "图片生成 GPT 模型",
  image_edit: "图片编辑模型"
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="space-y-5">
    <!-- 全局能力默认路由映射 -->
    <div class="rounded-xl border border-line/80 bg-canvas/30 p-3.5 space-y-3">
      <div class="flex items-center justify-between border-b border-line/50 pb-2">
        <div>
          <h5 class="text-xs font-semibold text-ink">全局默认能力路由策略</h5>
          <p class="text-[11px] text-muted">
            为生图、视觉反推、Prompt 优化设定缺省模型。工作台未指定时自动沿用。
          </p>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-2 text-xs">
        <div
          v-for="(label, capKey) in capabilityLabels"
          :key="capKey"
          class="flex items-center justify-between rounded-lg bg-white p-2.5 border border-line/60"
        >
          <div class="min-w-0 pr-2">
            <span class="font-medium text-xs text-ink">{{ label }}</span>
            <span class="ml-2 font-mono text-[10px] text-muted">({{ capKey }})</span>
          </div>

          <div class="shrink-0 w-56 sm:w-64">
            <AppleSelect
              size="sm"
              placeholder="-- 请选择默认模型 --"
              :model-value="getDefaultModelId(capKey) ?? ''"
              :options="getDefaultModelOptions(capKey)"
              empty-text="无支持该能力的模型"
              @change="(val) => { if (val) handleSetDefault(capKey, Number(val)); }"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 模型列表 -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <div>
          <h5 class="text-xs font-semibold text-ink">已配置模型列表 (Profiles)</h5>
          <p class="text-[11px] text-muted">
            为各 Provider 映射具体的 Model ID 及其支持的能力 Schema。
          </p>
        </div>
        <button
          type="button"
          class="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white shadow-xs transition hover:bg-accent/90 disabled:opacity-50"
          :disabled="providers.length === 0"
          @click="openAddModel()"
        >
          <SidebarIcon name="plus" class="h-3 w-3" />
          <span>添加模型</span>
        </button>
      </div>

      <div v-if="loading" class="flex justify-center py-4 text-xs text-muted">
        正在读取模型配置…
      </div>

      <div v-else-if="models.length === 0" class="rounded-xl border border-dashed border-line bg-canvas/40 p-4 text-center">
        <p class="text-xs text-muted">暂未配置任何模型。请先添加模型以激活生图或反推能力。</p>
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="m in models"
          :key="m.id"
          class="rounded-xl border border-line/80 bg-white p-3 shadow-2xs transition hover:border-line"
        >
          <div class="flex items-start justify-between">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="font-medium text-xs text-ink truncate">{{ m.name }}</span>
                <span class="rounded bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-muted">
                  {{ m.model_id }}
                </span>
                <span class="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-600">
                  {{ m.adapter_kind }}
                </span>
              </div>

              <!-- 能力徽章 -->
              <div class="mt-2 flex flex-wrap items-center gap-1.5">
                <span
                  v-for="(cap, cKey) in m.capabilities"
                  :key="cKey"
                  class="rounded-md px-1.5 py-0.5 text-[10px] font-medium"
                  :class="cap.supported ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/50' : 'bg-zinc-50 text-zinc-400'"
                >
                  {{ cKey }}
                </span>
              </div>
            </div>

            <div class="shrink-0 ml-3">
              <button
                type="button"
                class="rounded-md p-1 text-muted hover:bg-rose-50 hover:text-rose-600 transition"
                title="删除模型"
                @click="handleDeleteModel(m)"
              >
                <SidebarIcon name="close" class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加模型弹层 -->
    <div
      v-if="showAddModel"
      class="rounded-xl border border-line bg-canvas/50 p-4 space-y-3"
    >
      <div class="flex items-center justify-between border-b border-line/60 pb-2">
        <h5 class="text-xs font-semibold text-ink">添加模型配置</h5>
        <button class="text-muted hover:text-ink text-xs" @click="showAddModel = false">
          取消
        </button>
      </div>

      <div class="space-y-2.5 text-xs">
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="block text-[11px] font-medium text-ink/80">所属 Provider 连接</label>
            <button
              v-if="selectedProviderId"
              type="button"
              :disabled="fetchingRemoteModels"
              class="flex items-center gap-1 text-[11px] text-accent hover:text-accent/80 transition disabled:opacity-50 cursor-pointer"
              title="重新获取远程模型列表"
              @click="fetchRemoteModels(selectedProviderId)"
            >
              <SidebarIcon name="refresh" class="h-3 w-3" :class="{ 'animate-spin': fetchingRemoteModels }" />
              <span>{{ fetchingRemoteModels ? "正在拉取模型…" : "刷新模型列表" }}</span>
            </button>
          </div>
          <AppleSelect
            v-model="selectedProviderId"
            :options="providerOptions"
            placeholder="-- 请选择所属 Provider 连接 --"
            @change="() => { if (selectedProviderId) fetchRemoteModels(selectedProviderId); }"
          />
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div>
            <div class="flex items-center justify-between mb-1">
              <label class="block text-[11px] font-medium text-ink/80">Model ID (API 标识)</label>
              <div class="flex items-center gap-1.5">
                <button
                  v-if="remoteModels.length > 0"
                  type="button"
                  class="text-[10px] text-accent hover:underline cursor-pointer"
                  @click="manualInputMode = !manualInputMode"
                >
                  {{ manualInputMode ? "从模型列表选择" : "手动输入标识" }}
                </button>
              </div>
            </div>

            <!-- 下拉选择模式 -->
            <div v-if="!manualInputMode && (remoteModels.length > 0 || fetchingRemoteModels)">
              <AppleSelect
                :model-value="modelForm.model_id"
                :options="remoteModelOptions"
                :disabled="fetchingRemoteModels"
                mono
                searchable
                :placeholder="fetchingRemoteModels ? '-- 正在从 Provider 获取模型列表… --' : `-- 请选择远程模型 (已拉取 ${remoteModels.length} 个) --`"
                search-placeholder="搜索模型 ID 或关键字…"
                empty-text="未找到匹配的模型 ID"
                @change="onSelectRemoteModel"
              />
            </div>

            <!-- 手动输入模式 / 降级模式 -->
            <div v-else class="space-y-1">
              <input
                v-model="modelForm.model_id"
                type="text"
                placeholder="例如：dall-e-3 / gpt-4o-mini"
                class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent"
                @input="onManualInputModelId"
              />
              <p v-if="remoteModelsError" class="text-[10px] text-amber-600">
                {{ remoteModelsError }}，已切换为手动输入
              </p>
            </div>
          </div>

          <div>
            <label class="block text-[11px] font-medium text-ink/80 mb-1">显示名称</label>
            <input
              v-model="modelForm.name"
              type="text"
              placeholder="例如：DALL-E 3 高清生图"
              class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent"
            />
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="block text-[11px] font-medium text-ink/80">适配器协议 (Adapter)</label>
            <span class="text-[10.5px] text-muted">对话/反推默认走 /chat/completions</span>
          </div>
          <AppleSelect
            v-model="modelForm.adapter_kind"
            :options="adapterOptions"
            placeholder="请选择适配器协议"
          />
        </div>

        <!-- 能力勾选 -->
        <div>
          <label class="block text-[11px] font-medium text-ink/80 mb-1.5">支持的能力声明</label>
          <div class="grid grid-cols-2 gap-2">
            <label
              v-for="(lbl, key) in capabilityLabels"
              :key="key"
              class="flex items-center gap-2 rounded-md bg-white p-2 border border-line/60 cursor-pointer select-none"
            >
              <input
                v-model="modelForm.capabilities![key].supported"
                type="checkbox"
                class="rounded border-line text-accent focus:ring-0"
              />
              <span class="text-[11.5px] text-ink">{{ lbl }}</span>
            </label>
          </div>
        </div>

        <p v-if="saveError" class="text-[11px] text-rose-600">{{ saveError }}</p>

        <div class="flex justify-end gap-2 pt-2 border-t border-line/60">
          <button
            type="button"
            class="rounded-md border border-line bg-white px-3 py-1 text-xs text-ink hover:bg-canvas transition"
            @click="showAddModel = false"
          >
            取消
          </button>
          <button
            type="button"
            class="rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90 transition disabled:opacity-50"
            :disabled="saving"
            @click="handleSaveModel"
          >
            {{ saving ? "正在保存…" : "保存模型" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
