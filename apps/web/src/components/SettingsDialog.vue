<script setup lang="ts">
import { computed, ref } from "vue";
import SidebarIcon from "./SidebarIcon.vue";
import AiProviderSettings from "./AiProviderSettings.vue";
import AiModelSettings from "./AiModelSettings.vue";
import { library } from "../stores/library";
import type { AiProviderInstance } from "../api/types";

import type { ConfirmRequest } from "../composables/useConfirmDialog";

const props = defineProps<{
  open: boolean;
  onAskConfirm?: (request: ConfirmRequest) => void;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "edit-root"): void;
  (e: "open-stage0"): void;
}>();

const activeTab = ref<"general" | "providers" | "models">("general");
const cachedProviders = ref<AiProviderInstance[]>([]);

function onProvidersLoaded(list: AiProviderInstance[]): void {
  cachedProviders.value = list;
}

const rootStateLabel = computed(() => {
  switch (library.settings?.managed_root_state) {
    case "ok": return "可用";
    case "missing": return "目录未创建";
    case "unavailable": return "磁盘不可用";
    default: return "未知";
  }
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-xs"
      @click.self="emit('close')"
    >
      <div class="w-[580px] max-h-[85vh] flex flex-col rounded-2xl border border-line bg-white shadow-soft overflow-hidden">
        <!-- 弹窗顶栏与 Tab 切换 -->
        <div class="px-6 pt-5 pb-3 border-b border-line">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <SidebarIcon name="settings" class="h-4 w-4 text-muted" />
              <h3 class="text-sm font-semibold text-ink">系统偏好设置</h3>
            </div>
            <button
              class="flex h-6 w-6 items-center justify-center rounded-md text-muted hover:bg-canvas hover:text-ink transition-colors"
              @click="emit('close')"
            >
              <SidebarIcon name="close" class="h-3.5 w-3.5" />
            </button>
          </div>

          <!-- Apple HIG 风格 3-Segment Tab -->
          <div class="mt-3 flex rounded-lg bg-canvas p-0.5 border border-line/60">
            <button
              type="button"
              class="flex-1 rounded-md py-1 text-xs font-medium transition-all"
              :class="activeTab === 'general' ? 'bg-white text-ink shadow-2xs' : 'text-muted hover:text-ink'"
              @click="activeTab = 'general'"
            >
              存储与关于
            </button>
            <button
              type="button"
              class="flex-1 rounded-md py-1 text-xs font-medium transition-all"
              :class="activeTab === 'providers' ? 'bg-white text-ink shadow-2xs' : 'text-muted hover:text-ink'"
              @click="activeTab = 'providers'"
            >
              AI 连接 (Providers)
            </button>
            <button
              type="button"
              class="flex-1 rounded-md py-1 text-xs font-medium transition-all"
              :class="activeTab === 'models' ? 'bg-white text-ink shadow-2xs' : 'text-muted hover:text-ink'"
              @click="activeTab = 'models'"
            >
              模型与默认路由 (Models)
            </button>
          </div>
        </div>

        <!-- 弹窗主体内容滚动区 -->
        <div class="flex-1 overflow-y-auto px-6 py-4">
          <!-- Tab 1: 常规与存储 -->
          <div v-if="activeTab === 'general'" class="space-y-4">
            <div class="rounded-xl border border-line/80 bg-canvas/40 p-3.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-ink/80">默认托管存储目录</span>
                <span
                  class="rounded-full px-2 py-0.5 text-[10.5px] font-medium"
                  :class="library.settings?.managed_root_state === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'"
                >
                  {{ rootStateLabel }}
                </span>
              </div>
              <p
                class="mt-2 truncate rounded-lg bg-white px-2.5 py-1.5 font-mono text-xs text-muted border border-line/60"
                :title="library.settings?.managed_root"
              >
                {{ library.settings?.managed_root ?? "未设置" }}
              </p>
              <div class="mt-2.5 flex items-center justify-between text-[11px] text-muted">
                <span>修改后仅影响后续新导入的文件</span>
                <button
                  class="rounded-md border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink transition hover:bg-canvas"
                  @click="emit('edit-root')"
                >
                  修改位置…
                </button>
              </div>
            </div>

            <div class="rounded-xl border border-line/80 bg-canvas/40 p-3.5">
              <span class="text-xs font-semibold text-ink/80">关于 Ryan DAM</span>
              <p class="mt-1 text-xs text-muted leading-relaxed">
                面向个人创作者与团队的本地桌面资产管理器。支持图片、视频、音频、文档多格式快速检索、标签与提示词管理。
              </p>
              <div class="mt-3 flex items-center justify-between border-t border-line/50 pt-2.5">
                <span class="text-[11px] text-muted/80">桌面级架构 · Clean Architecture</span>
                <button
                  class="text-xs text-accent hover:underline"
                  @click="emit('open-stage0'); emit('close')"
                >
                  查看本地环境诊断 →
                </button>
              </div>
            </div>
          </div>

          <!-- Tab 2: AI 连接配置 -->
          <div v-else-if="activeTab === 'providers'">
            <AiProviderSettings
              :on-ask-confirm="onAskConfirm"
              @providers-loaded="onProvidersLoaded"
            />
          </div>

          <!-- Tab 3: 模型与默认路由 -->
          <div v-else-if="activeTab === 'models'">
            <AiModelSettings
              :providers="cachedProviders"
              :on-ask-confirm="onAskConfirm"
            />
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
