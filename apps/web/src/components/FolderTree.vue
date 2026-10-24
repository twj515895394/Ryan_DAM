<script setup lang="ts">
import { ref } from "vue";

import type { FolderNode } from "../api/types";

defineProps<{ nodes: FolderNode[]; activeId: number | null }>();

const emit = defineEmits<{
  (e: "select", node: FolderNode): void;
  (e: "create-child", node: FolderNode): void;
  (e: "rename", node: FolderNode): void;
  (e: "remove", node: FolderNode): void;
}>();

const collapsed = ref(new Set<number>());

function toggle(node: FolderNode): void {
  const next = new Set(collapsed.value);
  if (next.has(node.id)) next.delete(node.id);
  else next.add(node.id);
  collapsed.value = next;
}
</script>

<template>
  <ul class="space-y-0.5">
    <li v-for="node in nodes" :key="node.id">
      <div
        class="group flex items-center gap-1 rounded-lg px-1.5 py-1.5 text-sm transition-colors"
        :class="activeId === node.id ? 'bg-accent/10 font-medium text-accent' : 'hover:bg-canvas'"
        role="button"
        tabindex="0"
        @click="emit('select', node)"
        @keydown.enter="emit('select', node)"
      >
        <button
          v-if="node.children.length > 0"
          class="flex h-4 w-4 shrink-0 items-center justify-center text-muted hover:text-ink"
          :aria-label="collapsed.has(node.id) ? '展开目录' : '折叠目录'"
          @click.stop="toggle(node)"
        >
          <span class="inline-block text-[9px] transition-transform" :class="collapsed.has(node.id) ? '' : 'rotate-90'">▶</span>
        </button>
        <span v-else class="h-4 w-4 shrink-0" />
        <span class="min-w-0 flex-1 truncate">{{ node.name }}</span>
        <span class="hidden shrink-0 items-center gap-0.5 group-hover:flex">
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-accent"
            title="新建子文件夹"
            @click.stop="emit('create-child', node)"
          >＋</button>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-ink"
            title="重命名"
            @click.stop="emit('rename', node)"
          >✎</button>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-rose-600"
            title="删除空目录"
            @click.stop="emit('remove', node)"
          >×</button>
        </span>
      </div>
      <div v-if="node.children.length > 0 && !collapsed.has(node.id)" class="ml-3 border-l border-line pl-1">
        <FolderTree
          :nodes="node.children"
          :active-id="activeId"
          @select="(n) => emit('select', n)"
          @create-child="(n) => emit('create-child', n)"
          @rename="(n) => emit('rename', n)"
          @remove="(n) => emit('remove', n)"
        />
      </div>
    </li>
  </ul>
</template>
