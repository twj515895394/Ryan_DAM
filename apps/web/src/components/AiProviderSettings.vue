<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api/client";
import type {
  AiCapabilityType,
  AiProviderCreatePayload,
  AiProviderInstance,
  AiProviderTestResponse,
  AiProviderUpdatePayload
} from "../api/types";
import SidebarIcon from "./SidebarIcon.vue";
import { notify } from "../stores/library";

import type { ConfirmRequest } from "../composables/useConfirmDialog";

const props = defineProps<{
  onAskConfirm?: (request: ConfirmRequest) => void;
}>();

const emit = defineEmits<{
  (e: "providers-loaded", list: AiProviderInstance[]): void;
}>();

const providers = ref<AiProviderInstance[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

// 编辑/新增状态
const showEditor = ref(false);
const editingId = ref<number | null>(null);
const form = ref<AiProviderCreatePayload>({
  name: "",
  family: "openai_compatible",
  base_url: "http://127.0.0.1:8317/v1",
  api_key: "",
  enabled: true
});
const saving = ref(false);
const saveError = ref<string | null>(null);

// 测试状态
const testingId = ref<number | null>(null);
const testResult = ref<AiProviderTestResponse | null>(null);
const activeTestProviderId = ref<number | null>(null);

async function loadProviders(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    providers.value = await api.listAiProviders();
    emit("providers-loaded", providers.value);
  } catch (err: any) {
    error.value = err.message || "加载 AI Provider 列表失败";
  } finally {
    loading.value = false;
  }
}

function openAdd(family: "openai_compatible" | "openai_native" | "gemini_native" = "openai_compatible"): void {
  editingId.value = null;
  saveError.value = null;
  testResult.value = null;

  if (family === "openai_compatible") {
    form.value = {
      name: "本地网关 / 第三方中转",
      family: "openai_compatible",
      base_url: "http://127.0.0.1:8317/v1",
      api_key: "",
      enabled: true
    };
  } else if (family === "openai_native") {
    form.value = {
      name: "OpenAI 官方服务",
      family: "openai_native",
      base_url: "https://api.openai.com/v1",
      api_key: "",
      enabled: true
    };
  } else {
    form.value = {
      name: "Google Gemini 官方服务",
      family: "gemini_native",
      base_url: "https://generativelanguage.googleapis.com/v1beta/openai",
      api_key: "",
      enabled: true
    };
  }
  showEditor.value = true;
}

function openEdit(provider: AiProviderInstance): void {
  editingId.value = provider.id;
  saveError.value = null;
  testResult.value = null;
  form.value = {
    name: provider.name,
    family: provider.family,
    base_url: provider.base_url,
    api_key: "", // 保持空白，不修改则留空
    enabled: provider.enabled
  };
  showEditor.value = true;
}

async function handleSave(): Promise<void> {
  if (!form.value.name.trim()) {
    saveError.value = "请填写连接显示名称";
    return;
  }
  if (!form.value.base_url?.trim()) {
    saveError.value = "请填写 Base URL";
    return;
  }

  saving.value = true;
  saveError.value = null;
  try {
    if (editingId.value === null) {
      await api.createAiProvider(form.value);
    } else {
      const updatePayload: AiProviderUpdatePayload = {
        name: form.value.name,
        base_url: form.value.base_url,
        enabled: form.value.enabled
      };
      if (form.value.api_key?.trim()) {
        updatePayload.api_key = form.value.api_key.trim();
      }
      await api.updateAiProvider(editingId.value, updatePayload);
    }
    showEditor.value = false;
    await loadProviders();
  } catch (err: any) {
    saveError.value = err.message || "保存失败";
  } finally {
    saving.value = false;
  }
}

function handleDelete(provider: AiProviderInstance): void {
  const doDelete = async () => {
    try {
      await api.deleteAiProvider(provider.id);
      if (editingId.value === provider.id) {
        showEditor.value = false;
      }
      await loadProviders();
      notify("success", "AI 连接已删除");
    } catch (err: any) {
      notify("error", err.message || "删除连接失败");
    }
  };

  if (props.onAskConfirm) {
    props.onAskConfirm({
      title: "删除 AI 连接",
      description: `确定要删除连接「${provider.name}」吗？已加密保存的 API Key 将被安全彻底粉碎。`,
      intent: "danger",
      confirmText: "删除连接",
      action: () => {
        void doDelete();
      }
    });
  } else {
    void doDelete();
  }
}

async function runCapabilityTest(provider: AiProviderInstance): Promise<void> {
  testingId.value = provider.id;
  activeTestProviderId.value = provider.id;
  testResult.value = null;
  try {
    const res = await api.testAiProvider(provider.id, {});
    testResult.value = res;
  } catch (err: any) {
    testResult.value = {
      connection_ok: false,
      message: err.message || "连接测试失败",
      results: {
        text_optimize: {
          capability: "text_optimize",
          supported: false,
          model_id: "probe",
          latency_ms: 0,
          message: err.message || "连接测试失败"
        }
      }
    };
  } finally {
    testingId.value = null;
  }
}

onMounted(() => {
  loadProviders();
});
</script>

<template>
  <div class="space-y-4">
    <!-- 顶部说明与快捷新增 -->
    <div class="flex items-center justify-between">
      <div>
        <h4 class="text-xs font-semibold text-ink">AI 模型连接 (Providers)</h4>
        <p class="text-[11px] text-muted">
          配置自定义 OpenAI 兼容接口或官方 API。密钥通过 Windows DPAPI 本地强加密存储。
        </p>
      </div>
      <div class="flex items-center gap-1.5">
        <button
          type="button"
          class="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white shadow-xs transition hover:bg-accent/90"
          @click="openAdd('openai_compatible')"
        >
          <SidebarIcon name="plus" class="h-3 w-3" />
          <span>添加兼容接口</span>
        </button>
      </div>
    </div>

    <!-- 连接列表 -->
    <div v-if="loading" class="flex justify-center py-6 text-xs text-muted">
      正在读取连接配置…
    </div>

    <div v-else-if="providers.length === 0" class="rounded-xl border border-dashed border-line bg-canvas/40 p-5 text-center">
      <p class="text-xs text-muted">暂未添加任何 AI 服务连接</p>
      <div class="mt-3 flex justify-center gap-2">
        <button
          type="button"
          class="rounded-md border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink transition hover:bg-canvas"
          @click="openAdd('openai_compatible')"
        >
          推荐：添加自定义 OpenAI 兼容连接
        </button>
      </div>
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="p in providers"
        :key="p.id"
        class="rounded-xl border border-line/80 bg-white p-3 shadow-2xs transition hover:border-line"
      >
        <div class="flex items-start justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="font-medium text-xs text-ink truncate">{{ p.name }}</span>
              <span
                class="rounded-md px-1.5 py-0.5 text-[10px] font-mono"
                :class="p.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-zinc-100 text-zinc-500'"
              >
                {{ p.enabled ? "已启用" : "已停用" }}
              </span>
              <span class="rounded bg-canvas px-1.5 py-0.5 text-[10px] text-muted">
                {{ p.family }}
              </span>
            </div>
            <p class="mt-1 font-mono text-[11px] text-muted truncate" :title="p.base_url">
              {{ p.base_url }}
            </p>
            <div class="mt-1 flex items-center gap-2 text-[10.5px] text-muted">
              <span>密钥：{{ p.credential_masked ? p.credential_masked : "未设置" }}</span>
            </div>
          </div>

          <div class="flex items-center gap-1.5 shrink-0 ml-3">
            <button
              type="button"
              class="rounded-md border border-line/80 bg-canvas/60 px-2 py-1 text-[11px] font-medium text-ink transition hover:bg-canvas disabled:opacity-50"
              :disabled="testingId === p.id"
              @click="runCapabilityTest(p)"
            >
              {{ testingId === p.id ? "测试中…" : "能力测试" }}
            </button>
            <button
              type="button"
              class="rounded-md p-1 text-muted hover:bg-canvas hover:text-ink transition"
              title="编辑连接"
              @click="openEdit(p)"
            >
              <SidebarIcon name="edit" class="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              class="rounded-md p-1 text-muted hover:bg-rose-50 hover:text-rose-600 transition"
              title="删除连接"
              @click="handleDelete(p)"
            >
              <SidebarIcon name="close" class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <!-- 当前选中测试的结果展示 -->
        <div
          v-if="testResult && activeTestProviderId === p.id"
          class="mt-2.5 rounded-lg border border-line/60 bg-canvas/40 p-2 text-xs"
        >
          <div class="flex items-center justify-between pb-1.5 border-b border-line/40 text-[11px]">
            <span class="font-medium text-ink">连通测试结论</span>
            <span :class="testResult.connection_ok ? 'text-emerald-700' : 'text-amber-700'">
              {{ testResult.connection_ok ? "连接成功" : "连接受限 / 失败" }}
            </span>
          </div>
          <div class="grid grid-cols-2 gap-1.5 pt-1.5 text-[10.5px]">
            <template v-for="(cap, key) in testResult.results" :key="key">
              <div
                v-if="cap"
                class="flex items-center justify-between rounded bg-white px-2 py-1 border border-line/40"
              >
                <span class="text-muted">{{ key }}</span>
                <span
                  class="font-medium"
                  :class="cap.supported ? 'text-emerald-600' : 'text-zinc-400'"
                >
                  {{ cap.supported ? `✓ (${cap.latency_ms}ms)` : "✕ 不支持" }}
                </span>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑/添加抽屉式子面板 -->
    <div
      v-if="showEditor"
      class="mt-4 rounded-xl border border-line bg-canvas/50 p-4 space-y-3"
    >
      <div class="flex items-center justify-between border-b border-line/60 pb-2">
        <h5 class="text-xs font-semibold text-ink">
          {{ editingId === null ? "添加 AI Provider 连接" : "修改 AI Provider 连接" }}
        </h5>
        <button
          class="text-muted hover:text-ink text-xs"
          @click="showEditor = false"
        >
          取消
        </button>
      </div>

      <div class="space-y-2.5 text-xs">
        <div>
          <label class="block text-[11px] font-medium text-ink/80 mb-1">连接显示名称</label>
          <input
            v-model="form.name"
            type="text"
            placeholder="例如：本地网关 / 硅基流动 / 官方 API"
            class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent"
          />
        </div>

        <div>
          <label class="block text-[11px] font-medium text-ink/80 mb-1">Base URL</label>
          <input
            v-model="form.base_url"
            type="text"
            placeholder="http://127.0.0.1:8317/v1 或 https://api.openai.com/v1"
            class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent"
          />
          <span class="text-[10px] text-muted">提示：系统会自动规整结尾的斜杠与 /chat 等子路径。</span>
        </div>

        <div>
          <label class="block text-[11px] font-medium text-ink/80 mb-1">
            API Key {{ editingId !== null ? "（若不修改请留空）" : "" }}
          </label>
          <input
            v-model="form.api_key"
            type="password"
            placeholder="sk-..."
            class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent"
          />
        </div>

        <div class="flex items-center gap-2 pt-1">
          <input
            id="provider-enabled"
            v-model="form.enabled"
            type="checkbox"
            class="rounded border-line text-accent focus:ring-0"
          />
          <label for="provider-enabled" class="text-xs text-ink select-none">启用此连接</label>
        </div>

        <p v-if="saveError" class="text-[11px] text-rose-600">{{ saveError }}</p>

        <div class="flex justify-end gap-2 pt-2 border-t border-line/60">
          <button
            type="button"
            class="rounded-md border border-line bg-white px-3 py-1 text-xs text-ink hover:bg-canvas transition"
            @click="showEditor = false"
          >
            取消
          </button>
          <button
            type="button"
            class="rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90 transition disabled:opacity-50"
            :disabled="saving"
            @click="handleSave"
          >
            {{ saving ? "正在保存…" : "保存连接" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
