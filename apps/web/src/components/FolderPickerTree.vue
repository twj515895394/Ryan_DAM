<script setup lang="ts">
import { ref } from "vue";

import type { FolderPickerNode } from "../composables/useFolderOptions";
import SidebarIcon from "./SidebarIcon.vue";

const props = withDefaults(
  defineProps<{
    nodes: FolderPickerNode[];
    depth?: number;
  }>(),
  { depth: 0 }
);

const emit = defineEmits<{
  (e: "select", node: FolderPickerNode): void;
}>();

const collapsed = ref(new Set<string>());

function toggle(key: string): void {
  const next = new Set(collapsed.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  collapsed.value = next;
}

function pick(node: FolderPickerNode): void {
  if (node.disabled) return;
  emit("select", node);
}
</script>

<template>
  <ul class="space-y-px">
    <li v-for="node in nodes" :key="node.key">
      <div
        class="group flex h-7 cursor-pointer items-center gap-1.5 rounded-lg px-1.5 transition-colors duration-100"
        :class="
          node.disabled
            ? 'cursor-not-allowed text-muted/50'
            : 'text-ink hover:bg-canvas hover:text-accent'
        "
        :title="node.disabled ? '需选择一个具体目录' : node.label"
        role="button"
        :aria-disabled="node.disabled"
        tabindex="0"
        @click="pick(node)"
        @keydown.enter="pick(node)"
      >
        <!-- 折叠/展开箭头 -->
        <button
          v-if="node.children && node.children.length > 0"
          class="flex h-4 w-4 shrink-0 items-center justify-center rounded text-muted hover:text-ink"
          :aria-label="collapsed.has(node.key) ? '展开目录' : '折叠目录'"
          @click.stop="toggle(node.key)"
        >
          <SidebarIcon
            name="chevron-right"
            class="h-3 w-3 transition-transform duration-150"
            :class="collapsed.has(node.key) ? '' : 'rotate-90'"
          />
        </button>
        <span v-else class="h-4 w-4 shrink-0" />

        <!-- 库 / 项目 / 目录图标 -->
        <SidebarIcon
          :name="node.icon === 'project' ? 'project' : 'folder'"
          class="h-3.5 w-3.5 shrink-0"
          :class="node.icon === 'project' ? 'text-indigo-500' : depth === 0 ? 'text-accent' : 'text-amber-600'"
        />

        <span class="min-w-0 flex-1 truncate text-[13px]" :title="node.label">{{ node.label }}</span>
      </div>

      <!-- 子目录递归缩进 -->
      <div v-if="node.children && node.children.length > 0 && !collapsed.has(node.key)" class="ml-2 border-l border-line/70 pl-1">
        <FolderPickerTree :nodes="node.children" :depth="depth + 1" @select="(n) => emit('select', n)" />
      </div>
    </li>
  </ul>
</template>
