<script setup lang="ts">
import { computed, ref, watch } from "vue";
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
}>();

const { allFolderGroups } = useFolderOptions();

const hasExternalSelected = computed(() => {
  const selectedSet = new Set(library.selectedAssetIds);
  if (!library.assets?.items) return false;
  return library.assets.items.some((a) => selectedSet.has(a.id) && a.source_type === "external");
});

const batchPanel = ref<"none" | "add-tag" | "remove-tag" | "move">("none");
const batchTagQuery = ref("");
const isBatchTagSubmitting = ref(false);

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
  <div class="fixed bottom-5 left-1/2 z-40 -translate-x-1/2">
    <div class="flex items-center gap-2 rounded-2xl border border-line bg-white px-4 py-2.5 shadow-soft">
      <div class="mr-1 flex items-center gap-1.5">
        <span class="text-sm font-medium">已选 {{ library.selectedAssetIds.length }} 项</span>
        <button
          v-if="library.selectedAssetIds.length < props.totalCurrentAssets"
          type="button"
          class="rounded-md px-1.5 py-0.5 text-xs font-medium text-accent transition hover:bg-accent/10"
          title="全选当前列表所有资产 (Ctrl+A)"
          @click="emit('select-all')"
        >
          全选
        </button>
        <button
          v-else
          type="button"
          class="rounded-md px-1.5 py-0.5 text-xs font-medium text-muted transition hover:bg-canvas"
          title="清空当前所有选中 (Esc)"
          @click="clearAssetSelection"
        >
          全不选
        </button>
      </div>

      <!-- 加标签面板 -->
      <div class="relative">
        <button
          class="rounded-lg px-3 py-1.5 text-sm transition"
          :class="batchPanel === 'add-tag' ? 'bg-accent/10 font-medium text-accent' : 'text-ink hover:bg-canvas'"
          @click="batchPanel = batchPanel === 'add-tag' ? 'none' : 'add-tag'"
        >
          加标签
        </button>

        <div
          v-if="batchPanel === 'add-tag'"
          class="absolute bottom-11 left-0 z-50 w-64 rounded-xl border border-line bg-white p-2 shadow-soft"
        >
          <div class="relative">
            <input
              v-model="batchTagQuery"
              type="text"
              placeholder="搜索标签，或输入新标签…"
              class="w-full rounded-lg border border-line bg-white px-2.5 py-1.5 pr-7 text-xs text-ink outline-none transition placeholder:text-muted/60 focus:border-accent focus:ring-1 focus:ring-accent/20"
              @keydown.enter.prevent="handleBatchAddTagSubmit"
              @keydown.esc="batchPanel = 'none'"
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
      </div>

      <!-- 移除标签面板 -->
      <div class="relative">
        <button
          class="rounded-lg px-3 py-1.5 text-sm text-ink transition hover:bg-canvas"
          @click="batchPanel = batchPanel === 'remove-tag' ? 'none' : 'remove-tag'"
        >
          移除标签
        </button>
        <div
          v-if="batchPanel === 'remove-tag'"
          class="absolute bottom-11 left-0 z-50 w-52 rounded-xl border border-line bg-white p-2 shadow-soft"
        >
          <p v-if="library.tags.length === 0" class="px-2 py-1 text-xs text-muted">暂无标签</p>
          <button
            v-for="tag in library.tags"
            :key="tag.id"
            class="block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-sm transition hover:bg-canvas"
            @click="handleBatchRemoveTag(tag.id)"
          >
            {{ tag.name }}
          </button>
        </div>
      </div>

      <!-- 跨项目/跨库移动面板（结构化分组展示） -->
      <div class="relative">
        <button
          class="rounded-lg px-3 py-1.5 text-sm text-ink transition hover:bg-canvas"
          @click="batchPanel = batchPanel === 'move' ? 'none' : 'move'"
        >
          移动到…
        </button>
        <div
          v-if="batchPanel === 'move'"
          class="absolute bottom-11 left-0 z-50 max-h-72 w-72 overflow-y-auto rounded-xl border border-line bg-white p-1.5 shadow-soft"
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
      </div>

      <!-- 当选中有外部链接素材时，提供转为系统托管批量操作项 -->
      <button
        v-if="hasExternalSelected"
        type="button"
        class="rounded-lg px-3 py-1.5 text-sm text-ink transition hover:bg-canvas"
        title="将选中的外部链接素材复制为系统托管存储"
        @click="batchPanel = 'none'; emit('ask-convert')"
      >
        转为系统托管
      </button>

      <button
        class="rounded-lg px-3 py-1.5 text-sm text-rose-600 transition hover:bg-rose-50"
        @click="emit('ask-trash')"
      >
        删除
      </button>
      <button
        class="rounded-lg px-3 py-1.5 text-sm text-muted transition hover:bg-canvas"
        @click="clearAssetSelection(); batchPanel = 'none'"
      >
        取消
      </button>
    </div>
  </div>
</template>
