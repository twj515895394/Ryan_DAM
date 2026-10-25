<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import SidebarIcon from "./SidebarIcon.vue";
import { library, clearAssetFilters, type SizeRange, type ModifiedRange } from "../stores/library";

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

const popoverRef = ref<HTMLElement | null>(null);
const tagSearch = ref("");

// 键盘与外部点击关闭监听
function onDocClick(e: MouseEvent): void {
  if (!props.open) return;
  const target = e.target as HTMLElement | null;
  if (popoverRef.value && !popoverRef.value.contains(target)) {
    emit("close");
  }
}

function onDocKeydown(e: KeyboardEvent): void {
  if (props.open && e.key === "Escape") {
    emit("close");
  }
}

onMounted(() => {
  document.addEventListener("mousedown", onDocClick);
  document.addEventListener("keydown", onDocKeydown);
});

onUnmounted(() => {
  document.removeEventListener("mousedown", onDocClick);
  document.removeEventListener("keydown", onDocKeydown);
});

// 过滤标签列表
const filteredTags = computed(() => {
  const q = tagSearch.value.trim().toLowerCase();
  if (!q) return library.tags;
  return library.tags.filter((t) => t.name.toLowerCase().includes(q));
});

// 单选胶囊配置
const typeOptions: Array<{
  value: "" | "image" | "video" | "audio" | "document" | "other";
  label: string;
}> = [
  { value: "", label: "全部" },
  { value: "image", label: "图片" },
  { value: "video", label: "视频" },
  { value: "audio", label: "音频" },
  { value: "document", label: "文档" },
  { value: "other", label: "其他" }
];

const sizeOptions: Array<{ value: SizeRange; label: string }> = [
  { value: "", label: "不限" },
  { value: "small", label: "≤ 1 MB" },
  { value: "medium", label: "1 – 50 MB" },
  { value: "large", label: "≥ 50 MB" }
];

const modifiedOptions: Array<{ value: ModifiedRange; label: string }> = [
  { value: "", label: "不限" },
  { value: "today", label: "今天" },
  { value: "week", label: "最近 7 天" },
  { value: "month", label: "最近 30 天" }
];

function selectTag(id: number | null): void {
  library.assetQuery.tagId = id;
}
</script>

<template>
  <div
    v-if="open"
    ref="popoverRef"
    class="absolute right-0 top-11 z-50 w-80 rounded-2xl border border-white/60 bg-white/95 p-4 shadow-2xl backdrop-blur-xl ring-1 ring-black/5"
  >
    <!-- 头部信息与重置 -->
    <div class="flex items-center justify-between pb-3 border-b border-line/60">
      <div class="flex items-center gap-1.5 text-xs font-semibold text-ink">
        <SidebarIcon name="filter" class="h-3.5 w-3.5 text-accent" />
        <span>多维资产过滤</span>
      </div>
      <button
        type="button"
        class="text-[11px] font-medium text-muted hover:text-accent transition"
        @click="clearAssetFilters"
      >
        清空全部
      </button>
    </div>

    <!-- 资产类型 (胶囊选择) -->
    <div class="mt-3">
      <span class="block text-[11px] font-medium text-muted mb-1.5">文件类型</span>
      <div class="grid grid-cols-3 gap-1.5 bg-canvas/70 p-1 rounded-xl border border-line/50">
        <button
          v-for="opt in typeOptions"
          :key="opt.value"
          type="button"
          class="rounded-lg py-1 px-2 text-xs font-medium transition text-center"
          :class="
            library.assetQuery.assetType === opt.value
              ? 'bg-white text-accent shadow-xs'
              : 'text-muted hover:text-ink'
          "
          @click="library.assetQuery.assetType = opt.value"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>

    <!-- 文件大小 (药丸组) -->
    <div class="mt-3.5">
      <span class="block text-[11px] font-medium text-muted mb-1.5">文件体积</span>
      <div class="grid grid-cols-2 gap-1.5">
        <button
          v-for="opt in sizeOptions"
          :key="opt.value"
          type="button"
          class="rounded-lg border py-1.5 px-2.5 text-xs font-medium transition text-left flex items-center justify-between"
          :class="
            library.assetQuery.sizeRange === opt.value
              ? 'border-accent bg-accent/5 text-accent'
              : 'border-line/70 bg-white text-ink hover:border-line hover:bg-canvas/50'
          "
          @click="library.assetQuery.sizeRange = opt.value"
        >
          <span>{{ opt.label }}</span>
          <SidebarIcon
            v-if="library.assetQuery.sizeRange === opt.value"
            name="check"
            class="h-3 w-3 text-accent"
          />
        </button>
      </div>
    </div>

    <!-- 更新时间 (药丸组) -->
    <div class="mt-3.5">
      <span class="block text-[11px] font-medium text-muted mb-1.5">修改时间</span>
      <div class="grid grid-cols-2 gap-1.5">
        <button
          v-for="opt in modifiedOptions"
          :key="opt.value"
          type="button"
          class="rounded-lg border py-1.5 px-2.5 text-xs font-medium transition text-left flex items-center justify-between"
          :class="
            library.assetQuery.modifiedRange === opt.value
              ? 'border-accent bg-accent/5 text-accent'
              : 'border-line/70 bg-white text-ink hover:border-line hover:bg-canvas/50'
          "
          @click="library.assetQuery.modifiedRange = opt.value"
        >
          <span>{{ opt.label }}</span>
          <SidebarIcon
            v-if="library.assetQuery.modifiedRange === opt.value"
            name="check"
            class="h-3 w-3 text-accent"
          />
        </button>
      </div>
    </div>

    <!-- 关联标签过滤 (带搜索框和即时标签列表) -->
    <div class="mt-3.5">
      <div class="flex items-center justify-between mb-1.5">
        <span class="text-[11px] font-medium text-muted">关联标签</span>
        <span class="text-[10px] text-muted/80">共 {{ library.tags.length }} 个</span>
      </div>

      <!-- 标签轻量快速检索框 -->
      <div v-if="library.tags.length > 5" class="relative mb-2">
        <SidebarIcon
          name="search"
          class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted/60"
        />
        <input
          v-model="tagSearch"
          type="text"
          placeholder="快速筛选标签…"
          class="w-full rounded-lg border border-line bg-canvas/40 py-1 pl-7 pr-6 text-xs text-ink outline-none transition focus:border-accent focus:bg-white"
        />
        <button
          v-if="tagSearch"
          type="button"
          class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 text-muted hover:text-ink"
          @click="tagSearch = ''"
        >
          <SidebarIcon name="close" class="h-2.5 w-2.5" />
        </button>
      </div>

      <!-- 标签药丸瀑布流列表 -->
      <div class="max-h-28 overflow-y-auto rounded-xl border border-line/60 bg-canvas/30 p-1.5 flex flex-wrap gap-1">
        <button
          type="button"
          class="rounded-md px-2 py-0.5 text-[11px] font-medium transition"
          :class="
            library.assetQuery.tagId === null
              ? 'bg-accent text-white shadow-xs'
              : 'bg-white text-muted border border-line/60 hover:text-ink'
          "
          @click="selectTag(null)"
        >
          全部
        </button>
        <button
          v-for="tag in filteredTags"
          :key="tag.id"
          type="button"
          class="rounded-md px-2 py-0.5 text-[11px] font-medium transition flex items-center gap-1"
          :class="
            library.assetQuery.tagId === tag.id
              ? 'bg-accent text-white shadow-xs'
              : 'bg-white text-muted border border-line/60 hover:text-ink'
          "
          @click="selectTag(tag.id)"
        >
          <span>{{ tag.name }}</span>
          <span
            class="text-[9px] opacity-75"
            :class="library.assetQuery.tagId === tag.id ? 'text-white' : 'text-muted'"
          >
            {{ tag.asset_count }}
          </span>
        </button>
      </div>
    </div>

    <!-- 底部操作按钮 -->
    <div class="mt-4 flex items-center justify-end border-t border-line/60 pt-3">
      <button
        type="button"
        class="rounded-xl bg-accent px-4 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 shadow-sm active:scale-97"
        @click="emit('close')"
      >
        完成
      </button>
    </div>
  </div>
</template>
