<script setup lang="ts">
import { nextTick, ref, watch } from "vue";

import type { FolderEditPayload, FolderNode } from "../api/types";

const props = defineProps<{
  open: boolean;
  folder: FolderNode | null;
}>();

const emit = defineEmits<{
  (e: "save", payload: FolderEditPayload): void;
  (e: "cancel"): void;
}>();

const name = ref("");
const locked = ref(false);
const description = ref("");
const nameInput = ref<HTMLInputElement | null>(null);
const submitting = ref(false);

watch(
  () => [props.open, props.folder?.id] as const,
  async ([open]) => {
    if (!open || !props.folder) {
      submitting.value = false;
      return;
    }
    name.value = props.folder.name;
    locked.value = props.folder.locked;
    description.value = props.folder.description ?? "";
    await nextTick();
    nameInput.value?.focus();
    nameInput.value?.select();
  }
);

function confirm(): void {
  const cleaned = name.value.trim();
  if (!cleaned || submitting.value) return;
  submitting.value = true;
  try {
    emit("save", { name: cleaned, locked: locked.value, description: description.value.trim() || null });
  } finally {
    // 宿主成功后关闭弹窗；失败保留编辑现场，短暂防连点后重新武装
    setTimeout(() => {
      submitting.value = false;
    }, 400);
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-ink/20 px-6 backdrop-blur-[2px]" @click.self="emit('cancel')">
      <div class="w-full max-w-md rounded-2xl border border-line bg-white p-6 shadow-2xl">
        <p class="text-base font-semibold text-ink">编辑文件夹</p>

        <!-- 名称 -->
        <label class="mt-4 block text-xs font-medium text-muted">名称</label>
        <input
          ref="nameInput"
          v-model="name"
          type="text"
          maxlength="255"
          class="mt-1.5 w-full rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-sm outline-none transition focus:border-accent focus:bg-white"
          placeholder="输入文件夹名称"
          @keydown.enter="confirm"
          @keydown.esc="emit('cancel')"
        />

        <!-- 描述 / 备注 -->
        <label class="mt-4 block text-xs font-medium text-muted">描述</label>
        <textarea
          v-model="description"
          rows="3"
          maxlength="2000"
          class="mt-1.5 w-full resize-none rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-sm leading-relaxed outline-none transition focus:border-accent focus:bg-white"
          placeholder="为这个文件夹写点备注（可选）"
          @keydown.esc="emit('cancel')"
        />

        <!-- 锁定开关 -->
        <div class="mt-4 flex items-center justify-between gap-4 rounded-xl border border-line bg-canvas/70 px-3.5 py-3">
          <div class="min-w-0">
            <p class="text-sm font-medium text-ink">锁定此文件夹</p>
            <p class="mt-0.5 text-xs leading-relaxed" :class="locked ? 'text-amber-600' : 'text-muted'">
              {{ locked ? "已锁定：该文件夹不会被删除（含父级/项目级联删除）" : "锁定后此文件夹不会被删除，子目录与资产仍可单独管理" }}
            </p>
          </div>
          <button
            type="button"
            role="switch"
            :aria-checked="locked"
            aria-label="锁定此文件夹"
            class="relative h-6 w-11 shrink-0 rounded-full transition-colors duration-200"
            :class="locked ? 'bg-amber-500' : 'bg-black/15'"
            @click="locked = !locked"
          >
            <span
              class="absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-200"
              :class="locked ? 'translate-x-5' : ''"
            />
          </button>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button class="rounded-xl px-4 py-2 text-sm text-muted transition hover:bg-canvas" @click="emit('cancel')">取消</button>
          <button
            class="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="name.trim().length === 0 || submitting"
            @click="confirm"
          >保存</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
