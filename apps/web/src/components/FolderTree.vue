<script setup lang="ts">
import { ref } from "vue";

import type { FolderNode } from "../api/types";
import SidebarIcon from "./SidebarIcon.vue";

const props = withDefaults(
  defineProps<{
    nodes: FolderNode[];
    activeId: number | null;
    depth?: number;
  }>(),
  { depth: 0 }
);

const emit = defineEmits<{
  (e: "select", node: FolderNode): void;
  (e: "create-child", node: FolderNode): void;
  (e: "edit", node: FolderNode): void;
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
        class="group flex h-7 items-center gap-1.5 rounded-md px-2 transition-colors duration-100"
        :class="[
          depth === 0 ? 'text-[13px]' : 'text-xs text-ink/80',
          activeId === node.id
            ? 'bg-accent/10 font-medium text-accent'
            : 'hover:bg-black/5 text-ink'
        ]"
        role="button"
        tabindex="0"
        @click="emit('select', node)"
        @keydown.enter="emit('select', node)"
      >
        <!-- 折叠/展开箭头 -->
        <button
          v-if="node.children.length > 0"
          class="flex h-4 w-4 shrink-0 items-center justify-center rounded text-muted hover:text-ink"
          :aria-label="collapsed.has(node.id) ? '展开目录' : '折叠目录'"
          @click.stop="toggle(node)"
        >
          <SidebarIcon
            name="chevron-right"
            class="h-3 w-3 transition-transform duration-150"
            :class="collapsed.has(node.id) ? '' : 'rotate-90'"
          />
        </button>
        <span v-else class="h-4 w-4 shrink-0" />

        <!-- 目录图标 -->
        <SidebarIcon
          :name="node.children.length > 0 && !collapsed.has(node.id) ? 'folder-open' : 'folder'"
          class="h-3.5 w-3.5 text-muted group-hover:text-ink/80"
          :class="activeId === node.id ? 'text-accent' : ''"
        />

        <!-- 目录名称 + 锁定徽记 -->
        <span class="flex min-w-0 flex-1 items-center gap-1">
          <span class="truncate">{{ node.name }}</span>
          <span v-if="node.locked" class="shrink-0 text-amber-500" title="已锁定：该文件夹不会被删除">
            <SidebarIcon name="lock" class="h-3 w-3" />
          </span>
        </span>

        <!-- 悬停操作按钮组 -->
        <span class="hidden shrink-0 items-center gap-0.5 group-hover:flex">
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-accent hover:shadow-xs"
            title="新建子文件夹"
            @click.stop="emit('create-child', node)"
          >
            <SidebarIcon name="plus" class="h-3 w-3" />
          </button>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-ink hover:shadow-xs"
            title="编辑文件夹"
            @click.stop="emit('edit', node)"
          >
            <SidebarIcon name="edit" class="h-3 w-3" />
          </button>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-rose-600 hover:shadow-xs disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-muted disabled:hover:shadow-none"
            :class="node.locked ? 'text-muted/50' : ''"
            :title="node.locked ? '已锁定，需在「编辑文件夹」中解除锁定后才能删除' : '删除文件夹'"
            :disabled="node.locked"
            @click.stop="emit('remove', node)"
          >
            <SidebarIcon name="close" class="h-3 w-3" />
          </button>
        </span>
      </div>

      <!-- 子目录递归缩进 -->
      <div v-if="node.children.length > 0 && !collapsed.has(node.id)" class="ml-3.5 border-l border-line/70 pl-1.5">
        <FolderTree
          :nodes="node.children"
          :active-id="activeId"
          :depth="depth + 1"
          @select="(n) => emit('select', n)"
          @create-child="(n) => emit('create-child', n)"
          @edit="(n) => emit('edit', n)"
          @remove="(n) => emit('remove', n)"
        />
      </div>
    </li>
  </ul>
</template>
