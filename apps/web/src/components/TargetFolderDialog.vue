<script setup lang="ts">
import { computed, ref } from "vue";

export type TargetDialogRequest =
  | { kind: "external-link"; root: string }
  | { kind: "import-files" }
  | { kind: "import-folder" };

const props = defineProps<{
  request: TargetDialogRequest | null;
  options: { id: number; label: string }[];
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "pick", folderId: number): void;
  (e: "create-and-pick", name: string): void;
}>();

const newFolderDraft = ref("");

const title = computed(() => {
  switch (props.request?.kind) {
    case "external-link": return "选择库内目标目录";
    case "import-files": return "选择导入目标目录";
    case "import-folder": return "选择导入目标目录";
    default: return "";
  }
});

const hint = computed(() => {
  const req = props.request;
  if (!req) return "";
  if (req.kind === "external-link") {
    return `${req.root} 中的文件将索引到所选目录（保留子目录层级）；只读索引，源文件不会被修改或删除。`;
  }
  if (req.kind === "import-files") return "选择的文件将复制进所选目录的托管存储。";
  return "所选文件夹的子目录层级将镜像到目标目录下，文件复制进托管存储。";
});

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
            v-if="options.length > 0"
            class="max-h-52 overflow-y-auto rounded-xl border border-line p-1.5"
          >
            <button
              v-for="option in options"
              :key="option.id"
              class="block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-sm text-ink transition hover:bg-canvas hover:text-accent"
              :title="option.label"
              @click="emit('pick', option.id)"
            >
              {{ option.label }}
            </button>
          </div>

          <div class="rounded-xl border border-dashed border-line/80 bg-canvas/40 p-3">
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
