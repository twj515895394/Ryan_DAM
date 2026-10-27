<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";
import type {
  AiCapabilityType,
  AiDefaultBinding,
  AiModelProfile,
  AiModelProfileCreatePayload,
  AiProviderInstance
} from "../api/types";
import SidebarIcon from "./SidebarIcon.vue";
import type { ConfirmRequest } from "../composables/useConfirmDialog";

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

function openAddModel(providerId?: number): void {
  saveError.value = null;
  selectedProviderId.value = providerId || props.providers[0]?.id || null;
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
    } catch (err: any) {
      alert(err.message || "删除模型失败");
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
  } catch (err: any) {
    alert(err.message || "设置默认模型失败");
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

          <div class="shrink-0">
            <select
              class="rounded-md border border-line bg-canvas/40 px-2 py-1 text-xs text-ink outline-none focus:border-accent"
              :value="getDefaultModelId(capKey) ?? ''"
              @change="e => {
                const val = (e.target as HTMLSelectElement).value;
                if (val) handleSetDefault(capKey, Number(val));
              }"
            >
              <option value="" disabled>-- 请选择默认模型 --</option>
              <option
                v-for="m in models.filter(item => item.capabilities[capKey]?.supported)"
                :key="m.id"
                :value="m.id"
              >
                {{ m.name }} ({{ m.model_id }})
              </option>
            </select>
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
          <label class="block text-[11px] font-medium text-ink/80 mb-1">所属 Provider 连接</label>
          <select
            v-model="selectedProviderId"
            class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent"
          >
            <option v-for="p in providers" :key="p.id" :value="p.id">
              {{ p.name }} ({{ p.base_url }})
            </option>
          </select>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="block text-[11px] font-medium text-ink/80 mb-1">Model ID (API 标识)</label>
            <input
              v-model="modelForm.model_id"
              type="text"
              placeholder="例如：dall-e-3 / gpt-4o-mini"
              class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent"
            />
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
          <label class="block text-[11px] font-medium text-ink/80 mb-1">适配器协议 (Adapter)</label>
          <select
            v-model="modelForm.adapter_kind"
            class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent"
          >
            <option value="openai_standard">OpenAI 标准生图 (/images/generations)</option>
            <option value="openai_chat_markdown">OpenAI Chat 嵌入图 (Gemini/第三方 Markdown)</option>
            <option value="gemini_standard">Gemini 原生生图协议</option>
            <option value="custom">通用自定义适配器</option>
          </select>
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
