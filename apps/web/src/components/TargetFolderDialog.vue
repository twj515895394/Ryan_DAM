<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { FolderPickerNode } from "../composables/useFolderOptions";
import FolderPickerTree from "./FolderPickerTree.vue";

export type TargetDialogRequest =
  | { kind: "external-link"; root: string }
  | { kind: "import-files" }
  | { kind: "import-folder" };

const props = defineProps<{
  request: TargetDialogRequest | null;
  roots: FolderPickerNode[];
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "confirm", key: string, createMountFolder: boolean): void;
  (e: "create-and-pick", name: string): void;
}>();

const newFolderDraft = ref("");
// 默认：在所选节点下新建与磁盘目录同名的挂载目录；关闭后为旧行为（直接索进所选目录）
const createMount = ref(true);

watch(
  () => props.request,
  (req) => {
    if (req?.kind === "external-link") createMount.value = true;
  }
);

const isExternal = computed(() => props.request?.kind === "external-link");

const visibleRoots = computed<FolderPickerNode[]>(() => {
  if (isExternal.value && !createMount.value) {
    // 直接索引模式必须有具体目录承接，资产库/项目顶层置灰
    return props.roots.map((root) =>
      root.key.startsWith("folder:") ? root : { ...root, disabled: true }
    );
  }
  return props.roots;
});

const title = computed(() => (isExternal.value ? "选择库内目标目录" : "选择导入目标目录"));

const hint = computed(() => {
  const req = props.request;
  if (!req) return "";
  if (req.kind === "external-link") {
    return createMount.value
      ? `「${req.root}」将作为同名目录挂载到所选节点之下，内容保留其子目录层级；只读索引，源文件不会被修改或删除。`
      : `${req.root} 中的文件将直接索引到所选目录（保留子目录层级）；只读索引，源文件不会被修改或删除。`;
  }
  if (req.kind === "import-files") return "选择的文件将复制进所选目录的托管存储。";
  return "所选文件夹的子目录层级将镜像到目标目录下，文件复制进托管存储。";
});

function onSelect(node: FolderPickerNode): void {
  emit("confirm", node.key, createMount.value);
}

function handleCreate(): void {
  const name = newFolderDraft.value.trim();
  if (!name) return;
  emit("create-and-pick", name);
  newFolderDraft.value = "";
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="request !== null"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-xs"
      @click.self="emit('close')"
    >
      <div class="w-[460px] rounded-2xl border border-line bg-white p-5 shadow-soft">
        <h3 class="text-sm font-semibold text-ink">{{ title }}</h3>
        <p class="mt-1.5 break-all text-xs leading-5 text-muted">
          {{ hint }}
        </p>

        <div class="mt-3.5 space-y-3">
          <div
            v-if="visibleRoots.length === 0"
            class="rounded-xl border border-dashed border-line/80 bg-canvas/40 px-3 py-4 text-center text-xs text-muted"
          >
            {{ isExternal ? "库内还没有目录，直接选择上方的资产库或项目即可挂载" : "当前范围还没有目录，可在下方新建顶层目录" }}
          </div>
          <div v-else class="max-h-56 overflow-y-auto rounded-xl border border-line p-1.5">
            <FolderPickerTree :nodes="visibleRoots" @select="onSelect" />
          </div>

          <div
            v-if="isExternal"
            class="flex items-center justify-between gap-3 rounded-xl border border-line/80 bg-canvas/40 px-3 py-2.5"
          >
            <div class="min-w-0">
              <label class="block text-xs font-medium text-ink/80">在所选节点下新建同名目录</label>
              <p class="mt-0.5 text-[11px] leading-4 text-muted">
                {{ createMount
                  ? "关闭后不新建目录，内容直接索引进所选目录"
                  : "已关闭：请在上方选择一个具体目录" }}
              </p>
            </div>
            <button
              type="button"
              role="switch"
              :aria-checked="createMount"
              aria-label="在所选节点下新建同名目录"
              class="relative h-6 w-11 shrink-0 rounded-full transition-colors duration-200"
              :class="createMount ? 'bg-accent' : 'bg-black/15'"
              @click="createMount = !createMount"
            >
              <span
                class="absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-200"
                :class="createMount ? 'translate-x-5' : ''"
              />
            </button>
          </div>

          <div v-if="!isExternal" class="rounded-xl border border-dashed border-line/80 bg-canvas/40 p-3">
            <label class="block text-xs font-medium text-ink/80">或快速新建顶层目录并直接导入：</label>
            <div class="mt-2 flex gap-2">
              <input
                v-model="newFolderDraft"
                type="text"
                placeholder="输入新目录名称…"
                class="min-w-0 flex-1 rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none transition focus:border-accent"
                @keydown.enter.prevent="handleCreate"
              />
              <button
                type="button"
                class="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:opacity-40"
                :disabled="!newFolderDraft.trim()"
                @click="handleCreate"
              >
                创建并导入
              </button>
            </div>
          </div>
        </div>

        <div class="mt-4 flex justify-end">
          <button
            class="rounded-xl px-4 py-2 text-sm text-muted transition hover:bg-canvas hover:text-ink"
            @click="emit('close')"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
