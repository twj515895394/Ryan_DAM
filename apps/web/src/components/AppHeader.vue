<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import SidebarIcon from "./SidebarIcon.vue";
import FilterPopover from "./FilterPopover.vue";
import SortControl from "./SortControl.vue";
import { library } from "../stores/library";

const props = defineProps<{
  viewMode: "library" | "trash";
  locationTitle: string;
  activeScope: "general" | "project";
  activeProjectName: string | null;
  activeFolderId: number | null;
  canImport: boolean;
}>();

const emit = defineEmits<{
  (e: "empty-trash"): void;
  (e: "start-import"): void;
  (e: "start-folder-import"): void;
}>();

// ── 搜索状态与防抖 ───────────────────────────────────────────
const searchInputRef = ref<HTMLInputElement | null>(null);
const searchFocused = ref(false);
const searchDraft = ref(library.assetQuery.q);
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;

watch(
  () => library.assetQuery.q,
  (val) => {
    if (val !== searchDraft.value) {
      searchDraft.value = val;
    }
  }
);

watch(searchDraft, (val) => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    library.assetQuery.q = val;
  }, 300);
});

function commitSearchImmediately(): void {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
  library.assetQuery.q = searchDraft.value;
}

function clearSearch(): void {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
  searchDraft.value = "";
  library.assetQuery.q = "";
}

// 全局 Ctrl+K / Cmd+K 快捷键聚焦搜索
function onWindowKeydown(e: KeyboardEvent): void {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    searchInputRef.value?.focus();
    searchInputRef.value?.select();
  }
}

onMounted(() => {
  window.addEventListener("keydown", onWindowKeydown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", onWindowKeydown);
});

// ── 筛选弹层状态 ─────────────────────────────────────────────
const showFilterPopover = ref(false);

const activeFilterCount = computed(() => {
  let count = 0;
  // 顶部类型分段栏已直观展示当前类型，此处仅统计其他高级筛选条件（体积、时间、标签），避免点选快捷类型时导致筛选按钮尺寸和形态跳变
  if (library.assetQuery.sizeRange) count += 1;
  if (library.assetQuery.modifiedRange) count += 1;
  if (library.assetQuery.tagId !== null) count += 1;
  return count;
});

// ── 保留的文件类型快捷分段栏（常用快速切换） ───────────────────────
const quickTypes: Array<{
  value: "" | "image" | "video" | "audio" | "document" | "other";
  label: string;
}> = [
  { value: "", label: "全部" },
  { value: "image", label: "图片" },
  { value: "video", label: "视频" },
  { value: "audio", label: "音频" },
  { value: "document", label: "文档" }
];
</script>

<template>
  <header class="relative z-30 flex h-14 shrink-0 items-center justify-between border-b border-line bg-white/80 px-6 backdrop-blur-md">
    <!-- 左侧：位置标题与资产数量 -->
    <div class="min-w-0 flex items-center gap-3">
      <div>
        <h1 class="truncate text-base font-semibold text-ink leading-tight">
          {{ viewMode === "trash" ? "回收站" : locationTitle }}
        </h1>
        <p class="text-[11px] text-muted">
          <template v-if="viewMode === 'trash'">已删除的资产 · {{ library.trash.length }} 项</template>
          <template v-else>
            {{ activeScope === "general" ? "通用资产库" : activeProjectName ?? "项目资产库" }}
            <template v-if="library.assets">· {{ library.assets.total }} 项</template>
          </template>
        </p>
      </div>
    </div>

    <!-- 回收站专属操作 -->
    <div v-if="viewMode === 'trash'" class="flex items-center gap-2">
      <button
        class="rounded-xl border border-rose-200 bg-white px-4 py-2 text-sm font-medium text-rose-600 transition hover:bg-rose-50 active:scale-97 disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="library.trash.length === 0"
        @click="emit('empty-trash')"
      >
        清空回收站
      </button>
    </div>

    <!-- 正常库视图顶栏综合操作区 -->
    <div v-else class="flex items-center gap-2.5">
      <!-- 快捷文件类型分段切换器（保留用户要求的快捷筛选） -->
      <nav
        class="hidden lg:inline-flex items-center rounded-xl border border-line bg-canvas/70 p-0.5 shadow-2xs"
        aria-label="快捷类型筛选"
      >
        <button
          v-for="qt in quickTypes"
          :key="qt.value"
          type="button"
          class="rounded-lg px-2.5 py-1 text-xs font-medium transition active:scale-97"
          :class="
            library.assetQuery.assetType === qt.value
              ? 'bg-white text-accent shadow-xs'
              : 'text-muted hover:text-ink'
          "
          @click="library.assetQuery.assetType = qt.value"
        >
          {{ qt.label }}
        </button>
      </nav>

      <!-- 动态平滑扩展搜索条（支持 Ctrl+K 聚焦与 Escape 取消） -->
      <div
        class="relative transition-all duration-200 ease-out"
        :class="searchFocused || searchDraft ? 'w-64 sm:w-72' : 'w-48 sm:w-56'"
      >
        <SidebarIcon
          name="search"
          class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 transition-colors"
          :class="searchFocused ? 'text-accent' : 'text-muted/60'"
        />
        <input
          ref="searchInputRef"
          v-model="searchDraft"
          type="text"
          placeholder="搜索资产或文件夹…"
          class="w-full rounded-xl border border-line bg-white/95 pl-8 text-xs text-ink outline-none transition placeholder:text-muted/70 focus:border-accent focus:ring-2 focus:ring-accent/10 h-9"
          :class="searchDraft ? 'pr-7' : 'pr-12'"
          @focus="searchFocused = true"
          @blur="searchFocused = false"
          @keydown.enter="commitSearchImmediately"
          @keydown.esc="clearSearch"
        />

        <!-- 清空按钮 -->
        <button
          v-if="searchDraft"
          type="button"
          class="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-muted hover:text-ink transition"
          title="清空搜索"
          @click="clearSearch"
        >
          <SidebarIcon name="close" class="h-3 w-3" />
        </button>

        <!-- 键盘流徽标 Ctrl+K -->
        <div
          v-else
          class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 hidden sm:flex items-center gap-0.5"
        >
          <kbd class="rounded border border-line/80 bg-canvas/60 px-1 py-0.5 text-[10px] font-mono text-muted/70 leading-none">
            ⌘K
          </kbd>
        </div>
      </div>

      <!-- 高级多维筛选气泡按钮（定宽 w-[74px] 居中对齐，预留恒定宽度，避免激活徽标时挤压周围组件变形移位） -->
      <div class="relative">
        <button
          type="button"
          class="inline-flex h-9 w-[74px] items-center justify-center gap-1.5 rounded-xl border text-xs font-medium transition active:scale-97 select-none"
          :class="
            activeFilterCount > 0
              ? 'border-accent bg-accent/10 text-accent font-semibold'
              : 'border-line bg-white hover:bg-canvas/50 text-ink'
          "
          :title="activeFilterCount > 0 ? `已激活 ${activeFilterCount} 项过滤条件` : '打开多维筛选面板'"
          @click="showFilterPopover = !showFilterPopover"
        >
          <SidebarIcon name="filter" class="h-3.5 w-3.5 shrink-0" />
          <span>筛选</span>
          <span
            v-if="activeFilterCount > 0"
            class="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent text-[10px] font-semibold text-white px-1 leading-none shrink-0"
          >
            {{ activeFilterCount }}
          </span>
        </button>

        <!-- 独立抽离的毛玻璃筛选面板 -->
        <FilterPopover
          :open="showFilterPopover"
          @close="showFilterPopover = false"
        />
      </div>

      <!-- Apple HIG 连体排序组件 -->
      <SortControl />

      <!-- 垂直微分隔线 -->
      <div class="hidden sm:block h-5 w-[1px] bg-line/80 mx-0.5"></div>

      <!-- 导入按钮组 -->
      <div class="flex items-center gap-1.5">
        <button
          class="inline-flex h-9 items-center rounded-xl border border-line bg-white px-3 text-xs font-medium transition hover:bg-canvas text-ink active:scale-97 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="!props.canImport"
          :title="props.activeFolderId === null ? (props.activeScope === 'project' ? '选择本地文件夹，直接作为当前项目目录导入' : '选择本地文件夹，作为顶层目录导入') : '选择本地文件夹，导入到当前目录'"
          @click="emit('start-folder-import')"
        >
          导入文件夹
        </button>
        <button
          class="inline-flex h-9 items-center rounded-xl bg-accent px-3.5 text-xs font-medium text-white shadow-xs transition hover:bg-blue-700 active:scale-97 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="!props.canImport"
          :title="props.activeFolderId === null ? '选择文件导入（可指定或新建目录）' : '选择文件并导入到当前目录'"
          @click="emit('start-import')"
        >
          导入文件
        </button>
      </div>
    </div>
  </header>
</template>
