<script setup lang="ts">
import { nextTick, ref, watch } from "vue";

const props = defineProps<{
  open: boolean;
  title: string;
  initial?: string;
  placeholder?: string;
  confirmText?: string;
}>();

const emit = defineEmits<{
  (e: "confirm", value: string): void;
  (e: "cancel"): void;
}>();

const value = ref("");
const input = ref<HTMLInputElement | null>(null);
const submitting = ref(false);

watch(
  () => props.open,
  async (open) => {
    if (!open) {
      submitting.value = false;
      return;
    }
    value.value = props.initial ?? "";
    await nextTick();
    input.value?.focus();
    input.value?.select();
  }
);

async function confirm(): Promise<void> {
  const cleaned = value.value.trim();
  if (!cleaned || submitting.value) return;
  submitting.value = true;
  try {
    emit("confirm", cleaned);
  } finally {
    // Parent closes the dialog on success; re-arm on failure after a tick.
    setTimeout(() => {
      submitting.value = false;
    }, 400);
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-ink/20 px-6" @click.self="emit('cancel')">
      <div class="w-full max-w-md rounded-2xl border border-line bg-white p-6 shadow-soft">
        <p class="text-base font-semibold">{{ title }}</p>
        <input
          ref="input"
          v-model="value"
          type="text"
          class="mt-4 w-full rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-sm outline-none transition focus:border-accent focus:bg-white"
          :placeholder="placeholder ?? '输入名称'"
          @keydown.enter="confirm"
          @keydown.esc="emit('cancel')"
        />
        <div class="mt-5 flex justify-end gap-2">
          <button class="rounded-xl px-4 py-2 text-sm text-muted transition hover:bg-canvas" @click="emit('cancel')">取消</button>
          <button
            class="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="value.trim().length === 0 || submitting"
            @click="confirm"
          >{{ confirmText ?? "确定" }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
