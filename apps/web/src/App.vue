<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import FolderTree from "./components/FolderTree.vue";
import NameDialog from "./components/NameDialog.vue";
import Stage0Panel from "./components/Stage0Panel.vue";
import type { FolderNode } from "./api/types";
import {
  createGeneralFolder,
  createProject,
  createProjectFolder,
  deleteFolder,
  deleteProject,
  library,
  loadAll,
  renameFolder,
  renameProject,
  updateManagedRoot
} from "./stores/library";

type DialogRequest =
  | { kind: "project-create" }
  | { kind: "project-rename"; projectId: number; initial: string }
  | { kind: "folder-create"; scope: "general" | "project"; projectId: number | null; parentId: number | null }
  | { kind: "folder-rename"; folderId: number; initial: string }
  | { kind: "root-edit" };

const dialog = ref<DialogRequest | null>(null);
const showStage0 = ref(false);
const activeScope = ref<"general" | "project">("general");
const activeProjectId = ref<number | null>(null);
const activeFolderId = ref<number | null>(null);

function findFolder(nodes: FolderNode[], id: number): FolderNode | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    const hit = findFolder(node.children, id);
    if (hit) return hit;
  }
  return null;
}

const activeFolder = computed<FolderNode | null>(() => {
  if (activeFolderId.value === null) return null;
  const nodes = activeScope.value === "general"
    ? library.generalTree
    : library.projectTrees[activeProjectId.value ?? -1] ?? [];
  return findFolder(nodes, activeFolderId.value);
});

const activeProject = computed(() =>
  activeProjectId.value === null ? null : library.projects.find((p) => p.id === activeProjectId.value) ?? null
);

const locationTitle = computed(() => {
  if (activeFolder.value) return activeFolder.value.name;
  if (activeScope.value === "project" && activeProject.value) return activeProject.value.name;
  return "通用资产库";
});

const dialogTitle = computed(() => {
  const d = dialog.value;
  if (!d) return "";
  switch (d.kind) {
    case "project-create": return "新建项目";
    case "project-rename": return "重命名项目";
    case "folder-create": return d.parentId === null ? "新建顶层文件夹" : "新建子文件夹";
    case "folder-rename": return "重命名文件夹";
    case "root-edit": return "修改默认托管存储位置";
  }
});

const dialogInitial = computed(() => {
  const d = dialog.value;
  if (d?.kind === "project-rename" || d?.kind === "folder-rename") return d.initial;
  if (d?.kind === "root-edit") return library.settings?.managed_root ?? "";
  return "";
});

function selectGeneral(): void {
  activeScope.value = "general";
  activeProjectId.value = null;
  activeFolderId.value = null;
}

function selectProject(id: number): void {
  activeScope.value = "project";
  activeProjectId.value = id;
  activeFolderId.value = null;
}

function selectFolder(node: FolderNode): void {
  activeScope.value = node.scope_type === "project" ? "project" : "general";
  activeProjectId.value = node.project_id;
  activeFolderId.value = node.id;
}

function askDeleteProject(id: number, name: string): void {
  if (window.confirm(`确定删除项目「${name}」吗？仅允许删除没有任何文件夹的空项目。`)) {
    void deleteProject(id);
  }
}

function askDeleteFolder(node: FolderNode): void {
  if (window.confirm(`确定删除文件夹「${node.name}」吗？只有空文件夹（无子目录、无资产）可以删除。`)) {
    void deleteFolder(node.id);
  }
}

async function onDialogConfirm(value: string): Promise<void> {
  const d = dialog.value;
  if (!d) return;
  let ok = false;
  switch (d.kind) {
    case "project-create":
      ok = await createProject(value);
      break;
    case "project-rename":
      ok = await renameProject(d.projectId, value);
      break;
    case "folder-create":
      ok = d.scope === "general"
        ? await createGeneralFolder(value, d.parentId)
        : await createProjectFolder(d.projectId ?? -1, value, d.parentId);
      break;
    case "folder-rename":
      ok = await renameFolder(d.folderId, value);
      break;
    case "root-edit":
      ok = await updateManagedRoot(value);
      break;
  }
  if (ok) dialog.value = null;
}

const rootStateLabel = computed(() => {
  switch (library.settings?.managed_root_state) {
    case "ok": return "可用";
    case "missing": return "目录未创建";
    case "unavailable": return "磁盘不可用";
    default: return "未知";
  }
});

onMounted(() => {
  void loadAll();
});
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-canvas text-ink">
    <aside class="flex w-64 shrink-0 flex-col border-r border-line bg-white">
      <div class="flex items-center gap-2.5 px-4 py-4">
        <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-ink text-xs font-semibold text-white">R.</div>
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold">Ryan_DAM</p>
          <p class="text-[11px] text-muted">本地数字资产库</p>
        </div>
      </div>

      <nav class="flex-1 overflow-y-auto px-2.5 pb-4">
        <section>
          <div class="flex items-center justify-between pl-1.5 pr-1 pb-1 pt-2">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted">通用资产库</p>
            <button
              class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-canvas hover:text-accent"
              title="新建顶层文件夹"
              @click="dialog = { kind: 'folder-create', scope: 'general', projectId: null, parentId: null }"
            >＋</button>
          </div>
          <button
            class="flex w-full items-center gap-1.5 rounded-lg px-1.5 py-1.5 text-left text-sm transition-colors"
            :class="activeScope === 'general' && activeFolderId === null ? 'bg-accent/10 font-medium text-accent' : 'hover:bg-canvas'"
            @click="selectGeneral"
          >全部资产</button>
          <FolderTree
            :nodes="library.generalTree"
            :active-id="activeScope === 'general' ? activeFolderId : null"
            @select="selectFolder"
            @create-child="(n) => (dialog = { kind: 'folder-create', scope: 'general', projectId: null, parentId: n.id })"
            @rename="(n) => (dialog = { kind: 'folder-rename', folderId: n.id, initial: n.name })"
            @remove="askDeleteFolder"
          />
        </section>

        <section class="mt-5">
          <div class="flex items-center justify-between pl-1.5 pr-1 pb-1 pt-2">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted">项目资产库</p>
            <button
              class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-canvas hover:text-accent"
              title="新建项目"
              @click="dialog = { kind: 'project-create' }"
            >＋</button>
          </div>
          <p v-if="library.projects.length === 0" class="px-1.5 py-1 text-xs leading-5 text-muted">
            还没有项目。点击「＋」创建第一个项目。
          </p>
          <div v-for="project in library.projects" :key="project.id" class="group/proj">
            <div
              class="flex items-center gap-1 rounded-lg px-1.5 py-1.5 text-sm transition-colors"
              :class="activeScope === 'project' && activeProjectId === project.id && activeFolderId === null ? 'bg-accent/10 font-medium text-accent' : 'hover:bg-canvas'"
              role="button"
              tabindex="0"
              @click="selectProject(project.id)"
              @keydown.enter="selectProject(project.id)"
            >
              <span class="min-w-0 flex-1 truncate">{{ project.name }}</span>
              <span class="hidden shrink-0 items-center gap-0.5 group-hover/proj:flex">
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-accent"
                  title="在项目顶层新建文件夹"
                  @click.stop="dialog = { kind: 'folder-create', scope: 'project', projectId: project.id, parentId: null }"
                >＋</button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-ink"
                  title="重命名项目"
                  @click.stop="dialog = { kind: 'project-rename', projectId: project.id, initial: project.name }"
                >✎</button>
                <button
                  class="flex h-5 w-5 items-center justify-center rounded text-xs text-muted hover:bg-white hover:text-rose-600"
                  title="删除空项目"
                  @click.stop="askDeleteProject(project.id, project.name)"
                >×</button>
              </span>
            </div>
            <div class="ml-3 border-l border-line pl-1">
              <FolderTree
                :nodes="library.projectTrees[project.id] ?? []"
                :active-id="activeScope === 'project' && activeProjectId === project.id ? activeFolderId : null"
                @select="selectFolder"
                @create-child="(n) => (dialog = { kind: 'folder-create', scope: 'project', projectId: project.id, parentId: n.id })"
                @rename="(n) => (dialog = { kind: 'folder-rename', folderId: n.id, initial: n.name })"
                @remove="askDeleteFolder"
              />
            </div>
          </div>
        </section>
      </nav>

      <div class="border-t border-line px-3.5 py-3">
        <div class="flex items-center justify-between">
          <p class="text-[11px] font-semibold uppercase tracking-wider text-muted">设置</p>
          <button
            class="rounded-lg px-2 py-1 text-xs text-accent transition hover:bg-canvas"
            @click="dialog = { kind: 'root-edit' }"
          >编辑</button>
        </div>
        <template v-if="library.settings">
          <p class="mt-1 truncate font-mono text-[11px] text-muted" :title="library.settings.managed_root">
            {{ library.settings.managed_root }}
          </p>
          <p class="mt-0.5 text-[11px]" :class="library.settings.managed_root_state === 'ok' ? 'text-emerald-700' : library.settings.managed_root_state === 'missing' ? 'text-amber-700' : 'text-rose-700'">
            {{ rootStateLabel }} · 仅影响新导入
          </p>
        </template>
        <button class="mt-2 text-xs text-muted transition hover:text-ink" @click="showStage0 = true">阶段 0 诊断…</button>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex h-14 shrink-0 items-center justify-between border-b border-line bg-white/80 px-6">
        <div class="min-w-0">
          <h1 class="truncate text-base font-semibold">{{ locationTitle }}</h1>
          <p class="text-[11px] text-muted">
            {{ activeScope === "general" ? "通用资产库" : activeProject?.name ?? "项目资产库" }}
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white opacity-50"
            title="导入功能将在阶段 2 提供"
            disabled
          >导入</button>
        </div>
      </header>

      <main class="flex flex-1 items-center justify-center px-8 pb-10">
        <div class="w-full max-w-md rounded-3xl border border-line bg-white p-10 text-center shadow-sm">
          <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-canvas text-2xl">🗂</div>
          <h2 class="mt-5 text-base font-semibold">
            {{ library.loaded ? "此目录还没有资产" : "正在连接本地服务…" }}
          </h2>
          <p class="mt-2 text-sm leading-6 text-muted">
            {{ library.loaded
              ? "文件导入、缩略图与画廊将在阶段 2/3 接入。当前阶段已打通目录树与本地数据库。"
              : "如果长时间未连接，请打开左下角的「阶段 0 诊断」检查本地服务。" }}
          </p>
        </div>
      </main>
    </div>

    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150"
        enter-from-class="opacity-0 -translate-y-1"
        leave-active-class="transition duration-150"
        leave-to-class="opacity-0 -translate-y-1"
      >
        <div
          v-if="library.notice"
          class="fixed left-1/2 top-4 z-[60] -translate-x-1/2 rounded-xl border px-4 py-2.5 text-sm shadow-soft"
          :class="library.notice.kind === 'error' ? 'border-rose-100 bg-rose-50 text-rose-700' : 'border-emerald-100 bg-emerald-50 text-emerald-700'"
        >
          {{ library.notice.text }}
        </div>
      </Transition>
    </Teleport>

    <NameDialog
      :open="dialog !== null"
      :title="dialogTitle"
      :initial="dialogInitial"
      :placeholder="dialog?.kind === 'root-edit' ? '例如 D:\\Ryan_DAM\\assets' : '输入名称'"
      :confirm-text="dialog?.kind === 'root-edit' ? '保存' : '确定'"
      @confirm="onDialogConfirm"
      @cancel="dialog = null"
    />

    <Stage0Panel v-if="showStage0" @close="showStage0 = false" />
  </div>
</template>
