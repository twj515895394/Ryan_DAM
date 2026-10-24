<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

const emit = defineEmits<{ (e: "close"): void }>();

const backendState = ref<"checking" | "online" | "offline">("checking");
const apiVersion = ref("—");
const errorMessage = ref("");
const sampleReady = ref(false);
const sampleName = ref("");

const statusLabel = computed(() =>
  backendState.value === "online"
    ? "本地服务已连接"
    : backendState.value === "offline"
      ? "本地服务不可用"
      : "正在检查本地服务"
);

async function checkBackend(): Promise<void> {
  backendState.value = "checking";
  errorMessage.value = "";
  try {
    const info = await window.ryanDam.getBackendInfo();
    const response = await fetch(`${info.baseUrl}/health`, {
      headers: { "X-Ryan-DAM-Token": info.token }
    });
    if (!response.ok) throw new Error(`本地服务返回 HTTP ${response.status}`);
    const health = (await response.json()) as { version: string };
    apiVersion.value = health.version;
    backendState.value = "online";
  } catch (error) {
    backendState.value = "offline";
    errorMessage.value = error instanceof Error ? error.message : "无法连接本地服务";
  }
}

async function createSampleFile(): Promise<void> {
  try {
    const result = await window.ryanDam.createSampleFile();
    sampleName.value = result.name;
    sampleReady.value = true;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "创建测试文件失败";
  }
}

function startSampleDrag(): void {
  window.ryanDam.startSampleDrag();
}

onMounted(checkBackend);
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-ink/20 px-6" @click.self="emit('close')">
      <div class="w-full max-w-lg rounded-2xl border border-line bg-white p-6 shadow-soft">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-base font-semibold">阶段 0 诊断</p>
            <p class="mt-1 text-xs text-muted">Electron ↔ FastAPI 生命周期与原生拖出 PoC</p>
          </div>
          <button class="rounded-lg px-2 py-1 text-sm text-muted transition hover:bg-canvas" @click="emit('close')">关闭</button>
        </div>

        <div class="mt-5 space-y-3 text-sm">
          <div class="flex items-center justify-between rounded-xl border border-line px-3.5 py-2.5">
            <span>本地服务状态</span>
            <span class="flex items-center gap-2 text-xs font-medium" :class="backendState === 'online' ? 'text-emerald-700' : backendState === 'offline' ? 'text-rose-700' : 'text-muted'">
              <span class="h-2 w-2 rounded-full" :class="backendState === 'online' ? 'bg-emerald-500' : backendState === 'offline' ? 'bg-rose-500' : 'bg-amber-400'" />
              {{ statusLabel }}
            </span>
          </div>
          <div class="flex items-center justify-between rounded-xl border border-line px-3.5 py-2.5">
            <span>API 版本</span>
            <span class="font-mono text-xs text-muted">{{ apiVersion }}</span>
          </div>
        </div>

        <div class="mt-4 flex items-center gap-2">
          <button class="rounded-xl border border-line px-3.5 py-2 text-sm transition hover:bg-canvas" :disabled="backendState === 'checking'" @click="checkBackend">
            重新检查服务
          </button>
          <button v-if="!sampleReady" class="rounded-xl border border-line px-3.5 py-2 text-sm transition hover:bg-canvas" @click="createSampleFile">
            生成拖拽测试文件
          </button>
        </div>

        <div
          v-if="sampleReady"
          class="mt-4 flex cursor-grab items-center gap-3 rounded-2xl border border-dashed border-blue-200 bg-blue-50/60 p-3.5 active:cursor-grabbing"
          draggable="true"
          @dragstart="startSampleDrag"
        >
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-lg shadow-sm">⇧</div>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium">{{ sampleName }}</p>
            <p class="mt-0.5 text-xs text-muted">按住此卡片拖到 Chrome 上传区域 · 真实本地文件</p>
          </div>
        </div>

        <p v-if="errorMessage" class="mt-4 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2.5 text-xs leading-5 text-rose-700">{{ errorMessage }}</p>
      </div>
    </div>
  </Teleport>
</template>
