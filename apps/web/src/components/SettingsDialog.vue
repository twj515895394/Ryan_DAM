<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import SidebarIcon from "./SidebarIcon.vue";
import AiProviderSettings from "./AiProviderSettings.vue";
import AiModelSettings from "./AiModelSettings.vue";
import AiTemplateSettings from "./AiTemplateSettings.vue";
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

type SettingsTab = "general" | "providers" | "models" | "templates";

interface NavItem {
  id: SettingsTab;
  label: string;
  sublabel: string;
  icon: "settings" | "external" | "star" | "edit";
  title: string;
  description: string;
}

const navItems: NavItem[] = [
  {
    id: "general",
    label: "存储与关于",
    sublabel: "本地目录与诊断",
    icon: "settings",
    title: "通用存储与关于",
    description: "配置管理资产的默认托管存储位置与本地环境诊断信息"
  },
  {
    id: "providers",
    label: "AI 服务商",
    sublabel: "Providers 凭据",
    icon: "external",
    title: "AI 服务商连接 (Providers)",
    description: "配置聚合网关、OpenAI、Gemini、Claude 等模型服务商与 API 凭据"
  },
  {
    id: "models",
    label: "模型与路由",
    sublabel: "Profiles & Routing",
    icon: "star",
    title: "模型管理与默认路由 (Models)",
    description: "动态探测服务商模型，并指定视觉反推、文本优化与生图默认使用的模型"
  },
  {
    id: "templates",
    label: "模板与预设",
    sublabel: "Prompts & Presets",
    icon: "edit",
    title: "提示词模板与创作风格预设 (Templates)",
    description: "自定义配置与调优视觉反推 System Prompt 模板及工作台生图风格预设"
  }
];

const activeTab = ref<SettingsTab>("general");
const cachedProviders = ref<AiProviderInstance[]>([]);

const activeTabMeta = computed(() => {
  return navItems.find((item) => item.id === activeTab.value) || navItems[0];
});

function onProvidersLoaded(list: AiProviderInstance[]): void {
  cachedProviders.value = list;
}

const rootStateLabel = computed(() => {
  switch (library.settings?.managed_root_state) {
    case "ok":
      return "可用";
    case "missing":
      return "目录未创建";
    case "unavailable":
      return "磁盘不可用";
    default:
      return "未知";
  }
});

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape" && props.open) {
    e.preventDefault();
    e.stopPropagation();
    emit("close");
  }
}

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-md"
      @click.self="emit('close')"
    >
      <!-- 双栏桌面级系统偏好设置大弹窗 (macOS / Codex 风格) -->
      <div
        class="w-[960px] max-w-[95vw] h-[660px] max-h-[88vh] flex flex-row rounded-2xl border border-line/80 bg-white/95 backdrop-blur-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
      >
        <!-- 左侧分类侧边栏 (220px) -->
        <aside class="w-56 shrink-0 flex flex-col border-r border-line/70 bg-canvas/40 select-none">
          <!-- 侧栏顶部标题 -->
          <div class="px-5 py-4 border-b border-line/60 flex items-center gap-2.5">
            <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10 text-accent">
              <SidebarIcon name="settings" class="h-4 w-4" />
            </div>
            <div>
              <h3 class="text-xs font-semibold tracking-tight text-ink">系统偏好设置</h3>
              <p class="text-[10px] text-muted">Preferences</p>
            </div>
          </div>

          <!-- 导航菜单分类列表 -->
          <nav class="flex-1 overflow-y-auto p-2 space-y-1">
            <button
              v-for="item in navItems"
              :key="item.id"
              type="button"
              class="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-left transition-all duration-150"
              :class="
                activeTab === item.id
                  ? 'bg-accent text-white font-medium shadow-xs'
                  : 'text-ink/80 hover:bg-canvas/80 hover:text-ink'
              "
              @click="activeTab = item.id"
            >
              <SidebarIcon
                :name="item.icon"
                class="h-4 w-4 shrink-0"
                :class="activeTab === item.id ? 'text-white' : 'text-muted'"
              />
              <div class="min-w-0 flex-1">
                <div class="text-xs truncate font-medium">{{ item.label }}</div>
                <div
                  class="text-[10px] truncate"
                  :class="activeTab === item.id ? 'text-white/80' : 'text-muted'"
                >
                  {{ item.sublabel }}
                </div>
              </div>
            </button>
          </nav>

          <!-- 侧边栏底部版本与品牌信息 -->
          <div class="p-3 border-t border-line/50 text-[10px] text-muted/70 flex items-center justify-between">
            <span>Ryan DAM Desktop</span>
            <span>v2.0</span>
          </div>
        </aside>

        <!-- 右侧主体内容区 (自适应流式详情画布) -->
        <main class="flex-1 flex flex-col min-w-0 overflow-hidden bg-white/95">
          <!-- 右侧固定标题栏 -->
          <header class="flex items-center justify-between px-6 py-4 border-b border-line/60 shrink-0">
            <div>
              <h3 class="text-sm font-semibold text-ink">{{ activeTabMeta.title }}</h3>
              <p class="text-[11px] text-muted mt-0.5">{{ activeTabMeta.description }}</p>
            </div>
            <button
              type="button"
              class="flex h-7 w-7 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-ink transition-colors"
              title="关闭 (Esc)"
              @click="emit('close')"
            >
              <SidebarIcon name="close" class="h-4 w-4 pointer-events-none" />
            </button>
          </header>

          <!-- 右侧可滚动内容画布 -->
          <div class="flex-1 overflow-y-auto px-6 py-5">
            <!-- Tab 1: 通用存储与关于 -->
            <div v-if="activeTab === 'general'" class="space-y-4">
              <div class="rounded-xl border border-line/80 bg-canvas/40 p-4">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-semibold text-ink/80">默认托管存储目录</span>
                  <span
                    class="rounded-full px-2 py-0.5 text-[10.5px] font-medium"
                    :class="
                      library.settings?.managed_root_state === 'ok'
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-amber-50 text-amber-700'
                    "
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
                    type="button"
                    class="rounded-md border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink transition hover:bg-canvas"
                    @click="emit('edit-root')"
                  >
                    修改位置…
                  </button>
                </div>
              </div>

              <div class="rounded-xl border border-line/80 bg-canvas/40 p-4">
                <span class="text-xs font-semibold text-ink/80">关于 Ryan DAM</span>
                <p class="mt-1 text-xs text-muted leading-relaxed">
                  面向个人创作者与团队的高品质桌面级资产管理器。支持图片、视频、音频、文档多格式秒级检索、智能标签与多模态 AI 提示词反推创作体系。
                </p>
                <div class="mt-3 flex items-center justify-between border-t border-line/50 pt-2.5">
                  <span class="text-[11px] text-muted/80">桌面级架构 · Clean Architecture</span>
                  <button
                    type="button"
                    class="text-xs text-accent hover:underline"
                    @click="emit('open-stage0'); emit('close')"
                  >
                    查看本地环境诊断 →
                  </button>
                </div>
              </div>
            </div>

            <!-- Tab 2: AI 服务商连接 -->
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

            <!-- Tab 4: 提示词模板与创作风格预设 -->
            <div v-else-if="activeTab === 'templates'">
              <AiTemplateSettings
                :on-ask-confirm="onAskConfirm"
              />
            </div>
          </div>
        </main>
      </div>
    </div>
  </Teleport>
</template>
