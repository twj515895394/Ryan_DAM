<script setup lang="ts">
import { inject, provide, ref, type Ref } from "vue";

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
  (e: "toggle-pin", node: FolderNode): void;
}>();

// ── 折叠状态整树共享（provide/inject 沿递归实例下传）────────────────
// 双击目录行只展开「下一级」需要跨层写子孙节点的折叠位，故每个根
// FolderTree 实例建一份 Set，嵌套实例注入同一份。
interface TreeCollapseState {
  collapsed: Ref<Set<number>>;
}

// 必须用字符串 key：`<script setup>` 顶层的 `const` 编译后位于 setup() 内，
// 每个实例都会新建一个 Symbol，父子实例的 Symbol 永不相等导致 inject 静默落空。
// 字符串按值比较，跨实例稳定命中。
const COLLAPSE_STATE_KEY = "ryan-dam-folder-tree-collapse-state";

function createCollapseState(): TreeCollapseState {
  return { collapsed: ref(new Set<number>()) };
}

const collapseState =
  props.depth === 0
    ? createCollapseState()
    : inject(COLLAPSE_STATE_KEY, null) ?? createCollapseState();
provide(COLLAPSE_STATE_KEY, collapseState);
const collapsed = collapseState.collapsed;

function withCollapsed(mutate: (next: Set<number>) => void): void {
  const next = new Set(collapsed.value);
  mutate(next);
  collapsed.value = next;
}

function descendantsWithChildren(node: FolderNode): number[] {
  const ids: number[] = [];
  const walk = (n: FolderNode): void => {
    for (const child of n.children) {
      if (child.children.length > 0) ids.push(child.id);
      walk(child);
    }
  };
  walk(node);
  return ids;
}

/** 箭头点击：保持原有语义——展开时整个子树恢复全部展开。 */
function toggleChevron(node: FolderNode): void {
  withCollapsed((next) => {
    if (next.has(node.id)) {
      next.delete(node.id);
      for (const id of descendantsWithChildren(node)) next.delete(id);
    } else {
      next.add(node.id);
    }
  });
}

/** 双击目录行：只展开/收起下一级——展开时把直接子目录折叠，逐层点开。 */
function toggleOneLevel(node: FolderNode): void {
  if (node.children.length === 0) return;
  withCollapsed((next) => {
    if (next.has(node.id)) {
      next.delete(node.id);
      for (const child of node.children) next.add(child.id);
    } else {
      next.add(node.id);
    }
  });
}
</script>

<template>
  <ul class="space-y-px">
    <li v-for="node in nodes" :key="node.id">
      <div
        class="group flex h-6 items-center gap-1 rounded-md px-1.5 transition-colors duration-100"
        :class="[
          depth === 0 ? 'text-[13px]' : 'text-xs text-ink/80',
          activeId === node.id
            ? 'bg-accent/10 font-medium text-accent'
            : 'hover:bg-black/5 text-ink'
        ]"
        role="button"
        tabindex="0"
        @click="emit('select', node)"
        @dblclick="toggleOneLevel(node)"
        @keydown.enter="emit('select', node)"
      >
        <!-- 折叠/展开箭头（整树全展开语义） -->
        <button
          v-if="node.children.length > 0"
          class="flex h-4 w-4 shrink-0 items-center justify-center rounded text-muted hover:text-ink"
          :aria-label="collapsed.has(node.id) ? '展开目录' : '折叠目录'"
          @click.stop="toggleChevron(node)"
          @dblclick.stop
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

        <!-- 目录名称 + 置顶/锁定徽记 -->
        <span class="flex min-w-0 flex-1 items-center gap-1">
          <span
            class="truncate"
            :title="node.children.length > 0 ? `${node.name}（双击逐层展开/收起子目录）` : node.name"
            >{{ node.name }}</span
          >
          <span v-if="node.pinned" class="shrink-0 text-accent" title="已置顶：始终排在同层最上方">
            <SidebarIcon name="pin" class="h-3 w-3" />
          </span>
          <span v-if="node.locked" class="shrink-0 text-amber-500" title="已锁定：该文件夹不会被删除">
            <SidebarIcon name="lock" class="h-3 w-3" />
          </span>
        </span>

        <!-- 悬停操作按钮组 -->
        <span class="hidden shrink-0 items-center gap-0.5 group-hover:flex" @dblclick.stop>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-accent hover:shadow-xs"
            title="新建子文件夹"
            @click.stop="emit('create-child', node)"
          >
            <SidebarIcon name="plus" class="h-3 w-3" />
          </button>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-accent hover:shadow-xs active:scale-95 transition-transform"
            :class="node.pinned ? 'text-accent' : ''"
            :title="node.pinned ? '取消置顶' : '置顶：排在同层目录最上方'"
            @click.stop="emit('toggle-pin', node)"
          >
            <SidebarIcon name="pin" class="h-3 w-3" />
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
      <div v-if="node.children.length > 0 && !collapsed.has(node.id)" class="ml-2 border-l border-line/70 pl-1">
        <FolderTree
          :nodes="node.children"
          :active-id="activeId"
          :depth="depth + 1"
          @select="(n) => emit('select', n)"
          @create-child="(n) => emit('create-child', n)"
          @edit="(n) => emit('edit', n)"
          @remove="(n) => emit('remove', n)"
          @toggle-pin="(n) => emit('toggle-pin', n)"
        />
      </div>
    </li>
  </ul>
</template>
