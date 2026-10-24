<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";

export type ConfirmIntent = "danger" | "warning" | "default";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    description?: string;
    confirmText?: string;
    cancelText?: string;
    intent?: ConfirmIntent;
  }>(),
  {
    description: "",
    confirmText: "确定",
    cancelText: "取消",
    intent: "default"
  }
);

const emit = defineEmits<{
  (e: "confirm"): void;
  (e: "cancel"): void;
}>();

const confirmButton = ref<HTMLButtonElement | null>(null);

function handleKeydown(e: KeyboardEvent): void {
  if (!props.open) return;
  if (e.key === "Escape") {
    e.preventDefault();
    emit("cancel");
  } else if (e.key === "Enter") {
    e.preventDefault();
    emit("confirm");
  }
}

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeydown);
});

watch(
  () => props.open,
  (val) => {
    if (val) {
      setTimeout(() => {
        confirmButton.value?.focus();
      }, 50);
    }
  }
);
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm px-6"
        @click.self="emit('cancel')"
      >
        <div
          class="relative w-full max-w-sm overflow-hidden rounded-2xl border border-white/40 bg-white/95 p-6 shadow-2xl backdrop-blur-xl transition-all sm:max-w-md animate-in fade-in zoom-in-95 duration-150"
          role="dialog"
          aria-modal="true"
        >
          <div class="flex items-start gap-4">
            <!-- Icon badges per intent -->
            <div
              v-if="intent === 'danger'"
              class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 ring-1 ring-rose-200/60"
            >
              <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </div>
            <div
              v-else-if="intent === 'warning'"
              class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 ring-1 ring-amber-200/60"
            >
              <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div
              v-else
              class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-accent ring-1 ring-blue-200/60"
            >
              <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>

            <!-- Content -->
            <div class="flex-1 min-w-0 pt-0.5">
              <h3 class="text-base font-semibold text-ink leading-snug">{{ title }}</h3>
              <p
                v-if="description"
                class="mt-2 text-sm leading-relaxed text-muted whitespace-pre-line"
              >
                {{ description }}
              </p>
            </div>
          </div>

          <!-- Actions -->
          <div class="mt-6 flex items-center justify-end gap-2.5">
            <button
              type="button"
              class="rounded-xl border border-line bg-white/80 px-4 py-2 text-sm font-medium text-ink/80 transition hover:bg-canvas hover:text-ink active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-black/10"
              @click="emit('cancel')"
            >
              {{ cancelText }}
            </button>
            <button
              ref="confirmButton"
              type="button"
              class="rounded-xl px-4 py-2 text-sm font-medium text-white shadow-sm transition active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-offset-1"
              :class="[
                intent === 'danger'
                  ? 'bg-rose-600 hover:bg-rose-700 focus:ring-rose-500 shadow-rose-500/20'
                  : intent === 'warning'
                  ? 'bg-amber-600 hover:bg-amber-700 focus:ring-amber-500 shadow-amber-500/20'
                  : 'bg-accent hover:bg-blue-700 focus:ring-accent shadow-accent/20'
              ]"
              @click="emit('confirm')"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
