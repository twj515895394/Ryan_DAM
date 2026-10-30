<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import SidebarIcon from "./SidebarIcon.vue";
import {
  library,
  createTag,
  bulkAddTags,
  bulkRemoveTags,
  bulkMove,
  clearAssetSelection
} from "../stores/library";
import { useFolderOptions } from "../composables/useFolderOptions";

const props = defineProps<{
  totalCurrentAssets: number;
}>();

const emit = defineEmits<{
  (e: "select-all"): void;
  (e: "ask-trash"): void;
  (e: "ask-convert"): void;
  (e: "ask-batch-reverse"): void;
}>();

const { allFolderGroups } = useFolderOptions();

const selectedImageAssets = computed(() => {
  const selectedSet = new Set(library.selectedAssetIds);
  if (!library.assets?.items) return [];
  return library.assets.items.filter((a) => selectedSet.has(a.id) && a.asset_type === "image");
});

const hasExternalSelected = computed(() => {
  const selectedSet = new Set(library.selectedAssetIds);
  if (!library.assets?.items) return false;
  return library.assets.items.some((a) => selectedSet.has(a.id) && a.source_type === "external");
});

type BatchPanelKey = "none" | "add-tag" | "remove-tag" | "move";

const batchPanel = ref<BatchPanelKey>("none");
const batchTagQuery = ref("");
const isBatchTagSubmitting = ref(false);

// ── 上弹浮层锚定：批量栏是横向滚动容器（overflow-x-auto 会把 overflow-y 一并
// 计算为 auto 而裁切子级），因此三个面板必须 Teleport 到 body 用 fixed 定位 ──
const PANEL_WIDTHS: Record<Exclude<BatchPanelKey, "none">, number> = {
  "add-tag": 256,
  "remove-tag": 208,
  move: 288,
};

const barRoot = ref<HTMLElement | null>(null);
const flyout = ref<{ left: number; bottom: number; width: number } | null>(null);

const flyoutStyle = computed(() => {
  const f = flyout.value;
  if (!f) return {};
  return { left: `${f.left}px`, bottom: `${f.bottom}px`, width: `${f.width}px` };
});

function togglePanel(key: Exclude<BatchPanelKey, "none">, event: MouseEvent): void {
  if (batchPanel.value === key) {
    batchPanel.value = "none";
    return;
  }
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const width = PANEL_WIDTHS[key];
  const margin = 12;
  flyout.value = {
    left: Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin)),
    bottom: window.innerHeight - rect.top + 8,
    width,
  };
  batchPanel.value = key;
}

function closePanel(): void {
  batchPanel.value = "none";
}

function handleDocPointerDown(event: PointerEvent): void {
  const target = event.target as Node | null;
  if (!target) return;
  if (document.querySelector("[data-batch-flyout]")?.contains(target)) return;
  if (barRoot.value?.contains(target)) return;
  closePanel();
}

function handleDocKeyDown(event: KeyboardEvent): void {
  if (event.key !== "Escape") return;
  event.preventDefault();
  event.stopPropagation();
  closePanel();
}

watch(batchPanel, (panel) => {
  if (panel === "none") {
    document.removeEventListener("pointerdown", handleDocPointerDown, true);
    window.removeEventListener("keydown", handleDocKeyDown, true);
    return;
  }
  document.addEventListener("pointerdown", handleDocPointerDown, true);
  window.addEventListener("keydown", handleDocKeyDown, true);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", handleDocPointerDown, true);
  window.removeEventListener("keydown", handleDocKeyDown, true);
});

const trimmedBatchTagQuery = computed(() => batchTagQuery.value.trim());

const matchedExactBatchTag = computed(() => {
  if (!trimmedBatchTagQuery.value) return null;
  const q = trimmedBatchTagQuery.value.toLowerCase();
  return library.tags.find((t) => t.name.toLowerCase() === q) ?? null;
});

const isNewBatchTagCandidate = computed(() => {
  return trimmedBatchTagQuery.value.length > 0 && matchedExactBatchTag.value === null;
});

const filteredBatchTags = computed(() => {
  const q = trimmedBatchTagQuery.value.toLowerCase();
  if (!q) return library.tags;
  return library.tags.filter((t) => t.name.toLowerCase().includes(q));
});

watch(batchPanel, (panel) => {
  if (panel === "add-tag") {
    batchTagQuery.value = "";
  }
});

async function handleBatchAddTagSubmit(): Promise<void> {
  const name = trimmedBatchTagQuery.value;
  if (!name || isBatchTagSubmitting.value) return;

  isBatchTagSubmitting.value = true;
  try {
    let targetTagId: number | null = null;
    if (matchedExactBatchTag.value) {
      targetTagId = matchedExactBatchTag.value.id;
    } else {
      const created = await createTag(name);
      if (!created) return;
      targetTagId = created.id;
    }
    if (targetTagId !== null) {
      await bulkAddTags(targetTagId);
      batchTagQuery.value = "";
      batchPanel.value = "none";
    }
  } finally {
    isBatchTagSubmitting.value = false;
  }
}

async function handleBatchSelectTag(tagId: number): Promise<void> {
  if (isBatchTagSubmitting.value) return;
  isBatchTagSubmitting.value = true;
  try {
    await bulkAddTags(tagId);
    batchTagQuery.value = "";
    batchPanel.value = "none";
  } finally {
    isBatchTagSubmitting.value = false;
  }
}

function handleBatchRemoveTag(tagId: number): void {
  void bulkRemoveTags(tagId);
  batchPanel.value = "none";
}

function handleBatchMove(folderId: number): void {
  void bulkMove(folderId);
  batchPanel.value = "none";
}
</script>

<template>
  <div class="fixed bottom-5 left-1/2 z-40 -translate-x-1/2 max-w-[calc(100vw-2.5rem)]">
    <div
      ref="barRoot"
      class="flex items-center gap-1.5 overflow-x-auto scrollbar-none rounded-2xl border border-line/80 bg-white/95 px-3 py-2 shadow-2xl backdrop-blur-xl"
      @scroll="closePanel"
    >
      <!-- 选择数量与全选控制组 -->
      <div class="flex shrink-0 items-center gap-1.5 pr-1">
        <span class="whitespace-nowrap text-xs font-semibold text-ink">
          已选 {{ library.selectedAssetIds.length }} 项
        </span>
        <button
          v-if="library.selectedAssetIds.length < props.totalCurrentAssets"
          type="button"
          class="shrink-0 whitespace-nowrap rounded-md bg-canvas/80 px-2 py-1 text-xs font-medium text-accent transition hover:bg-accent/10"
          title="全选当前列表所有资产 (Ctrl+A)"
          @click="emit('select-all')"
        >
          全选
        </button>
        <button
          v-else
          type="button"
          class="shrink-0 whitespace-nowrap rounded-md bg-canvas/80 px-2 py-1 text-xs font-medium text-muted transition hover:bg-canvas hover:text-ink"
          title="清空当前所有选中 (Esc)"
          @click="clearAssetSelection"
        >
          全不选
        </button>
      </div>

      <!-- 分隔线 -->
      <div class="mx-0.5 h-4 w-px shrink-0 bg-line/80" />

      <!-- 加标签面板 -->
      <div class="relative shrink-0">
        <button
          type="button"
          class="flex h-8 shrink-0 items-center gap-1 whitespace-nowrap rounded-lg px-2.5 text-xs font-medium transition"
          :class="batchPanel === 'add-tag' ? 'bg-accent/15 text-accent' : 'text-ink hover:bg-canvas'"
          @click="togglePanel('add-tag', $event)"
        >
          <SidebarIcon name="plus" class="h-3 w-3 text-muted" />
          <span>加标签</span>
        </button>

        <Teleport to="body">
          <div
            v-if="batchPanel === 'add-tag'"
            data-batch-flyout
            class="fixed z-[55] rounded-xl border border-line bg-white/95 p-2 shadow-xl backdrop-blur-xl"
            :style="flyoutStyle"
          >
            <div class="relative">
              <input
                v-model="batchTagQuery"
                type="text"
                placeholder="搜索标签，或输入新标签…"
                class="w-full rounded-lg border border-line bg-white px-2.5 py-1.5 pr-7 text-xs text-ink outline-none transition placeholder:text-muted/60 focus:border-accent focus:ring-1 focus:ring-accent/20"
                @keydown.enter.prevent="handleBatchAddTagSubmit"
              />
              <button
                v-if="batchTagQuery"
                type="button"
                class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 text-muted/60 hover:text-ink"
                title="清空"
                @click="batchTagQuery = ''"
              >
                <SidebarIcon name="close" class="h-3 w-3" />
              </button>
            </div>

            <div
              v-if="isNewBatchTagCandidate"
              class="mt-1.5 rounded-lg border border-emerald-200 bg-emerald-50/70 p-1"
            >
              <button
                type="button"
                class="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs font-medium text-emerald-800 transition hover:bg-emerald-100/70"
                :disabled="isBatchTagSubmitting"
                @click="handleBatchAddTagSubmit"
              >
                <span class="flex items-center gap-1.5 truncate">
                  <SidebarIcon name="plus" class="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                  <span class="truncate">新建并打标 “<span class="font-bold">{{ trimmedBatchTagQuery }}</span>”</span>
                </span>
                <span class="shrink-0 rounded bg-emerald-200/80 px-1 py-0.5 text-[10px] text-emerald-800">
                  {{ isBatchTagSubmitting ? "打标中…" : "回车" }}
                </span>
              </button>
            </div>

            <div v-if="filteredBatchTags.length > 0" class="mt-1.5 max-h-48 overflow-y-auto">
              <div class="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted/70">
                {{ trimmedBatchTagQuery ? "匹配已有标签" : "选择已有标签" }}
              </div>
              <button
                v-for="tag in filteredBatchTags"
                :key="tag.id"
                type="button"
                class="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs text-ink transition hover:bg-canvas hover:text-accent"
                :disabled="isBatchTagSubmitting"
                @click="handleBatchSelectTag(tag.id)"
              >
                <span class="flex items-center gap-1.5 truncate">
                  <SidebarIcon name="tag" class="h-3 w-3 shrink-0 text-muted" />
                  <span class="truncate">{{ tag.name }}</span>
                </span>
                <span class="shrink-0 text-[10px] text-muted/60">点击打标</span>
              </button>
            </div>

            <div
              v-else-if="!isNewBatchTagCandidate"
              class="px-3 py-3 text-center text-xs text-muted"
            >
              {{ trimmedBatchTagQuery ? "无匹配标签，回车可新建" : "暂无标签，输入名称即可新建" }}
            </div>
          </div>
        </Teleport>
      </div>

      <!-- 移除标签面板 -->
      <div class="relative shrink-0">
        <button
          type="button"
          class="flex h-8 shrink-0 items-center gap-1 whitespace-nowrap rounded-lg px-2.5 text-xs font-medium transition"
          :class="batchPanel === 'remove-tag' ? 'bg-accent/15 text-accent' : 'text-ink hover:bg-canvas'"
          @click="togglePanel('remove-tag', $event)"
        >
          <span>移除标签</span>
        </button>
        <Teleport to="body">
          <div
            v-if="batchPanel === 'remove-tag'"
            data-batch-flyout
            class="fixed z-[55] rounded-xl border border-line bg-white/95 p-2 shadow-xl backdrop-blur-xl"
            :style="flyoutStyle"
          >
            <p v-if="library.tags.length === 0" class="px-2 py-1 text-xs text-muted">暂无标签</p>
            <button
              v-for="tag in library.tags"
              :key="tag.id"
              type="button"
              class="block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-xs text-ink transition hover:bg-canvas hover:text-rose-600"
              @click="handleBatchRemoveTag(tag.id)"
            >
              {{ tag.name }}
            </button>
          </div>
        </Teleport>
      </div>

      <!-- 跨项目/跨库移动面板（结构化分组展示） -->
      <div class="relative shrink-0">
        <button
          type="button"
          class="flex h-8 shrink-0 items-center gap-1 whitespace-nowrap rounded-lg px-2.5 text-xs font-medium transition"
          :class="batchPanel === 'move' ? 'bg-accent/15 text-accent' : 'text-ink hover:bg-canvas'"
          @click="togglePanel('move', $event)"
        >
          <span>移动到…</span>
        </button>
        <Teleport to="body">
          <div
            v-if="batchPanel === 'move'"
            data-batch-flyout
            class="fixed z-[55] max-h-72 overflow-y-auto rounded-xl border border-line bg-white/95 p-1.5 shadow-xl backdrop-blur-xl"
            :style="flyoutStyle"
          >
            <p v-if="allFolderGroups.length === 0" class="px-2 py-2 text-xs text-muted">暂无可移动到的目录</p>
            <div
              v-for="group in allFolderGroups"
              :key="group.id"
              class="mb-2 last:mb-0"
            >
              <div class="rounded bg-canvas/80 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted/80">
                {{ group.label }}
              </div>
              <div class="mt-0.5 space-y-0.5">
                <button
                  v-for="option in group.options"
                  :key="option.id"
                  type="button"
                  class="block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-xs text-ink transition hover:bg-canvas hover:text-accent"
                  :title="option.label"
                  @click="handleBatchMove(option.id)"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>
          </div>
        </Teleport>
      </div>

      <!-- 分隔线 -->
      <div
        v-if="selectedImageAssets.length > 0 || hasExternalSelected"
        class="mx-0.5 h-4 w-px shrink-0 bg-line/80"
      />

      <!-- 批量 AI 提示词反推 -->
      <button
        v-if="selectedImageAssets.length > 0"
        type="button"
        class="flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-accent/20 bg-accent/10 px-2.5 text-xs font-medium text-accent transition hover:bg-accent/20"
        :title="`对选中的 ${selectedImageAssets.length} 张图片批量反推视觉提示词`"
        @click="batchPanel = 'none'; emit('ask-batch-reverse')"
      >
        <SidebarIcon name="star" class="h-3.5 w-3.5" />
        <span>AI 批量反推 ({{ selectedImageAssets.length }})</span>
      </button>

      <!-- 当选中有外部链接素材时，提供转为系统托管批量操作项 -->
      <button
        v-if="hasExternalSelected"
        type="button"
        class="flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-line bg-canvas/60 px-2.5 text-xs font-medium text-ink transition hover:bg-canvas"
        title="将选中的外部链接素材复制为系统托管存储"
        @click="batchPanel = 'none'; emit('ask-convert')"
      >
        <span>转为系统托管</span>
      </button>

      <!-- 分隔线 -->
      <div class="mx-0.5 h-4 w-px shrink-0 bg-line/80" />

      <!-- 删除操作 -->
      <button
        type="button"
        class="flex h-8 shrink-0 items-center whitespace-nowrap rounded-lg px-2.5 text-xs font-medium text-rose-600 transition hover:bg-rose-50"
        @click="emit('ask-trash')"
      >
        删除
      </button>

      <!-- 取消选中操作 -->
      <button
        type="button"
        class="flex h-8 shrink-0 items-center whitespace-nowrap rounded-lg px-2.5 text-xs font-medium text-muted transition hover:bg-canvas hover:text-ink"
        @click="clearAssetSelection(); batchPanel = 'none'"
      >
        取消
      </button>
    </div>
  </div>
</template>
