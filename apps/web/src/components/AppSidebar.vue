<script setup lang="ts">
import { computed, ref } from "vue";
import FolderTree from "./FolderTree.vue";
import SidebarIcon from "./SidebarIcon.vue";
import { library } from "../stores/library";
import type { ExternalSource, FolderNode } from "../api/types";

const props = defineProps<{
  activeScope: "general" | "project";
  activeProjectId: number | null;
  activeFolderId: number | null;
  viewMode: "library" | "trash";
}>();

const emit = defineEmits<{
  (e: "select-general"): void;
  (e: "select-project", id: number): void;
  (e: "select-folder", node: FolderNode): void;
  (e: "select-trash"): void;
  (e: "create-folder", scope: "general" | "project", projectId: number | null, parentId: number | null): void;
  (e: "edit-folder", node: FolderNode): void;
  (e: "delete-folder", node: FolderNode): void;
  (e: "create-project"): void;
  (e: "rename-project", id: number, name: string): void;
  (e: "delete-project", id: number, name: string): void;
  (e: "link-external"): void;
  (e: "rescan-external", id: number): void;
  (e: "unlink-external", source: ExternalSource): void;
  (e: "create-tag"): void;
  (e: "rename-tag", id: number, name: string): void;
  (e: "delete-tag", id: number, name: string): void;
  (e: "open-settings"): void;
}>();

// ── 标签折叠与渐进式展开（优化问题 2）────────────────────────────────────
const isTagsExpanded = ref(true);
const showAllTags = ref(false);
const tagFilterQuery = ref("");

const filteredTags = computed(() => {
  const q = tagFilterQuery.value.trim().toLowerCase();
  if (!q) return library.tags;
  return library.tags.filter((t) => t.name.toLowerCase().includes(q));
});

const DEFAULT_TAG_LIMIT = 8;

const displayedTags = computed(() => {
  const isFiltering = tagFilterQuery.value.trim().length > 0;
  if (isFiltering || showAllTags.value) {
    return filteredTags.value;
  }
  return filteredTags.value.slice(0, DEFAULT_TAG_LIMIT);
});

const hasMoreTags = computed(() => {
  return tagFilterQuery.value.trim().length === 0 && library.tags.length > DEFAULT_TAG_LIMIT;
});

function toggleTagSelection(tagId: number): void {
  if (props.viewMode === "trash") {
    emit("select-general");
  }
  library.assetQuery.tagId = library.assetQuery.tagId === tagId ? null : tagId;
}
</script>

<template>
  <aside class="flex w-[var(--sidebar-w)] shrink-0 flex-col border-r border-line bg-canvas/40 backdrop-blur-sm">
    <div class="flex h-14 shrink-0 items-center justify-between border-b border-line px-4">
      <div class="flex items-center gap-2">
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-white shadow-xs">
          <SidebarIcon name="grid" class="h-4 w-4" />
        </div>
        <div>
          <h1 class="text-sm font-semibold tracking-tight text-ink">Ryan DAM</h1>
          <p class="text-[10.5px] leading-3 text-muted">个人 AI 资产管理器</p>
        </div>
      </div>
    </div>

    <nav class="flex-1 overflow-y-auto px-2 py-2">
      <!-- 通用资产库 -->
      <section class="space-y-0.5">
        <div class="flex items-center justify-between px-2 pb-0.5 pt-1">
          <span class="text-[11px] font-semibold uppercase tracking-wider text-muted/70">通用资产库</span>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-muted transition-colors hover:bg-black/5 hover:text-accent"
            title="新建顶层文件夹"
            @click="emit('create-folder', 'general', null, null)"
          >
            <SidebarIcon name="plus" class="h-3 w-3" />
          </button>
        </div>
        <button
          class="group flex h-6 w-full items-center gap-2 rounded-md px-2 text-left text-[13px] transition-colors duration-100"
          :class="activeScope === 'general' && activeFolderId === null && viewMode === 'library'
            ? 'bg-accent/10 font-medium text-accent'
            : 'text-ink/90 hover:bg-black/5'"
          @click="emit('select-general')"
        >
          <SidebarIcon
            name="grid"
            class="h-3.5 w-3.5 text-muted group-hover:text-ink/80"
            :class="activeScope === 'general' && activeFolderId === null && viewMode === 'library' ? 'text-accent' : ''"
          />
          <span class="min-w-0 flex-1 truncate">全部资产</span>
          <span v-if="library.assets && activeScope === 'general' && activeFolderId === null && viewMode === 'library'" class="text-[11px] text-muted">
            {{ library.assets.total }}
          </span>
        </button>
        <div class="pt-0.5">
          <FolderTree
            :nodes="library.generalTree"
            :active-id="activeScope === 'general' && viewMode === 'library' ? activeFolderId : null"
            @select="emit('select-folder', $event)"
            @create-child="emit('create-folder', 'general', null, $event.id)"
            @edit="emit('edit-folder', $event)"
            @remove="emit('delete-folder', $event)"
          />
        </div>
      </section>

      <!-- 项目资产库 -->
      <section class="mt-2.5 space-y-0.5">
        <div class="flex items-center justify-between px-2 pb-0.5 pt-0.5">
          <span class="text-[11px] font-semibold uppercase tracking-wider text-muted/70">项目</span>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-muted transition-colors hover:bg-black/5 hover:text-accent"
            title="新建项目"
            @click="emit('create-project')"
          >
            <SidebarIcon name="plus" class="h-3 w-3" />
          </button>
        </div>
        <div v-if="library.projects.length === 0" class="px-2 py-0.5 text-[11px] text-muted/60">
          暂无项目
        </div>
        <div v-for="project in library.projects" :key="project.id" class="group/proj">
          <div
            class="flex h-6 items-center gap-2 rounded-md px-2 text-[13px] transition-colors duration-100"
            :class="activeScope === 'project' && activeProjectId === project.id && activeFolderId === null && viewMode === 'library'
              ? 'bg-accent/10 font-medium text-accent'
              : 'text-ink/90 hover:bg-black/5'"
            role="button"
            tabindex="0"
            @click="emit('select-project', project.id)"
            @keydown.enter="emit('select-project', project.id)"
          >
            <SidebarIcon
              name="project"
              class="h-3.5 w-3.5 text-muted group-hover/proj:text-ink/80"
              :class="activeScope === 'project' && activeProjectId === project.id && activeFolderId === null && viewMode === 'library' ? 'text-accent' : ''"
            />
            <span class="min-w-0 flex-1 truncate" :title="project.name">{{ project.name }}</span>
            <span class="hidden shrink-0 items-center gap-0.5 group-hover/proj:flex">
              <button
                class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-accent hover:shadow-xs"
                title="新建子文件夹"
                @click.stop="emit('create-folder', 'project', project.id, null)"
              >
                <SidebarIcon name="plus" class="h-3 w-3" />
              </button>
              <button
                class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-ink hover:shadow-xs"
                title="重命名项目"
                @click.stop="emit('rename-project', project.id, project.name)"
              >
                <SidebarIcon name="edit" class="h-3 w-3" />
              </button>
              <button
                class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-rose-600 hover:shadow-xs"
                title="删除项目"
                @click.stop="emit('delete-project', project.id, project.name)"
              >
                <SidebarIcon name="close" class="h-3 w-3" />
              </button>
            </span>
          </div>
          <div class="ml-2 border-l border-line/70 pl-1">
            <FolderTree
              :nodes="library.projectTrees[project.id] ?? []"
              :active-id="activeScope === 'project' && activeProjectId === project.id && viewMode === 'library' ? activeFolderId : null"
              @select="emit('select-folder', $event)"
              @create-child="emit('create-folder', 'project', project.id, $event.id)"
              @edit="emit('edit-folder', $event)"
              @remove="emit('delete-folder', $event)"
            />
          </div>
        </div>
      </section>

      <!-- 外部目录关联 -->
      <section class="mt-2.5 space-y-0.5">
        <div class="flex items-center justify-between px-2 pb-0.5 pt-0.5">
          <span class="text-[11px] font-semibold uppercase tracking-wider text-muted/70">外部关联目录</span>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-muted transition-colors hover:bg-black/5 hover:text-accent"
            title="关联外部目录（索引现有文件，不复制源文件）"
            @click="emit('link-external')"
          >
            <SidebarIcon name="plus" class="h-3 w-3" />
          </button>
        </div>
        <div v-if="library.externalSources.length === 0" class="px-2 py-0.5 text-[11px] leading-4 text-muted/60">
          关联外部文件夹后，可在此统一检索和预览，不占用额外磁盘空间
        </div>
        <div v-for="source in library.externalSources" :key="source.id" class="group/src">
          <div
            class="flex h-6 items-center gap-2 rounded-md px-2 text-[12.5px] text-ink/90 transition-colors duration-100 hover:bg-black/5"
            :title="source.root_path"
          >
            <SidebarIcon name="folder" class="h-3.5 w-3.5 text-amber-600 shrink-0" />
            <span class="min-w-0 flex-1 truncate">{{ source.display_name ?? source.root_path }}</span>
            <span class="text-[11px] text-muted">{{ source.asset_count }}</span>
            <span class="hidden shrink-0 items-center gap-0.5 group-hover/src:flex">
              <button
                class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-accent hover:shadow-xs"
                title="重新扫描（检测新增/变更/失效）"
                @click.stop="emit('rescan-external', source.id)"
              >
                <SidebarIcon name="refresh" class="h-3 w-3" />
              </button>
              <button
                class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-rose-600 hover:shadow-xs"
                title="解除关联（只移除索引，不删除源文件）"
                @click.stop="emit('unlink-external', source)"
              >
                <SidebarIcon name="close" class="h-3 w-3" />
              </button>
            </span>
          </div>
          <p v-if="source.missing_count > 0" class="px-2 text-[10.5px] leading-4 text-amber-700">
            {{ source.missing_count }} 项源文件失效
          </p>
        </div>
      </section>

      <!-- 标签管理（优化问题 2：支持折叠、截断与快速过滤） -->
      <section class="mt-2.5 space-y-0.5">
        <div class="flex items-center justify-between px-2 pb-0.5 pt-0.5">
          <button
            type="button"
            class="flex items-center gap-1.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted/70 hover:text-ink transition-colors"
            @click="isTagsExpanded = !isTagsExpanded"
          >
            <SidebarIcon
              name="chevron-right"
              class="h-3 w-3 transition-transform duration-150"
              :class="isTagsExpanded ? 'rotate-90' : ''"
            />
            <span>标签</span>
            <span v-if="library.tags.length > 0" class="text-[10px] text-muted/80">({{ library.tags.length }})</span>
          </button>
          <button
            class="flex h-5 w-5 items-center justify-center rounded text-muted transition-colors hover:bg-black/5 hover:text-accent"
            title="新建标签"
            @click="emit('create-tag')"
          >
            <SidebarIcon name="plus" class="h-3 w-3" />
          </button>
        </div>

        <div v-show="isTagsExpanded" class="space-y-0.5 pt-0.5">
          <!-- 标签搜索过滤输入框（当标签总数 > 8 时提供） -->
          <div v-if="library.tags.length > DEFAULT_TAG_LIMIT" class="px-2 py-1">
            <div class="relative">
              <input
                v-model="tagFilterQuery"
                type="text"
                placeholder="快速筛选标签…"
                class="w-full rounded-md border border-line bg-white px-2 py-1 pr-6 text-xs text-ink outline-none transition placeholder:text-muted/50 focus:border-accent"
              />
              <button
                v-if="tagFilterQuery"
                type="button"
                class="absolute right-1 top-1/2 -translate-y-1/2 p-0.5 text-muted hover:text-ink"
                @click="tagFilterQuery = ''"
              >
                <SidebarIcon name="close" class="h-2.5 w-2.5" />
              </button>
            </div>
          </div>

          <div v-if="library.tags.length === 0" class="px-2 py-0.5 text-[11px] text-muted/60">
            暂无标签
          </div>

          <div v-else-if="displayedTags.length === 0" class="px-2 py-1 text-[11px] text-muted/60">
            无匹配标签
          </div>

          <div v-for="tag in displayedTags" :key="tag.id" class="group/tag">
            <div
              class="flex h-6 items-center gap-2 rounded-md px-2 text-[12.5px] transition-colors duration-100"
              :class="library.assetQuery.tagId === tag.id ? 'bg-accent/10 font-medium text-accent' : 'text-ink/90 hover:bg-black/5'"
              role="button"
              tabindex="0"
              @click="toggleTagSelection(tag.id)"
              @keydown.enter="toggleTagSelection(tag.id)"
            >
              <SidebarIcon
                name="tag"
                class="h-3 w-3 text-muted group-hover/tag:text-ink/80"
                :class="library.assetQuery.tagId === tag.id ? 'text-accent' : ''"
              />
              <span class="min-w-0 flex-1 truncate" :title="tag.name">{{ tag.name }}</span>
              <span class="text-[11px] text-muted">{{ tag.asset_count }}</span>
              <span class="hidden shrink-0 items-center gap-0.5 group-hover/tag:flex">
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-ink hover:shadow-xs"
                  title="重命名标签"
                  @click.stop="emit('rename-tag', tag.id, tag.name)"
                >
                  <SidebarIcon name="edit" class="h-3 w-3" />
                </button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-white hover:text-rose-600 hover:shadow-xs"
                  title="删除标签"
                  @click.stop="emit('delete-tag', tag.id, tag.name)"
                >
                  <SidebarIcon name="close" class="h-3 w-3" />
                </button>
              </span>
            </div>
          </div>

          <!-- 渐进式展开/收起按钮 -->
          <div v-if="hasMoreTags" class="px-2 pt-1 pb-0.5">
            <button
              type="button"
              class="flex items-center gap-1 text-[11.5px] font-medium text-accent hover:text-blue-700 transition-colors"
              @click="showAllTags = !showAllTags"
            >
              <span>{{ showAllTags ? "收起" : `展开更多 (${library.tags.length - DEFAULT_TAG_LIMIT})` }}</span>
              <SidebarIcon
                name="chevron-right"
                class="h-2.5 w-2.5 transition-transform duration-150"
                :class="showAllTags ? '-rotate-90' : 'rotate-90'"
              />
            </button>
          </div>
        </div>
      </section>

      <!-- 回收站：独立且清晰的系统入口 -->
      <section class="mt-3 border-t border-line/60 pt-1.5 space-y-0.5">
        <button
          class="group flex h-6 w-full items-center gap-2 rounded-md px-2 text-left text-[13px] transition-colors duration-100"
          :class="viewMode === 'trash' ? 'bg-accent/10 font-medium text-accent' : 'text-ink/90 hover:bg-black/5'"
          @click="emit('select-trash')"
        >
          <SidebarIcon
            name="trash"
            class="h-3.5 w-3.5 text-muted group-hover:text-ink/80"
            :class="viewMode === 'trash' ? 'text-accent' : ''"
          />
          <span class="min-w-0 flex-1 truncate">回收站</span>
          <span
            v-if="library.trash.length > 0"
            class="shrink-0 rounded-full px-1.5 py-0.5 text-[10.5px] font-medium leading-none"
            :class="viewMode === 'trash' ? 'bg-accent/15 text-accent' : 'bg-black/5 text-muted'"
          >
            {{ library.trash.length }}
          </span>
        </button>
      </section>
    </nav>

    <!-- 底部偏好设置入口 -->
    <div class="border-t border-line/60 p-1.5">
      <button
        class="flex w-full items-center gap-2 rounded-md px-2.5 py-1 text-[12.5px] text-ink/80 transition-colors duration-100 hover:bg-black/5"
        @click="emit('open-settings')"
      >
        <SidebarIcon name="settings" class="h-3.5 w-3.5 text-muted" />
        <span class="flex-1 text-left">偏好设置与存储</span>
        <span
          class="h-2 w-2 rounded-full"
          :class="library.settings?.managed_root_state === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'"
        />
      </button>
    </div>
  </aside>
</template>
