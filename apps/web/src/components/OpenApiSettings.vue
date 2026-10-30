<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import SidebarIcon from "./SidebarIcon.vue";
import { api } from "../api/client";
import type { OpenApiInfo } from "../api/types";

const info = ref<OpenApiInfo | null>(null);
const isLoading = ref(false);
const loadError = ref<string | null>(null);
const copiedKey = ref<string | null>(null);

const baseUrlSample = computed(() => {
  const first = info.value?.open_base_urls?.[0];
  return first ?? "http://<本机局域网IP>:8765/api/v1/open";
});

const loopbackUrl = computed(() => {
  const first = info.value?.open_base_urls?.[0] ?? "";
  const match = first.match(/:(\d+)\//);
  return match ? `http://127.0.0.1:${match[1]}/api/v1/open` : null;
});

const curlExample = computed(() =>
  [
    `curl -X POST ${baseUrlSample.value}/images/generations \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '{ "prompt": "窗边读书的白猫，电影感柔光", "size": "1024x1024", "wait": true }'`,
  ].join("\n")
);

async function copyText(key: string, text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    copiedKey.value = key;
    window.setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = null;
    }, 1500);
  } catch {
    /* 剪贴板不可用时静默降级，用户可手动选中复制 */
  }
}

async function loadInfo(): Promise<void> {
  isLoading.value = true;
  loadError.value = null;
  try {
    info.value = await api.getOpenApiInfo();
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : "读取开放接口信息失败";
  } finally {
    isLoading.value = false;
  }
}

onMounted(loadInfo);
</script>

<template>
  <div class="space-y-4">
    <!-- 能力说明 -->
    <div class="rounded-xl border border-line/80 bg-canvas/40 p-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10 text-accent">
            <SidebarIcon name="globe" class="h-4 w-4" />
          </div>
          <div>
            <span class="text-xs font-semibold text-ink/80">局域网开放接口 (Open API)</span>
            <p class="text-[10.5px] text-muted">供同一局域网内的其他项目复用本机 AI 生图 / 图生图能力</p>
          </div>
        </div>
        <button
          type="button"
          class="rounded-md border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink transition hover:bg-canvas disabled:opacity-50"
          :disabled="isLoading"
          @click="loadInfo"
        >
          {{ isLoading ? "刷新中…" : "刷新" }}
        </button>
      </div>
      <p class="mt-2.5 text-[11px] leading-relaxed text-muted">
        调用方无需任何配置即可生图：模型跟随「模型与路由」中设定的默认生图模型；
        生成结果默认自动入库到「{{ info?.default_ai_folder ?? "AI 生成" }}」目录，生成历史同步永久保留。
        仅 <code class="rounded bg-white px-1 py-0.5 font-mono text-[10.5px]">/api/v1/open</code>
        前缀免鉴权对外开放，本应用自身使用的其余接口仍然只允许本机访问。
      </p>
    </div>

    <p v-if="loadError" class="rounded-lg border border-rose-200 bg-rose-50/70 px-3 py-2 text-xs text-rose-700">
      {{ loadError }}
    </p>

    <!-- 访问地址 -->
    <div class="rounded-xl border border-line/80 bg-canvas/40 p-4">
      <span class="text-xs font-semibold text-ink/80">调用地址</span>
      <div v-if="info" class="mt-2 space-y-1.5">
        <div
          v-for="url in info.open_base_urls"
          :key="url"
          class="flex items-center justify-between gap-2 rounded-lg bg-white px-2.5 py-1.5"
        >
          <span class="truncate font-mono text-xs text-ink" :title="url">{{ url }}</span>
          <button
            type="button"
            class="shrink-0 rounded px-1.5 py-0.5 text-[10.5px] font-medium transition"
            :class="copiedKey === url ? 'text-emerald-600' : 'text-muted hover:text-accent'"
            @click="copyText(url, url)"
          >
            {{ copiedKey === url ? "已复制" : "复制" }}
          </button>
        </div>
        <div
          v-if="loopbackUrl"
          class="flex items-center justify-between gap-2 rounded-lg bg-white/60 px-2.5 py-1.5"
        >
          <span class="truncate font-mono text-xs text-muted" :title="loopbackUrl">{{ loopbackUrl }}（本机）</span>
          <button
            type="button"
            class="shrink-0 rounded px-1.5 py-0.5 text-[10.5px] font-medium text-muted transition hover:text-accent"
            @click="copyText('loopback', loopbackUrl)"
          >
            {{ copiedKey === "loopback" ? "已复制" : "复制" }}
          </button>
        </div>
        <p v-if="info.open_base_urls.length === 0" class="text-[11px] text-amber-700">
          未探测到局域网 IP：请确认本机已连接局域网后点击「刷新」。
        </p>
        <p class="pt-1 text-[10.5px] text-muted/80">
          同机其他项目可直接读取 <code class="rounded bg-white px-1 py-0.5 font-mono text-[10.5px]">~/.ryan_dam/data/endpoint.json</code>
          获取端口与内部令牌；完整协议见 <code class="rounded bg-white px-1 py-0.5 font-mono text-[10.5px]">docs/OPEN_API.md</code>。
        </p>
      </div>
      <p v-else class="mt-2 text-[11px] text-muted">正在读取本地服务信息…</p>
    </div>

    <!-- 当前默认模型 -->
    <div class="rounded-xl border border-line/80 bg-canvas/40 p-4">
      <span class="text-xs font-semibold text-ink/80">开放接口使用的默认模型</span>
      <div v-if="info" class="mt-2 grid grid-cols-2 gap-2">
        <div class="rounded-lg bg-white px-2.5 py-2">
          <p class="text-[10px] uppercase tracking-wider text-muted/70">文生图 image_generate</p>
          <p class="mt-0.5 truncate text-xs font-medium text-ink" :title="info.default_models.image_generate.name ?? ''">
            {{ info.default_models.image_generate.name ?? "未设定（自动取第一个可用模型）" }}
          </p>
        </div>
        <div class="rounded-lg bg-white px-2.5 py-2">
          <p class="text-[10px] uppercase tracking-wider text-muted/70">图生图 image_edit</p>
          <p class="mt-0.5 truncate text-xs font-medium text-ink" :title="info.default_models.image_edit.name ?? ''">
            {{ info.default_models.image_edit.name ?? "未设定（自动取第一个可用模型）" }}
          </p>
        </div>
      </div>
      <p class="mt-2 text-[10.5px] text-muted/80">
        调用方也可在请求体中用 model_profile_id 显式指定：
        <template v-if="info && info.models.length > 0">
          <span v-for="m in info.models" :key="m.id" class="mr-1.5 inline-block rounded bg-white px-1.5 py-0.5 font-mono text-[10.5px] text-ink/80">
            #{{ m.id }} {{ m.name }}
          </span>
        </template>
        <template v-else>（暂无启用的模型）</template>
      </p>
    </div>

    <!-- 调用示例 -->
    <div class="rounded-xl border border-line/80 bg-canvas/40 p-4">
      <div class="flex items-center justify-between">
        <span class="text-xs font-semibold text-ink/80">最简调用（文生图并等待结果）</span>
        <button
          type="button"
          class="rounded px-1.5 py-0.5 text-[10.5px] font-medium transition"
          :class="copiedKey === 'curl' ? 'text-emerald-600' : 'text-muted hover:text-accent'"
          @click="copyText('curl', curlExample)"
        >
          {{ copiedKey === "curl" ? "已复制" : "复制示例" }}
        </button>
      </div>
      <pre
        class="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-white px-3 py-2.5 font-mono text-[11px] leading-relaxed text-ink/90 border border-line/60"
      >{{ curlExample }}</pre>
      <p class="mt-2 text-[10.5px] leading-relaxed text-muted">
        返回中的 <code class="rounded bg-white px-1 py-0.5 font-mono">results[].content_path</code> 可 GET 取回图片二进制；
        <code class="rounded bg-white px-1 py-0.5 font-mono">imported_asset_id</code> 即已自动入库的资产。
        图生图在 references 里传 image_base64；长任务可去掉 "wait" 后用 GET /images/tasks/{task_id} 轮询。
      </p>
    </div>
  </div>
</template>
