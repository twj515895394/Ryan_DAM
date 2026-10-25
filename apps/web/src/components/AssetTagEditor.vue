<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import SidebarIcon from "./SidebarIcon.vue";
import { createTag, library, updateAssetTags } from "../stores/library";
import type { AssetOut } from "../api/types";

const props = defineProps<{ asset: AssetOut }>();

const tagQuery = ref("");
const isTagDropdownOpen = ref(false);
const isTagSubmitting = ref(false);
const tagInputRef = ref<HTMLInputElement | null>(null);
const tagInputContainerRef = ref<HTMLElement | null>(null);

const trimmedTagQuery = computed(() => tagQuery.value.trim());

const matchedExactTag = computed(() => {
  if (!trimmedTagQuery.value) return null;
  const q = trimmedTagQuery.value.toLowerCase();
  return library.tags.find((t) => t.name.toLowerCase() === q) ?? null;
});

const isMatchedTagAlreadyAttached = computed(() => {
  if (!matchedExactTag.value) return false;
  return props.asset.tags.some((t) => t.id === matchedExactTag.value?.id);
});

const isNewTagCandidate = computed(() => {
  return trimmedTagQuery.value.length > 0 && matchedExactTag.value === null;
});

const filteredTags = computed(() => {
  const q = trimmedTagQuery.value.toLowerCase();
  const list = q
    ? library.tags.filter((t) => t.name.toLowerCase().includes(q))
    : library.tags;
  return list.map((tag) => ({
    ...tag,
    isAttached: props.asset.tags.some((t) => t.id === tag.id)
  }));
});

const canSubmitTag = computed(() => {
  if (isTagSubmitting.value) return false;
  if (isNewTagCandidate.value) return true;
  if (matchedExactTag.value && !isMatchedTagAlreadyAttached.value) return true;
  return false;
});

const submitButtonLabel = computed(() => {
  if (isTagSubmitting.value) return "处理中…";
  if (isNewTagCandidate.value) return "新建并打标";
  if (isMatchedTagAlreadyAttached.value) return "已打标";
  return "添加";
});

async function handleTagSubmit(): Promise<void> {
  if (!canSubmitTag.value || isTagSubmitting.value) return;
  const name = trimmedTagQuery.value;
  if (!name) return;

  isTagSubmitting.value = true;
  try {
    let targetTagId: number | null = null;
    if (matchedExactTag.value) {
      targetTagId = matchedExactTag.value.id;
    } else {
      const created = await createTag(name);
      if (!created) return;
      targetTagId = created.id;
    }

    if (targetTagId !== null) {
      const currentIds = props.asset.tags.map((t) => t.id);
      if (!currentIds.includes(targetTagId)) {
        const nextTagIds = [...currentIds, targetTagId];
        const ok = await applyTagIds(nextTagIds);
        if (ok) {
          tagQuery.value = "";
          isTagDropdownOpen.value = false;
        }
      } else {
        tagQuery.value = "";
        isTagDropdownOpen.value = false;
      }
    }
  } finally {
    isTagSubmitting.value = false;
  }
}

async function selectExistingTag(tagId: number): Promise<void> {
  if (isTagSubmitting.value) return;
  if (props.asset.tags.some((t) => t.id === tagId)) return;

  isTagSubmitting.value = true;
  try {
    const nextTagIds = [...props.asset.tags.map((t) => t.id), tagId];
    const ok = await applyTagIds(nextTagIds);
    if (ok) {
      tagQuery.value = "";
      isTagDropdownOpen.value = false;
    }
  } finally {
    isTagSubmitting.value = false;
  }
}

async function removeTag(tagId: number): Promise<void> {
  await applyTagIds(props.asset.tags.filter((t) => t.id !== tagId).map((t) => t.id));
}

async function applyTagIds(tagIds: number[]): Promise<boolean> {
  const ok = await updateAssetTags(props.asset.id, tagIds);
  if (ok) {
    props.asset.tags = tagIds
      .map((id) => library.tags.find((t) => t.id === id))
      .filter((t): t is NonNullable<typeof t> => Boolean(t))
      .map((t) => ({ id: t.id, name: t.name, color: t.color }));
    return true;
  }
  return false;
}

function onDocumentClick(e: MouseEvent | PointerEvent): void {
  if (
    tagInputContainerRef.value &&
    !tagInputContainerRef.value.contains(e.target as Node)
  ) {
    isTagDropdownOpen.value = false;
  }
}

watch(isTagDropdownOpen, (open) => {
  if (open) {
    window.addEventListener("pointerdown", onDocumentClick);
  } else {
    window.removeEventListener("pointerdown", onDocumentClick);
  }
});

watch(
  () => props.asset.id,
  () => {
    tagQuery.value = "";
    isTagDropdownOpen.value = false;
  }
);

onUnmounted(() => {
  window.removeEventListener("pointerdown", onDocumentClick);
});
</script>

<template>
  <div class="mt-4 border-t border-line pt-3">
    <div class="flex items-center justify-between">
      <p class="text-xs font-medium text-muted">标签</p>
      <span v-if="asset.tags.length > 0" class="text-[11px] text-muted">已添加 {{ asset.tags.length }} 项</span>
    </div>

    <!-- 已添加标签药丸 -->
    <div v-if="asset.tags.length > 0" class="mt-2 flex flex-wrap gap-1.5">
      <span
        v-for="tag in asset.tags"
        :key="tag.id"
        class="inline-flex items-center gap-1 rounded-md bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent transition"
      >
        <span>{{ tag.name }}</span>
        <button
          type="button"
          class="rounded p-0.5 text-accent/60 transition hover:bg-accent/20 hover:text-accent"
          title="移除标签"
          @click="removeTag(tag.id)"
        >
          <SidebarIcon name="close" class="h-2.5 w-2.5" />
        </button>
      </span>
    </div>
    <p v-else class="mt-1.5 text-xs text-muted">暂无标签</p>

    <!-- 快捷搜索 / 新建打标输入组件 -->
    <div ref="tagInputContainerRef" class="relative mt-2.5">
      <div class="flex gap-1.5">
        <div class="relative min-w-0 flex-1">
          <input
            ref="tagInputRef"
            v-model="tagQuery"
            type="text"
            placeholder="搜索标签，或输入新标签…"
            class="w-full rounded-lg border border-line bg-white px-2.5 py-1.5 pr-7 text-xs text-ink outline-none transition placeholder:text-muted/60 focus:border-accent focus:ring-1 focus:ring-accent/20"
            @focus="isTagDropdownOpen = true"
            @keydown.enter.prevent="handleTagSubmit"
            @keydown.esc="isTagDropdownOpen = false; tagInputRef?.blur()"
          />
          <button
            v-if="tagQuery"
            type="button"
            class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 text-muted/60 hover:text-ink"
            title="清空"
            @click="tagQuery = ''; isTagDropdownOpen = true; tagInputRef?.focus()"
          >
            <SidebarIcon name="close" class="h-3 w-3" />
          </button>
          <button
            v-else
            type="button"
            class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 text-muted/50 hover:text-ink"
            title="展开标签列表"
            @click="isTagDropdownOpen = !isTagDropdownOpen; if (isTagDropdownOpen) tagInputRef?.focus()"
          >
            <SidebarIcon name="chevron-right" class="h-3 w-3 transition-transform duration-150" :class="isTagDropdownOpen ? 'rotate-90' : ''" />
          </button>
        </div>

        <button
          type="button"
          class="shrink-0 rounded-lg px-2.5 py-1.5 text-xs font-medium text-white transition disabled:cursor-not-allowed disabled:opacity-40"
          :class="isNewTagCandidate ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-accent hover:bg-blue-700'"
          :disabled="!canSubmitTag || isTagSubmitting"
          @click="handleTagSubmit"
        >
          <span class="flex items-center gap-1">
            <SidebarIcon v-if="isNewTagCandidate" name="plus" class="h-3 w-3" />
            <span>{{ submitButtonLabel }}</span>
          </span>
        </button>
      </div>

      <!-- 下拉推荐与新建面板 -->
      <div
        v-if="isTagDropdownOpen"
        class="absolute left-0 right-0 top-full z-40 mt-1 max-h-56 overflow-y-auto rounded-xl border border-line bg-white p-1 shadow-lg"
      >
        <!-- 快捷选项：库中不存在时直接新建并打标 -->
        <div
          v-if="isNewTagCandidate"
          class="mb-1 rounded-lg border border-emerald-200 bg-emerald-50/70 p-1"
        >
          <button
            type="button"
            class="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs font-medium text-emerald-800 transition hover:bg-emerald-100/70"
            @click="handleTagSubmit"
          >
            <span class="flex items-center gap-1.5 truncate">
              <SidebarIcon name="plus" class="h-3.5 w-3.5 shrink-0 text-emerald-600" />
              <span class="truncate">新建并打标 “<span class="font-bold">{{ trimmedTagQuery }}</span>”</span>
            </span>
            <span class="shrink-0 rounded bg-emerald-200/80 px-1 py-0.5 text-[10px] text-emerald-800">回车创建</span>
          </button>
        </div>

        <!-- 匹配已有标签列表 -->
        <div v-if="filteredTags.length > 0">
          <div class="px-2 py-1 text-[10px] font-semibold tracking-wider text-muted/70 uppercase">
            {{ trimmedTagQuery ? "匹配已有标签" : "标签库" }}
          </div>
          <button
            v-for="tag in filteredTags"
            :key="tag.id"
            type="button"
            class="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs transition"
            :class="tag.isAttached ? 'opacity-50 cursor-not-allowed bg-canvas/40 text-muted' : 'text-ink hover:bg-canvas hover:text-accent'"
            :disabled="tag.isAttached"
            @click="selectExistingTag(tag.id)"
          >
            <span class="flex items-center gap-1.5 truncate">
              <SidebarIcon name="tag" class="h-3 w-3 shrink-0 text-muted" />
              <span class="truncate">{{ tag.name }}</span>
            </span>
            <span v-if="tag.isAttached" class="shrink-0 text-[10px] text-muted">已添加</span>
            <span v-else class="shrink-0 text-[10px] text-muted/60">点击添加</span>
          </button>
        </div>

        <!-- 空状态提示 -->
        <div
          v-else-if="!isNewTagCandidate"
          class="px-3 py-3 text-center text-xs text-muted"
        >
          {{ trimmedTagQuery ? "无匹配标签" : (library.tags.length === 0 ? "暂无标签，输入名称即可新建" : "全部标签已添加") }}
        </div>
      </div>
    </div>
  </div>
</template>
