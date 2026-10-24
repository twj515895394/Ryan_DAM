<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

type BackendInfo = Awaited<ReturnType<typeof window.ryanDam.getBackendInfo>>;
const backendInfo = ref<BackendInfo | null>(null);
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

async function checkBackend() {
  backendState.value = "checking";
  errorMessage.value = "";
  try {
    const info = backendInfo.value ?? (await window.ryanDam.getBackendInfo());
    backendInfo.value = info;
    const response = await fetch(${info.baseUrl}/health`, {
      headers: { "X-Ryan-DAM-Token": info.token }
    });
    if (!response.ok) throw new Error(§本地服务返回 HTTP ${response.status}`);
    const health = (await response.json()) as { version: string };
    apiVersion.value = health.version;
    backendState.value = "online";
  } catch (error) {
    backendState.value = "offline";
    errorMessage.value = error instanceof Error ? error.message : "无法连接本地服务";
  }
}

async function createSampleFile() {
  try {
    const result = await window.ryanDam.createSampleFile();
    sampleName.value = result.name;
    sampleReady.value = true;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "创建测试文件失败";
  }
}

function startSampleDrag() {
  window.ryanDam.startSampleDrag();
}

onMounted(checkBackend);
</script>

<template>
  <main class="min-h-screen bg-canvas px-10 py-8 text-ink">
    <div class="mx-auto max-w-6xl">
      <header class="flex items-center justify-between border-b border-line pb-6">
        <div class="flex items-center gap-3">
          <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-ink text-sm font-semibold text-white">R.</div>
          <div>
            <p class="text-lg font-semibold tracking-tight">Ryan_DAM</p>
            <p class="mt-0.5 text-xs text-muted">Digital Asset Manager</p>
          </div>
        </div>
        <div class="flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium"
          :class="backendState === 'online' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : backendState === 'offline' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-line bg-white text-muted'">
          <span class="h-2 w-2 rounded-full" :class="backendState === 'online' ? 'bg-emerald-500' : backendState === 'offline' ? 'bg-rose-500' : 'bg-amber-400'" />
          {{ statusLabel }}
        </div>
      </header>

      <section class="grid gap-10 pb-10 pt-12 lg:grid-cols-[1.2fr_0.8fr]">
        <div class="flex flex-col justify-center">
          <p class="mb-4 text-xs font-semibold uppercase tracking-[0.22em] text-accent">Stage 0 · Foundation</p>
          <h1 class="max-w-2xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
            让你的创作资产，<span class="text-muted">先有一个可靠的家。</span>
          </h1>
          <p class="mt-5 max-w-xl text-base leading-7 text-muted">
            当前是技术验证骨架。先确认桌面窗口、本地 Python 服务和真实文件拖出可以可靠协作，再逐步构建完整资产库。
          </p>
          <div class="mt-8 flex flex-wrap items-center gap-3">
            <button class="rounded-xl bg-ink px-5 py-3 text-sm font-medium text-white shadow-sm transition hover:bg-black disabled:opacity-50"
              :disabled="backendState === 'checking'" @click="checkBackend">重新检查服务</button>
            <span class="text-sm text-muted">Windows 桌面端 · 本地优先</span>
          </div>
        </div>

        <div class="rounded-3xl border border-white bg-white p-6 shadow-soft">
          <div class="flex items-start justify-between">
            <div><p class="text-sm font-semibold">运行状态</p><p class="mt-1 text-xs text-muted">Electron ↔ FastAPI</p></div>
            <span class="rounded-lg bg-canvas px-2.5 py-1.5 text-xs text-muted">本机</span>
          </div>
          <div class="mt-6 space-y-4">
            <div class="flex items-center justify-between border-b border-line pb-4">
              <div><p class="text-sm font-medium">桌面容器</p><p class="mt-1 text-xs text-muted">Electron / 安全隔离</p></div>
              <span class="text-xs font-medium text-emerald-700">已启动</span>
            </div>
            <div class="flex items-center justify-between border-b border-line pb-4">
              <div><p class="text-sm font-medium">Python API</p><p class="mt-1 text-xs text-muted">FastAPI · 动态本地端口</p></div>
              <span class="text-xs font-medium" :class="backendState === 'online' ? 'text-emerald-700' : 'text-muted'">
                {{ backendState === 'online' ? '健康' : backendState === 'checking' ? '检查中' : '未连接' }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <div><p class="text-sm font-medium">API 版本</p><p class="mt-1 text-xs text-muted">本地健康检查</p></div>
              <span class="font-mono text-xs text-muted">{{ apiVersion }}</span>
            </div>
          </div>
          <p v-if="errorMessage" class="mt-5 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2.5 text-xs leading-5 text-rose-700">{{ errorMessage }}</p>
        </div>
      </section>

      <section class="grid gap-5 md:grid-cols-2">
        <article class="rounded-3xl border border-line bg-white p-6 shadow-sm">
          <div class="flex items-center justify-between">
            <div><p class="text-sm font-semibold">原生文件拖出 PoC</p><p class="mt-1 text-xs text-muted">验证桌面应用与外部应用的文件交互</p></div>
            <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-50 text-lg text-accent">↗</div>
          </div>
          <p class="mt-5 text-sm leading-6 text-muted">生成专用测试文件，然后按住文件卡片拖动到 Chrome 的文件上传区域。PoC 不会读取或移动你的其他文件。</p>
          <button v-if="!sampleReady" class="mt-5 rounded-xl border border-line bg-white px-4 py-2.5 text-sm font-medium transition hover:bg-canvas" @click="createSampleFile">生成拖拽测试文件</button>
          <div v-else class="mt-5 flex cursor-grab items-center gap-3 rounded-2xl border border-dashed border-blue-200 bg-blue-50/60 p-4 active:cursor-grabbing" draggable="true" @dragstart="startSampleDrag">
            <div class="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">⇧</div>
            <div class="min-w-0 flex-1"><p class="truncate text-sm font-medium">{{ sampleName }}</p><p class="mt-1 text-xs text-muted">按住并拖出 · 真实本地文件</p></div>
            <span class="text-xs font-medium text-accent">DRAG</span>
          </div>
          <p class="mt-4 text-xs leading-5 text-muted">当前仅验证拖拽机制，正式资产卡片将在后续阶段接入。</p>
        </article>

        <article class="rounded-3xl border border-line bg-white p-6 shadow-sm">
          <div class="flex items-center justify-between">
            <div><p class="text-sm font-semibold">阶段 0 验收范围</p><p class="mt-1 text-xs text-muted">项目骨架与关键风险验证</p></div>
            <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-50 text-lg text-emerald-700">✓</div>
          </div>
          <ul class="mt-5 space-y-3 text-sm">
            <li class="flex gap-3"><span class="text-emerald-600">✓</span><span>Electron 窗口与受限 Preload IPC</span></li>
            <li class="flex gap-3"><span class="text-emerald-600">✓</span><span>本机 FastAPI 动态端口与令牌校验</span></li>
            <li class="flex gap-3"><span class="text-emerald-600">✓</span><span>窗口状态持久化与屏幕范围保护</span></li>
            <li class="flex gap-3"><span class="text-emerald-600">✓</span><span>Windows 后端打包与 CI 脚本</span></li>
            <li class="flex gap-3"><span class="text-amber-600">○</span><span>Chrome 拖入：需在 Windows 桌面环境实测</span></li>
          </ul>
          <a class="mt-5 inline-flex text-sm font-medium text-accent hover:underline" href="https://github.com/twj515895394/Ryan_DAM/blob/main/docs/STAGE_0_VALIDATION.md" target="_blank" rel="noreferrer">查看完整验收清单 ↗</a>
        </article>
      </section>

      <footer class="flex flex-wrap items-center justify-between gap-3 py-8 text-xs text-muted">
        <span>Ryan_DAM · Local-first creator asset library</span>
        <span>本地服务仅绑定 loopback，不对局域网开放</span>
      </footer>
    </div>
  </main>
</template>
